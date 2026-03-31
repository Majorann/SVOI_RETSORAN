import { stagger } from "../modules/core.js";
import { setupCartDrawer } from "../modules/cartDrawer.js";
import { setupMenuCatalog } from "../modules/menuCatalog.js";
import { setupMenuHoverMood } from "../modules/menuHoverMood.js";
import { navigateWithAuth } from "../modules/authToken.js";
import { bootstrapPage } from "../shared/basePage.js";
import { loadCart, normalizeCart, saveCart } from "../shared/checkoutCart.js";

const syncDesktopMenuHands = () => {
  const desktopMenuHands = document.querySelector(".menu-side-hands");
  if (!desktopMenuHands || !document.body.classList.contains("page-menu")) return;
  if (window.innerWidth < 1180) {
    desktopMenuHands.style.removeProperty("left");
    desktopMenuHands.style.removeProperty("width");
    return;
  }

  const dpr = Math.max(window.devicePixelRatio || 1, 1);
  const zoomFactor = Math.min(Math.max((dpr - 1) / 1, 0), 1);
  const widthPx = Math.round(1700 - zoomFactor * 180);
  const leftPercent = 52 + (zoomFactor * 4);
  const leftOffsetPx = 260 + (zoomFactor * 120);

  desktopMenuHands.style.width = `${widthPx}px`;
  desktopMenuHands.style.left = `calc(${leftPercent}% + ${leftOffsetPx}px)`;
};

bootstrapPage(async () => {
  stagger(".menu-card", 120);
  setupMenuHoverMood();

  const menuViewport = document.getElementById("menuViewport");
  const menuList = document.getElementById("menuList") || document.querySelector(".menu");
  const menuCards = Array.from(document.querySelectorAll(".menu-card--menu"));

  syncDesktopMenuHands();
  window.addEventListener("resize", syncDesktopMenuHands);

  if (menuList && menuCards.length) {
    setupMenuCatalog({
      menuViewport,
      menuList,
      menuCards,
      categoryChips: Array.from(document.querySelectorAll(".menu-chip")),
      overflowCategoryControl: document.getElementById("overflowCategoryControl"),
      overflowCategoryToggle: document.getElementById("overflowCategoryToggle"),
      overflowCategoryMenu: document.getElementById("overflowCategoryMenu"),
      overflowCategoryValue: document.getElementById("overflowCategoryValue"),
      mobileMoreControl: document.getElementById("mobileMoreControl"),
      mobileMoreToggle: document.getElementById("mobileMoreToggle"),
      mobileMoreMenu: document.getElementById("mobileMoreMenu"),
      mobileMoreValue: document.getElementById("mobileMoreValue"),
      sortToggle: document.getElementById("sortToggle"),
      sortMenu: document.getElementById("sortMenu"),
      sortOptions: Array.from(document.querySelectorAll(".sort-option")),
      sortValue: document.getElementById("sortValue"),
      searchInputs: [
        document.getElementById("menuSearchInput"),
        document.getElementById("cartMenuSearchInput"),
      ].filter(Boolean),
      emptyState: document.getElementById("menuEmptyState"),
    });
  }

  setupCartDrawer({
    menuList,
    cartDrawer: document.getElementById("cartDrawer"),
    cartOverlay: document.getElementById("cartOverlay"),
    cartOverlayHint: document.getElementById("cartOverlayHint"),
    cartList: document.getElementById("cartList"),
    cartEmpty: document.getElementById("cartEmpty"),
    cartTotal: document.getElementById("cartTotal"),
    cartCheckout: document.getElementById("cartCheckout"),
    cartDrawerClose: document.getElementById("cartDrawerClose"),
    cartDrawerHeader: document.getElementById("cartDrawer")?.querySelector(".cart-drawer__header"),
    menuCartFab: document.getElementById("menuCartFab"),
    menuCartFabBadge: document.getElementById("menuCartFabBadge"),
    loadCart,
    saveCart,
    normalizeCart,
    navigateWithAuth,
  });
});
