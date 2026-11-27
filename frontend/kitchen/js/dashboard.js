(function () {
  const demoMode = new URLSearchParams(window.location.search).get("demo") === "1";
  const statuses = ["received","preparing","ready","collected"];
  const pendingRoot = document.getElementById("pending-confirmations");
  const pendingCount = document.getElementById("pending-confirmation-count");
  const summaryRoot = document.getElementById("summary");
  const boardRoot = document.getElementById("kitchen-board");
  const boardError = document.getElementById("board-error");
  const boardErrorMessage = document.getElementById("board-error-message");
  const boardSignIn = document.getElementById("board-signin");
  let pendingLoading = false;
  const demoQueue = {
    received: [
      {id:101,order_number:"TUP-4821",created_at:"10:24 AM",items:[{name:"Masala Dosa",quantity:2},{name:"Cold Coffee",quantity:1}]},
      {id:102,order_number:"TUP-4825",created_at:"10:31 AM",items:[{name:"Grilled Chicken Bowl",quantity:1}]}
    ],
    preparing:[{id:103,order_number:"TUP-4818",created_at:"10:11 AM",items:[{name:"Paneer Butter Masala",quantity:2}]}],
    ready:[{id:104,order_number:"TUP-4809",created_at:"9:58 AM",items:[{name:"Cheese Chilli Sandwich",quantity:2},{name:"Mango Shake",quantity:2}]}],
    collected:[{id:105,order_number:"TUP-4802",created_at:"9:40 AM",items:[{name:"Masala Dosa",quantity:1}] }]
  };
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  function updateTime() {
    document.getElementById("live-time").textContent = new Date().toLocaleString("en-IN", {
      weekday:"short",day:"numeric",month:"short",hour:"2-digit",minute:"2-digit"
    });
  }
  updateTime();
  const clock = setInterval(updateTime, 30000);
  window.addEventListener("pagehide", () => clearInterval(clock));

  function showError(detail, requiresSignIn) {
    summaryRoot.hidden = true;
    boardRoot.hidden = true;
    boardErrorMessage.textContent = detail;
    boardSignIn.hidden = !requiresSignIn;
    boardError.hidden = false;
  }
  function render(queue, readOnly) {
    summaryRoot.hidden = false;
    boardRoot.hidden = false;
    boardError.hidden = true;
    const counts = statuses.map(s => Array.isArray(queue[s]) ? queue[s].length : 0);
    document.getElementById("summary").innerHTML =
      (readOnly ? '<div class="metric"><span>Mode</span><strong>Demo · read only</strong></div>' : "") +
      [["New",counts[0]],["Preparing",counts[1]],["Ready",counts[2]],["Collected",counts[3]]]
        .map(([label,value]) => '<div class="metric"><span>' + label + '</span><strong>' + value + '</strong></div>').join("");
    statuses.forEach(status => {
      const col = document.querySelector('[data-status="' + status + '"]');
      const heading = col.querySelector("h2").outerHTML;
      const orders = Array.isArray(queue[status]) ? queue[status] : [];
      const cards = orders.map(order => {
        const id = Number(order.id);
        const safeId = Number.isInteger(id) && id > 0 ? String(id) : "";
        const items = (order.items || []).map(item =>
          "<li><span>" + Math.max(1,Number(item.quantity)||1) + " × " +
          esc(item.item_name || item.name || item.menu_item_name || "Item") + "</span></li>"
        ).join("");
        const action = readOnly ? "" :
          (status==="received" ? '<button class="btn btn-primary" data-next="preparing">Start preparing</button>' : "") +
          (status==="preparing" ? '<button class="btn btn-primary" data-next="ready">Mark ready</button>' : "") +
          (status==="ready" ? '<button class="btn btn-secondary" data-next="collected">Confirm collection</button>' : "");
        return '<article class="order-ticket" data-order="' + safeId + '"><header><span>' +
          esc(order.order_number || "Order") + "</span><span>" + esc(order.created_at || "") +
          "</span></header><ul>" + items + "</ul>" + action + "</article>";
      }).join("");
      col.innerHTML = heading + (cards || '<div class="empty-state" style="background:transparent">No orders</div>');
    });
  }
  function renderPendingConfirmations(orders) {
    pendingCount.textContent = `${orders.length} pending`;
    if (!orders.length) {
      pendingRoot.innerHTML = '<p class="empty-state">No payments are waiting for confirmation.</p>';
      return;
    }

    pendingRoot.innerHTML = orders.map(order => {
      const id = Number(order.id);
      const safeId = Number.isInteger(id) && id > 0 ? String(id) : "";
      const amount = (Number(order.total_paise) || 0) / 100;
      const items = (order.items || []).map(item =>
        "<li>" + Math.max(1, Number(item.quantity) || 1) + " × " +
        esc(item.item_name || item.name || "Item") + "</li>"
      ).join("");
      const created = order.created_at ? new Date(order.created_at) : null;
      const createdLabel = created && !Number.isNaN(created.getTime())
        ? created.toLocaleString("en-IN", { hour: "2-digit", minute: "2-digit", day: "numeric", month: "short" })
        : "";
      return '<article class="payment-confirmation-ticket" data-pending-order="' + safeId + '">' +
        '<header><strong>' + esc(order.order_number || "Order") + '</strong><time>' + esc(createdLabel) + '</time></header>' +
        '<p><strong>Amount:</strong> ₹' + amount.toLocaleString("en-IN", { maximumFractionDigits: 2 }) + '</p>' +
        '<p><strong>Method:</strong> ' + esc(order.payment_method || "UPI / Soundbox") + '</p>' +
        '<p><strong>UTR:</strong> ' + esc(order.utr_number || "Not provided") + '</p>' +
        '<ul>' + items + '</ul>' +
        (safeId ? '<div class="payment-confirmation-actions">' +
          '<button class="btn btn-primary" type="button" data-payment-action="confirm">Confirm payment</button>' +
          '<button class="btn btn-secondary" type="button" data-payment-action="reject">Reject</button>' +
        '</div>' : '<p role="alert">This order has an invalid ID and cannot be updated.</p>') +
        '</article>';
    }).join("");
  }
  async function loadPendingConfirmations() {
    if (pendingLoading) return;
    if (demoMode) {
      pendingCount.textContent = "Demo";
      pendingRoot.innerHTML = '<p class="empty-state">Payment confirmation actions are disabled in demo mode.</p>';
      return;
    }

    pendingLoading = true;
    try {
      const response = await trayApi.get("/kitchen/orders/pending-confirmation?limit=100");
      if (!Array.isArray(response?.data?.orders)) throw new Error("The payment confirmation queue returned an invalid response.");
      renderPendingConfirmations(response.data.orders);
    } catch (error) {
      pendingCount.textContent = "Unavailable";
      pendingRoot.textContent = error.status === 401
        ? "Please sign in with a kitchen or admin account to view payment claims."
        : error.status === 403
          ? "This account does not have permission to confirm payments."
          : error.message || "Unable to load payment claims. Retry when the backend is available.";
    } finally {
      pendingLoading = false;
    }
  }
  async function load() {
    if (demoMode) return render(demoQueue, true);
    try {
      const response = await trayApi.get("/kitchen/orders");
      render(response?.data?.queue || {}, false);
    } catch (error) {
      const requiresSignIn = error.status === 401 || error.status === 403;
      showError(error.status === 401 ? "Please sign in with a kitchen account." :
        error.status === 403 ? "This account does not have kitchen access." :
        "Unable to load live orders. Retry when the backend is available.", requiresSignIn);
    }
  }
  document.getElementById("retry-board").addEventListener("click", load);
  document.getElementById("kitchen-board").addEventListener("click", async event => {
    const button = event.target.closest("[data-next]");
    if (!button || demoMode) return;
    const ticket = button.closest("[data-order]");
    if (!ticket || !ticket.dataset.order) return;
    button.disabled = true;
    try {
      await trayApi.patch("/kitchen/orders/" + ticket.dataset.order + "/status", {status:button.dataset.next});
      trayNotify("Order status updated."); await load();
    } catch (error) {
      button.disabled = false; trayNotify(error.message || "Could not update order status.");
    }
  });
  pendingRoot.addEventListener("click", async event => {
    const button = event.target.closest("[data-payment-action]");
    if (!button || demoMode) return;
    const ticket = button.closest("[data-pending-order]");
    const orderId = ticket?.dataset.pendingOrder;
    if (!orderId) return;
    const action = button.dataset.paymentAction;
    if (action === "reject" && !window.confirm("Reject this payment claim and cancel the order?")) return;

    button.disabled = true;
    try {
      if (action === "confirm") {
        await trayApi.post("/kitchen/orders/" + orderId + "/confirm-payment", {
          notes: "Payment confirmed after Soundbox verification"
        });
        trayNotify("Payment confirmed and order moved to the kitchen queue.");
      } else {
        await trayApi.post("/kitchen/orders/" + orderId + "/reject-payment", {
          reason: "Payment not received"
        });
        trayNotify("Payment rejected and order cancelled.");
      }
      await Promise.all([load(), loadPendingConfirmations()]);
    } catch (error) {
      button.disabled = false;
      trayNotify(error.message || "Could not update the payment claim.");
    }
  });
  document.getElementById("logout").addEventListener("click", async () => {
    try { await trayAuth.logout(); } catch (_) {}
    window.location.href = "./login.html";
  });
  load();
  loadPendingConfirmations();
  if (!demoMode) {
    const poll = setInterval(() => {
      load();
      loadPendingConfirmations();
    },15000);
    window.addEventListener("pagehide",()=>clearInterval(poll));
  }
})();
