"""Minimal-diff editing of the date ranges in catalog yaml sources.

The yaml is parsed with ruamel only to locate the lines holding `urlpath` and `description`
of a source; the substitution is then done on the raw text of those lines, so formatting,
comments, anchors and `{{ DVC_PATH }}` spacing are untouched.

A range is '<start><sep><end>' with tokens YYYY or YYYYMM and sep '-', en dash or ' to '.
In urlpath the range is set to the YYYYMM tokens of the product file name; in descriptions
the width of the existing tokens is kept (years stay years).
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from ruamel.yaml import YAML

log = logging.getLogger(__name__)

YEAR = r"(?:18|19|20|21)\d{2}"
TOKEN = rf"{YEAR}(?:0[1-9]|1[0-2])?"
RANGE = re.compile(rf"(?<!\d)({TOKEN})(\s*(?:-|–|to)\s*)({TOKEN})(?!\d)")


@dataclass
class Edit:
    """A single line substitution in a catalog file."""
    path: Path
    lineno: int  # 0-based
    old: str
    new: str

    def __str__(self):
        return f"{self.path.name}:{self.lineno + 1}\n  - {self.old.strip()}\n  + {self.new.strip()}"


def _source_lines(text, source):
    """Line numbers of the urlpath value(s) and of the description of a source."""
    data = YAML().load(text)
    try:
        src = data["sources"][source]
    except KeyError as exc:
        raise KeyError(f"source '{source}' not found") from exc
    lines = {"urlpath": [], "description": []}
    if "description" in src:
        lines["description"].append(src.lc.value("description")[0])
    args = src.get("args", {}) or {}
    if "urlpath" in args:
        urlpath = args["urlpath"]
        if isinstance(urlpath, str):
            lines["urlpath"].append(args.lc.value("urlpath")[0])
        else:
            lines["urlpath"].extend(urlpath.lc.item(i)[0] for i in range(len(urlpath)))
    return lines


def _fit(token, width, end):
    """Adapt a YYYYMM token to the width of an existing token."""
    if width == 4:
        return token[:4]
    return token if len(token) == 6 else token + ("12" if end else "01")


def current_range(path, source):
    """(start, end) tokens of the range found in the urlpath of a source, or None."""
    text = Path(path).read_text(encoding="utf-8")
    lines = text.splitlines()
    for lineno in _source_lines(text, source)["urlpath"]:
        match = RANGE.search(lines[lineno])
        if match:
            return match.group(1), match.group(3)
    return None


def sync_range(path, source, start, end, fields=("urlpath", "description"), dry_run=False):
    """Set the range of the given fields of a source to start/end (YYYYMM tokens).

    Returns the list of edits (empty if already in sync). Writes the file unless dry_run.
    """
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    targets = _source_lines(text, source)

    def replace(match, exact):
        if exact:
            new_start, new_end = start, end
        else:
            new_start = _fit(start, len(match.group(1)), end=False)
            new_end = _fit(end, len(match.group(3)), end=True)
        return f"{new_start}{match.group(2)}{new_end}"

    edits = []
    for field in fields:
        for lineno in targets[field]:
            old = lines[lineno]
            new = RANGE.sub(lambda m, exact=(field == "urlpath"): replace(m, exact), old)
            if new != old:
                edits.append(Edit(path, lineno, old, new))
                lines[lineno] = new
    if "urlpath" in fields and not any(RANGE.search(lines[n]) for n in targets["urlpath"]):
        log.warning("%s: no date range found in the urlpath of %s", path.name, source)
    if edits and not dry_run:
        path.write_text("".join(lines), encoding="utf-8")
    return edits
