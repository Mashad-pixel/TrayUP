// Refunds. Lists every payment with what has been paid back, what is pending, and what can still be
// refunded. A refund is sent to Razorpay by the server. It shows as pending until Razorpay confirms it.
(function () {
  "use strict";

  const ui = window.trayUI;
  const root = document.querySelector(".admin-content");
  const PAYMENT_LABEL = {
    created: "Not paid",
    paid: "Paid",
    refund_required: "Refund required",
    partially_refunded: "Partly refunded",
    refunded: "Refunded"
  };
  const REFUND_LABEL = { pending: "Pending", processed: "Processed", failed: "Failed" };

  let payments = [];
  let refunds = [];
  let openFor = null;     // payment_id whose refund form is open
  let formError = null;
  let busy = false;
  let notice = null;

  function paymentRow(p) {
    const actions = p.refundable_paise > 0
      ? ui.el("button", { class: "btn btn-secondary", type: "button", dataset: { refund: String(p.payment_id) }, disabled: busy, text: "Refund…" })
      : ui.el("span", { class: "ui-muted", text: "Nothing to refund" });
    const cells = [
      ui.el("td", null, [
        ui.el("strong", { text: p.order_number || "—" }),
        ui.el("div", { class: "ui-muted", style: "font-size:13px", text: `Payment ${p.payment_id}` })
      ]),
      ui.el("td", { class: "ui-num", text: ui.money(p.amount_paise) }),
      ui.el("td", { class: "ui-num", text: ui.money(p.refunded_paise) }),
      ui.el("td", { class: "ui-num", text: ui.money(p.pending_refund_paise) }),
      ui.el("td", { class: "ui-num", text: ui.money(p.refundable_paise) }),
      ui.el("td", { text: PAYMENT_LABEL[p.payment_status] || p.payment_status }),
      ui.el("td", null, [actions])
    ];
    const rows = [ui.el("tr", null, cells)];
    if (openFor === p.payment_id) rows.push(refundForm(p));
    return rows;
  }

  function refundForm(p) {
    const amount = ui.el("input", { name: "amount", inputmode: "decimal", value: (p.refundable_paise / 100).toFixed(2), style: "height:36px;width:140px;border:1px solid var(--line);border-radius:6px;padding:6px 8px" });
    const reason = ui.el("textarea", { name: "reason", maxlength: 255, placeholder: "Why is this refund being made?", style: "width:100%;min-height:60px;border:1px solid var(--line);border-radius:6px;padding:8px" });
    const submit = ui.el("button", { class: "btn btn-primary", type: "submit", disabled: busy, text: busy ? "Sending…" : "Issue refund" });
    const cancel = ui.el("button", { class: "btn btn-secondary", type: "button", dataset: { cancel: "1" }, text: "Cancel" });
    const form = ui.el("form", { dataset: { refundFor: String(p.payment_id) }, style: "display:grid;gap:10px;max-width:520px" }, [
      ui.el("label", { class: "ui-field" }, ["Amount (₹). Up to " + ui.money(p.refundable_paise), amount]),
      ui.el("label", { class: "ui-field" }, ["Reason", reason]),
      formError ? ui.el("div", { class: "status danger", text: formError }) : null,
      ui.el("div", { style: "display:flex;gap:8px" }, [submit, cancel])
    ]);
    return ui.el("tr", null, [ui.el("td", { colspan: 7 }, [form])]);
  }

  function refundRow(r) {
    return ui.el("tr", null, [
      ui.el("td", { text: r.order_number || "—" }),
      ui.el("td", { class: "ui-num", text: ui.money(r.amount_paise) }),
      ui.el("td", null, [ui.el("span", { class: r.status === "failed" ? "status danger" : "status", text: REFUND_LABEL[r.status] || r.status })]),
      ui.el("td", { text: r.reason || "" }),
      ui.el("td", { text: ui.formatTime(r.created_at) }),
      ui.el("td", { text: r.processed_at ? ui.formatTime(r.processed_at) : "—" })
    ]);
  }

  function render() {
    const paymentRows = [];
    payments.forEach((p) => paymentRow(p).forEach((row) => paymentRows.push(row)));
    root.replaceChildren(
      ui.header("Refunds"),
      ui.el("p", { class: "ui-muted", style: "margin-top:10px", text: "Refunds go to the customer through Razorpay. A refund shows as pending until Razorpay confirms it, and the amount refundable here drops straight away." }),
      ...(notice ? [notice] : []),
      ui.el("div", { class: "ui-section" }, [
        ui.el("h2", { text: "Payments" }),
        ui.table(
          [{ label: "Order" }, { label: "Paid", numeric: true }, { label: "Refunded", numeric: true }, { label: "Pending", numeric: true }, { label: "Refundable", numeric: true }, { label: "Status" }, { label: "" }],
          paymentRows
        )
      ]),
      ui.el("div", { class: "ui-section" }, [
        ui.el("h2", { text: "Recent refunds" }),
        ui.table(
          [{ label: "Order" }, { label: "Amount", numeric: true }, { label: "Status" }, { label: "Reason" }, { label: "Requested" }, { label: "Processed" }],
          refunds.map(refundRow)
        )
      ])
    );
  }

  function say(text, tone) {
    notice = ui.notice(text, tone);
    render();
    setTimeout(() => { notice = null; render(); }, 6000);
  }

  async function load() {
    try {
      const [paymentList, refundList] = await Promise.all([
        trayApi.get("/admin/payments"),
        trayApi.get("/admin/payments/refunds")
      ]);
      payments = (paymentList.data && paymentList.data.payments) || [];
      refunds = (refundList.data && refundList.data.refunds) || [];
      render();
    } catch (error) {
      root.replaceChildren(ui.header("Refunds"), ui.errorNotice(error));
    }
  }

  async function issueRefund(form) {
    const paymentId = Number(form.dataset.refundFor);
    const payment = payments.find((p) => p.payment_id === paymentId);
    if (!payment) return;

    const data = new FormData(form);
    const paise = ui.rupeesToPaise(data.get("amount"));
    const reason = String(data.get("reason") || "").trim();
    if (paise === null || paise < 1 || paise > payment.refundable_paise) {
      formError = `Enter an amount from ₹0.01 up to ${ui.money(payment.refundable_paise)}.`;
      render();
      return;
    }
    if (!reason) {
      formError = "Enter a reason for the refund.";
      render();
      return;
    }
    if (!window.confirm(`Refund ${ui.money(paise)} for ${payment.order_number}? Razorpay sends the money back to the customer.`)) {
      return;
    }

    busy = true;
    formError = null;
    render();
    try {
      const response = await trayApi.post(`/admin/payments/${paymentId}/refund`, { amount_paise: paise, reason });
      busy = false;
      openFor = null;
      const status = response.data && response.data.status;
      say(status === "processed"
        ? `Refund of ${ui.money(paise)} sent and processed.`
        : `Refund of ${ui.money(paise)} requested. It shows as pending until Razorpay confirms it.`, "ok");
      await load();
    } catch (error) {
      busy = false;
      formError = error.message || ui.describeError(error).text;
      render();
    }
  }

  root.addEventListener("click", (event) => {
    const open = event.target.closest("[data-refund]");
    const cancel = event.target.closest("[data-cancel]");
    if (open && !open.disabled) {
      openFor = Number(open.dataset.refund);
      formError = null;
      render();
    } else if (cancel) {
      openFor = null;
      formError = null;
      render();
    }
  });

  root.addEventListener("submit", (event) => {
    event.preventDefault();
    if (event.target.dataset && event.target.dataset.refundFor) issueRefund(event.target);
  });

  load();
})();
