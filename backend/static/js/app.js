// Simple stagger animation helper
const stagger = (selector, step = 120) => {
  document.querySelectorAll(selector).forEach((el, index) => {
    el.style.animationDelay = `${index * step}ms`;
  });
};

// Menu hover mood: push dish photo to whole-page background
const setupMenuHoverMood = () => {
  const cards = document.querySelectorAll(".menu-card--menu");
  if (!cards.length) return;
  const body = document.body;
  const colorCache = new Map();
  const fallbackRgb = "112, 238, 255";
  let activeMoodId = 0;
  let clearMoodTimer = null;

  const clamp = (value) => Math.max(0, Math.min(255, Math.round(value)));
  const extractUrl = (cssUrlValue) => {
    const match = cssUrlValue.match(/url\((['"]?)(.*?)\1\)/);
    return match ? match[2] : null;
  };

  const colorFromImage = (url) => new Promise((resolve) => {
    if (!url) {
      resolve(fallbackRgb);
      return;
    }
    if (colorCache.has(url)) {
      resolve(colorCache.get(url));
      return;
    }

    const image = new Image();
    image.crossOrigin = "anonymous";
    image.onload = () => {
      try {
        const canvas = document.createElement("canvas");
        const side = 26;
        canvas.width = side;
        canvas.height = side;
        const ctx = canvas.getContext("2d", { willReadFrequently: true });
        if (!ctx) throw new Error("Canvas 2D context unavailable");

        ctx.drawImage(image, 0, 0, side, side);
        const pixels = ctx.getImageData(0, 0, side, side).data;
        let red = 0;
        let green = 0;
        let blue = 0;
        let weightTotal = 0;

        for (let i = 0; i < pixels.length; i += 4) {
          const alpha = pixels[i + 3] / 255;
          if (alpha < 0.12) continue;
          const luma = (pixels[i] + pixels[i + 1] + pixels[i + 2]) / 3;
          const contrastWeight = 0.55 + (Math.abs(128 - luma) / 255) * 0.45;
          const weight = alpha * contrastWeight;
          red += pixels[i] * weight;
          green += pixels[i + 1] * weight;
          blue += pixels[i + 2] * weight;
          weightTotal += weight;
        }

        if (!weightTotal) throw new Error("No visible pixels");
        const r = clamp((red / weightTotal) * 1.08 + 8);
        const g = clamp((green / weightTotal) * 1.06 + 6);
        const b = clamp((blue / weightTotal) * 1.08 + 8);
        const rgb = `${r}, ${g}, ${b}`;
        colorCache.set(url, rgb);
        resolve(rgb);
      } catch {
        colorCache.set(url, fallbackRgb);
        resolve(fallbackRgb);
      }
    };
    image.onerror = () => {
      colorCache.set(url, fallbackRgb);
      resolve(fallbackRgb);
    };
    image.src = url;
  });

  const applyMood = (rgb) => {
    if (clearMoodTimer) {
      window.clearTimeout(clearMoodTimer);
      clearMoodTimer = null;
    }
    body.style.setProperty("--menu-hover-rgb", rgb);
    body.style.setProperty("--menu-neon-rgb", rgb);
    body.classList.add("menu-photo-hover");
  };

  const activateMood = async (card) => {
    activeMoodId += 1;
    const moodId = activeMoodId;
    const photo = getComputedStyle(card).getPropertyValue("--dish-photo").trim();
    const photoUrl = extractUrl(photo);
    const rgb = await colorFromImage(photoUrl);
    if (moodId !== activeMoodId) return;
    applyMood(rgb);
  };

  const deactivateMood = () => {
    if (document.querySelector(".menu-card--menu:hover, .menu-card--menu:focus-within")) return;
    activeMoodId += 1;
    body.classList.remove("menu-photo-hover");
    if (clearMoodTimer) {
      window.clearTimeout(clearMoodTimer);
    }
    // Keep current color during fade-out to avoid bright flicker.
    clearMoodTimer = window.setTimeout(() => {
      if (document.querySelector(".menu-card--menu:hover, .menu-card--menu:focus-within")) return;
      body.style.removeProperty("--menu-hover-rgb");
      body.style.removeProperty("--menu-neon-rgb");
      clearMoodTimer = null;
    }, 760);
  };

  cards.forEach((card) => {
    card.addEventListener("mouseenter", () => activateMood(card));
    card.addEventListener("mouseleave", () => window.setTimeout(deactivateMood, 30));
    card.addEventListener("focusin", () => activateMood(card));
    card.addEventListener("focusout", () => window.setTimeout(deactivateMood, 30));
  });
};

// Hall map interactions: hover/tooltip, booking panel, time scale
const setupTableTooltip = () => {
  const tooltip = document.getElementById("tableTooltip");
  if (!tooltip) return;
  const hallMap = document.querySelector(".hall__map");
  const bookingPanel = document.getElementById("bookingPanel");
  const bookingTableId = document.getElementById("bookingTableId");
  const bookingTableSeats = document.getElementById("bookingTableSeats");
  const bookingInfo = document.getElementById("bookingInfo");
  const bookingCancel = document.getElementById("bookingCancel");
  const bookingSubmit = document.getElementById("bookingSubmit");
  const bookingDate = document.getElementById("bookingDate");
  const bookingTime = document.getElementById("bookingTime");
  const bookingName = document.getElementById("bookingName");
  const neon = document.getElementById("hallNeon");
  const timeScale = document.getElementById("timeScale");
  const bookingDateTop = document.getElementById("bookingDateTop");
  let selectedTableId = null;

  const pad = (value) => String(value).padStart(2, "0");
  const toDateInput = (date) =>
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
  const toTimeInput = (date) => `${pad(date.getHours())}:${pad(date.getMinutes())}`;

  // Clamp date/time inputs (no past time today)
  const updateDateTimeLimits = () => {
    if (!bookingDate || !bookingTime) return;
    const now = new Date();
    const today = toDateInput(now);
    bookingDate.min = today;
    if (!bookingDate.value) bookingDate.value = today;
    if (bookingDateTop) {
      bookingDateTop.min = today;
      if (!bookingDateTop.value) bookingDateTop.value = bookingDate.value;
    }

    if (bookingDate.value === today) {
      bookingTime.min = toTimeInput(now);
      if (!bookingTime.value) bookingTime.value = toTimeInput(now);
    } else {
      bookingTime.min = "00:00";
      if (!bookingTime.value) bookingTime.value = "12:00";
    }
  };

  // Fetch reserved tables for selected date/time
  const refreshAvailability = async () => {
    if (!bookingDate?.value || !bookingTime?.value) return;
    const params = new URLSearchParams({
      date: bookingDate.value,
      time: bookingTime.value,
    });
    const response = await fetch(`/availability?${params.toString()}`);
    const result = await response.json().catch(() => ({}));
    if (!response.ok || !result.ok) return;

    document.querySelectorAll(".table").forEach((table) => {
      const id = Number(table.dataset.id);
      if (result.reserved.includes(id)) {
        table.classList.remove("table--free");
        table.classList.add("table--reserved");
      } else {
        table.classList.remove("table--reserved");
        table.classList.add("table--free");
      }
    });
  };

  const timeToMinutes = (value) => {
    if (!value) return null;
    const parts = value.split(":");
    if (parts.length < 2) return null;
    return Number(parts[0]) * 60 + Number(parts[1]);
  };

  const updatePastSlots = () => {
    if (!timeScale || !bookingDate?.value) return;
    const now = new Date();
    const today = toDateInput(now);
    const nowMinutes = now.getHours() * 60 + now.getMinutes();
    timeScale.querySelectorAll(".timeline__slot").forEach((slot) => {
      const slotMinutes = timeToMinutes(slot.dataset.time);
      const isPast =
        bookingDate.value === today &&
        slotMinutes !== null &&
        slotMinutes < nowMinutes;
      slot.classList.toggle("timeline__slot--past", isPast);
      slot.dataset.past = isPast ? "1" : "0";
    });
  };

  // Highlight selected time on the timeline
  const markActiveTime = () => {
    if (!timeScale || !bookingTime?.value) return;
    const value = bookingTime.value;
    timeScale.querySelectorAll(".timeline__slot").forEach((slot) => {
      slot.classList.toggle("is-active", slot.dataset.time === value);
    });
  };

  // Change page tint based on time of day
  const setTimeMood = () => {
    if (!bookingTime?.value) return;
    const hour = Number(bookingTime.value.split(":")[0]);
    document.body.classList.remove("mood-morning", "mood-noon", "mood-evening", "mood-night");
    if (hour < 12) {
      document.body.classList.add("mood-morning");
    } else if (hour < 17) {
      document.body.classList.add("mood-noon");
    } else if (hour < 21) {
      document.body.classList.add("mood-evening");
    } else {
      document.body.classList.add("mood-night");
    }
  };

  // Snap timeline scroll to closest slot
  const syncTimeFromScroll = () => {
    if (!timeScale || !bookingTime) return;
    const slots = Array.from(timeScale.querySelectorAll(".timeline__slot"));
    const rect = timeScale.getBoundingClientRect();
    const center = rect.top + rect.height / 2;
    let closest = null;
    let closestDist = Infinity;
    slots.forEach((slot) => {
      const r = slot.getBoundingClientRect();
      const dist = Math.abs(r.top + r.height / 2 - center);
      if (dist < closestDist) {
        closestDist = dist;
        closest = slot;
      }
    });
    if (closest) {
      let target = closest;
      if (target.dataset.past === "1") {
        target = slots.find((slot) => slot.dataset.past !== "1") || closest;
      }
      if (bookingTime.value !== target.dataset.time) {
        bookingTime.value = target.dataset.time;
        markActiveTime();
        setTimeMood();
        refreshAvailability();
      }
    }
  };

  document.querySelectorAll(".table").forEach((table) => {
    const label = table.dataset.label;
    const seats = table.dataset.seats;
    const windowSide = table.dataset.window;
    const isFreeNow = () => table.classList.contains("table--free");

    table.addEventListener("mouseenter", () => {
      const isFree = isFreeNow();
      if (neon && hallMap) {
        const hallRect = hallMap.parentElement?.getBoundingClientRect() || hallMap.getBoundingClientRect();
        const rect = table.getBoundingClientRect();
        const x = ((rect.left + rect.width / 2 - hallRect.left) / hallRect.width) * 100;
        const y = ((rect.top + rect.height / 2 - hallRect.top) / hallRect.height) * 100;
        neon.style.setProperty("--neon-x", `${x}%`);
        neon.style.setProperty("--neon-y", `${y}%`);
        neon.classList.toggle("is-red", !isFree);
        neon.classList.add("is-visible");
      }
      tooltip.innerHTML = `
        <strong>${label}</strong><br />
        Мест: ${seats}<br />
        У окна: ${windowSide}
      `;
      if (isFree) {
        tooltip.classList.add("is-visible");
        hallMap?.classList.add("is-blurred");
        table.classList.add("table--hovered");
      }
    });

    table.addEventListener("mousemove", (event) => {
      tooltip.style.left = `${event.clientX}px`;
      tooltip.style.top = `${event.clientY - 18}px`;
    });

    table.addEventListener("mouseleave", () => {
      tooltip.classList.remove("is-visible");
      hallMap?.classList.remove("is-blurred");
      table.classList.remove("table--hovered");
      neon?.classList.remove("is-visible");
    });

    table.addEventListener("click", () => {
      if (!isFreeNow()) return;
      selectedTableId = table.dataset.id;
      bookingTableId.textContent = table.querySelector(".table__top")?.textContent || "";
      bookingTableSeats.textContent = `${seats} места`;
      bookingInfo.textContent = `Столик у окна: ${windowSide}`;
      bookingPanel?.classList.add("is-open");
      bookingPanel?.setAttribute("aria-hidden", "false");
      hallMap?.classList.add("is-blurred-strong");
      hallMap?.classList.add("is-booking");
      tooltip.classList.remove("is-visible");
      table.classList.add("table--hovered");
      updateDateTimeLimits();
      refreshAvailability();
    });
  });

  bookingCancel?.addEventListener("click", () => {
    bookingPanel?.classList.remove("is-open");
    bookingPanel?.setAttribute("aria-hidden", "true");
    hallMap?.classList.remove("is-blurred-strong");
    hallMap?.classList.remove("is-booking");
    hallMap?.classList.remove("is-typing");
    selectedTableId = null;
  });

  bookingSubmit?.addEventListener("click", async () => {
    if (!selectedTableId) return;
    const dateValue = bookingDate?.value;
    const timeValue = bookingTime?.value;
    const nameValue = bookingName?.value?.trim();

    if (!dateValue || !timeValue || !nameValue) {
      bookingInfo.textContent = "Заполните дату, время и имя.";
      return;
    }

    const now = new Date();
    const selected = new Date(`${dateValue}T${timeValue}`);
    if (selected < now) {
      bookingInfo.textContent = "Время не может быть в прошлом.";
      return;
    }

    bookingInfo.textContent = "Сохраняем бронь...";
    const response = await fetch("/book", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        table_id: Number(selectedTableId),
        date: dateValue,
        time: timeValue,
        name: nameValue,
      }),
    });

    const result = await response.json().catch(() => ({}));
    if (response.status === 401) {
      bookingInfo.textContent = "Войдите в аккаунт, чтобы забронировать.";
      window.location.href = "/login";
      return;
    }
    if (!response.ok) {
      bookingInfo.textContent = result.error || "Не удалось сохранить бронь.";
      return;
    }

    const table = document.querySelector(`.table[data-id=\"${selectedTableId}\"]`);
    if (table) {
      table.classList.remove("table--free");
      table.classList.add("table--reserved");
    }
    bookingInfo.textContent = "Бронь подтверждена.";
    window.location.href = "/";
  });

  [bookingDate, bookingTime, bookingName].forEach((field) => {
    if (!field) return;
    field.addEventListener("focus", () => {
      hallMap?.classList.add("is-typing");
    });
    field.addEventListener("blur", () => {
      const active = document.activeElement;
      const isInside =
        bookingPanel && active && bookingPanel.contains(active);
      if (!isInside) {
        hallMap?.classList.remove("is-typing");
      }
    });
  });

  bookingDate?.addEventListener("change", updateDateTimeLimits);
  bookingTime?.addEventListener("change", updateDateTimeLimits);
  bookingDate?.addEventListener("change", refreshAvailability);
  bookingTime?.addEventListener("change", refreshAvailability);
  bookingTime?.addEventListener("change", markActiveTime);
  bookingTime?.addEventListener("change", setTimeMood);
  bookingDate?.addEventListener("change", updatePastSlots);
  bookingDateTop?.addEventListener("change", () => {
    if (bookingDate) bookingDate.value = bookingDateTop.value;
    updateDateTimeLimits();
    updatePastSlots();
    refreshAvailability();
  });

  if (timeScale) {
    timeScale.addEventListener("scroll", () => {
      window.clearTimeout(timeScale._t);
      timeScale._t = window.setTimeout(syncTimeFromScroll, 80);
    });
    timeScale.addEventListener("click", (event) => {
      const slot = event.target.closest(".timeline__slot");
      if (!slot) return;
      if (slot.dataset.past === "1") return;
      bookingTime.value = slot.dataset.time;
      markActiveTime();
      setTimeMood();
      refreshAvailability();
    });
  }

  // Initial load: set defaults and fetch reserved tables
  updateDateTimeLimits();
  refreshAvailability();
  markActiveTime();
  setTimeMood();
  updatePastSlots();
  if (bookingDateTop) bookingDateTop.value = bookingDate?.value || "";
};

// Page init: animations + interactions
window.addEventListener("DOMContentLoaded", () => {
  stagger(".news-card", 140);
  stagger(".menu-card", 120);
  setupTableTooltip();
  setupMenuHoverMood();

  const filterToggle = document.getElementById("filterToggle");
  const filterMenu = document.getElementById("filterMenu");
  const menuCards = document.querySelectorAll(".menu-card--menu");
  const cartButton = document.getElementById("cartButton");
  const cartBadge = document.getElementById("cartBadge");
  const cartDrawer = document.getElementById("cartDrawer");
  const cartClose = document.getElementById("cartClose");
  const cartList = document.getElementById("cartList");
  const cartTotal = document.getElementById("cartTotal");
  const filterGroup = document.querySelector(".filter-group");
  const cardNumberInput = document.querySelector('input[name="card_number"]');
  const expiryInput = document.querySelector('input[name="expiry"]');
  const holderInput = document.querySelector('input[name="holder"]');
  if (filterToggle && filterMenu) {
    filterToggle.addEventListener("click", () => {
      filterMenu.classList.toggle("is-open");
      filterToggle.classList.toggle("is-open");
      if (filterGroup) filterGroup.classList.toggle("is-open");
    });
    filterMenu.querySelectorAll(".filter-item").forEach((item) => {
      item.addEventListener("click", () => {
        const type = item.dataset.type;
        menuCards.forEach((card) => {
          const matches = type === "all" || card.dataset.type === type;
          card.style.display = matches ? "" : "none";
        });
        filterMenu.classList.remove("is-open");
        filterToggle.classList.remove("is-open");
        if (filterGroup) filterGroup.classList.remove("is-open");
      });
    });
  }

  if (cardNumberInput) {
    cardNumberInput.addEventListener("input", () => {
      const digits = cardNumberInput.value.replace(/\D/g, "").slice(0, 16);
      const groups = digits.match(/.{1,4}/g) || [];
      cardNumberInput.value = groups.join(" ");
    });
  }

  if (expiryInput) {
    expiryInput.addEventListener("input", () => {
      const digits = expiryInput.value.replace(/\D/g, "").slice(0, 4);
      if (digits.length >= 3) {
        expiryInput.value = `${digits.slice(0, 2)}/${digits.slice(2)}`;
      } else {
        expiryInput.value = digits;
      }
    });
    expiryInput.addEventListener("blur", () => {
      const digits = expiryInput.value.replace(/\D/g, "");
      if (digits.length >= 2) {
        const month = Math.min(Math.max(parseInt(digits.slice(0, 2), 10) || 1, 1), 12);
        const year = digits.slice(2, 4);
        expiryInput.value = `${String(month).padStart(2, "0")}${year ? `/${year}` : ""}`;
      }
    });
  }

  if (holderInput) {
    holderInput.addEventListener("input", () => {
      const cleaned = holderInput.value
        .replace(/[^a-zA-Zа-яА-ЯёЁ\s-]/g, "")
        .replace(/\s+/g, " ")
        .trimStart();
      holderInput.value = cleaned.toUpperCase();
    });
  }

  const loadCart = () => {
    try {
      return JSON.parse(localStorage.getItem("cart") || "[]");
    } catch {
      return [];
    }
  };

  const saveCart = (cart) => {
    localStorage.setItem("cart", JSON.stringify(cart));
  };

  const updateCartUI = () => {
    if (!cartBadge || !cartList || !cartTotal) return;
    const cart = loadCart();
    const totalQty = cart.reduce((sum, item) => sum + item.qty, 0);
    const totalPrice = cart.reduce((sum, item) => sum + item.qty * item.price, 0);
    cartBadge.textContent = totalQty;
    cartList.innerHTML = "";
    cart.forEach((item) => {
      const row = document.createElement("div");
      row.className = "cart-item";
      row.innerHTML = `
        <div>
          <div class="cart-item__name">${item.name}</div>
          <div class="cart-item__meta">${item.qty} × ${item.price} ₽</div>
        </div>
        <div class="cart-item__actions">
          <button class="cart-item__btn" data-action="dec" data-id="${item.id}">−</button>
          <button class="cart-item__btn" data-action="inc" data-id="${item.id}">+</button>
        </div>
      `;
      cartList.appendChild(row);
    });
    cartTotal.textContent = totalPrice;
    updateMenuButtons(cart);
  };

  const updateMenuButtons = (cart) => {
    document.querySelectorAll(".add-button").forEach((btn) => {
      const id = Number(btn.dataset.id);
      const item = cart.find((row) => row.id === id);
      if (!item) {
        btn.classList.remove("is-active");
        btn.innerHTML = "В корзину";
        return;
      }
      btn.classList.add("is-active");
      btn.innerHTML = `
        <span class="add-button__btn" data-action="dec">−</span>
        <span class="add-button__qty">${item.qty}</span>
        <span class="add-button__btn" data-action="inc">+</span>
      `;
    });
  };

  const addToCart = (id, name, price) => {
    const cart = loadCart();
    const existing = cart.find((item) => item.id === id);
    if (existing) {
      existing.qty += 1;
    } else {
      cart.push({ id, name, price, qty: 1 });
    }
    saveCart(cart);
    updateCartUI();
  };

  document.querySelectorAll(".add-button").forEach((btn) => {
    btn.addEventListener("click", (event) => {
      const action = event.target.dataset.action;
      const id = Number(btn.dataset.id);
      const name = btn.dataset.name || "Позиция";
      const price = Number(btn.dataset.price) || 0;
      const cart = loadCart();
      const item = cart.find((row) => row.id === id);
      if (action === "inc") {
        if (item) item.qty += 1;
        else cart.push({ id, name, price, qty: 1 });
        saveCart(cart);
        updateCartUI();
        return;
      }
      if (action === "dec") {
        if (item) item.qty -= 1;
        const next = cart.filter((row) => row.qty > 0);
        saveCart(next);
        updateCartUI();
        return;
      }
      addToCart(id, name, price);
    });
  });

  cartButton?.addEventListener("click", () => {
    cartDrawer?.classList.toggle("is-open");
    cartDrawer?.setAttribute(
      "aria-hidden",
      cartDrawer?.classList.contains("is-open") ? "false" : "true"
    );
    updateCartUI();
  });

  cartClose?.addEventListener("click", () => {
    cartDrawer?.classList.remove("is-open");
    cartDrawer?.setAttribute("aria-hidden", "true");
  });

  cartList?.addEventListener("click", (event) => {
    const button = event.target.closest(".cart-item__btn");
    if (!button) return;
    const id = Number(button.dataset.id);
    const cart = loadCart();
    const item = cart.find((row) => row.id === id);
    if (!item) return;
    if (button.dataset.action === "inc") item.qty += 1;
    if (button.dataset.action === "dec") item.qty -= 1;
    const next = cart.filter((row) => row.qty > 0);
    saveCart(next);
    updateCartUI();
  });

  updateCartUI();
});
