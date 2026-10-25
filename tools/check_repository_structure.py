"""Read-only repository layout, navigation-link and current-release integrity audit.

Uses only the standard library. Checks the top-level layout, that every local link in the
reader-facing documents resolves, the manual's SHA-256 and the current serving manifest.
Archived history keeps its bytes under archive/; its frozen v8-v10.14 bindings and the 161-case
approval package were last verified in their original layout at HISTORY_LAYOUT_COMMIT. Passing
this audit is not factual, provider, deployment or release acceptance.
"""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MANUAL = "source/royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf"
MANUAL_SHA = "cf221a29e2f9cd5af6e80a99774a697c814e8eda661c27d72e519d8a7e80da89"
CURRENT_FREEZE = "releases/serving_manifest_v11_1.json"

ROOT_FILES = frozenset({".gitattributes", ".gitignore", ".dockerignore", "README.md", "AGENTS.md", "CONTRIBUTING.md"})
ROOT_DIRS = frozenset({".claude", ".github", "archive", "cloud", "docs", "evals", "ingest", "releases",
                       "rider_ui", "source", "tools"})
NAVIGATION = (
    "README.md", "AGENTS.md", "CONTRIBUTING.md",
    "docs/REVIEW_GUIDE.md", "docs/ARCHITECTURE.md", "docs/PRD.md", "docs/TRD.md", "docs/STATUS.md",
    "docs/SETUP.md", "docs/EXPERIMENTS.md", "docs/DECISIONS.md", "docs/TODO.md",
    "source/README.md", "ingest/README.md", "cloud/README.md", "rider_ui/README.md",
    "rider_ui/API_CONTRACT.md", "rider_ui/SERVICE_SAFEGUARDS.md", "tools/README.md",
    "evals/README.md", "evals/20261025_answer_release_v3/README.md", "releases/README.md", "archive/README.md",
)
CRITICAL = (
    MANUAL, "source/source_manifest.json", CURRENT_FREEZE, "releases/serving_manifest_v11.json",
    "releases/owner_decision_v5.json", "evals/20261025_answer_release_v3/owner_decision_v3.json",
    "evals/20261025_answer_release_v3/owner_decision_v4.json", "cloud/deployment_status.json",
)


def digest(path):
    with path.open("rb") as source:
        checksum = hashlib.sha256()
        for block in iter(lambda: source.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def tracked_top_level():
    try:
        names = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split("\n")
    except (OSError, subprocess.CalledProcessError):
        names = [p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts]
    files = {n for n in names if n and "/" not in n}
    dirs = {n.split("/", 1)[0] for n in names if "/" in n}
    return files, dirs


def audit():
    files, dirs = tracked_top_level()
    missing, broken, integrity = [], [], []
    checked = 0
    for relative in NAVIGATION:
        page = ROOT / relative
        if not page.is_file():
            missing.append(relative)
            continue
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", page.read_text(encoding="utf-8-sig")):
            target = target.strip().strip("<>")
            if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target) or target.startswith("#"):
                continue
            link = unquote(target.split("#", 1)[0])
            if not link:
                continue
            checked += 1
            resolved = (page.parent / link).resolve()
            if not resolved.is_relative_to(ROOT) or not resolved.exists():
                broken.append({"page": relative, "target": target})

    missing_critical = [relative for relative in CRITICAL if not (ROOT / relative).is_file()]
    if (ROOT / MANUAL).is_file() and digest(ROOT / MANUAL) != MANUAL_SHA:
        integrity.append({"path": MANUAL, "reason": "MANUAL_SHA256_MISMATCH"})

    current_count = 0
    try:
        from tools.serving_release import verify
        current_count = len(verify(ROOT)["file_sha256"])
    except (OSError, UnicodeError, KeyError, TypeError, ValueError, RuntimeError) as error:
        integrity.append({"path": CURRENT_FREEZE, "reason": "CURRENT_SERVING_BINDING_FAILED", "detail": str(error)})

    unexpected_files = sorted(files - ROOT_FILES)
    unexpected_dirs = sorted(dirs - ROOT_DIRS)
    return {
        "schema_version": "repository-structure-audit-v5",
        "ok": not (unexpected_files or unexpected_dirs or missing or broken or missing_critical or integrity),
        "unexpected_root_files": unexpected_files,
        "unexpected_root_dirs": unexpected_dirs,
        "missing_navigation_files": missing,
        "broken_navigation_links": broken,
        "missing_critical_files": missing_critical,
        "integrity_errors": integrity,
        "local_links_checked": checked,
        "current_serving_files_verified": current_count,
        "note": "Layout, reader-facing links, the manual and the current v11.1 serving inputs. Archived history is verified at its layout commit. Not factual or deployment acceptance.",
    }


if __name__ == "__main__":
    result = audit()
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["ok"] else 1)
