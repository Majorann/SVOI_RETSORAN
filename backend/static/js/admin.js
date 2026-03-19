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
  const width = 640;
  const height = 220;
  const values = items.map((item) => Number(item.value) || 0);
  const max = Math.max(...values, 1);
  const step = items.length > 1 ? width / (items.length - 1) : width;
  const points = values
    .map((value, index) => {
      const x = index * step;
      const y = height - (value / max) * (height - 24) - 12;
      return `${x},${y}`;
    })
    .join(" ");
  container.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
      <polyline fill="none" stroke="rgba(218,119,86,0.95)" stroke-width="3" points="${points}"></polyline>
      <polyline fill="rgba(218,119,86,0.12)" stroke="transparent" points="0,${height} ${points} ${width},${height}"></polyline>
    </svg>
    <div class="admin-chart-labels">${items
      .map((item) => {
        const [year, month, day] = String(item.label || "").split("-");
        return `<span>${day && month ? `${day}.${month}` : item.label}</span>`;
      })
      .join("")}</div>
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

document.querySelectorAll(".admin-chart").forEach((node) => {
  const chart = JSON.parse(node.dataset.chart || "[]");
  const kind = node.dataset.chartKind;
  if (kind === "line") {
    renderLineChart(node, chart);
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
