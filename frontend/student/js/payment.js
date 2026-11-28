(function () {
  window.trayPayment = {
    getMethods: () => trayApi.get("/payments/methods"),
    initiateUpi: (orderId) => trayApi.post("/payments/upi/initiate", { order_id: orderId }),
    submitUpiClaim: (orderId, utrNumber) => {
      const body = { order_id: orderId };
      if (utrNumber) body.utr_number = utrNumber;
      return trayApi.post("/payments/upi/submit-claim", body);
    },
    completeSandbox: (orderId) => trayApi.post("/payments/sandbox/complete", { order_id: orderId })
  };
})();
