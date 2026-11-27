// Student pages: paged order tracking, and a checkout key that survives a refresh.
const { test, describe, afterEach } = require("node:test");
const assert = require("node:assert/strict");
const path = require("path");
const { loadPage, settle, text } = require("./harness");

const ROOT = process.env.FRONTEND_ROOT || path.resolve(__dirname, "../../frontend");
const open = [];
afterEach(() => { while (open.length) { try { open.pop().close(); } catch (_) {} } });
const load = async (opts) => { const p = await loadPage({ root: ROOT, ...opts }); open.push(p); return p; };
const button = (p, selector) => p.doc.querySelector(selector);

const order = (n) => ({
  id: n, order_number: `TUP-${1000 + n}`, order_status: "received", payment_status: "paid",
  subtotal_paise: 1000, discount_paise: 0, tax_paise: 0, total_paise: 1000, items: [],
  created_at: "2026-02-10T04:30:00+00:00", updated_at: "2026-02-10T04:30:00+00:00",
});
const page = (from, to, total, hasNext) => ({
  success: true, message: "", data: {
    orders: Array.from({ length: to - from + 1 }, (_, i) => order(from + i)),
    pagination: { page: Math.ceil(from / 10), per_page: 10, total, pages: Math.ceil(total / 10), has_next: hasNext, has_prev: false },
  },
});

describe("order tracking pages through every order", () => {
  test("the first request asks for one page of ten", async () => {
    const p = await load({ page: "student/tracking.html", url: "/student/tracking.html", routes: {
      "GET /api/orders": { status: 200, body: page(1, 10, 25, true) },
    } });
    await settle(); await settle();
    const requested = p.calls.find((c) => c.path.includes("/api/orders"));
    assert.match(requested.path, /page=1&per_page=10/);
  });

  test("a Load more button appears while more orders exist, and appends the next page", async () => {
    const p = await load({ page: "student/tracking.html", url: "/student/tracking.html", routes: {
      "GET /api/orders": (req) => req.path.includes("page=2") ? { status: 200, body: page(11, 20, 25, true) } : { status: 200, body: page(1, 10, 25, true) },
    } });
    await settle(); await settle();
    assert.match(text(p.doc), /TUP-1001/);
    assert.doesNotMatch(text(p.doc), /TUP-1011/);
    button(p, "[data-load-more]").click();
    await settle(); await settle();
    assert.match(text(p.doc), /TUP-1011/);
    assert.match(text(p.doc), /TUP-1001/, "earlier orders stay on the page");
  });

  test("the button disappears when there are no more orders", async () => {
    const p = await load({ page: "student/tracking.html", url: "/student/tracking.html", routes: {
      "GET /api/orders": { status: 200, body: page(1, 5, 5, false) },
    } });
    await settle(); await settle();
    assert.equal(button(p, "[data-load-more]"), null);
  });

  test("a failed Load more keeps the orders already shown and says so", async () => {
    const p = await load({ page: "student/tracking.html", url: "/student/tracking.html", routes: {
      "GET /api/orders": (req) => req.path.includes("page=2") ? new TypeError("Failed to fetch") : { status: 200, body: page(1, 10, 25, true) },
    } });
    await settle(); await settle();
    button(p, "[data-load-more]").click();
    await settle(); await settle();
    assert.match(text(p.doc), /TUP-1001/);
    assert.match(text(p.doc), /We couldn’t load more orders/);
    assert.ok(button(p, "[data-load-more]"), "the button stays so the student can try again");
  });
});

describe("unpaid order confirmation uses the online payment model", () => {
  test("pending payment is not described as pay-at-counter or as a payment method", async () => {
    const p = await load({ page: "student/confirmation.html", url: "/student/confirmation.html?order_id=55", routes: {
      "GET /api/orders/55": { status: 200, body: { success: true, data: {
        id: 55, order_number: "TUP-55", order_status: "pending_payment", payment_status: "pending",
        customer_name: "Asha", customer_phone: "9876543210", instructions: "No onion", items: [],
      } } },
    } });
    await settle(); await settle();
    assert.match(text(p.doc), /Payment pending/);
    assert.match(text(p.doc), /Online payment pending/);
    assert.doesNotMatch(text(p.doc), /Pay at the counter|Payment method/);
  });
});

describe("checkout keeps its idempotency key across a refresh", () => {
  const CART = JSON.stringify([{ id: 1, name: "Samosa", price: 15, qty: 2 }]);
  const fill = (p) => {
    p.doc.getElementById("name").value = "Asha";
    p.doc.getElementById("phone").value = "9876543210";
  };
  const submit = (p) => p.doc.getElementById("checkout-form").dispatchEvent(new p.win.Event("submit", { cancelable: true, bubbles: true }));
  const orderPosts = (p) => p.calls.filter((c) => c.method === "POST" && c.path.endsWith("/api/orders"));

  test("a dropped order request is retried after a refresh with the same key, and the key stays until payment completes", async () => {
    let attempt = 0;
    const routes = {
      "POST /api/orders": () => {
        attempt += 1;
        if (attempt === 1) return new TypeError("Failed to fetch");
        return { status: 201, body: { success: true, message: "", data: { id: 9, order_number: "TUP-1009", total_paise: 3000, order_status: "pending_payment", payment_status: "pending", items: [] } } };
      },
    };
    const first = await load({ page: "student/checkout.html", url: "/student/checkout.html", local: { "trayup-cart": CART }, routes });
    await settle();
    fill(first);
    submit(first);
    await settle(); await settle();
    const firstKey = orderPosts(first)[0].headers["Idempotency-Key"];
    assert.ok(firstKey, "the first attempt sends a key");
    const saved = first.win.sessionStorage.getItem("trayup-checkout-key");
    assert.ok(saved, "the key is kept after a failed attempt");

    // A refresh is a new page load with the same tab storage.
    const second = await load({ page: "student/checkout.html", url: "/student/checkout.html",
      local: { "trayup-cart": CART }, session: { "trayup-checkout-key": saved }, routes });
    await settle();
    fill(second);
    submit(second);
    await settle(); await settle();
    assert.equal(orderPosts(second)[0].headers["Idempotency-Key"], firstKey, "the retry reuses the key");
    const stillSaved = JSON.parse(second.win.sessionStorage.getItem("trayup-checkout-key"));
    assert.equal(stillSaved.key, firstKey, "the key remains while payment is still pending");

    // A second refresh before paying must retrieve the same pending server order.
    const third = await load({ page: "student/checkout.html", url: "/student/checkout.html",
      local: { "trayup-cart": CART }, session: { "trayup-checkout-key": JSON.stringify(stillSaved) }, routes });
    await settle();
    fill(third);
    submit(third);
    await settle(); await settle();
    assert.equal(orderPosts(third)[0].headers["Idempotency-Key"], firstKey, "a refresh after order creation does not create a second order");
    assert.ok(third.win.sessionStorage.getItem("trayup-checkout-key"), "key remains available until payment confirmation");
  });

  test("a payment already confirmed on the server is not charged again", async () => {
    const details = { name: "Asha", phone: "9876543210", instructions: "", paymentMethod: "razorpay" };
    const fingerprint = JSON.stringify([[[1, 2]], details.name, "+91" + details.phone, details.instructions]);
    const p = await load({ page: "student/checkout.html", url: "/student/checkout.html",
      local: { "trayup-cart": CART },
      session: { "trayup-checkout-key": JSON.stringify({ key: "paid-order-key", fingerprint }) },
      routes: { "POST /api/orders": { status: 200, body: { success: true, data: {
        id: 44, order_number: "TUP-1044", total_paise: 3000, order_status: "received", payment_status: "paid", items: []
      } } } } });
    await settle();
    fill(p);
    submit(p);
    await settle(); await settle();
    assert.equal(p.calls.filter((call) => call.method === "POST" && call.path.endsWith("/api/payments/create-order")).length, 0,
      "the page must not open another payment for an order the server marks paid");
    assert.equal(p.win.sessionStorage.getItem("trayup-checkout-key"), null, "a completed order clears its key");
    assert.equal(p.win.localStorage.getItem("trayup-cart"), null, "a completed order clears the cart");
  });

  test("changing the cart gives the next order a new key", async () => {
    const p = await load({ page: "student/checkout.html", url: "/student/checkout.html", local: { "trayup-cart": CART },
      session: { "trayup-checkout-key": JSON.stringify({ key: "old-key", fingerprint: JSON.stringify([[9, 9]]) }) },
      routes: { "POST /api/orders": new TypeError("Failed to fetch") } });
    await settle();
    fill(p);
    submit(p);
    await settle(); await settle();
    assert.notEqual(orderPosts(p)[0].headers["Idempotency-Key"], "old-key");
  });
});
