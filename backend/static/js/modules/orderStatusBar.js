const PHRASE_POOLS = {
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
};

const STAGE_PRIORITY = { delivered: 0, delivering: 1, cooking: 2 };

const PHASE_DEFS = [
  {
    backendKey: "preparing",
    stageKey: "cooking",
    stageLabel: "Готовим",
    durationSeconds: 15 * 60,
    icon: "/static/img/frying-pan-svgrepo-com.svg",
  },
  {
    backendKey: "delivering",
    stageKey: "delivering",
    stageLabel: "Несём",
    durationSeconds: 60,
    icon: "/static/img/waiter.svg",
  },
  {
    backendKey: "served",
    stageKey: "delivered",
    stageLabel: "Заказ выдан",
    durationSeconds: 60,
    icon: "✓",
  },
];

const PROGRESS_RANGES = {
  cooking: [0.2, 0.6],
  delivering: [0.65, 0.9],
  delivered: [1, 1],
};
const TABLO_CHARS = "АБВГДЕЖЗИКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ#_";
const PHRASE_HOLD_MIN_MS = 9000;
const PHRASE_HOLD_MAX_MS = 14000;

const randomInt = (min, max) =>
  Math.floor(Math.random() * (max - min + 1)) + min;

const formatTimer = (seconds) => {
  const safe = Math.max(0, Math.floor(seconds));
  const mm = String(Math.floor(safe / 60)).padStart(2, "0");
  const ss = String(safe % 60).padStart(2, "0");
  return `${mm}:${ss}`;
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
  const bar = document.getElementById("orderStatusBar");
  if (!bar) return;

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
  const expandedNode = document.getElementById("orderStatusExpanded");
  const listNode = document.getElementById("orderStatusList");

  const rawOrders = bar.dataset.orders || "[]";
  let initialOrders = [];
  try {
    initialOrders = JSON.parse(rawOrders);
  } catch {
    initialOrders = [];
  }
  if (!Array.isArray(initialOrders) || !initialOrders.length) return;

  const totalDuration = PHASE_DEFS.reduce((sum, phase) => sum + phase.durationSeconds, 0);
  const phaseOffsets = [];
  let offset = 0;
  for (const phase of PHASE_DEFS) {
    phaseOffsets.push({ ...phase, start: offset, end: offset + phase.durationSeconds });
    offset += phase.durationSeconds;
  }

  const phraseState = {
    stageKey: "",
    phrase: "",
    nextChangeAtMs: 0,
  };

  let isExpanded = false;
  let timerId = null;
  let lastPrimarySignature = "";
  let statusAnimationToken = 0;
  let statusTypingTimeoutId = null;
  let statusTextCurrent = textNode?.textContent?.trim() || "";
  let statusTargetText = statusTextCurrent;
  let titleAnimationToken = 0;
  let stageTitleCurrent = titleNode?.textContent?.trim() || "";
  let stageTitleTarget = stageTitleCurrent;

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
    const [start, end] = PROGRESS_RANGES[stageKey] || [0.2, 0.6];
    const ratio = Math.max(0, Math.min(1, stagePhaseRatio));
    return start + (end - start) * ratio;
  };

  const resolveOrderState = (order) => {
    const cycleStartedAtMs = Date.parse(order?.cycle_started_at || "");
    if (!Number.isFinite(cycleStartedAtMs)) return null;

    const elapsedSeconds = Math.max(0, Math.floor((Date.now() - cycleStartedAtMs) / 1000));
    if (elapsedSeconds >= totalDuration) return null;

    for (const phase of phaseOffsets) {
      if (elapsedSeconds >= phase.end) continue;

      const stageElapsedSeconds = elapsedSeconds - phase.start;
      const remainingSeconds = Math.max(0, phase.durationSeconds - stageElapsedSeconds);
      const stagePhaseRatio = phase.durationSeconds
        ? stageElapsedSeconds / phase.durationSeconds
        : 1;

      return {
        orderId: order.order_id,
        backendPhase: phase.backendKey,
        stageKey: phase.stageKey,
        stageLabel: phase.stageLabel,
        icon: phase.icon,
        timer: formatTimer(remainingSeconds),
        remainingSeconds,
        progressRatio: resolveProgressRatio(phase.stageKey, stagePhaseRatio),
        rowText: `Заказ №${order.order_id} — ${phase.stageLabel} • ${formatTimer(remainingSeconds)}`,
      };
    }

    return null;
  };

  const resolveActiveStates = () => {
    const active = [];
    for (const order of initialOrders) {
      const state = resolveOrderState(order);
      if (state) active.push(state);
    }

    active.sort((a, b) => {
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
    if (expandedNode) expandedNode.hidden = !isExpanded;
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
    clearStatusTypingTimeout();
    bar.classList.add("is-exiting");
    const container = bar.closest(".order-status-section");
    window.setTimeout(() => {
      if (container) container.remove();
    }, 260);
  };

  const renderExpandedList = (states) => {
    if (!listNode) return;
    const visible = states.slice(0, 3);
    listNode.innerHTML = visible
      .map((item) => `<div class="order-status-bar__row">${item.rowText}</div>`)
      .join("");
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
  timerId = window.setInterval(() => {
    render();
  }, 1000);

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) render();
  });
};

export { setupOrderStatusBar };
