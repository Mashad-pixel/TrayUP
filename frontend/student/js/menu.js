(function () {
  const categories = ["All", "Breakfast", "Lunch", "Snacks", "Drinks", "Featured"];

  const header = document.getElementById("app-header");
  const grid = document.getElementById("food-grid");
  const drawer = document.getElementById("cart-drawer");
  const heroTrack = document.getElementById("hero-track");
  const heroCount = document.getElementById("hero-slide-count");
  const heroCarousel = document.querySelector(".menu-hero");
  const compactViewport = window.matchMedia("(max-width: 680px)");
  const mobileCartButton = document.querySelector("[data-mobile-cart]");
  const mobileCartCount = document.querySelector("[data-mobile-cart-count]");
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const heroTransitionDuration = 700;
  let activeCategory = "Featured";
  let activeMood = "";
  let heroProducts = [];
  let heroIndex = 0;
  let heroTimer = null;
  let heroTransitionTimer = null;
  let queuedHeroDirections = [];
  let heroPaused = reducedMotion.matches;
  let heroTransitioning = false;
  let heroDirection = 1;
  let catalog = window.trayDemoData.products;
  const searchParams = new URLSearchParams(window.location.search);
  const requestedCategory = searchParams.get("category");
  if (requestedCategory === "Popular") activeCategory = "Featured";
  else if (categories.includes(requestedCategory)) activeCategory = requestedCategory;
  const initialSearch = searchParams.get("search");
  if (initialSearch) activeCategory = "All";
  header.innerHTML = trayComponents.header(activeCategory);
  const searchInput = document.querySelector(".search input");
  if (initialSearch) searchInput.value = initialSearch;

  function rupees(value) {
    return `₹${Number(value).toLocaleString("en-IN")}`;
  }

  function normalizeSearch(value) {
    return String(value || "")
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-z0-9]+/g, " ")
      .trim();
  }

  function searchScore(item, rawQuery) {
    const query = normalizeSearch(rawQuery);
    if (!query) return 1;

    const name = normalizeSearch(item.name);
    const category = normalizeSearch(item.category);
    const description = normalizeSearch(item.description);
    const searchable = `${name} ${category} ${description}`;
    const queryWords = query.split(" ").filter(Boolean);

    if (name === query) return 100;
    if (name.startsWith(query)) return 90;
    if (name.includes(query)) return 80;
    if (category === query) return 70;
    if (category.includes(query)) return 60;

    let score = 0;
    queryWords.forEach((word) => {
      if (word.length < 2) return;
      if (name.includes(word)) score += 35;
      else if (category.includes(word)) score += 25;
      else if (description.includes(word)) score += 15;
      else if (searchable.includes(word)) score += 5;
    });

    return score;
  }

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (character) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      "\"": "&quot;",
      "'": "&#39;"
    })[character]);
  }

  function matchesMood(item, mood) {
    const text = `${item.name} ${item.description}`.toLowerCase();
    const matches = {
      spicy: /\b(masala|biryani|chole|pav bhaji|pakoda|momos|chilli|spicy)\b/,
      comfort: /\b(dosa|idli|pongal|paratha|thali|dal|rajma|rice|poori)\b/,
      quick: /\b(samosa|fries|burger|momos|sandwich|pakoda|pizza|puri)\b/,
      sweet: /\b(chocolate|oreo|mango|milkshake|lassi|strawberry|sweet)\b/,
      refreshing: /\b(juice|soda|lime|lassi|buttermilk|water|cold coffee|milkshake)\b/
    };
    return Boolean(matches[mood] && matches[mood].test(text));
  }

  function renderCategoryRail() {
    const rail = document.getElementById("category-rail");
    const categoryItems = [];
    Array.from(new Set(catalog.map((item) => item.category))).forEach((category) => {
      const item = catalog.find((product) => product.category === category && product.isAvailable);
      if (item) categoryItems.push({ category, item });
    });
    rail.innerHTML = categoryItems.map(({ category, item }, index) => `
      <button class="category-tile" type="button" data-category="${escapeHtml(category)}" aria-label="Browse ${escapeHtml(category)}">
        <img src="${escapeHtml(item.image)}" alt="" loading="lazy">
        <span class="category-number">0${index + 1}</span>
        <strong>${escapeHtml(category)}</strong>
        <span class="category-arrow" aria-hidden="true">↗</span>
      </button>
    `).join("");
  }

  function heroSlideMarkup(item) {
    return `
      <a class="hero-slide" href="./student/product.html?id=${encodeURIComponent(item.id)}"
        aria-label="Order ${escapeHtml(item.name)} for ${rupees(item.price)}. ${escapeHtml(item.description)}"
        aria-hidden="true" tabindex="-1" inert>
        <img class="hero-slide-image" src="${escapeHtml(item.image)}" alt="" loading="eager">
        <div class="hero-copy">
          <div class="hero-kicker">Campus canteen menu</div>
          <span class="hero-category">${escapeHtml(item.category)} · Featured dish</span>
          <h1>${escapeHtml(item.name)}</h1>
          <p>${escapeHtml(item.description)}</p>
          <div class="hero-slide-footer">
            <span class="hero-slide-price">${rupees(item.price)}</span>
            <span class="hero-slide-cta">View dish &amp; order <span aria-hidden="true">→</span></span>
          </div>
        </div>
      </a>
    `;
  }

  function renderHero() {
    heroProducts = catalog
      .filter((item) => item.isFeatured && item.isAvailable);

    if (!heroProducts.length) {
      heroCarousel.hidden = true;
      return;
    }

    heroCarousel.hidden = false;
    heroIndex = 0;
    heroTrack.innerHTML = heroSlideMarkup(heroProducts[heroIndex]);
    heroTrack.style.transition = "none";
    heroTrack.style.transform = "translateX(0)";
    setAccessibleHeroSlide(0);
    heroCount.textContent = `01 / ${String(heroProducts.length).padStart(2, "0")}`;
    heroTrack.getBoundingClientRect();
    heroTrack.style.transition = "";
    updateHeroAutoplay();
  }

  function setAccessibleHeroSlide(activeIndex) {
    Array.from(heroTrack.children).forEach((slide, index) => {
      const active = index === activeIndex;
      slide.setAttribute("aria-hidden", String(!active));
      slide.tabIndex = active ? 0 : -1;
      if (active) slide.removeAttribute("inert");
      else slide.setAttribute("inert", "");
    });
  }

  function finishHeroTransition() {
    if (!heroTransitioning) return;
    window.clearTimeout(heroTransitionTimer);
    heroTransitionTimer = null;
    if (heroDirection > 0) heroTrack.firstElementChild.remove();
    else heroTrack.lastElementChild.remove();
    heroTrack.style.transition = "none";
    heroTrack.style.transform = "translateX(0)";
    setAccessibleHeroSlide(0);
    heroTransitioning = false;
    heroTrack.getBoundingClientRect();
    heroTrack.style.transition = "";

    const queuedDirection = queuedHeroDirections.shift();
    if (queuedDirection) showHeroSlide(queuedDirection, true);
  }

  function showHeroSlide(direction, queueIfTransitioning = false) {
    if (heroProducts.length < 2) return;
    if (heroTransitioning) {
      if (queueIfTransitioning && queuedHeroDirections.length < 8) {
        queuedHeroDirections.push(direction);
      }
      return;
    }

    heroDirection = direction;
    heroIndex = (heroIndex + direction + heroProducts.length) % heroProducts.length;
    const nextSlide = heroSlideMarkup(heroProducts[heroIndex]);
    if (direction > 0) {
      heroTrack.insertAdjacentHTML("beforeend", nextSlide);
      heroTrack.style.transform = "translateX(0)";
      heroTrack.getBoundingClientRect();
      heroTrack.style.transform = "translateX(-100%)";
      setAccessibleHeroSlide(1);
    } else {
      heroTrack.insertAdjacentHTML("afterbegin", nextSlide);
      heroTrack.style.transition = "none";
      heroTrack.style.transform = "translateX(-100%)";
      heroTrack.getBoundingClientRect();
      setAccessibleHeroSlide(0);
      heroTrack.style.transition = "";
      heroTrack.style.transform = "translateX(0)";
    }
    heroTransitioning = true;
    heroCount.textContent = `${String(heroIndex + 1).padStart(2, "0")} / ${String(heroProducts.length).padStart(2, "0")}`;
    heroTransitionTimer = window.setTimeout(finishHeroTransition, heroTransitionDuration + 300);
    if (reducedMotion.matches) finishHeroTransition();
  }

  ["transitionend", "transitioncancel"].forEach((eventName) => {
    heroTrack.addEventListener(eventName, (event) => {
      if (event.target === heroTrack && event.propertyName === "transform") finishHeroTransition();
    });
  });

  function updateHeroAutoplay() {
    window.clearInterval(heroTimer);
    if (heroPaused || compactViewport.matches || heroProducts.length < 2 || document.hidden) return;
    heroTimer = window.setInterval(() => showHeroSlide(1), 5200);
  }

  document.getElementById("hero-previous").addEventListener("click", () => showHeroSlide(-1, true));
  document.getElementById("hero-next").addEventListener("click", () => showHeroSlide(1, true));
  heroCarousel.addEventListener("mouseenter", () => window.clearInterval(heroTimer));
  heroCarousel.addEventListener("mouseleave", updateHeroAutoplay);
  heroCarousel.addEventListener("focusin", () => window.clearInterval(heroTimer));
  heroCarousel.addEventListener("focusout", (event) => {
    if (!heroCarousel.contains(event.relatedTarget)) updateHeroAutoplay();
  });
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && heroTransitioning) finishHeroTransition();
    updateHeroAutoplay();
  });
  reducedMotion.addEventListener?.("change", (event) => {
    heroPaused = event.matches;
    if (heroPaused && heroTransitioning) finishHeroTransition();
    updateHeroAutoplay();
  });
  compactViewport.addEventListener?.("change", updateHeroAutoplay);

  function renderCatalog() {
    const query = document.querySelector(".search input")?.value.trim() || "";
    const normalizedQuery = normalizeSearch(query);
    const availability = document.getElementById("availability-filter")?.value || "all";
    const diet = document.getElementById("diet-filter")?.value || "all";
    const isFeaturedView = activeCategory === "Featured";
    let visible = catalog
      .map((item) => ({ item, score: searchScore(item, query) }))
      .filter(({ item, score }) =>
        score > 0 &&
        (!activeMood || matchesMood(item, activeMood)) &&
        (normalizedQuery ||
          activeCategory === "All" ||
          (isFeaturedView ? item.isFeatured : item.category === activeCategory)) &&
        (availability !== "available" || item.isAvailable) &&
        (diet === "all" ||
          (diet === "veg" && item.isVeg) ||
          (diet === "nonveg" && !item.isVeg && item.dietType !== "egg") ||
          (diet === "egg" && (item.dietType === "egg" ||
            /\begg\b/i.test(`${item.name} ${item.description}`))))
      )
      .sort((a, b) => b.score - a.score)
      .map(({ item }) => item);

    if (!visible.length) {
      grid.innerHTML = "";
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.style.gridColumn = "1/-1";
      const title = document.createElement("h3");
      title.textContent = normalizedQuery ? "Couldn't find that craving" :
        isFeaturedView ? "No featured dishes right now" : "No dishes found";
      const copy = document.createElement("p");
      copy.textContent = normalizedQuery ? `No menu items matched "${query}". Try another dish or category.` :
        isFeaturedView ? "Browse the full menu to find something you love." : "Try a different category or search.";
      empty.append(title, copy);
      grid.appendChild(empty);
      const heading = document.querySelector(".menu-heading h2");
      heading.textContent = normalizedQuery ? "Search results" : isFeaturedView ? "Featured dishes" : activeCategory;
      return;
    }
    const heading = document.querySelector(".menu-heading h2");
    heading.textContent = normalizedQuery ? `Results for "${query}"` :
      activeCategory === "Featured" ? "Featured dishes" :
      activeCategory === "All" ? "All dishes" : activeCategory;
    grid.innerHTML = visible.map((item) => `
      <article class="food-card" data-id="${escapeHtml(item.id)}">
        <div class="food-card-image-wrap">
          <a class="food-card-image-link" href="./student/product.html?id=${encodeURIComponent(item.id)}" aria-label="View ${escapeHtml(item.name)} details">
            <img class="food-card-image" src="${escapeHtml(item.image)}" alt="" loading="lazy" onerror="this.style.display='none';this.closest('.food-card-image-wrap').classList.add('food-image-unavailable')">
          </a>
          ${item.isFeatured ? '<span class="food-card-ribbon">Featured</span>' : ""}
        </div>
        <div class="food-card-body">
          <span class="eyebrow">${escapeHtml(item.category)}</span>
          <h3><a href="./student/product.html?id=${encodeURIComponent(item.id)}">${escapeHtml(item.name)}</a></h3>
          <p class="food-card-description">${escapeHtml(item.description || "")}</p>
          <div class="food-card-status-row">
            <span class="status ${item.isAvailable ? "" : "danger"}">${item.isAvailable ? "On menu" : "Sold out"}</span>
            <span class="food-card-diet ${item.dietType === "egg" || /\begg\b/i.test(`${item.name} ${item.description}`) ? "is-egg" : item.isVeg ? "is-veg" : "is-non-veg"}">${item.dietType === "egg" || /\begg\b/i.test(`${item.name} ${item.description}`) ? "Egg" : item.isVeg ? "Veg" : "Non-veg"}</span>
          </div>
          <div class="food-meta">
            <span class="price">${rupees(item.price)}</span>
            <div class="food-card-actions" data-card-actions="${escapeHtml(item.id)}">
              <button class="food-card-add" type="button" data-card-add="${escapeHtml(item.id)}" aria-label="Add ${escapeHtml(item.name)} to your tray" ${item.isAvailable ? "" : "disabled"}>Add <span aria-hidden="true">+</span></button>
              <div class="food-card-quantity" data-card-quantity-control="${escapeHtml(item.id)}" hidden>
                <button type="button" data-card-qty="-1" data-id="${escapeHtml(item.id)}" aria-label="Remove one ${escapeHtml(item.name)}">−</button>
                <span data-card-quantity>0</span>
                <button type="button" data-card-qty="1" data-id="${escapeHtml(item.id)}" aria-label="Add one ${escapeHtml(item.name)}">+</button>
              </div>
            </div>
          </div>
        </div>
      </article>
    `).join("");
    updateCardQuantities();
  }

  function getCart() {
    return trayStorage.get("trayup-cart", []);
  }

  function saveCart(cart) {
    trayStorage.set("trayup-cart", cart);
    renderCart();
  }

  function renderCart() {
    const cart = getCart();
    const quantity = cart.reduce((sum, item) => sum + item.qty, 0);
    document.getElementById("cart-count").textContent = quantity;
    mobileCartCount.textContent = quantity;
    mobileCartCount.hidden = quantity === 0;
    mobileCartButton.setAttribute("aria-label", `Open your tray, ${quantity} ${quantity === 1 ? "item" : "items"}`);
    document.getElementById("cart-total").textContent = rupees(cart.reduce((sum, item) => sum + item.price * item.qty, 0));
    document.getElementById("cart-items").innerHTML = cart.length ? cart.map((item) => `
      <div class="cart-item">
        <img src="${escapeHtml(item.image)}" alt="">
        <div><strong>${escapeHtml(item.name)}</strong><span>${rupees(item.price)}</span>
          <div class="qty-control">
            <button type="button" data-qty="-1" data-id="${escapeHtml(item.id)}" aria-label="Remove one ${escapeHtml(item.name)}">−</button>
            <span>${Number(item.qty) || 0}</span>
            <button type="button" data-qty="1" data-id="${escapeHtml(item.id)}" aria-label="Add one ${escapeHtml(item.name)}">+</button>
          </div>
        </div>
      </div>
    `).join("") : `<div class="empty-state"><p>Your cart is empty</p><a href="#popular">Browse the menu</a></div>`;
    document.getElementById("drawer-checkout").hidden = !cart.length;
    updateCardQuantities();
    const count = document.getElementById("cart-count");
    count.classList.remove("cart-count-pop");
    requestAnimationFrame(() => count.classList.add("cart-count-pop"));
  }

  function updateCardQuantities() {
    const cart = getCart();
    document.querySelectorAll("[data-card-actions]").forEach((actions) => {
      const item = cart.find((entry) => entry.id === Number(actions.dataset.cardActions));
      const quantity = item ? item.qty : 0;
      const addButton = actions.querySelector("[data-card-add]");
      const controls = actions.querySelector("[data-card-quantity-control]");
      if (!addButton || !controls) return;
      addButton.hidden = quantity > 0;
      controls.hidden = quantity <= 0;
      controls.querySelector("[data-card-quantity]").textContent = quantity;
    });
  }

  grid.addEventListener("click", (event) => {
    const addButton = event.target.closest("[data-card-add]");
    const quantityButton = event.target.closest("[data-card-qty]");
    if (addButton || quantityButton) {
      event.stopPropagation();
      const id = Number((addButton || quantityButton).dataset.id || (addButton || quantityButton).dataset.cardAdd);
      const product = catalog.find((item) => item.id === id);
      if (!product || !product.isAvailable) return;
      const cart = getCart();
      const item = cart.find((entry) => entry.id === id);
      const change = quantityButton ? Number(quantityButton.dataset.cardQty) : 1;
      if (item) item.qty += change;
      else if (change > 0) cart.push({ ...product, qty: change });
      saveCart(cart.filter((entry) => entry.qty > 0));
      if (change > 0 && window.trayNotify) window.trayNotify("Good choice! Added to your tray.");
      return;
    }
  });

  document.getElementById("open-cart").addEventListener("click", () => drawer.classList.add("open"));
  document.getElementById("close-cart").addEventListener("click", () => drawer.classList.remove("open"));
  const searchForm = document.querySelector(".search");
  const suggestionList = document.getElementById("menu-suggestions");

  function renderSuggestions(query) {
    const trimmed = query.trim();
    if (!trimmed) {
      suggestionList.hidden = true;
      suggestionList.innerHTML = "";
      return;
    }
    const matches = catalog
      .map((item) => ({ item, score: searchScore(item, trimmed) }))
      .filter(({ score }) => score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, 5);
    suggestionList.hidden = false;
    suggestionList.innerHTML = matches.length
      ? matches.map(({ item }) => `
        <button class="search-suggestion" type="button" role="option" data-suggestion-id="${escapeHtml(item.id)}">
          <img src="${escapeHtml(item.image)}" alt="" loading="lazy">
          <span><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(item.category)}</small></span>
          <b>${rupees(item.price)}</b>
        </button>`).join("")
      : '<p class="search-no-results">Couldn’t find that craving. Try another dish.</p>';
  }

  function selectSuggestion(button) {
    if (!button) return;
    window.location.href = `./student/product.html?id=${encodeURIComponent(button.dataset.suggestionId)}`;
  }

  searchForm.addEventListener("submit", (event) => {
    event.preventDefault();
    suggestionList.hidden = true;
    activeCategory = "All";
    document.querySelectorAll(".category-nav a").forEach((entry) =>
      entry.classList.toggle("active", entry.dataset.navCategory === "All")
    );
    renderCatalog();
    document.getElementById("popular").scrollIntoView({ behavior: "smooth", block: "start" });
  });
  searchInput.addEventListener("input", () => {
    renderSuggestions(searchInput.value);
    if (searchInput.value.trim()) {
      activeCategory = "All";
      document.querySelectorAll(".category-nav a").forEach((entry) =>
        entry.classList.toggle("active", entry.dataset.navCategory === "All")
      );
    }
    renderCatalog();
  });
  searchInput.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown" && !suggestionList.hidden) {
      const firstSuggestion = suggestionList.querySelector("[data-suggestion-id]");
      if (firstSuggestion) {
        event.preventDefault();
        firstSuggestion.focus();
      }
    } else if (event.key === "Escape") {
      suggestionList.hidden = true;
    }
  });
  suggestionList.addEventListener("click", (event) => {
    selectSuggestion(event.target.closest("[data-suggestion-id]"));
  });
  suggestionList.addEventListener("keydown", (event) => {
    const buttons = Array.from(suggestionList.querySelectorAll("[data-suggestion-id]"));
    const currentIndex = buttons.indexOf(document.activeElement);
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const direction = event.key === "ArrowDown" ? 1 : -1;
      const nextIndex = (currentIndex + direction + buttons.length) % buttons.length;
      if (buttons[nextIndex]) buttons[nextIndex].focus();
    } else if (event.key === "Escape") {
      suggestionList.hidden = true;
      searchInput.focus();
    } else if (event.key === "Enter") {
      event.preventDefault();
      selectSuggestion(buttons[currentIndex]);
    }
  });
  document.addEventListener("click", (event) => {
    if (!searchForm.contains(event.target)) suggestionList.hidden = true;
  });
  document.getElementById("availability-filter").addEventListener("change", renderCatalog);
  document.getElementById("diet-filter").addEventListener("change", (event) => {
    if (event.target.value !== "all") {
      activeCategory = "All";
      document.querySelectorAll(".category-nav a").forEach((entry) =>
        entry.classList.toggle("active", entry.dataset.navCategory === "All")
      );
    }
    renderCatalog();
  });
  document.getElementById("clear-search").addEventListener("click", () => {
    document.querySelector(".search input").value = "";
    suggestionList.hidden = true;
    document.getElementById("availability-filter").value = "all";
    document.getElementById("diet-filter").value = "all";
    activeMood = "";
    document.getElementById("clear-mood").hidden = true;
    document.querySelectorAll("[data-mood]").forEach((button) => button.classList.remove("active"));
    activeCategory = "Featured";
    document.querySelectorAll(".category-nav a").forEach((entry) =>
      entry.classList.toggle("active", entry.dataset.navCategory === "Featured")
    );
    renderCatalog();
  });

  document.querySelector(".category-nav").addEventListener("click", (event) => {
    const link = event.target.closest("[data-nav-category]");
    if (!link) return;
    const category = link.dataset.navCategory;
    if (category === "My Orders") return;
    event.preventDefault();
    activeCategory = category;
    activeMood = "";
    document.getElementById("clear-mood").hidden = true;
    document.querySelectorAll("[data-mood]").forEach((button) => button.classList.remove("active"));
    document.querySelector(".search input").value = "";
    document.querySelectorAll(".category-nav a").forEach((entry) => entry.classList.toggle("active", entry === link));
    renderCatalog();
    document.getElementById("popular").scrollIntoView({ behavior: "smooth" });
  });

  document.getElementById("category-rail").addEventListener("click", (event) => {
    const tile = event.target.closest("[data-category]");
    if (!tile) return;
    activeCategory = tile.dataset.category;
    activeMood = "";
    document.getElementById("clear-mood").hidden = true;
    document.querySelectorAll("[data-mood]").forEach((button) => button.classList.remove("active"));
    searchInput.value = "";
    document.querySelectorAll(".category-nav a").forEach((link) =>
      link.classList.toggle("active", link.dataset.navCategory === activeCategory)
    );
    renderCatalog();
    document.getElementById("popular").scrollIntoView({ behavior: "smooth", block: "start" });
  });

  document.getElementById("mood-choices").addEventListener("click", (event) => {
    const button = event.target.closest("[data-mood]");
    if (!button) return;
    activeMood = activeMood === button.dataset.mood ? "" : button.dataset.mood;
    activeCategory = "All";
    searchInput.value = "";
    document.getElementById("clear-mood").hidden = !activeMood;
    document.querySelectorAll("[data-mood]").forEach((choice) =>
      choice.classList.toggle("active", choice.dataset.mood === activeMood)
    );
    document.querySelectorAll(".category-nav a").forEach((link) =>
      link.classList.toggle("active", link.dataset.navCategory === "All")
    );
    renderCatalog();
    document.getElementById("popular").scrollIntoView({ behavior: "smooth", block: "start" });
  });

  document.getElementById("clear-mood").addEventListener("click", () => {
    activeMood = "";
    document.querySelectorAll("[data-mood]").forEach((button) => button.classList.remove("active"));
    document.getElementById("clear-mood").hidden = true;
    renderCatalog();
  });

  function showAllMenu(event) {
    event.preventDefault();
    activeCategory = "All";
    activeMood = "";
    searchInput.value = "";
    document.getElementById("clear-mood").hidden = true;
    document.querySelectorAll("[data-mood]").forEach((button) => button.classList.remove("active"));
    document.querySelectorAll(".category-nav a").forEach((link) =>
      link.classList.toggle("active", link.dataset.navCategory === "All")
    );
    renderCatalog();
    document.getElementById("popular").scrollIntoView({ behavior: "smooth", block: "start" });
  }
  document.querySelectorAll("[data-browse-all]").forEach((link) =>
    link.addEventListener("click", showAllMenu)
  );

  document.getElementById("surprise-me").addEventListener("click", () => {
    const visibleIds = new Set(Array.from(grid.querySelectorAll(".food-card"), (card) => Number(card.dataset.id)));
    const options = catalog.filter((item) => item.isAvailable && visibleIds.has(item.id));
    const result = document.getElementById("roulette-result");
    if (!options.length) {
      result.innerHTML = '<div class="roulette-placeholder"><span>!</span></div><p>No available dishes match those filters. Clear filters and try again.</p>';
      result.classList.add("is-revealed");
      return;
    }
    const item = options[Math.floor(Math.random() * options.length)];
    result.innerHTML = `
      <a class="roulette-dish" href="./student/product.html?id=${encodeURIComponent(item.id)}">
        <img src="${escapeHtml(item.image)}" alt="${escapeHtml(item.name)}">
        <span class="roulette-dish-info"><small>YOUR RANDOM PICK</small><strong>${escapeHtml(item.name)}</strong><b>${rupees(item.price)}</b></span>
        <span class="roulette-dish-arrow" aria-hidden="true">↗</span>
      </a>`;
    result.classList.remove("is-revealed");
    requestAnimationFrame(() => result.classList.add("is-revealed"));
  });

  mobileCartButton.addEventListener("click", () => drawer.classList.add("open"));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && drawer.classList.contains("open")) {
      drawer.classList.remove("open");
      document.getElementById("open-cart").focus();
    }
  });

  document.getElementById("cart-items").addEventListener("click", (event) => {
    const button = event.target.closest("[data-qty]");
    if (!button) return;
    const cart = getCart();
    const item = cart.find((entry) => entry.id === Number(button.dataset.id));
    if (!item) return;
    item.qty += Number(button.dataset.qty);
    saveCart(cart.filter((entry) => entry.qty > 0));
  });

  renderCategoryRail();
  renderHero();
  renderCatalog();
  renderCart();
})();
