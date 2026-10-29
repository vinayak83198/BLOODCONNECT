# BloodConnect

Smart Blood Donation & Emergency Request Platform — mini-project prototype
(CIT-4, 2026-27). FastAPI backend + a static HTML/CSS/JS frontend, matching
the architecture and technology stack described in the project synopsis.

## Structure

```
backend/
  main.py              FastAPI app, CORS, centralized error handlers
  models.py             Pydantic request/response schemas + validation
  core/
    auth.py              JWT issue/verify, password hashing, role guard
    database.py          JSON-file data store (users.json, requests.json)
  routers/
    auth.py               POST /api/auth/signup, /login, /verify-email, /resend-verification,
                            /forgot-password, /reset-password, GET /me
    donors.py              GET/PUT profile, GET /api/donors/search
    requests.py            create / mine / incoming / accept / fulfill
  utils/
    matching.py           Haversine distance, blood-compatibility matrix,
                            90-day eligibility guard
  data/                  JSON "database" files (created on first write)
  seed_data.py           Populates a few demo donor/recipient accounts
  requirements.txt

frontend/
  index.html             Login & Signup, verification resend, Telegram share
  forgot-password.html   Request a password reset email
  reset-password.html    Set a new password from a secure link
  verify-email.html      Confirm the email address
  terms.html             Terms & Conditions
  donor-search.html      Donor Search
  request-form.html      Request Form
  my-requests.html       My Requests (sent + incoming matches)
  css/styles.css
  js/api.js               fetch wrapper, JWT storage, auth guard
  js/nav.js                shared top-nav behavior
  js/*.js                 per-page logic
```

## Account security features

- New registrations must accept `frontend/terms.html` and verify their email before logging in.
- Verification and password-reset links expire after 30 minutes and can only be used once.
- Password-reset requests return a generic response to avoid confirming whether an email is registered.
- Existing demo/seed users without an `email_verified` field are treated as verified for backward compatibility.
- The project uses JSON files for its mini-project prototype. For real public use, migrate to a database with transactional updates and add rate limiting, HTTPS, monitoring, and a proper privacy policy.

## Configure email delivery

The backend sends email through SMTP. Copy `backend/.env.example` as a reference and set the variables in your terminal or hosting provider. Do not commit real credentials.

For Gmail, enable 2-Step Verification and create an App Password; use that App Password as `SMTP_PASSWORD` (not your normal Gmail password). See Google's official guide: https://support.google.com/accounts/answer/185833

Example for a local macOS/Linux terminal (replace the example values):
```bash
export FRONTEND_BASE_URL="http://127.0.0.1:5500"
export SMTP_HOST="smtp.gmail.com"
export SMTP_PORT="587"
export SMTP_USERNAME="your-email@gmail.com"
export SMTP_PASSWORD="your-app-password"
export SMTP_FROM_EMAIL="your-email@gmail.com"
export SMTP_USE_TLS="true"
export BLOODCONNECT_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
```
Run the backend in the same terminal session so it inherits these variables. If email delivery is not configured, signup/verification and reset email requests cannot deliver links; configure SMTP and use the resend links.

## Running it

**1. Backend**

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # optional but recommended
pip install -r requirements.txt
python seed_data.py            # optional: adds demo donors around Indore
uvicorn main:app --reload --port 8000
```

The API is now at `http://127.0.0.1:8000`. Interactive docs at
`http://127.0.0.1:8000/docs`.

**2. Frontend**

The frontend is plain static files — no build step. Serve it with any
static server (opening the HTML files directly with `file://` also works,
since the API allows all origins in this prototype):

```bash
cd frontend
python -m http.server 5500
```

Then open `http://127.0.0.1:5500`. If your backend runs somewhere other
than `http://127.0.0.1:8000`, set it before the page scripts load, e.g. by
adding this in each HTML `<head>` before `api.js`:

```html
<script>window.BLOODCONNECT_API_BASE_URL = "https://your-api-host";</script>
```

## Python version

Tested against Python 3.11–3.14. `requirements.txt` uses floor versions
(`>=`) rather than exact pins specifically so pip resolves fresh releases
with pre-built wheels for whatever Python you're on — pinning exact old
versions is what forces a slow, often-failing source build on very new
Python releases (this bit us once already on 3.14; see git history).

## Demo login

If you ran `seed_data.py`, every seeded account uses the password
`Passw0rd!` (see `backend/seed_data.py` for the list of emails).

## Telegram sharing and deployment

The login page has a **Share on Telegram** action. It opens Telegram's share dialog with the current `index.html` URL. This URL must be publicly reachable for other people to open it; a local URL such as `127.0.0.1` or a `file://` URL only works on your own device.

To publish the project, deploy the `frontend/` directory to a static host and deploy `backend/` to a Python web host. Then:
1. Set `FRONTEND_BASE_URL` to the public frontend URL so verification/reset emails point to the hosted pages.
2. Set `BLOODCONNECT_API_BASE_URL` to the public backend URL before `js/api.js` loads on every frontend HTML page (the default is local development).
3. Configure SMTP and a strong `BLOODCONNECT_SECRET_KEY` in the backend host's environment variables.
4. Restrict CORS in `backend/main.py` to your actual frontend domain before production use.
5. Use HTTPS on both frontend and backend. Do not expose a local development server directly to the internet.

## Notes on scope

- Storage is JSON files, per the Technology Stack slide's "JSON prototype → MongoDB / PostgreSQL" note — swap `core/database.py` for a real driver when moving past the mini-project stage.
- Contact details (`accepted_by_phone`/name) are only ever included in an
  API response once a request's status is `matched`, keeping the "private
  until accepted" principle enforced server-side, not just hidden in the UI.
- `GET /api/donors/search` and `GET /api/requests/incoming` both apply the
  compatibility matrix, the radius filter, and the 90-day eligibility guard
  server-side — the frontend never re-implements that logic.


## Login OTP (no Redis required)

Every login now requires the user's email and password followed by a 6-digit email OTP. OTP records are stored in `backend/data/login_otps.json` (created automatically), with a 5-minute expiry, one-time use, a five-attempt limit, and a 30-second resend/request cooldown. This JSON storage is suitable for a local/student demo; for production or multiple backend workers, use a transactional database and shared rate limiting. Configure the SMTP variables shown in `backend/.env.example` before testing.
