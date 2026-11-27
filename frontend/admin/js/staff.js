// Staff accounts from the server. Administrators can create ADMIN and KITCHEN accounts, change roles,
// activate or deactivate them, and set a new password. Nothing here is stored in the browser.
(function () {
  "use strict";

  const content = document.querySelector(".admin-content");
  let staff = [];
  let me = null;
  let addOpen = false;
  let passwordFor = null;   // id of the row showing the "set password" form
  let busy = false;
  let notice = null;

  function el(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  }

  function errorText(error) {
    if (error && typeof error.status !== "number") return "Could not reach the server. Nothing was changed.";
    return (error && error.message) || "Something went wrong. Nothing was changed.";
  }

  function roleLabel(role) {
    return role === "ADMIN" ? "Administrator" : "Kitchen";
  }

  function roleSelect(member) {
    const select = el("select");
    select.dataset.role = String(member.id);
    select.setAttribute("aria-label", `Role for ${member.name}`);
    select.disabled = busy || (me && me.id === member.id);
    [["KITCHEN", "Kitchen"], ["ADMIN", "Administrator"]].forEach(([value, label]) => {
      const option = el("option", label);
      option.value = value;
      option.selected = member.role === value;
      select.appendChild(option);
    });
    return select;
  }

  function actionButton(label, dataset, disabled) {
    const button = el("button", label, "btn btn-secondary");
    button.type = "button";
    Object.assign(button.dataset, dataset);
    button.disabled = busy || disabled;
    return button;
  }

  function staffRow(member) {
    const isMe = me && me.id === member.id;
    const actions = el("div", undefined, undefined);
    actions.className = "ui-row-actions";
    actions.style.cssText = "display:flex;gap:8px;flex-wrap:wrap";
    actions.appendChild(actionButton(member.is_active ? "Deactivate" : "Activate", { toggle: String(member.id) }, isMe));
    actions.appendChild(actionButton("Set password", { password: String(member.id) }, isMe));

    const cells = [
      el("td", undefined),
      el("td", member.email),
      el("td", undefined),
      el("td", undefined),
      el("td", undefined)
    ];
    cells[0].appendChild(el("strong", member.name));
    if (isMe) cells[0].appendChild(el("span", " (you)", "ui-muted"));
    cells[2].appendChild(roleSelect(member));
    cells[3].appendChild(el("span", member.is_active ? "Active" : "Deactivated",
      member.is_active ? "status" : "status danger"));
    cells[4].appendChild(actions);

    const rows = [el("tr", undefined, undefined)];
    cells.forEach((cell) => rows[0].appendChild(cell));
    if (passwordFor === member.id) rows.push(passwordRow(member));
    return rows;
  }

  function field(label, input, hint) {
    const wrap = el("label", undefined, "field");
    wrap.style.cssText = "display:grid;gap:4px";
    wrap.appendChild(el("span", label));
    wrap.appendChild(input);
    if (hint) wrap.appendChild(el("span", hint, "hint"));
    return wrap;
  }

  function addForm() {
    const form = el("form");
    form.id = "staff-form";
    form.className = "card";
    form.style.cssText = "margin-top:22px;padding:22px;max-width:760px";
    const name = el("input"); name.name = "name"; name.required = true; name.maxLength = 100; name.autocomplete = "off";
    const email = el("input"); email.name = "email"; email.type = "email"; email.required = true; email.maxLength = 120; email.autocomplete = "off";
    const password = el("input"); password.name = "password"; password.type = "password"; password.required = true;
    password.minLength = 8; password.maxLength = 128; password.autocomplete = "new-password";
    const role = el("select"); role.name = "role";
    [["KITCHEN", "Kitchen"], ["ADMIN", "Administrator"]].forEach(([value, label]) => {
      const option = el("option", label); option.value = value; role.appendChild(option);
    });
    const grid = el("div", undefined, undefined);
    grid.style.cssText = "display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px";
    grid.append(
      field("Name", name),
      field("Email (login)", email),
      field("Temporary password", password, "8–128 characters, with a letter and a number. Share it securely; they can change it later."),
      field("Role", role)
    );
    form.appendChild(el("h2", "Add a staff account"));
    form.appendChild(grid);
    const actions = el("div", undefined, undefined);
    actions.style.cssText = "display:flex;gap:8px;margin-top:14px";
    const save = el("button", busy ? "Creating…" : "Create account", "btn btn-primary");
    save.type = "submit";
    save.disabled = busy;
    const cancel = el("button", "Cancel", "btn btn-secondary");
    cancel.type = "button";
    cancel.id = "cancel-add";
    actions.append(save, cancel);
    form.appendChild(actions);
    return form;
  }

  function passwordRow(member) {
    const row = el("tr", undefined, undefined);
    const cell = el("td", undefined, undefined);
    cell.colSpan = 5;
    const form = el("form");
    form.dataset.password = String(member.id);
    form.style.cssText = "display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:8px 0";
    const input = el("input");
    input.type = "password";
    input.name = "password";
    input.required = true;
    input.minLength = 8;
    input.maxLength = 128;
    input.autocomplete = "new-password";
    input.placeholder = `New password for ${member.name}`;
    input.style.cssText = "height:36px;padding:6px 8px;border:1px solid var(--line);border-radius:6px";
    const save = el("button", "Save password", "btn btn-primary");
    save.type = "submit";
    save.disabled = busy;
    const cancel = el("button", "Cancel", "btn btn-secondary");
    cancel.type = "button";
    cancel.dataset.cancelPassword = "1";
    form.append(input, save, cancel, el("span", "This signs them out everywhere.", "ui-muted"));
    cell.appendChild(form);
    row.appendChild(cell);
    return row;
  }

  function render() {
    const body = el("tbody", undefined, undefined);
    body.id = "staff-body";
    if (!staff.length) {
      const empty = el("tr", undefined, undefined);
      const cell = el("td", "No staff accounts yet.", "ui-muted");
      cell.colSpan = 5;
      empty.appendChild(cell);
      body.appendChild(empty);
    } else {
      staff.forEach((member) => staffRow(member).forEach((row) => body.appendChild(row)));
    }

    const header = el("div", undefined, undefined);
    header.style.cssText = "display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap";
    const add = el("button", addOpen ? "Close" : "Add staff", "btn btn-primary");
    add.type = "button";
    add.id = "add-staff";
    add.disabled = busy;
    header.append(el("h1", "Staff accounts", "admin-title"), add);

    const table = el("div", undefined, "card table-card");
    table.style.marginTop = "22px";
    const thead = el("thead", undefined, undefined);
    const headRow = el("tr", undefined, undefined);
    ["Name", "Login email", "Role", "Status", "Actions"].forEach((label) => headRow.appendChild(el("th", label)));
    thead.appendChild(headRow);
    const bodyTable = el("table", undefined, "data-table");
    bodyTable.append(thead, body);
    table.appendChild(bodyTable);

    content.replaceChildren(
      header,
      el("p", "Kitchen staff can handle orders and collections. Administrators can also manage the menu, staff and reports. Administrators must set up two-factor sign-in before they can open admin pages.", "ui-muted"),
      ...(notice ? [notice] : []),
      ...(addOpen ? [addForm()] : []),
      table
    );
  }

  function say(text, tone) {
    notice = el("div", text, tone === "danger" ? "card status danger" : "card status");
    notice.style.cssText = "margin:14px 0;padding:12px 16px";
    render();
    setTimeout(() => { notice = null; render(); }, 5000);
  }

  async function reload() {
    const [list, who] = await Promise.all([trayApi.get("/admin/staff"), trayAuth.currentUser()]);
    staff = (list.data && list.data.staff) || [];
    me = who.data || null;
    render();
  }

  async function run(action, success) {
    if (busy) return;
    busy = true;
    render();
    try {
      await action();
      busy = false;
      say(success, "ok");
      await reload();
    } catch (error) {
      busy = false;
      say(errorText(error), "danger");
      try { await reload(); } catch (_) {}
    }
  }

  function addStaff(form) {
    const data = new FormData(form);
    const body = {
      name: String(data.get("name") || "").trim(),
      email: String(data.get("email") || "").trim(),
      password: String(data.get("password") || ""),
      role: String(data.get("role") || "KITCHEN")
    };
    run(async () => {
      const created = await trayApi.post("/admin/staff", body);
      addOpen = false;
      return created;
    }, "Staff account created. They must sign in with the temporary password.");
  }

  content.addEventListener("click", (event) => {
    const add = event.target.closest("#add-staff");
    const cancelAdd = event.target.closest("#cancel-add");
    const toggle = event.target.closest("[data-toggle]");
    const password = event.target.closest("[data-password]");
    const cancelPassword = event.target.closest("[data-cancel-password]");
    if (add) {
      addOpen = !addOpen;
      render();
    } else if (cancelAdd) {
      addOpen = false;
      render();
    } else if (toggle && !toggle.disabled) {
      const member = staff.find((m) => String(m.id) === toggle.dataset.toggle);
      if (member) {
        run(() => trayApi.patch(`/admin/staff/${member.id}`, { is_active: !member.is_active }),
          member.is_active ? `${member.name} has been deactivated and signed out.` : `${member.name} can sign in again.`);
      }
    } else if (password && !password.disabled) {
      passwordFor = Number(password.dataset.password);
      render();
    } else if (cancelPassword) {
      passwordFor = null;
      render();
    }
  });

  content.addEventListener("change", (event) => {
    const select = event.target;
    if (select.dataset && select.dataset.role) {
      const member = staff.find((m) => String(m.id) === select.dataset.role);
      if (member && select.value !== member.role) {
        run(() => trayApi.patch(`/admin/staff/${member.id}`, { role: select.value }),
          `${member.name} is now ${roleLabel(select.value)}. Their current sessions have ended.`);
      }
    }
  });

  content.addEventListener("submit", (event) => {
    event.preventDefault();
    const form = event.target;
    if (form.id === "staff-form") {
      addStaff(form);
    } else if (form.dataset.password) {
      const member = staff.find((m) => String(m.id) === form.dataset.password);
      const password = String(new FormData(form).get("password") || "");
      if (member) {
        run(async () => {
          await trayApi.patch(`/admin/staff/${member.id}`, { password });
          passwordFor = null;
        }, `Password updated for ${member.name}. They have been signed out everywhere.`);
      }
    }
  });

  reload().catch((error) => {
    content.replaceChildren(el("h1", "Staff accounts", "admin-title"), el("div", errorText(error), "card status danger"));
  });
})();
