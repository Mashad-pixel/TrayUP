// Menu categories. Items refer to a category by name, so renaming moves them on the server,
// and a category that still has items cannot be deleted.
(function () {
  "use strict";

  const ui = window.trayUI;
  const root = document.querySelector(".admin-content");
  if (window.trayMode.isDemo()) {
    ui.demoOnly(root, "Categories", "Categories are not loaded in demo mode.");
    return;
  }

  let categories = [];
  let renaming = null;   // id of the row being renamed
  let addErrors = {};
  let rowErrors = {};    // id -> message
  let notice = null;

  function addForm() {
    const name = ui.el("input", { name: "name", required: true, maxlength: 60, placeholder: "e.g. Hot Drinks" });
    const order = ui.el("input", { name: "sort_order", type: "number", min: 0, max: 10000, value: String(nextOrder()) });
    return ui.el("form", { id: "add-form", class: "card", style: "padding:16px;margin-top:18px" }, [
      ui.el("div", { class: "ui-form" }, [
        ui.el("label", { class: "ui-field" }, ["Name", name, addErrors.name ? ui.el("span", { class: "ui-error", text: addErrors.name }) : null]),
        ui.el("label", { class: "ui-field" }, ["Display order", order, ui.el("span", { class: "ui-hint", text: "Lower numbers appear first on the menu." })]),
        ui.el("button", { class: "btn btn-primary", type: "submit", text: "Add category" })
      ]),
      addErrors.unknown_fields ? ui.el("div", { class: "ui-error", text: addErrors.unknown_fields }) : null
    ]);
  }

  function nextOrder() {
    return categories.reduce((max, c) => Math.max(max, c.sort_order), -10) + 10;
  }

  function row(category) {
    const cells = [];
    if (renaming === category.id) {
      cells.push(ui.el("td", null, [
        ui.el("form", { class: "ui-row-actions", dataset: { rename: category.id } }, [
          ui.el("input", { name: "name", value: category.name, maxlength: 60, required: true, style: "height:36px;border:1px solid var(--line);border-radius:6px;padding:6px 8px" }),
          ui.el("button", { class: "btn btn-primary", type: "submit", text: "Save" }),
          ui.el("button", { class: "btn btn-secondary", type: "button", dataset: { cancel: category.id }, text: "Cancel" })
        ]),
        rowErrors[category.id] ? ui.el("div", { class: "ui-error", text: rowErrors[category.id] }) : null
      ]));
    } else {
      cells.push(ui.el("td", { text: category.name }));
    }
    cells.push(ui.el("td", { class: "ui-num", text: String(category.item_count) }));
    cells.push(ui.el("td", null, [
      ui.el("input", { type: "number", min: 0, max: 10000, value: String(category.sort_order), dataset: { order: category.id }, style: "width:90px;height:36px;border:1px solid var(--line);border-radius:6px;padding:6px 8px", "aria-label": `Display order for ${category.name}` })
    ]));
    cells.push(ui.el("td", null, [ui.el("div", { class: "ui-row-actions" }, [
      renaming === category.id ? null : ui.el("button", { class: "btn btn-secondary", type: "button", dataset: { rename: category.id }, text: "Rename" }),
      ui.el("button", {
        class: "btn btn-secondary", type: "button", dataset: { remove: category.id },
        disabled: category.item_count > 0,
        title: category.item_count > 0 ? "Move its items to another category first" : "Delete this category",
        text: "Delete"
      })
    ])]));
    return ui.el("tr", null, cells);
  }

  function render() {
    root.replaceChildren(
      ui.header("Menu categories"),
      ui.el("p", { class: "ui-muted", style: "margin-top:10px", text: "Categories group items on the student menu. Renaming a category moves its items with it. A category with items cannot be deleted until they are moved." }),
      notice,
      addForm(),
      ui.el("div", { class: "card table-card", style: "margin-top:18px;overflow-x:auto" }, [
        ui.el("table", { class: "data-table" }, [
          ui.el("thead", null, [ui.el("tr", null, ["Category", "Items", "Display order", ""].map((t) => ui.el("th", { text: t })))]),
          ui.el("tbody", null, categories.length
            ? categories.map(row)
            : [ui.el("tr", null, [ui.el("td", { colspan: 4, class: "ui-muted", text: "No categories yet." })])])
        ])
      ])
    );
  }

  function say(text, tone) {
    notice = ui.notice(text, tone);
    render();
    setTimeout(() => { notice = null; }, 4000);
  }

  async function reload() {
    try {
      const response = await trayApi.get("/admin/categories");
      categories = response.categories || [];
      render();
    } catch (error) {
      root.replaceChildren(ui.header("Menu categories"), ui.errorNotice(error));
    }
  }

  async function add(form) {
    addErrors = {};
    const data = new FormData(form);
    const body = { name: String(data.get("name") || ""), sort_order: Number(data.get("sort_order") || 0) };
    try {
      await trayApi.post("/admin/categories", body);
      say("Category added", "ok");
      await reload();
    } catch (error) {
      addErrors = ui.fieldErrors(error);
      if (!Object.keys(addErrors).length) addErrors = { unknown_fields: ui.describeError(error).text };
      render();
    }
  }

  async function saveRename(form) {
    const id = Number(form.dataset.rename);
    rowErrors = {};
    try {
      await trayApi.patch(`/admin/categories/${id}`, { name: String(new FormData(form).get("name") || "") });
      renaming = null;
      say("Category renamed. Its items moved with it.", "ok");
      await reload();
    } catch (error) {
      rowErrors[id] = Object.values(ui.fieldErrors(error))[0] || ui.describeError(error).text;
      render();
    }
  }

  async function saveOrder(input) {
    const id = Number(input.dataset.order);
    try {
      await trayApi.patch(`/admin/categories/${id}`, { sort_order: Number(input.value) });
      say("Display order saved", "ok");
      await reload();
    } catch (error) {
      say(Object.values(ui.fieldErrors(error))[0] || ui.describeError(error).text, "danger");
    }
  }

  async function remove(id) {
    const category = categories.find((c) => c.id === id);
    if (!category || !window.confirm(`Delete the category "${category.name}"?`)) return;
    try {
      await trayApi.del(`/admin/categories/${id}`);
      say("Category deleted", "ok");
      await reload();
    } catch (error) {
      say(ui.describeError(error).text, "danger");
    }
  }

  root.addEventListener("click", (event) => {
    const rename = event.target.closest("[data-rename]");
    const cancel = event.target.closest("[data-cancel]");
    const remover = event.target.closest("[data-remove]");
    if (rename && rename.tagName === "BUTTON") {
      renaming = Number(rename.dataset.rename);
      rowErrors = {};
      render();
    } else if (cancel) {
      renaming = null;
      rowErrors = {};
      render();
    } else if (remover) {
      remove(Number(remover.dataset.remove));
    }
  });

  root.addEventListener("submit", (event) => {
    event.preventDefault();
    if (event.target.id === "add-form") add(event.target);
    else if (event.target.dataset.rename) saveRename(event.target);
  });

  root.addEventListener("change", (event) => {
    if (event.target.dataset && event.target.dataset.order) saveOrder(event.target);
  });

  reload();
})();
