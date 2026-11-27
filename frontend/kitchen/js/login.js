(function () {
  const form = document.getElementById("login-form");
  const demoEntry = document.getElementById("demo-entry");
  const submit = form.querySelector('button[type="submit"]');
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const email = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value;
    if (!trayValidation.email(email) || !password) {
      trayNotify("Enter a valid email and password."); return;
    }
    submit.disabled = true;
    try {
      const response = await trayAuth.login(email, password);
      const role = response?.data?.role;
      if (role === "KITCHEN") window.location.href = "./dashboard.html";
      else if (role === "ADMIN") window.location.href = "../admin/dashboard.html";
      else {
        try { await trayAuth.logout(); } catch (_) {}
        trayNotify("This account does not have kitchen access.");
      }
    } catch (error) {
      // Failed authentication must never create a local demo role.
      trayNotify(typeof error.status === "number" ? error.message : "Could not reach the server. Check your connection and try again.");
    } finally { submit.disabled = false; }
  });

  if (demoEntry) demoEntry.addEventListener("click", () => {
    window.trayMode.enterDemo();
    window.location.href = "./dashboard.html";
  });

})();
