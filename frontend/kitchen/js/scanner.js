(function () {
  const form = document.getElementById("scan-form");
  const tokenInput = document.getElementById("token");
  const result = document.getElementById("scan-result");
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;"
  })[c]);
  const demoMode = Boolean(window.trayMode?.isDemo?.());
  let stream = null;
  let scanning = false;

  function message(title, detail) {
    result.innerHTML = '<div class="empty-state"><strong>' + escapeHtml(title) +
      "</strong><p>" + escapeHtml(detail) + "</p></div>";
  }

  function stopCamera() {
    scanning = false;
    if (stream) { stream.getTracks().forEach((track) => track.stop()); stream = null; }
    const video = document.getElementById("camera");
    if (video) video.srcObject = null;
  }

  function safeError(error, fallback) {
    if (error && error.code === "DEMO_MODE") return error.message;
    if (error && typeof error.status !== "number") return "Could not reach the server. Nothing was checked.";
    return (error && error.message) || fallback;
  }

  async function verify(token) {
    if (!token) return message("Collection not verified", "Enter or scan a collection code.");
    if (demoMode) {
      result.innerHTML = '<div class="card" style="padding:16px"><span class="status">Demo order · not a real order</span>' +
        '<p style="margin:10px 0 14px">This sample collection has not been checked by the server.</p>' +
        '<button class="btn btn-primary" id="confirm-handover" type="button">Confirm handover</button></div>';
      document.getElementById("confirm-handover").addEventListener("click", () => {
        trayNotify("Demo only: nothing was recorded.");
        message("Demo only", "Nothing was recorded or sent to the server.");
      });
      stopCamera();
      return;
    }

    try {
      const response = await trayApi.post("/kitchen/collection/verify", { token });
      const data = response?.data || {};
      if (data.order_status !== "ready") {
        return message("Collection not ready", "This order cannot be handed over yet.");
      }
      const orderNumber = escapeHtml(data.order_number || "Collection ready");
      result.innerHTML = '<div class="card" style="padding:16px"><span class="status">Valid code</span>' +
        '<p style="margin:10px 0 14px">' + orderNumber + '</p>' +
        '<button class="btn btn-primary" id="confirm-handover" type="button">Confirm handover</button></div>';
      document.getElementById("confirm-handover").addEventListener("click", () => confirmHandover(token));
      stopCamera();
    } catch (error) {
      message("Collection not verified", safeError(error, "Invalid or expired collection code."));
    }
  }

  async function confirmHandover(token) {
    const button = document.getElementById("confirm-handover");
    if (button) button.disabled = true;
    try {
      await trayApi.post("/kitchen/collection/confirm", { token });
      trayNotify("Order collected successfully.");
      message("Collection complete", "Handover was confirmed by the server.");
    } catch (error) {
      if (button) button.disabled = false;
      const detail = safeError(error, "Unable to confirm collection.");
      trayNotify(error.message || detail);
      message("Handover not confirmed", detail);
    }
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    verify(tokenInput.value.trim());
  });

  async function startCamera() {
    if (demoMode || !navigator.mediaDevices?.getUserMedia) return;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
      const video = document.getElementById("camera");
      video.srcObject = stream;
      video.hidden = false;
      await video.play();
      document.getElementById("scanner-placeholder").hidden = true;
      if (!("BarcodeDetector" in window)) return;
      const detector = new BarcodeDetector({ formats: ["qr_code"] });
      scanning = true;
      const scan = async () => {
        if (!scanning) return;
        try {
          const codes = await detector.detect(video);
          if (codes.length) {
            tokenInput.value = codes[0].rawValue;
            await verify(codes[0].rawValue);
            return;
          }
        } catch (_) {}
        if (scanning) requestAnimationFrame(scan);
      };
      scan();
    } catch (_) {
      document.getElementById("scanner-placeholder").textContent =
        "Camera unavailable — enter the collection token manually.";
      stopCamera();
    }
  }

  window.addEventListener("pagehide", stopCamera);
  startCamera();
})();
