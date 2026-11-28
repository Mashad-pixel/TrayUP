(function () {
  document.getElementById("app-header").innerHTML = trayComponents.header();

  const cart = trayStorage.get("trayup-cart", []);
  if (!cart.length) {
    document.getElementById("checkout-empty-state").hidden = false;
    document.getElementById("checkout-layout").hidden = true;
    return;
  }
  const loginUrl = "./login.html?next=checkout.html";
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;"
  })[character]);
  const rupees = (value) => `₹${Number(value).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
  // Before the order exists, the total is only an estimate from the cart.
  const estimatedTotal = cart.reduce((sum, item) => sum + item.price * item.qty, 0);
  const totalEl = document.getElementById("checkout-total");
  const totalNote = document.getElementById("total-note");
  const summaryEl = document.getElementById("summary");
  const paymentPanel = document.getElementById("upi-payment-panel");
  const checkoutSteps = Array.from(document.querySelectorAll("[data-checkout-step]"));

  function setCheckoutStep(currentStep) {
    checkoutSteps.forEach((step) => {
      const stepNumber = Number(step.dataset.checkoutStep);
      step.classList.toggle("is-current", stepNumber === currentStep);
      step.classList.toggle("is-complete", stepNumber < currentStep);
      if (stepNumber === currentStep) step.setAttribute("aria-current", "step");
      else step.removeAttribute("aria-current");
    });
  }

  function renderEstimate() {
    totalEl.textContent = rupees(estimatedTotal);
    totalNote.textContent = "Estimate. The server confirms the final amount when you place the order.";
    summaryEl.innerHTML = cart.length
      ? cart.map((item) => `<div class="checkout-summary-row"><span>${item.qty} × ${escapeHtml(item.name)}</span><strong>${rupees(item.price * item.qty)}</strong></div>`).join("")
      : `<p style="color:var(--muted)">Your cart is empty</p>`;
  }

  // Once the server has created the order, show its lines and total: this is what gets charged.
  function renderServerOrder(order) {
    totalEl.textContent = rupees(order.total_paise / 100);
    totalNote.textContent = "Confirmed by the server. This is the amount you will be charged.";
    summaryEl.innerHTML = (order.items || []).map((line) => `<div class="checkout-summary-row"><span>${Number(line.quantity)} × ${escapeHtml(line.item_name)}</span><strong>${rupees(line.line_total_paise / 100)}</strong></div>`).join("");
  }

  renderEstimate();
  const summaryFoodImages = document.getElementById("summary-food-images");
  summaryFoodImages.addEventListener("error", (event) => {
    if (event.target instanceof HTMLImageElement) event.target.style.display = "none";
  }, true);
  summaryFoodImages.innerHTML = cart.map((item) => `
<figure class="checkout-food-image">
 <img src="${escapeHtml(item.image || "")}" alt="${escapeHtml(item.name)}" loading="eager">
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
  let phoneValidationRequested = false;

  // The server order for this checkout. Once it exists, retrying payment reuses it instead of
  // creating another order.
  let serverOrder = null;
  let orderDetails = null;
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

  function updateSubmitButton() {
    submitButton.disabled = submitting || !cart.length;
    const total = serverOrder ? serverOrder.total_paise / 100 : estimatedTotal;
    submitButton.textContent = submitting ? "Preparing payment…" : `Pay ${rupees(total)}`;
  }

  function setBusy(busy, busyLabel) {
    submitting = busy;
    submitButton.disabled = busy;
    if (busy) submitButton.textContent = busyLabel;
    else updateSubmitButton();
  }

  updateSubmitButton();
  setCheckoutStep(1);

  function validatePhone(showError) {
    const valid = trayValidation.phone(phoneInput.value);
    phoneError.hidden = valid || !showError;
    phoneInput.setAttribute("aria-invalid", String(!valid && showError));
    return valid;
  }

  async function prefillStudentDetails() {
    try {
      const response = await trayAuth.currentUser();
      const student = response?.data;
      if (String(student?.role || "").toUpperCase() !== "STUDENT") return;
      nameInput.value = student.name || "";
      phoneInput.value = student.mobile_number || "";
      validatePhone(false);
    } catch (error) {
      if (error.status !== 401) {
        trayNotify(error.message || "Could not load your account details.");
      }
    }
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
    window.location.href = "./confirmation.html";
  }

  function showUpiPayment(data) {
    setCheckoutStep(2);
    const amountPaise = data.amount_paise || serverOrder.total_paise;
    document.getElementById("upi-order-summary").textContent =
      `Order ${data.order_number || serverOrder.order_number} · ${rupees(amountPaise / 100)}`;

    if (openUpiLink) {
      openUpiLink.href = data.upi_uri || "#";
    }

    const qr = document.getElementById("upi-qr");
    const qrPath = data.qr_svg_url || `/api/payments/${serverOrder.id}/upi-qr.svg`;
    qr.src = new URL(qrPath, window.location.origin).href;
    qr.hidden = false;

    paymentMessage.textContent = "After paying, enter your 12-digit UTR number and tap “I Have Paid”.";
    paymentPanel.hidden = false;
    submitButton.hidden = true;
    nameInput.disabled = true;
    phoneInput.disabled = true;
    document.getElementById("instructions").disabled = true;

    // On mobile phones, automatically trigger the native OS UPI app chooser
    const isMobile = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
    if (isMobile && data.upi_uri) {
      try {
        window.location.href = data.upi_uri;
      } catch (_) {}
    }
  }

  function handleError(error) {
    if (error.status === 401) {
      window.location.href = loginUrl;
      return;
    } else if (error.code === "ORDER_EXPIRED" || error.code === "ORDER_NOT_PAYABLE_REFUND_REQUIRED") {
      serverOrder = null;
      orderDetails = null;
      renderEstimate();
      trayNotify(error.message);
    } else trayNotify(error.message || "The order could not be placed");

    setBusy(false);
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (submitting) return;

    setBusy(true, "Checking sign in…");
    try {
      const response = await trayAuth.currentUser();
      if (String(response?.data?.role || "").toUpperCase() !== "STUDENT") {
        window.location.href = loginUrl;
        return;
      }
    } catch (error) {
      if (error.status === 401) {
        window.location.href = loginUrl;
        return;
      }
      setBusy(false);
      trayNotify(error.message || "Could not verify your sign-in. Please try again.");
      return;
    }
    setBusy(false);

    const name = nameInput.value.trim();
    const phone = phoneInput.value.trim();
    const instructions = document.getElementById("instructions").value.trim();
    const details = {
      name,
      phone,
      instructions,
      paymentMethod: "upi",
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
      setCheckoutStep(2);

      setBusy(true, "Preparing UPI payment…");
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
    if (!/^\d{12}$/.test(utrNumber)) {
      paymentMessage.textContent = "Enter the 12-digit UTR number from your UPI payment receipt.";
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
        paymentMethod: "upi",
        paymentProvider: "UPI / Soundbox"
      });
    } catch (error) {
      paymentMessage.textContent = error.message || "Could not submit the payment claim.";
      claimButton.disabled = false;
    } finally {
      submitting = false;
    }
  });

  prefillStudentDetails();
})();
