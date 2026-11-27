const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const SOURCE = fs.readFileSync(path.resolve(__dirname, "../../frontend/shared/api.js"), "utf8");

test("trayApi accepts an AbortSignal and reports an explicit request-cancelled error", async () => {
  const context = vm.createContext({
    window: {},
    AbortController,
    setTimeout,
    clearTimeout,
    fetch: (_url, options) => new Promise((_resolve, reject) => {
      options.signal.addEventListener("abort", () => {
        const error = new Error("aborted");
        error.name = "AbortError";
        reject(error);
      }, { once: true });
    }),
  });
  vm.runInContext(SOURCE, context);

  const controller = new AbortController();
  const pending = context.window.trayApi.get("/slow", { signal: controller.signal });
  controller.abort();

  await assert.rejects(pending, (error) => error.code === "REQUEST_ABORTED");
});

test("trayApi turns its 20-second request deadline into a REQUEST_TIMEOUT error", async () => {
  const context = vm.createContext({
    window: {},
    AbortController,
    setTimeout: (callback) => setTimeout(callback, 5),
    clearTimeout,
    fetch: (_url, options) => new Promise((_resolve, reject) => {
      options.signal.addEventListener("abort", () => {
        const error = new Error("aborted");
        error.name = "AbortError";
        reject(error);
      }, { once: true });
    }),
  });
  vm.runInContext(SOURCE, context);

  await assert.rejects(context.window.trayApi.get("/slow"), (error) => error.code === "REQUEST_TIMEOUT");
});
