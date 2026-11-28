// Tests the actual browser-facing catalog mapper without a DOM dependency.
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

function loadCatalog() {
  const calls = [];
  const window = {
    trayApi: {
      async get(url) {
        calls.push(url);
        if (url === "/menu") return { items: [
          { id: 12, name: "Veg Pulao", category: "Lunch", description: "Rice", price_paise: 9000, image_url: null },
          { id: 34, name: "Cold Coffee", category: "Drinks", description: "Chilled", price_paise: 8000, image_url: "https://example.com/a.jpg" }
        ] };
        if (url === "/menu/12") return { item: { id: 12, name: "Veg Pulao", category: "Lunch", price_paise: 9000 } };
        if (url.startsWith("/menu/popular")) return { items: [{ menu_item_id: 12, quantity: 4 }] };
        throw new Error("Unexpected API path: " + url);
      }
    }
  };
  const context = { window, trayApi: window.trayApi, URL, Map, Number, Array, Date, Promise, encodeURIComponent };
  const source = fs.readFileSync(path.join(__dirname, "../../frontend/shared/catalog.js"), "utf8");
  vm.runInNewContext(source, context);
  return { catalog: window.trayCatalog, calls };
}

test("mapItem converts paise to rupees and normalizes optional fields", () => {
  const { catalog } = loadCatalog();
  const item = catalog.mapItem({ id: 12, name: "Veg Pulao", category: "Lunch", price_paise: 9000, image_url: null });
  assert.equal(item.price, 90);
  assert.equal(item.isAvailable, true);
  assert.equal(item.image, "");
  assert.equal(item.hasDiet, false);
  assert.equal(Array.from(item.ingredients).length, 0);
});

test("list loads and maps the live menu", async () => {
  const { catalog, calls } = loadCatalog();
  const items = await catalog.list();
  assert.equal(items.length, 2);
  assert.equal(items[1].price, 80);
  assert.equal(items[1].image, "https://example.com/a.jpg");
  assert.deepEqual(calls, ["/menu"]);
});

test("list caches the in-flight/result promise for the current page", async () => {
  const { catalog, calls } = loadCatalog();
  await Promise.all([catalog.list(), catalog.list()]);
  assert.equal(calls.filter(path => path === "/menu").length, 1);
});

test("get retrieves one item by numeric ID", async () => {
  const { catalog, calls } = loadCatalog();
  const item = await catalog.get("12");
  assert.equal(item.name, "Veg Pulao");
  assert.equal(calls[0], "/menu/12");
});

test("popularity maps server quantities by menu item ID", async () => {
  const { catalog, calls } = loadCatalog();
  const popular = await catalog.popularity("week");
  assert.equal(popular.get(12), 4);
  assert.match(calls[0], /period=week/);
});
