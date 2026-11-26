(function () {
  document.getElementById("app-header").innerHTML = trayComponents.header();

  const cart = trayStorage.get("trayup-cart", []);
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;"
  })[character]);
  const rupees = (value) => `₹${Number(value).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
  const paidStatuses = new Set(["paid", "captured", "completed", "success"]);
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
  const paymentPanel = document.getElementById("upi-payment-panel");

  function renderEstimate() {
    totalEl.textContent = rupees(estimatedTotal);
    totalNote.textContent = "Estimate. The server confirms the final amount when you place the order.";
    summaryEl.innerHTML = cart.length
      ? cart.map((item) => `<div style="${summaryRowStyle}"><span>${item.qty} × ${escapeHtml(item.name)}</span><strong>${rupees(item.price * item.qty)}</strong></div>`).join("")
      : `<p style="color:var(--muted)">Your cart is empty</p>`;
  }

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
  const submitButton = document.getElementById("checkout-submit-btn") || form.querySelector('button[type="submit"]');
  const nameInput = document.getElementById("name");
  const phoneInput = document.getElementById("phone");
  const phoneError = document.getElementById("phone-error");
  const claimButton = document.getElementById("submit-payment-claim");
  const utrInput = document.getElementById("utr-number");
  const paymentMessage = document.getElementById("upi-payment-message");
  const openUpiLink = document.getElementById("open-upi");
  const sandboxDevContainer = document.getElementById("sandbox-dev-container");
  const sandboxPayBtn = document.getElementById("sandbox-pay-btn");

  let phoneValidationRequested = false;
  let serverOrder = null;
  let orderDetails = null;
  let idempotencyKey = null;
  let submitting = false;
  let sandboxAvailable = false;

  // Pre-fill student name & phone if available from saved storage or session
  const savedProfile = trayStorage.get("trayup-student-profile", null);
  if (savedProfile) {
    if (savedProfile.name && !nameInput.value) nameInput.value = savedProfile.name;
    if (savedProfile.phone && !phoneInput.value) phoneInput.value = savedProfile.phone;
  }
  trayApi.get("/auth/me").then((res) => {
    if (res?.data) {
      if (res.data.name && !nameInput.value) nameInput.value = res.data.name;
      if (res.data.phone && !phoneInput.value) phoneInput.value = res.data.phone;
      trayStorage.set("trayup-user", res.data);
    }
  }).catch(() => {});

  // Check backend payment capabilities in background
  trayPayment.getMethods().then((res) => {
    sandboxAvailable = Boolean(res?.data?.sandbox?.enabled);
  }).catch(() => {});

  function updateSubmitButton() {
    if (!cart.length) {
      submitButton.disabled = true;
      submitButton.textContent = "Your cart is empty";
      return;
    }
    submitButton.disabled = submitting;
    submitButton.textContent = submitting ? "Preparing payment…" : `Pay ${rupees(estimatedTotal)}`;
  }
  updateSubmitButton();

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
    else updateSubmitButton();
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
        payment_method: details?.paymentMethod || "upi_soundbox",
        payment_provider: details?.paymentProvider || "UPI / Soundbox",
        total_paise: order.total_paise,
        items: cart,
        instructions: details?.instructions || "",
        student_name: details?.name || "",
        phone_number: details?.phone || "",
        created_at: order.created_at
      }
    };
    trayStorage.remove("trayup-cart");
    trayStorage.set("trayup-last-order", saved);
    window.location.href = confirmationUrl(saved);
  }

  function showUpiPayment(data) {
    document.getElementById("upi-order-summary").textContent =
      `Order ${data.order_number || serverOrder.order_number} · ${rupees(data.amount_paise / 100)}`;

    if (openUpiLink) {
      openUpiLink.href = data.upi_uri || "#";
    }

    const qr = document.getElementById("upi-qr");
    if (data.qr_svg_url) {
      qr.src = new URL(data.qr_svg_url, window.location.origin).href;
      qr.hidden = false;
    } else {
      qr.hidden = true;
    }

    if (sandboxDevContainer && sandboxAvailable) {
      sandboxDevContainer.hidden = false;
    }

    paymentMessage.textContent = "After paying, return here and tap “I Have Paid”.";
    paymentPanel.hidden = false;
    submitButton.hidden = true;
    nameInput.disabled = true;
    phoneInput.disabled = true;
    document.getElementById("instructions").disabled = true;

    // On mobile devices, automatically prompt the native OS UPI app chooser (PhonePe, GPay, Paytm, etc.)
    const isMobile = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
    if (isMobile && data.upi_uri) {
      try {
        window.location.href = data.upi_uri;
      } catch (e) {
        console.warn("Direct intent redirect failed, user can tap the link", e);
      }
    }
  }

  function handleError(error) {
    if (error.status === 401) {
      trayNotify("Sign in with a student account to place your order. You can keep browsing or choose Log in.");
    } else if (error.code === "ORDER_EXPIRED" || error.code === "ORDER_NOT_PAYABLE_REFUND_REQUIRED") {
      serverOrder = null;
      orderDetails = null;
      renderEstimate();
      trayNotify(error.message);
    } else {
      trayNotify(error.message || "The order could not be placed");
    }
    setBusy(false);
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (submitting) return;

    const name = nameInput.value.trim();
    const phone = phoneInput.value.trim();
    const instructions = document.getElementById("instructions").value.trim();
    const details = {
      name,
      phone,
      instructions,
      paymentMethod: "upi_soundbox",
      paymentProvider: "UPI / Soundbox"
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

    // Remember name and phone for future orders so user is not asked again
    trayStorage.set("trayup-student-profile", { name, phone });

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
      orderDetails = details;

      setBusy(true, "Opening payment…");
      const response = await trayPayment.initiateUpi(serverOrder.id);
      showUpiPayment(response.data);
      setBusy(false);
    } catch (error) {
      handleError(error);
    }
  });

  claimButton.addEventListener("click", async () => {
    if (!serverOrder || submitting) return;
    const utrNumber = utrInput.value.trim();
    if (utrNumber && !/^[A-Za-z0-9]{12}$/.test(utrNumber)) {
      paymentMessage.textContent = "Enter a 12-character alphanumeric UTR, or leave it blank.";
      utrInput.focus();
      return;
    }

    submitting = true;
    claimButton.disabled = true;
    paymentMessage.textContent = "Submitting your payment claim…";
    try {
      const response = await trayPayment.submitUpiClaim(serverOrder.id, utrNumber);
      completeOrder({ ...serverOrder, ...response.data }, {
        ...orderDetails,
        paymentMethod: "upi_soundbox",
        paymentProvider: "UPI / Soundbox"
      });
    } catch (error) {
      paymentMessage.textContent = error.message || "Could not submit the payment claim.";
      claimButton.disabled = false;
    } finally {
      submitting = false;
    }
  });

  if (sandboxPayBtn) {
    sandboxPayBtn.addEventListener("click", async () => {
      if (!serverOrder || submitting) return;
      submitting = true;
      sandboxPayBtn.disabled = true;
      paymentMessage.textContent = "Simulating instant test payment…";
      try {
        const response = await trayPayment.completeSandbox(serverOrder.id);
        completeOrder({ ...serverOrder, ...response.data }, {
          ...orderDetails,
          paymentMethod: "sandbox",
          paymentProvider: "Test Sandbox"
        });
      } catch (error) {
        paymentMessage.textContent = error.message || "Sandbox payment failed.";
        sandboxPayBtn.disabled = false;
      } finally {
        submitting = false;
      }
    });
  }
})();
