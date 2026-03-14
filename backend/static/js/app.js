import { stagger, getCsrfToken } from "./modules/core.js";
import { setupMenuHoverMood } from "./modules/menuHoverMood.js";
import { setupBottomNavMotion } from "./modules/bottomNavMotion.js";
import { setupTableTooltip } from "./modules/tableTooltip.js";
import { setupOrderStatusBar } from "./modules/orderStatusBar.js";
import { setupPointsBalanceCard } from "./modules/pointsBalanceCard.js";
import { setupDeliveryFlow } from "./modules/deliveryFlow.js";
window.addEventListener("DOMContentLoaded", () => {
  stagger(".news-card", 140);
  stagger(".menu-card", 120);
  setupPointsBalanceCard();
  setupBottomNavMotion();
  setupTableTooltip();
  setupMenuHoverMood();
  setupOrderStatusBar();
  setupDeliveryFlow();

  const menuViewport = document.getElementById("menuViewport");
  const menuList = document.getElementById("menuList") || document.querySelector(".menu");
  const menuCards = Array.from(document.querySelectorAll(".menu-card--menu"));
  const categoryChips = Array.from(document.querySelectorAll(".menu-chip"));
  const typeToggle = document.getElementById("typeToggle");
  const typeMenu = document.getElementById("typeMenu");
  const typeOptions = Array.from(document.querySelectorAll(".filter-option"));
  const typeValue = document.getElementById("typeValue");
  const sortToggle = document.getElementById("sortToggle");
  const sortMenu = document.getElementById("sortMenu");
  const sortOptions = Array.from(document.querySelectorAll(".sort-option"));
  const sortValue = document.getElementById("sortValue");
  const cartDrawer = document.getElementById("cartDrawer");
  const cartOverlay = document.getElementById("cartOverlay");
  const cartOverlayHint = document.getElementById("cartOverlayHint");
  const cartList = document.getElementById("cartList");
  const cartEmpty = document.getElementById("cartEmpty");
  const cartTotal = document.getElementById("cartTotal");
  const cartCheckout = document.getElementById("cartCheckout");
  const cartDrawerClose = document.getElementById("cartDrawerClose");
  const cartDrawerHeader = cartDrawer?.querySelector(".cart-drawer__header");
  const menuCartFab = document.getElementById("menuCartFab");
  const menuCartFabBadge = document.getElementById("menuCartFabBadge");
  const checkoutForm = document.getElementById("checkoutForm");
  const checkoutItemsNode = document.getElementById("checkoutItems");
  const checkoutItemsTotal = document.getElementById("checkoutItemsTotal");
  const checkoutTotal = document.getElementById("checkoutTotal");
  const checkoutItemsJson = document.getElementById("checkoutItemsJson");
  const checkoutEmpty = document.getElementById("checkoutEmpty");
  const checkoutSummaryList = document.getElementById("checkoutSummaryList");
  const checkoutComment = document.getElementById("checkoutComment");
  const checkoutCommentCount = document.getElementById("checkoutCommentCount");
  const usePoints = document.getElementById("usePoints");
  const availablePoints = document.getElementById("availablePoints");
  const checkoutPointsApplied = document.getElementById("checkoutPointsApplied");
  const checkoutPayable = document.getElementById("checkoutPayable");
  const goToPayment = document.getElementById("goToPayment");
  const serveCustomTime = document.getElementById("serveCustomTime");
  const isDeliveryMenuPage = document.body.classList.contains("page-delivery-menu");
  const cartStorageKey = isDeliveryMenuPage ? "delivery_cart" : "cart";
  const cardNumberInput = document.querySelector('input[name="card_number"]');
  const expiryInput = document.querySelector('input[name="expiry"]');
  const holderInput = document.querySelector('input[name="holder"]');
  const phoneInputs = Array.from(document.querySelectorAll('input[name="phone"]'));
  if (menuList && menuCards.length) {
    const sortLabels = {
      popular: "По популярности",
      "price-asc": "Цена ↑",
      "price-desc": "Цена ↓",
    };
    let activeCategory = "all";
    let activeSort = "popular";
    let isMenuTransitionRunning = false;
    let pendingCategory = null;
    const normalizeType = (value) =>
      String(value || "")
        .toLowerCase()
        .replace(/\s+/g, " ")
        .trim();
    const categoryOrder = categoryChips.map((chip) => chip.dataset.type || "all");
    const categoryLabels = new Map(
      categoryChips.map((chip) => [chip.dataset.type || "all", chip.textContent.trim() || "Все"])
    );

    const getNumber = (value) => {
      const parsed = Number(value);
      return Number.isFinite(parsed) ? parsed : 0;
    };

    const compareCards = (a, b) => {
      const priceA = getNumber(a.dataset.price);
      const priceB = getNumber(b.dataset.price);
      const popularityA = getNumber(a.dataset.popularity);
      const popularityB = getNumber(b.dataset.popularity);
      if (activeSort === "price-asc") {
        if (priceA !== priceB) return priceA - priceB;
      } else if (activeSort === "price-desc") {
        if (priceA !== priceB) return priceB - priceA;
      } else if (popularityA !== popularityB) {
        return popularityB - popularityA;
      }
      return (a.dataset.name || a.querySelector("h3")?.textContent || "")
        .localeCompare(b.dataset.name || b.querySelector("h3")?.textContent || "", "ru");
    };

    const closeSortMenu = () => {
      sortMenu?.classList.remove("is-open");
      sortToggle?.setAttribute("aria-expanded", "false");
      sortMenu?.setAttribute("aria-hidden", "true");
    };

    const closeTypeMenu = () => {
      typeMenu?.classList.remove("is-open");
      typeToggle?.setAttribute("aria-expanded", "false");
      typeMenu?.setAttribute("aria-hidden", "true");
    };

    const openSortMenu = () => {
      closeTypeMenu();
      sortMenu?.classList.add("is-open");
      sortToggle?.setAttribute("aria-expanded", "true");
      sortMenu?.setAttribute("aria-hidden", "false");
    };

    const openTypeMenu = () => {
      closeSortMenu();
      typeMenu?.classList.add("is-open");
      typeToggle?.setAttribute("aria-expanded", "true");
      typeMenu?.setAttribute("aria-hidden", "false");
    };

    const getFilteredCards = (category) => {
      const selectedType = normalizeType(category);
      return menuCards
        .filter((card) => {
          if (selectedType === "all") return true;
          return normalizeType(card.dataset.type) === selectedType;
        })
        .sort(compareCards);
    };

    const syncMenuControls = () => {
      if (sortValue) {
        sortValue.textContent = sortLabels[activeSort] || sortLabels.popular;
      }
      if (typeValue) {
        typeValue.textContent = categoryLabels.get(activeCategory) || "Все";
      }
      categoryChips.forEach((chip) => {
        chip.classList.toggle("is-active", chip.dataset.type === activeCategory);
      });
      typeOptions.forEach((option) => {
        option.classList.toggle("is-active", option.dataset.type === activeCategory);
      });
      sortOptions.forEach((option) => {
        option.classList.toggle("is-active", option.dataset.sort === activeSort);
      });
    };

    const renderMenuCards = (cards, animate = true) => {
      menuCards.forEach((card) => {
        card.hidden = true;
        card.style.display = "none";
        card.style.animationDelay = "";
        card.classList.remove("menu-card--reveal", "is-expanded");
      });

      cards.forEach((card, index) => {
        card.hidden = false;
        card.style.display = "";
        menuList.appendChild(card);
        if (animate) {
          card.style.animationDelay = `${index * 28}ms`;
          card.classList.add("menu-card--reveal");
        }
      });
    };

    const finishMenuTransition = (outgoingLayer) => {
      outgoingLayer?.remove();
      menuList.classList.remove(
        "menu--transition-layer",
        "menu--incoming",
        "menu--from-left",
        "menu--from-right"
      );
      if (menuViewport) {
        menuViewport.classList.remove("is-animating");
        menuViewport.style.height = "";
      }
      isMenuTransitionRunning = false;

      if (pendingCategory && pendingCategory !== activeCategory) {
        const nextCategory = pendingCategory;
        pendingCategory = null;
        activateCategory(nextCategory);
      } else {
        pendingCategory = null;
      }
    };

    const animateCategoryTransition = (nextCategory) => {
      if (!menuViewport) {
        activeCategory = nextCategory;
        renderMenuCards(getFilteredCards(activeCategory), true);
        syncMenuControls();
        return;
      }

      const currentIndex = Math.max(0, categoryOrder.indexOf(activeCategory));
      const nextIndex = Math.max(0, categoryOrder.indexOf(nextCategory));
      const direction = nextIndex >= currentIndex ? "forward" : "backward";
      const currentCards = Array.from(menuList.children).filter((card) => !card.hidden);
      const nextCards = getFilteredCards(nextCategory);
      const outgoingLayer = menuList.cloneNode(false);
      const currentHeight = menuList.offsetHeight;

      isMenuTransitionRunning = true;
      activeCategory = nextCategory;
      syncMenuControls();

      outgoingLayer.id = "";
      outgoingLayer.className = `${menuList.className} menu--transition-layer menu--outgoing ${
        direction === "forward" ? "menu--to-left" : "menu--to-right"
      }`;
      currentCards.forEach((card) => {
        outgoingLayer.appendChild(card.cloneNode(true));
      });

      menuViewport.classList.add("is-animating");
      menuViewport.appendChild(outgoingLayer);
      renderMenuCards(nextCards, false);
      menuViewport.style.height = `${Math.max(currentHeight, menuList.offsetHeight)}px`;
      menuList.classList.add(
        "menu--transition-layer",
        "menu--incoming",
        direction === "forward" ? "menu--from-right" : "menu--from-left"
      );

      requestAnimationFrame(() => {
        const onTransitionEnd = () => {
          menuList.removeEventListener("animationend", onTransitionEnd);
          renderMenuCards(nextCards, true);
          finishMenuTransition(outgoingLayer);
        };
        menuList.addEventListener("animationend", onTransitionEnd);
      });
    };

    const activateCategory = (nextCategory) => {
      const normalizedNextCategory = nextCategory || "all";
      if (normalizedNextCategory === activeCategory) return;
      if (isMenuTransitionRunning) {
        pendingCategory = normalizedNextCategory;
        return;
      }
      animateCategoryTransition(normalizedNextCategory);
    };

    const applyMenuControls = (animate = true) => {
      renderMenuCards(getFilteredCards(activeCategory), animate);
      syncMenuControls();
    };

    categoryChips.forEach((chip) => {
      chip.addEventListener("click", () => {
        closeTypeMenu();
        activateCategory(chip.dataset.type || "all");
      });
    });

    typeToggle?.addEventListener("click", () => {
      if (!typeMenu?.classList.contains("is-open")) openTypeMenu();
      else closeTypeMenu();
    });

    typeOptions.forEach((option) => {
      option.addEventListener("click", () => {
        closeTypeMenu();
        activateCategory(option.dataset.type || "all");
      });
    });

    sortToggle?.addEventListener("click", () => {
      if (!sortMenu?.classList.contains("is-open")) openSortMenu();
      else closeSortMenu();
    });

    sortOptions.forEach((option) => {
      option.addEventListener("click", () => {
        activeSort = option.dataset.sort || "popular";
        closeSortMenu();
        applyMenuControls(true);
      });
    });

    document.addEventListener("click", (event) => {
      if (!sortMenu || !sortToggle) return;
      if (sortMenu.contains(event.target) || sortToggle.contains(event.target)) return;
      closeSortMenu();
    });

    document.addEventListener("click", (event) => {
      if (!typeMenu || !typeToggle) return;
      if (typeMenu.contains(event.target) || typeToggle.contains(event.target)) return;
      closeTypeMenu();
    });

    const isMenuMobileViewport = () => window.matchMedia("(max-width: 767px)").matches;
    const collapseMobileMenuCards = (exceptCard = null) => {
      if (!isMenuMobileViewport()) return;
      menuCards.forEach((card) => {
        if (exceptCard && card === exceptCard) return;
        card.classList.remove("is-expanded");
      });
    };

    menuList.addEventListener("click", (event) => {
      if (!isMenuMobileViewport()) return;
      const card = event.target.closest(".menu-card--menu");
      if (!card || !menuList.contains(card)) return;

      // Let cart button keep its own behavior without toggling card state.
      if (event.target.closest(".add-button")) return;

      const willExpand = !card.classList.contains("is-expanded");
      collapseMobileMenuCards(willExpand ? card : null);
      card.classList.toggle("is-expanded", willExpand);
    });

    document.addEventListener("click", (event) => {
      if (!isMenuMobileViewport()) return;
      if (event.target.closest(".menu-card--menu")) return;
      collapseMobileMenuCards();
    });

    applyMenuControls(false);
  }

  if (cardNumberInput) {
    cardNumberInput.addEventListener("input", () => {
      const digits = cardNumberInput.value.replace(/\D/g, "").slice(0, 16);
      const groups = digits.match(/.{1,4}/g) || [];
      cardNumberInput.value = groups.join(" ");
    });
  }

  if (expiryInput) {
    const validateExpiryInput = () => {
      const raw = (expiryInput.value || "").trim();
      if (!raw) {
        expiryInput.setCustomValidity("");
        return;
      }
      const match = raw.match(/^(\d{2})\/(\d{2})$/);
      if (!match) {
        expiryInput.setCustomValidity("Введите срок в формате MM/YY");
        return;
      }
      const month = Number(match[1]);
      const year = Number(match[2]);
      if (month < 1 || month > 12) {
        expiryInput.setCustomValidity("Месяц должен быть от 01 до 12");
        return;
      }
      const now = new Date();
      const currentMonth = now.getMonth() + 1;
      const currentYear = now.getFullYear() % 100;
      if (year < currentYear || (year === currentYear && month < currentMonth)) {
        expiryInput.setCustomValidity("Срок карты в прошлом");
        return;
      }
      expiryInput.setCustomValidity("");
    };
    expiryInput.addEventListener("input", () => {
      const digits = expiryInput.value.replace(/\D/g, "").slice(0, 4);
      if (digits.length >= 3) {
        expiryInput.value = `${digits.slice(0, 2)}/${digits.slice(2)}`;
      } else {
        expiryInput.value = digits;
      }
      validateExpiryInput();
    });
    expiryInput.addEventListener("blur", () => {
      const digits = expiryInput.value.replace(/\D/g, "");
      if (digits.length >= 2) {
        const month = Math.min(Math.max(parseInt(digits.slice(0, 2), 10) || 1, 1), 12);
        const year = digits.slice(2, 4);
        expiryInput.value = `${String(month).padStart(2, "0")}${year ? `/${year}` : ""}`;
      }
      validateExpiryInput();
    });
  }

  if (holderInput) {
    const translitMap = {
      "А": "A", "Б": "B", "В": "V", "Г": "G", "Д": "D",
      "Е": "E", "Ё": "YO", "Ж": "ZH", "З": "Z", "И": "I",
      "Й": "Y", "К": "K", "Л": "L", "М": "M", "Н": "N",
      "О": "O", "П": "P", "Р": "R", "С": "S", "Т": "T",
      "У": "U", "Ф": "F", "Х": "KH", "Ц": "TS", "Ч": "CH",
      "Ш": "SH", "Щ": "SHCH", "Ъ": "", "Ы": "Y", "Ь": "",
      "Э": "E", "Ю": "YU", "Я": "YA",
      "а": "A", "б": "B", "в": "V", "г": "G", "д": "D",
      "е": "E", "ё": "YO", "ж": "ZH", "з": "Z", "и": "I",
      "й": "Y", "к": "K", "л": "L", "м": "M", "н": "N",
      "о": "O", "п": "P", "р": "R", "с": "S", "т": "T",
      "у": "U", "ф": "F", "х": "KH", "ц": "TS", "ч": "CH",
      "ш": "SH", "щ": "SHCH", "ъ": "", "ы": "Y", "ь": "",
      "э": "E", "ю": "YU", "я": "YA",
    };
    const normalizeHolder = (value, trimTail = false) => {
      const transliterated = Array.from(String(value || ""))
        .map((ch) => (Object.prototype.hasOwnProperty.call(translitMap, ch) ? translitMap[ch] : ch))
        .join("");
      let cleaned = transliterated
        .toUpperCase()
        .replace(/[^A-Z\s-]/g, "")
        .replace(/\s+/g, " ")
        .replace(/^\s+/, "");
      if (trimTail) {
        cleaned = cleaned.trim();
      }
      return cleaned.slice(0, 26);
    };
    holderInput.addEventListener("input", () => {
      holderInput.value = normalizeHolder(holderInput.value, false);
    });
    holderInput.addEventListener("blur", () => {
      holderInput.value = normalizeHolder(holderInput.value, true);
    });
  }

  if (phoneInputs.length) {
    const formatPhone = (value) => {
      const raw = String(value || "").trim();
      let digits = String(value || "").replace(/\D/g, "");
      if (!digits) return "+7";

      if (digits.startsWith("8") && digits.length >= 11) {
        digits = digits.slice(1);
      } else if (digits.startsWith("7") && (digits.length >= 11 || raw.startsWith("+7"))) {
        digits = digits.slice(1);
      }
      const local = digits.slice(0, 10);

      let result = "+7";
      if (local.length > 0) result += ` ${local.slice(0, 3)}`;
      if (local.length > 3) result += ` ${local.slice(3, 6)}`;
      if (local.length > 6) result += `-${local.slice(6, 8)}`;
      if (local.length > 8) result += `-${local.slice(8, 10)}`;
      return result;
    };

    const enforcePhoneMask = (input) => {
      input.value = formatPhone(input.value);
      input.setCustomValidity("");
    };

    const syncPhoneVisualState = (input) => {
      const digits = input.value.replace(/\D/g, "");
      const isValidPhone = digits.length === 11 && digits.startsWith("7");
      input.classList.toggle("is-phone-valid", isValidPhone);
      return isValidPhone;
    };

    phoneInputs.forEach((input) => {
      enforcePhoneMask(input);
      syncPhoneVisualState(input);
      input.addEventListener("focus", () => {
        if (!input.value.trim()) input.value = "+7";
        syncPhoneVisualState(input);
      });
      input.addEventListener("keydown", (event) => {
        const start = input.selectionStart ?? 0;
        const end = input.selectionEnd ?? start;
        const touchesPrefix = start <= 2;
        const deletesAll = start === 0 && end >= input.value.length;
        if ((event.key === "Backspace" || event.key === "Delete") && (touchesPrefix || deletesAll)) {
          event.preventDefault();
          input.value = formatPhone(input.value);
          input.setSelectionRange(2, 2);
          syncPhoneVisualState(input);
        }
      });
      input.addEventListener("input", () => {
        enforcePhoneMask(input);
        syncPhoneVisualState(input);
      });
      input.addEventListener("blur", () => {
        if (!syncPhoneVisualState(input)) {
          input.setCustomValidity("Введите номер в формате +7 999 000-00-00");
        } else {
          input.setCustomValidity("");
        }
        input.reportValidity();
      });
    });
  }

  const loadCart = () => {
    try {
      return JSON.parse(localStorage.getItem(cartStorageKey) || "[]");
    } catch {
      return [];
    }
  };

  const saveCart = (cart) => {
    localStorage.setItem(cartStorageKey, JSON.stringify(cart));
  };

  const normalizeCart = (cart) =>
    cart
      .map((item) => ({
        ...item,
        id: Number(item.id),
        qty: Number(item.qty) || 0,
        price: Number(item.price) || 0,
      }))
      .filter((item) => item.qty > 0);

  const menuMobileQuery = window.matchMedia("(max-width: 767px)");
  const isMenuMobile = () => Boolean(menuMobileQuery.matches && menuList && cartDrawer);
  const dragCloseRatio = 0.3;
  let mobileCartOpen = false;
  let mobileDragActive = false;
  let mobileDragStartY = 0;
  let mobileDragY = 0;
  let mobileDrawerHeight = 0;
  const mobileCartHintMinGap = 88;
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

  const updateCartUI = (options = {}) => {
    if (!cartList || !cartTotal) return;
    const previousRows = Array.from(cartList.querySelectorAll(".cart-item"));
    const previousQtyById = new Map(
      previousRows.map((row) => [Number(row.dataset.id), Number(row.dataset.qty)])
    );
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
          <span
            class="cart-item__qty${
              prevQty && prevQty !== item.qty
                ? item.qty > prevQty
                  ? " is-updated-up"
                  : " is-updated-down"
                : ""
            }"
            data-prev="${prevQty || item.qty}"
            data-next="${item.qty}"
          >${item.qty}</span>
          <button class="cart-item__btn" data-action="inc" data-id="${item.id}">+</button>
        </div>
      `;
      cartList.appendChild(row);
    });

    if (cartEmpty) {
      cartEmpty.hidden = cart.length > 0;
    }
    if (cartCheckout) {
      cartCheckout.disabled = cart.length === 0;
    }
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
    // Restart animation when user clicks quickly several times.
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
    updateCartUI({ addedId: id });
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

  cartDrawerClose?.addEventListener("click", () => {
    closeMobileCart();
  });

  cartOverlay?.addEventListener("click", () => {
    closeMobileCart();
  });

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
    if (mobileDragY > 0) {
      event.preventDefault();
    }
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
    if (cartOverlay) {
      cartOverlay.style.opacity = "";
    }
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

  menuMobileQuery.addEventListener("change", () => {
    mobileCartOpen = false;
    hideMobileCartHint();
    setDrawerState(normalizeCart(loadCart()).length > 0);
  });

  window.addEventListener("resize", () => {
    updateMobileCartHint();
  });

  cartCheckout?.addEventListener("click", () => {
    const cart = loadCart();
    if (!cart.length) {
      if (cartTotal) cartTotal.textContent = "0";
      return;
    }
    const checkoutUrl = cartCheckout.dataset.checkoutUrl || "/checkout";
    window.location.href = checkoutUrl;
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

  // Checkout page: items list + comment + serving settings
  if (checkoutForm && checkoutItemsNode) {
    const commentStorageKey = "checkout_comment";
    const menuCatalogNode = document.getElementById("menuCatalogJson");
    const menuCatalog = (() => {
      try {
        const parsed = JSON.parse(menuCatalogNode?.textContent || "[]");
        if (!Array.isArray(parsed)) return [];
        return parsed;
      } catch {
        return [];
      }
    })();
    const menuById = new Map(menuCatalog.map((item) => [Number(item.id), item]));
    const goToPaymentDefaultText = goToPayment?.textContent?.trim() || "Перейти к оплате";
    const goToPaymentInitiallyDisabled = Boolean(goToPayment?.disabled);
    const normalizeCheckoutItem = (item) => {
      const id = Number(item.id);
      const fromCatalog = menuById.get(id) || {};
      return {
        ...item,
        id,
        name: item.name || fromCatalog.name || "Позиция",
        price: Number(item.price) || Number(fromCatalog.price) || 0,
        qty: Number(item.qty) || 0,
        photo: item.photo || fromCatalog.photo || "",
      };
    };
    const getCheckoutCart = () =>
      loadCart()
        .map(normalizeCheckoutItem)
        .filter((item) => Number(item.qty) > 0);

    const resetGoToPaymentState = () => {
      if (!goToPayment) return;
      goToPayment.classList.remove("is-loading");
      goToPayment.textContent = goToPaymentDefaultText;
      const cartLength = getCheckoutCart().length;
      goToPayment.disabled = goToPaymentInitiallyDisabled || cartLength === 0;
    };

    const updateCommentCounter = () => {
      if (!checkoutComment || !checkoutCommentCount) return;
      checkoutCommentCount.textContent = String(checkoutComment.value.length);
    };

    const renderCheckout = () => {
      const cart = getCheckoutCart();
      const total = cart.reduce((sum, item) => sum + Number(item.qty) * Number(item.price), 0);
      const balance = Number(availablePoints?.textContent || 0);
      const pointsApplied = usePoints?.checked ? Math.min(balance, total) : 0;
      const payableTotal = Math.max(0, total - pointsApplied);
      if (checkoutItemsJson) {
        checkoutItemsJson.value = JSON.stringify(
          cart.map((item) => ({ id: Number(item.id), qty: Number(item.qty) }))
        );
      }

      if (checkoutItemsTotal) checkoutItemsTotal.textContent = String(total);
      if (checkoutTotal) checkoutTotal.textContent = String(total);
      if (checkoutPointsApplied) checkoutPointsApplied.textContent = String(pointsApplied);
      if (checkoutPayable) checkoutPayable.textContent = String(payableTotal);
      if (checkoutEmpty) {
        checkoutEmpty.hidden = cart.length > 0;
        checkoutEmpty.style.display = cart.length > 0 ? "none" : "";
      }
      if (goToPayment) goToPayment.disabled = goToPaymentInitiallyDisabled || cart.length === 0;

      checkoutItemsNode.innerHTML = "";
      cart.forEach((item) => {
        const row = document.createElement("div");
        row.className = "checkout-item";
        row.innerHTML = `
          <div class="checkout-item__left">
            ${
              item.photo
                ? `<img class="checkout-item__photo" src="/static/${item.photo}" alt="${item.name}" />`
                : `<div class="checkout-item__photo checkout-item__photo--fallback"></div>`
            }
            <div class="checkout-item__meta">
              <p class="checkout-item__name">${item.name}</p>
              <p class="checkout-item__sub">${item.price} ₽</p>
            </div>
          </div>
          <div class="checkout-item__controls">
            <span class="checkout-item__qty">${item.qty}</span>
            <span class="checkout-item__sub">× ${item.price} ₽</span>
            <strong>${item.qty * item.price} ₽</strong>
          </div>
        `;
        checkoutItemsNode.appendChild(row);
      });

      if (checkoutSummaryList) {
        checkoutSummaryList.innerHTML = "";
        cart.forEach((item) => {
          const brief = document.createElement("div");
          brief.className = "checkout-brief";
          brief.innerHTML = `<span>${item.name}</span><span>× ${item.qty}</span>`;
          checkoutSummaryList.appendChild(brief);
        });
      }
    };

    const storedComment = sessionStorage.getItem(commentStorageKey) || "";
    if (checkoutComment) {
      checkoutComment.value = storedComment.slice(0, 300);
      updateCommentCounter();
      checkoutComment.addEventListener("input", () => {
        if (checkoutComment.value.length > 300) {
          checkoutComment.value = checkoutComment.value.slice(0, 300);
        }
        sessionStorage.setItem(commentStorageKey, checkoutComment.value);
        updateCommentCounter();
      });
    }

    const updateServingCustom = () => {
      if (!serveCustomTime) return;
      const customChecked = Boolean(
        checkoutForm.querySelector('input[name="serve_mode"][value="custom"]')?.checked
      );
      serveCustomTime.disabled = !customChecked;
      serveCustomTime.required = customChecked;
      if (customChecked && !serveCustomTime.value && serveCustomTime.min) {
        serveCustomTime.value = serveCustomTime.min;
      }
    };

    checkoutForm.querySelectorAll('input[name="serve_mode"]').forEach((radio) => {
      radio.addEventListener("change", updateServingCustom);
    });
    usePoints?.addEventListener("change", renderCheckout);
    updateServingCustom();

    checkoutForm.addEventListener("submit", (event) => {
      const cart = getCheckoutCart();
      if (!cart.length) {
        event.preventDefault();
        resetGoToPaymentState();
        return;
      }
      const customChecked = Boolean(
        checkoutForm.querySelector('input[name="serve_mode"][value="custom"]')?.checked
      );
      if (customChecked && serveCustomTime && !serveCustomTime.value) {
        event.preventDefault();
        resetGoToPaymentState();
        return;
      }
      if (checkoutComment) {
        sessionStorage.setItem(commentStorageKey, checkoutComment.value);
      }
      if (goToPayment) {
        goToPayment.classList.add("is-loading");
        goToPayment.disabled = true;
        goToPayment.textContent = "Переходим...";
      }
    });

    window.addEventListener("pageshow", () => {
      resetGoToPaymentState();
      renderCheckout();
    });

    const cards = Array.from(document.querySelectorAll(".checkout-main .checkout-card"));
    cards.forEach((card, index) => {
      card.classList.add("checkout-card--stagger");
      card.style.animationDelay = `${index * 60}ms`;
    });
    document.getElementById("checkoutHead")?.classList.add("checkout-head--show");
    document.getElementById("checkoutTotalPanel")?.classList.add("checkout-total--show");

    renderCheckout();
  }

  // Payment page: loading + success/error states
  const paymentConfirmForm = document.getElementById("paymentConfirmForm");
  const payNowButton = document.getElementById("payNowButton");
  const paymentCardMain = document.getElementById("paymentCardMain");
  const paymentSuccess = document.getElementById("paymentSuccess");
  const paymentError = document.getElementById("paymentError");
  const retryPaymentButton = document.getElementById("retryPaymentButton");
  const paymentHead = document.getElementById("paymentHead");
  const paymentTotalBlock = document.getElementById("paymentTotalBlock");
  paymentHead?.classList.add("payment-head--show");
  paymentCardMain?.classList.add("payment-card--show");
  paymentTotalBlock?.classList.add("payment-total--show");
  Array.from(paymentCardMain?.querySelectorAll(".payment-block") || []).forEach((block, index) => {
    if (block.id === "paymentTotalBlock") return;
    block.classList.add("payment-block--stagger");
    block.style.animationDelay = `${index * 70}ms`;
  });

  if (paymentConfirmForm && payNowButton) {
    const setLoading = (loading) => {
      payNowButton.disabled = loading || payNowButton.hasAttribute("data-lock");
      payNowButton.classList.toggle("is-loading", loading);
      paymentCardMain?.classList.toggle("is-processing", loading);
      const label = payNowButton.querySelector(".pay-btn__label");
      if (label) label.textContent = loading ? "Обработка..." : "Оплатить";
    };

    const hideAllPaymentStates = () => {
      paymentCardMain?.setAttribute("hidden", "true");
      paymentSuccess?.setAttribute("hidden", "true");
      paymentError?.setAttribute("hidden", "true");
    };

    const showMainState = () => {
      hideAllPaymentStates();
      paymentCardMain?.removeAttribute("hidden");
      paymentCardMain?.classList.remove("payment-card--show");
      void paymentCardMain?.offsetWidth;
      paymentCardMain?.classList.add("payment-card--show");
    };

    const showErrorState = async () => {
      paymentCardMain?.classList.remove("is-shake");
      void paymentCardMain?.offsetWidth;
      paymentCardMain?.classList.add("is-shake");
      await new Promise((resolve) => window.setTimeout(resolve, 220));
      hideAllPaymentStates();
      paymentError?.removeAttribute("hidden");
      paymentError?.classList.remove("is-shake");
      void paymentError?.offsetWidth;
      paymentError?.classList.add("is-shake");
      setLoading(false);
    };

    const showSuccessState = () => {
      hideAllPaymentStates();
      paymentSuccess?.removeAttribute("hidden");
      paymentSuccess?.classList.add("payment-result--show");
      localStorage.removeItem("cart");
      sessionStorage.removeItem("checkout_comment");
      payNowButton.setAttribute("data-lock", "1");
      setLoading(false);
    };

    const resetPaymentLoadingState = () => {
      const successVisible = paymentSuccess && !paymentSuccess.hasAttribute("hidden");
      if (successVisible) return;
      setLoading(false);
    };

    paymentConfirmForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (payNowButton.disabled) return;
      setLoading(true);
      const delayMs = 1200 + Math.floor(Math.random() * 700);
      await new Promise((resolve) => window.setTimeout(resolve, delayMs));

      const response = await fetch(paymentConfirmForm.action, {
        method: "POST",
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          ...(getCsrfToken() ? { "X-CSRF-Token": getCsrfToken() } : {}),
        },
        body: new FormData(paymentConfirmForm),
      }).catch(() => null);
      if (!response || !response.ok) {
        await showErrorState();
        return;
      }
      const result = await response.json().catch(() => ({}));
      if (!result.ok) {
        await showErrorState();
        return;
      }
      showSuccessState();
    });

    retryPaymentButton?.addEventListener("click", () => {
      showMainState();
      payNowButton.removeAttribute("data-lock");
      setLoading(false);
    });

    window.addEventListener("pageshow", () => {
      resetPaymentLoadingState();
    });

    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) resetPaymentLoadingState();
    });
  }

  const params = new URLSearchParams(window.location.search);
  if (params.get("paid") === "1") {
    localStorage.removeItem("cart");
    localStorage.removeItem("delivery_cart");
    sessionStorage.removeItem("checkout_comment");
  }

  updateCartUI();
});
