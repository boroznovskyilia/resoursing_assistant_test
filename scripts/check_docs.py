"""Check local inline Markdown link targets; this is not a semantic docs audit."""

from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit


LINK = re.compile(r"!?\[[^\]\n]*\]\(([^)\n]+)\)")
IGNORED = {".git", ".venv", "node_modules", "__pycache__"}


def local_targets(text):
    # shortcut: inline links without spaces only; use a Markdown parser if this format changes.
    fence = None
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(("```", "~~~")):
            marker = stripped[0]
            if fence is None:
                fence = marker
            elif fence == marker:
                fence = None
            continue
        if fence is not None:
            continue
        for target in LINK.findall(line):
            target = target.strip().split()[0].strip("<>") if target.strip() else ""
            parsed = urlsplit(target)
            if target and not parsed.scheme and not parsed.netloc and parsed.path:
                yield unquote(parsed.path)


def broken_links(root):
    failures = []
    for document in sorted(root.rglob("*.md")):
        if IGNORED.intersection(document.relative_to(root).parts):
            continue
        for target in local_targets(document.read_text(encoding="utf-8")):
            if not (document.parent / target).exists():
                failures.append(f"{document.relative_to(root)}: {target}")
    return failures


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    if not root.is_dir():
        print(f"Not a directory: {root}", file=sys.stderr)
        return 2
    failures = broken_links(root)
    if failures:
        print("Broken local links:\n" + "\n".join(failures), file=sys.stderr)
        return 1
    print(f"Local Markdown link targets exist: {root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
