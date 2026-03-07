"""
pipeline.py — Orchestrates the full ingestion pipeline for a single file.

Architecture (each stage is explicit and logged):

    PDF / PPTX
        │
        ▼
    Stage 1 — Native Parsing       (PyMuPDF / python-pptx)
        │
        ▼
    Stage 2 — Block Segmentation   (text / image / table regions per page)
        │
        ▼
    Stage 3 — Specialized Extraction (ALL pages in parallel)
        ├── OCR with layout detection on image blocks  (ThreadPool)
        ├── Camelot table extraction on flagged pages   (ThreadPool)
        └── Native text kept as-is
        │
        ▼
    Stage 4 — Unified Block Merge  (per-page: native text + OCR text + tables)
        │   - Table images → reconstructed markdown tables
        │   - Diagram-only pages → flagged with description
        │   - Text images → cleaned OCR text
        │
        ▼
    Stage 5 — AI Cleanup           (Ollama Llama3, ONLY on native text)
        │   - OCR text NOT sent to AI (avoids hallucination)
        │   - AI cleans only reliably parsed native text
        │
        ▼
    Stage 6 — Markdown Generation

This module is called by the anchor (__init__.py) for each unprocessed file.
"""

import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from ingestion.config import MAX_WORKERS
from ingestion.parser_pdf import parse_pdf
from ingestion.parser_pptx import parse_pptx
from ingestion.ocr_engine import ocr_image_bytes_with_layout, build_table_from_ocr
from ingestion.table_extractor import extract_tables_from_pdf
from ingestion.ai_cleanup import cleanup_text
from ingestion.md_writer import write_markdown


# ═══════════════════════════════════════════════════════════════════════
# Stage 2 — Block Segmentation
# ═══════════════════════════════════════════════════════════════════════

def _segment_pages(raw_pages: list[dict]) -> dict:
    """
    Classify every page into text blocks, image blocks, and table hints.
    Returns work-lists for Stage 3.
    """
    text_map: dict[int, list[str]] = {}
    ocr_jobs: list[tuple[int, int, bytes]] = []
    table_pages: list[int] = []

    total_text = 0
    total_img = 0
    total_tbl = 0

    for page in raw_pages:
        pnum = page["page_num"]
        n_text = len(page["text_blocks"])
        n_img = len(page["image_blocks"])
        has_tbl = page.get("has_tables", False)

        total_text += n_text
        total_img += n_img
        if has_tbl:
            total_tbl += 1

        # Build tag for logging
        parts = []
        if n_text:
            parts.append(f"text={n_text}")
        if n_img:
            parts.append(f"img={n_img}")
        if has_tbl:
            parts.append("TABLE-HINT")
        pptx_tables = page.get("table_data", [])
        if pptx_tables:
            parts.append(f"pptx-tbl={len(pptx_tables)}")
        if not n_text and n_img:
            parts.append("IMAGE-ONLY")

        print(f"  [SEG] Page {pnum:>3}  | {' '.join(parts)}")

        text_map[pnum] = [b["text"] for b in page["text_blocks"]]

        for idx, img_block in enumerate(page["image_blocks"]):
            ocr_jobs.append((pnum, idx, img_block.get("image_bytes", b"")))

        if has_tbl:
            table_pages.append(pnum)

    print(f"  [SEG] --------------------------------------------------")
    print(f"  [SEG] Total: {len(raw_pages)} pages, "
          f"{total_text} text blocks, {total_img} image blocks, "
          f"{total_tbl} pages with table hints")

    return {
        "text_map": text_map,
        "ocr_jobs": ocr_jobs,
        "table_pages": table_pages,
    }


# ═══════════════════════════════════════════════════════════════════════
# Stage 3 — Parallel Specialized Extraction
# ═══════════════════════════════════════════════════════════════════════

def _run_ocr_parallel(ocr_jobs: list[tuple[int, int, bytes]]) -> dict:
    """
    Run OCR with layout detection on ALL image blocks in parallel.

    Returns {
        page_num: [
            {"text": str, "lines": list, "is_table_like": bool, "img_height": int},
            ...
        ]
    }
    """
    if not ocr_jobs:
        print("[OCR ] No image blocks to OCR.")
        return {}

    print(f"[OCR ] Submitting {len(ocr_jobs)} image blocks to PaddleOCR (parallel)...")

    results: dict[int, list[dict]] = {}

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        future_map = {}
        for pnum, idx, img_bytes in ocr_jobs:
            fut = pool.submit(ocr_image_bytes_with_layout, img_bytes)
            future_map[fut] = (pnum, idx, img_bytes)

        done = 0
        for fut in as_completed(future_map):
            pnum, idx, img_bytes = future_map[fut]
            done += 1
            try:
                ocr_result = fut.result(timeout=120)
                # Attach image height for table reconstruction
                from PIL import Image
                import io
                try:
                    img = Image.open(io.BytesIO(img_bytes))
                    ocr_result["img_height"] = img.size[1]
                except Exception:
                    ocr_result["img_height"] = 500

                results.setdefault(pnum, []).append(ocr_result)

                text = ocr_result["text"]
                kind = "TABLE" if ocr_result["is_table_like"] else "TEXT"
                snippet = text[:50].replace("\n", " ") if text.strip() else "(empty)"
                print(f"[OCR ] Page {pnum} img#{idx}  [{done}/{len(ocr_jobs)}]  "
                      f"{kind}  {snippet}")
            except Exception as e:
                results.setdefault(pnum, []).append(
                    {"text": "", "lines": [], "is_table_like": False, "img_height": 500}
                )
                print(f"[OCR ] Page {pnum} img#{idx}  [{done}/{len(ocr_jobs)}]  FAIL: {e}")

    table_imgs = sum(
        1 for page_results in results.values()
        for r in page_results if r["is_table_like"]
    )
    print(f"[OCR ] Done: {done} images processed, {table_imgs} detected as tables.")
    return results


def _run_tables_parallel(filepath: str, table_pages: list[int]) -> dict[int, list]:
    """
    Run Camelot table extraction on ALL flagged pages in parallel.
    Returns {page_num: [table1, table2, ...]}
    """
    if not table_pages:
        print("[TBL ] No pages flagged for Camelot table extraction.")
        return {}

    print(f"[TBL ] Submitting {len(table_pages)} page(s) to Camelot (parallel)...")

    results: dict[int, list] = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        future_map = {
            pool.submit(extract_tables_from_pdf, filepath, pn): pn
            for pn in table_pages
        }

        done = 0
        for fut in as_completed(future_map):
            pn = future_map[fut]
            done += 1
            try:
                tables = fut.result(timeout=120)
                results[pn] = tables
                print(f"[TBL ] Page {pn}  [{done}/{len(table_pages)}]  "
                      f"{len(tables)} table(s) found")
            except Exception as e:
                results[pn] = []
                print(f"[TBL ] Page {pn}  [{done}/{len(table_pages)}]  FAIL: {e}")

    total = sum(len(v) for v in results.values())
    print(f"[TBL ] Done: {total} table(s) extracted from {done} pages.")
    return results


# ═══════════════════════════════════════════════════════════════════════
# Stage 4 — Unified Block Merge
# ═══════════════════════════════════════════════════════════════════════

def _merge_blocks(
    raw_pages: list[dict],
    text_map: dict[int, list[str]],
    ocr_results: dict[int, list[dict]],
    table_results: dict[int, list],
) -> list[dict]:
    """
    Merge native text + OCR results + Camelot tables per page.

    Key decisions:
      - OCR images detected as tables -> reconstructed into table grids
      - OCR images with text -> kept as separate OCR text (not mixed with native)
      - Diagram-only pages (no text, only images with little OCR) -> flagged
      - Camelot tables take priority over OCR-reconstructed tables
    """
    merged = []

    for page in raw_pages:
        pnum = page["page_num"]

        native_text = "\n\n".join(text_map.get(pnum, []))
        page_ocr = ocr_results.get(pnum, [])

        # Separate OCR results into table-images and text-images
        ocr_text_parts = []
        ocr_tables = []

        for ocr_res in page_ocr:
            if ocr_res["is_table_like"] and ocr_res["lines"]:
                tbl = build_table_from_ocr(ocr_res["lines"], ocr_res["img_height"])
                if tbl and len(tbl) >= 2:
                    ocr_tables.append(tbl)
                    print(f"  [MERGE] Page {pnum}: image -> table ({len(tbl)} rows)")
                else:
                    if ocr_res["text"].strip():
                        ocr_text_parts.append(ocr_res["text"])
            else:
                if ocr_res["text"].strip():
                    ocr_text_parts.append(ocr_res["text"])

        ocr_combined = "\n".join(ocr_text_parts)

        # Tables: Camelot > PPTX > OCR-reconstructed
        camelot_tables = table_results.get(pnum, [])
        pptx_tables = page.get("table_data", [])
        all_tables = pptx_tables + camelot_tables + ocr_tables

        # Detect diagram-only pages (image with little/no text)
        is_diagram = (
            not native_text.strip()
            and len(page["image_blocks"]) > 0
            and len(ocr_combined.strip()) < 30
            and not all_tables
        )

        merged.append({
            "page_num": pnum,
            "native_text": native_text,
            "ocr_text": ocr_combined,
            "tables": all_tables,
            "is_diagram": is_diagram,
        })

    n_diagrams = sum(1 for m in merged if m["is_diagram"])
    n_tables = sum(len(m["tables"]) for m in merged)
    print(f"[MERGE] {len(merged)} pages merged: {n_tables} tables, {n_diagrams} diagram pages.")
    return merged


# ═══════════════════════════════════════════════════════════════════════
# Stage 5 — AI Cleanup (ONLY on native text, NOT OCR text)
# ═══════════════════════════════════════════════════════════════════════

def _run_ai_cleanup(merged_pages: list[dict]) -> list[dict]:
    """
    Send ONLY native text (not OCR) to Ollama for cleanup.
    This prevents the AI from hallucinating on noisy OCR content.
    """
    pages_with_text = [
        (i, p) for i, p in enumerate(merged_pages)
        if p["native_text"].strip()
    ]

    if not pages_with_text:
        print("[AI  ] No native text to clean.")
        for p in merged_pages:
            p["cleaned_text"] = ""
        return merged_pages

    print(f"[AI  ] Sending {len(pages_with_text)} page(s) native text to Llama3 "
          f"(parallel, max_workers={MAX_WORKERS})...")

    cleaned_texts: dict[int, str] = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        future_map = {
            pool.submit(cleanup_text, p["native_text"]): (idx, p["page_num"])
            for idx, p in pages_with_text
        }

        done = 0
        for fut in as_completed(future_map):
            idx, pnum = future_map[fut]
            done += 1
            try:
                cleaned = fut.result(timeout=180)
                cleaned_texts[idx] = cleaned
                print(f"[AI  ] Page {pnum}  [{done}/{len(pages_with_text)}]  done")
            except Exception as e:
                cleaned_texts[idx] = merged_pages[idx]["native_text"]
                print(f"[AI  ] Page {pnum}  [{done}/{len(pages_with_text)}]  FAIL: {e}")

    for idx, cleaned in cleaned_texts.items():
        merged_pages[idx]["cleaned_text"] = cleaned

    for p in merged_pages:
        if "cleaned_text" not in p:
            p["cleaned_text"] = ""

    print(f"[AI  ] Done: {len(cleaned_texts)} page(s) cleaned.")
    return merged_pages


# ═══════════════════════════════════════════════════════════════════════
# Full Pipeline Orchestration
# ═══════════════════════════════════════════════════════════════════════

def _process_pdf(filepath: str) -> list[dict]:
    """Full staged pipeline for a PDF file."""
    fname = os.path.basename(filepath)

    print(f"\n[STAGE 1] Parsing PDF: {fname}")
    raw_pages = parse_pdf(filepath)
    print(f"[STAGE 1] Extracted {len(raw_pages)} pages.\n")

    print(f"[STAGE 2] Block segmentation:")
    seg = _segment_pages(raw_pages)
    print()

    print(f"[STAGE 3] Specialized extraction (OCR + Tables in parallel):")
    ocr_results = _run_ocr_parallel(seg["ocr_jobs"])
    table_results = _run_tables_parallel(filepath, seg["table_pages"])
    print()

    print(f"[STAGE 4] Merging blocks:")
    merged = _merge_blocks(raw_pages, seg["text_map"], ocr_results, table_results)
    print()

    print(f"[STAGE 5] AI cleanup via Ollama/Llama3:")
    final_pages = _run_ai_cleanup(merged)
    print()

    return final_pages


def _process_pptx(filepath: str) -> list[dict]:
    """Full staged pipeline for a PPTX file."""
    fname = os.path.basename(filepath)

    print(f"\n[STAGE 1] Parsing PPTX: {fname}")
    raw_slides = parse_pptx(filepath)
    print(f"[STAGE 1] Extracted {len(raw_slides)} slides.\n")

    print(f"[STAGE 2] Block segmentation:")
    seg = _segment_pages(raw_slides)
    print()

    print(f"[STAGE 3] Specialized extraction (OCR in parallel):")
    ocr_results = _run_ocr_parallel(seg["ocr_jobs"])
    print()

    print(f"[STAGE 4] Merging blocks:")
    merged = _merge_blocks(raw_slides, seg["text_map"], ocr_results, table_results={})
    print()

    print(f"[STAGE 5] AI cleanup via Ollama/Llama3:")
    final_pages = _run_ai_cleanup(merged)
    print()

    return final_pages


def run_pipeline(filepath: str) -> str | None:
    """
    Run the full ingestion pipeline on a single file.
    Returns path to generated markdown in knowledge/, or None on failure.
    """
    ext = os.path.splitext(filepath)[1].lower()
    filename = os.path.basename(filepath)

    try:
        if ext == ".pdf":
            pages = _process_pdf(filepath)
        elif ext in (".pptx", ".ppt"):
            pages = _process_pptx(filepath)
        else:
            print(f"[SKIP] Unsupported: {filepath}")
            return None

        if not pages:
            print(f"[WARN] No content extracted from {filename}")
            return None

        print(f"[STAGE 6] Writing markdown:")
        out_path = write_markdown(filename, pages)
        print(f"[STAGE 6] {filename} -> {out_path}")
        return out_path

    except Exception as e:
        print(f"[ERROR] Pipeline failed for {filename}: {e}")
        import traceback
        traceback.print_exc()
        return None
