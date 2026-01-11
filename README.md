# Jump AI Email Sorter (Python 3.11.9)

A minimal, deployable AI email sorting app:
- Google OAuth (test users supported)
- Create custom categories (name + description)
- Import new Gmail inbox messages, AI-categorize + summarize, then **archive** in Gmail
- View emails by category; open original content
- Bulk actions: delete (Gmail trash) or unsubscribe (best-effort via List-Unsubscribe)

## Tech choices
- Backend: FastAPI + Jinja templates (simple server-rendered UI)
- DB: SQLite via SQLModel
- OAuth: Authlib (popular + quick)
- Gmail: Google API Python Client
- AI: OpenAI SDK (set `OPENAI_API_KEY`), default model `gpt-4o-mini`

> Note: Full "agentic" unsubscribe (arbitrary forms) is hard to guarantee in 72 hours.
> This implementation prioritizes standards-based unsubscribe via `List-Unsubscribe` and common patterns.

See **Setup Guide** at the bottom of this file.
