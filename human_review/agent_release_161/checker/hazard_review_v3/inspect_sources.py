"""Independent read-only source inspection for the EXP001/EXP002 correction."""
from pathlib import Path
import hashlib
import json
import subprocess
import pypdfium2 as pdfium

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
PDF = ROOT / 'royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf'
RENDERER = Path('C:/Users/kumar maneshwar/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin/pdftoppm.exe')

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    pages = []
    document = pdfium.PdfDocument(str(PDF))
    for number in (23, 29, 30):
        image = OUT / ('original_pdf_023.png' if number == 23 else f'original_page-{number:03d}.png')
        if not image.exists():
            subprocess.run([str(RENDERER), '-f', str(number), '-l', str(number), '-singlefile', '-r', '150', '-png', str(PDF), str(image.with_suffix(''))], check=True)
        text_path = OUT / f'original_pdf_{number:03d}.txt'
        page = document[number - 1]
        text_page = page.get_textpage()
        text_path.write_text(text_page.get_text_range(), encoding='utf-8')
        pages.append({
            'pdf_page': number,
            'printed_label': str(number - 2),
            'image_path': image.relative_to(ROOT).as_posix(),
            'image_sha256': digest(image),
            'text_path': text_path.relative_to(ROOT).as_posix(),
            'text_sha256': digest(text_path),
            'text': text_path.read_text(encoding='utf-8'),
        })
        text_page.close()
        page.close()
    document.close()
    inventory = {
        'schema_version': 'independent-hazard-source-inspection-v3',
        'reviewer': '/root/hazard_checker',
        'original_pdf_path': PDF.relative_to(ROOT).as_posix(),
        'original_pdf_sha256': digest(PDF),
        'source_manifest_sha256': digest(ROOT / 'source_manifest.json'),
        'page_count': 149,
        'render_engine': 'Poppler pdftoppm 150 DPI',
        'text_engine': 'pypdfium2',
        'inspection_status': 'RENDERED_PENDING_VISUAL_REVIEW',
        'engineering_only': True,
        'end_user_display_permission': False,
        'pages': pages,
    }
    (OUT / 'source_inspection.json').write_text(json.dumps(inventory, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(inventory, indent=2, ensure_ascii=True))

if __name__ == '__main__':
    main()
