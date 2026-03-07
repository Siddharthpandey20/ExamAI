"""
parser_pdf.py — Extract content blocks from PDF files using PyMuPDF.

Returns a list of page dicts, each containing:
  - page_num: int
  - text_blocks: list of text strings with position info
  - image_blocks: list of image bytes (for OCR)
  - has_tables: bool hint (based on line density heuristic)
"""

import fitz  # PyMuPDF


def parse_pdf(filepath: str) -> list[dict]:
    """
    Parse a PDF and return structured blocks per page.

    Each page dict:
        {
            "page_num": 1,
            "text_blocks": [{"text": "...", "bbox": (x0,y0,x1,y1)}],
            "image_blocks": [{"image_bytes": b"...", "bbox": (x0,y0,x1,y1)}],
            "has_tables": True/False
        }
    """
    doc = fitz.open(filepath)
    pages = []

    for page_num, page in enumerate(doc, start=1):
        text_blocks = []
        image_blocks = []

        # --- Text blocks via get_text("dict") for positional data ---
        page_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)

        for block in page_dict.get("blocks", []):
            # type 0 = text, type 1 = image
            if block["type"] == 0:
                lines_text = []
                for line in block.get("lines", []):
                    spans_text = "".join(span["text"] for span in line.get("spans", []))
                    lines_text.append(spans_text)
                combined = "\n".join(lines_text).strip()
                if combined:
                    text_blocks.append({
                        "text": combined,
                        "bbox": tuple(block["bbox"]),
                    })

            elif block["type"] == 1:
                # Embedded image — extract bytes for OCR
                img_bytes = block.get("image")
                if img_bytes:
                    image_blocks.append({
                        "image_bytes": img_bytes,
                        "bbox": tuple(block["bbox"]),
                    })

        # --- Also grab page-level images via get_images() ---
        for img_info in page.get_images(full=True):
            xref = img_info[0]
            try:
                base_image = doc.extract_image(xref)
                if base_image and base_image.get("image"):
                    image_blocks.append({
                        "image_bytes": base_image["image"],
                        "bbox": None,  # position unknown from this API
                    })
            except Exception:
                continue

        # --- Table heuristic: lots of horizontal/vertical lines ---
        drawings = page.get_drawings()
        line_count = sum(1 for d in drawings for item in d.get("items", [])
                         if item[0] in ("l", "re"))
        has_tables = line_count > 8

        pages.append({
            "page_num": page_num,
            "text_blocks": text_blocks,
            "image_blocks": image_blocks,
            "has_tables": has_tables,
        })

    doc.close()
    return pages
