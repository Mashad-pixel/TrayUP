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
    const normalized = String(status).toLowerCase();
    if (normalized === "collected" || normalized === "completed" || normalized === "delivered") return "";
    if (normalized === "cancelled") return "danger";
    return "warning";
  }

  function renderOrderProgress(status) {
    const steps = ["received", "preparing", "ready", "collected"];
    const currentIndex = steps.indexOf(status);
    if (currentIndex < 0) return "";

    const labels = ["Received", "Preparing", "Ready for pickup", "Collected"];
    return `
      <div class="order-progress order-progress-compact" aria-label="Order progress">
        ${labels.map((label, index) => {
          const complete = index < currentIndex || currentIndex === steps.length - 1;
          const active = index === currentIndex && !complete;
          const state = complete ? "complete" : active ? "active" : "";
          return `<div class="progress-step ${state}" ${active ? 'aria-current="step"' : ""}><span class="progress-circle"></span><span>${label}</span></div>`;
        }).join("")}
      </div>`;
  }

  function renderOrders(allOrders) {
    ordersById.clear();
    allOrders.forEach((order) => {
      if (order.id != null) ordersById.set(String(order.id), order);
      if (order.order_number) ordersById.set(String(order.order_number), order);
    });
    target.innerHTML = allOrders.map((order) => {
      const items = (order.items || []).map((entry) => {
        const entryName = entry.item_name || entry.name || entry.menu_item_name || "";
        const product = entryName
          ? products.find((item) => item.name.toLowerCase() === String(entryName).toLowerCase())
          : products.find((item) => item.id === Number(entry.productId || entry.menu_item_id || entry.id));
        const quantity = Number(entry.quantity || entry.qty || 1);
        const price = entry.unit_price_paise != null ? Number(entry.unit_price_paise) / 100 :
          Number(entry.price ?? entry.unit_price ?? product?.price ?? 0);
        return {
          ...product,
          name: entryName || product?.name || "Food item",
          image: product?.image || entry.image || "",
          description: product?.description || entry.description || "",
          price,
          lineTotal: entry.line_total_paise != null ? Number(entry.line_total_paise) / 100 : price * quantity,
          quantity,
          productId: product?.id
        };
      });
      const orderKey = String(order.id || order.order_number || "Order");
      const orderNumber = order.order_number || order.id || "Order";
      const safeKey = escapeHtml(orderKey);
      const safeNumber = escapeHtml(orderNumber);
      const statusKey = String(order.order_status || order.status || "received").toLowerCase().replace(/ /g, "_");
      const status = statusKey
        .replace(/_/g, " ")
        .replace(/\b\w/g, (letter) => letter.toUpperCase());
      const total = order.total_paise != null ? Number(order.total_paise) / 100 :
        Number(order.total ?? order.total_amount ?? order.amount ?? 0);
      const studentName = order.studentName || order.student_name || "";
      const phoneNumber = order.phoneNumber || order.phone_number || order.phone || "";
      const instructions = order.instructions || order.description || "";
      const paymentMethod = String(order.paymentMethod || order.payment_method || "Not selected");
      const paymentStatus = String(order.paymentStatus || order.payment_status || "pending").toLowerCase();
      const paymentProvider = String(order.paymentProvider || order.payment_provider || "");
      const paymentMethodLabels = {
        cash: "Cash on pickup",
        online: "Online",
        upi: "UPI",
        upi_soundbox: "UPI / Soundbox",
        sandbox: "Test Sandbox"
      };
      const paymentMethodLabel = paymentProvider || paymentMethodLabels[paymentMethod.toLowerCase()] || paymentMethod;
      const paymentStatusLabel = paymentStatus === "cash_due" ? "Due in cash" :
        paymentStatus === "demo_pending" || paymentStatus === "online_pending" ? "Pending" :
        paymentStatus === "paid" ? "Paid" :
        paymentStatus.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
      const normalizedStatus = statusKey.replace(/_/g, " ");
      const orderPendingPayment = normalizedStatus === "pending payment";
      const orderCancelled = normalizedStatus === "cancelled";
      const placedDate = order.createdAt || order.created_at;
      const canReorder = !orderCancelled &&
        items.length > 0 && items.every((item) => item.productId != null);

      return `
        <article class="order-card" data-order="${safeKey}">
          <div class="order-card-header">
            <div class="order-card-heading">
              <strong class="receipt-order-number">Receipt ${safeNumber}</strong>
              <p class="order-card-summary">${items.length} item${items.length === 1 ? "" : "s"} · ₹${total.toLocaleString("en-IN")}</p>
            </div>
            <span class="status order-status ${statusClass(status)}">${escapeHtml(status)}</span>
          </div>
          ${orderCancelled || orderPendingPayment ? "" : renderOrderProgress(statusKey)}
          <div class="order-meta">
            ${placedDate ? `<span><strong>Placed</strong> ${escapeHtml(new Date(placedDate).toLocaleString())}</span>` : ""}
            <span><strong>Payment</strong> ${escapeHtml(paymentMethodLabel)} · ${escapeHtml(paymentStatusLabel)}</span>
            ${studentName ? `<span><strong>Name</strong> ${escapeHtml(studentName)}</span>` : ""}
            ${phoneNumber ? `<span><strong>Phone</strong> ${escapeHtml(phoneNumber)}</span>` : ""}
            ${instructions ? `<span><strong>Instructions</strong> ${escapeHtml(instructions)}</span>` : ""}
          </div>
          <div class="order-food-carousel">
            <div class="order-food-track" tabindex="0" aria-label="Ordered foods; swipe horizontally to view each item">
              ${items.map((item) => `
                <div class="order-food-slide">
                  <div>
                    <strong>${escapeHtml(item.name)}</strong>
                    <p>Qty ${item.quantity} · ₹${Number(item.price).toLocaleString("en-IN")} each</p>
                    ${item.description ? `<p>${escapeHtml(item.description)}</p>` : ""}
                    <strong>Item total: ₹${Number(item.lineTotal).toLocaleString("en-IN")}</strong>
                  </div>
                  ${item.image ? `<img class="order-food-image" src="${escapeHtml(item.image)}" alt="${escapeHtml(item.name)}">` : ""}
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
          <div class="order-details" hidden>
            ${placedDate ? `Placed ${escapeHtml(new Date(placedDate).toLocaleString())} · ` : ""}Payment status ${escapeHtml(paymentStatusLabel)} · Order total ₹${total.toLocaleString("en-IN")}
          </div>
          <div class="order-card-actions">
            <button class="btn btn-secondary" type="button" data-view="${safeKey}" aria-expanded="false">View Details</button>
            <button class="btn btn-primary" type="button" data-reorder="${safeKey}" ${canReorder ? "" : "disabled"}>Reorder</button>
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
    target.innerHTML = '<div class="empty-state" role="status">Loading your orders…</div>';
    try {
      const response = await trayApi.get("/orders");
      const orders = response?.data?.orders;
      if (!Array.isArray(orders)) throw new Error("The orders response was invalid.");
      if (!orders.length) {
        target.innerHTML = `
          <div class="empty-state">
            <h2>No orders yet</h2>
            <p>Your placed orders will appear here.</p>
            <a class="btn btn-primary" href="../index.html">Browse the menu</a>
          </div>`;
        return;
      }
      renderOrders(orders);
    } catch (error) {
      if (error.status === 401) {
        target.innerHTML = `
          <div class="empty-state" role="status">
            <h2>Sign in to view your orders</h2>
            <p>Your order history is linked to your student account.</p>
            <a class="btn btn-primary" href="./login.html?next=tracking.html">Sign in</a>
          </div>`;
        return;
      }
      target.innerHTML = `
        <div class="empty-state" role="alert">
          <h2>Orders couldn’t load</h2>
          <p>Please check your connection and try again.</p>
          <button class="btn btn-secondary" type="button" data-retry-orders>Try again</button>
        </div>`;
    }
  }

  target.addEventListener("click", (event) => {
    if (event.target.closest("[data-retry-orders]")) {
      load();
      return;
    }
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
      view.setAttribute("aria-expanded", String(!details.hidden));
      view.textContent = details.hidden ? "View Details" : "Hide Details";
    }
    if (reorder) {
      const order = ordersById.get(reorder.dataset.reorder);
      if (!order) return;
      const cart = trayStorage.get("trayup-cart", []);
      (order.items || []).forEach((entry) => {
        const entryName = entry.item_name || entry.name || entry.menu_item_name || "";
        const product = entryName
          ? products.find((item) => item.name.toLowerCase() === String(entryName).toLowerCase())
          : products.find((item) => item.id === Number(entry.productId || entry.menu_item_id || entry.id));
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
  document.addEventListener("error", (event) => {
    const img = event.target;
    if (img instanceof HTMLImageElement && img.classList.contains("order-food-image")) {
      img.remove();
    }
  }, true);
})();
