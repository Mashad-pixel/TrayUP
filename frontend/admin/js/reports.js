// Reports from the reporting API. Every figure comes from the server for the chosen canteen-local days.
// The CSV export is built from the same sales rows shown on the page.
(function () {
  "use strict";

  const ui = window.trayUI;
  const root = document.querySelector(".admin-content");

  const MAX_DAYS = 366;
  let period = null;     // { from, to }
  let data = null;       // loaded report bodies
  let problem = null;    // message for an invalid range or a failed load

  const ORDER_STATUS_LABELS = { received: "Received", preparing: "Preparing", ready: "Ready", collected: "Collected", cancelled: "Cancelled" };
  const PAYMENT_LABELS = { pending: "Pending", paid: "Paid", failed: "Failed", refunded: "Refunded", partially_refunded: "Partly refunded" };

  function rupees(paise) {
    return (Number(paise || 0) / 100).toFixed(2);
  }

  function dayCount(from, to) {
    return Math.round((new Date(to + "T00:00:00Z") - new Date(from + "T00:00:00Z")) / 86400000) + 1;
  }

  function validatePeriod(from, to) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(from) || !/^\d{4}-\d{2}-\d{2}$/.test(to)) return "Choose both dates.";
    if (from > to) return "The start date must be on or before the end date.";
    if (dayCount(from, to) > MAX_DAYS) return `Choose a range of ${MAX_DAYS} days or fewer.`;
    return null;
  }

  function stat(label, value) {
    return ui.el("div", { class: "admin-card" }, [ui.el("span", { text: label }), ui.el("div", { class: "value", text: value })]);
  }

  function summaryCards() {
    const o = data.overview;
    return ui.el("div", { class: "admin-stats" }, [
      stat("Orders", String(o.total_orders)),
      stat("Paid", String(o.paid_orders)),
      stat("Cancelled", String(o.cancelled_orders)),
      stat("Gross revenue", ui.money(o.gross_revenue_paise)),
      stat("Refunded", ui.money(o.refunded_paise)),
      stat("Net revenue", ui.money(o.net_revenue_paise)),
      stat("Average order", ui.money(o.average_order_value_paise)),
      stat("Collected", `${o.completion_rate_percent}%`),
      stat("Avg. preparation", o.average_preparation_minutes === null ? "—" : `${o.average_preparation_minutes} min`)
    ]);
  }

  function salesTable() {
    const rows = data.sales.days.map((day) => ui.el("tr", null, [
      ui.el("td", { text: ui.formatDay(day.date) }),
      ui.el("td", { class: "ui-num", text: String(day.orders) }),
      ui.el("td", { class: "ui-num", text: ui.money(day.revenue_paise) }),
      ui.el("td", { class: "ui-num", text: ui.money(day.refunded_paise) }),
      ui.el("td", { class: "ui-num", text: ui.money(day.revenue_paise - day.refunded_paise) })
    ]));
    return ui.table(
      [{ label: "Day" }, { label: "Orders", numeric: true }, { label: "Revenue", numeric: true }, { label: "Refunded", numeric: true }, { label: "Net", numeric: true }],
      rows
    );
  }

  function popularTable() {
    const rows = data.popular.items.map((item) => ui.el("tr", null, [
      ui.el("td", { text: item.item_name }),
      ui.el("td", { class: "ui-num", text: String(item.quantity) }),
      ui.el("td", { class: "ui-num", text: ui.money(item.revenue_paise) })
    ]));
    return ui.table([{ label: "Item" }, { label: "Sold", numeric: true }, { label: "Revenue", numeric: true }], rows);
  }

  function categoryTable() {
    const rows = data.categories.categories.map((c) => ui.el("tr", null, [
      ui.el("td", { text: c.category }),
      ui.el("td", { class: "ui-num", text: String(c.quantity) }),
      ui.el("td", { class: "ui-num", text: ui.money(c.revenue_paise) })
    ]));
    return ui.table([{ label: "Category" }, { label: "Sold", numeric: true }, { label: "Revenue", numeric: true }], rows);
  }

  function peakTable() {
    const hours = data.peak.hours;
    const busiest = Math.max(1, ...hours.map((h) => h.orders));
    const rows = hours.filter((h) => h.orders > 0).map((h) => ui.el("tr", null, [
      ui.el("td", { text: `${String(h.hour).padStart(2, "0")}:00–${String((h.hour + 1) % 24).padStart(2, "0")}:00` }),
      ui.el("td", { class: "ui-num", text: String(h.orders) }),
      ui.el("td", null, [ui.el("div", { class: "ui-bar", style: `width:${Math.round((h.orders / busiest) * 100)}%` })])
    ]));
    const offset = data.peak.timezone_offset_minutes;
    const sign = offset >= 0 ? "+" : "-";
    const label = `${sign}${String(Math.floor(Math.abs(offset) / 60)).padStart(2, "0")}:${String(Math.abs(offset) % 60).padStart(2, "0")}`;
    return ui.el("div", null, [
      ui.el("p", { class: "ui-muted", text: `Hours are in canteen time (UTC${label}).` }),
      ui.table([{ label: "Hour" }, { label: "Orders", numeric: true }, { label: "Busiest" }], rows)
    ]);
  }

  function statusTable(title, source, labels) {
    const rows = Object.entries(source || {}).map(([key, count]) => ui.el("tr", null, [
      ui.el("td", { text: labels[key] || key }),
      ui.el("td", { class: "ui-num", text: String(count) })
    ]));
    return ui.el("div", null, [ui.el("h2", { style: "font-size:16px;margin:0 0 8px", text: title }), ui.table([{ label: "Status" }, { label: "Orders", numeric: true }], rows)]);
  }

  function render() {
    const toolbar = ui.el("div", { class: "ui-toolbar" }, [
      ui.el("label", { class: "ui-field" }, ["From", ui.el("input", { id: "from", type: "date", value: period.from })]),
      ui.el("label", { class: "ui-field" }, ["To", ui.el("input", { id: "to", type: "date", value: period.to })]),
      ui.el("button", { class: "btn btn-primary", type: "button", id: "apply", text: "Show" }),
      ui.el("button", { class: "btn btn-secondary", type: "button", id: "export", disabled: !data, text: "Export sales CSV" })
    ]);
    const body = [];
    if (problem) body.push(ui.notice(problem, "warning"));
    if (data) {
      body.push(
        ui.el("div", { class: "ui-section" }, [ui.el("h2", { text: "Summary" }), summaryCards()]),
        ui.el("div", { class: "ui-section" }, [ui.el("h2", { text: "Sales by day" }), salesTable()]),
        ui.el("div", { class: "ui-section" }, [ui.el("h2", { text: "Popular items" }), popularTable()]),
        ui.el("div", { class: "ui-section" }, [ui.el("h2", { text: "Categories" }), categoryTable()]),
        ui.el("div", { class: "ui-section" }, [ui.el("h2", { text: "Busiest hours" }), peakTable()]),
        ui.el("div", { class: "ui-section" }, [ui.el("h2", { text: "Order status" }),
          ui.el("div", { class: "ui-grid" }, [
            statusTable("By order status", data.orders.by_order_status, ORDER_STATUS_LABELS),
            statusTable("By payment status", data.orders.by_payment_status, PAYMENT_LABELS)
          ])])
      );
    }
    root.replaceChildren(
      ui.header("Reports", null),
      ui.el("p", { class: "ui-muted", style: "margin-top:10px", text: "Figures are for the days you choose, in canteen time. Refunds are subtracted from revenue on the day they were issued." }),
      toolbar,
      ...body
    );
  }

  async function load() {
    const query = `from=${period.from}&to=${period.to}`;
    try {
      const [overview, sales, popular, categories, peak, orders] = await Promise.all([
        trayApi.get(`/admin/reports/overview?${query}`),
        trayApi.get(`/admin/reports/sales?${query}`),
        trayApi.get(`/admin/reports/popular-items?${query}&limit=10`),
        trayApi.get(`/admin/reports/categories?${query}`),
        trayApi.get(`/admin/reports/peak-hours?${query}`),
        trayApi.get(`/admin/reports/orders?${query}`)
      ]);
      data = {
        overview: overview.data,
        sales: sales.data,
        popular: popular.data,
        categories: categories.data,
        peak: peak.data,
        orders: orders.data
      };
      problem = null;
    } catch (error) {
      data = null;
      problem = ui.describeError(error).text;
    }
    render();
  }

  function apply() {
    const from = root.querySelector("#from").value;
    const to = root.querySelector("#to").value;
    const invalid = validatePeriod(from, to);
    if (invalid) {
      problem = invalid;
      data = null;
      render();
      return;
    }
    period = { from, to };
    problem = null;
    load();
  }

  function exportSales() {
    if (!data) return;
    const rows = [["Day", "Orders", "Revenue (INR)", "Refunded (INR)", "Net (INR)"]];
    data.sales.days.forEach((day) => {
      rows.push([day.date, day.orders, rupees(day.revenue_paise), rupees(day.refunded_paise), rupees(day.revenue_paise - day.refunded_paise)]);
    });
    ui.downloadCsv(`sales-${period.from}-to-${period.to}.csv`, rows);
  }

  root.addEventListener("click", (event) => {
    if (event.target.closest("#apply")) apply();
    else if (event.target.closest("#export")) exportSales();
  });

  period = { from: ui.addDays(ui.canteenToday(), -29), to: ui.canteenToday() };
  render();
  load();
})();
