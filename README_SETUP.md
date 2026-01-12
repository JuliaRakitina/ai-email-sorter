# Setup Guide

Complete step-by-step instructions for setting up Jump AI Email Sorter locally and deploying to production.

---

## Prerequisites

- **Python 3.11.9** (required for compatibility)
- **Google Cloud Project** with billing enabled (for Gmail API and Pub/Sub)
- **OpenAI API Key** (for AI categorization and summarization)
- **Gmail Account(s)** for testing
- **Git** (for cloning repository)

---

## Local Setup

### 1. Clone Repository

```bash
git clone <repository-url>
cd jump_email_sorter
```

### 2. Create Virtual Environment

```bash
python3.11 -m venv .venv

# Activate virtual environment
# On macOS/Linux:
source .venv/bin/activate

# On Windows:
.venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Edit `.env` with the following variables:

```env
# App Configuration
SECRET_KEY=your-random-secret-key-here-minimum-32-characters
BASE_URL=http://localhost:8000

# Google OAuth (see Google OAuth Setup section)
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# OpenAI
OPENAI_API_KEY=sk-your-openai-api-key
OPENAI_MODEL=gpt-4o-mini

# Optional: Gmail Sync Query
SYNC_QUERY=in:inbox newer_than:3d

# Optional: Pub/Sub Configuration (for real-time sync)
GCP_PROJECT_ID=your-gcp-project-id
PUBSUB_TOPIC_NAME=gmail-notifications
PUBSUB_PUSH_AUDIENCE=https://your-domain.com
```

**Important**: Generate a secure `SECRET_KEY` (minimum 32 characters). This is used for encrypting OAuth tokens and signing session cookies.

### 5. Initialize Database

The database is automatically initialized on first run. No manual migration steps required.

### 6. Start Development Server

```bash
uvicorn app.asgi:app --reload --port 8000
```

The application will be available at: **http://localhost:8000**

---

## Google OAuth Setup

### 1. Create OAuth Client ID

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select or create a project
3. Navigate to **APIs & Services** → **Credentials**
4. Click **Create Credentials** → **OAuth client ID**
5. Choose **Web application**
6. Configure:
   - **Name**: Jump Email Sorter (or your preferred name)
   - **Authorized JavaScript origins**:
     - `http://localhost:8000` (for local development)
     - `https://your-domain.com` (for production)
   - **Authorized redirect URIs**:
     - `http://localhost:8000/auth/google/callback` (for local)
     - `https://your-domain.com/auth/google/callback` (for production)

### 2. OAuth Consent Screen

1. Navigate to **APIs & Services** → **OAuth consent screen**
2. Choose **External** user type (for testing)
3. Fill in required fields:
   - App name, user support email, developer contact
4. Add **Scopes**:
   - `https://www.googleapis.com/auth/gmail.readonly`
   - `https://www.googleapis.com/auth/gmail.modify`
   - `https://www.googleapis.com/auth/userinfo.email`
   - `https://www.googleapis.com/auth/userinfo.profile`
5. Add **Test Users** (for external apps):
   - Add your Gmail address(es) that will be used for testing
   - Example: `webshookeng@gmail.com`

### 3. Copy Credentials

Copy the **Client ID** and **Client Secret** from the OAuth client credentials page into your `.env` file.

### 4. Refresh Token Notes

**Important**: Google only provides `refresh_token` on the first OAuth authorization. If you need to get a new refresh token:

1. Go to https://myaccount.google.com/permissions
2. Find your app and click **Remove** or **Revoke Access**
3. Clear browser cookies for your app domain
4. Sign in again — this will return a new `refresh_token`

The app handles token refresh automatically using stored refresh tokens.

---

## Gmail API + Pub/Sub Setup (Auto Sync)

For real-time email processing via Gmail push notifications:

### 1. Enable APIs

In Google Cloud Console:

1. **APIs & Services** → **Library**
2. Enable the following APIs:
   - **Gmail API**
   - **Cloud Pub/Sub API**

### 2. Create Pub/Sub Topic

1. Navigate to **Pub/Sub** → **Topics**
2. Click **Create Topic**
3. Name: `gmail-notifications` (or your preferred name)
4. Click **Create**

### 3. Create Push Subscription

1. In your topic, click **Create Subscription**
2. Choose **Push** delivery type
3. **Subscription ID**: `gmail-push-subscription`
4. **Endpoint URL**: `https://your-domain.com/webhooks/pubsub`
   - For local testing with Cloudflare Tunnel: `https://your-tunnel-url.trycloudflare.com/webhooks/pubsub`
5. **Audience**: Set to your domain (e.g., `https://your-domain.com`)
6. Click **Create**

### 4. Configure Webhook Endpoint

The webhook endpoint is automatically available at `/webhooks/pubsub`. Ensure:

- Endpoint is publicly accessible (HTTPS required)
- JWT verification is enabled (automatic)
- Pub/Sub service account has permission to publish

### 5. Gmail Watch Setup

The app automatically sets up Gmail Watch when you:
- Sign in with a Gmail account
- Connect an additional Gmail account

**Watch Expiration**: Gmail Watch subscriptions expire after 7 days. The app automatically renews watches before expiration.

**Watch Limits**: Gmail allows one active watch per mailbox. The app handles watch renewal transparently.

### 6. Update Environment Variables

Add to your `.env`:

```env
GCP_PROJECT_ID=your-gcp-project-id
PUBSUB_TOPIC_NAME=gmail-notifications
PUBSUB_PUSH_AUDIENCE=https://your-domain.com
```

---

## Cloudflare Tunnel (Local Webhook Testing)

For local development, Cloudflare Tunnel provides a public HTTPS endpoint that Gmail and Pub/Sub can reach.

### 1. Install cloudflared

**macOS**:
```bash
brew install cloudflare/cloudflare/cloudflared
```

**Linux**:
```bash
# Download from https://github.com/cloudflare/cloudflared/releases
# Or use package manager
```

**Windows**:
Download from https://github.com/cloudflare/cloudflared/releases

### 2. Run Tunnel

```bash
cloudflared tunnel --url http://localhost:8000
```

This will output a URL like:
```
https://random-name.trycloudflare.com
```

### 3. Update Configuration

1. Update `.env`:
   ```env
   BASE_URL=https://random-name.trycloudflare.com
   ```

2. Update Google Cloud Console:
   - **OAuth**: Add tunnel URL to authorized origins and redirect URIs
   - **Pub/Sub**: Update push subscription endpoint to `https://random-name.trycloudflare.com/webhooks/pubsub`

3. Restart the application to pick up new `BASE_URL`

### 4. Common Issues

**Tunnel URL Changes**: Each time you restart `cloudflared`, you get a new URL. Update your configuration accordingly.

**Timeout Errors**: Cloudflare free tunnels may timeout on long requests. For production, use a persistent domain or deploy to Render.

**JWT Verification**: Pub/Sub JWT verification requires the correct audience. Ensure `PUBSUB_PUSH_AUDIENCE` matches your tunnel URL.

---

## Render Deployment

### 1. Prepare Repository

1. Push code to GitHub
2. Ensure `Dockerfile` exists (if using Docker) or configure build commands

### 2. Create Web Service

1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click **New** → **Web Service**
3. Connect your GitHub repository
4. Configure:
   - **Name**: jump-email-sorter (or your preferred name)
   - **Region**: Choose closest to your users
   - **Branch**: `main` (or your deployment branch)
   - **Root Directory**: (leave empty if root)
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.asgi:app --host 0.0.0.0 --port $PORT`

### 3. Environment Variables

Add all required environment variables in Render dashboard:

```env
SECRET_KEY=<generate-secure-random-key>
BASE_URL=https://your-service.onrender.com
GOOGLE_CLIENT_ID=<your-client-id>
GOOGLE_CLIENT_SECRET=<your-client-secret>
OPENAI_API_KEY=<your-openai-key>
GCP_PROJECT_ID=<your-gcp-project>
PUBSUB_TOPIC_NAME=gmail-notifications
PUBSUB_PUSH_AUDIENCE=https://your-service.onrender.com
```

### 4. Persistent Disk (for SQLite)

1. In Render dashboard, go to your service
2. Navigate to **Disks** tab
3. Create a new disk:
   - **Name**: `database`
   - **Mount Path**: `/opt/render/project/src`
   - **Size**: 1 GB (adjust as needed)

This ensures the SQLite database persists across deployments.

### 5. Update Google Cloud Console

1. **OAuth Consent Screen**:
   - Add `https://your-service.onrender.com` to authorized origins
   - Add `https://your-service.onrender.com/auth/google/callback` to redirect URIs

2. **Pub/Sub Subscription**:
   - Update push endpoint to `https://your-service.onrender.com/webhooks/pubsub`
   - Update audience to `https://your-service.onrender.com`

### 6. Deploy

1. Click **Manual Deploy** or push to trigger automatic deploy
2. Monitor build logs for errors
3. Once deployed, test OAuth flow and webhook endpoint

### 7. Health Check

Render automatically health checks your service. Ensure your app responds to root path `/` for health checks.

---

## Common Issues & Troubleshooting

### Missing Refresh Token

**Symptom**: App works initially but fails to refresh tokens later.

**Solution**:
1. Revoke app access at https://myaccount.google.com/permissions
2. Clear browser cookies
3. Sign in again to get a new `refresh_token`

**Prevention**: The app stores refresh tokens encrypted. Ensure `SECRET_KEY` is stable and not changed after initial setup.

### OAuth Scope Errors

**Symptom**: "Not all requested scopes were granted" warning.

**Cause**: User denied some permissions during OAuth flow.

**Solution**: This is informational. The app works with granted scopes. For full functionality, ensure all required scopes are approved.

### Pub/Sub 403 Forbidden

**Symptom**: Webhook returns 403 when Pub/Sub tries to deliver messages.

**Causes**:
- JWT verification failing (check `PUBSUB_PUSH_AUDIENCE` matches your domain)
- Pub/Sub service account lacks permissions
- Webhook endpoint not publicly accessible

**Solution**:
1. Verify `PUBSUB_PUSH_AUDIENCE` in `.env` matches your `BASE_URL`
2. Ensure webhook endpoint is HTTPS and publicly reachable
3. Check Pub/Sub subscription configuration

### Cloudflare 524 Timeout

**Symptom**: Requests timeout on Cloudflare tunnel.

**Cause**: Free Cloudflare tunnels have timeout limits.

**Solution**: Use Render deployment for production, or upgrade to Cloudflare paid plan for persistent tunnels.

### SQLite Locked Errors

**Symptom**: "database is locked" errors during concurrent operations.

**Cause**: SQLite WAL mode helps but has limits under high concurrency.

**Solution**:
- Ensure WAL mode is enabled (automatic via event listener)
- Reduce concurrent operations
- For production scale, consider migrating to PostgreSQL

### Counts Not Updating

**Symptom**: Email counts in dashboard don't update immediately.

**Cause**: Counts are calculated on page load, not real-time.

**Solution**: Refresh the page. For real-time updates, the unsubscribe status polling works independently.

### Unsubscribe Notifications Not Showing

**Symptom**: Unsubscribe completes but no notification appears.

**Causes**:
- JavaScript polling stopped (check browser console)
- Toastr library not loaded
- Notification logic filtered out status

**Solution**:
1. Check browser console for JavaScript errors
2. Verify Toastr is loaded (check Network tab)
3. Ensure page wasn't refreshed during processing (polling continues for 4 minutes)

---

## Running Tests

### Basic Test Execution

```bash
# Run all tests
pytest

# Verbose output
pytest -v

# Quiet output (minimal)
pytest -q

# Run specific test file
pytest tests/test_unsubscribe.py

# Run specific test
pytest tests/test_unsubscribe.py::test_parse_list_unsubscribe_one_click
```

### Test Coverage

```bash
# Generate coverage report
pytest --cov=app --cov-report=html

# View HTML report
open htmlcov/index.html  # macOS
# or open htmlcov/index.html in browser
```

### Test Structure

Tests are organized by functionality:
- `test_ai.py`: AI categorization and summarization
- `test_gmail_service.py`: Gmail API parsing functions
- `test_unsubscribe.py`: Unsubscribe agent logic
- `test_unsubscribe_automation.py`: Background unsubscribe processing
- `test_bulk_actions.py`: Bulk operations
- `test_webhook.py`: Pub/Sub webhook handling
- `test_routes.py`: API endpoint testing

### Mocking Strategy

All external services are mocked:
- **Gmail API**: Mocked using `unittest.mock`
- **OpenAI API**: Mocked responses for deterministic tests
- **HTTP Requests**: Unsubscribe HTTP calls are mocked
- **Database**: Each test uses isolated temporary SQLite database

### Test Fixtures

Common fixtures in `tests/conftest.py`:
- `test_engine`: Temporary database engine
- `session`: Database session
- `client`: FastAPI test client
- `logged_in_session`: Authenticated user session
- `test_gmail_account`: Sample Gmail account
- `test_category`: Sample category
- `test_email_record`: Sample email record

---

## Next Steps

After setup:

1. **Sign in** with Google OAuth
2. **Create categories** for email organization
3. **Connect Gmail accounts** (can add multiple)
4. **Sync emails** manually or wait for real-time processing
5. **Review categorized emails** in dashboard
6. **Use bulk actions** to manage emails efficiently
7. **Monitor unsubscribe status** for automated processing

For production deployment, ensure:
- Secure `SECRET_KEY` (use strong random value)
- HTTPS enabled (required for OAuth and Pub/Sub)
- Proper error monitoring and logging
- Database backups (for SQLite, backup the `.db` file)

---

## Support

For additional help:
- Check application logs for detailed error messages
- Review Google Cloud Console for API quota and error logs
- Verify environment variables are correctly set
- Ensure all required APIs are enabled in Google Cloud Console
