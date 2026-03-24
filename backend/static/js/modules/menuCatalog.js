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
    popular: "По популярности",
    "price-asc": "Цена ↑",
    "price-desc": "Цена ↓",
  };
  const PRIMARY_MENU_CATEGORIES = ["Горячие блюда", "Закуски", "Салаты"];
  let activeCategory = "all";
  let activeSort = "popular";
  let searchQuery = "";
  let isMenuTransitionRunning = false;
  let pendingCategory = null;
  let overflowMenuMountedToBody = false;
  let mobileMoreMenuMountedToBody = false;
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
  let overflowOptions = [];
  let overflowWidthFrame = 0;

  const updateToggleWidth = (toggle) => {
    if (!toggle) return;
    if (overflowWidthFrame) {
      cancelAnimationFrame(overflowWidthFrame);
    }
    overflowWidthFrame = requestAnimationFrame(() => {
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
      overflowWidthFrame = requestAnimationFrame(() => {
        toggle.style.width = `${measuredWidth}px`;
      });
    });
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
    let left = toggleRect.left;
    let top = preferredTop;

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

  const openSortMenu = () => {
    closeOverflowMenu();
    sortMenu?.classList.add("is-open");
    sortToggle?.setAttribute("aria-expanded", "true");
    sortMenu?.setAttribute("aria-hidden", "false");
  };

  const openOverflowMenu = () => {
    closeMobileMoreMenu();
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
    closeSortMenu();
    mountMobileMoreMenuToBody();
    positionFloatingMenu(mobileMoreToggle, mobileMoreMenu);
    mobileMoreMenu?.classList.add("is-open");
    mobileMoreToggle?.setAttribute("aria-expanded", "true");
    mobileMoreMenu?.setAttribute("aria-hidden", "false");
    mobileMoreToggle?.classList.add("is-open");
  };

  const getFilteredCards = (category) => {
    const selectedType = normalizeType(category);
    return menuCards
      .filter((card) => {
        const cardType = normalizeType(card.dataset.type);
        const cardName = String(card.dataset.name || card.querySelector("h3")?.textContent || "").toLowerCase();
        const cardLore = String(card.querySelector(".menu-card__lore")?.textContent || "").toLowerCase();
        const matchesCategory = selectedType === "all" ? true : cardType === selectedType;
        const matchesSearch =
          !searchQuery ||
          cardName.includes(searchQuery) ||
          cardLore.includes(searchQuery) ||
          cardType.includes(searchQuery);
        return matchesCategory && matchesSearch;
      })
      .sort(compareCards);
  };

  const syncMenuControls = () => {
    if (sortValue) {
      sortValue.textContent = sortLabels[activeSort] || sortLabels.popular;
    }
    categoryChips.forEach((chip) => {
      chip.classList.toggle("is-active", chip.dataset.type === activeCategory);
    });
    overflowOptions.forEach((option) => {
      option.classList.toggle("is-active", option.dataset.type === activeCategory);
    });
    const isOverflowActive = overflowCategories.includes(activeCategory);
    const isMobileSelectionActive = activeCategory !== "all";
    overflowCategoryToggle?.classList.toggle("is-active", isOverflowActive);
    overflowCategoryToggle?.classList.toggle("has-selection", isOverflowActive);
    mobileMoreToggle?.classList.toggle("is-active", isMobileSelectionActive);
    mobileMoreToggle?.classList.toggle("has-selection", isMobileSelectionActive);
    if (overflowCategoryValue) {
      overflowCategoryValue.textContent = isOverflowActive ? categoryLabels.get(activeCategory) || activeCategory : "";
      overflowCategoryValue.hidden = false;
    }
    if (mobileMoreValue) {
      mobileMoreValue.textContent = isMobileSelectionActive ? categoryLabels.get(activeCategory) || activeCategory : "";
      mobileMoreValue.hidden = false;
    }
    updateToggleWidth(overflowCategoryToggle);
    updateToggleWidth(mobileMoreToggle);
    sortOptions.forEach((option) => {
      option.classList.toggle("is-active", option.dataset.sort === activeSort);
    });
    if (mobileMoreMenu) {
      Array.from(mobileMoreMenu.querySelectorAll(".filter-option")).forEach((option) => {
        option.classList.toggle("is-active", option.dataset.type === activeCategory);
      });
    }
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

  window.addEventListener("resize", () => {
    if (overflowCategoryMenu?.classList.contains("is-open")) {
      positionFloatingMenu(overflowCategoryToggle, overflowCategoryMenu);
    }
    if (mobileMoreMenu?.classList.contains("is-open")) {
      positionFloatingMenu(mobileMoreToggle, mobileMoreMenu);
    }
    updateToggleWidth(overflowCategoryToggle);
    updateToggleWidth(mobileMoreToggle);
  });

  window.addEventListener("scroll", () => {
    if (overflowCategoryMenu?.classList.contains("is-open")) {
      positionFloatingMenu(overflowCategoryToggle, overflowCategoryMenu);
    }
    if (mobileMoreMenu?.classList.contains("is-open")) {
      positionFloatingMenu(mobileMoreToggle, mobileMoreMenu);
    }
  }, true);

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
  applyMenuControls(false);
  updateToggleWidth(overflowCategoryToggle);
  updateToggleWidth(mobileMoreToggle);
};

export { setupMenuCatalog };
