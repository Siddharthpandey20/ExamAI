"""
ingestion_helper.py — PYQ-specific text extraction from scanned exam papers.

PYQ papers are almost always scanned images or camera photos in a PDF.
Unlike lecture slides, they rarely have native text or structured tables.

Pipeline (purpose-built for PYQ):

  Stage 1 — Native Text + Page Rendering
    PyMuPDF extracts any native text (rare for scanned papers).
    Each page is also rendered as a high-res image for OCR.

  Stage 2 — OCR Every Page
    PaddleOCR runs on all rendered page images in parallel.
    This is the primary text source for scanned PYQs.

  (No Stage 3 — table extraction is not useful on OCR text from scans)

Returns a list of page dicts with: page_num, native_text, ocr_text
"""

import os
import io
import tempfile
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import fitz  # PyMuPDF

log = logging.getLogger(__name__)

# ── OCR setup (reuses the singleton from ingestion) ──────────────────

_ocr_instance = None
_ocr_lock = threading.Lock()


def _get_ocr():
    """Lazy-init PaddleOCR singleton (thread-safe)."""
    global _ocr_instance
    if _ocr_instance is None:
        with _ocr_lock:
            if _ocr_instance is None:
                os.environ["FLAGS_use_mkldnn"] = "0"
                os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
                from paddleocr import PaddleOCR
                _ocr_instance = PaddleOCR(
                    lang="en",
                    use_doc_orientation_classify=False,
                    use_doc_unwarping=False,
                    use_textline_orientation=False,
                    enable_mkldnn=False,
                )
    return _ocr_instance


def _ocr_page_image(page_png_bytes: bytes, page_num: int) -> str:
    """
    Run PaddleOCR on a rendered page image.
    Returns cleaned text string.
    """
    if not page_png_bytes:
        return ""

    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    try:
        tmp.write(page_png_bytes)
        tmp.close()

        ocr = _get_ocr()
        results = ocr.predict(tmp.name)

        lines = []
        for res in results:
            texts = res.get("rec_texts", [])
            scores = res.get("rec_scores", [])
            for txt, score in zip(texts, scores):
                if score >= 0.4 and txt.strip():
                    lines.append(txt.strip())

        return "\n".join(lines)
    except Exception as e:
        log.error(f"[PYQ OCR] Page {page_num} failed: {e}")
        return ""
    finally:
        os.unlink(tmp.name)


# ── Stage 1: Native text + render pages as images ────────────────────

def _stage1_parse_and_render(filepath: str) -> list[dict]:
    """
    Extract native text from each page AND render each page as a PNG
    for OCR. Returns list of dicts with: page_num, native_text, page_image.
    """
    doc = fitz.open(filepath)
    pages = []

    # Render at 2x zoom for better OCR accuracy on scanned docs
    zoom = 2.0
    matrix = fitz.Matrix(zoom, zoom)

    for page_num, page in enumerate(doc, start=1):
        # Native text (usually empty for scanned PYQs)
        native_text = page.get_text("text").strip()

        # Render page to PNG image
        pix = page.get_pixmap(matrix=matrix)
        page_image = pix.tobytes("png")

        pages.append({
            "page_num": page_num,
            "native_text": native_text,
            "page_image": page_image,
        })

        has_text = "text" if native_text else "no-text"
        log.info(f"  [Stage 1] Page {page_num}: {has_text}, rendered {pix.width}x{pix.height}")

    doc.close()
    log.info(f"  [Stage 1] {len(pages)} pages parsed and rendered")
    return pages


# ── Stage 2: OCR all page images in parallel ─────────────────────────

def _stage2_ocr_pages(pages: list[dict], max_workers: int = 3) -> list[dict]:
    """
    Run PaddleOCR on every rendered page image in parallel.
    Adds 'ocr_text' key to each page dict.
    """
    log.info(f"  [Stage 2] Running OCR on {len(pages)} pages (parallel, workers={max_workers})")

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_map = {
            pool.submit(_ocr_page_image, p["page_image"], p["page_num"]): i
            for i, p in enumerate(pages)
        }

        done = 0
        for future in as_completed(future_map):
            idx = future_map[future]
            done += 1
            try:
                ocr_text = future.result(timeout=180)
                pages[idx]["ocr_text"] = ocr_text
                chars = len(ocr_text)
                log.info(f"  [Stage 2] Page {pages[idx]['page_num']} [{done}/{len(pages)}]: {chars} chars")
            except Exception as e:
                pages[idx]["ocr_text"] = ""
                log.error(f"  [Stage 2] Page {pages[idx]['page_num']} [{done}/{len(pages)}]: FAIL {e}")

    # Drop the heavy image bytes — no longer needed
    for p in pages:
        p.pop("page_image", None)

    total_chars = sum(len(p.get("ocr_text", "")) for p in pages)
    log.info(f"  [Stage 2] OCR complete: {total_chars} total chars from {len(pages)} pages")
    return pages


# ── Public API ────────────────────────────────────────────────────────

def extract_pyq_text(filepath: str) -> list[dict]:
    """
    PYQ-specific text extraction pipeline.

    Stage 1: Parse native text + render each page as high-res image
    Stage 2: OCR every page image in parallel

    Parameters
    ----------
    filepath : str
        Path to the PYQ PDF.

    Returns
    -------
    list[dict]
        Each dict has: page_num, native_text, ocr_text
    """
    fname = os.path.basename(filepath)
    log.info(f"[PYQ Ingest] Starting: {fname}")

    log.info(f"[PYQ Ingest] Stage 1: Parse + render pages")
    pages = _stage1_parse_and_render(filepath)

    if not pages:
        log.warning(f"[PYQ Ingest] No pages found in {fname}")
        return []

    log.info(f"[PYQ Ingest] Stage 2: OCR all pages")
    pages = _stage2_ocr_pages(pages)

    log.info(f"[PYQ Ingest] Done: {fname} — {len(pages)} pages processed")
    return pages