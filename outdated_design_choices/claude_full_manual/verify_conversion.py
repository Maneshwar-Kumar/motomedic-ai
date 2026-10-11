"""Check hosted conversion integrity; this does not approve technical claims."""
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    manifest = json.loads((HERE / "conversion_manifest.json").read_text(encoding="utf-8"))
    selection = json.loads((HERE / "evaluation_selection.json").read_text(encoding="utf-8"))
    source_notes = json.loads((ROOT / "source_review_notes.json").read_text(encoding="utf-8"))
    raw = (HERE / manifest["markdown_file"]).read_bytes()
    text = raw.decode("utf-8")
    markers = list(re.finditer(r"<!-- PDF_PAGE:(\d{3}) -->", text))
    numbers = [int(m.group(1)) for m in markers]
    if manifest["source_sha256"] != selection["source_sha256"]:
        raise ValueError("Source binding mismatch")
    if hashlib.sha256(raw).hexdigest() != manifest["markdown_sha256"]:
        raise ValueError("Markdown integrity mismatch")
    if numbers != list(range(1, 150)) or manifest["pdf_pages"] != 149:
        raise ValueError("Expected exactly 149 ordered physical PDF pages")
    chunks = {
        n: text[markers[i].end():markers[i + 1].start() if i + 1 < len(markers) else len(text)]
        for i, n in enumerate(numbers)
    }
    page_info = {p["pdf_page"]: p for p in manifest["pages"]}
    report = {
        "schema_version": "markitdown-conversion-integrity-v1",
        "source_sha256": manifest["source_sha256"],
        "markdown_sha256": manifest["markdown_sha256"],
        "ordered_page_markers": "PASS_149_OF_149",
        "empty_pages": manifest["empty_pages"],
        "replacement_character_count": text.count("\ufffd"),
        "short_pages_under_100_characters": [n for n, p in page_info.items() if p["characters"] < 100],
        "selected_case_page_extraction": [
            {"record_id": c["record_id"], "pages": [
                {"pdf_page": p, "extracted_characters": page_info[p]["characters"],
                 "replacement_characters": chunks[p].count("\ufffd")}
                for p in c["source_pages"]
            ], "content_review": "PENDING_ORIGINAL_PAGE_COMPARISON"}
            for c in selection["cases"]
        ],
        "known_source_review_notes": source_notes["reviews"],
        "figure_and_table_associations": "NOT_ESTABLISHED_BY_TEXT_CONVERSION",
        "experiment_inference_status": "NOT_RUN",
        "claude_requests": 0,
    }
    (HERE / "conversion_qa.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ["ordered_page_markers", "empty_pages", "replacement_character_count", "short_pages_under_100_characters"]}))


if __name__ == "__main__":
    main()
