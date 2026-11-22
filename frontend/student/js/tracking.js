(function () {
  document.getElementById("app-header").innerHTML = trayComponents.header("My Orders");
  const target = document.getElementById("tracking");
  const products = window.trayDemoData.products;
  const ordersById = new Map();

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (character) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      "\"": "&quot;",
      "'": "&#39;"
    })[character]);
  }

  function statusClass(status) {
    if (status === "Delivered") return "";
    if (status === "Cancelled") return "danger";
    return "warning";
  }

  function renderDemoOrders(apiOrders = []) {
    const savedOrders = trayStorage.get("trayup-user-orders", []);
    const savedOrdersById = new Map(savedOrders.map((order) => [
      String(order.id || order.order_number),
      order
    ]));
    const seen = new Set();
    const allOrders = [...apiOrders, ...savedOrders, ...window.trayDemoData.orders]
      .filter((order) => {
        const id = order.id || order.order_number;
        if (seen.has(String(id))) return false;
        seen.add(String(id));
        return true;
      })
      .map((order) => ({
        ...(savedOrdersById.get(String(order.id || order.order_number)) || {}),
        ...order
      }));

    ordersById.clear();
    allOrders.forEach((order) => ordersById.set(String(order.id || order.order_number), order));
    target.innerHTML = allOrders.map((order) => {
      const items = (order.items || []).map((entry) => {
        const product = products.find((item) => item.id === Number(entry.productId || entry.menu_item_id || entry.id));
        return {
          ...product,
          name: product?.name || entry.name || entry.menu_item_name || "Food item",
          image: product?.image || entry.image || "",
          description: product?.description || entry.description || "",
          price: product?.price ?? entry.price ?? entry.unit_price ?? 0,
          quantity: Number(entry.quantity || entry.qty || 1)
        };
      });
      const id = order.id || order.order_number || "Order";
      const safeId = escapeHtml(id);
      const status = order.status || order.order_status || "Received";
      const total = Number(order.total ?? order.total_amount ?? order.amount ?? 0);
      const studentName = order.studentName || order.student_name || "Not provided";
      const phoneNumber = order.phoneNumber || order.phone_number || order.phone || "Not provided";
      const instructions = order.instructions || order.description || "None";
      const paymentMethod = String(order.paymentMethod || order.payment_method || "Not selected");
      const paymentStatus = String(order.paymentStatus || order.payment_status || "pending");
      const paymentProvider = String(order.paymentProvider || order.payment_provider || "");
      const paymentMethodLabel = paymentProvider || (paymentMethod.toLowerCase() === "cash" ? "Cash on pickup" :
        paymentMethod.toLowerCase() === "online" ? "Online" : paymentMethod);
      const paymentStatusLabel = paymentStatus === "cash_due" ? "Due in cash" :
        paymentStatus === "demo_pending" || paymentStatus === "online_pending" ? "Pending" :
        paymentStatus === "paid" ? "Paid" : paymentStatus;
      const paymentComplete = paymentStatus === "paid" || ["captured","completed","success"].includes(paymentStatus.toLowerCase());
      const orderComplete = ["Delivered","Collected","Completed"].includes(status);
      const placedDate = order.createdAt || order.created_at;

      return `
        <article class="card" style="margin-bottom:14px;padding:18px" data-order="${safeId}">
          <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start">
            <div>
              <strong class="receipt-order-number">Receipt ${safeId}</strong>
              <p style="color:var(--muted);font-size:13px;margin-top:5px">${items.length} item${items.length === 1 ? "" : "s"} · ₹${total.toLocaleString("en-IN")}</p>
            </div>
            <span class="status ${statusClass(status)}">${escapeHtml(status)}</span>
          </div>
          <div class="order-progress order-progress-compact" aria-label="Order progress">
            <div class="progress-step complete"><span class="progress-circle"></span><span>Confirmed</span></div>
            <div class="progress-step ${paymentComplete ? "complete" : "active"}"><span class="progress-circle"></span><span>Payment</span></div>
            <div class="progress-step ${orderComplete ? "complete" : ""}"><span class="progress-circle"></span><span>Completed</span></div>
          </div>
          <div class="order-customer-details">
            <p><strong>Student name</strong>${escapeHtml(studentName)}</p>
            <p><strong>Phone number</strong>${escapeHtml(phoneNumber)}</p>
            <p><strong>Payment</strong>${escapeHtml(paymentMethodLabel)} · ${escapeHtml(paymentStatusLabel)}</p>
            <p class="order-description"><strong>Description / special instructions</strong>${escapeHtml(instructions)}</p>
          </div>
          <div class="order-food-carousel">
            <div class="order-food-track" tabindex="0" aria-label="Ordered foods; swipe horizontally to view each item">
              ${items.map((item) => `
                <div class="order-food-slide">
                  <div>
                    <strong>${escapeHtml(item.name)}</strong>
                    <p>Qty ${item.quantity} · ₹${Number(item.price).toLocaleString("en-IN")} each</p>
                    <p>${escapeHtml(item.description)}</p>
                    <strong>Item total: ₹${(Number(item.price) * item.quantity).toLocaleString("en-IN")}</strong>
                  </div>
                  <img src="${escapeHtml(item.image)}" alt="${escapeHtml(item.name)}" onerror="this.style.display='none'">
                </div>
              `).join("")}
            </div>
            ${items.length > 1 ? `
              <div class="order-carousel-controls">
                <button type="button" data-carousel-prev aria-label="Previous food">‹</button>
                <span aria-live="polite"><span data-carousel-current>1</span> / ${items.length}</span>
                <button type="button" data-carousel-next aria-label="Next food">›</button>
              </div>
            ` : ""}
          </div>
          <div class="order-details" hidden style="border-top:1px solid #eee;padding-top:12px;color:var(--muted);font-size:13px">
            ${placedDate ? `Placed ${escapeHtml(new Date(placedDate).toLocaleString())} · ` : ""}Payment status ${escapeHtml(paymentStatusLabel)} · Order total ₹${total.toLocaleString("en-IN")}
          </div>
          <div style="display:flex;justify-content:flex-end;gap:8px;margin-top:12px">
            <button class="btn btn-secondary" type="button" data-view="${safeId}">View Details</button>
            <button class="btn btn-primary" type="button" data-reorder="${safeId}" ${status === "Cancelled" ? "disabled" : ""}>Reorder</button>
          </div>
        </article>`;
    }).join("");
    target.querySelectorAll(".order-food-track").forEach((track) => {
      track.addEventListener("scroll", () => {
        const current = track.closest(".order-food-carousel").querySelector("[data-carousel-current]");
        if (current) current.textContent = String(Math.round(track.scrollLeft / track.clientWidth) + 1);
      }, { passive: true });
    });
  }

  async function load() {
    if (window.TRAYUP_CONFIG?.demoMode !== false) {
      renderDemoOrders();
      return;
    }
    try {
      const response = await trayApi.get("/orders");
      const orders = response?.data?.orders || [];
      renderDemoOrders(orders);
      return;
    } catch (_) {}
    renderDemoOrders();
  }

  target.addEventListener("click", (event) => {
    const previous = event.target.closest("[data-carousel-prev]");
    const next = event.target.closest("[data-carousel-next]");
    if (previous || next) {
      const track = (previous || next).closest(".order-food-carousel").querySelector(".order-food-track");
      track.scrollLeft += (next ? 1 : -1) * track.clientWidth;
      const current = track.closest(".order-food-carousel").querySelector("[data-carousel-current]");
      if (current) current.textContent = String(Math.round(track.scrollLeft / track.clientWidth) + 1);
      return;
    }

    const view = event.target.closest("[data-view]");
    const reorder = event.target.closest("[data-reorder]");
    if (view) {
      const details = view.closest("[data-order]").querySelector(".order-details");
      details.hidden = !details.hidden;
      view.textContent = details.hidden ? "View Details" : "Hide Details";
    }
    if (reorder) {
      const savedOrders = trayStorage.get("trayup-user-orders", []);
      const order = ordersById.get(reorder.dataset.reorder) ||
        [...savedOrders, ...window.trayDemoData.orders].find((entry) => String(entry.id) === reorder.dataset.reorder);
      if (!order) return;
      const cart = trayStorage.get("trayup-cart", []);
      (order.items || []).forEach((entry) => {
        const product = products.find((item) =>
          item.id === Number(entry.productId || entry.menu_item_id || entry.id) ||
          item.name === entry.name ||
          item.name === entry.menu_item_name
        );
        if (!product) return;
        const quantity = Number(entry.quantity || entry.qty || 1);
        const existing = cart.find((item) => item.id === product.id);
        if (existing) existing.qty += quantity;
        else cart.push({ ...product, vegetarian: product.isVeg, available: product.isAvailable, qty: quantity });
      });
      trayStorage.set("trayup-cart", cart);
      trayNotify("Items added to your cart");
      window.location.href = "../student/cart.html";
    }
  });

  load();
})();
