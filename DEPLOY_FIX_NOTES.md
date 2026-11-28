# Deployment fixes

This note lists what was changed to make the Render deployment start, and what must be set in
the Render dashboard before the first successful deploy.

## Changes in this package

| File | Change | Why |
| --- | --- | --- |
| `requirements.txt` | Added `qrcode>=7.4,<9` and `requests>=2.32,<3` | `app/services/upi_service.py` imports `qrcode`, which was missing. The app crashed on import (`No module named 'qrcode'`), so gunicorn never started and `flask db upgrade` never ran. `requests` is imported directly by `razorpay_client.py`. |
| `app/services/upi_service.py` | `qrcode` is imported inside `render_upi_qr_svg` instead of at module level | Importing the app, and therefore pytest's `conftest.py`, no longer needs the package. The QR function still needs it. |
| `app/__init__.py` | `create_app` now calls `validate_runtime_settings` | The presence settings check (canteen coordinates, https `PUBLIC_BASE_URL`, token and session TTL bounds) was written and tested but never called at startup, so production did not fail closed as `PRESENCE_VERIFICATION.md` says it does. |
| `render.yaml` | Added `PUBLIC_BASE_URL`, `CANTEEN_LATITUDE`, `CANTEEN_LONGITUDE`, `UPI_VPA` | Production refuses to start without the first three, and UPI orders need `UPI_VPA`. |
| `migrations/versions/3b4c5d6e7f8a_seed_admin_user.py` | Body replaced with a no-op | The migration created an administrator and a kitchen account with passwords published in the source code (`AdminPass123!`, `KitchenPass123!`). It ran on every production deploy. |
| `migrations/versions/a9f8e7d6c5b4_deactivate_demo_accounts.py` | New migration | Deactivates the two demo accounts, but only while they still use the published password. Accounts whose password has been changed are left alone. Nothing is deleted. |
| `docs/qr/trayup-github-qr.svg`, `.png` | New | QR code that opens `https://github.com/trayup-team/TrayUP.git`. Verified by decoding the rendered image. |

## Set these in Render before deploying

- `CANTEEN_LATITUDE` and `CANTEEN_LONGITUDE`: the surveyed coordinates of the canteen. Without them
  the service refuses to start. Presence check-in uses these values with a 100 m radius.
- `UPI_VPA`: the UPI address payments go to, for example `name@bank`. Needed only for UPI orders.
- `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`, `MAIL_HOST`, `MAIL_USERNAME`,
  `MAIL_PASSWORD`, `MAIL_FROM`: already declared as `sync: false` in `render.yaml`. Fill them in if
  you use those features.

## After the first successful deploy

1. Rotate any password that was ever used with the demo accounts. The migration deactivates them,
   but treat the published passwords as known to everyone.
2. Create the real administrator from the Render shell, then sign in and enrol two-factor authentication:

       flask --app wsgi:app setup-admin --email you@example.com --name "Your Name"

3. Check `https://trayup.onrender.com/api/health` returns `{"status": "ok", "database": "ok"}`.

## Not verified here

The build environment for this package had no network access, so these were not run:
the full pytest suite (CI runs it on Python 3.11), `pip-audit --strict` (CI runs it on every
push), `bandit`, and the migrations against PostgreSQL (`tests/test_migrations.py` supports this
through `TRAYUP_MIGRATION_DATABASE_URL`). Run them in CI or locally before relying on this build.
