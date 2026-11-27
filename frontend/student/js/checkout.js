(function () {
  document.getElementById("app-header").innerHTML = trayComponents.header();

  const cart = trayStorage.getCart();
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;"
  })[character]);
  const rupees = (value) => `₹${Number(value).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
  const paidStatuses = new Set(["paid", "captured", "completed", "success"]);
  const summaryRowStyle = "display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #eee";

  // The confirmation pages load the order from the server by id. The order is not passed through
  // browser storage, so nothing on the page can change what the student is shown.
  function confirmationUrl(order, cartClearFailed) {
    const orderId = encodeURIComponent(order.id);
    const paymentStatus = String(order.payment_status || "").toLowerCase();
    const target = paidStatuses.has(paymentStatus)
      ? `./order-placed-animation.html?receipt=${encodeURIComponent(order.order_number || "Pending")}&order_id=${orderId}`
      : `./confirmation.html?order_id=${orderId}`;
    return cartClearFailed ? `${target}&cart_clear_failed=1` : target;
  }

  // Before the order exists, the total is only an estimate from the cart.
  const estimatedTotal = cart.reduce((sum, item) => sum + item.price * item.qty, 0);
  const totalEl = document.getElementById("checkout-total");
  const totalNote = document.getElementById("total-note");
  const summaryEl = document.getElementById("summary");

  function renderEstimate() {
    totalEl.textContent = rupees(estimatedTotal);
    totalNote.textContent = "Estimate. The server confirms the final amount when you place the order.";
    summaryEl.innerHTML = cart.length
      ? cart.map((item) => `<div style="${summaryRowStyle}"><span>${item.qty} × ${escapeHtml(item.name)}</span><strong>${rupees(item.price * item.qty)}</strong></div>`).join("")
      : `<p style="color:var(--muted)">Your cart is empty</p>`;
  }

  // Once the server has created the order, show its lines and total: this is what gets charged.
  function renderServerOrder(order) {
    totalEl.textContent = rupees(order.total_paise / 100);
    totalNote.textContent = "Confirmed by the server. This is the amount you will be charged.";
    summaryEl.innerHTML = (order.items || []).map((line) => `<div style="${summaryRowStyle}"><span>${Number(line.quantity)} × ${escapeHtml(line.item_name)}</span><strong>${rupees(line.line_total_paise / 100)}</strong></div>`).join("");
  }

  renderEstimate();
  document.getElementById("summary-food-images").innerHTML = cart.map((item) => `
<figure class="checkout-food-image">
 <img src="${escapeHtml(item.image || "")}" alt="${escapeHtml(item.name)}" loading="eager" data-hide-on-error>
 <figcaption><strong>${escapeHtml(item.name)}</strong><span>Qty ${Number(item.qty) || 1}</span></figcaption>
</figure>`).join("");

  const form = document.getElementById("checkout-form");
  const submitButton = form.querySelector('button[type="submit"]');
  const idleLabel = submitButton.textContent;
  const nameInput = document.getElementById("name");
  const phoneInput = document.getElementById("phone");
  const instructionsInput = document.getElementById("instructions");
  const phoneError = document.getElementById("phone-error");
  let phoneValidationRequested = false;

  // The server order for this checkout. Once it exists, retrying payment reuses it instead of
  // creating another order.
  let serverOrder = null;
  // Sent as Idempotency-Key. It remains in tab storage until payment is confirmed (or the
  // server tells us the order has expired/cancelled), so a refresh after order creation reuses
  // the same pending order instead of reserving stock a second time.
  let idempotencyKey = null;
  let idempotencyFingerprint = null;
  let submitting = false;

  // The key is kept in tab storage and tied to the cart and the typed details. It remains until
  // payment completes or the server says the pending order can no longer be paid. This also
  // protects the interval between order creation and opening the payment window.
  const IDEMPOTENCY_STORAGE = "trayup-checkout-key";

  function requestFingerprint(details) {
    // Match the backend's canonical request shape: sorted item IDs and an Indian mobile
    // normalized to +91, so harmless line ordering or phone formatting does not create a
    // second pending order after a refresh.
    const phone = String(details.phone || "").replace(/[\s-]/g, "");
    const normalizedPhone = phone.startsWith("+91") ? phone : `+91${phone}`;
    const sortedItems = cart.map((item) => [Number(item.id), Number(item.qty)])
      .sort((a, b) => a[0] - b[0]);
    return JSON.stringify([
      sortedItems,
      details.name.trim(),
      normalizedPhone,
      details.instructions.trim()
    ]);
  }

  function idempotencyKeyFor(details) {
    const fingerprint = requestFingerprint(details);
    if (idempotencyKey && idempotencyFingerprint === fingerprint) return idempotencyKey;
    try {
      const saved = JSON.parse(sessionStorage.getItem(IDEMPOTENCY_STORAGE) || "null");
      if (saved && saved.fingerprint === fingerprint && typeof saved.key === "string") {
        idempotencyKey = saved.key;
        idempotencyFingerprint = fingerprint;
        return saved.key;
      }
    } catch (_) {
      // Some privacy modes block tab storage. The in-memory key still protects retries
      // while this page stays open; cross-refresh protection requires sessionStorage.
    }
    const key = newIdempotencyKey();
    idempotencyKey = key;
    idempotencyFingerprint = fingerprint;
    try {
      sessionStorage.setItem(IDEMPOTENCY_STORAGE, JSON.stringify({ key, fingerprint }));
    } catch (_) {}
    return key;
  }

  function forgetIdempotencyKey() {
    idempotencyKey = null;
    idempotencyFingerprint = null;
    try { sessionStorage.removeItem(IDEMPOTENCY_STORAGE); } catch (_) {}
  }

  function newIdempotencyKey() {
    if (window.crypto?.randomUUID) return window.crypto.randomUUID();
    const bytes = new Uint8Array(16);
    window.crypto.getRandomValues(bytes);
    return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
  }

  function lockCustomerDetails(locked) {
    [nameInput, phoneInput, instructionsInput].forEach((input) => {
      input.readOnly = locked;
      if (locked) input.setAttribute("aria-readonly", "true");
      else input.removeAttribute("aria-readonly");
    });
  }

  function setBusy(busy, busyLabel) {
    submitting = busy;
    submitButton.disabled = busy;
    if (busy) submitButton.textContent = busyLabel;
    else submitButton.textContent = serverOrder ? `Pay ${rupees(serverOrder.total_paise / 100)}` : idleLabel;
  }

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

  function completeOrder(order) {
    // Do not retain a successful order's idempotency key: the next deliberate checkout
    // must be allowed to create a new order. Cart removal is best-effort if storage is blocked.
    const cartClearFailed = !trayStorage.remove("trayup-cart");
    forgetIdempotencyKey();
    window.location.href = confirmationUrl(order, cartClearFailed);
  }

  function handleError(error) {
    if (error.code === "VERIFY_FAILED") {
      // The money may already have been taken. Do not offer another payment attempt;
      // take the student to the server-backed order list to check the recorded status.
      submitButton.disabled = true;
      submitButton.textContent = "Opening Track orders…";
      submitting = false;
      trayNotify(error.message);
      window.location.href = "./tracking.html";
      return;
    }

    if (error.status === 401) trayNotify("Sign in with a student account to place your order. You can keep browsing or choose Log in.");
    else if (error.code === "PAYMENT_CANCELLED") trayNotify("Payment was cancelled. Tap Pay to try again.");
    else if (error.code === "IDEMPOTENCY_KEY_REUSED") {
      // The browser held a key that the server has associated with different order details.
      // Clear it only after the server explicitly rejects it; the next deliberate submit can
      // start a fresh order instead of being trapped in a permanent 409 response.
      serverOrder = null;
      lockCustomerDetails(false);
      forgetIdempotencyKey();
      trayNotify("Your saved checkout no longer matches these details. Tap Place order again to start a new order.");
    }
    else if (["ORDER_EXPIRED", "ORDER_CANCELLED", "ORDER_NOT_PAYABLE_REFUND_REQUIRED"].includes(error.code)) {
      // This order can no longer be paid. Forget it and its key, so the next submit creates a new order
      // instead of being sent back to this one.
      serverOrder = null;
      lockCustomerDetails(false);
      forgetIdempotencyKey();
      trayNotify(error.message);
    } else trayNotify(error.message || "The order could not be placed");

    setBusy(false);
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (submitting) return;

    const name = nameInput.value.trim();
    const phone = phoneInput.value.trim();
    const instructions = document.getElementById("instructions").value.trim();
    const paymentMethod = form.querySelector('input[name="payment_method"]:checked')?.value;
    if (paymentMethod !== "razorpay") { trayNotify("Select online payment to continue."); return; }
    const details = { name, phone, instructions, paymentMethod };

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

    setBusy(true, "Placing order…");
    try {
      if (!serverOrder) {
        idempotencyKey = idempotencyKeyFor(details);
        const response = await trayApi.post("/orders", {
          items: cart.map((item) => ({ menu_item_id: item.id, quantity: item.qty })),
          customer_name: name,
          customer_phone: phone,
          instructions
        }, { headers: { "Idempotency-Key": idempotencyKey } });
        serverOrder = response.data;
        lockCustomerDetails(true);
        renderServerOrder(serverOrder);
      }

      // A retry can return an order that was already paid before the browser lost the
      // payment callback. Never open a second payment for an order the server marks paid.
      if (paidStatuses.has(String(serverOrder.payment_status || "").toLowerCase())) {
        completeOrder(serverOrder);
        return;
      }

      setBusy(true, "Opening payment…");
      const verified = await trayPayment.pay(serverOrder.id, { name, phone }, {
        onFailed: (message) => trayNotify(message)
      });
      completeOrder({ ...serverOrder, ...verified.data });
    } catch (error) {
      handleError(error);
    }
  });
})();
