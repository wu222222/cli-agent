#!/usr/bin/env python3
"""
PDF text extractor using pypdf (actively maintained, handles AES-256).

Usage:
    python3 readpdf.py file.pdf           # print all text
    python3 readpdf.py file.pdf 3         # print page 3 only
    python3 readpdf.py file.pdf 1 5       # print pages 1-5
"""

import sys
import os

try:
    from pypdf import PdfReader
except ImportError:
    print("Error: pypdf not installed. Run: pip3 install pypdf")
    sys.exit(1)


def extract_text(filepath: str):
    reader = PdfReader(filepath)

    # Handle encrypted PDFs with empty password (SEED Labs PDFs)
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:
            print("Warning: PDF is encrypted and could not be decrypted.")
            print("Text extraction may be limited.")

    pages = {}
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text:
            pages[i + 1] = text.strip()
    return pages


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 readpdf.py <file.pdf> [page | start end]")
        sys.exit(1)

    path = sys.argv[1]
    if not os.path.exists(path):
        print(f"File not found: {path}")
        sys.exit(1)

    pages = extract_text(path)

    if not pages:
        print("No text extracted.")
        sys.exit(1)

    if len(sys.argv) == 3:
        # Single page
        pg = int(sys.argv[2])
        text = pages.get(pg, f"Page {pg} not found")
        print(text)
    elif len(sys.argv) >= 4:
        # Page range
        start = int(sys.argv[2])
        end = int(sys.argv[3])
        for pg in range(start, end + 1):
            text = pages.get(pg)
            if text:
                print(f"\n{'='*60}")
                print(f"=== Page {pg} ===")
                print(f"{'='*60}\n")
                print(text)
    else:
        # All pages
        for pg in sorted(pages):
            print(f"\n{'='*60}")
            print(f"=== Page {pg} ===")
            print(f"{'='*60}\n")
            print(pages[pg])


if __name__ == "__main__":
    main()
