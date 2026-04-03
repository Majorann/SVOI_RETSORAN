import { navigateWithAuth } from "../modules/authToken.js";

const setupIndexNewsCards = () => {
  const newsCards = Array.from(document.querySelectorAll(".news-card"));
  if (!newsCards.length) return;

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
    if (!timerId) return;
    window.clearTimeout(timerId);
    newsAnimationTimers.delete(card);
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
    card.addEventListener("click", () => {
      const cardLink = card.dataset.link;
      if (cardLink) {
        navigateWithAuth(cardLink);
        return;
      }
      if (!isTouchNewsMode()) return;
      setNewsExpanded(card, !card.classList.contains("is-expanded"));
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
      setNewsExpanded(card, !card.classList.contains("is-expanded"));
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
};

const setupIndexFeaturedMenuCards = () => {
  const featuredCards = Array.from(document.querySelectorAll(".menu-card--featured"));
  if (!featuredCards.length) return;

  const touchQuery = window.matchMedia("(hover: none) and (pointer: coarse)");
  const mobileViewportQuery = window.matchMedia("(max-width: 767px)");
  const shouldUseTwoTapMode = () => touchQuery.matches || mobileViewportQuery.matches;
  const animationTimers = new WeakMap();
  const EXPAND_ANIMATION_MS = 560;

  const clearAnimationTimer = (card) => {
    const timerId = animationTimers.get(card);
    if (!timerId) return;
    window.clearTimeout(timerId);
    animationTimers.delete(card);
  };

  const setExpandedState = (card, expanded) => {
    clearAnimationTimer(card);
    card.classList.toggle("is-expanded", expanded);
    card.classList.toggle("is-expanding", expanded);
    card.dataset.expandedReady = expanded ? "0" : "0";
    card.setAttribute("aria-expanded", expanded ? "true" : "false");

    if (!expanded) {
      return;
    }

    const timerId = window.setTimeout(() => {
      card.classList.remove("is-expanding");
      card.dataset.expandedReady = "1";
      animationTimers.delete(card);
    }, EXPAND_ANIMATION_MS);
    animationTimers.set(card, timerId);
  };

  const collapseCards = (exceptCard = null) => {
    featuredCards.forEach((card) => {
      if (exceptCard && card === exceptCard) return;
      setExpandedState(card, false);
    });
  };

  featuredCards.forEach((card) => {
    card.setAttribute("aria-expanded", "false");
    card.dataset.expandedReady = "0";

    card.addEventListener("click", (event) => {
      if (!shouldUseTwoTapMode()) return;

      const isExpanded = card.classList.contains("is-expanded");
      const isReadyToNavigate = card.dataset.expandedReady === "1";
      const href = card.getAttribute("href");

      if (!isExpanded) {
        event.preventDefault();
        collapseCards(card);
        setExpandedState(card, true);
        return;
      }

      if (!isReadyToNavigate) {
        event.preventDefault();
        return;
      }

      if (!href) {
        event.preventDefault();
        return;
      }

      event.preventDefault();
      navigateWithAuth(href);
    }, { capture: true });

    card.addEventListener("keydown", (event) => {
      if (!shouldUseTwoTapMode()) return;
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();

      const isExpanded = card.classList.contains("is-expanded");
      const isReadyToNavigate = card.dataset.expandedReady === "1";
      const href = card.getAttribute("href");

      if (!isExpanded) {
        collapseCards(card);
        setExpandedState(card, true);
        return;
      }

      if (!isReadyToNavigate || !href) {
        return;
      }

      navigateWithAuth(href);
    });
  });

  document.addEventListener("click", (event) => {
    if (!shouldUseTwoTapMode()) return;
    if (event.target.closest(".menu-card--featured")) return;
    collapseCards();
  });

  const syncInteractionMode = () => {
    if (shouldUseTwoTapMode()) return;
    collapseCards();
  };

  if (typeof touchQuery.addEventListener === "function") {
    touchQuery.addEventListener("change", syncInteractionMode);
  } else if (typeof touchQuery.addListener === "function") {
    touchQuery.addListener(syncInteractionMode);
  }
  if (typeof mobileViewportQuery.addEventListener === "function") {
    mobileViewportQuery.addEventListener("change", syncInteractionMode);
  } else if (typeof mobileViewportQuery.addListener === "function") {
    mobileViewportQuery.addListener(syncInteractionMode);
  }
  window.addEventListener("resize", syncInteractionMode);
};

export { setupIndexFeaturedMenuCards, setupIndexNewsCards };
