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

// Bottom navigation: animated focus fill between tabs
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

  const active = items.find((item) => item.classList.contains("bottom-nav__item--active")) || items[0];
  setActive(active, true);

  items.forEach((item) => {
    item.addEventListener("click", (event) => {
      const isMainClick = event.button === 0;
      const hasModifier = event.metaKey || event.ctrlKey || event.shiftKey || event.altKey;
      const href = item.getAttribute("href");
      if (!isMainClick || hasModifier || !href) return;
      event.preventDefault();
      setActive(item);
      window.setTimeout(() => {
        window.location.href = href;
      }, 170);
    });
  });

  window.addEventListener("resize", () => {
    const current = items.find((item) => item.classList.contains("bottom-nav__item--active")) || items[0];
    moveIndicator(current, true);
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
  const bookingSummary = document.getElementById("bookingSummary");
  const bookingCancel = document.getElementById("bookingCancel");
  const bookingSubmit = document.getElementById("bookingSubmit");
  const bookingDate = document.getElementById("bookingDate");
  const bookingTime = document.getElementById("bookingTime");
  const bookingName = document.getElementById("bookingName");
  const bookingDateTop = document.getElementById("bookingDateTop");
  const bookingDateMobile = document.getElementById("bookingDateMobile");
  const bookingDateMobilePicker = document.getElementById("bookingDateMobilePicker");
  const bookingDateMobileError = document.getElementById("bookingDateMobileError");
  const bookingDateSummary = document.getElementById("bookingDateSummary");
  const bookingTimeSummary = document.getElementById("bookingTimeSummary");
  const openDateTimeSheet = document.getElementById("openDateTimeSheet");
  const dateTimeSheet = document.getElementById("dateTimeSheet");
  const dateTimeClose = document.getElementById("dateTimeClose");
  const dateTimeApply = document.getElementById("dateTimeApply");
  const sheetBackdrop = document.getElementById("sheetBackdrop");
  const neon = document.getElementById("hallNeon");
  const timeScale = document.getElementById("timeScale");
  const timeScaleMobile = document.getElementById("timeScaleMobile");

  const timeScales = [timeScale, timeScaleMobile].filter(Boolean);
  const timelineIndicators = new Map();
  timeScales.forEach((scaleNode) => {
    const indicator = document.createElement("div");
    indicator.className = "timeline__active-indicator";
    scaleNode.prepend(indicator);
    timelineIndicators.set(scaleNode, indicator);
  });

  const isMobileViewport = () => window.matchMedia("(max-width: 767px)").matches;

  const pad = (value) => String(value).padStart(2, "0");
  const toDateInput = (date) =>
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
  const toTimeInput = (date) => `${pad(date.getHours())}:${pad(date.getMinutes())}`;
  const formatDateDisplay = (value) => {
    if (!value || !value.includes("-")) return value || "-";
    const [year, month, day] = value.split("-");
    return `${day}.${month}.${year}`;
  };
  const isoToMaskedDate = (value) => formatDateDisplay(value);
  const maskedToIsoDate = (maskedValue) => {
    const parts = String(maskedValue || "").trim().split(".");
    if (parts.length !== 3) return null;
    const [dayRaw, monthRaw, yearRaw] = parts;
    if (dayRaw.length !== 2 || monthRaw.length !== 2 || yearRaw.length !== 4) return null;
    const day = Number(dayRaw);
    const month = Number(monthRaw);
    const year = Number(yearRaw);
    if (!Number.isInteger(day) || !Number.isInteger(month) || !Number.isInteger(year)) return null;
    if (month < 1 || month > 12 || day < 1 || day > 31) return null;
    const candidate = `${yearRaw}-${monthRaw}-${dayRaw}`;
    const parsed = new Date(`${candidate}T00:00:00`);
    if (Number.isNaN(parsed.getTime())) return null;
    if (toDateInput(parsed) !== candidate) return null;
    return candidate;
  };
  const applyDateMask = (rawValue) => {
    const digits = String(rawValue || "").replace(/\D/g, "").slice(0, 8);
    if (!digits) return "";
    if (digits.length <= 2) return digits;
    if (digits.length <= 4) return `${digits.slice(0, 2)}.${digits.slice(2)}`;
    return `${digits.slice(0, 2)}.${digits.slice(2, 4)}.${digits.slice(4)}`;
  };

  let selectedTableId = null;
  let selectedTableLabel = "";
  let isDateValid = true;

  const setBackdropVisible = (isVisible) => {
    if (!sheetBackdrop) return;
    sheetBackdrop.hidden = !isVisible;
    sheetBackdrop.classList.toggle("is-open", isVisible);
  };

  const updateDateValidation = ({ candidateIso = bookingDate?.value || "", rawMasked = "" } = {}) => {
    const today = toDateInput(new Date());
    const currentTime = bookingTime?.value || "";
    const hasTime = /^\d{2}:\d{2}$/.test(currentTime);
    let valid = Boolean(candidateIso) && candidateIso >= today;
    let errorText = "";
    let timeValid = hasTime;
    let selectedIsPast = false;
    if (valid && hasTime) {
      const selectedMoment = new Date(`${candidateIso}T${currentTime}`);
      if (!Number.isNaN(selectedMoment.getTime()) && selectedMoment < new Date()) {
        selectedIsPast = true;
        timeValid = false;
      }
    }
    if (rawMasked && !candidateIso) {
      valid = false;
      errorText = "Введите дату в формате ДД.ММ.ГГГГ.";
    } else if (candidateIso && candidateIso < today) {
      valid = false;
      errorText = "Дата не может быть раньше сегодняшней.";
    } else if (!candidateIso || !valid) {
      valid = false;
      errorText = "Укажите дату бронирования.";
    } else if (!hasTime) {
      valid = false;
      timeValid = false;
      errorText = "Укажите время бронирования.";
    } else if (selectedIsPast) {
      valid = false;
      errorText = "Время не может быть в прошлом.";
    }
    isDateValid = valid;
    if (bookingDateMobileError) {
      bookingDateMobileError.textContent = valid ? "" : errorText;
    }
    bookingDate?.classList.toggle("is-invalid", !valid);
    bookingDateTop?.classList.toggle("is-invalid", !valid);
    bookingDateMobile?.classList.toggle("is-invalid", !valid);
    bookingTime?.classList.toggle("is-invalid", !timeValid);
    if (dateTimeApply) dateTimeApply.disabled = !valid;
    if (bookingSubmit) bookingSubmit.disabled = !valid;
    return valid;
  };

  const isSelectedDateTimeInPast = () => {
    const dateValue = bookingDate?.value;
    const timeValue = bookingTime?.value;
    if (!dateValue || !timeValue) return false;
    const selectedMoment = new Date(`${dateValue}T${timeValue}`);
    if (Number.isNaN(selectedMoment.getTime())) return false;
    return selectedMoment < new Date();
  };

  const setAllTablesReserved = (reserved) => {
    document.querySelectorAll(".table").forEach((table) => {
      table.classList.toggle("table--reserved", reserved);
      table.classList.toggle("table--free", !reserved);
    });
  };

  const syncSummaryLine = () => {
    if (bookingDateSummary) bookingDateSummary.textContent = formatDateDisplay(bookingDate?.value || "");
    if (bookingTimeSummary) bookingTimeSummary.textContent = bookingTime?.value || "-";
  };

  const syncBookingSummary = () => {
    if (!bookingSummary) return;
    if (!selectedTableId) {
      bookingSummary.textContent = "Выберите свободный столик на схеме.";
      return;
    }
    bookingSummary.textContent = `${selectedTableLabel || selectedTableId} • ${formatDateDisplay(
      bookingDate?.value || ""
    )} • ${bookingTime?.value || "-"}`;
  };

  const setDateValue = (nextDate, source = "") => {
    if (!nextDate) return;
    if (bookingDate && bookingDate.value !== nextDate) bookingDate.value = nextDate;
    if (bookingDateTop && source !== "top" && bookingDateTop.value !== nextDate) bookingDateTop.value = nextDate;
    const maskedDate = isoToMaskedDate(nextDate);
    if (bookingDateMobile && source !== "mobile" && bookingDateMobile.value !== maskedDate) {
      bookingDateMobile.value = maskedDate;
    }
    if (bookingDateMobilePicker && source !== "picker" && bookingDateMobilePicker.value !== nextDate) {
      bookingDateMobilePicker.value = nextDate;
    }
    updateDateValidation();
    syncSummaryLine();
    syncBookingSummary();
  };

  const setTimeValue = (nextTime) => {
    if (!nextTime || !bookingTime) return;
    if (bookingTime.value !== nextTime) bookingTime.value = nextTime;
    updateDateValidation();
    syncSummaryLine();
    syncBookingSummary();
  };

  const closeDateTimeSheet = () => {
    dateTimeSheet?.classList.remove("is-open");
    dateTimeSheet?.setAttribute("aria-hidden", "true");
    if (!bookingPanel?.classList.contains("is-open")) setBackdropVisible(false);
  };

  const openDateTimeSheetPanel = () => {
    if (!dateTimeSheet) return;
    dateTimeSheet.classList.add("is-open");
    dateTimeSheet.setAttribute("aria-hidden", "false");
    setBackdropVisible(true);
  };

  const closeBookingPanel = () => {
    bookingPanel?.classList.remove("is-open");
    bookingPanel?.setAttribute("aria-hidden", "true");
    hallMap?.classList.remove("is-blurred-strong");
    hallMap?.classList.remove("is-booking");
    hallMap?.classList.remove("is-typing");
    if (!dateTimeSheet?.classList.contains("is-open")) setBackdropVisible(false);
    selectedTableId = null;
    selectedTableLabel = "";
    syncBookingSummary();
  };

  const openBookingPanel = () => {
    closeDateTimeSheet();
    bookingPanel?.classList.add("is-open");
    bookingPanel?.setAttribute("aria-hidden", "false");
    hallMap?.classList.add("is-blurred-strong");
    hallMap?.classList.add("is-booking");
    setBackdropVisible(isMobileViewport());
  };

  const updateDateTimeLimits = () => {
    if (!bookingDate || !bookingTime) return;
    const now = new Date();
    const today = toDateInput(now);
    bookingDate.min = today;
    if (bookingDateTop) bookingDateTop.min = today;
    if (bookingDateMobilePicker) bookingDateMobilePicker.min = today;

    if (!bookingDate.value) setDateValue(today, "booking");
    if (!bookingDateTop?.value && bookingDateTop) bookingDateTop.value = bookingDate.value;
    if (!bookingDateMobile?.value && bookingDateMobile) bookingDateMobile.value = isoToMaskedDate(bookingDate.value);
    if (!bookingDateMobilePicker?.value && bookingDateMobilePicker) bookingDateMobilePicker.value = bookingDate.value;

    if (bookingDate.value === today) {
      bookingTime.min = toTimeInput(now);
      if (!bookingTime.value || bookingTime.value < bookingTime.min) {
        setTimeValue(toTimeInput(now));
      }
    } else {
      bookingTime.min = "00:00";
      if (!bookingTime.value) setTimeValue("12:00");
    }

    updateDateValidation();
    syncSummaryLine();
    syncBookingSummary();
  };

  const refreshAvailability = async () => {
    if (!bookingDate?.value || !bookingTime?.value) return;
    if (isSelectedDateTimeInPast()) {
      setAllTablesReserved(true);
      updateDateValidation();
      return;
    }
    const params = new URLSearchParams({ date: bookingDate.value, time: bookingTime.value });
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
    if (!bookingDate?.value) return;
    const now = new Date();
    const today = toDateInput(now);
    const nowMinutes = now.getHours() * 60 + now.getMinutes();
    timeScales.forEach((scaleNode) => {
      scaleNode.querySelectorAll(".timeline__slot").forEach((slot) => {
        const slotMinutes = timeToMinutes(slot.dataset.time);
        const isPast =
          bookingDate.value === today &&
          slotMinutes !== null &&
          slotMinutes < nowMinutes;
        slot.classList.toggle("timeline__slot--past", isPast);
        slot.dataset.past = isPast ? "1" : "0";
      });
    });
  };

  const markActiveTime = () => {
    if (!bookingTime?.value) return;
    const value = bookingTime.value;
    timeScales.forEach((scaleNode) => {
      const slots = scaleNode.querySelectorAll(".timeline__slot");
      slots.forEach((slot) => {
        slot.classList.toggle("is-active", slot.dataset.time === value);
      });
      const indicator = timelineIndicators.get(scaleNode);
      if (!indicator) return;
      const activeSlot = Array.from(slots).find((slot) => slot.dataset.time === value);
      if (!activeSlot) return;
      indicator.style.height = `${activeSlot.offsetHeight}px`;
      indicator.style.transform = `translateY(${activeSlot.offsetTop}px)`;
      indicator.style.opacity = "1";
    });
    syncSummaryLine();
    syncBookingSummary();
  };

  const setTimeMood = () => {
    if (!bookingTime?.value) return;
    const hour = Number(bookingTime.value.split(":")[0]);
    const hourColors = {
      9: "#5C2A27",
      10: "#63302B",
      11: "#6A362F",
      12: "#7A4033",
      13: "#874836",
      14: "#92503A",
      15: "#9B583E",
      16: "#8F4A36",
      17: "#824132",
      18: "#76382E",
      19: "#6A312A",
      20: "#5E2A24",
      21: "#51231E",
      22: "#441C18",
    };
    const clampedHour = Math.max(9, Math.min(22, hour));
    const tone = hourColors[clampedHour] || hourColors[9];
    const hexToRgb = (hex) => {
      const normalized = hex.replace("#", "");
      const value = Number.parseInt(normalized, 16);
      const r = (value >> 16) & 255;
      const g = (value >> 8) & 255;
      const b = value & 255;
      return `${r}, ${g}, ${b}`;
    };
    document.body.style.setProperty("--time-bg-color", tone);
    document.body.style.setProperty("--time-bg-rgb", hexToRgb(tone));
  };

  const syncTimeFromScroll = (scaleNode) => {
    if (!scaleNode || !bookingTime) return;
    const slots = Array.from(scaleNode.querySelectorAll(".timeline__slot"));
    const rect = scaleNode.getBoundingClientRect();
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
        setTimeValue(target.dataset.time);
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
      if (isMobileViewport()) return;
      const isFree = isFreeNow();
      if (neon && hallMap) {
        const mapRect = hallMap.getBoundingClientRect();
        const rect = table.getBoundingClientRect();
        const x = ((rect.left + rect.width / 2 - mapRect.left) / mapRect.width) * 100;
        const y = ((rect.top + rect.height / 2 - mapRect.top) / mapRect.height) * 100;
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
      if (isMobileViewport()) return;
      tooltip.style.left = `${event.clientX}px`;
      tooltip.style.top = `${event.clientY - 18}px`;
    });

    table.addEventListener("mouseleave", () => {
      if (isMobileViewport()) return;
      tooltip.classList.remove("is-visible");
      hallMap?.classList.remove("is-blurred");
      table.classList.remove("table--hovered");
      neon?.classList.remove("is-visible");
    });

    table.addEventListener("click", () => {
      if (!isFreeNow()) return;
      selectedTableId = table.dataset.id;
      selectedTableLabel = table.dataset.label || table.dataset.id;
      bookingTableId.textContent = table.querySelector(".table__top")?.textContent || "";
      bookingTableSeats.textContent = `${seats} места`;
      bookingInfo.textContent = `Столик у окна: ${windowSide}`;
      openBookingPanel();
      tooltip.classList.remove("is-visible");
      table.classList.add("table--hovered");
      updateDateTimeLimits();
      syncBookingSummary();
      refreshAvailability();
    });
  });

  bookingCancel?.addEventListener("click", closeBookingPanel);

  bookingSubmit?.addEventListener("click", async () => {
    if (!selectedTableId) return;
    if (!isDateValid) {
      bookingInfo.textContent = "Укажите корректную дату.";
      return;
    }
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

    const table = document.querySelector(`.table[data-id="${selectedTableId}"]`);
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
      const isInside = bookingPanel && active && bookingPanel.contains(active);
      if (!isInside) hallMap?.classList.remove("is-typing");
    });
  });

  bookingDate?.addEventListener("change", () => {
    setDateValue(bookingDate.value, "booking");
    updateDateTimeLimits();
    updatePastSlots();
    refreshAvailability();
  });

  bookingTime?.addEventListener("change", () => {
    setTimeValue(bookingTime.value);
    updateDateTimeLimits();
    markActiveTime();
    setTimeMood();
    refreshAvailability();
  });

  bookingDateTop?.addEventListener("change", () => {
    setDateValue(bookingDateTop.value, "top");
    updateDateTimeLimits();
    updatePastSlots();
    refreshAvailability();
  });

  bookingDateMobile?.addEventListener("input", () => {
    bookingDateMobile.value = applyDateMask(bookingDateMobile.value);
    const parsedIso = maskedToIsoDate(bookingDateMobile.value);
    if (parsedIso) {
      setDateValue(parsedIso, "mobile");
      updateDateTimeLimits();
      updatePastSlots();
      refreshAvailability();
      return;
    }
    updateDateValidation({ candidateIso: null, rawMasked: bookingDateMobile.value });
  });

  bookingDateMobile?.addEventListener("blur", () => {
    const parsedIso = maskedToIsoDate(bookingDateMobile.value);
    if (parsedIso) {
      setDateValue(parsedIso, "mobile");
      return;
    }
    updateDateValidation({ candidateIso: null, rawMasked: bookingDateMobile.value });
  });

  bookingDateMobile?.addEventListener("focus", () => {
    if (!isMobileViewport()) return;
    if (!bookingDateMobilePicker) return;
    try {
      if (typeof bookingDateMobilePicker.showPicker === "function") {
        bookingDateMobilePicker.showPicker();
      } else {
        bookingDateMobilePicker.click();
      }
    } catch {
      bookingDateMobilePicker.click();
    }
  });

  bookingDateMobilePicker?.addEventListener("change", () => {
    const pickerDate = bookingDateMobilePicker.value;
    if (!pickerDate) return;
    setDateValue(pickerDate, "picker");
    updateDateTimeLimits();
    updatePastSlots();
    refreshAvailability();
  });

  const bindScaleInteractions = (scaleNode) => {
    if (!scaleNode) return;
    scaleNode.addEventListener("scroll", () => {
      window.clearTimeout(scaleNode._t);
      scaleNode._t = window.setTimeout(() => syncTimeFromScroll(scaleNode), 80);
    });
    scaleNode.addEventListener("click", (event) => {
      const slot = event.target.closest(".timeline__slot");
      if (!slot || slot.dataset.past === "1") return;
      setTimeValue(slot.dataset.time);
      markActiveTime();
      setTimeMood();
      refreshAvailability();
    });
  };

  bindScaleInteractions(timeScale);
  bindScaleInteractions(timeScaleMobile);

  openDateTimeSheet?.addEventListener("click", openDateTimeSheetPanel);
  dateTimeClose?.addEventListener("click", closeDateTimeSheet);
  dateTimeApply?.addEventListener("click", () => {
    if (!updateDateValidation()) return;
    closeDateTimeSheet();
  });

  sheetBackdrop?.addEventListener("click", () => {
    if (dateTimeSheet?.classList.contains("is-open")) {
      closeDateTimeSheet();
      return;
    }
    if (bookingPanel?.classList.contains("is-open")) {
      closeBookingPanel();
    }
  });

  window.addEventListener("resize", () => {
    if (!isMobileViewport()) {
      closeDateTimeSheet();
      setBackdropVisible(false);
    } else if (bookingPanel?.classList.contains("is-open") || dateTimeSheet?.classList.contains("is-open")) {
      setBackdropVisible(true);
    }
  });

  updateDateTimeLimits();
  syncSummaryLine();
  syncBookingSummary();
  refreshAvailability();
  markActiveTime();
  setTimeMood();
  updatePastSlots();
  if (bookingDateTop) bookingDateTop.value = bookingDate?.value || "";
  if (bookingDateMobile) bookingDateMobile.value = isoToMaskedDate(bookingDate?.value || "");
  if (bookingDateMobilePicker) bookingDateMobilePicker.value = bookingDate?.value || "";
  updateDateValidation();
};
// Page init: animations + interactions
window.addEventListener("DOMContentLoaded", () => {
  stagger(".news-card", 140);
  stagger(".menu-card", 120);
  setupBottomNavMotion();
  setupTableTooltip();
  setupMenuHoverMood();

  const menuList = document.querySelector(".menu");
  const menuCards = Array.from(document.querySelectorAll(".menu-card--menu"));
  const categoryChips = Array.from(document.querySelectorAll(".menu-chip"));
  const sortToggle = document.getElementById("sortToggle");
  const sortMenu = document.getElementById("sortMenu");
  const sortOptions = Array.from(document.querySelectorAll(".sort-option"));
  const sortValue = document.getElementById("sortValue");
  const cartDrawer = document.getElementById("cartDrawer");
  const cartList = document.getElementById("cartList");
  const cartTotal = document.getElementById("cartTotal");
  const cartCheckout = document.getElementById("cartCheckout");
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
  const cardNumberInput = document.querySelector('input[name="card_number"]');
  const expiryInput = document.querySelector('input[name="expiry"]');
  const holderInput = document.querySelector('input[name="holder"]');
  if (menuList && menuCards.length) {
    const sortLabels = {
      popular: "По популярности",
      "price-asc": "Цена ↑",
      "price-desc": "Цена ↓",
    };
    let activeCategory = "all";
    let activeSort = "popular";
    const normalizeType = (value) =>
      String(value || "")
        .toLowerCase()
        .replace(/\s+/g, " ")
        .trim();

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

    const openSortMenu = () => {
      sortMenu?.classList.add("is-open");
      sortToggle?.setAttribute("aria-expanded", "true");
      sortMenu?.setAttribute("aria-hidden", "false");
    };

    const applyMenuControls = (animate = true) => {
      menuList.classList.toggle("menu--updating", animate);
      const run = () => {
        const selectedType = normalizeType(activeCategory);
        const filtered = menuCards
          .filter((card) => {
            if (selectedType === "all") return true;
            return normalizeType(card.dataset.type) === selectedType;
          })
          .sort(compareCards);

        menuCards.forEach((card) => {
          card.hidden = true;
          card.style.display = "none";
          card.classList.remove("menu-card--reveal");
        });
        filtered.forEach((card, index) => {
          card.hidden = false;
          card.style.display = "";
          menuList.appendChild(card);
          if (animate) {
            card.style.animationDelay = `${index * 28}ms`;
            card.classList.add("menu-card--reveal");
          }
        });

        if (sortValue) {
          sortValue.textContent = sortLabels[activeSort] || sortLabels.popular;
        }
        categoryChips.forEach((chip) => {
          chip.classList.toggle("is-active", chip.dataset.type === activeCategory);
        });
        sortOptions.forEach((option) => {
          option.classList.toggle("is-active", option.dataset.sort === activeSort);
        });
        if (animate) {
          window.setTimeout(() => menuList.classList.remove("menu--updating"), 190);
        }
      };
      if (animate) {
        window.setTimeout(run, 70);
      } else {
        run();
      }
    };

    categoryChips.forEach((chip) => {
      chip.addEventListener("click", () => {
        activeCategory = chip.dataset.type || "all";
        applyMenuControls(true);
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

  const normalizeCart = (cart) =>
    cart
      .map((item) => ({
        ...item,
        id: Number(item.id),
        qty: Number(item.qty) || 0,
        price: Number(item.price) || 0,
      }))
      .filter((item) => item.qty > 0);

  const setDrawerState = (hasItems) => {
    if (!cartDrawer || !menuList) return;
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
    document.body.classList.remove("menu-cart-open");
    cartDrawer._hideTimer = window.setTimeout(() => {
      cartDrawer.hidden = true;
      cartDrawer.setAttribute("aria-hidden", "true");
      cartDrawer.classList.remove("is-closing");
      cartDrawer._hideTimer = null;
    }, 230);
  };

  const updateCartUI = (options = {}) => {
    if (!cartList || !cartTotal) return;
    const previousRows = Array.from(cartList.querySelectorAll(".cart-item"));
    const previousQtyById = new Map(
      previousRows.map((row) => [Number(row.dataset.id), Number(row.dataset.qty)])
    );
    const previousTotal = Number(cartTotal.textContent || 0);
    const cart = normalizeCart(loadCart());
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

    cartTotal.textContent = String(totalPrice);
    if (previousTotal !== totalPrice) {
      cartTotal.closest(".cart-drawer__total")?.classList.add("is-pulse");
      window.setTimeout(() => {
        cartTotal.closest(".cart-drawer__total")?.classList.remove("is-pulse");
      }, 280);
    }
    setDrawerState(cart.length > 0);
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

  cartCheckout?.addEventListener("click", () => {
    const cart = loadCart();
    if (!cart.length) {
      if (cartTotal) cartTotal.textContent = "0";
      return;
    }
    window.location.href = "/checkout";
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
      if (goToPayment) goToPayment.disabled = cart.length === 0;

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
        return;
      }
      const customChecked = Boolean(
        checkoutForm.querySelector('input[name="serve_mode"][value="custom"]')?.checked
      );
      if (customChecked && serveCustomTime && !serveCustomTime.value) {
        event.preventDefault();
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

    paymentConfirmForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (payNowButton.disabled) return;
      setLoading(true);
      const delayMs = 1200 + Math.floor(Math.random() * 700);
      await new Promise((resolve) => window.setTimeout(resolve, delayMs));

      const response = await fetch(paymentConfirmForm.action, {
        method: "POST",
        headers: { "X-Requested-With": "XMLHttpRequest" },
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
  }

  const params = new URLSearchParams(window.location.search);
  if (params.get("paid") === "1") {
    localStorage.removeItem("cart");
    sessionStorage.removeItem("checkout_comment");
  }

  updateCartUI();
});
