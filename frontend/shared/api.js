(function () {
  const baseUrl = window.TRAYUP_CONFIG?.apiBaseUrl || "/api";
  const STATE_CHANGING = new Set(["POST", "PUT", "PATCH", "DELETE"]);
  let csrfToken = null;

  // Flask-WTF protects every state-changing request. Fetch a token once, reuse it, and
  // refresh it if the server rejects it.
  async function fetchCsrfToken() {
    const response = await fetch(`${baseUrl}/csrf-token`, {
      credentials: "include",
      headers: { "Accept": "application/json" }
    });
    const data = await response.json().catch(() => null);
    csrfToken = data?.csrf_token || null;
    return csrfToken;
  }

  async function request(method, path, body, extraHeaders, retried) {
    const options = {
      method,
      credentials: "include",
      headers: { "Accept": "application/json", ...(extraHeaders || {}) }
    };
    if (body !== undefined) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body);
    }
    if (STATE_CHANGING.has(method)) {
      const token = csrfToken || await fetchCsrfToken();
      if (token) options.headers["X-CSRFToken"] = token;
    }

    const response = await fetch(`${baseUrl}${path}`, options);
    let data = null;
    try { data = await response.json(); } catch (_) {}

    // Login, logout and register return a fresh CSRF token. Keep it for the next request.
    if (data?.data?.csrf_token) csrfToken = data.data.csrf_token;

    if (!response.ok) {
      if (!retried && STATE_CHANGING.has(method) && data?.error?.code === "CSRF_TOKEN_INVALID") {
        csrfToken = null;
        return request(method, path, body, extraHeaders, true);
      }
      const error = new Error(data?.message || "Request failed");
      error.status = response.status;
      error.code = data?.error?.code;
      error.data = data;
      throw error;
    }
    return data;
  }

  window.trayApi = {
    get: (path, headers) => request("GET", path, undefined, headers),
    post: (path, body, headers) => request("POST", path, body, headers),
    patch: (path, body, headers) => request("PATCH", path, body, headers),
    put: (path, body, headers) => request("PUT", path, body, headers),
    del: (path, headers) => request("DELETE", path, undefined, headers)
  };
})();
