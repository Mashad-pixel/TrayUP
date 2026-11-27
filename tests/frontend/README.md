# Frontend behaviour tests

These tests load the real pages and scripts from `frontend/` into jsdom with a scripted API. They check page behaviour, request payloads, server-driven filtering, student checkout safeguards, and staff workflows.

Run locally:

```bash
cd tests/frontend
npm install
npm test
```

The GitHub Actions security workflow installs these test dependencies and runs the suite on pushes and pull requests to `main`. The separate JavaScript syntax check also runs for all frontend and test scripts.

Coverage includes collection verification, the kitchen board, staff sign-in/logout, admin order search and pagination, reporting and refunds, persistent categories and canteen settings, demo-mode isolation, student tracking, checkout idempotency, and failure handling. Live Render, Vercel, SMTP, Firebase, and Razorpay integrations still require deployment-level smoke tests with valid provider credentials.
