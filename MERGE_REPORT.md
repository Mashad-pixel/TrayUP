# TrayUP final merged package

## Source archives merged

- `TrayUP-fixed-2.zip` was used as the canonical base for backend services, route registration, migration scripts, and Python tests.
- `TrayUP-errors-3-onward-fixed(1).zip` contributed the later frontend fixes, frontend regression tests, CI workflow additions, and issue 3-onward documentation.

The second archive was **not** applied as a blanket overwrite. Several of its overlapping backend files removed safeguards or coverage present in the first archive. The merged package therefore preserves the stronger first-archive versions for those files.

## Preserved backend and migration behavior

The merge retains the first archive's:

- batched unpaid-order expiry sweep and expiry-health CLI options;
- menu item deletion checks and corresponding route;
- inventory reservation release-state update;
- maximum admin-order pagination bound;
- defensive role decorator behavior;
- detailed staff validation responses and unique-email race handling;
- complete authorization matrix and tests that create valid server-side sessions;
- SQLite-safe stock-reservation migration that drops dependent check constraints before dropping the column.

The migration directory contains 24 revision files, not 17. A static revision-graph check found one root (`b6561fd9dcfb`) and one head (`a9f8e7d6c5b4`). The file for revision `8a9b0c1d2e3f` was renamed to match its revision ID; the ID itself is unchanged. This does not prove an existing production database can be upgraded safely; back it up first and test the migration against a copy.

## Included later frontend fixes

The merge brings in the later archive's:

- admin order search/filter request queuing and the `pending_payment` filter;
- server-backed category/menu/settings/refund/report loading states instead of obsolete “API unavailable” placeholders;
- corrected payment-status labels and unpaid-order confirmation wording;
- checkout idempotency-key retention through the payment flow and refresh recovery;
- protection against opening a second payment when the server returns an already-paid order;
- cart-storage failure handling on menu, product, cart, and reorder flows;
- optional API `AbortSignal` cancellation and distinct cancellation/timeout errors;
- guarded demo-mode storage operations and a post-payment cart-clear warning.

## Tests and CI

The merged package keeps the fuller Python test coverage from the first archive. It includes the later frontend regression tests for API cancellation/timeouts, blocked storage, queued admin searches, pending-payment messaging, and checkout idempotency. GitHub Actions now installs frontend test dependencies and runs the frontend suite as well as the Python and JavaScript checks.

`tests/frontend/README.md` uses `npm install` because the package currently has no `package-lock.json`; `npm ci` would therefore fail.

## Validation performed for this merged archive

See `MERGE_VALIDATION.txt` for the checks run while creating this archive. Static compilation and archive integrity checks do not replace the full backend integration suite, jsdom suite, or live deployment checks.

## Deployment reminders

- Keep `wsgi.py`, `requirements.txt`, `app/`, and `migrations/` together at the Render service root.
- Set Vercel's root directory to `frontend` when the repository root is the contents of the `TrayUP` folder. If the repository has an outer folder, include that folder in the Vercel root path.
- Verify `frontend/vercel.json` points to the actual public Render URL. The archive retains the existing `trayup-mashad-api.onrender.com` target because the actual URL was not supplied with these two files.
- Configure provider secrets in Render, not in source control. See `DEPLOYMENT_CHECKLIST.md`.
