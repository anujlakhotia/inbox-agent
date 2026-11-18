# Inbox Agent

A personal web app (works as a phone-installable PWA) that reads your Gmail (read-only), picks what's worth reading, and lets you ask questions about your mail.

- **Tabs:** AI & Business · Growth · Important · Ask
- **Cards:** 1–2 sentence summary, "why it matters", and an Open link to the Gmail thread
- **Feedback:** "Tune ranking" on each card gives ▲/▼ for the sender and each topic. Ranking = model score + your weights
- **Ask:** a tool-using assistant. Claude decides which searches to run (`search_emails`, `list_recent`, `list_by_sender`, `read_email`), reads what it needs, and answers with sources. Expand "search steps" under an answer to see what it did. It is read-only and keeps the last few turns as context.
- Edit `data/profile.txt` to describe your interests; it steers the triage

## Try it now (no Gmail, sample emails)

```bash
cd inbox-agent
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
DEMO=1 .venv/bin/uvicorn app.main:app --port 8000
```
Open http://localhost:8000. Without `ANTHROPIC_API_KEY` it uses simple keyword ranking.

## Connect your Gmail

1. Google Cloud Console → create a project → enable the **Gmail API**.
2. OAuth consent screen → External, add yourself as a test user. Scope used: `gmail.readonly` only.
3. Credentials → Create **OAuth client ID** → *Desktop app* → download JSON to `data/credentials.json`.
4. `cp .env.example .env`, then set `ANTHROPIC_API_KEY` and `APP_TOKEN`.
5. Authorise once: `.venv/bin/python -m app.gmail` (opens a browser, writes `data/token.json`).
6. Run: `.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000`

The app syncs on startup and every `SYNC_EVERY_HOURS`; the Refresh button syncs on demand.

## Ask costs

- Everyday questions use `AGENT_MODEL` (Sonnet); tick **Deep** in the Ask tab to use `AGENT_DEEP_MODEL` (Opus) for hard ones.
- Prompt caching is on, so each step of the loop re-reads earlier context at a fraction of the price. Email bodies are cleaned (quoted replies, signatures, footers, long tracking links removed) before the model sees them, and the loop is capped at 5 steps (the last one must answer).
- Every answer shows its model, steps, tokens (and how many were cached) and time. `GET /api/usage` totals this per model for the last 30 days. Question text is never stored.

## Use it on your phone

Same Wi-Fi: open `http://<your-computer-ip>:8000` on the phone and "Add to Home Screen". For access anywhere, deploy to a small host with a persistent disk (Fly.io, Railway, a VPS) and keep `data/` on that disk, or use a tunnel (Tailscale, Cloudflare Tunnel). Always set `APP_TOKEN` and serve over HTTPS. Note: Gmail OAuth for a Desktop client must be authorised on a machine with a browser, then copy `data/token.json` to the server.

## Privacy

Email text is stored in a local SQLite file (`data/agent.db`) and sent to the Claude API for summarising and answering. Nothing is written back to Gmail.

## Layout

```
app/gmail.py   read-only Gmail fetch + OAuth
app/ai.py      triage (section, score, summary, topics)
app/agent.py   Ask tab: tool-use loop over your stored emails
app/textclean.py  strips quotes, signatures and footers from email text
app/db.py      SQLite + full-text search + feedback weights + usage log
app/main.py    API, ranking, background sync
app/static/    PWA front end
```
