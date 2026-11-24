(function () {
  document.getElementById("app-header").innerHTML = trayComponents.header();

  const cart = trayStorage.get("trayup-cart", []);
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;"
  })[character]);
  const rupees = (value) => `₹${Number(value).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
  const paidStatuses = new Set(["paid", "captured", "completed", "success"]);
  const paymentLabels = { googlepay: "Google Pay", phonepe: "PhonePe", razorpay: "Razorpay", cash: "Cash on pickup" };
  const summaryRowStyle = "display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #eee";

  function confirmationUrl(order) {
    const data = order?.data || {};
    const paymentStatus = String(data.payment_status || "").toLowerCase();
    return paidStatuses.has(paymentStatus)
      ? `./order-placed-animation.html?receipt=${encodeURIComponent(data.order_number || "Pending")}`
      : "./confirmation.html";
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
 <img src="${escapeHtml(item.image || "")}" alt="${escapeHtml(item.name)}" loading="eager" onerror="this.style.display='none'">
 <figcaption><strong>${escapeHtml(item.name)}</strong><span>Qty ${Number(item.qty) || 1}</span></figcaption>
</figure>`).join("");

  const form = document.getElementById("checkout-form");
  const submitButton = form.querySelector('button[type="submit"]');
  const idleLabel = submitButton.textContent;
  const nameInput = document.getElementById("name");
  const phoneInput = document.getElementById("phone");
  const phoneError = document.getElementById("phone-error");
  let phoneValidationRequested = false;

  // The server order for this checkout. Once it exists, retrying payment reuses it instead of
  // creating another order.
  let serverOrder = null;
  // Sent as Idempotency-Key. Kept across retries until the order is created, so a double tap or
  // a dropped response cannot create two orders.
  let idempotencyKey = null;
  let submitting = false;

  function newIdempotencyKey() {
    if (window.crypto?.randomUUID) return window.crypto.randomUUID();
    const bytes = new Uint8Array(16);
    window.crypto.getRandomValues(bytes);
    return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
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

  function completeOrder(order, details) {
    const saved = {
      success: true,
      data: {
        order_number: order.order_number,
        order_status: order.order_status,
        payment_status: order.payment_status,
        payment_method: details.paymentMethod,
        payment_provider: details.paymentProvider,
        total_paise: order.total_paise,
        items: cart,
        instructions: details.instructions,
        student_name: details.name,
        phone_number: details.phone,
        created_at: order.created_at
      }
    };
    trayStorage.remove("trayup-cart");
    trayStorage.set("trayup-last-order", saved);
    window.location.href = confirmationUrl(saved);
  }

  function handleError(error) {
    if (error.code === "VERIFY_FAILED") {
      // The money may already have been taken. Do not let the student pay this order again.
      submitButton.disabled = true;
      submitButton.textContent = "Check Track orders";
      submitting = false;
      trayNotify(error.message);
      return;
    }

    if (error.status === 401) trayNotify("Please sign in with a student account before placing an order");
    else if (error.code === "PAYMENT_CANCELLED") trayNotify("Payment was cancelled. Tap Pay to try again.");
    else if (error.code === "ORDER_EXPIRED" || error.code === "ORDER_NOT_PAYABLE_REFUND_REQUIRED") {
      // This order can no longer be paid. The next submit creates a new one.
      serverOrder = null;
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
    const paymentMethod = form.querySelector('input[name="payment_method"]:checked').value;
    const details = {
      name,
      phone,
      instructions,
      paymentMethod,
      paymentProvider: paymentLabels[paymentMethod] || "Payment"
    };

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
        idempotencyKey = idempotencyKey || newIdempotencyKey();
        const response = await trayApi.post("/orders", {
          items: cart.map((item) => ({ menu_item_id: item.id, quantity: item.qty }))
        }, { headers: { "Idempotency-Key": idempotencyKey } });
        serverOrder = response.data;
        idempotencyKey = null;
        renderServerOrder(serverOrder);
      }

      if (paymentMethod === "cash") {
        completeOrder(serverOrder, details);
        return;
      }

      setBusy(true, "Opening payment…");
      const verified = await trayPayment.pay(serverOrder.id, { name, phone }, {
        onFailed: (message) => trayNotify(message)
      });
      completeOrder({ ...serverOrder, ...verified.data }, details);
    } catch (error) {
      handleError(error);
    }
  });
})();
