import { getCsrfToken } from "./core.js";

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

  const clearHoveredTables = (exceptTable = null) => {
    document.querySelectorAll(".table.table--hovered").forEach((tableNode) => {
      if (exceptTable && tableNode === exceptTable) return;
      tableNode.classList.remove("table--hovered");
    });
  };

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
    clearHoveredTables();
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
      clearHoveredTables(table);
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
    const csrfToken = getCsrfToken();
    const response = await fetch("/book", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(csrfToken ? { "X-CSRF-Token": csrfToken } : {}),
      },
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
export { setupTableTooltip };

