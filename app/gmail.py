from __future__ import annotations

"""Read-only Gmail access. Run `python -m app.gmail` once to authorise."""
import base64
import html
import re
import time
from datetime import datetime, timezone
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
CREDS_FILE = Path("data/credentials.json")  # OAuth client downloaded from Google Cloud
TOKEN_FILE = Path("data/token.json")
MAX_BODY = 8000


def login():
    flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
    creds = flow.run_local_server(port=0)
    TOKEN_FILE.write_text(creds.to_json())
    print(f"Saved {TOKEN_FILE}")


def _service():
    if not TOKEN_FILE.exists():
        raise RuntimeError("Not authorised yet. Run: python -m app.gmail")
    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds.valid:
        if creds.refresh_token:
            creds.refresh(Request())
            TOKEN_FILE.write_text(creds.to_json())
        else:
            raise RuntimeError("Token expired. Run: python -m app.gmail")
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _decode(data: str) -> str:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", errors="replace")


def _strip_html(s: str) -> str:
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def _body(payload: dict) -> str:
    plain, html_part = [], []

    def walk(p):
        mime = p.get("mimeType", "")
        data = p.get("body", {}).get("data")
        if data and mime == "text/plain":
            plain.append(_decode(data))
        elif data and mime == "text/html":
            html_part.append(_decode(data))
        for sub in p.get("parts", []) or []:
            walk(sub)

    walk(payload)
    text = "\n".join(plain) if plain else _strip_html("\n".join(html_part))
    return re.sub(r"\s+", " ", text).strip()[:MAX_BODY]


def _get_with_backoff(svc, mid: str) -> dict:
    """Fetch one message, waiting and retrying when Gmail's per-minute quota is hit."""
    for attempt in range(6):
        try:
            return svc.users().messages().get(userId="me", id=mid, format="full").execute()
        except HttpError as ex:
            if ex.resp.status not in (403, 429) or attempt == 5:
                raise
            time.sleep(min(60, 5 * 2**attempt))


def fetch_new(days: int, known: set[str], limit: int = 100):
    """Yields new emails one at a time so callers can save progress as it arrives."""
    svc = _service()
    ids, token = [], None
    q = f"newer_than:{days}d -in:spam -in:trash -in:sent -in:drafts"
    # Page (newest first) until we have `limit` emails we don't already store. Counting stored ones toward the
    # limit would stop us before ever reaching older, unfetched mail.
    while len(ids) < limit:
        resp = svc.users().messages().list(userId="me", q=q, maxResults=100, pageToken=token).execute()
        ids += [m["id"] for m in resp.get("messages", []) if m["id"] not in known]
        token = resp.get("nextPageToken")
        if not token:
            break
    for mid in ids[:limit]:
        time.sleep(0.2)  # stay well under Gmail's per-user rate limit
        m = _get_with_backoff(svc, mid)
        headers = {h["name"].lower(): h["value"] for h in m["payload"].get("headers", [])}
        name, addr = parseaddr(headers.get("from", ""))
        try:
            dt = parsedate_to_datetime(headers["date"]).astimezone(timezone.utc)
        except Exception:
            dt = datetime.fromtimestamp(int(m["internalDate"]) / 1000, tz=timezone.utc)
        yield (
            {
                "id": mid,
                "thread_id": m["threadId"],
                "sender": name or addr,
                "sender_email": addr.lower(),
                "subject": headers.get("subject", "(no subject)"),
                "date": dt.strftime("%Y-%m-%d %H:%M:%S"),
                "snippet": m.get("snippet", ""),
                "body": _body(m["payload"]),
            }
        )


if __name__ == "__main__":
    login()
