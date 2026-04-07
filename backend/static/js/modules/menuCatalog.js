const setupMenuCatalog = ({
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
  priceToggle,
  priceMenu,
  priceOverlay,
  priceOverlayHint,
  priceValue,
  priceMinInput,
  priceMaxInput,
  priceMinRange,
  priceMaxRange,
  priceTrackFill,
  priceReset,
  sortToggle,
  sortMenu,
  sortOptions,
  sortValue,
  searchInputs = [],
  emptyState,
}) => {
  if (!menuList || !Array.isArray(menuCards) || !menuCards.length) {
    return;
  }

  const sortLabels = {
    alpha: "От А до Я",
    popular: "По популярности",
    "price-asc": "Цена ↑",
    "price-desc": "Цена ↓",
  };
  const PRIMARY_MENU_CATEGORIES = ["Горячие блюда", "Закуски"];
  let activeCategory = "all";
  let activeSort = "alpha";
  let searchQuery = "";
  let isMenuTransitionRunning = false;
  let pendingCategory = null;
  let overflowMenuMountedToBody = false;
  let mobileMoreMenuMountedToBody = false;
  let priceMenuMountedToBody = false;
  const normalizedSearchInputs = Array.isArray(searchInputs)
    ? searchInputs.filter(Boolean)
    : searchInputs
      ? [searchInputs]
      : [];
  const normalizeType = (value) =>
    String(value || "")
      .toLowerCase()
      .replace(/\s+/g, " ")
      .trim();
  const getNumber = (value) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  };
  const primaryCategorySet = new Set(PRIMARY_MENU_CATEGORIES.map((category) => normalizeType(category)));
  const discoveredCategories = Array.from(
    new Map(
      menuCards
        .map((card) => String(card.dataset.type || "").trim())
        .filter(Boolean)
        .map((category) => [normalizeType(category), category])
    ).values()
  );
  const overflowCategories = discoveredCategories.filter(
    (category) => !primaryCategorySet.has(normalizeType(category))
  );
  const categoryOrder = Array.from(new Set(["all", ...PRIMARY_MENU_CATEGORIES, ...discoveredCategories]));
  const categoryLabels = new Map([
    ...categoryChips.map((chip) => [chip.dataset.type || "all", chip.textContent.trim() || "Все"]),
    ...overflowCategories.map((category) => [category, category]),
  ]);
  const priceValues = menuCards
    .map((card) => getNumber(card.dataset.price))
    .filter((value) => Number.isFinite(value) && value >= 0);
  const minAvailablePrice = priceValues.length ? Math.min(...priceValues) : 0;
  const maxAvailablePrice = priceValues.length ? Math.max(...priceValues) : 0;
  let activePriceMin = minAvailablePrice;
  let activePriceMax = maxAvailablePrice;
  let overflowOptions = [];
  const VALUE_SWAP_OUT_MS = 150;

  const formatPriceNumber = (value) =>
    new Intl.NumberFormat("ru-RU", {
      maximumFractionDigits: 0,
    }).format(getNumber(value));

  const isMobileViewport = () => window.matchMedia("(max-width: 767px)").matches;
  let priceOverlayHideTimer = 0;
  let priceHintHideTimer = 0;
  let priceMenuRestoreTimer = 0;

  const formatPriceLabel = () => {
    const hasCustomMin = activePriceMin > minAvailablePrice;
    const hasCustomMax = activePriceMax < maxAvailablePrice;
    if (hasCustomMin && hasCustomMax) {
      return `${formatPriceNumber(activePriceMin)}-${formatPriceNumber(activePriceMax)} ₽`;
    }
    if (hasCustomMin) {
      return `от ${formatPriceNumber(activePriceMin)} ₽`;
    }
    if (hasCustomMax) {
      return `до ${formatPriceNumber(activePriceMax)} ₽`;
    }
    return "";
  };

  const hasActivePriceFilter = () =>
    activePriceMin > minAvailablePrice || activePriceMax < maxAvailablePrice;

  const updateToggleWidth = (toggle) => {
    if (!toggle) return;
    if (toggle._widthFrame) {
      cancelAnimationFrame(toggle._widthFrame);
    }
    toggle._widthFrame = requestAnimationFrame(() => {
      const probe = toggle.cloneNode(true);
      probe.style.position = "fixed";
      probe.style.left = "-9999px";
      probe.style.top = "0";
      probe.style.width = "auto";
      probe.style.maxWidth = "none";
      probe.style.visibility = "hidden";
      probe.style.pointerEvents = "none";
      probe.style.transition = "none";
      document.body.appendChild(probe);
      const measuredWidth = Math.ceil(probe.scrollWidth);
      probe.remove();
      toggle._widthFrame = requestAnimationFrame(() => {
        toggle.style.width = `${measuredWidth}px`;
      });
    });
  };

  const animateToggleValue = (toggle, valueNode, nextText, isActive) => {
    if (!toggle || !valueNode) return;
    const normalizedText = isActive ? String(nextText || "").trim() : "";
    const currentText = valueNode.dataset.renderedValue ?? valueNode.textContent ?? "";
    const currentActive = toggle.classList.contains("has-selection");

    if (valueNode._swapTimer) {
      clearTimeout(valueNode._swapTimer);
      valueNode._swapTimer = 0;
    }

    if (currentText === normalizedText && currentActive === isActive) {
      valueNode.hidden = false;
      updateToggleWidth(toggle);
      return;
    }

    const commitNextValue = () => {
      valueNode.textContent = normalizedText;
      valueNode.dataset.renderedValue = normalizedText;
      valueNode.hidden = false;
      toggle.classList.toggle("has-selection", isActive);
      updateToggleWidth(toggle);
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          valueNode.classList.remove("is-swapping");
        });
      });
    };

    valueNode.hidden = false;
    valueNode.classList.add("is-swapping");

    if (currentText) {
      valueNode._swapTimer = window.setTimeout(() => {
        valueNode._swapTimer = 0;
        commitNextValue();
      }, VALUE_SWAP_OUT_MS);
      return;
    }

    commitNextValue();
  };

  const buildCategoryOptionButtons = (categories, menu, onSelect) =>
    categories.map((category) => {
      const optionValue = category === "all" ? "all" : category;
      const optionLabel = categoryLabels.get(optionValue) || category;
      const option = document.createElement("button");
      option.className = "filter-option";
      option.type = "button";
      option.dataset.type = optionValue;
      option.innerHTML = `
        <span>${optionLabel}</span>
        <span class="sort-option__check">✓</span>
      `;
      option.addEventListener("click", () => {
        onSelect(optionValue);
      });
      menu.appendChild(option);
      return option;
    });

  const buildOverflowOptions = () => {
    if (!overflowCategoryMenu) {
      return;
    }
    overflowCategoryMenu.innerHTML = "";
    overflowOptions = buildCategoryOptionButtons(overflowCategories, overflowCategoryMenu, (category) => {
      closeOverflowMenu();
      activateCategory(category);
    });
    overflowCategoryControl.hidden = overflowCategories.length === 0;
    if (mobileMoreMenu) {
      mobileMoreMenu.innerHTML = "";
      buildCategoryOptionButtons(categoryOrder, mobileMoreMenu, (category) => {
        closeMobileMoreMenu();
        activateCategory(category);
      });
    }
    if (mobileMoreControl) {
      mobileMoreControl.hidden = discoveredCategories.length === 0;
    }
  };

  const positionFloatingMenu = (toggle, menu) => {
    if (!toggle || !menu) return;
    const toggleRect = toggle.getBoundingClientRect();
    const menuRect = menu.getBoundingClientRect();
    const viewportWidth = window.innerWidth || document.documentElement.clientWidth || 0;
    const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 0;
    const preferredTop = toggleRect.bottom + 6;
    const menuWidth = Math.max(toggleRect.width, menuRect.width || 178);
    const alignEnd = menu.dataset.align === "end";
    let left = alignEnd ? toggleRect.right - menuWidth : toggleRect.left;
    let top = preferredTop;

    if (left < 12) {
      left = 12;
    }

    if (left + menuWidth > viewportWidth - 12) {
      left = Math.max(12, viewportWidth - menuWidth - 12);
    }

    const maxHeight = Math.max(140, viewportHeight - preferredTop - 12);
    menu.style.minWidth = `${Math.round(toggleRect.width)}px`;
    menu.style.maxWidth = `${Math.round(Math.max(menuWidth, toggleRect.width))}px`;
    menu.style.maxHeight = `${Math.round(maxHeight)}px`;
    menu.style.left = `${Math.round(left)}px`;
    menu.style.top = `${Math.round(top)}px`;
  };

  const mountOverflowMenuToBody = () => {
    if (!overflowCategoryMenu || overflowMenuMountedToBody) return;
    document.body.appendChild(overflowCategoryMenu);
    overflowCategoryMenu.classList.add("sort-menu--portal");
    overflowMenuMountedToBody = true;
  };

  const restoreOverflowMenu = () => {
    if (!overflowCategoryMenu || !overflowCategoryControl || !overflowMenuMountedToBody) return;
    overflowCategoryControl.appendChild(overflowCategoryMenu);
    overflowCategoryMenu.classList.remove("sort-menu--portal");
    overflowCategoryMenu.style.removeProperty("left");
    overflowCategoryMenu.style.removeProperty("top");
    overflowCategoryMenu.style.removeProperty("min-width");
    overflowCategoryMenu.style.removeProperty("max-width");
    overflowCategoryMenu.style.removeProperty("max-height");
    overflowMenuMountedToBody = false;
  };

  const mountMobileMoreMenuToBody = () => {
    if (!mobileMoreMenu || mobileMoreMenuMountedToBody) return;
    document.body.appendChild(mobileMoreMenu);
    mobileMoreMenu.classList.add("sort-menu--portal");
    mobileMoreMenuMountedToBody = true;
  };

  const restoreMobileMoreMenu = () => {
    if (!mobileMoreMenu || !mobileMoreControl || !mobileMoreMenuMountedToBody) return;
    mobileMoreControl.appendChild(mobileMoreMenu);
    mobileMoreMenu.classList.remove("sort-menu--portal");
    mobileMoreMenu.style.removeProperty("left");
    mobileMoreMenu.style.removeProperty("top");
    mobileMoreMenu.style.removeProperty("min-width");
    mobileMoreMenu.style.removeProperty("max-width");
    mobileMoreMenu.style.removeProperty("max-height");
    mobileMoreMenuMountedToBody = false;
  };

  const mountPriceMenuToBody = () => {
    if (!priceMenu || priceMenuMountedToBody) return;
    document.body.appendChild(priceMenu);
    priceMenu.classList.add("sort-menu--portal");
    priceMenuMountedToBody = true;
  };

  const restorePriceMenu = () => {
    const priceControl = priceToggle?.closest(".price-control");
    if (!priceMenu || !priceControl || !priceMenuMountedToBody) return;
    if (priceMenuRestoreTimer) {
      window.clearTimeout(priceMenuRestoreTimer);
      priceMenuRestoreTimer = 0;
    }
    priceControl.appendChild(priceMenu);
    priceMenu.classList.remove("sort-menu--portal");
    priceMenu.classList.remove("sort-menu--mobile-sheet");
    priceMenu.style.removeProperty("left");
    priceMenu.style.removeProperty("top");
    priceMenu.style.removeProperty("min-width");
    priceMenu.style.removeProperty("max-width");
    priceMenu.style.removeProperty("max-height");
    priceMenuMountedToBody = false;
  };

  const showPriceOverlay = () => {
    if (!priceOverlay || !isMobileViewport()) return;
    if (priceOverlayHideTimer) {
      window.clearTimeout(priceOverlayHideTimer);
      priceOverlayHideTimer = 0;
    }
    priceOverlay.hidden = false;
    requestAnimationFrame(() => {
      priceOverlay.classList.add("is-open");
    });
    document.body.classList.add("menu-price-open-mobile");
  };

  const hidePriceOverlay = () => {
    if (!priceOverlay) return;
    priceOverlay.classList.remove("is-open");
    document.body.classList.remove("menu-price-open-mobile");
    if (priceOverlayHideTimer) {
      window.clearTimeout(priceOverlayHideTimer);
    }
    priceOverlayHideTimer = window.setTimeout(() => {
      if (!priceOverlay.classList.contains("is-open")) {
      priceOverlay.hidden = true;
      }
      priceOverlayHideTimer = 0;
    }, 220);
  };

  const showPriceOverlayHint = () => {
    if (!priceOverlayHint || !isMobileViewport()) return;
    if (priceHintHideTimer) {
      window.clearTimeout(priceHintHideTimer);
      priceHintHideTimer = 0;
    }
    priceOverlayHint.hidden = false;
    priceOverlayHint.style.top = "375px";
    requestAnimationFrame(() => {
      priceOverlayHint.classList.add("is-visible");
    });
  };

  const hidePriceOverlayHint = () => {
    if (!priceOverlayHint) return;
    priceOverlayHint.classList.remove("is-visible");
    if (priceHintHideTimer) {
      window.clearTimeout(priceHintHideTimer);
    }
    priceHintHideTimer = window.setTimeout(() => {
      if (!priceOverlayHint.classList.contains("is-visible")) {
        priceOverlayHint.hidden = true;
        priceOverlayHint.style.top = "";
      }
      priceHintHideTimer = 0;
    }, 260);
  };

  const syncPriceTrack = () => {
    if (!priceTrackFill) return;
    const range = Math.max(maxAvailablePrice - minAvailablePrice, 1);
    const startPercent = ((activePriceMin - minAvailablePrice) / range) * 100;
    const endPercent = ((activePriceMax - minAvailablePrice) / range) * 100;
    priceTrackFill.style.left = `${Math.max(0, Math.min(startPercent, 100))}%`;
    priceTrackFill.style.right = `${Math.max(0, Math.min(100 - endPercent, 100))}%`;
  };

  const syncPriceInputs = () => {
    [priceMinRange, priceMaxRange].forEach((input) => {
      if (!input) return;
      input.min = String(minAvailablePrice);
      input.max = String(maxAvailablePrice);
    });
    if (priceMinRange) priceMinRange.value = String(activePriceMin);
    if (priceMaxRange) priceMaxRange.value = String(activePriceMax);
    if (priceMinInput) priceMinInput.value = String(activePriceMin);
    if (priceMaxInput) priceMaxInput.value = String(activePriceMax);
    syncPriceTrack();
  };

  const applyPriceRange = (nextMin, nextMax, source = "min") => {
    let normalizedMin = Number.isFinite(nextMin) ? Math.round(nextMin) : minAvailablePrice;
    let normalizedMax = Number.isFinite(nextMax) ? Math.round(nextMax) : maxAvailablePrice;

    normalizedMin = Math.min(Math.max(normalizedMin, minAvailablePrice), maxAvailablePrice);
    normalizedMax = Math.min(Math.max(normalizedMax, minAvailablePrice), maxAvailablePrice);

    if (normalizedMin > normalizedMax) {
      if (source === "max") {
        normalizedMin = normalizedMax;
      } else {
        normalizedMax = normalizedMin;
      }
    }

    activePriceMin = normalizedMin;
    activePriceMax = normalizedMax;
    syncPriceInputs();
    applyMenuControls(false);
  };

  const compareCards = (a, b) => {
    const priceA = getNumber(a.dataset.price);
    const priceB = getNumber(b.dataset.price);
    const popularityA = getNumber(a.dataset.popularity);
    const popularityB = getNumber(b.dataset.popularity);
    const nameA = String(a.dataset.name || a.querySelector("h3")?.textContent || "").trim();
    const nameB = String(b.dataset.name || b.querySelector("h3")?.textContent || "").trim();
    if (activeSort === "price-asc") {
      if (priceA !== priceB) return priceA - priceB;
    } else if (activeSort === "price-desc") {
      if (priceA !== priceB) return priceB - priceA;
    } else if (popularityA !== popularityB) {
      return popularityB - popularityA;
    }
    return nameA.localeCompare(nameB, ["ru", "en"], {
      sensitivity: "base",
      numeric: true,
    });
  };

  const closeSortMenu = () => {
    sortMenu?.classList.remove("is-open");
    sortToggle?.setAttribute("aria-expanded", "false");
    sortMenu?.setAttribute("aria-hidden", "true");
    sortToggle?.classList.remove("is-open");
  };

  const closeOverflowMenu = () => {
    overflowCategoryMenu?.classList.remove("is-open");
    overflowCategoryToggle?.setAttribute("aria-expanded", "false");
    overflowCategoryMenu?.setAttribute("aria-hidden", "true");
    overflowCategoryToggle?.classList.remove("is-open");
    restoreOverflowMenu();
  };

  const closeMobileMoreMenu = () => {
    mobileMoreMenu?.classList.remove("is-open");
    mobileMoreToggle?.setAttribute("aria-expanded", "false");
    mobileMoreMenu?.setAttribute("aria-hidden", "true");
    mobileMoreToggle?.classList.remove("is-open");
    restoreMobileMoreMenu();
  };

  const closePriceMenu = () => {
    const shouldAnimateMobileSheetClose =
      Boolean(priceMenu?.classList.contains("sort-menu--mobile-sheet")) && isMobileViewport();
    priceMenu?.classList.remove("is-open");
    priceToggle?.setAttribute("aria-expanded", "false");
    priceMenu?.setAttribute("aria-hidden", "true");
    priceToggle?.classList.remove("is-open");
    hidePriceOverlay();
    hidePriceOverlayHint();
    if (shouldAnimateMobileSheetClose) {
      if (priceMenuRestoreTimer) {
        window.clearTimeout(priceMenuRestoreTimer);
      }
      priceMenuRestoreTimer = window.setTimeout(() => {
        restorePriceMenu();
      }, 240);
      return;
    }
    restorePriceMenu();
  };

  const openSortMenu = () => {
    closeOverflowMenu();
    closePriceMenu();
    sortMenu?.classList.add("is-open");
    sortToggle?.setAttribute("aria-expanded", "true");
    sortMenu?.setAttribute("aria-hidden", "false");
    sortToggle?.classList.add("is-open");
  };

  const openOverflowMenu = () => {
    closeMobileMoreMenu();
    closePriceMenu();
    closeSortMenu();
    mountOverflowMenuToBody();
    positionFloatingMenu(overflowCategoryToggle, overflowCategoryMenu);
    overflowCategoryMenu?.classList.add("is-open");
    overflowCategoryToggle?.setAttribute("aria-expanded", "true");
    overflowCategoryMenu?.setAttribute("aria-hidden", "false");
    overflowCategoryToggle?.classList.add("is-open");
  };

  const openMobileMoreMenu = () => {
    closeOverflowMenu();
    closePriceMenu();
    closeSortMenu();
    mountMobileMoreMenuToBody();
    positionFloatingMenu(mobileMoreToggle, mobileMoreMenu);
    mobileMoreMenu?.classList.add("is-open");
    mobileMoreToggle?.setAttribute("aria-expanded", "true");
    mobileMoreMenu?.setAttribute("aria-hidden", "false");
    mobileMoreToggle?.classList.add("is-open");
  };

  const openPriceMenu = () => {
    closeOverflowMenu();
    closeMobileMoreMenu();
    closeSortMenu();
    if (priceMenuRestoreTimer) {
      window.clearTimeout(priceMenuRestoreTimer);
      priceMenuRestoreTimer = 0;
    }
    mountPriceMenuToBody();
    if (isMobileViewport()) {
      priceMenu?.classList.add("sort-menu--mobile-sheet");
      priceMenu?.style.removeProperty("left");
      priceMenu?.style.removeProperty("top");
      priceMenu?.style.removeProperty("min-width");
      priceMenu?.style.removeProperty("max-width");
      priceMenu?.style.removeProperty("max-height");
      showPriceOverlay();
      window.setTimeout(showPriceOverlayHint, 220);
    } else {
      priceMenu?.classList.remove("sort-menu--mobile-sheet");
      positionFloatingMenu(priceToggle, priceMenu);
    }
    priceMenu?.classList.add("is-open");
    priceToggle?.setAttribute("aria-expanded", "true");
    priceMenu?.setAttribute("aria-hidden", "false");
    priceToggle?.classList.add("is-open");
  };

  const getFilteredCards = (category) => {
    const selectedType = normalizeType(category);
    return menuCards
      .filter((card) => {
        const cardType = normalizeType(card.dataset.type);
        const cardName = String(card.dataset.name || card.querySelector("h3")?.textContent || "").toLowerCase();
        const cardLore = String(card.querySelector(".menu-card__lore")?.textContent || "").toLowerCase();
        const cardPrice = getNumber(card.dataset.price);
        const matchesCategory = selectedType === "all" ? true : cardType === selectedType;
        const matchesSearch =
          !searchQuery ||
          cardName.includes(searchQuery) ||
          cardLore.includes(searchQuery) ||
          cardType.includes(searchQuery);
        const matchesPrice = cardPrice >= activePriceMin && cardPrice <= activePriceMax;
        return matchesCategory && matchesSearch && matchesPrice;
      })
      .sort(compareCards);
  };

  const syncMenuControls = () => {
    animateToggleValue(
      sortToggle,
      sortValue,
      sortLabels[activeSort] || sortLabels.alpha,
      true,
    );
    sortToggle?.classList.add("is-active");
    categoryChips.forEach((chip) => {
      chip.classList.toggle("is-active", chip.dataset.type === activeCategory);
    });
    overflowOptions.forEach((option) => {
      option.classList.toggle("is-active", option.dataset.type === activeCategory);
    });
    const isOverflowActive = overflowCategories.includes(activeCategory);
    const isMobileSelectionActive = activeCategory !== "all";
    overflowCategoryToggle?.classList.toggle("is-active", isOverflowActive);
    mobileMoreToggle?.classList.toggle("is-active", isMobileSelectionActive);
    animateToggleValue(
      overflowCategoryToggle,
      overflowCategoryValue,
      categoryLabels.get(activeCategory) || activeCategory,
      isOverflowActive,
    );
    animateToggleValue(
      mobileMoreToggle,
      mobileMoreValue,
      categoryLabels.get(activeCategory) || activeCategory,
      isMobileSelectionActive,
    );
    priceToggle?.classList.toggle("is-active", hasActivePriceFilter());
    animateToggleValue(
      priceToggle,
      priceValue,
      formatPriceLabel(),
      hasActivePriceFilter(),
    );
    sortOptions.forEach((option) => {
      option.classList.toggle("is-active", option.dataset.sort === activeSort);
    });
    if (mobileMoreMenu) {
      Array.from(mobileMoreMenu.querySelectorAll(".filter-option")).forEach((option) => {
        option.classList.toggle("is-active", option.dataset.type === activeCategory);
      });
    }
  };

  const applyRevealAnimation = (card, index) => {
    card.style.animationDelay = `${index * 28}ms`;
    card.classList.add("menu-card--reveal");

    let revealCleared = false;
    const clearRevealClass = (event) => {
      if (revealCleared) return;
      if (event && event.animationName !== "menuReveal") return;
      revealCleared = true;
      card.classList.remove("menu-card--reveal");
      card.style.animationDelay = "";
    };

    card.addEventListener("animationend", clearRevealClass, { once: true });
    window.setTimeout(clearRevealClass, 260);
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
        applyRevealAnimation(card, index);
      }
    });
    if (emptyState) {
      emptyState.hidden = cards.length > 0;
    }
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
      closeOverflowMenu();
      closePriceMenu();
      activateCategory(chip.dataset.type || "all");
    });
  });

  overflowCategoryToggle?.addEventListener("click", () => {
    if (!overflowCategoryMenu?.classList.contains("is-open")) openOverflowMenu();
    else closeOverflowMenu();
  });

  mobileMoreToggle?.addEventListener("click", () => {
    if (!mobileMoreMenu?.classList.contains("is-open")) openMobileMoreMenu();
    else closeMobileMoreMenu();
  });

  priceToggle?.addEventListener("click", () => {
    if (!priceMenu?.classList.contains("is-open")) openPriceMenu();
    else closePriceMenu();
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

  normalizedSearchInputs.forEach((input) => {
    input.addEventListener("input", () => {
      const nextValue = String(input.value || "");
      searchQuery = nextValue.trim().toLowerCase();
      normalizedSearchInputs.forEach((peer) => {
        if (peer !== input && peer.value !== nextValue) {
          peer.value = nextValue;
        }
      });
      applyMenuControls(false);
    });
  });

  priceMinRange?.addEventListener("input", () => {
    applyPriceRange(getNumber(priceMinRange.value), activePriceMax, "min");
  });

  priceMaxRange?.addEventListener("input", () => {
    applyPriceRange(activePriceMin, getNumber(priceMaxRange.value), "max");
  });

  priceMinInput?.addEventListener("change", () => {
    applyPriceRange(getNumber(priceMinInput.value), activePriceMax, "min");
  });

  priceMaxInput?.addEventListener("change", () => {
    applyPriceRange(activePriceMin, getNumber(priceMaxInput.value), "max");
  });

  priceMinInput?.addEventListener("blur", () => {
    applyPriceRange(getNumber(priceMinInput.value), activePriceMax, "min");
  });

  priceMaxInput?.addEventListener("blur", () => {
    applyPriceRange(activePriceMin, getNumber(priceMaxInput.value), "max");
  });

  priceReset?.addEventListener("click", () => {
    applyPriceRange(minAvailablePrice, maxAvailablePrice, "min");
  });

  document.addEventListener("click", (event) => {
    if (!sortMenu || !sortToggle) return;
    if (sortMenu.contains(event.target) || sortToggle.contains(event.target)) return;
    closeSortMenu();
  });

  document.addEventListener("click", (event) => {
    if (!overflowCategoryMenu || !overflowCategoryToggle) return;
    if (overflowCategoryMenu.contains(event.target) || overflowCategoryToggle.contains(event.target)) return;
    closeOverflowMenu();
  });

  document.addEventListener("click", (event) => {
    if (!mobileMoreMenu || !mobileMoreToggle) return;
    if (mobileMoreMenu.contains(event.target) || mobileMoreToggle.contains(event.target)) return;
    closeMobileMoreMenu();
  });

  document.addEventListener("click", (event) => {
    if (!priceMenu || !priceToggle) return;
    if (priceMenu.contains(event.target) || priceToggle.contains(event.target)) return;
    closePriceMenu();
  });

  priceOverlay?.addEventListener("click", closePriceMenu);

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    closePriceMenu();
  });

  window.addEventListener("resize", () => {
    if (overflowCategoryMenu?.classList.contains("is-open")) {
      positionFloatingMenu(overflowCategoryToggle, overflowCategoryMenu);
    }
    if (mobileMoreMenu?.classList.contains("is-open")) {
      positionFloatingMenu(mobileMoreToggle, mobileMoreMenu);
    }
    if (priceMenu?.classList.contains("is-open")) {
      if (isMobileViewport()) {
        showPriceOverlay();
      } else {
        positionFloatingMenu(priceToggle, priceMenu);
      }
    }
    updateToggleWidth(sortToggle);
    updateToggleWidth(overflowCategoryToggle);
    updateToggleWidth(mobileMoreToggle);
    updateToggleWidth(priceToggle);
    syncPriceTrack();
  });

  window.addEventListener("scroll", () => {
    if (overflowCategoryMenu?.classList.contains("is-open")) {
      positionFloatingMenu(overflowCategoryToggle, overflowCategoryMenu);
    }
    if (mobileMoreMenu?.classList.contains("is-open")) {
      positionFloatingMenu(mobileMoreToggle, mobileMoreMenu);
    }
    if (priceMenu?.classList.contains("is-open")) {
      if (!isMobileViewport()) {
        positionFloatingMenu(priceToggle, priceMenu);
      }
    }
  }, true);

  const isMenuMobileViewport = () => isMobileViewport();
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

  buildOverflowOptions();
  syncPriceInputs();
  applyMenuControls(false);
  updateToggleWidth(sortToggle);
  updateToggleWidth(overflowCategoryToggle);
  updateToggleWidth(mobileMoreToggle);
  updateToggleWidth(priceToggle);
};

export { setupMenuCatalog };
