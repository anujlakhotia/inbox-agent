"""Strip the parts of an email that cost tokens but carry no information for the model."""
from __future__ import annotations

import re

_REPLY_START = re.compile(r"^(on .{5,200} wrote:|-{2,}\s*original message\s*-{2,})\s*$", re.I)
_FOOTER = re.compile(
    r"unsubscribe|view (this )?(email )?(in|on) (your )?browser|manage (your )?(email )?(preferences|subscription)"
    r"|update (your )?(email )?preferences|all rights reserved|©|privacy policy|sent from my (iphone|ipad|android)",
    re.I,
)
_LONG_URL = re.compile(r"https?://\S{40,}")


def clean(text: str | None) -> str:
    """Drop quoted replies, signatures, footer boilerplate and long tracking URLs; collapse blank lines."""
    if not text:
        return ""
    kept = []
    for line in text.replace("\r\n", "\n").split("\n"):
        s = line.strip()
        if s == "--" or _REPLY_START.match(s):
            break  # everything after is a signature or the quoted thread
        if s.startswith(">"):
            continue
        if len(s) < 200 and _FOOTER.search(s):
            continue
        kept.append(_LONG_URL.sub("[link]", line.rstrip()))
    out = re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()
    # never return less than a stub when the original had real content (e.g. a mail that is all quote)
    return out if len(out) >= 20 or len(text.strip()) < 20 else text.strip()
