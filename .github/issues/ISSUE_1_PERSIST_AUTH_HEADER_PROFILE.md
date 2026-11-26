# Issue 1: Header shows "Log in" after student authentication instead of profile icon / profile page

## Problem Description
When a student logs in to TrayUP and navigates across pages (or back to the homepage), the top navbar header still shows the generic "Log in" link with an avatar icon. There is no visual indication that the user is authenticated, and clicking the avatar redirects back to the login page rather than the student's profile/account page.

## Expected Behavior
1. When authenticated (via session cookie or stored user session):
   - The header should show the student's name / avatar / profile icon instead of "Log in".
   - Clicking the profile icon should navigate to a Student Profile page (e.g., `student/profile.html` or an account popup) where students can view their details, order history link, and log out.
2. If unauthenticated, it should continue showing "Log in".

## Technical Context & Files
- `frontend/shared/components.js`: The header template currently hardcodes `<a class="login-link" href="loginpage.html"><span>Log in</span></a>`.
- `frontend/shared/auth.js`: Can provide a helper like `trayAuth.currentUser()` or check `trayStorage.get("trayup-user")` on page load to toggle between the Log In button and Profile link.
- Needs a dedicated profile view or dropdown (e.g. `frontend/student/profile.html`).
