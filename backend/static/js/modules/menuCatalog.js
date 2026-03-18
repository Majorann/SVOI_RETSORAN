const setupMenuCatalog = ({
  menuViewport,
  menuList,
  menuCards,
  categoryChips,
  typeToggle,
  typeMenu,
  typeOptions,
  typeValue,
  sortToggle,
  sortMenu,
  sortOptions,
  sortValue,
}) => {
  if (!menuList || !Array.isArray(menuCards) || !menuCards.length) {
    return;
  }

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
};

export { setupMenuCatalog };
