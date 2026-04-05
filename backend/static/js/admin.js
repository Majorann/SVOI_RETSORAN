const toastStack = document.getElementById("adminToastStack");
const appRoot = document.querySelector(".admin-app");
const modal = document.getElementById("adminActionModal");
const modalTitle = document.getElementById("adminModalTitle");
const modalText = document.getElementById("adminModalText");
const modalReason = document.getElementById("adminModalReason");
const modalConfirm = document.getElementById("adminModalConfirm");
const drawer = document.getElementById("adminDetailDrawer");
const drawerTitle = document.getElementById("adminDrawerTitle");
const drawerBody = document.getElementById("adminDrawerBody");
const networkLoader = document.getElementById("adminNetworkLoader");
const networkLoaderText = document.getElementById("adminNetworkLoaderText");

let currentAction = null;

const adminNetworkActivity = (() => {
  if (!(networkLoader instanceof HTMLElement)) {
    return {
      begin: () => null,
      end: () => {},
      beginNavigation: () => {},
      restoreNavigation: () => {},
    };
  }

  const persistedNavigationKey = "adminLoaderNavigation";
  const minVisibleMs = 960;
  const resolveMs = 560;
  const restoredNavigationMaxAgeMs = 4000;
  const restoreVisibleMs = 320;
  let pendingCount = 0;
  let visibleSince = 0;
  let resolveTimer = 0;
  let hideTimer = 0;
  let currentLabel = "раздел";

  const formatLoadingLabel = (label) => {
    const normalized = String(label || "раздел").trim();
    if (!normalized) {
      return "Грузим раздел";
    }
    return `Грузим ${normalized}`;
  };

  const syncLabel = (label) => {
    currentLabel = String(label || currentLabel || "раздел").trim() || "раздел";
    if (networkLoaderText) {
      networkLoaderText.textContent = formatLoadingLabel(currentLabel);
    }
  };

  const applyState = (state, label) => {
    networkLoader.dataset.state = state;
    networkLoader.setAttribute("aria-hidden", state === "idle" ? "true" : "false");
    syncLabel(label);
  };

  const clearTimers = () => {
    window.clearTimeout(resolveTimer);
    window.clearTimeout(hideTimer);
  };

  const open = (label) => {
    clearTimers();
    visibleSince = Date.now();
    applyState("loading", label);
  };

  const resolve = (label = "") => {
    clearTimers();
    applyState("resolve", label || currentLabel);
    hideTimer = window.setTimeout(() => {
      applyState("idle", "");
    }, resolveMs);
  };

  const scheduleClose = (label) => {
    const elapsed = Date.now() - visibleSince;
    const wait = Math.max(0, minVisibleMs - elapsed);
    clearTimers();
    resolveTimer = window.setTimeout(() => resolve(label), wait);
  };

  const begin = (label = "данные") => {
    pendingCount += 1;
    if (pendingCount === 1) {
      open(label);
    } else {
      syncLabel(label);
    }
    return Symbol("admin-network-activity");
  };

  const end = (_token, label = "") => {
    pendingCount = Math.max(0, pendingCount - 1);
    if (pendingCount === 0) {
      scheduleClose(label);
    }
  };

  const beginNavigation = (label = "раздел") => {
    try {
      sessionStorage.setItem(
        persistedNavigationKey,
        JSON.stringify({ label, at: Date.now() })
      );
    } catch (error) {
      // Ignore session storage errors, navigation hint is optional.
    }
    open(label);
  };

  const restoreNavigation = () => {
    let payload = null;
    try {
      payload = JSON.parse(sessionStorage.getItem(persistedNavigationKey) || "null");
      sessionStorage.removeItem(persistedNavigationKey);
    } catch (error) {
      payload = null;
    }
    if (!payload || Date.now() - Number(payload.at || 0) > restoredNavigationMaxAgeMs) {
      return;
    }
    open(payload.label || "раздел");
    const finalizeRestore = () => {
      window.setTimeout(() => {
        scheduleClose("");
      }, restoreVisibleMs);
    };
    if (document.readyState === "complete") {
      finalizeRestore();
      return;
    }
    window.addEventListener("load", finalizeRestore, { once: true });
  };

  return { begin, end, beginNavigation, restoreNavigation };
})();

window.adminLoaderDebug = {
  loading(label = "раздел") {
    if (networkLoader instanceof HTMLElement) {
      networkLoader.dataset.state = "loading";
      networkLoader.setAttribute("aria-hidden", "false");
      if (networkLoaderText) networkLoaderText.textContent = `Грузим ${String(label || "раздел").trim() || "раздел"}`;
    }
  },
  resolve(label = "раздел") {
    if (networkLoader instanceof HTMLElement) {
      networkLoader.dataset.state = "resolve";
      networkLoader.setAttribute("aria-hidden", "false");
      if (networkLoaderText) networkLoaderText.textContent = `Грузим ${String(label || "раздел").trim() || "раздел"}`;
    }
  },
  idle() {
    if (networkLoader instanceof HTMLElement) {
      networkLoader.dataset.state = "idle";
      networkLoader.setAttribute("aria-hidden", "true");
    }
  },
};

adminNetworkActivity.restoreNavigation();

document.querySelectorAll("[data-admin-loader-nav]").forEach((link) => {
  link.addEventListener("click", (event) => {
    if (!(link instanceof HTMLAnchorElement)) return;
    if (
      event.defaultPrevented ||
      event.button !== 0 ||
      link.target === "_blank" ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey
    ) {
      return;
    }
    const href = link.getAttribute("href") || "";
    if (!href || href.startsWith("#")) return;
    const nextUrl = new URL(link.href, window.location.href);
    if (
      nextUrl.pathname === window.location.pathname &&
      nextUrl.search === window.location.search &&
      nextUrl.hash === window.location.hash
    ) {
      return;
    }
    adminNetworkActivity.beginNavigation(link.dataset.adminLoaderLabel || link.textContent?.trim() || "раздел");
  });
});

document.querySelectorAll("form").forEach((form) => {
  form.addEventListener("submit", (event) => {
    if (!(form instanceof HTMLFormElement) || event.defaultPrevented) return;
    if ((form.target || "").toLowerCase() === "_blank") return;
    adminNetworkActivity.beginNavigation(
      form.dataset.adminLoaderLabel ||
        (String(form.method || "get").toLowerCase() === "get" ? "раздел" : "форму")
    );
  });
});

if (typeof window.fetch === "function") {
  const nativeFetch = window.fetch.bind(window);
  window.fetch = async (...args) => {
    const [resource, init] = args;
    const url =
      typeof resource === "string"
        ? resource
        : resource instanceof Request
          ? resource.url
          : "";
    const method =
      String(
        (init && typeof init === "object" && "method" in init ? init.method : null) ||
        (resource instanceof Request ? resource.method : "GET")
      ).toUpperCase();
    const label =
      url.includes("/promo/validate")
        ? "акцию"
        : method === "GET"
          ? "данные"
          : "изменения";
    const ticket = adminNetworkActivity.begin(label);
    try {
      return await nativeFetch(...args);
    } finally {
      adminNetworkActivity.end(ticket, "");
    }
  };
}

const showToast = (message, kind = "info") => {
  if (!toastStack || !message) return;
  const node = document.createElement("div");
  node.className = `admin-toast admin-toast--${kind}`;
  node.textContent = message;
  toastStack.appendChild(node);
  window.setTimeout(() => node.remove(), 3200);
};

const openModal = (config) => {
  currentAction = config;
  modalTitle.textContent = config.title || "Подтвердите действие";
  modalText.textContent = config.message || "Действие будет записано в журнал.";
  modalReason.value = "";
  modal.hidden = false;
  modalReason.focus();
};

const closeModal = () => {
  modal.hidden = true;
  currentAction = null;
};

const openDrawer = (title, body) => {
  drawerTitle.textContent = title || "Карточка";
  drawerBody.textContent = body || "";
  drawer.hidden = false;
};

const closeDrawer = () => {
  drawer.hidden = true;
};

document.querySelectorAll("[data-modal-close]").forEach((node) => node.addEventListener("click", closeModal));
document.querySelectorAll("[data-drawer-close]").forEach((node) => node.addEventListener("click", closeDrawer));

document.querySelectorAll("[data-drawer-title]").forEach((button) => {
  button.addEventListener("click", () => openDrawer(button.dataset.drawerTitle, button.dataset.drawerBody));
});

document.querySelectorAll("[data-admin-api]").forEach((button) => {
  button.addEventListener("click", () => {
    openModal({
      api: button.dataset.adminApi,
      title: button.dataset.adminTitle,
      message: button.dataset.adminMessage,
      payloadSource: button.dataset.adminPayloadSource,
      payloadKey: button.dataset.adminPayloadKey,
      redirectUrl: button.dataset.adminRedirectUrl,
    });
  });
});

modalConfirm?.addEventListener("click", async () => {
  if (!currentAction) return;
  const action = currentAction;
  const reason = modalReason.value.trim();
  if (!reason) {
    showToast("Причина обязательна.", "error");
    modalReason.focus();
    return;
  }
  const payload = { reason };
  if (action.payloadSource && action.payloadKey) {
    const source = document.getElementById(action.payloadSource);
    payload[action.payloadKey] = source ? source.value : "";
  }
  try {
    const response = await fetch(action.api, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": document.querySelector('meta[name="csrf-token"]')?.content || "",
      },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "Не удалось выполнить действие.");
    }
    closeModal();
    sessionStorage.setItem("adminToast", data.toast || "Действие выполнено.");
    const redirectUrl = action.redirectUrl || data.redirect_url || "";
    if (redirectUrl) {
      window.location.assign(redirectUrl);
      return;
    }
    window.location.reload();
  } catch (error) {
    showToast(error.message || "Ошибка запроса.", "error");
  }
});

const persistedToast = sessionStorage.getItem("adminToast");
if (persistedToast) {
  showToast(persistedToast);
  sessionStorage.removeItem("adminToast");
}
if (appRoot?.dataset.toast) {
  showToast(appRoot.dataset.toast);
}

const closeAdminSelects = (except = null) => {
  document.querySelectorAll(".admin-select-wrap.is-open").forEach((wrap) => {
    if (wrap === except) return;
    wrap.classList.remove("is-open");
    const trigger = wrap.querySelector(".admin-select-trigger");
    if (trigger) trigger.setAttribute("aria-expanded", "false");
  });
};

const enhanceAdminSelects = () => {
  document.querySelectorAll("select.admin-select:not([data-admin-enhanced])").forEach((select) => {
    select.dataset.adminEnhanced = "1";
    const wrapper = document.createElement("div");
    wrapper.className = "admin-select-wrap";
    const trigger = document.createElement("button");
    trigger.type = "button";
    trigger.className = "admin-select-trigger";
    trigger.setAttribute("aria-haspopup", "listbox");
    trigger.setAttribute("aria-expanded", "false");
    const menu = document.createElement("div");
    menu.className = "admin-select-menu";
    menu.setAttribute("role", "listbox");

    select.classList.add("admin-select-native");
    select.parentNode.insertBefore(wrapper, select);
    wrapper.append(select, trigger, menu);

    const syncFromSelect = () => {
      const selectedOption = select.options[select.selectedIndex];
      trigger.textContent = selectedOption ? selectedOption.textContent : "Выберите значение";
      menu.innerHTML = "";
      Array.from(select.options).forEach((option) => {
        const optionButton = document.createElement("button");
        optionButton.type = "button";
        optionButton.className = "admin-select-option";
        optionButton.textContent = option.textContent;
        optionButton.disabled = option.disabled;
        optionButton.dataset.value = option.value;
        if (option.selected) optionButton.classList.add("is-selected");
        optionButton.addEventListener("click", () => {
          select.value = option.value;
          select.dispatchEvent(new Event("input", { bubbles: true }));
          select.dispatchEvent(new Event("change", { bubbles: true }));
          closeAdminSelects();
        });
        menu.append(optionButton);
      });
    };

    trigger.addEventListener("click", () => {
      const isOpen = wrapper.classList.contains("is-open");
      if (isOpen) {
        closeAdminSelects();
        return;
      }
      closeAdminSelects(wrapper);
      wrapper.classList.add("is-open");
      trigger.setAttribute("aria-expanded", "true");
    });

    select.addEventListener("change", syncFromSelect);
    syncFromSelect();
  });
};

document.addEventListener("click", (event) => {
  if (!(event.target instanceof Element) || !event.target.closest(".admin-select-wrap")) {
    closeAdminSelects();
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeAdminSelects();
  }
});

enhanceAdminSelects();

document.querySelectorAll("[data-filter-target]").forEach((button) => {
  button.addEventListener("click", () => {
    const form = button.closest("form");
    if (!(form instanceof HTMLFormElement)) return;
    const target = button.dataset.filterTarget;
    const value = button.dataset.filterValue || "";
    const input = form.querySelector(`input[name="${target}"]`);
    if (!(input instanceof HTMLInputElement)) return;
    if (input.value === value) return;
    input.value = value;
    button.closest("[data-filter-group]")?.querySelectorAll(".analytics-segmented__item").forEach((item) => item.classList.remove("is-active"));
    button.classList.add("is-active");
    if (typeof form.requestSubmit === "function") {
      form.requestSubmit();
      return;
    }
    form.submit();
  });
});

const sampleDateLabels = (items, maxLabels = 8) => {
  const step = Math.max(1, Math.ceil(items.length / maxLabels));
  return items.map((item, index) => {
    if (index % step !== 0 && index !== items.length - 1) return "";
    const [year, month, day] = String(item.label || "").split("-");
    return day && month ? `${day}.${month}` : item.label;
  });
};

const formatAxisTick = (value) => {
  return new Intl.NumberFormat("ru-RU").format(Number(value) || 0);
};

const formatMetricValue = (metric, value) => {
  const normalized = Number(value) || 0;
  if (metric === "revenue" || metric === "average_check") {
    return `${formatAxisTick(normalized)} ₽`;
  }
  return formatAxisTick(normalized);
};

const buildAxisTicks = (max) =>
  Array.from({ length: 5 }, (_, index) => {
    const ratio = index / 4;
    const value = Math.round(max * (1 - ratio));
    return { value, ratio };
  });

const renderFixedAxis = (ticks, plotHeight) => `
  <div class="admin-chart-y-axis" aria-hidden="true" style="height:${plotHeight}px;">
    ${ticks
      .map(
        (tick) => `
          <span class="admin-chart-y-axis__tick" style="top:${tick.ratio * plotHeight}px;">
            ${formatAxisTick(tick.value)}
          </span>
        `
      )
      .join("")}
  </div>
`;

const renderBarChart = (container, items) => {
  const max = Math.max(...items.map((item) => Number(item.value) || 0), 1);
  container.innerHTML = items
    .map((item) => {
      const width = Math.max(4, Math.round(((Number(item.value) || 0) / max) * 100));
      return `
        <div class="admin-chart-bar">
          <div class="admin-chart-bar__head"><span>${item.label}</span><strong>${item.value}</strong></div>
          <div class="admin-chart-bar__track"><span style="width:${width}%"></span></div>
        </div>
      `;
    })
    .join("");
};

const renderLineChart = (container, items) => {
  if (!items.length) {
    container.innerHTML = '<div class="admin-empty">Недостаточно данных.</div>';
    return;
  }
  const axisLabel = container.dataset.axisLabel || "";
  const width = Math.max(920, items.length * 58);
  const height = 260;
  const margin = { top: 16, right: 18, bottom: 42, left: 16 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const values = items.map((item) => Number(item.value) || 0);
  const max = Math.max(...values, 1);
  const step = items.length > 1 ? plotWidth / (items.length - 1) : plotWidth;
  const points = values
    .map((value, index) => {
      const x = margin.left + index * step;
      const y = margin.top + (plotHeight - (value / max) * plotHeight);
      return `${x},${y}`;
    })
    .join(" ");
  const ticks = buildAxisTicks(max);
  const labels = sampleDateLabels(items);
  container.innerHTML = `
    <div class="admin-chart-shell">
      <div class="admin-chart-axis-label">${axisLabel}</div>
      ${renderFixedAxis(ticks, plotHeight)}
      <div class="admin-chart-scroll">
        <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMinYMin meet" width="${width}" height="${height}" style="width:${width}px;height:${height}px;display:block;">
          ${ticks
            .map(
              (tick) => `
                <line x1="${margin.left}" y1="${margin.top + plotHeight * tick.ratio}" x2="${width - margin.right}" y2="${margin.top + plotHeight * tick.ratio}" stroke="rgba(255,255,255,0.08)" stroke-dasharray="4 6"></line>
              `
            )
            .join("")}
          <polyline fill="none" stroke="rgba(218,119,86,0.95)" stroke-width="3" points="${points}"></polyline>
          <polyline fill="rgba(218,119,86,0.12)" stroke="transparent" points="${margin.left},${height - margin.bottom} ${points} ${width - margin.right},${height - margin.bottom}"></polyline>
        </svg>
        <div class="admin-chart-labels" style="width:${width}px;grid-template-columns:repeat(${items.length}, minmax(34px, 1fr));">${labels.map((label) => `<span>${label}</span>`).join("")}</div>
      </div>
    </div>
  `;
};

const renderDonut = (container, items) => {
  const total = items.reduce((sum, item) => sum + (Number(item.value) || 0), 0) || 1;
  let offset = 0;
  const colors = ["#da7756", "#f1b36c", "#8aa7ff"];
  const circles = items
    .map((item, index) => {
      const value = Number(item.value) || 0;
      const length = (value / total) * 314;
      const circle = `<circle cx="70" cy="70" r="50" fill="none" stroke="${colors[index % colors.length]}" stroke-width="18" stroke-dasharray="${length} 314" stroke-dashoffset="-${offset}" transform="rotate(-90 70 70)"></circle>`;
      offset += length;
      return circle;
    })
    .join("");
  container.innerHTML = `
    <svg viewBox="0 0 140 140">
      ${circles}
      <text x="70" y="74" text-anchor="middle" fill="#f8f5f3" font-size="12">${total}</text>
    </svg>
    <div class="admin-list">
      ${items
        .map(
          (item, index) =>
            `<div class="admin-list__item"><strong><span style="display:inline-block;width:10px;height:10px;border-radius:999px;background:${colors[index % colors.length]};margin-right:8px;vertical-align:middle;"></span>${item.label}</strong><span>${item.value}</span></div>`
        )
        .join("")}
    </div>
  `;
};

const renderGroupedBarChart = (container, items) => {
  if (!items.length) {
    container.innerHTML = '<div class="admin-empty">Недостаточно данных.</div>';
    return;
  }
  const axisLabel = container.dataset.axisLabel || "";
  const width = Math.max(920, items.length * 58);
  const height = 260;
  const margin = { top: 16, right: 18, bottom: 42, left: 16 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const max = Math.max(...items.flatMap((item) => [Number(item.dine_in) || 0, Number(item.delivery) || 0]), 1);
  const groupWidth = plotWidth / Math.max(items.length, 1);
  const barWidth = Math.max(8, Math.min(16, (groupWidth - 10) / 2));
  const ticks = buildAxisTicks(max);
  const labels = sampleDateLabels(items);
  const bars = items
    .map((item, index) => {
      const groupX = margin.left + index * groupWidth + (groupWidth - (barWidth * 2 + 6)) / 2;
      const dineIn = Number(item.dine_in) || 0;
      const delivery = Number(item.delivery) || 0;
      const dineHeight = max ? (dineIn / max) * plotHeight : 0;
      const deliveryHeight = max ? (delivery / max) * plotHeight : 0;
      return `
        <rect x="${groupX}" y="${margin.top + plotHeight - dineHeight}" width="${barWidth}" height="${dineHeight}" rx="6" fill="rgba(218,119,86,0.9)"></rect>
        <rect x="${groupX + barWidth + 6}" y="${margin.top + plotHeight - deliveryHeight}" width="${barWidth}" height="${deliveryHeight}" rx="6" fill="rgba(241,179,108,0.9)"></rect>
      `;
    })
    .join("");
  container.innerHTML = `
    <div class="admin-chart-shell">
      <div class="admin-chart-axis-label">${axisLabel}</div>
      ${renderFixedAxis(ticks, plotHeight)}
      <div class="admin-chart-scroll">
        <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMinYMin meet" width="${width}" height="${height}" style="width:${width}px;height:${height}px;display:block;">
          ${ticks
            .map(
              (tick) => `
                <line x1="${margin.left}" y1="${margin.top + plotHeight * tick.ratio}" x2="${width - margin.right}" y2="${margin.top + plotHeight * tick.ratio}" stroke="rgba(255,255,255,0.08)" stroke-dasharray="4 6"></line>
              `
            )
            .join("")}
          ${bars}
        </svg>
        <div class="admin-chart-labels" style="width:${width}px;grid-template-columns:repeat(${items.length}, minmax(34px, 1fr));">${labels.map((label) => `<span>${label}</span>`).join("")}</div>
        <div class="admin-chart-legend">
          <span><i style="background:rgba(218,119,86,0.9)"></i>Зал</span>
          <span><i style="background:rgba(241,179,108,0.9)"></i>Доставка</span>
        </div>
      </div>
    </div>
  `;
};

const renderTrendChart = (container, chartData) => {
  const metricMeta = {
    revenue: { label: "Выручка", note: "Сумма оплаченных заказов за период" },
    orders: { label: "Заказы", note: "Количество неотменённых заказов" },
    average_check: { label: "Средний чек", note: "Среднее значение по дням" },
  };
  const summary = JSON.parse(container.dataset.summary || "{}");
  const periodLabel = container.dataset.periodLabel || "";
  const switcher = container.closest(".analytics-trend-card")?.querySelector("[data-chart-switcher]");

  const setActiveMetric = (metric) => {
    switcher?.querySelectorAll("[data-chart-metric]").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.chartMetric === metric);
    });
  };

  const drawMetric = (metric) => {
    const items = Array.isArray(chartData?.[metric]) ? chartData[metric] : [];
    if (!items.length) {
      container.innerHTML = '<div class="admin-empty">Недостаточно данных.</div>';
      return;
    }
    const barMode = items.length <= 3;
    const width = Math.max(620, items.length * (barMode ? 140 : 42) + 80);
    const height = 280;
    const margin = { top: 16, right: 20, bottom: 20, left: 10 };
    const plotWidth = width - margin.left - margin.right;
    const plotHeight = height - margin.top - margin.bottom;
    const values = items.map((item) => Number(item.value) || 0);
    const max = Math.max(...values, 1);
    const ticks = buildAxisTicks(max);
    const labels = sampleDateLabels(items, barMode ? items.length : 8);
    const meta = metricMeta[metric] || metricMeta.revenue;
    const summaryValue = Object.prototype.hasOwnProperty.call(summary, metric)
      ? summary[metric]
      : values.reduce((acc, value) => acc + value, 0);

    let geometry = "";
    if (barMode) {
      const gap = 18;
      const barWidth = Math.max(40, (plotWidth - gap * Math.max(items.length - 1, 0)) / Math.max(items.length, 1));
      geometry = items
        .map((item, index) => {
          const value = Number(item.value) || 0;
          const x = margin.left + index * (barWidth + gap);
          const barHeight = max ? (value / max) * plotHeight : 0;
          const y = margin.top + plotHeight - barHeight;
          return `
            <rect x="${x}" y="${y}" width="${barWidth}" height="${Math.max(barHeight, 4)}" rx="14" fill="rgba(218,119,86,0.92)"></rect>
            <rect data-point-index="${index}" data-x="${x + barWidth / 2}" data-y="${y}" x="${x}" y="${margin.top}" width="${barWidth}" height="${plotHeight}" fill="transparent"></rect>
          `;
        })
        .join("");
    } else {
      const step = items.length > 1 ? plotWidth / (items.length - 1) : plotWidth;
      const points = values
        .map((value, index) => {
          const x = margin.left + index * step;
          const y = margin.top + (plotHeight - (value / max) * plotHeight);
          return { x, y, value, index };
        });
      const polyline = points.map((point) => `${point.x},${point.y}`).join(" ");
      geometry = `
        <polyline fill="rgba(218,119,86,0.16)" stroke="transparent" points="${margin.left},${height - 4} ${polyline} ${width - margin.right},${height - 4}"></polyline>
        <polyline fill="none" stroke="rgba(241,179,108,0.92)" stroke-width="2.5" points="${polyline}"></polyline>
        ${points
          .map(
            (point) => `
              <circle cx="${point.x}" cy="${point.y}" r="5" fill="#f8f5f3" stroke="rgba(218,119,86,0.96)" stroke-width="3"></circle>
              <rect data-point-index="${point.index}" data-x="${point.x}" data-y="${point.y}" x="${point.x - step / 2}" y="${margin.top}" width="${Math.max(step, 24)}" height="${plotHeight}" fill="transparent"></rect>
            `
          )
          .join("")}
      `;
    }

    container.innerHTML = `
      <div class="analytics-trend-shell">
        <div class="analytics-trend-headline">
          <div>
            <span>${meta.label}</span>
            <strong>${formatMetricValue(metric, summaryValue)}</strong>
          </div>
          <div class="analytics-trend-legend">
            <i></i>
            <span>${periodLabel || meta.note}</span>
          </div>
        </div>
        <div class="analytics-trend-viewport">
          <div class="analytics-trend-tooltip"></div>
          <div class="analytics-trend-axis">
            <div class="analytics-trend-y" style="height:${plotHeight}px;">
              ${ticks
                .map(
                  (tick) => `
                    <span style="top:${tick.ratio * plotHeight}px;">${formatAxisTick(tick.value)}</span>
                  `
                )
                .join("")}
            </div>
            <div class="admin-chart-scroll">
              <svg class="analytics-trend-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMinYMin meet" width="${width}" height="${height}" style="width:${width}px;height:${height}px;">
                ${ticks
                  .map(
                    (tick) => `
                      <line
                        x1="${margin.left}"
                        y1="${margin.top + plotHeight * tick.ratio}"
                        x2="${width - margin.right}"
                        y2="${margin.top + plotHeight * tick.ratio}"
                        stroke="rgba(255,255,255,0.08)"
                        stroke-dasharray="4 6"
                      ></line>
                    `
                  )
                  .join("")}
                ${geometry}
              </svg>
              <div class="analytics-trend-x">
                <div class="analytics-trend-x__labels" style="width:${width}px;grid-template-columns:repeat(${items.length}, minmax(24px, 1fr));">
                  ${labels.map((label) => `<span>${label}</span>`).join("")}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;

    const viewport = container.querySelector(".analytics-trend-viewport");
    const tooltip = container.querySelector(".analytics-trend-tooltip");
    container.querySelectorAll("[data-point-index]").forEach((target) => {
      const showTooltip = (event) => {
        if (!(tooltip instanceof HTMLElement) || !(viewport instanceof HTMLElement)) return;
        const index = Number(target.getAttribute("data-point-index")) || 0;
        const item = items[index];
        if (!item) return;
        const rect = viewport.getBoundingClientRect();
        const clientX = event instanceof MouseEvent ? event.clientX : rect.left + Number(target.getAttribute("data-x"));
        const clientY = event instanceof MouseEvent ? event.clientY : rect.top + Number(target.getAttribute("data-y"));
        tooltip.innerHTML = `
          <span>${item.label}</span>
          <strong>${formatMetricValue(metric, item.value)}</strong>
        `;
        tooltip.style.left = `${clientX - rect.left}px`;
        tooltip.style.top = `${clientY - rect.top}px`;
        tooltip.classList.add("is-visible");
      };
      target.addEventListener("mouseenter", showTooltip);
      target.addEventListener("mousemove", showTooltip);
      target.addEventListener("mouseleave", () => tooltip?.classList.remove("is-visible"));
    });

    setActiveMetric(metric);
  };

  const initialMetric = container.dataset.defaultMetric || "revenue";
  switcher?.querySelectorAll("[data-chart-metric]").forEach((button) => {
    button.addEventListener("click", () => drawMetric(button.dataset.chartMetric || initialMetric));
  });
  drawMetric(initialMetric);
};

document.querySelectorAll(".admin-chart").forEach((node) => {
  const chart = JSON.parse(node.dataset.chart || "[]");
  const kind = node.dataset.chartKind;
  if (kind === "trend") {
    renderTrendChart(node, chart);
  } else if (kind === "line") {
    renderLineChart(node, chart);
  } else if (kind === "grouped-bar") {
    renderGroupedBarChart(node, chart);
  } else if (kind === "donut") {
    renderDonut(node, chart);
  } else {
    renderBarChart(node, chart);
  }
});

const menuForm = document.getElementById("adminMenuForm");

if (menuForm) {
  const previewMedia = document.getElementById("adminMenuPreviewMedia");
  const previewName = document.getElementById("adminMenuPreviewName");
  const previewType = document.getElementById("adminMenuPreviewType");
  const previewFeatured = document.getElementById("adminMenuPreviewFeatured");
  const previewHidden = document.getElementById("adminMenuPreviewHidden");
  const previewLore = document.getElementById("adminMenuPreviewLore");
  const previewPrice = document.getElementById("adminMenuPreviewPrice");
  const previewWeight = document.getElementById("adminMenuPreviewWeight");
  const previewId = document.getElementById("adminMenuPreviewId");
  const previewPopularity = document.getElementById("adminMenuPreviewPopularity");

  const field = (name) => menuForm.querySelector(`[name="${name}"]`);
  const nameInput = field("name");
  const typeInput = field("type");
  const priceInput = field("price");
  const weightInput = field("weight");
  const loreInput = field("lore");
  const idInput = field("id");
  const popularityInput = field("popularity");
  const featuredInput = field("featured");
  const activeInput = field("active");
  const photoInput = field("photo");

  const updateMenuPreview = () => {
    if (previewName) previewName.textContent = nameInput?.value?.trim() || "Новое блюдо";
    if (previewType) previewType.textContent = typeInput?.value?.trim() || "Категория";
    if (previewLore) {
      previewLore.textContent =
        loreInput?.value?.trim() || "Здесь появится описание блюда, чтобы можно было сразу оценить общий вид карточки.";
    }
    if (previewPrice) previewPrice.textContent = `${priceInput?.value?.trim() || "0"} ₽`;
    if (previewWeight) previewWeight.textContent = weightInput?.value?.trim() || "—";
    if (previewId) previewId.textContent = idInput?.value?.trim() || "—";
    if (previewPopularity) previewPopularity.textContent = popularityInput?.value?.trim() || "0";
    if (previewFeatured) previewFeatured.hidden = !featuredInput?.checked;
    if (previewHidden) previewHidden.hidden = !!activeInput?.checked;
  };

  [nameInput, typeInput, priceInput, weightInput, loreInput, idInput, popularityInput, featuredInput, activeInput].forEach((input) => {
    input?.addEventListener("input", updateMenuPreview);
    input?.addEventListener("change", updateMenuPreview);
  });

  photoInput?.addEventListener("change", () => {
    const file = photoInput.files?.[0];
    if (!file || !previewMedia) {
      if (previewMedia) {
        previewMedia.style.backgroundImage = "";
      }
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      previewMedia.style.backgroundImage = `url("${reader.result}")`;
    };
    reader.readAsDataURL(file);
  });

  updateMenuPreview();
}

const promoForm = document.getElementById("adminPromoForm");

if (promoForm) {
  const field = (name) => promoForm.querySelector(`[name="${name}"]`);
  const promoType = field("class_name");
  const promoName = field("name");
  const promoText = field("text");
  const promoLink = field("link");
  const promoLore = field("lore");
  const promoDslVersion = field("dsl_version");
  const promoCondition = field("condition");
  const promoReward = field("reward");
  const promoNotify = field("notify");
  const promoRewardMode = field("reward_mode");
  const promoLimitPerOrder = field("limit_per_order");
  const promoLimitPerUserDay = field("limit_per_user_per_day");
  const promoPriority = field("priority");
  const promoStart = field("start_at");
  const promoEnd = field("end_at");
  const promoActive = field("active");
  const promoPhoto = field("photo");
  const promoValidateButton = document.getElementById("adminPromoValidateButton");
  const promoValidateResult = document.getElementById("adminPromoValidateResult");
  const promoHelper = document.getElementById("adminPromoDslHelper");
  const promoHelperStatus = document.getElementById("adminPromoHelperStatus");
  const promoPreviewType = document.getElementById("adminPromoPreviewType");
  const promoPreviewTitle = document.getElementById("adminPromoPreviewTitle");
  const promoPreviewBody = document.getElementById("adminPromoPreviewBody");
  const promoPreviewPriority = document.getElementById("adminPromoPreviewPriority");
  const promoPreviewTiming = document.getElementById("adminPromoPreviewTiming");
  const promoPreviewHidden = document.getElementById("adminPromoPreviewHidden");
  const promoPreviewMedia = document.getElementById("adminPromoPreviewMedia");
  const promoPreviewLink = document.getElementById("adminPromoPreviewLink");
  const promoScopedFields = Array.from(document.querySelectorAll("[data-promo-field]"));
  const promoConditionSource = document.getElementById("promoConditionSource");
  const promoConditionItemField = document.getElementById("promoConditionItemField");
  const promoConditionTypeField = document.getElementById("promoConditionTypeField");
  const promoConditionGroupField = document.getElementById("promoConditionGroupField");
  const promoConditionItemId = document.getElementById("promoConditionItemId");
  const promoConditionType = document.getElementById("promoConditionType");
  const promoConditionGroupIds = document.getElementById("promoConditionGroupIds");
  const promoConditionMetric = document.getElementById("promoConditionMetric");
  const promoConditionOperator = document.getElementById("promoConditionOperator");
  const promoConditionValue = document.getElementById("promoConditionValue");
  const promoConditionSet = document.getElementById("promoConditionSet");
  const promoConditionAnd = document.getElementById("promoConditionAnd");
  const promoConditionOr = document.getElementById("promoConditionOr");
  const promoConditionPreview = document.getElementById("promoConditionPreview");
  const promoRewardKind = document.getElementById("promoRewardKind");
  const promoRewardValueField = document.getElementById("promoRewardValueField");
  const promoRewardValue = document.getElementById("promoRewardValue");
  const promoRewardGiftIdField = document.getElementById("promoRewardGiftIdField");
  const promoRewardGiftId = document.getElementById("promoRewardGiftId");
  const promoRewardGiftQtyField = document.getElementById("promoRewardGiftQtyField");
  const promoRewardGiftQty = document.getElementById("promoRewardGiftQty");
  const promoRewardTargetField = document.getElementById("promoRewardTargetField");
  const promoRewardTarget = document.getElementById("promoRewardTarget");
  const promoRewardTargetGroupField = document.getElementById("promoRewardTargetGroupField");
  const promoRewardTargetGroupIds = document.getElementById("promoRewardTargetGroupIds");
  const promoRewardSet = document.getElementById("promoRewardSet");
  const promoRewardPreview = document.getElementById("promoRewardPreview");

  const setPromoValidationState = (message, kind = "") => {
    if (!promoValidateResult) return;
    promoValidateResult.textContent = message;
    promoValidateResult.classList.remove("admin-note--success", "admin-note--danger");
    if (kind === "success") {
      promoValidateResult.classList.add("admin-note--success");
    } else if (kind === "danger") {
      promoValidateResult.classList.add("admin-note--danger");
    }
  };

  const getDslVersion = () => ((promoDslVersion?.value || "").trim() === "2" ? 2 : 1);

  const buildConditionFragment = () => {
    const dslVersion = getDslVersion();
    const source = promoConditionSource?.value || "item";
    const metric = promoConditionMetric?.value || "QTY";
    let operator = promoConditionOperator?.value || ">=";
    const rawValue = promoConditionValue?.value?.trim() || "1";
    let left = "ID.QTY";
    if (dslVersion === 2 && operator === "=") {
      operator = "==";
    }
    if (dslVersion === 1 && operator === "==") {
      operator = "=";
    }
    if (dslVersion === 1 && operator === "!=") {
      operator = "=";
    }
    if (source === "item") {
      const itemId = promoConditionItemId?.value?.trim() || "0";
      left = `ID(${itemId}).${metric}`;
    } else if (source === "type") {
      const itemType = promoConditionType?.value?.trim() || "тип";
      left = dslVersion === 2 ? `TYPE(${itemType}).${metric}` : `ID.${itemType}.${metric}`;
    } else if (source === "group") {
      const groupIds = promoConditionGroupIds?.value?.trim() || "101,205";
      left = `GROUP(${groupIds}).${metric}`;
    } else if (source === "order") {
      left = dslVersion === 2 ? "ORDER.SUBTOTAL" : "ORDER.SUM";
    }
    return `${left} ${operator} ${rawValue}`;
  };

  const buildRewardFragment = () => {
    const dslVersion = getDslVersion();
    const rewardKind = promoRewardKind?.value || "POINTS";
    const target = promoRewardTarget?.value || "ORDER";
    const targetGroupIds = promoRewardTargetGroupIds?.value?.trim() || "101,205";
    if (rewardKind === "CHEAPEST_FREE_FROM_GROUP") {
      return `CHEAPEST_FREE_FROM_GROUP(${targetGroupIds})`;
    }
    if (rewardKind === "GIFT") {
      const giftId = promoRewardGiftId?.value?.trim() || "0";
      const giftQty = promoRewardGiftQty?.value?.trim() || "1";
      return `GIFT(${giftId}, ${giftQty})`;
    }
    if (rewardKind === "DISCOUNT_PERCENT" || rewardKind === "DISCOUNT_RUB") {
      const rewardValue = promoRewardValue?.value?.trim() || "100";
      if (dslVersion === 2) {
        if (target === "GROUP") {
          return `${rewardKind}(${rewardValue}, TARGET=GROUP(${targetGroupIds}))`;
        }
        return `${rewardKind}(${rewardValue}, TARGET=ORDER)`;
      }
      return `${rewardKind}(${rewardValue})`;
    }
    return `${rewardKind}(${promoRewardValue?.value?.trim() || "100"})`;
  };

  const syncHelperVisibility = () => {
    const isPromo = (promoType?.value || "akciya") === "akciya";
    if (promoHelper) promoHelper.classList.toggle("is-disabled", !isPromo);
    if (promoHelperStatus) {
      promoHelperStatus.textContent = isPromo
        ? "Соберите фрагмент и вставьте его в DSL-поле."
        : "Для reklama helper отключён.";
    }
  };

  const syncConditionBuilder = () => {
    const dslVersion = getDslVersion();
    const source = promoConditionSource?.value || "item";
    if (promoConditionItemField) promoConditionItemField.hidden = source !== "item";
    if (promoConditionTypeField) promoConditionTypeField.hidden = source !== "type";
    if (promoConditionGroupField) promoConditionGroupField.hidden = source !== "group";
    if (promoConditionMetric && source === "order") {
      promoConditionMetric.value = dslVersion === 2 ? "SUBTOTAL" : "SUM";
    }
    if (promoConditionMetric && dslVersion === 1 && promoConditionMetric.value === "UNIQUE_QTY") {
      promoConditionMetric.value = "QTY";
    }
    if (promoConditionOperator && dslVersion === 2 && promoConditionOperator.value === "=") {
      promoConditionOperator.value = "==";
    }
    if (promoConditionOperator && dslVersion === 1 && promoConditionOperator.value === "==") {
      promoConditionOperator.value = "=";
    }
    if (promoConditionOperator && dslVersion === 1 && promoConditionOperator.value === "!=") {
      promoConditionOperator.value = "=";
    }
    if (promoConditionMetric) promoConditionMetric.disabled = source === "order";
    const fragment = buildConditionFragment();
    if (promoConditionPreview) promoConditionPreview.textContent = fragment;
  };

  const syncRewardBuilder = () => {
    const dslVersion = getDslVersion();
    const rewardKind = promoRewardKind?.value || "POINTS";
    const isGift = rewardKind === "GIFT";
    const isDiscount = rewardKind === "DISCOUNT_PERCENT" || rewardKind === "DISCOUNT_RUB";
    const isCheapest = rewardKind === "CHEAPEST_FREE_FROM_GROUP";
    if (promoRewardValueField) promoRewardValueField.hidden = isGift || isCheapest;
    if (promoRewardGiftIdField) promoRewardGiftIdField.hidden = !isGift;
    if (promoRewardGiftQtyField) promoRewardGiftQtyField.hidden = !isGift;
    if (promoRewardTargetField) promoRewardTargetField.hidden = !isDiscount || dslVersion !== 2;
    const targetKind = promoRewardTarget?.value || "ORDER";
    if (promoRewardTargetGroupField) {
      promoRewardTargetGroupField.hidden = isGift || (!isCheapest && (!isDiscount || dslVersion !== 2 || targetKind !== "GROUP"));
    }
    if (promoRewardPreview) promoRewardPreview.textContent = buildRewardFragment();
  };

  const insertConditionFragment = (joiner = "") => {
    if (!promoCondition) return;
    const fragment = buildConditionFragment();
    const current = promoCondition.value.trim();
    promoCondition.value = joiner && current ? `${current} ${joiner} ${fragment}` : fragment;
    promoCondition.dispatchEvent(new Event("input", { bubbles: true }));
  };

  const syncPromoFields = () => {
    const type = promoType?.value || "akciya";
    promoScopedFields.forEach((node) => {
      node.hidden = node.dataset.promoField !== type;
    });
    syncHelperVisibility();
  };

  const syncPromoPreview = () => {
    const type = promoType?.value || "akciya";
    if (promoPreviewType) promoPreviewType.textContent = type;
    if (promoPreviewTitle) {
      promoPreviewTitle.textContent =
        type === "akciya" ? promoName?.value?.trim() || "Новая акция" : promoText?.value?.trim() || "Новая реклама";
    }
    if (promoPreviewBody) {
      promoPreviewBody.textContent =
        type === "akciya"
          ? promoLore?.value?.trim() || promoCondition?.value?.trim() || "Здесь появится описание акции."
          : promoLink?.value?.trim() || "Здесь появится ссылка рекламы.";
    }
    if (promoPreviewPriority) promoPreviewPriority.textContent = promoPriority?.value?.trim() || "100";
    if (promoPreviewTiming) {
      const start = promoStart?.value?.trim();
      const end = promoEnd?.value?.trim();
      promoPreviewTiming.textContent = start || end ? `${start || "сейчас"} → ${end || "без конца"}` : "Без ограничения по датам";
    }
    if (promoPreviewHidden) promoPreviewHidden.hidden = !!promoActive?.checked;
    if (promoPreviewLink) {
      const href = promoLink?.value?.trim() || "#";
      promoPreviewLink.hidden = type !== "reklama" || !promoLink?.value?.trim();
      promoPreviewLink.href = href;
    }
  };

  [
    promoType,
    promoName,
    promoText,
    promoLink,
    promoLore,
    promoDslVersion,
    promoCondition,
    promoReward,
    promoNotify,
    promoRewardMode,
    promoLimitPerOrder,
    promoLimitPerUserDay,
    promoPriority,
    promoStart,
    promoEnd,
    promoActive,
  ].forEach((input) => {
    input?.addEventListener("input", syncPromoPreview);
    input?.addEventListener("change", () => {
      syncPromoFields();
      syncPromoPreview();
    });
  });

  promoValidateButton?.addEventListener("click", async () => {
    if ((promoType?.value || "akciya") !== "akciya") {
      setPromoValidationState("Проверка DSL нужна только для акций.");
      return;
    }
    const payload = {
      class_name: promoType?.value || "akciya",
      name: promoName?.value || "",
      lore: promoLore?.value || "",
      dsl_version: promoDslVersion?.value || "",
      condition: promoCondition?.value || "",
      reward: promoReward?.value || "",
      notify: promoNotify?.value || "",
      reward_mode: promoRewardMode?.value || "",
      limit_per_order: promoLimitPerOrder?.value || "",
      limit_per_user_per_day: promoLimitPerUserDay?.value || "",
      priority: promoPriority?.value || "100",
      start_at: promoStart?.value || "",
      end_at: promoEnd?.value || "",
      active: promoActive?.checked ? "1" : "0",
    };
    setPromoValidationState("Проверяю DSL...");
    try {
      const response = await fetch("/admin/api/promo/validate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": document.querySelector('meta[name="csrf-token"]')?.content || "",
        },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok || !data.ok) {
        throw new Error(data.error || "DSL не прошёл проверку.");
      }
      const rewardKindLabel = data.summary?.reward_kind || "неизвестно";
      const dslVersionLabel = data.summary?.dsl_version || "1";
      const rewardModeRaw = data.summary?.reward_mode || "";
      const rewardModeLabel =
        rewardModeRaw === "per_match" ? "за каждое совпадение" : rewardModeRaw === "once" ? "один раз" : "нет";
      setPromoValidationState(
        `DSL валиден (v${dslVersionLabel}). Награда: ${rewardKindLabel}. Режим: ${rewardModeLabel}.`,
        "success"
      );
    } catch (error) {
      setPromoValidationState(error.message || "Ошибка проверки DSL.", "danger");
    }
  });

  [promoDslVersion, promoConditionSource, promoConditionItemId, promoConditionType, promoConditionGroupIds, promoConditionMetric, promoConditionOperator, promoConditionValue].forEach((input) => {
    input?.addEventListener("input", syncConditionBuilder);
    input?.addEventListener("change", syncConditionBuilder);
  });

  [promoDslVersion, promoRewardKind, promoRewardValue, promoRewardGiftId, promoRewardGiftQty, promoRewardTarget, promoRewardTargetGroupIds].forEach((input) => {
    input?.addEventListener("input", syncRewardBuilder);
    input?.addEventListener("change", syncRewardBuilder);
  });

  promoConditionSet?.addEventListener("click", () => insertConditionFragment(""));
  promoConditionAnd?.addEventListener("click", () => insertConditionFragment("AND"));
  promoConditionOr?.addEventListener("click", () => insertConditionFragment("OR"));
  promoRewardSet?.addEventListener("click", () => {
    if (!promoReward) return;
    promoReward.value = buildRewardFragment();
    promoReward.dispatchEvent(new Event("input", { bubbles: true }));
  });

  promoPhoto?.addEventListener("change", () => {
    const file = promoPhoto.files?.[0];
    if (!file || !promoPreviewMedia) {
      if (promoPreviewMedia) promoPreviewMedia.style.backgroundImage = "";
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      promoPreviewMedia.style.backgroundImage = `url("${reader.result}")`;
    };
    reader.readAsDataURL(file);
  });

  syncPromoFields();
  syncPromoPreview();
  syncConditionBuilder();
  syncRewardBuilder();
  }
