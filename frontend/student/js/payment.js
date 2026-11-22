(function () {
  window.trayPayment = {
    openOptions: async function (orderId) {
      const response = await trayApi.post("/payments/create-order", { order_id: orderId });
      if (!window.Razorpay) {
        throw new Error("Razorpay Checkout is not loaded");
      }
      return new window.Razorpay(response.data);
    }
  };
})();
