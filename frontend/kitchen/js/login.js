(function () {
  "use strict";

  // Staff sign-in. A failed login only shows an error: there is no demo fallback that opens the dashboard.
  // The backend returns roles in uppercase (KITCHEN, ADMIN, STUDENT), so compare in uppercase.
  const form = document.getElementById("login-form");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const email = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value;
    if (!trayValidation.email(email) || !password) {
      trayNotify("Enter a valid email and password");
      return;
    }

    try {
      const response = await trayAuth.login(email, password);
      const role = String(response?.data?.role || "").toUpperCase();
      if (role === "KITCHEN" || role === "ADMIN") {
        window.location.href = "./dashboard.html";
        return;
      }
      await trayAuth.logout().catch(() => {});
      trayNotify("This account does not have kitchen access.");
    } catch (error) {
      trayNotify(error.status === 429 ? "Too many attempts. Wait a few minutes and try again." : (error.message || "Unable to sign in"));
    }
  });
})();
