// Administrator overview. Figures come from the reporting overview API for two windows: today and
// the last 30 days (canteen-local days). If a request fails, the page says so and shows no figures.
(function () {
  "use strict";

  const ui = window.trayUI;
  const statsBox = document.getElementById("admin-stats");
  const rows = document.getElementById("admin-orders");

  const nav = [["Overview", "dashboard.html"], ["Menu", "menu.html"], ["Categories", "categories.html"], ["Orders", "orders.html"], ["Staff", "staff.html"], ["Reports", "reports.html"], ["Refunds", "refunds.html"], ["Settings", "settings.html"]];
  document.getElementById("admin-nav").innerHTML = nav.map(([name, file]) =>
    `<a class="${file === "dashboard.html" ? "active" : ""}" href="./${file}">${name}</a>`).join("");

  function stat(label, value) {
    return ui.el("div", { class: "admin-card" }, [ui.el("span", { text: label }), ui.el("div", { class: "value", text: value })]);
  }

  function windowCards(title, summary) {
    return ui.el("div", { class: "ui-section" }, [
      ui.el("h2", { text: title }),
      ui.el("div", { class: "admin-stats" }, [
        stat("Orders", String(summary.total_orders)),
        stat("Paid", String(summary.paid_orders)),
        stat("Gross revenue", ui.money(summary.gross_revenue_paise)),
        stat("Net revenue", ui.money(summary.net_revenue_paise)),
        stat("Average order", ui.money(summary.average_order_value_paise)),
        stat("Collected", `${summary.completion_rate_percent}%`)
      ])
    ]);
  }

  function orderRow(order) {
    return ui.el("tr", null, [
      ui.el("td", { text: order.order_number || String(order.id) }),
      ui.el("td", { text: (order.student && order.student.name) || "Guest" }),
      ui.el("td", { class: "ui-num", text: ui.money(order.total_paise) }),
      ui.el("td", { text: order.order_status || "—" }),
      ui.el("td", { text: order.payment_status || "—" })
    ]);
  }

  function messageRow(text) {
    return ui.el("tr", null, [ui.el("td", { colspan: 5, class: "ui-muted", text })]);
  }

  function showError(error) {
    const described = ui.describeError(error);
    const text = described.signIn
      ? described.text
      : "Could not load the figures or orders. Nothing is shown in their place. Refresh the page to try again.";
    statsBox.replaceChildren(ui.el("div", { class: "admin-card status warning", style: "grid-column:1/-1" }, [
      ui.el("span", { text }),
      described.signIn ? ui.el("div", { class: "value", style: "font-size:16px" }, [ui.el("a", { href: "./login.html", style: "text-decoration:underline", text: "Sign in" })]) : null
    ]));
    rows.replaceChildren(messageRow(described.signIn ? "Sign in to view orders" : "Could not load orders"));
  }

  async function load() {
    const today = ui.canteenToday();
    const monthStart = ui.addDays(today, -29);
    try {
      const [todayReport, monthReport, recent] = await Promise.all([
        trayApi.get(`/admin/reports/overview?from=${today}&to=${today}`),
        trayApi.get(`/admin/reports/overview?from=${monthStart}&to=${today}`),
        trayApi.get("/admin/orders?per_page=8")
      ]);
      statsBox.replaceChildren(
        windowCards(`Today (${ui.formatDay(today)})`, todayReport.data),
        windowCards(`Last 30 days (${ui.formatDay(monthStart)} to ${ui.formatDay(today)})`, monthReport.data)
      );
      const orders = recent.data.orders || [];
      rows.replaceChildren(...(orders.length ? orders.map(orderRow) : [messageRow("No orders yet")]));
    } catch (error) {
      showError(error);
    }
  }

  document.getElementById("logout").addEventListener("click", async () => {
    if (window.trayMode?.isDemo?.()) { window.trayMode.exitDemo(); window.location.href = "./login.html"; return; }
    try {
      await trayAuth.logout();
    } catch (_) {
      trayNotify("Could not sign out. Check the connection and try again.");
      return;
    }
    window.location.href = "./login.html";
  });

  load();
})();
