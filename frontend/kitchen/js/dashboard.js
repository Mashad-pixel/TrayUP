(function () {
  const demoMode = Boolean(window.trayMode?.isDemo?.());
  const statuses = ["received", "preparing", "ready"];
  const demoQueue = {
    received: [
      { id: 101, order_number: "TUP-4821", created_at: "10:24 AM", items: [{ name: "Masala Dosa", quantity: 2 }, { name: "Cold Coffee", quantity: 1 }] },
      { id: 102, order_number: "TUP-4825", created_at: "10:31 AM", items: [{ name: "Grilled Chicken Bowl", quantity: 1 }] }
    ],
    preparing: [{ id: 103, order_number: "TUP-4818", created_at: "10:11 AM", items: [{ name: "Paneer Butter Masala", quantity: 2 }] }],
    ready: [{ id: 104, order_number: "TUP-4809", created_at: "9:58 AM", items: [{ name: "Cheese Chilli Sandwich", quantity: 2 }, { name: "Mango Shake", quantity: 2 }] }]
  };
  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;"
  })[c]);
  let queue = null;
  let lastLoadedAt = null;
  let stale = false;
  let loading = false;

  function updateTime() {
    document.getElementById("live-time").textContent = new Date().toLocaleString("en-IN", {
      weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit"
    });
  }
  updateTime();
  const clock = setInterval(updateTime, 30000);
  window.addEventListener("pagehide", () => clearInterval(clock));

  function errorMessage(error) {
    if (error && error.status === 401) return "You are not signed in as kitchen staff. Sign in to view orders.";
    if (error && error.status === 403) return "This account does not have kitchen access.";
    if (error && typeof error.status !== "number") return "Could not reach the server. Check your connection and try again.";
    return (error && error.message) || "Could not refresh orders.";
  }

  function showError(error) {
    stale = true;
    const message = errorMessage(error);
    if (!queue) {
      document.getElementById("summary").textContent = message;
      statuses.forEach((status) => {
        const col = document.querySelector(`[data-status="${status}"]`);
        const heading = col.querySelector("h2");
        col.replaceChildren(heading);
        const p = document.createElement("p");
        p.className = "empty-state";
        p.textContent = status === "received" ? `${message} No orders are loaded.` : "No orders are loaded.";
        col.appendChild(p);
      });
      return;
    }
    render(queue, false);
    const summary = document.getElementById("summary");
    const warning = document.createElement("p");
    warning.className = "status danger";
    warning.textContent = `Could not refresh orders. Showing orders as of ${lastLoadedAt}.`;
    summary.appendChild(warning);
  }

  function render(nextQueue, isDemo) {
    queue = nextQueue;
    const counts = statuses.map((status) => Array.isArray(queue[status]) ? queue[status].length : 0);
    document.getElementById("summary").innerHTML =
      (isDemo ? '<div class="metric"><span>Mode</span><strong>Demo · sample data</strong></div>' : "") +
      [["New", counts[0]], ["Preparing", counts[1]], ["Ready for collection", counts[2]]]
        .map(([label, value]) => '<div class="metric"><span>' + label + '</span><strong>' + value + '</strong></div>').join("");
    statuses.forEach((status) => {
      const col = document.querySelector(`[data-status="${status}"]`);
      const heading = col.querySelector("h2").outerHTML;
      const orders = Array.isArray(queue[status]) ? queue[status] : [];
      const cards = orders.map((order) => {
        const id = Number(order.id);
        const safeId = Number.isInteger(id) && id > 0 ? String(id) : "";
        const items = (order.items || []).map((item) => "<li><span>" + Math.max(1, Number(item.quantity) || 1) + " × " +
          esc(item.item_name || item.name || item.menu_item_name || "Item") + "</span></li>").join("");
        const action = status === "received"
          ? '<button class="btn btn-primary" data-next="preparing">Start preparing</button>'
          : status === "preparing"
            ? '<button class="btn btn-primary" data-next="ready">Mark ready</button>'
            : '<a class="btn btn-secondary" href="./scanner.html">Hand over at the scanner</a>';
        return '<article class="order-ticket" data-order="' + safeId + '"><header><span>' + esc(order.order_number || "Order") +
          "</span><span>" + esc(order.created_at || "") + "</span></header><ul>" + items + "</ul>" + action + "</article>";
      }).join("");
      col.innerHTML = heading + (cards || '<div class="empty-state" style="background:transparent">No orders</div>');
      if (stale) col.querySelectorAll("[data-next]").forEach((button) => { button.disabled = true; });
    });
  }

  async function load() {
    if (demoMode) {
      render(demoQueue, true);
      return;
    }
    if (loading) return;
    loading = true;
    try {
      const response = await trayApi.get("/kitchen/orders");
      queue = response?.data?.queue || {};
      stale = false;
      lastLoadedAt = new Date().toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
      render(queue, false);
    } catch (error) {
      showError(error);
    } finally {
      loading = false;
    }
  }

  document.getElementById("kitchen-board").addEventListener("click", async (event) => {
    const button = event.target.closest("[data-next]");
    if (!button || stale) return;
    const ticket = button.closest("[data-order]");
    if (!ticket || !ticket.dataset.order) return;

    if (demoMode) {
      const from = statuses.find((status) => queue[status].some((order) => String(order.id) === ticket.dataset.order));
      const orderIndex = queue[from].findIndex((order) => String(order.id) === ticket.dataset.order);
      const [order] = queue[from].splice(orderIndex, 1);
      queue[button.dataset.next].push(order);
      render(queue, true);
      trayNotify("Demo only: nothing was saved.");
      return;
    }

    button.disabled = true;
    try {
      await trayApi.patch("/kitchen/orders/" + ticket.dataset.order + "/status", { status: button.dataset.next });
      trayNotify("Order status updated.");
      await load();
    } catch (error) {
      trayNotify(errorMessage(error));
      await load();
    }
  });

  document.getElementById("logout").addEventListener("click", async () => {
    const button = document.getElementById("logout");
    button.disabled = true;
    if (demoMode) {
      window.trayMode.exitDemo();
      window.location.href = "./login.html";
      return;
    }
    try {
      await trayAuth.logout();
      window.location.href = "./login.html";
    } catch (_) {
      button.disabled = false;
      trayNotify("Could not sign out. Check your connection and try again.");
    }
  });

  load();
  if (!demoMode) {
    const poll = setInterval(load, 15000);
    window.addEventListener("pagehide", () => clearInterval(poll));
  }
})();
