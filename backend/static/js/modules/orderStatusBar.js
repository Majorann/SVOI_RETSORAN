const PHRASE_POOLS = {
  waiting: [
    "Ждём время вашей брони",
    "Заказ запланирован заранее",
    "Начнём готовить ближе к вашему приходу",
    "Всё под контролем, ждём нужное время",
    "Заказ принят и ожидает старта",
    "Подготовим всё к вашему визиту",
    "Готовка начнётся вовремя",
    "Заказ в очереди к нужному времени",
    "Всё будет готово к вашей брони",
    "Ожидаем начало приготовления",
  ],
  cooking: [
    "Готовим ваш заказ",
    "На кухне кипит работа",
    "Повар уже колдует",
    "Собираем ваш заказ",
    "Почти готово",
    "Блюдо в процессе",
    "Готовим с пылу с жару",
    "Последние штрихи",
    "Повар уже у плиты",
    "Скоро будет готово",
  ],
  delivering: [
    "Уже несём",
    "Заказ в пути",
    "Идём к вашему столику",
    "Несём горяченькое",
    "Подходим к вам",
    "Уже рядом",
    "Официант в пути",
    "Осталось пару шагов",
    "Ваш заказ уже идёт",
    "Почти у вас",
  ],
  delivered: [
    "Приятного аппетита!",
    "Заказ у вас",
    "Готово!",
    "Наслаждайтесь",
    "Всё подано",
    "Можно пробовать",
    "Заказ доставлен",
    "Приятного вечера",
    "Всё готово",
    "Ваш заказ готов",
  ],
  delivery_cooking: [
    "Готовим ваш заказ для доставки",
    "Кухня собирает заказ в дорогу",
    "Подготавливаем доставку",
    "Собираем пакет для курьера",
    "Готовим к отправке",
  ],
  courier_sent: [
    "Курьер уже выехал",
    "Курьер в пути",
    "Передали заказ курьеру",
    "Заказ передан курьеру",
    "Курьер забрал заказ",
    "Курьер направляется к вам",
    "Заказ едет к вам",
    "Курьер уже в дороге",
    "Доставка началась",
  ],
  delivery_delivering: [
    "Курьер приближается",
    "Уже едем к вам",
    "Почти на месте",
    "Доставка рядом",
    "Остались минуты",
  ],
  delivery_delivered: [
    "Заказ доставлен",
    "Приятного аппетита!",
    "Доставка завершена",
    "Ваш заказ у двери",
    "Готово!",
  ],
};

const STAGE_PRIORITY = {
  delivered: 0,
  delivery_delivered: 0,
  delivering: 1,
  courier_sent: 1,
  delivery_delivering: 1,
  cooking: 2,
  delivery_cooking: 2,
  waiting: 3,
};

const PHASE_DEFS = {
  dine_in: {
    waiting: {
      stageKey: "waiting",
      stageLabel: "Ожидаем время брони",
      icon: "/static/img/time.svg",
    },
    preparing: {
      stageKey: "cooking",
      stageLabel: "Готовим",
      icon: "/static/img/frying_pan.svg",
    },
    delivering: {
      stageKey: "delivering",
      stageLabel: "Несём",
      icon: "/static/img/waiter_pixel.svg",
    },
    served: {
      stageKey: "delivered",
      stageLabel: "Заказ выдан",
      icon: "/static/img/checkmark.svg",
    },
  },
  delivery: {
    cooking: {
      stageKey: "delivery_cooking",
      stageLabel: "Готовим заказ",
      icon: "/static/img/frying_pan.svg",
    },
    courier_sent: {
      stageKey: "courier_sent",
      stageLabel: "Отправили курьера",
      icon: "/static/img/truck.svg",
    },
    delivering: {
      stageKey: "delivery_delivering",
      stageLabel: "Доставляем",
      icon: "/static/img/truck.svg",
    },
    delivered: {
      stageKey: "delivery_delivered",
      stageLabel: "Заказ доставлен",
      icon: "/static/img/checkmark.svg",
    },
  },
};

const PROGRESS_RANGES = {
  waiting: [0.05, 0.05],
  cooking: [0.15, 0.88],
  delivering: [0.88, 0.97],
  delivered: [1, 1],
  delivery_cooking: [0, 0.4],
  courier_sent: [0.4, 0.55],
  delivery_delivering: [0.55, 1],
  delivery_delivered: [1, 1],
};
const TABLO_CHARS = "АБВГДЕЖЗИКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ#_";
const PHRASE_HOLD_MIN_MS = 9000;
const PHRASE_HOLD_MAX_MS = 14000;
const ORDER_STATUS_POLL_INTERVAL_MS = 5000;
const ORDER_STATUS_POLL_BACKOFF_MAX_MS = 30000;

const randomInt = (min, max) =>
  Math.floor(Math.random() * (max - min + 1)) + min;

const formatTimer = (seconds) => {
  const safe = Math.max(0, Math.floor(seconds));
  const mm = String(Math.floor(safe / 60)).padStart(2, "0");
  const ss = String(safe % 60).padStart(2, "0");
  return `${mm}:${ss}`;
};

const formatLongTimer = (seconds) => {
  const safe = Math.max(0, Math.floor(seconds));
  const hh = String(Math.floor(safe / 3600)).padStart(2, "0");
  const mm = String(Math.floor((safe % 3600) / 60)).padStart(2, "0");
  const ss = String(safe % 60).padStart(2, "0");
  return `${hh}:${mm}:${ss}`;
};

const parseIsoToMs = (value, assumeUtc = false) => {
  if (!value) return null;
  const raw = String(value).trim();
  if (!raw) return null;
  const hasExplicitTimezone = /(?:Z|[+-]\d{2}:\d{2})$/i.test(raw);
  const normalized = assumeUtc && !hasExplicitTimezone ? `${raw}Z` : raw;
  const ts = Date.parse(normalized);
  return Number.isFinite(ts) ? ts : null;
};

const pickRandomPhrase = (stageKey, previousPhrase) => {
  const pool = PHRASE_POOLS[stageKey] || [];
  if (!pool.length) return "";
  if (pool.length === 1) return pool[0];

  let picked = pool[randomInt(0, pool.length - 1)];
  let guard = 8;
  while (picked === previousPhrase && guard > 0) {
    picked = pool[randomInt(0, pool.length - 1)];
    guard -= 1;
  }
  return picked;
};

const setupOrderStatusBar = () => {
  const section = document.getElementById("orderStatusSection");
  const bar = document.getElementById("orderStatusBar");
  if (!section || !bar) return;
  if (bar.dataset.initialized === "true") return;

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const reducedMotionForStatusText = false;
  const secondaryRow = document.getElementById("orderStatusSecondary");
  const secondaryTextNode = document.getElementById("orderStatusSecondaryText");
  const iconNode = document.getElementById("orderStatusIcon");
  const titleNode = document.getElementById("orderStatusTitle");
  const orderNode = document.getElementById("orderStatusOrder");
  const moreNode = document.getElementById("orderStatusMore");
  const textNode = document.getElementById("orderStatusText");
  const timerNode = document.getElementById("orderStatusTimer");
  const progressNode = document.getElementById("orderStatusProgress");
  const deliveryLoopNode = document.getElementById("deliveryProgressLoop");
  const expandedNode = document.getElementById("orderStatusExpanded");
  const listNode = document.getElementById("orderStatusList");

  const rawOrders = bar.dataset.orders || "[]";
  let initialOrders = [];
  try {
    initialOrders = JSON.parse(rawOrders);
  } catch {
    initialOrders = [];
  }
  if (!Array.isArray(initialOrders) || !initialOrders.length) {
    section.hidden = true;
    bar.hidden = true;
    return;
  }
  bar.dataset.initialized = "true";
  section.hidden = false;
  bar.hidden = false;

  const phraseState = {
    stageKey: "",
    phrase: "",
    nextChangeAtMs: 0,
  };

  let isExpanded = false;
  let timerId = null;
  let pollId = null;
  let pollInFlight = false;
  let pollDelayMs = ORDER_STATUS_POLL_INTERVAL_MS;
  let statusesSnapshotAtMs = Date.now();
  let lastPrimarySignature = "";
  let statusAnimationToken = 0;
  let statusTypingTimeoutId = null;
  let statusTextCurrent = textNode?.textContent?.trim() || "";
  let statusTargetText = statusTextCurrent;
  let titleAnimationToken = 0;
  let stageTitleCurrent = titleNode?.textContent?.trim() || "";
  let stageTitleTarget = stageTitleCurrent;
  let expandedTransitionCleanup = null;

  const sleep = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));

  const clearStatusTypingTimeout = () => {
    if (statusTypingTimeoutId !== null) {
      window.clearTimeout(statusTypingTimeoutId);
      statusTypingTimeoutId = null;
    }
  };

  const scheduleStatusTypingStep = (fn, delayMs) => {
    statusTypingTimeoutId = window.setTimeout(fn, delayMs);
  };

  const animateStatusText = (nextText) => {
    if (!textNode || !nextText) return;
    if (nextText === statusTargetText) return;
    statusTargetText = nextText;

    const token = ++statusAnimationToken;
    clearStatusTypingTimeout();

    if (reducedMotionForStatusText) {
      textNode.classList.remove("is-fade");
      void textNode.offsetWidth;
      textNode.textContent = nextText;
      textNode.classList.add("is-fade");
      statusTextCurrent = nextText;
      return;
    }

    const eraseStepMs = 78;
    const typeStepMs = 118;
    const swapPauseMs = 320;

    bar.classList.add("is-status-typing");

    const typeNext = (index) => {
      if (token !== statusAnimationToken) return;
      textNode.textContent = nextText.slice(0, index);
      if (index < nextText.length) {
        scheduleStatusTypingStep(() => typeNext(index + 1), typeStepMs);
        return;
      }
      statusTextCurrent = nextText;
      bar.classList.remove("is-status-typing");
      statusTypingTimeoutId = null;
    };

    const erasePrev = (index) => {
      if (token !== statusAnimationToken) return;
      textNode.textContent = statusTextCurrent.slice(0, index);
      if (index > 0) {
        scheduleStatusTypingStep(() => erasePrev(index - 1), eraseStepMs);
        return;
      }
      scheduleStatusTypingStep(() => typeNext(1), swapPauseMs);
    };

    erasePrev(statusTextCurrent.length);
  };

  const randomTabloChar = () => TABLO_CHARS[randomInt(0, TABLO_CHARS.length - 1)];

  const animateStageTitle = async (nextTitle) => {
    if (!titleNode || !nextTitle) return;
    if (nextTitle === stageTitleTarget) return;
    stageTitleTarget = nextTitle;

    const token = ++titleAnimationToken;

    if (reducedMotion) {
      titleNode.classList.remove("is-fade");
      void titleNode.offsetWidth;
      titleNode.textContent = nextTitle;
      titleNode.classList.add("is-fade");
      stageTitleCurrent = nextTitle;
      return;
    }

    const prevText = stageTitleCurrent || "";
    const maxLen = Math.max(prevText.length, nextTitle.length);
    const frames = 10;

    bar.classList.add("is-title-scrambling");

    for (let frame = 0; frame <= frames; frame += 1) {
      if (token !== titleAnimationToken) return;
      const revealCount = Math.floor((frame / frames) * nextTitle.length);
      let output = "";

      for (let i = 0; i < maxLen; i += 1) {
        if (i < revealCount && i < nextTitle.length) {
          output += nextTitle[i];
          continue;
        }
        if (i >= nextTitle.length) continue;
        output += randomTabloChar();
      }

      titleNode.textContent = output || nextTitle;
      await sleep(34);
    }

    titleNode.textContent = nextTitle;
    stageTitleCurrent = nextTitle;
    bar.classList.remove("is-title-scrambling");
  };

  const resolveStagePhrase = (stageKey, nowMs) => {
    if (phraseState.stageKey !== stageKey) {
      phraseState.stageKey = stageKey;
      phraseState.phrase = pickRandomPhrase(stageKey, "");
      phraseState.nextChangeAtMs = nowMs + randomInt(PHRASE_HOLD_MIN_MS, PHRASE_HOLD_MAX_MS);
      return phraseState.phrase;
    }

    if (nowMs >= phraseState.nextChangeAtMs) {
      phraseState.phrase = pickRandomPhrase(stageKey, phraseState.phrase);
      phraseState.nextChangeAtMs = nowMs + randomInt(PHRASE_HOLD_MIN_MS, PHRASE_HOLD_MAX_MS);
    }

    return phraseState.phrase;
  };

  const resolveProgressRatio = (stageKey, stagePhaseRatio) => {
    const [start, end] = PROGRESS_RANGES[stageKey] || [0.15, 0.88];
    const ratio = Math.max(0, Math.min(1, stagePhaseRatio));
    return start + (end - start) * ratio;
  };

  const resolveOrderState = (order) => {
    const orderId = Number(order?.order_id);
    const flow = String(order?.order_type || "dine_in") === "delivery" ? "delivery" : "dine_in";
    const backendPhase = String(order?.phase || "");
    const phaseDef = PHASE_DEFS[flow]?.[backendPhase];
    if (!Number.isFinite(orderId) || !phaseDef) return null;
    if (flow === "delivery" && phaseDef.stageKey === "delivery_delivered") return null;

    const elapsedFromSnapshot = Math.max(0, Math.floor((Date.now() - statusesSnapshotAtMs) / 1000));
    const rawRemainingSeconds = Math.max(0, Number(order?.phase_remaining_seconds) || 0);
    const rawEtaRemainingSeconds = Math.max(0, Number(order?.eta_remaining_seconds) || 0);
    const remainingFromSnapshot = Math.max(0, rawRemainingSeconds - elapsedFromSnapshot);
    const etaFromSnapshot = Math.max(0, rawEtaRemainingSeconds - elapsedFromSnapshot);
    const phaseEndMs = parseIsoToMs(order?.phase_ends_at, true);
    const phaseRemainingByDeadline = phaseEndMs === null
      ? null
      : Math.max(0, Math.ceil((phaseEndMs - Date.now()) / 1000));
    const cycleStartMs = parseIsoToMs(order?.cycle_started_at, true);
    const etaTotalSeconds = Number(order?.eta_total_seconds);
    const etaEndMs = (cycleStartMs !== null && Number.isFinite(etaTotalSeconds))
      ? cycleStartMs + (etaTotalSeconds * 1000)
      : null;
    const etaRemainingByDeadline = etaEndMs === null
      ? null
      : Math.max(0, Math.ceil((etaEndMs - Date.now()) / 1000));
    const remainingSeconds = phaseRemainingByDeadline ?? remainingFromSnapshot;
    const etaRemainingSeconds = etaRemainingByDeadline ?? etaFromSnapshot;
    const phaseProgress = Number(order?.phase_progress_ratio);
    const phaseRatio = Number.isFinite(phaseProgress)
      ? Math.max(0, Math.min(1, phaseProgress))
      : 0;
    const backendTargetSecondsRaw = Number(order?.time_to_target_seconds);
    const backendTargetSeconds = Number.isFinite(backendTargetSecondsRaw)
      ? Math.max(0, Math.floor(backendTargetSecondsRaw) - elapsedFromSnapshot)
      : null;
    const fallbackTargetSeconds = flow === "delivery" ? etaRemainingSeconds : remainingSeconds;
    const timeToTargetSeconds = backendTargetSeconds ?? fallbackTargetSeconds;

    const timer = phaseDef.stageKey === "waiting"
      ? formatLongTimer(remainingSeconds)
      : flow === "delivery"
        ? formatTimer(etaRemainingSeconds)
      : formatTimer(remainingSeconds);
    const rowTimer = flow === "delivery"
      ? `ETA ${formatTimer(etaRemainingSeconds)}`
      : phaseDef.stageKey === "waiting"
        ? `До вашей брони ${formatLongTimer(remainingSeconds)}`
      : formatTimer(remainingSeconds);

    return {
      orderId,
      flow,
      backendPhase,
      stageKey: phaseDef.stageKey,
      stageLabel: phaseDef.stageLabel,
      icon: phaseDef.icon,
      timer,
      remainingSeconds,
      timeToTargetSeconds,
      progressRatio: resolveProgressRatio(phaseDef.stageKey, phaseRatio),
      rowText: `Заказ №${orderId} — ${phaseDef.stageLabel} • ${rowTimer}`,
    };
  };

  const resolveActiveStates = () => {
    const active = [];
    for (const order of initialOrders) {
      const state = resolveOrderState(order);
      if (state) active.push(state);
    }

    active.sort((a, b) => {
      const targetDiff = a.timeToTargetSeconds - b.timeToTargetSeconds;
      if (targetDiff !== 0) return targetDiff;
      const phaseDiff = (STAGE_PRIORITY[a.stageKey] ?? 99) - (STAGE_PRIORITY[b.stageKey] ?? 99);
      if (phaseDiff !== 0) return phaseDiff;
      const remainingDiff = a.remainingSeconds - b.remainingSeconds;
      if (remainingDiff !== 0) return remainingDiff;
      return (a.orderId || 0) - (b.orderId || 0);
    });

    return active;
  };

  const setExpanded = (nextExpanded) => {
    isExpanded = Boolean(nextExpanded);
    bar.classList.toggle("is-expanded", isExpanded);
    bar.setAttribute("aria-expanded", isExpanded ? "true" : "false");
    if (!expandedNode) return;

    if (expandedTransitionCleanup) {
      expandedTransitionCleanup();
      expandedTransitionCleanup = null;
    }

    if (isExpanded) {
      expandedNode.hidden = false;
      expandedNode.style.maxHeight = "0px";
      expandedNode.style.opacity = "0";
      expandedNode.style.transform = "translateY(-6px)";
      void expandedNode.offsetHeight;
      expandedNode.style.maxHeight = `${expandedNode.scrollHeight}px`;
      expandedNode.style.opacity = "1";
      expandedNode.style.transform = "translateY(0)";

      const handleExpandEnd = (event) => {
        if (event.target !== expandedNode || event.propertyName !== "max-height") return;
        expandedNode.removeEventListener("transitionend", handleExpandEnd);
        expandedNode.style.maxHeight = "none";
        expandedTransitionCleanup = null;
      };

      expandedNode.addEventListener("transitionend", handleExpandEnd);
      expandedTransitionCleanup = () => {
        expandedNode.removeEventListener("transitionend", handleExpandEnd);
      };
      return;
    }

    expandedNode.style.maxHeight = `${expandedNode.scrollHeight}px`;
    expandedNode.style.opacity = "1";
    expandedNode.style.transform = "translateY(0)";
    void expandedNode.offsetHeight;
    expandedNode.style.maxHeight = "0px";
    expandedNode.style.opacity = "0";
    expandedNode.style.transform = "translateY(-6px)";

    const handleCollapseEnd = (event) => {
      if (event.target !== expandedNode || event.propertyName !== "max-height") return;
      expandedNode.removeEventListener("transitionend", handleCollapseEnd);
      expandedNode.hidden = true;
      expandedTransitionCleanup = null;
    };

    expandedNode.addEventListener("transitionend", handleCollapseEnd);
    expandedTransitionCleanup = () => {
      expandedNode.removeEventListener("transitionend", handleCollapseEnd);
    };
  };

  const toggleExpanded = () => {
    if (!resolveActiveStates().length) return;
    setExpanded(!isExpanded);
  };

  const removeStatusBar = () => {
    if (timerId) {
      window.clearInterval(timerId);
      timerId = null;
    }
    if (pollId) {
      window.clearTimeout(pollId);
      pollId = null;
    }
    clearStatusTypingTimeout();
    bar.classList.add("is-exiting");
    window.setTimeout(() => {
      section.hidden = true;
      bar.hidden = true;
    }, 260);
  };

  const renderExpandedList = (states) => {
    if (!listNode) return;
    const visible = states.slice(0, 3);
    listNode.innerHTML = visible
      .map((item) => `<div class="order-status-bar__row">${item.rowText}</div>`)
      .join("");
  };

  const stopRenderTimer = () => {
    if (timerId) {
      window.clearInterval(timerId);
      timerId = null;
    }
  };

  const ensureRenderTimer = () => {
    if (timerId || document.hidden) return;
    timerId = window.setInterval(() => {
      render();
    }, 1000);
  };

  const stopPolling = () => {
    if (pollId) {
      window.clearTimeout(pollId);
      pollId = null;
    }
  };

  const scheduleNextPoll = (delayMs = pollDelayMs) => {
    stopPolling();
    if (document.hidden) return;
    pollId = window.setTimeout(() => {
      void fetchOrderStatuses();
    }, delayMs);
  };

  const fetchOrderStatuses = async () => {
    if (document.hidden) {
      stopPolling();
      return;
    }
    if (pollInFlight) {
      scheduleNextPoll();
      return;
    }
    pollInFlight = true;
    let nextDelayMs = ORDER_STATUS_POLL_INTERVAL_MS;
    try {
      const response = await fetch("/api/order-statuses", {
        method: "GET",
        headers: { "X-Requested-With": "XMLHttpRequest" },
        cache: "no-store",
      });
      if (!response.ok) {
        nextDelayMs = Math.min(pollDelayMs * 2, ORDER_STATUS_POLL_BACKOFF_MAX_MS);
        return;
      }
      const payload = await response.json().catch(() => null);
      if (!payload || !Array.isArray(payload.order_statuses)) {
        nextDelayMs = Math.min(pollDelayMs * 2, ORDER_STATUS_POLL_BACKOFF_MAX_MS);
        return;
      }
      initialOrders = payload.order_statuses;
      statusesSnapshotAtMs = Date.now();
      pollDelayMs = ORDER_STATUS_POLL_INTERVAL_MS;
      render();
    } catch {
      nextDelayMs = Math.min(pollDelayMs * 2, ORDER_STATUS_POLL_BACKOFF_MAX_MS);
      // Ignore transient polling errors; next tick will retry.
    } finally {
      pollInFlight = false;
      pollDelayMs = nextDelayMs;
      if (!document.hidden) {
        scheduleNextPoll(nextDelayMs);
      }
    }
  };

  const render = () => {
    const activeStates = resolveActiveStates();
    if (!activeStates.length) {
      removeStatusBar();
      return false;
    }

    const primary = activeStates[0];
    const next = activeStates[1] || null;
    const moreCount = Math.max(0, activeStates.length - 1);
    const signature = `${primary.orderId}:${primary.stageKey}`;

    if (signature !== lastPrimarySignature) {
      bar.classList.remove("is-phase-changing");
      void bar.offsetWidth;
      bar.classList.add("is-phase-changing");
      window.setTimeout(() => bar.classList.remove("is-phase-changing"), 240);
      lastPrimarySignature = signature;
      phraseState.nextChangeAtMs = 0;
    }

    const nowMs = Date.now();
    const statusPhrase = resolveStagePhrase(primary.stageKey, nowMs);

    bar.dataset.phase = primary.backendPhase;
    bar.dataset.stage = primary.stageKey;
    bar.dataset.flow = primary.flow;

    if (iconNode) {
      if (typeof primary.icon === "string" && primary.icon.startsWith("/static/")) {
        iconNode.innerHTML = `<img src="${primary.icon}" alt="" />`;
      } else {
        iconNode.textContent = primary.icon;
      }
    }

    void animateStageTitle(primary.stageLabel);
    if (orderNode) orderNode.textContent = `Заказ №${primary.orderId}`;
    if (timerNode) timerNode.textContent = primary.timer;
    if (progressNode) {
      const widthPercent = Math.round(Math.max(0, Math.min(1, primary.progressRatio)) * 1000) / 10;
      progressNode.style.width = `${widthPercent}%`;
      bar
        .querySelector(".order-status-bar__progress")
        ?.setAttribute("aria-valuenow", String(Math.round(widthPercent)));
    }

    if (deliveryLoopNode) {
      const showRoadLoop = primary.flow === "delivery"
        && (primary.stageKey === "delivery_cooking"
          || primary.stageKey === "courier_sent"
          || primary.stageKey === "delivery_delivering");
      const showTruck = primary.flow === "delivery"
        && (primary.stageKey === "courier_sent" || primary.stageKey === "delivery_delivering");
      deliveryLoopNode.hidden = !showRoadLoop;
      bar.dataset.deliveryVehicle = showTruck ? "on" : "off";
    }

    void animateStatusText(statusPhrase);

    if (secondaryRow && secondaryTextNode) {
      if (next) {
        secondaryRow.hidden = false;
        secondaryTextNode.textContent = `Следующий: заказ №${next.orderId} — ${next.stageLabel}`;
      } else {
        secondaryRow.hidden = true;
      }
    }

    if (moreNode) {
      if (moreCount > 0) {
        moreNode.hidden = false;
        moreNode.textContent = `+${moreCount}`;
      } else {
        moreNode.hidden = true;
      }
    }

    renderExpandedList(activeStates);
    return true;
  };

  bar.addEventListener("click", () => toggleExpanded());
  bar.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    toggleExpanded();
  });

  window.requestAnimationFrame(() => bar.classList.add("is-entered"));
  if (!render()) return;

  setExpanded(false);
  ensureRenderTimer();
  scheduleNextPoll(ORDER_STATUS_POLL_INTERVAL_MS);

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      stopRenderTimer();
      stopPolling();
      return;
    }
    render();
    ensureRenderTimer();
    pollDelayMs = ORDER_STATUS_POLL_INTERVAL_MS;
    void fetchOrderStatuses();
  });
};

export { setupOrderStatusBar };
