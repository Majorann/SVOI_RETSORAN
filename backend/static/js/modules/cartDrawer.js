const setupCartDrawer = ({
  menuList,
  cartDrawer,
  cartOverlay,
  cartOverlayHint,
  cartList,
  cartEmpty,
  cartTotal,
  cartCheckout,
  cartDrawerClose,
  cartDrawerHeader,
  menuCartFab,
  menuCartFabBadge,
  loadCart,
  saveCart,
  normalizeCart,
  navigateWithAuth,
}) => {
  if (typeof loadCart !== "function" || typeof saveCart !== "function" || typeof normalizeCart !== "function") {
    return;
  }

  const menuMobileQuery = window.matchMedia("(max-width: 767px)");
  const isMenuMobile = () => Boolean(menuMobileQuery.matches && menuList && cartDrawer);
  const dragCloseRatio = 0.3;
  const mobileCartHintMinGap = 88;
  let mobileCartOpen = false;
  let mobileDragActive = false;
  let mobileDragStartY = 0;
  let mobileDragY = 0;
  let mobileDrawerHeight = 0;
  let mobileCartHintHideTimer = null;

  const hideMobileCartHint = () => {
    if (!cartOverlayHint) return;
    cartOverlayHint.classList.remove("is-visible");
    if (mobileCartHintHideTimer) {
      window.clearTimeout(mobileCartHintHideTimer);
    }
    mobileCartHintHideTimer = window.setTimeout(() => {
      if (!cartOverlayHint.classList.contains("is-visible")) {
        cartOverlayHint.hidden = true;
        cartOverlayHint.style.top = "";
      }
      mobileCartHintHideTimer = null;
    }, 260);
  };

  const updateMobileCartHint = () => {
    if (!cartOverlayHint || !isMenuMobile() || !mobileCartOpen || !cartDrawer || cartDrawer.hidden) {
      hideMobileCartHint();
      return;
    }
    const drawerRect = cartDrawer.getBoundingClientRect();
    const topGap = Math.max(0, drawerRect.top);
    if (topGap < mobileCartHintMinGap) {
      hideMobileCartHint();
      return;
    }
    if (mobileCartHintHideTimer) {
      window.clearTimeout(mobileCartHintHideTimer);
      mobileCartHintHideTimer = null;
    }
    cartOverlayHint.hidden = false;
    cartOverlayHint.style.top = `${Math.round(topGap / 2)}px`;
    requestAnimationFrame(() => cartOverlayHint.classList.add("is-visible"));
  };

  const syncFabState = (cartCount) => {
    if (!menuCartFab || !menuCartFabBadge) return;
    menuCartFabBadge.textContent = String(cartCount);
    menuCartFabBadge.hidden = cartCount <= 0;
    menuCartFab.setAttribute("aria-label", cartCount > 0 ? `Открыть корзину, товаров: ${cartCount}` : "Открыть корзину");
  };

  const closeMobileCart = () => {
    if (!isMenuMobile() || !cartDrawer) return;
    mobileCartOpen = false;
    mobileDragActive = false;
    mobileDragY = 0;
    cartDrawer.classList.remove("is-open", "is-settle");
    cartDrawer.classList.add("is-closing");
    cartDrawer.classList.remove("is-dragging");
    cartDrawer.style.transform = "";
    cartDrawer.setAttribute("aria-hidden", "true");
    cartOverlay?.classList.remove("is-open");
    if (cartOverlay) {
      cartOverlay.style.opacity = "";
      cartOverlay.hidden = true;
    }
    hideMobileCartHint();
    document.body.classList.remove("menu-cart-open", "menu-cart-open-mobile");
    if (menuCartFab) {
      menuCartFab.setAttribute("aria-expanded", "false");
      menuCartFab.classList.remove("is-hidden");
    }
    window.setTimeout(() => {
      if (!mobileCartOpen && cartDrawer) {
        cartDrawer.hidden = true;
        cartDrawer.classList.remove("is-closing");
      }
    }, 220);
  };

  const openMobileCart = () => {
    if (!isMenuMobile() || !cartDrawer) return;
    if (cartDrawer._hideTimer) {
      window.clearTimeout(cartDrawer._hideTimer);
      cartDrawer._hideTimer = null;
    }
    mobileCartOpen = true;
    mobileDragActive = false;
    mobileDragY = 0;
    cartDrawer.hidden = false;
    cartDrawer.classList.remove("is-closing");
    cartDrawer.classList.remove("is-dragging");
    cartDrawer.style.transform = "";
    cartDrawer.setAttribute("aria-hidden", "false");
    if (cartOverlay) {
      cartOverlay.style.opacity = "";
      cartOverlay.hidden = false;
      requestAnimationFrame(() => cartOverlay.classList.add("is-open"));
    }
    document.body.classList.add("menu-cart-open-mobile");
    if (menuCartFab) {
      menuCartFab.setAttribute("aria-expanded", "true");
      menuCartFab.classList.add("is-hidden");
    }
    requestAnimationFrame(() => {
      cartDrawer.classList.add("is-open", "is-settle");
      window.setTimeout(() => cartDrawer.classList.remove("is-settle"), 120);
      window.setTimeout(updateMobileCartHint, 220);
    });
  };

  const setDrawerState = (hasItems) => {
    if (!cartDrawer || !menuList) return;
    if (isMenuMobile()) {
      if (mobileCartOpen) {
        cartDrawer.hidden = false;
      } else {
        cartDrawer.hidden = true;
        cartDrawer.setAttribute("aria-hidden", "true");
        cartDrawer.classList.remove("is-open", "is-settle", "is-closing");
        cartOverlay?.classList.remove("is-open");
        if (cartOverlay) cartOverlay.hidden = true;
        hideMobileCartHint();
        document.body.classList.remove("menu-cart-open-mobile", "menu-cart-open");
      }
      return;
    }

    mobileCartOpen = false;
    mobileDragActive = false;
    mobileDragY = 0;
    if (menuCartFab) {
      menuCartFab.setAttribute("aria-expanded", "false");
      menuCartFab.classList.remove("is-hidden");
    }
    cartOverlay?.classList.remove("is-open");
    if (cartOverlay) cartOverlay.hidden = true;
    hideMobileCartHint();

    const closeDurationMs = 360;
    if (hasItems) {
      if (cartDrawer._hideTimer) {
        window.clearTimeout(cartDrawer._hideTimer);
        cartDrawer._hideTimer = null;
      }
      cartDrawer.hidden = false;
      cartDrawer.setAttribute("aria-hidden", "false");
      cartDrawer.classList.remove("is-closing");
      if (!cartDrawer.classList.contains("is-open")) {
        cartDrawer.classList.add("is-open", "is-settle");
        window.setTimeout(() => cartDrawer.classList.remove("is-settle"), 140);
      }
      document.body.classList.add("menu-cart-open");
      return;
    }
    if (!cartDrawer.classList.contains("is-open")) {
      cartDrawer.hidden = true;
      cartDrawer.setAttribute("aria-hidden", "true");
      document.body.classList.remove("menu-cart-open");
      return;
    }
    cartDrawer.classList.remove("is-open", "is-settle");
    cartDrawer.classList.add("is-closing");
    cartDrawer._hideTimer = window.setTimeout(() => {
      cartDrawer.hidden = true;
      cartDrawer.setAttribute("aria-hidden", "true");
      cartDrawer.classList.remove("is-closing");
      document.body.classList.remove("menu-cart-open");
      cartDrawer._hideTimer = null;
    }, closeDurationMs);
  };

  const updateMenuButtons = (currentCart = null) => {
    const cart = currentCart || normalizeCart(loadCart());
    const idsInCart = new Set(cart.map((item) => Number(item.id)));
    document.querySelectorAll(".add-button").forEach((btn) => {
      if (!btn.dataset.defaultLabel) {
        btn.dataset.defaultLabel = btn.textContent.trim() || "В корзину";
      }
      const id = Number(btn.dataset.id);
      const inCart = idsInCart.has(id);
      if (inCart) {
        btn.classList.remove("is-added");
        btn.classList.add("is-remove");
        btn.textContent = "Убрать";
      } else {
        btn.classList.remove("is-remove", "is-added");
        btn.textContent = btn.dataset.defaultLabel;
      }
    });
  };

  const updateCartUI = () => {
    if (!cartList || !cartTotal) {
      updateMenuButtons();
      return;
    }

    const previousRows = Array.from(cartList.querySelectorAll(".cart-item"));
    const previousQtyById = new Map(previousRows.map((row) => [Number(row.dataset.id), Number(row.dataset.qty)]));
    const previousTotal = Number(cartTotal.textContent || 0);
    const cart = normalizeCart(loadCart());
    const cartCount = cart.reduce((sum, item) => sum + item.qty, 0);
    const totalPrice = cart.reduce((sum, item) => sum + item.qty * item.price, 0);

    cartList.innerHTML = "";
    cart.forEach((item, index) => {
      const prevQty = previousQtyById.get(item.id) || 0;
      const row = document.createElement("div");
      row.className = "cart-item";
      row.dataset.id = String(item.id);
      row.dataset.qty = String(item.qty);
      row.style.setProperty("--cart-stagger-delay", `${index * 60}ms`);
      if (!prevQty) row.classList.add("cart-item--new");
      row.innerHTML = `
        <div>
          <div class="cart-item__name">${item.name}</div>
          <div class="cart-item__meta">${item.price} ₽</div>
        </div>
        <div class="cart-item__actions">
          <button class="cart-item__btn" data-action="dec" data-id="${item.id}">−</button>
          <span class="cart-item__qty${
            prevQty && prevQty !== item.qty
              ? item.qty > prevQty
                ? " is-updated-up"
                : " is-updated-down"
              : ""
          }" data-prev="${prevQty || item.qty}" data-next="${item.qty}">${item.qty}</span>
          <button class="cart-item__btn" data-action="inc" data-id="${item.id}">+</button>
        </div>
      `;
      cartList.appendChild(row);
    });

    if (cartEmpty) cartEmpty.hidden = cart.length > 0;
    if (cartCheckout) cartCheckout.disabled = cart.length === 0;
    cartTotal.textContent = String(totalPrice);
    if (previousTotal !== totalPrice) {
      cartTotal.closest(".cart-drawer__total")?.classList.add("is-pulse");
      window.setTimeout(() => {
        cartTotal.closest(".cart-drawer__total")?.classList.remove("is-pulse");
      }, 280);
    }
    syncFabState(cartCount);
    setDrawerState(cart.length > 0);
    updateMobileCartHint();
    updateMenuButtons(cart);
  };

  const animateQtyChange = (qtyNode, prev, next) => {
    if (!qtyNode || prev === next) return;
    qtyNode.classList.remove("is-updated-up", "is-updated-down");
    void qtyNode.offsetWidth;
    qtyNode.dataset.prev = String(prev);
    qtyNode.dataset.next = String(next);
    qtyNode.textContent = String(next);
    qtyNode.classList.add(next > prev ? "is-updated-up" : "is-updated-down");
    window.setTimeout(() => {
      qtyNode.classList.remove("is-updated-up", "is-updated-down");
    }, 190);
  };

  const pulseCartTotal = (nextTotal) => {
    if (!cartTotal) return;
    cartTotal.textContent = String(nextTotal);
    const totalBlock = cartTotal.closest(".cart-drawer__total");
    totalBlock?.classList.add("is-pulse");
    window.setTimeout(() => {
      totalBlock?.classList.remove("is-pulse");
    }, 280);
  };

  const addToCart = (id, name, price) => {
    const button = document.querySelector(`.add-button[data-id="${id}"]`);
    const photo = button?.dataset.photo || "";
    const cart = loadCart();
    const existing = cart.find((item) => Number(item.id) === id);
    if (existing) {
      existing.qty += 1;
      if (!existing.photo && photo) existing.photo = photo;
    } else {
      cart.push({ id, name, price, qty: 1, photo });
    }
    saveCart(cart);
    updateCartUI();
  };

  const removeFromCart = (id) => {
    const cart = normalizeCart(loadCart());
    const next = cart.filter((item) => Number(item.id) !== id);
    saveCart(next);
    updateCartUI();
  };

  document.querySelectorAll(".add-button").forEach((btn) => {
    if (!btn.dataset.defaultLabel) {
      btn.dataset.defaultLabel = btn.textContent.trim() || "В корзину";
    }
    btn.addEventListener("click", () => {
      const id = Number(btn.dataset.id);
      if (btn.classList.contains("is-remove")) {
        removeFromCart(id);
        return;
      }
      const name = btn.dataset.name || "Позиция";
      const price = Number(btn.dataset.price) || 0;
      addToCart(id, name, price);
    });
  });

  menuCartFab?.addEventListener("click", () => {
    if (!isMenuMobile()) return;
    if (mobileCartOpen) {
      closeMobileCart();
      return;
    }
    openMobileCart();
  });

  cartDrawerClose?.addEventListener("click", closeMobileCart);
  cartOverlay?.addEventListener("click", closeMobileCart);

  const onMobileDrawerTouchStart = (event) => {
    if (!isMenuMobile() || !mobileCartOpen || !cartDrawer) return;
    const touch = event.touches?.[0];
    if (!touch) return;
    mobileDragActive = true;
    mobileDragStartY = touch.clientY;
    mobileDragY = 0;
    mobileDrawerHeight = cartDrawer.getBoundingClientRect().height || 0;
    cartDrawer.classList.add("is-dragging");
  };

  const onMobileDrawerTouchMove = (event) => {
    if (!mobileDragActive || !cartDrawer) return;
    const touch = event.touches?.[0];
    if (!touch) return;
    const delta = touch.clientY - mobileDragStartY;
    mobileDragY = Math.max(0, delta);
    cartDrawer.style.transform = `translateY(${mobileDragY}px)`;
    updateMobileCartHint();
    if (cartOverlay && mobileDrawerHeight > 0) {
      const progress = Math.max(0, Math.min(1, mobileDragY / (mobileDrawerHeight * 0.9)));
      cartOverlay.style.opacity = String(1 - progress);
    }
    if (mobileDragY > 0) event.preventDefault();
  };

  const onMobileDrawerTouchEnd = () => {
    if (!mobileDragActive || !cartDrawer) return;
    mobileDragActive = false;
    const threshold = mobileDrawerHeight * dragCloseRatio;
    cartDrawer.classList.remove("is-dragging");
    if (mobileDragY >= threshold) {
      cartDrawer.style.transform = "";
      closeMobileCart();
      return;
    }
    cartDrawer.style.transform = "";
    if (cartOverlay) cartOverlay.style.opacity = "";
    mobileDragY = 0;
    updateMobileCartHint();
  };

  if (cartDrawerHeader) {
    cartDrawerHeader.addEventListener("touchstart", onMobileDrawerTouchStart, { passive: true });
    cartDrawerHeader.addEventListener("touchmove", onMobileDrawerTouchMove, { passive: false });
    cartDrawerHeader.addEventListener("touchend", onMobileDrawerTouchEnd);
    cartDrawerHeader.addEventListener("touchcancel", onMobileDrawerTouchEnd);
  }

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape" || !mobileCartOpen) return;
    closeMobileCart();
  });

  const syncOnViewportChange = () => {
    mobileCartOpen = false;
    hideMobileCartHint();
    setDrawerState(normalizeCart(loadCart()).length > 0);
  };
  if (typeof menuMobileQuery.addEventListener === "function") {
    menuMobileQuery.addEventListener("change", syncOnViewportChange);
  } else if (typeof menuMobileQuery.addListener === "function") {
    menuMobileQuery.addListener(syncOnViewportChange);
  }

  window.addEventListener("resize", updateMobileCartHint);

  cartCheckout?.addEventListener("click", () => {
    const cart = loadCart();
    if (!cart.length) {
      if (cartTotal) cartTotal.textContent = "0";
      return;
    }
    const checkoutUrl = cartCheckout.dataset.checkoutUrl || "/checkout";
    navigateWithAuth(checkoutUrl);
  });

  cartList?.addEventListener("click", (event) => {
    const button = event.target.closest(".cart-item__btn");
    if (!button) return;
    const id = Number(button.dataset.id);
    const cart = loadCart();
    const item = cart.find((row) => Number(row.id) === id);
    if (!item) return;
    const rowNode = button.closest(".cart-item");
    const qtyNode = rowNode?.querySelector(".cart-item__qty");
    const prevQty = Number(item.qty) || 0;
    if (button.dataset.action === "inc") {
      item.qty += 1;
      saveCart(cart);
      const normalized = normalizeCart(cart);
      const totalPrice = normalized.reduce((sum, row) => sum + row.qty * row.price, 0);
      if (rowNode) rowNode.dataset.qty = String(item.qty);
      animateQtyChange(qtyNode, prevQty, item.qty);
      pulseCartTotal(totalPrice);
      updateMenuButtons(normalized);
      return;
    }
    if (button.dataset.action === "dec" && item.qty <= 1) {
      const row = cartList.querySelector(`.cart-item[data-id="${id}"]`);
      if (row) {
        row.classList.add("cart-item--removing");
        window.setTimeout(() => {
          const next = cart.filter((rowItem) => rowItem.id !== id);
          saveCart(next);
          updateCartUI();
        }, 250);
        return;
      }
    }
    if (button.dataset.action === "dec") {
      item.qty -= 1;
    }
    const next = normalizeCart(cart);
    saveCart(next);
    const totalPrice = next.reduce((sum, row) => sum + row.qty * row.price, 0);
    if (rowNode) rowNode.dataset.qty = String(item.qty);
    animateQtyChange(qtyNode, prevQty, item.qty);
    pulseCartTotal(totalPrice);
    updateMenuButtons(next);
  });

  updateCartUI();
};

export { setupCartDrawer };
