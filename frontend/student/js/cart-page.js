document.getElementById("app-header").innerHTML = trayComponents.header();

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;"
  })[character]);
}

function renderCart() {
  const cart = trayStorage.getCart();
  const total = cart.reduce((sum, item) => sum + item.price * item.qty, 0);
  const count = document.getElementById("cart-count");
  if (count) count.textContent = cart.reduce((sum, item) => sum + item.qty, 0);
  document.getElementById("cart-total").textContent = "₹" + total.toLocaleString("en-IN");
  document.getElementById("cart-list").innerHTML = cart.length ? cart.map((item) => {
    const id = escapeHtml(item.id);
    return `
      <div class="cart-item" style="background:#fff;padding:12px;border:1px solid var(--line);margin-bottom:8px;border-radius:10px">
        <img src="${escapeHtml(item.image)}" alt="">
        <div><strong>${escapeHtml(item.name)}</strong><span style="display:block;color:var(--muted);font-size:13px;margin:4px 0">₹${escapeHtml(item.price)} each</span>
          <div class="qty-control"><button type="button" data-delta="-1" data-id="${id}">−</button><span>${escapeHtml(item.qty)}</span><button type="button" data-delta="1" data-id="${id}">+</button></div>
        </div>
        <div style="text-align:right"><strong>₹${escapeHtml(item.price * item.qty)}</strong><button type="button" data-remove="${id}" style="display:block;border:0;background:none;color:var(--danger);font-size:12px;margin:8px 0 0 auto;cursor:pointer">Remove</button></div>
      </div>`;
  }).join("") : '<div class="empty-state"><h3>Your cart is empty</h3><p><a href="../index.html" style="text-decoration:underline">Return to the menu</a></p></div>';
}

function saveCartOrWarn(cart) {
  if (trayStorage.set("trayup-cart", cart)) return true;
  trayNotify("Your browser blocked cart storage. Enable site storage and try again.");
  renderCart();
  return false;
}

document.getElementById("cart-list").addEventListener("click", (event) => {
  const cart = trayStorage.getCart();
  const qtyButton = event.target.closest("[data-delta]");
  const removeButton = event.target.closest("[data-remove]");
  if (qtyButton) {
    const item = cart.find((entry) => entry.id === Number(qtyButton.dataset.id));
    if (!item) return;
    item.qty += Number(qtyButton.dataset.delta);
    saveCartOrWarn(cart.filter((entry) => entry.qty > 0));
  }
  if (removeButton) {
    const saved = saveCartOrWarn(cart.filter((entry) => entry.id !== Number(removeButton.dataset.remove)));
    if (saved) trayNotify("Item removed");
  }
});

document.getElementById("clear-cart").addEventListener("click", () => {
  if (trayStorage.remove("trayup-cart")) trayNotify("Cart cleared");
  else trayNotify("Your browser blocked cart storage. The cart could not be cleared.");
  renderCart();
});

renderCart();
