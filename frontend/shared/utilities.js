(function () {
  window.trayUtils = {
    escapeHtml(value) {
      const node = document.createElement("span");
      node.textContent = value == null ? "" : String(value);
      return node.innerHTML;
    },
    rupees(value) {
      return `₹${Number(value).toLocaleString("en-IN")}`;
    }
  };
})();
