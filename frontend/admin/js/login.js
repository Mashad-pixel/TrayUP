(function () {
  const loginForm = document.getElementById("login-form");
  const mfaForm = document.getElementById("mfa-form");
  const setupForm = document.getElementById("mfa-setup-form");
  const mfaCode = document.getElementById("mfa-code");
  const setupCode = document.getElementById("setup-code");
  const secretText = document.getElementById("mfa-secret");
  const setupLink = document.getElementById("mfa-link");
  const submit = loginForm.querySelector('button[type="submit"]');
  // The role returned by the password step. Kept so the setup step can route after enrollment.
  let pendingRole = null;

  function showOnly(form) {
    [loginForm, mfaForm, setupForm].forEach((entry) => { entry.hidden = entry !== form; });
  }

  function goToDashboard(role) {
    if (role === "ADMIN") window.location.href = "./dashboard.html";
    else trayNotify("This account does not have administrator access.");
  }

  async function startSetup() {
    const response = await trayApi.post("/auth/mfa/setup", {});
    const setup = response?.data || {};
    // Values from the server are written as text. The link only accepts otpauth:// URIs.
    secretText.textContent = setup.secret || "";
    if (typeof setup.otpauth_uri === "string" && setup.otpauth_uri.startsWith("otpauth://")) {
      setupLink.href = setup.otpauth_uri;
      setupLink.hidden = false;
    } else {
      setupLink.hidden = true;
    }
    showOnly(setupForm);
    setupCode.focus();
  }

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const email = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value;
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email) || !password) {
      trayNotify("Enter a valid email and password."); return;
    }
    submit.disabled = true;
    try {
      const response = await trayAuth.login(email, password);
      const data = response?.data || {};
      pendingRole = data.role || null;
      if (pendingRole !== "ADMIN") {
        try { await trayAuth.logout(); } catch (_) {}
        trayNotify(pendingRole === "KITCHEN"
          ? "This kitchen account should sign in on the kitchen page."
          : "This account does not have administrator access.");
        return;
      }
      if (data.mfa_required) {
        showOnly(mfaForm);
        mfaCode.focus();
      } else if (data.mfa_setup_required) {
        await startSetup();
      } else {
        goToDashboard(data.role);
      }
    } catch (error) {
      // Failed authentication must never create a local role.
      trayNotify(error.message || "Unable to sign in.");
    } finally { submit.disabled = false; }
  });

  mfaForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = mfaForm.querySelector('button[type="submit"]');
    button.disabled = true;
    try {
      const response = await trayApi.post("/auth/mfa/verify", { code: mfaCode.value.replace(/\s/g, "") });
      goToDashboard(response?.data?.role);
    } catch (error) {
      trayNotify(error.message || "Unable to verify the code.");
    } finally { button.disabled = false; }
  });

  setupForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = setupForm.querySelector('button[type="submit"]');
    button.disabled = true;
    try {
      await trayApi.post("/auth/mfa/confirm", { code: setupCode.value.replace(/\s/g, "") });
      goToDashboard(pendingRole);
    } catch (error) {
      trayNotify(error.message || "Unable to turn on two-factor authentication.");
    } finally { button.disabled = false; }
  });
})();
