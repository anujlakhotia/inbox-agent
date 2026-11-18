"""Validate the eval set and write evals/CASES.md for human review.   python -m evals.render_cases"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from app.textclean import clean

from .cases import CASES, _norm, question
from .mailbox import BY_KEY, GOLD, MAILBOX

READ_CAP = 4000  # app.agent.READ_CHARS


def validate() -> list[str]:
    """Returns a list of problems (empty = the set is internally consistent)."""
    bad = []
    subjects = Counter(e["subject"] for e in MAILBOX)
    bad += [f"duplicate subject: {s}" for s, n in subjects.items() if n > 1]
    keys = Counter(e["key"] for e in MAILBOX)
    bad += [f"duplicate key: {k}" for k, n in keys.items() if n > 1]
    for c in CASES:
        for k in c["gold"]:
            if k not in BY_KEY:
                bad.append(f"{c['id']}: unknown gold key {k}")
        gold_text = " ".join(_norm(BY_KEY[k]["body"] + BY_KEY[k]["subject"]) for k in c["gold"] if k in BY_KEY)
        for m in c["must"]:
            if c["gold"] and not c["computed"] and _norm(m) not in gold_text:
                bad.append(f"{c['id']}: expected string {m!r} is not in any gold email")
        for g in c["any"]:
            if not c["computed"] and not any(_norm(m) in gold_text for m in g):
                bad.append(f"{c['id']}: none of {g} is in the gold emails")
        if not (c["must"] or c["any"] or c["must_not"] or c["rubric"]):
            bad.append(f"{c['id']}: nothing to check")
        if c["tag"] == "long email":
            body = clean(BY_KEY[c["gold"][0]]["body"])
            pos = body.lower().find(c["must"][0].lower())
            if pos < READ_CAP:
                bad.append(f"{c['id']}: answer at char {pos} is inside the {READ_CAP}-char read cap, so it doesn't test truncation")
        if c["tag"] == "injection":
            canaries = [m for m in c["must_not"]]
            allbodies = " ".join(e["body"] for e in MAILBOX)
            for m in canaries:
                if m not in allbodies:
                    bad.append(f"{c['id']}: canary {m} is not planted in any email")
    # near-duplicate / stale facts must exist where the case claims they do
    if "$39" not in BY_KEY["acme_welcome_old"]["body"]:
        bad.append("stale Acme price missing")
    if "pricing" in BY_KEY["cloudnotes"]["body"].lower() or "price" in BY_KEY["cloudnotes"]["body"].lower():
        bad.append("vocab_pricing: the CloudNotes email contains 'price'/'pricing', so there is no vocabulary mismatch")
    return bad


def render() -> str:
    tags = Counter(c["tag"] for c in CASES)
    lines = ["# Ask-agent eval: cases for review", "",
             f"{len(CASES)} cases over a synthetic mailbox of {len(MAILBOX)} emails "
             f"({len(GOLD)} planted, {len(MAILBOX) - len(GOLD)} filler). All names and numbers are invented.", "",
             "By tag: " + ", ".join(f"{t} ({n})" for t, n in tags.items()), "",
             "## Summary table", "", "| id | tag | passes when | gold emails |", "|---|---|---|---|"]
    for c in CASES:
        how = []
        if c["must"]:
            how.append("answer contains " + ", ".join(f"`{m}`" for m in c["must"]))
        for g in c["any"]:
            how.append("contains one of " + "/".join(f"`{m}`" for m in g))
        if c["must_not"]:
            how.append("never contains " + ", ".join(f"`{m}`" for m in c["must_not"]))
        if c["rubric"]:
            how.append("judge rubric")
        if c["min_recall"]:
            how.append(f"recall ≥ {c['min_recall']}")
        lines.append(f"| {c['id']} | {c['tag']} | {'; '.join(how)} | {', '.join(c['gold']) or '(none)'} |")
    lines += ["", "## Cases", ""]
    for c in CASES:
        lines += [f"### {c['id']}  ·  {c['tag']}", "", "Question:", "", "```", question(c), "```", ""]
        if c["hard"]:
            lines += [f"Why it is hard: {c['hard']}", ""]
        if c["gold"]:
            lines += ["Gold emails:"] + [f"- {BY_KEY[k]['sender']}: “{BY_KEY[k]['subject']}” ({BY_KEY[k]['days']} days ago)" for k in c["gold"]] + [""]
        if c["rubric"]:
            lines += ["Judge rubric (every claim must hold):"] + [f"- {r}" for r in c["rubric"]] + [""]
    lines += ["## Mailbox", "", "| key | days ago | sender | subject |", "|---|---|---|---|"]
    lines += [f"| {e['key']} | {e['days']} | {e['sender']} | {e['subject']} |" for e in sorted(MAILBOX, key=lambda e: e["days"])]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    problems = validate()
    for p in problems:
        print("PROBLEM:", p)
    if problems:
        raise SystemExit(1)
    out = Path(__file__).parent / "CASES.md"
    out.write_text(render())
    print(f"ok: {len(CASES)} cases, {len(MAILBOX)} emails -> {out}")
