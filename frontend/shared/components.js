(function () {
  window.trayComponents = {
    header(active = "") {
      return `
        <header class="top-strip">
          <div class="container nav-main">
            <a class="brand" href="/index.html" aria-label="trayUP home">
              <span class="brand-mark"></span><span>trayUP</span>
            </a>
            <form class="search" role="search">
              <input type="search" placeholder="Search food, meals & snacks" aria-label="Search menu">
              <button type="submit" aria-label="Search">⌕</button>
            </form>
            <nav class="nav-actions" aria-label="Account navigation">
              <a class="primary" href="/kitchen/login.html">KITCHEN</a>
              <a class="sign-link" href="/admin/login.html">ADMIN</a>
              <a class="sign-link" href="/student/cart.html" aria-label="View cart">CART</a>
              <button class="cart-btn" id="open-cart" type="button" aria-label="Open cart">🛒
                <span class="cart-count" id="cart-count">0</span>
              </button>
            </nav>
          </div>
          <nav class="category-nav" aria-label="Main navigation">
            ${["All","Breakfast","Lunch","Snacks","Drinks","Popular","My Orders"].map((item) =>
              `<a class="${active === item ? "active" : ""}" data-nav-category="${item}" href="${item === "My Orders" ? "/student/tracking.html" : "/index.html"}">${item}</a>`
            ).join("")}
          </nav>
        </header>`;
    }
  };
})();
