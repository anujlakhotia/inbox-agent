"""Free retrieval eval: no API calls, no key needed.   python -m evals.retrieval

For every case that has gold emails it asks two questions of the real search code in app/db.py:
  1. SEARCH   - using the question's content words as the query (a proxy for what the agent would type),
                are the gold emails in the top 8 / top 20 results?
  2. READABLE - is the expected fact inside the first READ_CHARS characters of the cleaned body, i.e. what the
                agent actually sees when it calls read_email? (Facts past the cap can never be answered.)

It can't judge answers, abstention or injection resistance; those need the model (see evals/README.md).
The query is a proxy: the real agent rewrites its searches, so vocabulary-mismatch results here are pessimistic.
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

# Point the app at a throwaway database BEFORE importing anything that reads DB_PATH.
_TMP = tempfile.mkdtemp(prefix="eval_retrieval_")
os.environ["DB_PATH"] = str(Path(_TMP) / "eval.db")
os.environ.pop("ANTHROPIC_API_KEY", None)  # guarantee this level cannot spend anything

from app import db  # noqa: E402
from app.agent import READ_CHARS  # noqa: E402
from app.textclean import clean  # noqa: E402

from .cases import CASES, _norm  # noqa: E402
from .mailbox import BY_KEY, seed  # noqa: E402

assert str(db.DB_PATH).startswith(_TMP), f"refusing to run: db path is {db.DB_PATH}, not the throwaway database"

STOP = set("""what which who whom how did does do is are was were my me i the a an of in on to for and or from about say said
tell told get got have has any anything this that these those last now recently over across each after will would can could
it its there their than then so if as at by with you your""".split())


def keywords(q: str) -> str:
    q = re.sub(r"\{d\d+\}", " ", q)  # a relative date is not something the agent would search for
    return " ".join(w for w in re.findall(r"[A-Za-z0-9$%.:']+", q) if w.lower().strip("'.:") not in STOP)


def ranks(query: str, gold_ids: dict, k: int = 20) -> dict:
    """Position (1-based) of each gold email in the top-k search results, or None."""
    rows = db.search_emails(keywords(query), None, k)
    pos = {r["id"]: i + 1 for i, r in enumerate(rows)}
    return {key: pos.get(eid) for key, eid in gold_ids.items()}


def readable(case: dict) -> bool | None:
    """Is every expected string inside the part of the email the agent can read? None if not applicable."""
    if not case["gold"] or not case["must"] or case["computed"]:
        return None
    seen = " ".join(_norm(clean(BY_KEY[k]["body"])[:READ_CHARS] + " " + BY_KEY[k]["subject"]) for k in case["gold"])
    return all(_norm(m) in seen for m in case["must"])


def run() -> list[dict]:
    db.init()
    ids = seed(db)
    rows = []
    for c in CASES:
        if not c["gold"]:
            continue
        gold = {k: ids[k] for k in c["gold"]}
        r = ranks(c["q"], gold)
        need = c["min_recall"] or 1.0
        r8 = sum(1 for p in r.values() if p and p <= 8) / len(r)
        r20 = sum(1 for p in r.values() if p) / len(r)
        rows.append(dict(id=c["id"], tag=c["tag"], query=keywords(c["q"]), ranks=r, recall8=r8, recall20=r20,
                         hit=r8 >= need - 1e-9, readable=readable(c)))
    return rows


def report(rows: list[dict]) -> str:
    n = len(rows)
    hits = sum(r["hit"] for r in rows)
    rd = [r for r in rows if r["readable"] is not None]
    unread = [r for r in rd if not r["readable"]]
    out = ["# Free retrieval eval", "",
           "No API calls. Real search code (`app/db.py`) over the synthetic mailbox; query = the question's content words "
           "(a proxy: the real agent rewrites its searches). A case is a **hit** when the gold emails are in the top 8 "
           "results (all of them, or the case's `min_recall` share).", "",
           f"**Search hit rate: {hits}/{n} ({hits / n:.0%})**   ·   mean recall@8 {sum(r['recall8'] for r in rows) / n:.2f}   ·   "
           f"mean recall@20 {sum(r['recall20'] for r in rows) / n:.2f}",
           f"**Fact readable within the {READ_CHARS}-char read cap: {len(rd) - len(unread)}/{len(rd)}** (cases with a checkable fact)", "",
           "## By tag", "", "| tag | cases | hits | readable |", "|---|---|---|---|"]
    by = defaultdict(list)
    for r in rows:
        by[r["tag"]].append(r)
    for tag, rs in by.items():
        rdt = [r for r in rs if r["readable"] is not None]
        rd_txt = f"{sum(1 for r in rdt if r['readable'])}/{len(rdt)}" if rdt else "n/a"
        out.append(f"| {tag} | {len(rs)} | {sum(r['hit'] for r in rs)}/{len(rs)} | {rd_txt} |")
    out += ["", "## Per case", "", "| id | tag | query used | gold rank in results | hit | fact readable |", "|---|---|---|---|---|---|"]
    for r in rows:
        rk = ", ".join(f"{k}: {p or '>20'}" for k, p in r["ranks"].items())
        rdv = "n/a" if r["readable"] is None else ("yes" if r["readable"] else "**NO**")
        out.append(f"| {r['id']} | {r['tag']} | {r['query']} | {rk} | {'yes' if r['hit'] else '**NO**'} | {rdv} |")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    import atexit
    import shutil

    atexit.register(shutil.rmtree, _TMP, ignore_errors=True)  # the throwaway database
    rows = run()
    text = report(rows)
    dest = Path(__file__).parent / "results"
    dest.mkdir(exist_ok=True)
    (dest / "retrieval.md").write_text(text)
    print(text)
    print(f"written: {dest / 'retrieval.md'}", file=sys.stderr)
