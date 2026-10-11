"""Read-only audit of human navigation and compatibility-root additions."""
from pathlib import Path
import json
import re
import sys
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]


def audit():
    layout = json.loads((ROOT / 'docs/repository_layout.json').read_text(encoding='utf-8'))
    actual = {p.name for p in ROOT.iterdir() if p.is_file()}
    unexpected = sorted(actual - set(layout['allowed_root_files']))
    missing = []
    broken = []
    checked = 0
    for relative in layout['navigation_files']:
        page = ROOT / relative
        if not page.is_file():
            missing.append(relative)
            continue
        text = page.read_text(encoding='utf-8-sig')
        for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)', text):
            if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target) or target.startswith('#'):
                continue
            path = unquote(target.split('#')[0]).strip('<>')
            if not path:
                continue
            checked += 1
            resolved = (page.parent / path).resolve()
            if not resolved.is_relative_to(ROOT) or not resolved.exists():
                broken.append({'page': relative, 'target': target})
    return {
        'schema_version': 'repository-structure-audit-v1',
        'ok': not (unexpected or missing or broken),
        'unexpected_root_files': unexpected,
        'missing_navigation_files': missing,
        'broken_navigation_links': broken,
        'local_links_checked': checked,
        'root_file_count': len(actual),
        'note': 'Existing compatibility paths are allowlisted; this is not a source or runtime approval check.',
    }


if __name__ == '__main__':
    result = audit()
    print(json.dumps(result, indent=2))
    sys.exit(0 if result['ok'] else 1)
