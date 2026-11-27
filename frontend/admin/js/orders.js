(async function () {
  const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const body = document.getElementById("orders-body");
  const search = document.getElementById("order-search");
  const payment = document.getElementById("payment-filter");
  const status = document.getElementById("status-filter");
  let page = 1, pages = 1, busy = false, queuedPage = null, timer = null;
  let currentOrders = [], loadError = "";

  function render(orders = currentOrders) {
    currentOrders = orders;
    if (loadError) {
      body.innerHTML = `<tr><td colspan="5">${esc(loadError)}</td></tr>`;
      return;
    }
    body.innerHTML = orders.length ? orders.map(order => {
      const student = order.student && order.student.name;
      const amount = Number(order.total_paise || 0) / 100;
      return `<tr><td><strong>${esc(order.order_number || order.id)}</strong></td><td>${esc(student || "Student")}</td>` +
        `<td>₹${amount.toLocaleString("en-IN", {maximumFractionDigits:2})}</td>` +
        `<td><span class="status">${esc(order.order_status || "—")}</span></td>` +
        `<td>${esc(order.payment_status || "—")}</td></tr>`;
    }).join("") : '<tr><td colspan="5">No matching orders</td></tr>';

    const pager = document.getElementById("orders-pagination");
    if (pager) pager.innerHTML = `<button class="btn btn-secondary" id="orders-prev" ${page <= 1 || busy ? "disabled" : ""}>Previous</button>` +
      `<span>Page ${page} of ${Math.max(1, pages)}</span>` +
      `<button class="btn btn-secondary" id="orders-next" ${page >= pages || busy ? "disabled" : ""}>Next</button>`;
  }

  async function load(nextPage = 1) {
    // Do not drop a search/filter change just because the previous request is still in flight.
    // Keep only the latest requested page; the next request reads the latest control values.
    if (busy) {
      queuedPage = nextPage;
      return;
    }

    busy = true;
    page = Math.max(1, Number(nextPage) || 1);
    loadError = "";
    body.innerHTML = '<tr><td colspan="5">Loading…</td></tr>';

    const params = new URLSearchParams({page:String(page), per_page:"10"});
    if (search.value.trim()) params.set("search", search.value.trim());
    if (payment.value) params.set("payment_status", payment.value);
    if (status.value) params.set("order_status", status.value);

    try {
      const response = await trayApi.get(`/admin/orders?${params.toString()}`);
      const data = response?.data || {};
      pages = Math.max(1, Number(data.pagination?.pages) || 1);
      currentOrders = Array.isArray(data.orders) ? data.orders : [];
    } catch (error) {
      currentOrders = [];
      loadError = error.status===401 ? "Please sign in to view administrator orders." : error.status===403 ? "Administrator access is required." : error.message || "Unable to load orders. Please retry.";
      const pager = document.getElementById("orders-pagination");
      if (pager) pager.replaceChildren();
    } finally {
      busy = false;
      if (queuedPage !== null) {
        const requestedPage = queuedPage;
        queuedPage = null;
        void load(requestedPage);
      } else {
        render();
      }
    }
  }

  [payment,status].forEach(input => input.addEventListener("change", () => load(1)));
  search.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(() => load(1), 300);
  });
  document.getElementById("orders-pagination")?.addEventListener("click", event => {
    if (event.target.id === "orders-prev" && page > 1) load(page - 1);
    if (event.target.id === "orders-next" && page < pages) load(page + 1);
  });
  await load(1);
})();
