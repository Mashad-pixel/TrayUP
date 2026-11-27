(function () {
  "use strict";

  const content = document.querySelector(".admin-content");
  const ui = window.trayUI;
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;"
  })[character]);

  content.innerHTML = `<div style="display:flex;justify-content:space-between;align-items:center"><h1 class="admin-title">Menu items</h1><button class="btn btn-primary" id="add-item" type="button">Add item</button></div><p id="menu-status" role="status" style="margin-top:12px;color:var(--muted)"></p><div id="item-form-container"></div><div class="card table-card" style="margin-top:22px"><table class="data-table"><thead><tr><th>Item</th><th>Category</th><th>Price</th><th>Availability</th><th>Actions</th></tr></thead><tbody id="menu-body"></tbody></table></div>`;

  const body = document.getElementById("menu-body");
  const status = document.getElementById("menu-status");
  const formContainer = document.getElementById("item-form-container");
  let items = [];
  let categories = [];
  let formErrors = {};

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
        <td><strong>${escapeHtml(item.name)}</strong><br><small style="color:var(--muted)">${escapeHtml(dietLabel(item.is_veg))}</small></td>
        <td>${escapeHtml(item.category)}</td>
        <td>${rupees(item.price_paise)}</td>
        <td><span class="status ${item.is_available ? "" : "danger"}">${item.is_available ? "Available" : "Hidden from students"}</span></td>
        <td>
          <button class="btn btn-secondary" data-edit="${escapeHtml(item.id)}" type="button">Edit</button>
          <button class="btn btn-secondary" data-toggle="${escapeHtml(item.id)}" type="button">${item.is_available ? "Disable" : "Enable"}</button>
        </td>
      </tr>`).join("") : '<tr><td colspan="5">No menu items yet.</td></tr>';
  }

  function field(label, input, key) {
    const wrapper = ui.el("label", { class: "ui-field" }, [label, input]);
    if (formErrors[key]) wrapper.appendChild(ui.el("span", { class: "ui-error", text: formErrors[key] }));
    return wrapper;
  }

  function addForm() {
    const name = ui.el("input", { name: "name", required: true, maxlength: 120 });
    const category = ui.el("select", { name: "category", required: true }, [
      ui.el("option", { value: "", text: "Choose a category" }),
      ...categories.map((entry) => ui.el("option", { value: entry.name, text: entry.name }))
    ]);
    const price = ui.el("input", { name: "price", type: "text", inputmode: "decimal", required: true, placeholder: "e.g. 75.50" });
    const form = ui.el("form", { id: "item-form", class: "card", style: "padding:18px;margin-top:18px" }, [
      ui.el("h2", { style: "font-size:18px;margin:0 0 12px", text: "Add a menu item" }),
      ui.el("div", { class: "ui-form" }, [
        field("Item name", name, "name"),
        field("Category", category, "category"),
        field("Price (₹)", price, "price")
      ]),
      formErrors.body ? ui.el("p", { class: "ui-error", role: "alert", text: formErrors.body }) : null,
      ui.el("div", { class: "ui-row-actions", style: "margin-top:14px" }, [
        ui.el("button", { class: "btn btn-primary", type: "submit", text: "Save item" }),
        ui.el("button", { class: "btn btn-secondary", type: "button", id: "cancel-item", text: "Cancel" })
      ])
    ]);
    return form;
  }

  function parseDiet(answer) {
    const value = String(answer || "").trim().toLowerCase();
    if (value === "veg") return true;
    if (value === "nonveg" || value === "non-veg") return false;
    return null;
  }

  async function load() {
    try {
      const [menuResponse, categoryResponse] = await Promise.all([
        trayApi.get("/admin/menu"),
        trayApi.get("/admin/categories")
      ]);
      items = menuResponse.items || menuResponse.data?.items || [];
      categories = categoryResponse.categories || categoryResponse.data?.categories || [];
      render();
    } catch (error) {
      status.textContent = ui.describeError(error).text;
    }
  }

  async function save(request, successMessage) {
    status.textContent = "";
    try {
      await request();
      formErrors = {};
      formContainer.replaceChildren();
      await load();
      trayNotify(successMessage);
    } catch (error) {
      formErrors = ui.fieldErrors(error);
      if (!Object.keys(formErrors).length) formErrors = { body: ui.describeError(error).text };
      formContainer.replaceChildren(addForm());
    }
  }

  content.addEventListener("click", (event) => {
    const add = event.target.closest("#add-item");
    const cancel = event.target.closest("#cancel-item");
    const edit = event.target.closest("[data-edit]");
    const toggle = event.target.closest("[data-toggle]");

    if (add) {
      formErrors = {};
      formContainer.replaceChildren(addForm());
      formContainer.querySelector('input[name="name"]').focus();
      return;
    }
    if (cancel) {
      formContainer.replaceChildren();
      return;
    }

    if (edit) {
      const item = items.find((entry) => String(entry.id) === edit.dataset.edit);
      if (!item) return;
      const name = prompt("Item name", item.name);
      if (name === null) return;
      const price = ui.rupeesToPaise(prompt("Price in INR", String(item.price_paise / 100)));
      if (price === null) { status.textContent = "Enter a valid price."; return; }
      const categoryName = prompt("Category", item.category);
      if (categoryName === null) return;
      const dietAnswer = prompt("Diet: veg, nonveg, or leave blank if not recorded", item.is_veg === true ? "veg" : item.is_veg === false ? "nonveg" : "");
      if (dietAnswer === null) return;
      save(() => trayApi.patch(`/admin/menu/${item.id}`, {
        name: name.trim(), category: categoryName.trim(), price_paise: price, is_veg: parseDiet(dietAnswer)
      }), "Menu item updated");
      return;
    }

    if (toggle) {
      const item = items.find((entry) => String(entry.id) === toggle.dataset.toggle);
      if (item) {
        save(() => trayApi.patch(`/admin/menu/${item.id}`, { is_available: !item.is_available }),
          item.is_available ? "Item disabled" : "Item enabled");
      }
    }
  });

  content.addEventListener("submit", (event) => {
    if (event.target.id !== "item-form") return;
    event.preventDefault();
    formErrors = {};
    const data = new FormData(event.target);
    const name = String(data.get("name") || "").trim();
    const category = String(data.get("category") || "").trim();
    const price = ui.rupeesToPaise(data.get("price"));
    if (!name) formErrors.name = "Enter an item name.";
    if (!category) formErrors.category = "Choose a category.";
    if (price === null || price < 0) formErrors.price = "Enter an amount such as 75.";
    if (Object.keys(formErrors).length) {
      formContainer.replaceChildren(addForm());
      return;
    }
    save(() => trayApi.post("/admin/menu", {
      name, category, price_paise: price, stock_quantity: null, is_veg: null, is_available: true
    }), "Menu item added");
  });

  load();
})();
