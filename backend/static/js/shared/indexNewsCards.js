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

export { setupIndexNewsCards };
