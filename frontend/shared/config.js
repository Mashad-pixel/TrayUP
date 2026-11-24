// Frontend runtime settings.
//
// demoMode must stay false. In demo mode, checkout used to create a fake order in the browser
// whenever the backend returned 401, 404 or 500. That bypassed live QR + GPS verification.
// The demo fallback has been removed from checkout. The backend enforces verification whatever
// this flag says, so changing it cannot unlock ordering.
window.TRAYUP_CONFIG = Object.freeze({
  apiBaseUrl: "/api",
  demoMode: false,
  razorpayKeyId: "",
  appName: "trayUP"
});
