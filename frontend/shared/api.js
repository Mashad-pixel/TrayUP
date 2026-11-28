(function () {
  const baseUrl = window.TRAYUP_CONFIG?.apiBaseUrl || "/api";
  const unsafeMethods = new Set(["POST", "PATCH", "PUT", "DELETE"]);
  const REQUEST_TIMEOUT_MS = 20000;
  let csrfTokenPromise = null;

  function assertLiveMode() {
    if (window.trayMode?.isDemo?.()) {
      const error = new Error("Demo mode cannot access live canteen data.");
      error.code = "DEMO_MODE";
      throw error;
    }
  }

  function requestAbortError() {
    const error = new Error("Request cancelled.");
    error.code = "REQUEST_ABORTED";
    return error;
  }

  function requestTimeoutError() {
    const error = new Error("The server took too long to respond. Check your connection and try again.");
    error.code = "REQUEST_TIMEOUT";
    return error;
  }

  async function readJson(response) {
    try { return await response.json(); }
    catch (error) {
      if (error && error.name === "AbortError") throw error;
      return null;
    }
  }

  // The CSRF token is tied to the server session, so it is fetched once and reused until
  // the server rejects it (after login/logout, or when it expires). Its body read is timed too.
  function getCsrfToken() {
    assertLiveMode();
    if (!csrfTokenPromise) {
      csrfTokenPromise = (async () => {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
        try {
          const response = await fetch(`${baseUrl}/csrf-token`, {
            credentials: "include",
            headers: { "Accept": "application/json" },
            signal: controller.signal
          });
          const data = await readJson(response);
          if (!response.ok || !data?.csrf_token) throw new Error("Could not load the security token. Please retry.");
          return data.csrf_token;
        } catch (error) {
          if (error && error.name === "AbortError") throw requestTimeoutError();
          throw error;
        } finally {
          clearTimeout(timeout);
        }
      })().catch((error) => {
        csrfTokenPromise = null;
        throw error;
      });
    }
    return csrfTokenPromise;
  }

  async function send(method, path, body, extraHeaders, callerSignal) {
    assertLiveMode();
    if (callerSignal?.aborted) throw requestAbortError();

    const headers = { "Accept": "application/json", ...(extraHeaders || {}) };
    const options = { method, credentials: "include", headers };
    if (body !== undefined) {
      headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body);
    }
    if (unsafeMethods.has(method)) {
      const csrfToken = await getCsrfToken();
      if (callerSignal?.aborted) throw requestAbortError();
      headers["X-CSRFToken"] = csrfToken;
    }

    const controller = new AbortController();
    const abortFromCaller = () => controller.abort();
    if (callerSignal) callerSignal.addEventListener("abort", abortFromCaller, { once: true });
    const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    options.signal = controller.signal;

    let response;
    let data = null;
    try {
      response = await fetch(`${baseUrl}${path}`, options);
      data = await readJson(response);
    } catch (error) {
      if (error && error.name === "AbortError") {
        if (callerSignal?.aborted) throw requestAbortError();
        throw requestTimeoutError();
      }
      throw error;
    } finally {
      clearTimeout(timeout);
      if (callerSignal) callerSignal.removeEventListener("abort", abortFromCaller);
    }

    if (!response.ok) {
      const error = new Error(data?.message || "Request failed");
      error.status = response.status;
      error.code = data?.error?.code;
      error.data = data;
      throw error;
    }
    return data;
  }

  async function request(method, path, body, options) {
    const extraHeaders = options?.headers;
    const callerSignal = options?.signal;
    try {
      return await send(method, path, body, extraHeaders, callerSignal);
    } catch (error) {
      // A CSRF rejection happens before the view runs, so retrying once with a fresh token is safe.
      if (unsafeMethods.has(method) && error.code === "CSRF_TOKEN_INVALID" && !callerSignal?.aborted) {
        csrfTokenPromise = null;
        return send(method, path, body, extraHeaders, callerSignal);
      }
      throw error;
    }
  }

  window.trayApi = {
    get: (path, options) => request("GET", path, undefined, options),
    post: (path, body, options) => request("POST", path, body, options),
    patch: (path, body, options) => request("PATCH", path, body, options),
    put: (path, body, options) => request("PUT", path, body, options),
    del: (path, options) => request("DELETE", path, undefined, options)
  };
})();
