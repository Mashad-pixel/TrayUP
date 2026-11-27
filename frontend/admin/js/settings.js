// Canteen settings are persisted on the server. The ordering switch controls order acceptance;
// the opening and closing times are reference information and do not automatically close ordering.
(function () {
  "use strict";

  const ui = window.trayUI;
  const root = document.querySelector(".admin-content");

  let settings = null;
  let account = null;
  let formErrors = {};
  let statusErrors = {};
  let notice = null;

  function detailsForm() {
    const field = (label, input, key, hint) => ui.el("label", { class: "ui-field" }, [
      label, input, hint ? ui.el("span", { class: "ui-hint", text: hint }) : null,
      formErrors[key] ? ui.el("span", { class: "ui-error", text: formErrors[key] }) : null
    ]);
    return ui.el("form", { id: "details-form", class: "card", style: "padding:18px;margin-top:18px;max-width:720px" }, [
      ui.el("h2", { style: "font-size:18px;margin:0 0 12px", text: "Name and hours" }),
      ui.el("div", { class: "ui-form" }, [
        field("Canteen name", ui.el("input", { name: "canteen_name", required: true, maxlength: 120, value: settings.canteen_name }), "canteen_name"),
        field("Opens", ui.el("input", { name: "opens_at", type: "time", required: true, value: settings.opens_at }), "opens_at"),
        field("Closes", ui.el("input", { name: "closes_at", type: "time", required: true, value: settings.closes_at }), "closes_at", "Closing time must be after opening time."),
      ]),
      formErrors.unknown_fields || formErrors.body ? ui.el("div", { class: "ui-error", style: "margin-top:8px", text: formErrors.unknown_fields || formErrors.body }) : null,
      ui.el("div", { style: "margin-top:14px" }, [ui.el("button", { class: "btn btn-primary", type: "submit", text: "Save name and hours" })])
    ]);
  }

  function statusCard() {
    const open = settings.is_accepting_orders;
    const message = ui.el("input", { name: "closed_message", maxlength: 200, value: settings.closed_message || "", placeholder: "Shown to students when ordering is closed, e.g. Closed for exams" });
    return ui.el("form", { id: "status-form", class: "card", style: "padding:18px;margin-top:18px;max-width:720px" }, [
      ui.el("h2", { style: "font-size:18px;margin:0 0 8px", text: "Ordering" }),
      ui.el("p", { class: "ui-muted", text: open ? "Students can place orders right now." : "Students cannot place orders right now." }),
      ui.el("label", { class: "ui-field" }, ["Message when closed", message, statusErrors.closed_message ? ui.el("span", { class: "ui-error", text: statusErrors.closed_message }) : null]),
      ui.el("div", { class: "ui-row-actions", style: "margin-top:14px" }, [
        ui.el("button", { class: "btn btn-primary", type: "submit", name: "is_accepting_orders", value: open ? "false" : "true", text: open ? "Stop taking orders" : "Start taking orders" })
      ]),
      statusErrors.body ? ui.el("div", { class: "ui-error", style: "margin-top:8px", text: statusErrors.body }) : null
    ]);
  }

  function accountCard() {
    return ui.el("section", { class: "card", style: "padding:18px;margin-top:18px;max-width:720px" }, [
      ui.el("h2", { style: "font-size:18px;margin:0 0 8px", text: "Account security" }),
      ui.el("p", { class: "ui-muted", text: `Signed in as ${account.name} (${account.email})` }),
      ui.el("form", { id: "email-form", class: "ui-form" }, [
        ui.el("label", { class: "ui-field" }, ["New email", ui.el("input", { name: "new_email", type: "email", required: true })]),
        ui.el("label", { class: "ui-field" }, ["Current password", ui.el("input", { name: "current_password", type: "password", required: true, autocomplete: "current-password" })]),
        ui.el("button", { class: "btn btn-secondary", type: "submit", text: "Change email" })
      ]),
      ui.el("form", { id: "password-form", class: "ui-form", style: "margin-top:12px" }, [
        ui.el("label", { class: "ui-field" }, ["Current password", ui.el("input", { name: "current_password", type: "password", required: true, autocomplete: "current-password" })]),
        ui.el("label", { class: "ui-field" }, ["New password", ui.el("input", { name: "new_password", type: "password", required: true, autocomplete: "new-password" })]),
        ui.el("button", { class: "btn btn-secondary", type: "submit", text: "Change password" })
      ]),
      ui.el("div", { class: "ui-row-actions", style: "margin-top:12px" }, [
        ui.el("button", { class: "btn btn-secondary", id: "revoke-sessions", type: "button", text: "Sign out other sessions" })
      ])
    ]);
  }

  function render() {
    root.replaceChildren(
      ui.header("Canteen settings"),
      ui.el("p", { class: "ui-muted", style: "margin-top:10px", text: "Opening hours are saved as reference information. Use the ordering switch to control whether students can place orders." }),
      notice,
      detailsForm(),
      statusCard(),
      account ? accountCard() : null
    );
  }

  function say(text, tone) {
    notice = ui.notice(text, tone);
    render();
    setTimeout(() => { notice = null; }, 5000);
  }

  async function load() {
    try {
      [settings, account] = await Promise.all([
        trayApi.get("/admin/canteen/settings"),
        trayApi.get("/account").then((response) => response.data)
      ]);
      render();
    } catch (error) {
      root.replaceChildren(ui.header("Canteen settings"), ui.errorNotice(error));
    }
  }

  async function saveDetails(form) {
    formErrors = {};
    const data = new FormData(form);
    try {
      settings = await trayApi.patch("/admin/canteen/settings", {
        canteen_name: String(data.get("canteen_name") || ""),
        opens_at: String(data.get("opens_at") || ""),
        closes_at: String(data.get("closes_at") || "")
      });
      say("Name and hours saved", "ok");
    } catch (error) {
      formErrors = ui.fieldErrors(error);
      if (!Object.keys(formErrors).length) formErrors = { body: ui.describeError(error).text };
      render();
    }
  }

  async function saveStatus(form, submitter) {
    statusErrors = {};
    const wantOpen = submitter.value === "true";
    const body = { is_accepting_orders: wantOpen };
    const message = String(new FormData(form).get("closed_message") || "").trim();
    if (!wantOpen) body.closed_message = message || null;
    try {
      await trayApi.patch("/admin/canteen/status", body);
      // The status endpoint returns only the ordering fields, so reload the full settings.
      settings = await trayApi.get("/admin/canteen/settings");
      say(wantOpen ? "Students can order again." : "Ordering is closed for students.", "ok");
    } catch (error) {
      statusErrors = ui.fieldErrors(error);
      if (!Object.keys(statusErrors).length) statusErrors = { body: ui.describeError(error).text };
      render();
    }
  }

  root.addEventListener("submit", (event) => {
    event.preventDefault();
    if (event.target.id === "details-form") saveDetails(event.target);
    else if (event.target.id === "status-form") saveStatus(event.target, event.submitter || event.target.querySelector("button[type=submit]"));
    else if (event.target.id === "email-form") saveAccountChange(event.target, "/account/email", "Email address changed.");
    else if (event.target.id === "password-form") saveAccountChange(event.target, "/account/password", "Password changed.");
  });

  async function saveAccountChange(form, path, message) {
    const data = Object.fromEntries(new FormData(form));
    try {
      await trayApi.post(path, data);
      form.reset();
      account = (await trayApi.get("/account")).data;
      say(message, "ok");
    } catch (error) {
      formErrors = ui.fieldErrors(error);
      if (!Object.keys(formErrors).length) formErrors = { body: ui.describeError(error).text };
      render();
    }
  }

  root.addEventListener("click", async (event) => {
    if (event.target.id !== "revoke-sessions") return;
    event.target.disabled = true;
    try {
      const response = await trayApi.post("/account/sessions/revoke-others", {});
      say(`${response.data.revoked} other session(s) signed out.`, "ok");
    } catch (error) {
      statusErrors = { body: ui.describeError(error).text };
      render();
    }
  });

  load();
})();
