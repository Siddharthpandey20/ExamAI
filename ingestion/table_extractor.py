"""
table_extractor.py — Extract tables from PDF pages using Camelot.

Returns tables as list-of-lists (rows × cells) per page.
Designed to be called in parallel from pipeline.py.
"""

import camelot


def extract_tables_from_pdf(filepath: str, page_num: int) -> list[list[list[str]]]:
    """
    Extract all tables from a specific page of a PDF.

    Returns:
        List of tables. Each table is a list of rows, each row a list of cell strings.
    """
    try:
        # Camelot uses 1-based page numbers as strings
        tables = camelot.read_pdf(filepath, pages=str(page_num), flavor="lattice")

        if not tables or tables.n == 0:
            # Fallback to stream detection
            tables = camelot.read_pdf(filepath, pages=str(page_num), flavor="stream")

        result = []
        for table in tables:
            df = table.df
            rows = df.values.tolist()
            result.append(rows)
        return result

    except Exception as e:
        print(f"[TABLE] Camelot failed on page {page_num}: {e}")
        return []


def extract_tables_all_pages(filepath: str, page_nums: list[int]) -> dict[int, list]:
    """
    Extract tables from multiple pages.

    Returns:
        Dict mapping page_num → list of tables for that page.
    """
    results = {}
    for pn in page_nums:
        results[pn] = extract_tables_from_pdf(filepath, pn)
    return results
