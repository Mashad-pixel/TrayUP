(function () {
  document.getElementById("app-header").innerHTML = trayComponents.header();
  const order = trayStorage.get("trayup-last-order", null);
  const data = order && order.data ? order.data : {};
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;"
  }[character]));
  const paid = ["paid", "captured", "completed", "success"].includes(String(data.payment_status || "").toLowerCase());
  const awaitingConfirmation = String(data.payment_status || "").toLowerCase() === "awaiting_confirmation";
  document.getElementById("receipt-number").textContent = escapeHtml(data.order_number || "Pending");
  document.getElementById("confirmation-name").textContent = escapeHtml(data.student_name || "Not provided");
  document.getElementById("confirmation-phone").textContent = escapeHtml(data.phone_number || "Not provided");
  document.getElementById("confirmation-payment").textContent = escapeHtml(data.payment_provider || (data.payment_method === "cash" ? "Cash on pickup" : "Online"));
  document.getElementById("confirmation-instructions").textContent = escapeHtml(data.instructions || "No special instructions");
  if (!paid) {
    document.getElementById("payment-progress").classList.remove("complete");
    document.getElementById("payment-progress").classList.add("active");
    if (awaitingConfirmation) {
      document.getElementById("confirmation-title").textContent = "Payment awaiting confirmation";
      document.getElementById("confirmation-copy").textContent =
        "Your payment claim was received. Staff will confirm it after hearing the Soundbox.";
      document.querySelector("#payment-progress span:last-child").textContent = "Awaiting confirmation";
      document.querySelector(".order-progress .progress-step").classList.remove("complete");
      document.querySelector(".order-progress .progress-step span:last-child").textContent = "Order placed";
      document.querySelector(".confirmation-icon").textContent = "…";
    } else {
      document.getElementById("confirmation-copy").textContent = "Your order is waiting for payment.";
    }
  }
  const items = Array.isArray(data.items) ? data.items : [];
  document.getElementById("confirmation-food-track").innerHTML = items.length ? items.map((item) => `
    <article class="confirmation-food-card">
      <img src="${escapeHtml(item.image || "")}" alt="${escapeHtml(item.name || "Food")}" loading="eager">
      <div><strong>${escapeHtml(item.name || "Food")}</strong><span>Qty ${Number(item.qty || item.quantity || 1)}</span></div>
    </article>
  `).join("") : '<p style="color:var(--muted)">No food items found.</p>';
})();
