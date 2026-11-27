# TrayUP deployment checklist

This checklist covers configuration outside the source code. Never commit real credentials or service-account JSON files.

## Render backend

- Root directory: the repository root containing `wsgi.py`, `requirements.txt`, `app/`, and `migrations/`.
- Runtime: Python.
- Build command: `pip install -r requirements.txt`.
- Start command: use the command in `render.yaml` so migrations are applied before Gunicorn starts.
- Confirm Render has created the PostgreSQL database and shared key-value store referenced by `render.yaml`.
- Confirm `FLASK_CONFIG=production`, a generated `SECRET_KEY`, `DATABASE_URL`, and `RATELIMIT_STORAGE_URI` are present.
- Keep `FIREBASE_ENABLED=false` unless Firebase sync is deliberately enabled and both `FIREBASE_DATABASE_URL` and a valid secret file at the configured `FIREBASE_SERVICE_ACCOUNT_PATH` are supplied.
- For online payments, set `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, and `RAZORPAY_WEBHOOK_SECRET` in Render. Configure the Razorpay webhook to the backend payment-webhook endpoint from the API routes. Use live keys only for live payments and test keys for testing.
- For password-recovery email, set `MAIL_BACKEND=smtp`, `MAIL_HOST`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_FROM`, and `MAIL_USE_TLS`. Production must not use console email delivery.
- Review Render logs after deployment and confirm `/api/health` responds successfully.

## Vercel frontend

- Root directory: `frontend`.
- Framework preset: `Other`.
- Build command: blank.
- Output directory: `.`.
- Install command: blank.
- In `frontend/vercel.json`, verify the `/api/:path*` rewrite destination exactly matches the public HTTPS URL shown for your Render Web Service, ending with `/api/:path*`.
- Deploy again after changing `vercel.json`.

## Production smoke test

1. Open the Vercel site and confirm the menu loads from the API.
2. Sign in as a student and create a small test order using Razorpay test mode first.
3. Confirm the order appears on the kitchen board only after payment is marked paid.
4. Verify collection with the QR/token collection flow; do not use a manual status override.
5. Confirm the order appears in admin history, reports, and refund records as appropriate.
6. Test admin category and canteen settings updates, then reload and confirm persistence.
7. Test an expired/cancelled unpaid order and check that held stock is released.
8. Check browser console, Render logs, and Razorpay webhook delivery logs. Do not claim live payment readiness until the end-to-end payment and webhook flow succeeds.
