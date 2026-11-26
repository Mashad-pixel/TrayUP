# Issue 2: Pre-fill student name and phone number on checkout from saved profile/session

## Problem Description
Every time a student goes through checkout, they are forced to manually type their Name and Phone number again, even if they have already logged in or placed orders in the past.

## Expected Behavior
1. Checkout should automatically pre-fill the **Name** and **Phone Number** fields from the authenticated user's session (`/api/auth/me`) or from locally persisted student profile storage (`trayup-student-profile`).
2. If the user edits the name or phone during checkout, the new values should be remembered for subsequent checkouts.
3. Students should only need to enter their details once.

## Technical Context & Files
- `frontend/student/js/checkout.js`: Pre-fill `nameInput` and `phoneInput` upon loading, and persist to `trayStorage` upon submission.
- `frontend/student/checkout.html`: Ensure `autocomplete="name"` and `autocomplete="tel"` attributes are maintained.
