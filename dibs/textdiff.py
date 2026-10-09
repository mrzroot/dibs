"""Line-level helpers shared by the journal, briefs and the revert guard."""
from __future__ import annotations

import difflib
import re
from collections import Counter
from typing import List, Optional, Tuple

MAX_DIFF_LINES = 20000
_TRIVIAL = re.compile(r"^[\s{}\[\]();,:.\-*/#<>\"'`|=+!?\\]*$")
_TRIVIAL_WORDS = {"else", "else:", "end", "fi", "done", "pass", "return", "break", "continue",
                  "try:", "finally:", "}", "};", "]", ")", "});", "</div>", "<div>", "\"\"\"", "'''"}


def to_lines(data: Optional[bytes]) -> Optional[List[str]]:
    """Decode to lines; None for binary or oversized content."""
    if data is None:
        return []
    if b"\0" in data[:8000]:
        return None
    text = data.decode("utf-8", "replace")
    lines = text.splitlines()
    if len(lines) > MAX_DIFF_LINES:
        return None
    return lines


def line_delta(before: Optional[List[str]], after: Optional[List[str]]) -> Tuple[List[str], List[str]]:
    """Return (added lines, removed lines) between two line lists."""
    a = before or []
    b = after or []
    plus: List[str] = []
    minus: List[str] = []
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("replace", "delete"):
            minus.extend(a[i1:i2])
        if tag in ("replace", "insert"):
            plus.extend(b[j1:j2])
    return plus, minus


def key(line: str) -> str:
    return " ".join(line.split())


def significant(line: str) -> bool:
    k = key(line)
    if len(k) < 3 or _TRIVIAL.match(k):
        return False
    return k not in _TRIVIAL_WORDS


def counts(lines: List[str]) -> Counter:
    return Counter(key(l) for l in lines)


def unified(before: Optional[List[str]], after: Optional[List[str]], limit: int) -> List[str]:
    """Compact +/- lines (no context) for briefs, capped at ``limit``."""
    plus, minus = line_delta(before, after)
    out = [f"- {l.strip()}" for l in minus if l.strip()] + [f"+ {l.strip()}" for l in plus if l.strip()]
    if len(out) > limit:
        more = len(out) - limit
        out = out[:limit] + [f"… {more} more changed lines"]
    return [o if len(o) <= 160 else o[:157] + "…" for o in out]
