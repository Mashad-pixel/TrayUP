const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const SOURCE = fs.readFileSync(path.resolve(__dirname, "../../frontend/shared/storage.js"), "utf8");

test("trayStorage catches browser storage failures and returns safe results", () => {
  const context = vm.createContext({
    window: { location: { href: "https://trayup.example/student/cart.html" } },
    localStorage: {
      getItem() { throw new Error("storage disabled"); },
      setItem() { throw new Error("storage disabled"); },
      removeItem() { throw new Error("storage disabled"); },
    },
    URL,
  });
  vm.runInContext(SOURCE, context);
  const storage = context.window.trayStorage;

  assert.deepEqual(Array.from(storage.getCart()), []);
  assert.equal(storage.set("trayup-cart", [{ id: 1 }]), false);
  assert.equal(storage.remove("trayup-cart"), false);
});
