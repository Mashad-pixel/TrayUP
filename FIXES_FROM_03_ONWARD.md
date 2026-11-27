# TrayUP fixes: issues 3 onward

This file records the fixes included in this package for the reported issues numbered 3 onward. The database migration graph and application blueprint registration (items 1 and 2) were not modified in this pass; this package inherits the previous package's state for those areas.

## Kitchen and order lifecycle

- Removed the invalid manual `collected` status action from the kitchen board. Staff must scan/enter the collection token, verify it with the backend, and confirm the handover through the collection endpoint.
- Kept the live kitchen queue limited to `received`, `preparing`, and `ready`, matching the backend queue. Collected orders leave the active queue rather than appearing in an unsupported fourth column.
- Replaced fabricated rider/delivery milestones with an order confirmation page that fetches the actual order, payment, and item details from the server. The copy correctly describes canteen-counter collection.
- Kept payment state authoritative on the server. An order returned by an idempotent retry with `paid` status bypasses a second Razorpay payment attempt.

## Admin workflows

- Admin order search, payment/order filters, and pagination are sent to the backend. A search/filter request made while another request is running is queued instead of discarded.
- Added the `pending_payment` order status to the filter and used backend payment-status values (`pending`, `paid`, `failed`, `refunded`, `partially_refunded`).
- Categories use the persistent admin API for listing, creation, renaming, ordering, and deletion. Stale HTML text claiming the API does not exist was replaced with loading text.
- Canteen name, hours, and order-acceptance status are loaded and saved through server endpoints. Opening hours are documented as reference information; the separate ordering switch controls whether new orders are accepted.
- Reports and refunds use server-returned data. Their initial HTML placeholders no longer claim that the endpoints are absent.

## Student, payments, and browser behavior

- Student sign-in validates email addresses to match the backend's email-only login. The separate manual support-recovery form can still accept an email or mobile identifier as its API supports that workflow; it does not automatically reset an account.
- Admin and kitchen logout handlers report failures and do not redirect as though logout succeeded.
- Local/session storage reads and writes are guarded. Cart add/remove/reorder flows now check whether storage actually succeeded and show an error instead of pretending the cart changed. Demo-mode storage operations are guarded as well.
- API and CSRF requests use abort timeouts and convert timeout failures into a readable error. The shared API methods also accept an optional `AbortSignal` and report caller cancellations as `REQUEST_ABORTED`.
- Checkout sends the student's name, phone number, and instructions. The backend validates and stores these details with the order.
- The backend binds each idempotency key to a fingerprint of the requested items and customer details, rejecting a reused key with a different request.
- The checkout key is now retained in session storage until payment is confirmed or the order is no longer payable. This protects the interval after order creation and before/during payment, including a page refresh. A retry that returns an already-paid order does not create another payment.
- The checkout offers one Online payment choice. UPI apps, cards, and netbanking are selected inside Razorpay Checkout where the provider supports them; unsupported standalone cash/Google Pay/PhonePe selectors are not presented.
- If the browser cannot clear its saved cart after payment, the confirmation page warns the student to review the cart before another order.

## Deployment and test setup

- Firebase remains optional and disabled by default in the Render manifest. SMTP and Razorpay credentials are supplied as Render environment variables, not committed into the repository.
- `DEPLOYMENT_CHECKLIST.md` lists the external Render/Vercel settings and production smoke tests. Verify that the Vercel rewrite target matches the actual Render public URL before deployment.
- GitHub Actions now installs the frontend behavior-test dependency and runs the jsdom suite in addition to Python tests, Python security checks, and JavaScript syntax checks.
- Frontend tests include regression coverage for idempotency-key retention across refresh and for not opening a second payment when the server reports an already-paid order.

## Validation performed for this update

- `node --check` across all frontend and frontend-test JavaScript files: passed.
- `python -m compileall -q app tests`: passed (syntax/bytecode compilation only; it does not execute Flask tests).
- Dependency-free Node tests (`api-client.test.js`, `storage-errors.test.js`, and `catalog.test.js`): 8 passed.
- Complete jsdom browser suite: included and wired into GitHub Actions, but not executed in this workspace because `jsdom` could not be installed here.
- Flask integration suite: not executed in this workspace because Flask dependencies are not installed here.
- Live Render, Vercel, PostgreSQL, SMTP, Firebase, and Razorpay flows: require the user's deployed services and credentials and were not tested from this environment.

These changes address the listed source-code issues, but they are not a claim that all possible defects are eliminated or that external services have been tested. Back up the production database before any deployment migration.
