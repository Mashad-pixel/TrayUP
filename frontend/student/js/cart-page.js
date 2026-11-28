(function () {
  document.getElementById("app-header").innerHTML = trayComponents.header();

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (character) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;"
    }[character]));
  }

  const cartList = document.getElementById("cart-list");
  cartList.addEventListener("error", (event) => {
    const img = event.target;
    if (img instanceof HTMLImageElement) {
      img.style.display = "none";
      img.parentElement?.classList.add("cart-item-image-fallback");
    }
  }, true);

  function renderCart() {
    const cart = trayStorage.get("trayup-cart", []);
    const total = cart.reduce((n, i) => n + i.price * i.qty, 0);
    const cartCount = document.getElementById("cart-count");
    if (cartCount) cartCount.textContent = cart.reduce((sum, item) => sum + Number(item.qty || 0), 0);
    document.getElementById("cart-total").textContent = "₹" + total.toLocaleString("en-IN");
    document.getElementById("cart-foot").hidden = !cart.length;
    cartList.innerHTML = cart.length ? cart.map((i) => `
 <article class="cart-page-item">
   <img src="${escapeHtml(i.image || "")}" alt="" loading="lazy">
   <div class="cart-page-item-info"><strong>${escapeHtml(i.name)}</strong><span class="cart-page-unit-price">₹${Number(i.price).toLocaleString("en-IN")} each</span>
     <div class="qty-control">
       <button type="button" data-delta="-1" data-id="${Number(i.id)}" aria-label="Remove one ${escapeHtml(i.name)}">−</button>
       <span aria-live="polite">${Number(i.qty) || 0}</span>
       <button type="button" data-delta="1" data-id="${Number(i.id)}" aria-label="Add one ${escapeHtml(i.name)}">+</button>
     </div>
   </div>
   <div class="cart-page-line-total"><strong>₹${(Number(i.price) * Number(i.qty)).toLocaleString("en-IN")}</strong><button type="button" data-remove="${Number(i.id)}">Remove</button></div>
 </article>`).join("") : `<div class="empty-state cart-empty-state"><span class="cart-empty-icon" aria-hidden="true">＋</span><h2>Your cart is empty</h2><p>Choose something fresh from the menu to get started.</p><a class="btn btn-primary" href="../index.html">Browse the menu</a></div>`;
  }

  cartList.addEventListener("click", (e) => {
    const cart = trayStorage.get("trayup-cart", []);
    const qtyButton = e.target.closest("[data-delta]");
    const removeButton = e.target.closest("[data-remove]");
    if (qtyButton) {
      const item = cart.find((i) => i.id === Number(qtyButton.dataset.id));
      if (item) {
        item.qty += Number(qtyButton.dataset.delta);
        trayStorage.set("trayup-cart", cart.filter((i) => i.qty > 0));
        renderCart();
      }
    }
    if (removeButton) {
      trayStorage.set("trayup-cart", cart.filter((i) => i.id !== Number(removeButton.dataset.remove)));
      trayNotify("Item removed");
      renderCart();
    }
  });

  document.getElementById("clear-cart").addEventListener("click", () => {
    trayStorage.remove("trayup-cart");
    trayNotify("Cart cleared");
    renderCart();
  });

  renderCart();
})();
