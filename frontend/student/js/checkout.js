(function () {
  "use strict";

  document.getElementById("app-header").innerHTML = trayComponents.header("My Orders");

  const SESSION_KEY = "trayup-presence-session";
  const cart = trayStorage.get("trayup-cart", []);
  const total = cart.reduce((sum, item) => sum + item.price * item.qty, 0);
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;"
  }[character]));
  const paidStatuses = new Set(["paid", "captured", "completed", "success"]);

  // One key per checkout page. A double tap or a retry after a dropped connection returns the
  // same order instead of creating a second one.
  const idempotencyKey = (window.crypto && window.crypto.randomUUID)
    ? window.crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;

  function confirmationUrl(order) {
    const data = order?.data || {};
    const paymentStatus = String(data.payment_status || "").toLowerCase();
    return paidStatuses.has(paymentStatus)
      ? `./order-placed-animation.html?receipt=${encodeURIComponent(data.order_number || "Pending")}`
      : "./confirmation.html";
  }

  // ---------- presence session (from verify.html) ----------

  function readPresenceSession() {
    try {
      const saved = JSON.parse(sessionStorage.getItem(SESSION_KEY) || "null");
      if (saved && typeof saved.token === "string" && Number.isFinite(saved.expiresAt) && saved.expiresAt > Date.now()) {
        return saved;
      }
    } catch (_) {}
    sessionStorage.removeItem(SESSION_KEY);
    return null;
  }

  function formatTime(ms) {
    const seconds = Math.max(0, Math.ceil(ms / 1000));
    return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
  }

  const banner = document.getElementById("presence-banner");
  const submitButton = document.querySelector("#checkout-form button[type=\"submit\"]");
  let countdownTimer = null;

  function renderPresenceBanner() {
    clearInterval(countdownTimer);
    const session = readPresenceSession();
    if (!session) {
      banner.dataset.tone = "error";
      banner.innerHTML = `Verify that you're at the canteen before you order. <a href="./verify.html">Verify now</a>`;
      submitButton.disabled = true;
      return;
    }

    banner.dataset.tone = "ok";
    const tick = () => {
      const remaining = session.expiresAt - Date.now();
      if (remaining <= 0) {
        clearInterval(countdownTimer);
        sessionStorage.removeItem(SESSION_KEY);
        renderPresenceBanner();
        return;
      }
      banner.innerHTML = `Verified at the canteen. Place your order within <strong>${formatTime(remaining)}</strong>.`;
    };
    tick();
    countdownTimer = setInterval(tick, 250);
    submitButton.disabled = !cart.length;
  }

  // ---------- cart summary ----------

  document.getElementById("checkout-total").textContent = `₹${total.toLocaleString("en-IN")}`;
  document.getElementById("summary").innerHTML = cart.length
    ? cart.map((item) => `<div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #eee"><span>${item.qty} × ${escapeHtml(item.name)}</span><strong>₹${item.price * item.qty}</strong></div>`).join("")
    : `<p style="color:var(--muted)">Your cart is empty</p>`;
  document.getElementById("summary-food-images").innerHTML = cart.map((item) => `
<figure class="checkout-food-image">
 <img src="${escapeHtml(item.image || "")}" alt="${escapeHtml(item.name)}" loading="eager" onerror="this.style.display='none'">
 <figcaption><strong>${escapeHtml(item.name)}</strong><span>Qty ${Number(item.qty) || 1}</span></figcaption>
</figure>`).join("");

  // ---------- form validation ----------

  const nameInput = document.getElementById("name");
  const phoneInput = document.getElementById("phone");
  const phoneError = document.getElementById("phone-error");
  let phoneValidationRequested = false;

  function validatePhone(showError) {
    const valid = trayValidation.phone(phoneInput.value);
    phoneError.hidden = valid || !showError;
    phoneInput.setAttribute("aria-invalid", String(!valid && showError));
    return valid;
  }

  nameInput.addEventListener("input", () => nameInput.removeAttribute("aria-invalid"));
  phoneInput.addEventListener("blur", () => validatePhone(true));
  phoneInput.addEventListener("input", () => {
    if (phoneValidationRequested || !phoneError.hidden) validatePhone(true);
  });

  // ---------- submit ----------

  function backToLogin() {
    window.location.href = "./login.html?next=checkout.html";
  }

  document.getElementById("checkout-form").addEventListener("submit", async (event) => {
    event.preventDefault();

    const name = nameInput.value.trim();
    const phone = phoneInput.value.trim();
    const instructions = document.getElementById("instructions").value.trim();
    const paymentMethod = document.querySelector('input[name="payment_method"]:checked').value;
    const paymentLabels = { googlepay: "Google Pay", phonepe: "PhonePe", razorpay: "Razorpay", cash: "Cash on pickup" };
    const paymentProvider = paymentLabels[paymentMethod] || "Payment";

    phoneValidationRequested = true;
    const validPhone = validatePhone(true);
    if (!trayValidation.required(name)) {
      nameInput.setAttribute("aria-invalid", "true");
      nameInput.focus();
      trayNotify("Please enter your name");
      return;
    }
    if (!validPhone) {
      phoneInput.focus();
      return;
    }
    if (!cart.length) {
      trayNotify("Your cart is empty");
      return;
    }

    const session = readPresenceSession();
    if (!session) {
      trayNotify("Verify that you're at the canteen first");
      renderPresenceBanner();
      return;
    }

    const originalButtonText = submitButton.textContent;
    submitButton.disabled = true;
    submitButton.textContent = "Placing order…";

    try {
      const payload = { items: cart.map((item) => ({ menu_item_id: item.id, quantity: item.qty })) };
      const response = await trayApi.post("/orders", payload, {
        "X-Presence-Session": session.token,
        "Idempotency-Key": idempotencyKey
      });

      // The backend is the only source of truth for totals, status and the order number.
      window.trayDemoData.recordOrder({
        id: response?.data?.order_number,
        items: cart.map((item) => ({ productId: item.id, quantity: item.qty })),
        total: Number(response?.data?.total_amount || total),
        status: response?.data?.status || "received",
        paymentStatus: response?.data?.payment_status || "pending",
        studentName: name,
        phoneNumber: phone,
        paymentMethod,
        paymentProvider,
        instructions
      });

      sessionStorage.removeItem(SESSION_KEY);
      trayStorage.remove("trayup-cart");
      const savedResponse = {
        ...response,
        data: {
          ...(response?.data || {}),
          items: cart,
          student_name: name,
          phone_number: phone,
          instructions,
          payment_method: paymentMethod,
          payment_provider: paymentProvider,
          payment_status: response?.data?.payment_status || "pending"
        }
      };
      trayStorage.set("trayup-last-order", savedResponse);
      window.location.href = confirmationUrl(savedResponse);
    } catch (error) {
      if (error.status === 401) {
        trayNotify("Please log in to place your order");
        backToLogin();
        return;
      }

      if (error.code && error.code.startsWith("PRESENCE_")) {
        // The verification was used, expired or is missing. Only a fresh verification can help.
        sessionStorage.removeItem(SESSION_KEY);
        trayNotify(error.message || "Verify again to place your order");
        renderPresenceBanner();
      } else if (error.status === undefined) {
        trayNotify("Connection problem. Check My Orders before trying again, so you don't pay twice.");
      } else {
        trayNotify(error.message || "The order could not be placed");
      }

      submitButton.textContent = originalButtonText;
      submitButton.disabled = false;
      if (!readPresenceSession()) submitButton.disabled = true;
    }
  });

  // ---------- startup ----------

  async function init() {
    if (!cart.length) {
      submitButton.disabled = true;
    }
    try {
      const me = await trayApi.get("/auth/me");
      if (String(me?.data?.role || "").toUpperCase() !== "STUDENT") {
        trayNotify("Only student accounts can place orders.");
        submitButton.disabled = true;
        banner.hidden = true;
        return;
      }
    } catch (error) {
      if (error.status === 401) {
        backToLogin();
        return;
      }
    }
    renderPresenceBanner();
  }

  init();
})();
