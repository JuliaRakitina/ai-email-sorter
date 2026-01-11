## Setup Guide (Local)

### 1) Create venv (Python 3.11.9)
```bash
python3.11 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2) Create Google OAuth credentials
In Google Cloud Console:
- APIs & Services → Library → enable **Gmail API**
- OAuth consent screen → External (dev) + add test user: **webshookeng@gmail.com**
- Credentials → Create Credentials → OAuth client ID (Web application)
  - Authorized JavaScript origins:
    - http://localhost:8000
  - Authorized redirect URIs:
    - http://localhost:8000/auth/google/callback

Copy Client ID + Secret into `.env`.

### 3) Configure environment
```bash
cp .env.example .env
# edit .env with:
# GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, OPENAI_API_KEY, SECRET_KEY
```

### 4) Run the app
```bash
uvicorn app.asgi:app --reload --port 8000
```

Open:
- http://localhost:8000

### 5) Use the app
1. Sign in with Google
2. Add categories
3. Click **Sync New Emails** (imports inbox emails matching `SYNC_QUERY`)
4. Emails get AI-categorized + summarized, and archived in Gmail
5. Click a category to see email summaries, then bulk delete/unsubscribe

---

## Deploy Guide (Render)

### Option A: Docker (recommended)
1. Push repo to GitHub
2. Create a new Render **Web Service** from repo
3. Choose **Docker**
4. Set environment variables:
   - BASE_URL=https://<your-render-service>.onrender.com
   - SECRET_KEY=<random-long>
   - GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET
   - OPENAI_API_KEY
5. In Google Console, add the Render URL:
   - Authorized origins: https://<your-render-service>.onrender.com
   - Redirect URI: https://<your-render-service>.onrender.com/auth/google/callback
6. Deploy, then sign in and sync

### Notes
- This challenge expects real-time sorting on incoming mail. For a quick demo, we use manual sync.
  To go further, add: Gmail push notifications (watch) + webhook endpoint + background worker.
