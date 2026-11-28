// Student order pages: checkout sends the typed details, the confirmation page shows the order the
// server saved, and the buttons on the animated page lead somewhere.
const { test, describe, afterEach } = require("node:test");
const assert = require("node:assert/strict");
const path = require("path");
const { loadPage, settle, text } = require("./harness");

const ROOT = process.env.FRONTEND_ROOT || path.resolve(__dirname, "../../frontend");
const open = [];
afterEach(() => { while (open.length) { try { open.pop().close(); } catch (_) {} } });
const load = async (opts) => { const p = await loadPage({ root: ROOT, ...opts }); open.push(p); return p; };

const SERVER_ORDER = {
  id: 7, order_number: "TU2611270001", order_status: "pending_payment", payment_status: "pending",
  subtotal_paise: 1000, discount_paise: 0, tax_paise: 0, total_paise: 1000,
  customer_name: "Asha Rao", customer_phone: "+919876543210", instructions: "Less sugar",
  items: [{ menu_item_id: 1, item_name: "Samosa", unit_price_paise: 1000, quantity: 2, line_total_paise: 2000 }],
  created_at: "2026-11-27T04:30:00+00:00", updated_at: "2026-11-27T04:30:00+00:00",
};
const orderResponse = (order) => ({ status: 200, body: { success: true, message: "", data: order } });

describe("confirmation shows the order the server saved", () => {
  test("it loads the order by id and ignores anything stored in the browser", async () => {
    const p = await load({
      page: "student/confirmation.html", url: "/student/confirmation.html?order_id=7",
      local: { "trayup-last-order": JSON.stringify({ success: true, data: { order_number: "FAKE", student_name: "Someone Else", payment_status: "paid" } }) },
      routes: { "GET /api/orders/7": orderResponse(SERVER_ORDER) },
    });
    await settle(); await settle();

    assert.ok(p.calls.some((c) => c.method === "GET" && c.path === "/api/orders/7"), "the order is fetched from the server");
    const body = text(p.doc);
    assert.match(body, /TU2611270001/);
    assert.match(body, /Asha Rao/);
    assert.match(body, /\+919876543210/);
    assert.match(body, /Less sugar/);
    assert.doesNotMatch(body, /FAKE|Someone Else/, "the stored copy is not shown");
    assert.equal(p.navigations.length, 0, "an unpaid order stays on this page");
  });

  test("without an order id it says the order was not found and makes no order request", async () => {
    const p = await load({ page: "student/confirmation.html", url: "/student/confirmation.html", routes: {} });
    await settle(); await settle();

    assert.match(text(p.doc), /couldn’t find this order/);
    assert.equal(p.calls.filter((c) => c.path.startsWith("/api/orders/")).length, 0);
  });

  test("an order that is not the student's shows not found, not the details", async () => {
    const p = await load({
      page: "student/confirmation.html", url: "/student/confirmation.html?order_id=99",
      routes: { "GET /api/orders/99": { status: 404, body: { success: false, message: "Order not found.", error: { code: "ORDER_NOT_FOUND" } } } },
    });
    await settle(); await settle();

    assert.match(text(p.doc), /couldn’t find this order/);
    assert.doesNotMatch(text(p.doc), /Asha/);
  });

  test("a signed-out visitor is sent to log in", async () => {
    const p = await load({
      page: "student/confirmation.html", url: "/student/confirmation.html?order_id=7",
      routes: { "GET /api/orders/7": { status: 401, body: { success: false, message: "Please log in first.", error: { code: "AUTH_REQUIRED" } } } },
    });
    await settle(); await settle();

    assert.ok(p.navigations.length > 0, "the page tries to leave for the login page");
  });

  test("the track link carries the order id", async () => {
    const p = await load({
      page: "student/confirmation.html", url: "/student/confirmation.html?order_id=7",
      routes: { "GET /api/orders/7": orderResponse(SERVER_ORDER) },
    });
    await settle(); await settle();

    const trackYourOrder = [...p.doc.querySelectorAll("a")].find((a) => a.textContent.trim() === "Track your order");
    assert.ok(trackYourOrder, "the Track your order link is on the page");
    assert.match(trackYourOrder.getAttribute("href"), /tracking\.html\?order_id=7$/);
  });
});

describe("paid confirmation uses the server order details", () => {
  const animated = (query) => load({
    page: "student/order-placed-animation.html",
    url: `/student/order-placed-animation.html?receipt=TU2611270001${query || ""}`,
    routes: { "GET /api/orders/7": orderResponse({ ...SERVER_ORDER, payment_status: "paid" }) },
  });

  test("Track My Order links to the order's tracking page", async () => {
    const p = await animated("&order_id=7");
    await settle(); await settle();
    assert.equal(p.doc.getElementById("track-link").getAttribute("href"), "./tracking.html?order_id=7");
  });

  test("Continue Shopping links to the menu", async () => {
    const p = await animated("&order_id=7");
    const link = [...p.doc.querySelectorAll("a")].find((entry) => entry.textContent.trim() === "Continue shopping");
    assert.equal(link.getAttribute("href"), "../index.html");
  });

  test("the receipt number on the page comes from the server", async () => {
    const p = await animated("&order_id=7");
    await settle(); await settle();
    assert.equal(p.doc.getElementById("receipt").textContent, SERVER_ORDER.order_number);
  });
});

describe("tracking opens the order it was linked to", () => {
  test("an order id in the link is accepted and the orders still render", async () => {
    const p = await load({
      page: "student/tracking.html", url: "/student/tracking.html?order_id=7",
      routes: { "GET /api/orders": { status: 200, body: { success: true, message: "", data: { orders: [SERVER_ORDER], pagination: { page: 1, per_page: 10, total: 1, pages: 1, has_next: false, has_prev: false } } } } },
    });
    await settle(); await settle();

    assert.match(text(p.doc), /TU2611270001/);
    assert.ok(p.doc.querySelector('[data-order="7"]'), "the matching order card is on the page");
  });
});

describe("checkout sends the typed details to the server", () => {
  const CART = JSON.stringify([{ id: 1, name: "Samosa", price: 10, qty: 2 }]);
  const liveMenu = { "GET /api/menu": { status: 200, body: { items: [
    { id: 1, name: "Samosa", price_paise: 1000, is_available: true },
  ] } } };
  const fill = (p, name = "Asha", instructions = "Less sugar") => {
    p.doc.getElementById("name").value = name;
    p.doc.getElementById("phone").value = "9876543210";
    p.doc.getElementById("instructions").value = instructions;
  };
  const submit = (p) => p.doc.getElementById("checkout-form").dispatchEvent(new p.win.Event("submit", { cancelable: true, bubbles: true }));
  const orderPosts = (p) => p.calls.filter((c) => c.method === "POST" && c.path.endsWith("/api/orders"));
  const created = { status: 201, body: { success: true, message: "", data: { id: 7, order_number: "TU2611270001", total_paise: 2000, order_status: "pending_payment", payment_status: "pending", items: [] } } };
  const mockSuccessfulPayment = (p) => {
    p.win.trayPayment.pay = async () => ({ data: { payment_status: "paid", order_status: "received" } });
  };

  test("the order request carries the name, phone and instructions", async () => {
    const p = await load({ page: "student/checkout.html", url: "/student/checkout.html", local: { "trayup-cart": CART }, routes: { ...liveMenu, "POST /api/orders": created } });
    await settle();
    fill(p);
    mockSuccessfulPayment(p);
    submit(p);
    await settle(); await settle();

    const body = orderPosts(p)[0].body;
    assert.equal(body.customer_name, "Asha");
    assert.equal(body.customer_phone, "9876543210");
    assert.equal(body.instructions, "Less sugar");
    assert.deepEqual(body.items, [{ menu_item_id: 1, quantity: 2 }]);
  });

  test("a verified online payment goes to its confirmation page by id, and the cart is cleared", async () => {
    const p = await load({ page: "student/checkout.html", url: "/student/checkout.html", local: { "trayup-cart": CART }, routes: { ...liveMenu, "POST /api/orders": created } });
    await settle();
    fill(p);
    mockSuccessfulPayment(p);
    submit(p);
    await settle(); await settle();

    assert.ok(p.navigations.length > 0, "the page moves on to the confirmation");
    assert.equal(p.win.localStorage.getItem("trayup-last-order"), null, "no copy of the order is stored in the browser");
    assert.equal(p.win.localStorage.getItem("trayup-cart"), null, "the cart is cleared");
  });

  test("cash payment is not offered and cannot create an order", async () => {
    const p = await load({ page: "student/checkout.html", url: "/student/checkout.html", local: { "trayup-cart": CART }, routes: { ...liveMenu, "POST /api/orders": created } });
    await settle();
    fill(p);
    assert.equal(p.doc.querySelector('input[name="payment_method"][value="cash"]'), null);
    const online = p.doc.querySelector('input[name="payment_method"][value="razorpay"]');
    online.checked = false;
    const unsupported = p.doc.createElement("input");
    unsupported.type = "radio"; unsupported.name = "payment_method"; unsupported.value = "cash"; unsupported.checked = true;
    p.doc.getElementById("checkout-form").appendChild(unsupported);
    submit(p); await settle();
    assert.equal(orderPosts(p).length, 0);
  });

  test("changing the typed name gives the next attempt a new idempotency key", async () => {
    let attempt = 0;
    const routes = {
      ...liveMenu,
      "POST /api/orders": () => {
        attempt += 1;
        return attempt === 1 ? new TypeError("Failed to fetch") : created;
      },
    };
    const first = await load({ page: "student/checkout.html", url: "/student/checkout.html", local: { "trayup-cart": CART }, routes });
    await settle();
    fill(first, "Asha");
    submit(first);
    await settle(); await settle();
    const firstKey = orderPosts(first)[0].headers["Idempotency-Key"];

    const second = await load({ page: "student/checkout.html", url: "/student/checkout.html", local: { "trayup-cart": CART },
      session: { "trayup-checkout-key": first.win.sessionStorage.getItem("trayup-checkout-key") }, routes });
    await settle();
    fill(second, "Ravi");
    mockSuccessfulPayment(second);
    submit(second);
    await settle(); await settle();

    assert.notEqual(orderPosts(second)[0].headers["Idempotency-Key"], firstKey, "different details are a different request");
  });
});

describe("a paid-out or expired order is not reused under its key", () => {
  const CART = JSON.stringify([{ id: 1, name: "Samosa", price: 10, qty: 2 }]);
  const liveMenu = { "GET /api/menu": { status: 200, body: { items: [
    { id: 1, name: "Samosa", price_paise: 1000, is_available: true },
  ] } } };
  const fill = (p) => {
    p.doc.getElementById("name").value = "Asha";
    p.doc.getElementById("phone").value = "9876543210";
  };
  const submit = (p) => p.doc.getElementById("checkout-form").dispatchEvent(new p.win.Event("submit", { cancelable: true, bubbles: true }));
  const orderPosts = (p) => p.calls.filter((c) => c.method === "POST" && c.path.endsWith("/api/orders"));
  const mockSuccessfulPayment = (p) => {
    p.win.trayPayment.pay = async () => ({ data: { payment_status: "paid", order_status: "received" } });
  };

  test("after ORDER_CANCELLED the next submit sends a new key and creates a new order", async () => {
    let attempt = 0;
    const routes = {
      ...liveMenu,
      "POST /api/orders": () => {
        attempt += 1;
        if (attempt === 1) {
          return { status: 409, body: { success: false, message: "This order was cancelled. Place a new order.", error: { code: "ORDER_CANCELLED" } } };
        }
        return { status: 201, body: { success: true, message: "", data: { id: 8, order_number: "TU2611270002", total_paise: 2000, order_status: "pending_payment", payment_status: "pending", items: [] } } };
      },
    };
    const p = await load({ page: "student/checkout.html", url: "/student/checkout.html", local: { "trayup-cart": CART }, routes });
    await settle();
    fill(p);
    mockSuccessfulPayment(p);
    submit(p);
    await settle(); await settle();
    const firstKey = orderPosts(p)[0].headers["Idempotency-Key"];
    assert.match(text(p.doc), /This order was cancelled/);

    mockSuccessfulPayment(p);
    submit(p);
    await settle(); await settle();
    const secondKey = orderPosts(p)[1].headers["Idempotency-Key"];
    assert.notEqual(secondKey, firstKey, "the cancelled order's key is not sent again");
    assert.ok(p.navigations.length > 0, "the new order is created and the page moves on");
  });
});
