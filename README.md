# Jump AI Email Sorter

An intelligent email management application that automatically categorizes, summarizes, and organizes Gmail inboxes using AI. Built with FastAPI, this production-ready system processes incoming emails in real-time, provides intelligent categorization, and offers powerful bulk management tools including automated unsubscribe capabilities.

**Built for:** Professionals managing multiple Gmail accounts who need intelligent email organization without manual sorting.

**Why it's useful:** Automatically processes incoming emails, categorizes them using AI, provides concise summaries, and handles bulk operations including unsubscribe automation—all while keeping your Gmail inbox organized and archived.

---

## Key Features

### Authentication & Accounts
- **Google OAuth Integration**: Secure sign-in with Google accounts
- **Multi-Inbox Support**: Connect and manage multiple Gmail accounts per user
- **Per-Account Categories**: Each Gmail account maintains its own category structure
- **Active Account Selection**: Switch between connected accounts seamlessly

### AI Email Processing
- **Intelligent Categorization**: Uses OpenAI GPT-4o-mini to automatically assign emails to user-defined categories
- **AI Summarization**: Generates concise summaries of email content for quick review
- **Uncategorized Fallback**: Emails that don't match any category are placed in a system "Uncategorized" category
- **Smart Matching**: Analyzes subject, snippet, and body text to determine best category fit

### Categories & Inbox Management
- **Custom Categories**: Create categories with names and descriptions to guide AI classification
- **System Categories**: Automatic "Uncategorized" category for unmatched emails
- **Category Scoping**: Categories are scoped per Gmail account for multi-inbox workflows
- **Email Archiving**: Processed emails are automatically archived in Gmail to keep inbox clean

### Automation (Sync + Webhooks)
- **Real-Time Push Notifications**: Gmail Watch API + Google Pub/Sub for instant email processing
- **Manual Sync**: On-demand sync button to import recent inbox emails(Per sync, we pull up to 10 emails from the last 3 days.)
- **Automatic Watch Renewal**: Gmail watch subscriptions are automatically renewed before expiration
- **History Sync**: Processes email changes via Gmail history API for reliable state management
- **Background Processing**: Non-blocking async jobs for email processing and unsubscribe operations

### Bulk Actions & Unsubscribe Automation
- **Bulk Delete**: Trash multiple emails in Gmail with a single action
- **Bulk Category Assignment**: Move multiple emails between categories
- **Best-Effort Unsubscribe Agent**: Automated unsubscribe processing with multiple fallback strategies:
  - **RFC8058 One-Click**: Supports List-Unsubscribe-Post one-click unsubscribe
  - **Header Link**: Extracts and follows List-Unsubscribe header links
  - **HTML Form Parsing**: Automatically fills and submits unsubscribe forms (no JavaScript required)
  - **Manual Fallback**: Provides unsubscribe URLs when automation isn't possible
- **Status Tracking**: Per-email unsubscribe status (success, attempted, manual_required, failed)
- **Live UI Updates**: Real-time status updates via polling with detailed notifications

### UX & Performance
- **Modern Dark Theme**: Polished dark UI with responsive design
- **Fully Responsive**: Works seamlessly on desktop, tablet, and mobile devices
- **Live Status Updates**: Automatic UI refresh for background operations
- **Toast Notifications**: Detailed success/failure notifications for user actions
- **Optimized Performance**: Lightweight metadata requests, stored HTML bodies, efficient database queries

---

## How It Works

### High-Level Flow

1. **User Authentication**
   - User signs in with Google OAuth
   - App requests Gmail API access with appropriate scopes
   - User can connect additional Gmail accounts after initial login

2. **Category Setup**
   - User creates custom categories with descriptive names
   - Categories are stored per Gmail account for multi-inbox support

3. **Email Processing**
   - **Real-Time Path**: New emails trigger Gmail Watch → Pub/Sub webhook → background processing
   - **Manual Path**: User clicks "Sync New Emails" to import recent inbox messages
   - Emails are fetched, parsed, and sent to OpenAI for categorization and summarization
   - Processed emails are automatically archived in Gmail

4. **AI Classification**
   - Subject, snippet, and body text are analyzed by GPT-4o-mini
   - AI matches email to best-fitting user category based on category descriptions
   - If no match, email goes to "Uncategorized" system category

5. **Email Management**
   - User reviews emails in category views with AI summaries
   - Bulk actions available: delete, assign category, unsubscribe
   - Unsubscribe automation runs in background with live status updates

6. **Unsubscribe Processing**
   - Background task discovers unsubscribe mechanism (headers → HTML links)
   - Attempts one-click, then form-based unsubscribe
   - Updates email record with status, method, URL, and error details
   - UI polls for status updates and shows notifications

---

## Architecture Overview

### Backend Stack
- **FastAPI**: Modern, fast web framework with async support
- **SQLModel**: Type-safe ORM built on SQLAlchemy with Pydantic validation
- **SQLite**: Lightweight database with WAL mode for better concurrency
- **Jinja2**: Server-side templating for HTML rendering

### External Services
- **Google Gmail API**: Email reading, modification, archiving, and watch management
- **Google OAuth 2.0**: Secure authentication and authorization
- **Google Cloud Pub/Sub**: Real-time push notifications for Gmail changes
- **OpenAI API**: GPT-4o-mini for email categorization and summarization

### Frontend
- **Server-Rendered HTML**: Jinja2 templates with minimal JavaScript
- **Bootstrap 5**: CSS framework for responsive layout
- **Custom Dark Theme**: Professional dark UI with CSS variables
- **Toastr.js**: Toast notifications for user feedback
- **Vanilla JavaScript**: Polling for live updates, no heavy frameworks

### Background Processing
- **FastAPI BackgroundTasks**: Non-blocking async job execution
- **HTTPX**: Async HTTP client for unsubscribe requests
- **BeautifulSoup4**: HTML parsing for form-based unsubscribe

### Security & Data
- **Encrypted Tokens**: Gmail OAuth tokens encrypted at rest using Fernet
- **Session Management**: Secure session cookies with configurable expiration
- **JWT Verification**: Pub/Sub webhook JWT validation for security

---

## Screenshots / Demo

### Dashboard
The main dashboard displays all connected Gmail accounts with sync status, last sync time, and active account indicators. Categories are shown with email counts and system category badges.

### Category View
Email list view with AI summaries, unsubscribe status badges, and bulk action controls. Responsive table layout with horizontal scrolling on mobile.

### Email Detail
Full email content display with HTML rendering, unsubscribe status details, and AI summary. Dark theme with white email body background for readability.

### Unsubscribe Status
Real-time status updates with color-coded badges (success, attempted, manual required, failed) and detailed notifications showing method, URL, and error information.

<img width="1138" height="705" alt="image" src="https://github.com/user-attachments/assets/fcc6cf8c-9000-4d9f-9f77-9392e30ce24b" />
<img width="1372" height="696" alt="image" src="https://github.com/user-attachments/assets/10399dc4-61f6-438e-8b99-5dba6eb61dc7" />
<img width="1253" height="745" alt="image" src="https://github.com/user-attachments/assets/c8b3a01a-e422-4eab-9cf5-944b594d9de4" />
<img width="1299" height="863" alt="image" src="https://github.com/user-attachments/assets/08d6dd46-ad79-4d98-841b-95ff7bae536b" />

---

## Unsubscribe Automation

The unsubscribe feature is a **best-effort agent** designed to handle the majority of unsubscribe scenarios without requiring browser automation or JavaScript execution.

### Supported Methods (in priority order)

1. **RFC8058 One-Click Unsubscribe**
   - Detects `List-Unsubscribe-Post: List-Unsubscribe=One-Click` header
   - Performs HTTP POST with `List-Unsubscribe=One-Click` body
   - Highest success rate for compliant senders

2. **Header Link Unsubscribe**
   - Extracts HTTPS URL from `List-Unsubscribe` header
   - Attempts GET request to unsubscribe endpoint
   - Falls back to form parsing if page contains unsubscribe form

3. **HTML Form-Based Unsubscribe**
   - Parses HTML response for forms containing "unsubscribe" in action or button text
   - Extracts form fields (including hidden inputs)
   - Submits form via POST or GET as specified
   - Detects success via response text/title analysis

4. **Body Link Discovery**
   - Searches email HTML body for unsubscribe links
   - Uses first matching link as unsubscribe target
   - Falls back to form parsing if link leads to form page

5. **Manual Fallback**
   - When automation isn't possible (mailto links, JavaScript-heavy pages, CAPTCHAs)
   - Stores unsubscribe URL for manual action
   - Status marked as "manual_required" with clickable link

### Safety & Transparency

- **Short Timeouts**: 10-second HTTP timeout to prevent hanging
- **User-Agent Header**: Identifies requests as automated unsubscribe agent
- **No Authentication Bypass**: Does not attempt to login or bypass security measures
- **No CAPTCHA Handling**: Marks as manual_required when CAPTCHA detected
- **Per-Email Status**: Each email tracks unsubscribe status, method, URL, and error details
- **Error Logging**: Comprehensive logging for debugging and transparency

### Status Tracking

Each email record stores:
- `unsubscribe_status`: `success`, `attempted`, `manual_required`, or `failed`
- `unsubscribe_method`: `one_click`, `header_link`, `body_link`, `html_form`, or `manual`
- `unsubscribe_url`: Discovered unsubscribe URL
- `unsubscribe_error`: Error message if failed
- `unsubscribed_at`: Timestamp when successfully unsubscribed

---

## Limitations & Tradeoffs

### Unsubscribe Automation
- **No Browser Automation**: Does not use Playwright or Selenium, limiting ability to handle JavaScript-heavy unsubscribe flows
- **Best-Effort Approach**: Some senders require manual unsubscribe (marked clearly in UI)
- **Form Detection Heuristics**: Form selection based on keywords; may not handle all edge cases

### Database
- **SQLite**: Chosen for simplicity and portability; suitable for single-instance deployments
- **WAL Mode**: Enabled for better concurrency, but still limited compared to PostgreSQL for high concurrency
- **No Connection Pooling**: Simple session-per-request model

### Background Jobs
- **In-Memory Tracking**: Background tasks use FastAPI's BackgroundTasks (no persistent job queue)
- **No Retry Logic**: Failed unsubscribe attempts are logged but not automatically retried
- **Single Instance**: Background tasks run on the same process; not suitable for horizontal scaling

### AI Decisions
- **Best-Effort Classification**: AI may misclassify emails; users can manually reassign categories
- **Model Limitations**: Uses GPT-4o-mini for cost efficiency; may have lower accuracy than larger models
- **No Learning**: System does not learn from user corrections

### Real-Time Updates
- **Polling-Based**: UI polls for status updates rather than using WebSockets
- **Polling Interval**: 2-second intervals with maximum 120 polls (4 minutes)

---

## Testing

The project includes comprehensive test coverage using pytest:

### Test Structure
- **Unit Tests**: Individual function testing (AI prompting, Gmail parsing, unsubscribe logic)
- **Integration Tests**: End-to-end route testing with mocked external services
- **Webhook Tests**: Pub/Sub message parsing and JWT verification
- **Bulk Actions Tests**: Delete, unsubscribe, and category assignment workflows

### Test Features
- **Zero Real Network Calls**: All external APIs (Google, OpenAI, unsubscribe URLs) are mocked
- **Isolated Database**: Each test uses a temporary SQLite database
- **Deterministic**: Tests run fast and reliably without external dependencies
- **Comprehensive Mocking**: Gmail API, OpenAI API, and HTTP requests are fully mocked

### Running Tests
```bash
pytest                    # Run all tests
pytest -v                 # Verbose output
pytest -q                 # Quiet output
pytest tests/test_unsubscribe.py  # Run specific test file
```

See `README_SETUP.md` for detailed testing instructions.

---

## Deployment

### Render (Recommended)

The application is configured for deployment on Render with:
- **Docker Support**: Containerized deployment
- **Environment Variables**: Secure configuration via Render dashboard
- **Persistent Disk**: SQLite database persists across deployments
- **Auto-Deploy**: GitHub integration for automatic deployments

### Cloudflare Tunnel (Local Development)

For local webhook testing, Cloudflare Tunnel provides a public HTTPS endpoint:
- Install `cloudflared`
- Run tunnel pointing to localhost:8000
- Update `BASE_URL` and Pub/Sub webhook endpoint
- Enables Gmail Watch and Pub/Sub to reach local development server

### Environment Variables

Required:
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`: OAuth credentials
- `OPENAI_API_KEY`: OpenAI API key for AI features
- `SECRET_KEY`: Encryption key for tokens and sessions
- `BASE_URL`: Public URL for OAuth redirects and webhooks

Optional:
- `GCP_PROJECT_ID`: Google Cloud project for Pub/Sub
- `PUBSUB_TOPIC_NAME`: Pub/Sub topic name
- `PUBSUB_PUSH_AUDIENCE`: Pub/Sub push subscription audience
- `SYNC_QUERY`: Gmail query for manual sync (default: `in:inbox newer_than:3d`)

See `README_SETUP.md` for detailed deployment instructions.

---

## License / Challenge Note

This project was built as part of a 72-hour hiring challenge to demonstrate:
- Full-stack development capabilities
- Integration with multiple external APIs
- Production-ready code quality
- Comprehensive testing
- Professional documentation

**Development Tools**: This project was developed with AI assistance using Cursor IDE and ChatGPT for code generation, debugging, and optimization. The final codebase represents a collaborative effort between human engineering decisions and AI-assisted development.

**Production Readiness**: While optimized for the challenge timeline, the codebase follows production best practices including error handling, logging, security considerations, and comprehensive testing. Some tradeoffs (SQLite, in-memory jobs) were made for simplicity but can be upgraded for larger scale deployments.

---

## Quick Start

For detailed setup instructions, see [README_SETUP.md](README_SETUP.md).

**TL;DR:**
1. Clone repository
2. Create virtual environment (Python 3.11.9)
3. Install dependencies: `pip install -r requirements.txt`
4. Configure `.env` with Google OAuth and OpenAI credentials
5. Run: `uvicorn app.asgi:app --reload --port 8000`
6. Open http://localhost:8000 and sign in with Google

---

## Support

For issues, questions, or contributions, please refer to the setup guide in `README_SETUP.md` for troubleshooting common problems.
