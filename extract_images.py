"""
Extract images from PDF papers for fish scale analysis test cases.
Uses PyMuPDF (fitz) as specified in test_cases.md Option 2.
"""

import fitz  # PyMuPDF
import os
from pathlib import Path

# Define paths
PAPERS_DIR = Path("papers")
OUTPUT_DIR = Path("test_images")

# Paper mapping based on test_cases.md
PAPERS = {
    "P1": "Gayet & Meunier 1986 Microstructure Ganoid Scales.pdf",
    "P2": "Microstructure Ganoid Scales S. America.pdf",
    "P3": "Microstructure of Obaichthys Scales.pdf",
}

def extract_images_from_pdf(pdf_path: Path, output_prefix: str):
    """Extract all images from a PDF file."""
    doc = fitz.open(pdf_path)
    extracted = []

    print(f"\nProcessing: {pdf_path.name}")
    print(f"  Pages: {len(doc)}")

    for page_num in range(len(doc)):
        page = doc[page_num]
        image_list = page.get_images()

        print(f"  Page {page_num + 1}: {len(image_list)} images found")

        for img_index, img in enumerate(image_list):
            xref = img[0]  # Image reference number

            # Extract image
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]

            # Generate filename
            filename = f"{output_prefix}_page{page_num + 1}_img{img_index + 1}.{image_ext}"
            output_path = OUTPUT_DIR / filename

            # Save image
            with open(output_path, "wb") as f:
                f.write(image_bytes)

            extracted.append({
                "filename": filename,
                "page": page_num + 1,
                "size": len(image_bytes),
                "format": image_ext,
                "width": base_image.get("width", 0),
                "height": base_image.get("height", 0),
            })

            print(f"    Saved: {filename} ({base_image.get('width', '?')}x{base_image.get('height', '?')} {image_ext})")

    doc.close()
    return extracted


def main():
    # Ensure output directory exists
    OUTPUT_DIR.mkdir(exist_ok=True)

    all_extracted = {}

    for paper_id, pdf_name in PAPERS.items():
        pdf_path = PAPERS_DIR / pdf_name

        if not pdf_path.exists():
            print(f"WARNING: {pdf_path} not found, skipping...")
            continue

        extracted = extract_images_from_pdf(pdf_path, paper_id)
        all_extracted[paper_id] = extracted

    # Summary
    print("\n" + "=" * 60)
    print("EXTRACTION SUMMARY")
    print("=" * 60)

    total = 0
    for paper_id, images in all_extracted.items():
        print(f"\n{paper_id} ({PAPERS[paper_id]}):")
        print(f"  Total images extracted: {len(images)}")
        total += len(images)

        # List by page
        pages = {}
        for img in images:
            pg = img["page"]
            if pg not in pages:
                pages[pg] = []
            pages[pg].append(img)

        for pg in sorted(pages.keys()):
            print(f"    Page {pg}: {len(pages[pg])} images")

    print(f"\nTotal images extracted: {total}")
    print(f"Output directory: {OUTPUT_DIR.absolute()}")


if __name__ == "__main__":
    main()
