(async function () {
  document.getElementById("app-header").innerHTML = trayComponents.header();

  const $ = (id) => document.getElementById(id);
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;"
  })[character]);
  const paidStatuses = ["paid", "captured", "completed", "success"];
  const PAYMENT_LABELS = { pending: "Online payment pending", failed: "Payment failed", refunded: "Refunded", partially_refunded: "Partially refunded", paid: "Paid" };

  function showUnavailable(title, message) {
    $("confirmation-title").textContent = title;
    $("confirmation-copy").textContent = message;
    $("receipt-number").textContent = "—";
    $("confirmation-food-track").innerHTML = `<p style="color:var(--muted)">${escapeHtml(message)}</p>`;
  }

  // The order comes from the server, looked up by the id in the URL. Nothing is read from browser
  // storage, so the receipt, name, phone and items shown are the ones the server saved.
  const orderId = Number(new URLSearchParams(window.location.search).get("order_id"));
  if (!Number.isInteger(orderId) || orderId < 1) {
    showUnavailable("Order not found", "We couldn’t find this order. Open Track orders to see your orders.");
    return;
  }

  let order;
  try {
    const response = await trayApi.get(`/orders/${orderId}`);
    order = response.data;
  } catch (error) {
    if (error.status === 401) {
      window.location.replace("./login.html");
      return;
    }
    if (error.status === 404) {
      showUnavailable("Order not found", "We couldn’t find this order. Open Track orders to see your orders.");
    } else {
      showUnavailable("Order unavailable", "We couldn’t load your order. Check your connection and refresh the page.");
    }
    return;
  }

  // A paid order goes to the animated confirmation.
  if (paidStatuses.includes(String(order.payment_status || "").toLowerCase())) {
    window.location.replace(`./order-placed-animation.html?receipt=${encodeURIComponent(order.order_number)}&order_id=${orderId}`);
    return;
  }

  const trackLink = document.querySelector('a[href="./tracking.html"]');
  if (trackLink) trackLink.href = `./tracking.html?order_id=${orderId}`;

  $("receipt-number").textContent = order.order_number || "Pending";
  $("confirmation-name").textContent = order.customer_name || "Not provided";
  $("confirmation-phone").textContent = order.customer_phone || "Not provided";
  $("confirmation-payment").textContent = PAYMENT_LABELS[order.payment_status] || "Payment status unavailable";
  $("confirmation-instructions").textContent = order.instructions || "No special instructions";

  $("payment-progress").classList.remove("complete");
  $("payment-progress").classList.add("active");
  if (order.order_status === "cancelled") {
    $("confirmation-title").textContent = "Order cancelled";
    $("confirmation-copy").textContent = "This order was cancelled. Ask the canteen counter if you need help.";
  } else if (order.payment_status === "pending") {
    $("confirmation-title").textContent = "Payment pending";
    $("confirmation-copy").textContent = "Your order has been saved, but online payment has not been confirmed. Check My Orders before attempting another payment.";
  } else if (order.payment_status === "failed") {
    $("confirmation-title").textContent = "Payment failed";
    $("confirmation-copy").textContent = "Payment was not confirmed. Check My Orders for the latest order status.";
  } else {
    $("confirmation-copy").textContent = "Your order status is shown below. Check My Orders for the latest updates.";
  }

  // Dish photos come from the menu catalog. The order itself only stores names and quantities.
  let imageById = new Map();
  try {
    const dishes = await window.trayCatalog.list();
    imageById = new Map(dishes.map((dish) => [dish.id, dish.image]));
  } catch (_) {}

  const items = Array.isArray(order.items) ? order.items : [];
  $("confirmation-food-track").innerHTML = items.length ? items.map((item) => {
    const image = imageById.get(item.menu_item_id);
    return `
      <article class="confirmation-food-card">
        ${image ? `<img src="${escapeHtml(image)}" alt="${escapeHtml(item.item_name || "Food")}" loading="eager">` : ""}
        <div><strong>${escapeHtml(item.item_name || "Food")}</strong><span>Qty ${Number(item.quantity) || 1}</span></div>
      </article>`;
  }).join("") : '<p style="color:var(--muted)">No food items found.</p>';
})();
