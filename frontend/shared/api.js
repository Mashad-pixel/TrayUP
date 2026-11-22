(function () {
  const baseUrl = window.TRAYUP_CONFIG?.apiBaseUrl || "/api";

  async function request(method, path, body) {
    const options = {
      method,
      credentials: "include",
      headers: { "Accept": "application/json" }
    };
    if (body !== undefined) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body);
    }
    const response = await fetch(`${baseUrl}${path}`, options);
    let data = null;
    try { data = await response.json(); } catch (_) {}
    if (!response.ok) {
      const error = new Error(data?.message || "Request failed");
      error.status = response.status;
      error.code = data?.error?.code;
      error.data = data;
      throw error;
    }
    return data;
  }

  window.trayApi = {
    get: (path) => request("GET", path),
    post: (path, body) => request("POST", path, body),
    patch: (path, body) => request("PATCH", path, body),
    put: (path, body) => request("PUT", path, body),
    del: (path) => request("DELETE", path)
  };
})();
