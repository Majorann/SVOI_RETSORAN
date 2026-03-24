import { stagger } from "./modules/core.js";
import { navigateWithAuth, setupAuthTokenBridge } from "./modules/authToken.js";
import { setupMenuHoverMood } from "./modules/menuHoverMood.js";
import { setupBottomNavMotion } from "./modules/bottomNavMotion.js";
import { setupTableTooltip } from "./modules/tableTooltip.js";
import { setupOrderStatusBar } from "./modules/orderStatusBar.js";
import { setupPointsBalanceCard } from "./modules/pointsBalanceCard.js";
import { setupDeliveryFlow } from "./modules/deliveryFlow.js";
import { setupPaymentAddAccordion } from "./modules/paymentAddAccordion.js";
import { setupProfileNameFit } from "./modules/profileNameFit.js";
window.addEventListener("DOMContentLoaded", async () => {
  const authSessionSyncPending = await setupAuthTokenBridge();
  if (authSessionSyncPending) return;
  stagger(".news-card", 140);
  stagger(".menu-card", 120);
  setupPointsBalanceCard();
  setupBottomNavMotion();
  setupTableTooltip();
  setupMenuHoverMood();
  setupOrderStatusBar();
  setupPaymentAddAccordion();
  setupProfileNameFit();
  if (document.body.classList.contains("page-index")) {
    const { setupIndexSummaryHydration } = await import("./modules/indexSummaryHydration.js");
    await setupIndexSummaryHydration(setupOrderStatusBar);
  }
  setupDeliveryFlow();

  const newsCards = Array.from(document.querySelectorAll(".news-card"));
  if (newsCards.length) {
    const newsAnimationTimers = new WeakMap();
    const newsTouchQuery = window.matchMedia("(hover: none) and (pointer: coarse)");
    const isTouchNewsMode = () => newsTouchQuery.matches;
    const syncNewsCardMetrics = () => {
      newsCards.forEach((card) => {
        const text = card.querySelector(".news-card__text");
        const details = card.querySelector(".news-card__details");
        const wasExpanded = card.classList.contains("is-expanded");
        card.classList.remove("is-expanded");
        const collapsedHeight = details ? details.scrollHeight : 0;

        card.classList.add("is-expanded");
        const expandedHeight = details ? details.scrollHeight : collapsedHeight;

        card.classList.toggle("is-expanded", wasExpanded);
        card.style.setProperty("--news-details-collapsed-height", `${collapsedHeight}px`);
        card.style.setProperty("--news-details-expanded-height", `${expandedHeight}px`);
        if (text) {
          card.style.setProperty("--news-text-expanded-height", `${text.scrollHeight}px`);
        }
      });
    };
    const clearNewsTimer = (card) => {
      const timerId = newsAnimationTimers.get(card);
      if (timerId) {
        window.clearTimeout(timerId);
        newsAnimationTimers.delete(card);
      }
    };
    const pulseNewsState = (card, stateClass, durationMs) => {
      clearNewsTimer(card);
      card.classList.remove("is-expanding", "is-collapsing");
      if (!stateClass) return;
      card.classList.add(stateClass);
      const timerId = window.setTimeout(() => {
        card.classList.remove(stateClass);
        newsAnimationTimers.delete(card);
      }, durationMs);
      newsAnimationTimers.set(card, timerId);
    };
    const setNewsExpanded = (card, expanded) => {
      const isExpanded = card.classList.contains("is-expanded");
      if (isExpanded === expanded) return;
      if (expanded) {
        card.classList.remove("is-collapsing");
        pulseNewsState(card, "is-expanding", 340);
      } else {
        card.classList.remove("is-expanding");
        pulseNewsState(card, "is-collapsing", 240);
      }
      card.classList.toggle("is-expanded", expanded);
      card.setAttribute("aria-expanded", expanded ? "true" : "false");
    };

    const collapseNewsCards = () => {
      newsCards.forEach((card) => {
        setNewsExpanded(card, false);
      });
    };

    newsCards.forEach((card) => {
      card.addEventListener("click", (event) => {
        const cardLink = card.dataset.link;
        if (cardLink) {
          navigateWithAuth(cardLink);
          return;
        }
        if (!isTouchNewsMode()) return;
        const willExpand = !card.classList.contains("is-expanded");
        setNewsExpanded(card, willExpand);
      });

      card.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        const cardLink = card.dataset.link;
        if (cardLink) {
          navigateWithAuth(cardLink);
          return;
        }
        if (!isTouchNewsMode()) return;
        const willExpand = !card.classList.contains("is-expanded");
        setNewsExpanded(card, willExpand);
      });
    });

    document.addEventListener("click", (event) => {
      if (event.target.closest(".news-card")) return;
      collapseNewsCards();
    });

    syncNewsCardMetrics();
    window.addEventListener("resize", syncNewsCardMetrics);
    const syncNewsInteractionMode = () => {
      if (!isTouchNewsMode()) {
        collapseNewsCards();
      }
    };
    if (typeof newsTouchQuery.addEventListener === "function") {
      newsTouchQuery.addEventListener("change", syncNewsInteractionMode);
    } else if (typeof newsTouchQuery.addListener === "function") {
      newsTouchQuery.addListener(syncNewsInteractionMode);
    }
    window.addEventListener("resize", syncNewsInteractionMode);
  }

  const menuViewport = document.getElementById("menuViewport");
  const menuList = document.getElementById("menuList") || document.querySelector(".menu");
  const menuCards = Array.from(document.querySelectorAll(".menu-card--menu"));
  const categoryChips = Array.from(document.querySelectorAll(".menu-chip"));
  const overflowCategoryControl = document.getElementById("overflowCategoryControl");
  const overflowCategoryToggle = document.getElementById("overflowCategoryToggle");
  const overflowCategoryMenu = document.getElementById("overflowCategoryMenu");
  const overflowCategoryValue = document.getElementById("overflowCategoryValue");
  const mobileMoreControl = document.getElementById("mobileMoreControl");
  const mobileMoreToggle = document.getElementById("mobileMoreToggle");
  const mobileMoreMenu = document.getElementById("mobileMoreMenu");
  const mobileMoreValue = document.getElementById("mobileMoreValue");
  const sortToggle = document.getElementById("sortToggle");
  const sortMenu = document.getElementById("sortMenu");
  const sortOptions = Array.from(document.querySelectorAll(".sort-option"));
  const sortValue = document.getElementById("sortValue");
  const menuSearchInput = document.getElementById("menuSearchInput");
  const cartMenuSearchInput = document.getElementById("cartMenuSearchInput");
  const menuEmptyState = document.getElementById("menuEmptyState");
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
  const desktopMenuHands = document.querySelector(".menu-side-hands");

  const syncDesktopMenuHands = () => {
    if (!desktopMenuHands || !document.body.classList.contains("page-menu")) return;
    if (window.innerWidth < 1180) {
      desktopMenuHands.style.removeProperty("left");
      desktopMenuHands.style.removeProperty("width");
      return;
    }

    const dpr = Math.max(window.devicePixelRatio || 1, 1);
    const zoomFactor = Math.min(Math.max((dpr - 1) / 1, 0), 1);
    const widthPx = Math.round(1700 - zoomFactor * 180);
    const leftPercent = 52 + zoomFactor * 4;
    const leftOffsetPx = 260 + zoomFactor * 120;

    desktopMenuHands.style.width = `${widthPx}px`;
    desktopMenuHands.style.left = `calc(${leftPercent}% + ${leftOffsetPx}px)`;
  };

  syncDesktopMenuHands();
  window.addEventListener("resize", syncDesktopMenuHands);
  if (menuList && menuCards.length) {
    const { setupMenuCatalog } = await import("./modules/menuCatalog.js");
    setupMenuCatalog({
      menuViewport,
      menuList,
      menuCards,
      categoryChips,
      overflowCategoryControl,
      overflowCategoryToggle,
      overflowCategoryMenu,
      overflowCategoryValue,
      mobileMoreControl,
      mobileMoreToggle,
      mobileMoreMenu,
      mobileMoreValue,
      sortToggle,
      sortMenu,
      sortOptions,
      sortValue,
      searchInputs: [menuSearchInput, cartMenuSearchInput].filter(Boolean),
      emptyState: menuEmptyState,
    });
  }

  if (cardNumberInput || expiryInput || holderInput || phoneInputs.length) {
    const { setupFormEnhancements } = await import("./modules/formEnhancements.js");
    setupFormEnhancements({
      cardNumberInput,
      expiryInput,
      holderInput,
      phoneInputs,
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

  const params = new URLSearchParams(window.location.search);
  if (params.get("paid") === "1") {
    localStorage.removeItem("cart");
    localStorage.removeItem("delivery_cart");
    sessionStorage.removeItem("checkout_comment");
  }

  const { setupCartDrawer } = await import("./modules/cartDrawer.js");
  setupCartDrawer({
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
  });

  const paymentConfirmForm = document.getElementById("paymentConfirmForm");
  const payNowButton = document.getElementById("payNowButton");
  const paymentCardMain = document.getElementById("paymentCardMain");
  const paymentSuccess = document.getElementById("paymentSuccess");
  const paymentError = document.getElementById("paymentError");
  const retryPaymentButton = document.getElementById("retryPaymentButton");
  const paymentHead = document.getElementById("paymentHead");
  const paymentTotalBlock = document.getElementById("paymentTotalBlock");
  let setupCheckoutPage = null;
  let setupPaymentPage = null;
  if ((checkoutForm && checkoutItemsNode) || paymentHead || paymentConfirmForm) {
    ({ setupCheckoutPage, setupPaymentPage } = await import("./modules/checkoutPaymentFlow.js"));
  }
  if (setupCheckoutPage) {
    setupCheckoutPage({
      checkoutForm,
      checkoutItemsNode,
      checkoutItemsTotal,
      checkoutTotal,
      checkoutItemsJson,
      checkoutEmpty,
      checkoutSummaryList,
      checkoutComment,
      checkoutCommentCount,
      usePoints,
      availablePoints,
      checkoutPointsApplied,
      checkoutBonusEarned: document.getElementById("checkoutBonusEarned"),
      checkoutPayable,
      checkoutPromoHighlight: document.getElementById("checkoutPromoHighlight"),
      checkoutPromoList: document.getElementById("checkoutPromoList"),
      checkoutPromoMeta: document.getElementById("checkoutPromoMeta"),
      checkoutPromoChip: document.getElementById("checkoutPromoChip"),
      goToPayment,
      serveCustomTime,
      loadCart,
    });
  }

  // Payment page: loading + success/error states
  if (setupPaymentPage) {
    setupPaymentPage({
      paymentConfirmForm,
      payNowButton,
      paymentCardMain,
      paymentSuccess,
      paymentError,
      retryPaymentButton,
      paymentHead,
      paymentTotalBlock,
    });
  }

});
