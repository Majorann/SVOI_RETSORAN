const setupBottomNavMotion = () => {
  const nav = document.querySelector(".bottom-nav");
  if (!nav) return;
  const items = Array.from(nav.querySelectorAll(".bottom-nav__item"));
  if (!items.length) return;

  const indicator = document.createElement("span");
  indicator.className = "bottom-nav__indicator";
  nav.prepend(indicator);

  const moveIndicator = (target, instant = false) => {
    const navRect = nav.getBoundingClientRect();
    const itemRect = target.getBoundingClientRect();
    const left = itemRect.left - navRect.left;
    indicator.classList.toggle("is-no-anim", instant);
    indicator.style.width = `${itemRect.width}px`;
    indicator.style.transform = `translateX(${left}px)`;
    indicator.style.opacity = "1";
    if (instant) {
      window.requestAnimationFrame(() => indicator.classList.remove("is-no-anim"));
    }
  };

  const setActive = (target, instant = false) => {
    items.forEach((item) => item.classList.remove("bottom-nav__item--active"));
    target.classList.add("bottom-nav__item--active");
    moveIndicator(target, instant);
  };

  const pulseNavItem = (target) => {
    target.classList.remove("is-neon-pulse");
    window.requestAnimationFrame(() => {
      target.classList.add("is-neon-pulse");
      window.setTimeout(() => target.classList.remove("is-neon-pulse"), 360);
    });
  };

  const path = window.location.pathname;
  const getItemPath = (item) => {
    try {
      return new URL(item.getAttribute("href"), window.location.origin).pathname;
    } catch {
      return "";
    }
  };
  const profileLikePaths = new Set(["/profile", "/login", "/register", "/checkout", "/payment"]);

  const resolveActiveNavItem = () => {
    const explicitActive = items.find((item) => item.classList.contains("bottom-nav__item--active"));
    if (explicitActive) return explicitActive;

    const exactPathMatch = items.find((item) => getItemPath(item) === path);
    if (exactPathMatch) return exactPathMatch;

    if (profileLikePaths.has(path) || path.startsWith("/orders")) {
      const profileItem = items.find((item) => getItemPath(item) === "/profile");
      if (profileItem) return profileItem;
    }

    const homeItem = items.find((item) => getItemPath(item) === "/");
    return homeItem || items[0];
  };

  const active = resolveActiveNavItem();
  setActive(active, true);

  items.forEach((item) => {
    item.addEventListener("click", (event) => {
      const isMainClick = event.button === 0;
      const hasModifier = event.metaKey || event.ctrlKey || event.shiftKey || event.altKey;
      if (!isMainClick || hasModifier) return;
      setActive(item);
      pulseNavItem(item);
    });
  });

  window.addEventListener("resize", () => {
    const current = items.find((item) => item.classList.contains("bottom-nav__item--active")) || items[0];
    moveIndicator(current, true);
  });
};

export { setupBottomNavMotion };
