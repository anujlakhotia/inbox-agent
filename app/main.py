import asyncio
import json
import os
import threading
from typing import Optional
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import Depends, FastAPI, Header, HTTPException  # noqa: E402
from fastapi.responses import FileResponse, StreamingResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from . import agent, ai, db  # noqa: E402

LOOKBACK_DAYS = int(os.getenv("LOOKBACK_DAYS", "3"))
SYNC_EVERY_HOURS = float(os.getenv("SYNC_EVERY_HOURS", "6"))
DEMO = os.getenv("DEMO") == "1"
STEP = 1.5  # how far one tap on More/Less moves the ranking

app = FastAPI(title="Inbox Agent")
_sync_lock = threading.Lock()


def auth(x_token: Optional[str] = Header(default=None)):
    expected = os.getenv("APP_TOKEN")
    if expected and x_token != expected:
        raise HTTPException(401, "Bad or missing token")


def sync_now() -> dict:
    if not _sync_lock.acquire(blocking=False):
        return {"status": "already running"}
    try:
        if DEMO:
            from .demo import EMAILS as new
        else:
            from . import gmail

            new = gmail.fetch_new(LOOKBACK_DAYS, db.known_ids())
        fetched, error = 0, None
        try:
            for e in new:  # saved one by one so a mid-sync failure keeps what was fetched
                db.upsert_email(e)
                fetched += 1
        except Exception as ex:
            error = str(ex)
            print("fetch stopped early:", ex)
        todo = db.unclassified()
        for e, r in zip(todo, ai.classify(todo)):
            db.set_classification(e["id"], r["section"], r["score"], r["summary"], r["why"], r["topics"])
        if error:
            return {"status": "partial, will resume next refresh", "fetched": fetched, "classified": len(todo)}
        return {"status": "ok", "fetched": fetched, "classified": len(todo)}
    finally:
        _sync_lock.release()


@app.on_event("startup")
async def startup():
    db.init()

    async def loop():
        while True:
            try:
                await asyncio.to_thread(sync_now)
            except Exception as ex:
                print("sync failed:", ex)
            await asyncio.sleep(SYNC_EVERY_HOURS * 3600)

    asyncio.create_task(loop())


@app.post("/api/sync", dependencies=[Depends(auth)])
def sync():
    try:
        return sync_now()
    except Exception as ex:
        raise HTTPException(500, str(ex))


@app.get("/api/brief", dependencies=[Depends(auth)])
def brief(days: int = LOOKBACK_DAYS):
    weights = db.get_weights()
    sections = {"ai_business": [], "growth": [], "important": []}
    for e in db.recent_classified(days):
        topics = [t for t in (e["topics"] or "").split(",") if t]
        rank = (
            (e["score"] or 0)
            + weights.get(f"sender:{e['sender_email']}", 0)
            + sum(weights.get(f"topic:{t}", 0) for t in topics)
        )
        if rank < 1:
            continue
        e["topics"] = topics
        e["rank"] = round(rank, 1)
        e["sender_weight"] = weights.get(f"sender:{e['sender_email']}", 0)
        e["topic_weights"] = {t: weights.get(f"topic:{t}", 0) for t in topics}
        sections[e["section"]].append(e)
    for items in sections.values():
        items.sort(key=lambda x: x["rank"], reverse=True)
    return sections


class Feedback(BaseModel):
    kind: str  # "sender" | "topic"
    value: str  # sender email or topic tag
    direction: int  # +1 more, -1 less


@app.post("/api/feedback", dependencies=[Depends(auth)])
def feedback(f: Feedback):
    if f.kind not in ("sender", "topic") or f.direction not in (-1, 1):
        raise HTTPException(400, "bad feedback")
    db.add_weight(f"{f.kind}:{f.value.lower()}", STEP * f.direction)
    return {"ok": True}


@app.get("/api/weights", dependencies=[Depends(auth)])
def weights():
    return db.get_weights()


@app.delete("/api/weights/{key:path}", dependencies=[Depends(auth)])
def reset_weight(key: str):
    db.delete_weight(key)
    return {"ok": True}


class Ask(BaseModel):
    question: str
    history: list = []
    deep: bool = False  # use the stronger (pricier) model


def _claude_error(ex: Exception, deep: bool) -> Optional[str]:
    """A readable message for Claude API failures, or None if it isn't one."""
    import anthropic

    if isinstance(ex, anthropic.AuthenticationError):
        return "Claude rejected the API key. Check ANTHROPIC_API_KEY in .env and restart."
    if isinstance(ex, anthropic.NotFoundError):
        return (f"Model not available to your account ({agent.DEEP_MODEL if deep else agent.MODEL}). "
                "Set AGENT_MODEL / AGENT_DEEP_MODEL in .env.")
    if isinstance(ex, anthropic.APIError):
        return f"Claude API error: {ex.message}"
    return None


@app.post("/api/chat", dependencies=[Depends(auth)])
def chat(a: Ask):
    try:
        return agent.ask(a.question, a.history, a.deep)
    except Exception as ex:
        msg = _claude_error(ex, a.deep)
        if msg:
            raise HTTPException(502, msg)
        raise


@app.post("/api/chat/stream", dependencies=[Depends(auth)])
def chat_stream(a: Ask):
    """Same as /api/chat, but streams newline-delimited JSON events as the agent works."""

    def events():
        try:
            for ev in agent.ask_stream(a.question, a.history, a.deep):
                yield json.dumps(ev) + "\n"
        except Exception as ex:
            msg = _claude_error(ex, a.deep)
            if not msg:
                print("chat stream failed:", ex)
            yield json.dumps({"type": "error", "message": msg or "Something went wrong. Check the server log."}) + "\n"

    return StreamingResponse(
        events(), media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},  # no proxy buffering
    )


@app.get("/api/usage", dependencies=[Depends(auth)])
def usage(days: int = 30):
    return db.usage_summary(days)


STATIC = Path(__file__).parent / "static"


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/", StaticFiles(directory=STATIC), name="static")
