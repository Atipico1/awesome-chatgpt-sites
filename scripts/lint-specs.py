#!/usr/bin/env python3
"""Check app specs against skills/awesome-sites/references/shared/spec-template.md.

Usage: python3 scripts/lint-specs.py [spec-name ...]
With no arguments every spec in references/apps is checked. Exit code 1 on any error.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "awesome-sites"
APPS = SKILL / "references" / "apps"
SHARED = SKILL / "references" / "shared"

# Specs written before the template existed. Remove entries as they are upgraded.
LEGACY = {"issue-tracker", "memory-mcp"}

REQUIRED_HEADER_WORDS = ["Read first", "Access", "Keys", "Audience"]
REQUIRED_SECTIONS = ["Data", "API", "Screens", "Limits", "Verification", "Out of scope"]
ALLOWED_FENCES = {"sql", "json", "text", ""}
SECRET_RE = re.compile(r"`([A-Z][A-Z0-9]+(?:_[A-Z0-9]+)+)`")


def read(path):
    return path.read_text(encoding="utf-8")


def main(argv):
    names = argv or sorted(p.stem for p in APPS.glob("*.md"))
    shared_text = "\n".join(read(p) for p in SHARED.glob("*.md"))
    skill_md = read(SKILL / "SKILL.md")
    readme = read(ROOT / "README.md")
    access = read(SHARED / "access-and-domains.md")
    errors, warnings = [], []

    for name in names:
        path = APPS / f"{name}.md"
        if not path.exists():
            errors.append(f"{name}: file not found")
            continue
        text = read(path)
        legacy = name in LEGACY

        if name.startswith("sites-"):
            errors.append(f"{name}: file name must not start with 'sites-'")
        if f"apps/{name}.md" not in skill_md:
            errors.append(f"{name}: no catalog row in skills/awesome-sites/SKILL.md")
        if name not in readme:
            errors.append(f"{name}: not listed in README.md")
        if not legacy and name not in access:
            errors.append(f"{name}: no row in shared/access-and-domains.md audience table")

        for ref in re.findall(r"\.\./shared/([\w-]+\.md)", text):
            if not (SHARED / ref).exists():
                errors.append(f"{name}: links to missing shared file {ref}")

        if legacy:
            continue

        headings = re.findall(r"^#{2,3} (.+)$", text, re.M)
        for word in REQUIRED_HEADER_WORDS:
            if word not in text:
                errors.append(f"{name}: header line '{word}' missing")
        for sec in REQUIRED_SECTIONS:
            if not any(sec.lower() in h.lower() for h in headings):
                errors.append(f"{name}: section '{sec}' missing")

        fences = re.findall(r"^```(\w*)", text, re.M)[::2]
        for lang in set(fences) - ALLOWED_FENCES:
            errors.append(f"{name}: code block language '{lang}' (specs hold no application code)")

        if "SITE_URL" not in text:
            warnings.append(f"{name}: no mention of SITE_URL (fine only if the app has no absolute links)")
        if re.search(r"\b(TODO|TBD|or similar|etc\.)", text):
            warnings.append(f"{name}: contains TODO/TBD/'or similar'/'etc.'; decide instead")

        for secret in sorted(set(SECRET_RE.findall(text))):
            if secret not in shared_text and secret not in {"NOT_NULL"}:
                warnings.append(f"{name}: `{secret}` not documented in shared files")

    for w in warnings:
        print(f"warning: {w}")
    for e in errors:
        print(f"error: {e}")
    print(f"{len(names)} spec(s) checked, {len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
