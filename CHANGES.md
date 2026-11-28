# Changes

1. **Checkout idempotency key persists across refresh** (`frontend/student/js/checkout.js`).
   The key is stored in sessionStorage, tied to the cart contents, so a retry after a refresh or a
   dropped response reuses it and the server returns the original order. It is cleared when the
   order is completed or can no longer be paid.
2. **Confirmation page closing tag fixed** (`frontend/student/confirmation.html`): `</bod</html>` is now `</body></html>`.
3. **Order tracking pages through all orders** (`frontend/student/js/tracking.js`): 10 orders per page
   with a "Load more orders" button, replacing the single `per_page=50` request. A failed load-more
   keeps the orders already shown.
4. **Admin reports use the real reporting API** (`frontend/admin/js/reports.js`): overview, sales by day,
   top items, categories and busiest hours come from `/api/admin/reports/*` for the chosen date range.
   The hardcoded sample figures and the fake CSV export were removed; the CSV is built from the loaded data.
5. **Admin menu uses the real menu API** (`frontend/admin/js/menu.js`): lists items from `/api/admin/menu`,
   and adds, edits and enables/disables items through the existing endpoints. The localStorage demo data
   was removed. The backend has no delete endpoint, so there is no delete action.
6. **Staff management uses the protected staff API** (`frontend/admin/js/staff.js`): administrators can list,
   create, update, and deactivate staff through the server-backed management routes. No sample staff accounts
   are shown in production.
7. **Outdated admin placeholder text removed** from `menu.html` and `reports.html`.

## Round 2

8. **Password recovery and backup codes** (item 6). New endpoints under `/api/forgot/*`,
   `/api/recovery/*` and `/api/auth/recovery-codes`, matching the login page's recovery screens.
   - Email code: 6 digits, expires after 5 minutes, locks after 5 wrong tries, single use. Resend
     is limited to one every 30 seconds and five per hour. Only an HMAC of the code is stored.
   - Verifying the code returns a reset token that works once and expires after 10 minutes.
   - Replies never reveal whether an email has an account.
   - A password reset signs out every session (sessions record when they were authenticated).
   - Backup codes: eight single-use codes, shown once, stored hashed. Generating new codes
     replaces the unused ones.
   - Support requests are stored with a reference number for staff review (`GET
     /api/admin/recovery-requests`). Nothing is approved automatically.
   - Delivery: the active recovery service uses `MAIL_BACKEND=smtp` and the `MAIL_*` settings.
     Development can use the `console` backend. Production refuses `console` and `memory`, so
     recovery codes are never written to logs there. Recovery by mobile number is not available
     because student accounts are keyed by email.
   - The login page now sends requests through the shared API client. It had been posting without
     a CSRF token and displaying the error object instead of its message.
9. **Checkout details sent and stored** (item 7). The order request carries the customer name,
   phone and special instructions. They are validated on the server (phone as a 10-digit Indian
   mobile, stored as `+91…`; name up to 100 characters; instructions up to 500) and returned with
   the order.
10. **Idempotency keys tied to the request** (item 8). Each order stores a fingerprint of its
    items and customer details. Reusing a key for a different request returns `409
    IDEMPOTENCY_KEY_REUSED` and changes nothing. Orders created before this change are compared by
    items only, because their details were never recorded. Checkout drops the saved key when it
    receives that error.

Migration: `migrations/versions/3f9a1c2b4d5e_add_checkout_details.py` (run `flask db upgrade`).


## High-priority follow-up (27 November 2026)

- The admin orders page now queues the latest search/filter when another request is still pending, avoiding dropped filter changes.
- Added the `pending_payment` order-status filter so every backend order status can be selected.
- Corrected the unpaid-order confirmation page: pending and failed online payments are no longer described as counter/cash payments.
- Corrected canteen settings helper text so it does not claim that reference hours appear in reports or staff screens when those screens do not currently consume those fields.
- Added browser regression tests for these changes and removed old tests that targeted a superseded canteen-settings screen.

## Follow-up pass: reported issues 3 onward (27 November 2026)

- Retained the checkout idempotency key through payment confirmation, including after a refresh between order creation and payment. A server-returned paid order no longer opens another Razorpay payment.
- Made product, menu, cart, and reorder flows report storage failures instead of showing unsaved cart changes as successful.
- Added a confirmation-page warning if the browser cannot clear the saved cart after payment.
- Removed outdated static admin copy claiming that category, menu, settings, reports, or refund APIs are unavailable; pages now show a loading state while their live scripts fetch data.
- Hardened demo-mode session storage against blocked browser storage.
- Added optional `AbortSignal` cancellation to shared API calls and explicit cancellation errors.
- Added frontend jsdom installation and test execution to the GitHub Actions security workflow.
- Added `api-client.test.js` and `storage-errors.test.js` dependency-free regression tests.
- Added `DEPLOYMENT_CHECKLIST.md` and `FIXES_FROM_03_ONWARD.md` for provider configuration, smoke testing, and a precise fix/validation record.
