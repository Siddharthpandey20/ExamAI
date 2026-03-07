"""
ocr_engine.py — PaddleOCR 3.4.0 wrapper for extracting text from images.

Accepts raw image bytes and returns recognized text.
Includes post-processing to strip OCR garbage before output.
Designed to be called in parallel from pipeline.py.
"""

import os
import io
import re
import tempfile

# ── Must be set BEFORE any paddle / paddleocr import ─────────────────
os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

import numpy as np
from PIL import Image
import threading
from concurrent.futures import ThreadPoolExecutor

from ingestion.config import OCR_LANG

# Thread-safe lazy-initialized singleton — PaddleOCR is heavy to instantiate.
_ocr_instance = None
_ocr_lock = threading.Lock()


def _get_ocr():
    global _ocr_instance
    if _ocr_instance is None:
        with _ocr_lock:
            if _ocr_instance is None:
                from paddleocr import PaddleOCR
                _ocr_instance = PaddleOCR(
                    lang=OCR_LANG,
                    use_doc_orientation_classify=False,
                    use_doc_unwarping=False,
                    use_textline_orientation=False,
                    enable_mkldnn=False,
                )
    return _ocr_instance


# ── OCR Garbage Filters ──────────────────────────────────────────────

# Patterns that indicate OCR noise (applied per-line)
_GARBAGE_PATTERNS = [
    re.compile(r"^[A-F0-9]{5,}$"),          # hex strings like EFFFFFFE
    re.compile(r"^[\*\#\=\-\~\+]{3,}$"),    # repeated symbols: *****, ====, ----
    re.compile(r"^[^a-zA-Z0-9]{3,}$"),       # lines of only special chars
    re.compile(r"^(.)\1{4,}$"),              # single char repeated 5+ times
    re.compile(r"^[\s\d]{1,3}$"),            # stray 1-3 digit/space tokens
    re.compile(r"^[A-Z0-9\s]{1,2}$"),        # 1-2 char uppercase noise
]


def _clean_ocr_text(raw: str) -> str:
    """Remove OCR garbage lines from raw OCR output."""
    if not raw:
        return ""

    cleaned_lines = []
    for line in raw.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue

        # Skip lines matching any garbage pattern
        is_garbage = False
        for pat in _GARBAGE_PATTERNS:
            if pat.match(stripped):
                is_garbage = True
                break

        if not is_garbage:
            cleaned_lines.append(stripped)

    return "\n".join(cleaned_lines)


def ocr_image_bytes(image_bytes: bytes) -> str:
    """
    Run OCR on raw image bytes.
    Returns cleaned extracted text as a single string.
    """
    if not image_bytes:
        return ""

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    # Skip tiny images (icons, bullets, decorations)
    w, h = img.size
    if w < 50 or h < 50:
        return ""

    # PaddleOCR 3.4 predict() works reliably with file paths on Windows
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    try:
        img.save(tmp.name)
        tmp.close()

        ocr = _get_ocr()
        results = ocr.predict(tmp.name)

        lines = []
        for res in results:
            # PaddleOCR 3.4 returns OCRResult (dict-like) with rec_texts key
            texts = res.get("rec_texts", [])
            scores = res.get("rec_scores", [])
            # Filter out low-confidence detections
            for txt, score in zip(texts, scores):
                if score >= 0.5:
                    lines.append(txt)

        raw_text = "\n".join(lines)
        return _clean_ocr_text(raw_text)

    except Exception as e:
        print(f"[OCR] Failed: {e}")
        return ""
    finally:
        os.unlink(tmp.name)


def ocr_image_bytes_with_layout(image_bytes: bytes) -> dict:
    """
    Run OCR and return structured result with text, scores, and bboxes.
    Used for detecting if image contains a table layout.
    """
    if not image_bytes:
        return {"text": "", "lines": [], "is_table_like": False}

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = img.size
    if w < 50 or h < 50:
        return {"text": "", "lines": [], "is_table_like": False}

    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    try:
        img.save(tmp.name)
        tmp.close()

        ocr = _get_ocr()
        results = ocr.predict(tmp.name)

        entries = []
        for res in results:
            texts = res.get("rec_texts", [])
            scores = res.get("rec_scores", [])
            polys = res.get("dt_polys", [])

            for txt, score, poly in zip(texts, scores, polys):
                if score >= 0.5:
                    # Get y-center of the text box for row grouping
                    y_vals = [p[1] for p in poly]
                    y_center = sum(y_vals) / len(y_vals) if y_vals else 0
                    x_vals = [p[0] for p in poly]
                    x_center = sum(x_vals) / len(x_vals) if x_vals else 0
                    entries.append({
                        "text": txt.strip(),
                        "y": float(y_center),
                        "x": float(x_center),
                        "score": float(score),
                    })

        # Detect table-like layout: multiple rows with aligned columns
        is_table = _detect_table_layout(entries, h)
        clean_text = _clean_ocr_text("\n".join(e["text"] for e in entries))

        return {
            "text": clean_text,
            "lines": entries,
            "is_table_like": is_table,
        }

    except Exception as e:
        print(f"[OCR] Layout extraction failed: {e}")
        return {"text": "", "lines": [], "is_table_like": False}
    finally:
        os.unlink(tmp.name)


def _detect_table_layout(entries: list[dict], img_height: int) -> bool:
    """
    Heuristic: if OCR entries cluster into 4+ distinguishable rows
    with 2+ columns, it's likely a table image.
    """
    if len(entries) < 6:
        return False

    # Group by Y coordinate (rows), tolerance = 2% of image height
    tolerance = max(img_height * 0.02, 8)
    rows: list[list[dict]] = []
    sorted_entries = sorted(entries, key=lambda e: e["y"])

    current_row = [sorted_entries[0]]
    for e in sorted_entries[1:]:
        if abs(e["y"] - current_row[-1]["y"]) < tolerance:
            current_row.append(e)
        else:
            rows.append(current_row)
            current_row = [e]
    rows.append(current_row)

    # Table-like if 4+ rows and at least half have 2+ items
    multi_col_rows = sum(1 for r in rows if len(r) >= 2)
    return len(rows) >= 4 and multi_col_rows >= len(rows) * 0.5


def _is_garbage_cell(text: str) -> bool:
    """Check if a table cell is OCR garbage."""
    stripped = text.strip()
    if not stripped:
        return False
    for pat in _GARBAGE_PATTERNS:
        if pat.match(stripped):
            return True
    return False


def build_table_from_ocr(entries: list[dict], img_height: int) -> list[list[str]]:
    """
    Given OCR entries with x,y positions, reconstruct a table grid.
    Returns list of rows, each row is a list of cell strings.
    Filters out garbage cells.
    """
    if not entries:
        return []

    tolerance = max(img_height * 0.02, 8)
    sorted_entries = sorted(entries, key=lambda e: e["y"])

    # Group into rows by Y
    rows: list[list[dict]] = []
    current_row = [sorted_entries[0]]
    for e in sorted_entries[1:]:
        if abs(e["y"] - current_row[-1]["y"]) < tolerance:
            current_row.append(e)
        else:
            rows.append(current_row)
            current_row = [e]
    rows.append(current_row)

    # Sort each row by X, filter garbage cells
    table = []
    for row in rows:
        sorted_row = sorted(row, key=lambda e: e["x"])
        cleaned_cells = [e["text"] for e in sorted_row if not _is_garbage_cell(e["text"])]
        if cleaned_cells:  # skip entirely empty/garbage rows
            table.append(cleaned_cells)

    return table


def ocr_image_list(image_blocks: list[dict]) -> list[str]:
    """
    Run OCR on a list of image block dicts (each has 'image_bytes').
    Returns list of extracted text strings (same order).
    """
    if not image_blocks:
        return []
    with ThreadPoolExecutor() as executor:
        results = list(
            executor.map(lambda b: ocr_image_bytes(b.get("image_bytes", b"")), image_blocks)
        )
    return results
