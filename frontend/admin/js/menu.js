(function () {
  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;"
  })[character]);
  const content = document.querySelector(".admin-content");
  // Menu items are stored by the server. Items are disabled rather than deleted, so order
  // history keeps its dish names and prices.
  content.innerHTML = `<div style="display:flex;justify-content:space-between;align-items:center"><h1 class="admin-title">Menu items</h1><button class="btn btn-primary" id="add-item" type="button">Add item</button></div><p id="menu-status" role="status" style="margin-top:12px;color:var(--muted)"></p><div class="card table-card" style="margin-top:22px"><table class="data-table"><thead><tr><th>Item</th><th>Category</th><th>Price</th><th>Availability</th><th>Actions</th></tr></thead><tbody id="menu-body"></tbody></table></div>`;

  const body = document.getElementById("menu-body");
  const status = document.getElementById("menu-status");
  let items = [];

  function describeError(error) {
    const details = error.data?.details;
    if (details && typeof details === "object") {
      const first = Object.values(details).find((value) => typeof value === "string");
      if (first) return first;
    }
    return error.message || "Something went wrong. Try again.";
  }

  function rupees(paise) {
    return `₹${(Number(paise || 0) / 100).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
  }

  function dietLabel(value) {
    if (value === true) return "Veg";
    if (value === false) return "Non-veg";
    return "Not recorded";
  }

  function render() {
    body.innerHTML = items.length ? items.map((item) => `
      <tr>
        <td><strong>${esc(item.name)}</strong><br><small style="color:var(--muted)">${esc(dietLabel(item.is_veg))}</small></td>
        <td>${esc(item.category)}</td>
        <td>${rupees(item.price_paise)}</td>
        <td><span class="status ${item.is_available ? "" : "danger"}">${item.is_available ? "Available" : "Unavailable"}</span></td>
        <td>
          <button class="btn btn-secondary" data-edit="${esc(item.id)}" type="button">Edit</button>
          <button class="btn btn-secondary" data-toggle="${esc(item.id)}" type="button">${item.is_available ? "Disable" : "Enable"}</button>
        </td>
      </tr>`).join("") : '<tr><td colspan="5">No menu items yet.</td></tr>';
  }

  function parseDiet(answer) {
    const value = String(answer || "").trim().toLowerCase();
    if (value === "veg") return true;
    if (value === "nonveg" || value === "non-veg") return false;
    return null;
  }

  async function load() {
    try {
      const response = await trayApi.get("/admin/menu");
      items = response.items || [];
      render();
    } catch (error) {
      status.textContent = describeError(error);
    }
  }

  async function save(request, successMessage) {
    status.textContent = "";
    try {
      await request();
      await load();
      trayNotify(successMessage);
    } catch (error) {
      status.textContent = describeError(error);
    }
  }

  content.addEventListener("click", (event) => {
    const add = event.target.closest("#add-item");
    const edit = event.target.closest("[data-edit]");
    const toggle = event.target.closest("[data-toggle]");

    if (add) {
      const name = prompt("Item name");
      if (!name) return;
      const price = Number(prompt("Price in INR", "100"));
      if (!Number.isFinite(price) || price < 0) { status.textContent = "Enter a price of zero or more."; return; }
      const category = prompt("Category", "Snacks") || "Meals";
      const diet = prompt("Diet: veg, nonveg, or leave blank if not recorded", "");
      save(() => trayApi.post("/admin/menu", {
        name: name.trim(),
        category: category.trim(),
        price_paise: Math.round(price * 100),
        is_veg: parseDiet(diet),
        is_available: true
      }), "Menu item added");
      return;
    }

    if (edit) {
      const item = items.find((entry) => entry.id === Number(edit.dataset.edit));
      if (!item) return;
      const name = prompt("Item name", item.name);
      if (name === null) return;
      const price = Number(prompt("Price in INR", String(item.price_paise / 100)));
      if (!Number.isFinite(price) || price < 0) { status.textContent = "Enter a price of zero or more."; return; }
      const category = prompt("Category", item.category);
      if (category === null) return;
      const dietAnswer = prompt("Diet: veg, nonveg, or leave blank if not recorded", item.is_veg === true ? "veg" : item.is_veg === false ? "nonveg" : "");
      if (dietAnswer === null) return;
      save(() => trayApi.patch(`/admin/menu/${item.id}`, {
        name: name.trim(),
        category: category.trim(),
        price_paise: Math.round(price * 100),
        is_veg: parseDiet(dietAnswer)
      }), "Menu item updated");
      return;
    }

    if (toggle) {
      const item = items.find((entry) => entry.id === Number(toggle.dataset.toggle));
      if (!item) return;
      save(() => trayApi.patch(`/admin/menu/${item.id}`, { is_available: !item.is_available }),
        item.is_available ? "Item disabled" : "Item enabled");
    }
  });

  load();
})();
