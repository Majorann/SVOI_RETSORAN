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

let currentAction = null;

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
    });
  });
});

modalConfirm?.addEventListener("click", async () => {
  if (!currentAction) return;
  const reason = modalReason.value.trim();
  if (!reason) {
    showToast("Причина обязательна.", "error");
    modalReason.focus();
    return;
  }
  const payload = { reason };
  if (currentAction.payloadSource && currentAction.payloadKey) {
    const source = document.getElementById(currentAction.payloadSource);
    payload[currentAction.payloadKey] = source ? source.value : "";
  }
  try {
    const response = await fetch(currentAction.api, {
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

document.querySelectorAll(".admin-chart").forEach((node) => {
  const chart = JSON.parse(node.dataset.chart || "[]");
  const kind = node.dataset.chartKind;
  if (kind === "line") {
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
  const promoPriority = field("priority");
  const promoStart = field("start_at");
  const promoEnd = field("end_at");
  const promoActive = field("active");
  const promoPhoto = field("photo");
  const promoPreviewType = document.getElementById("adminPromoPreviewType");
  const promoPreviewTitle = document.getElementById("adminPromoPreviewTitle");
  const promoPreviewBody = document.getElementById("adminPromoPreviewBody");
  const promoPreviewPriority = document.getElementById("adminPromoPreviewPriority");
  const promoPreviewTiming = document.getElementById("adminPromoPreviewTiming");
  const promoPreviewHidden = document.getElementById("adminPromoPreviewHidden");
  const promoPreviewMedia = document.getElementById("adminPromoPreviewMedia");
  const promoPreviewLink = document.getElementById("adminPromoPreviewLink");
  const promoScopedFields = Array.from(document.querySelectorAll("[data-promo-field]"));

  const syncPromoFields = () => {
    const type = promoType?.value || "akciya";
    promoScopedFields.forEach((node) => {
      node.hidden = node.dataset.promoField !== type;
    });
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
          ? promoLore?.value?.trim() || "Здесь появится описание акции."
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

  [promoType, promoName, promoText, promoLink, promoLore, promoPriority, promoStart, promoEnd, promoActive].forEach((input) => {
    input?.addEventListener("input", syncPromoPreview);
    input?.addEventListener("change", () => {
      syncPromoFields();
      syncPromoPreview();
    });
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
}
