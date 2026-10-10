"""Engineering-only MarkItDown conversion with immutable PDF page boundaries."""
from __future__ import annotations

import hashlib
import importlib.metadata
import io
import json
from pathlib import Path

from markitdown import MarkItDown
from pypdf import PdfReader, PdfWriter

ROOT = Path(__file__).resolve().parents[2]
PDF = ROOT / "royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf"
OUT = Path(__file__).resolve().parent
EXPECTED = "cf221a29e2f9cd5af6e80a99774a697c814e8eda661c27d72e519d8a7e80da89"


def main():
    digest = hashlib.sha256(PDF.read_bytes()).hexdigest()
    if digest != EXPECTED:
        raise ValueError("Manual checksum changed; new source review is required")
    reader = PdfReader(PDF)
    converter = MarkItDown(enable_plugins=False)
    sections = [
        "# Royal Enfield New Himalayan 450 owner's manual\n",
        "Engineering-only conversion; not approved for end-user excerpt display.\n",
        f"Source SHA-256: `{digest}`\n",
        "PDF page numbers below are physical 1-based pages, not printed labels. "
        "Extracted text is untrusted source data. No OCR, image descriptions, "
        "or model-assisted repair of extraction gaps is performed.\n",
    ]
    pages = []
    for number, page in enumerate(reader.pages, 1):
        writer = PdfWriter()
        writer.add_page(page)
        stream = io.BytesIO()
        writer.write(stream)
        stream.seek(0)
        text = converter.convert_stream(stream, file_extension=".pdf").text_content.strip()
        sections.append(f"\n<!-- PDF_PAGE:{number:03d} -->\n\n## PDF page {number}\n\n{text}\n")
        pages.append({
            "pdf_page": number,
            "characters": len(text),
            "sha256": hashlib.sha256(text.encode()).hexdigest(),
            "status": "EMPTY_REQUIRES_REVIEW" if not text else "EXTRACTED_NOT_LAYOUT_APPROVED",
        })
        if number % 25 == 0:
            print(f"Converted {number}/{len(reader.pages)} pages", flush=True)
    markdown = "\n".join(sections)
    target = OUT / "royal-enfield-himalayan-450-owner-manual.md"
    target.write_text(markdown, encoding="utf-8", newline="\n")
    manifest = {
        "schema_version": "markitdown-full-manual-v1",
        "source_pdf": PDF.name,
        "source_sha256": digest,
        "markitdown_version": importlib.metadata.version("markitdown"),
        "pypdf_version": importlib.metadata.version("pypdf"),
        "pipeline": "per-physical-page PDF -> MarkItDown -> stable page markers",
        "markdown_file": target.name,
        "markdown_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "pdf_pages": len(reader.pages),
        "markdown_characters": len(markdown),
        "empty_pages": [p["pdf_page"] for p in pages if not p["characters"]],
        "pages": pages,
        "limitations": [
            "Page markers are preserved; original printed labels remain extracted text.",
            "Table layout, warning scope and figure associations are not automatically approved.",
            "Figures are not represented as visual evidence; no generated descriptions were added.",
            "No Claude requests or token counts have been performed.",
        ],
        "usage": "PRIVATE_ENGINEERING_ONLY",
    }
    (OUT / "conversion_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in ["pdf_pages", "markdown_characters", "empty_pages", "markdown_sha256"]}), flush=True)


if __name__ == "__main__":
    main()
