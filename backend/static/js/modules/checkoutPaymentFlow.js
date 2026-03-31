import { getCsrfToken } from "./core.js";

const setupCheckoutPage = ({
  checkoutForm,
  checkoutItemsNode,
  checkoutItemsTotal,
  checkoutTotal,
  checkoutItemsJson,
  checkoutEmpty,
  checkoutSummaryList,
  checkoutComment,
  checkoutCommentCount,
  usePoints,
  availablePoints,
  checkoutPointsApplied,
  checkoutBonusEarned,
  checkoutPayable,
  checkoutPromoHighlight,
  checkoutPromoList,
  checkoutPromoMeta,
  checkoutPromoChip,
  goToPayment,
  serveCustomTime,
  loadCart,
}) => {
  if (!checkoutForm || !checkoutItemsNode || typeof loadCart !== "function") {
    return;
  }

  const commentStorageKey = "checkout_comment";
  const goToPaymentDefaultText = goToPayment?.textContent?.trim() || "Перейти к оплате";
  const goToPaymentInitiallyDisabled = Boolean(goToPayment?.disabled);
  let promoPreviewAbortController = null;
  let promoPreviewSequence = 0;

  const renderPromoHighlight = ({
    promotionsApplied = [],
    promoPoints = 0,
    discountTotal = 0,
  } = {}) => {
    if (!checkoutPromoHighlight || !checkoutPromoList || !checkoutPromoMeta || !checkoutPromoChip) {
      return;
    }

    const hasPromo = promotionsApplied.length > 0;
    checkoutPromoHighlight.hidden = !hasPromo;
    checkoutPromoList.innerHTML = "";
    checkoutPromoMeta.textContent = "";
    checkoutPromoChip.textContent = hasPromo ? String(promotionsApplied.length) : "0";

    if (!hasPromo) {
      return;
    }

    promotionsApplied.forEach((promo) => {
      const row = document.createElement("div");
      row.className = "promo-highlight__item";

      let rewardText = `× ${promo.applied_count || 1}`;
      if (promo.reward_kind === "POINTS" && promoPoints > 0) {
        rewardText = `+${promoPoints} баллов`;
      } else if (
        (promo.reward_kind === "DISCOUNT_PERCENT" || promo.reward_kind === "DISCOUNT_RUB") &&
        discountTotal > 0
      ) {
        rewardText = `-${discountTotal} ₽`;
      }

      row.innerHTML = `
        <span class="promo-highlight__name">${promo.name || "Акция"}</span>
        <span class="promo-highlight__value">${rewardText}</span>
      `;
      checkoutPromoList.appendChild(row);
    });

    if (promoPoints > 0) {
      checkoutPromoMeta.textContent = `Начислится дополнительно ${promoPoints} бонусов после оплаты.`;
    } else if (discountTotal > 0) {
      checkoutPromoMeta.textContent = "Скидка уже включена в итоговую сумму.";
    }
  };

  const updateTotalsFromServer = async (cart) => {
    const fallbackTotal = cart.reduce((sum, item) => sum + Number(item.qty) * Number(item.price), 0);
    const fallbackBalance = Number(availablePoints?.textContent || 0);
    const fallbackPointsApplied = usePoints?.checked ? Math.min(fallbackBalance, fallbackTotal) : 0;
    const fallbackPayableTotal = Math.max(0, fallbackTotal - fallbackPointsApplied);
    const fallbackBonusEarned = Math.max(0, Math.floor(fallbackPayableTotal * 0.05));

    if (!cart.length) {
      if (checkoutItemsTotal) checkoutItemsTotal.textContent = String(fallbackTotal);
      if (checkoutTotal) checkoutTotal.textContent = String(fallbackTotal);
      if (checkoutPointsApplied) checkoutPointsApplied.textContent = String(fallbackPointsApplied);
      if (checkoutBonusEarned) checkoutBonusEarned.textContent = String(fallbackBonusEarned);
      if (checkoutPayable) checkoutPayable.textContent = String(fallbackPayableTotal);
      renderPromoHighlight();
      return;
    }

    promoPreviewAbortController?.abort();
    promoPreviewAbortController = new AbortController();
    promoPreviewSequence += 1;
    const requestSequence = promoPreviewSequence;

    const response = await fetch("/api/checkout/promo-preview", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(getCsrfToken() ? { "X-CSRF-Token": getCsrfToken() } : {}),
      },
      body: JSON.stringify({
        items: cart.map((item) => ({ id: Number(item.id), qty: Number(item.qty) })),
        use_points: Boolean(usePoints?.checked),
      }),
      signal: promoPreviewAbortController.signal,
    }).catch(() => null);

    if (!response || !response.ok || requestSequence !== promoPreviewSequence) {
      if (checkoutItemsTotal) checkoutItemsTotal.textContent = String(fallbackTotal);
      if (checkoutTotal) checkoutTotal.textContent = String(fallbackTotal);
      if (checkoutPointsApplied) checkoutPointsApplied.textContent = String(fallbackPointsApplied);
      if (checkoutBonusEarned) checkoutBonusEarned.textContent = String(fallbackBonusEarned);
      if (checkoutPayable) checkoutPayable.textContent = String(fallbackPayableTotal);
      return;
    }

    const result = await response.json().catch(() => ({}));
    if (!result.ok || requestSequence !== promoPreviewSequence) {
      if (checkoutItemsTotal) checkoutItemsTotal.textContent = String(fallbackTotal);
      if (checkoutTotal) checkoutTotal.textContent = String(fallbackTotal);
      if (checkoutPointsApplied) checkoutPointsApplied.textContent = String(fallbackPointsApplied);
      if (checkoutBonusEarned) checkoutBonusEarned.textContent = String(fallbackBonusEarned);
      if (checkoutPayable) checkoutPayable.textContent = String(fallbackPayableTotal);
      return;
    }

    const totals = result.totals || {};
    if (checkoutItemsTotal) checkoutItemsTotal.textContent = String(Number(totals.items_total) || fallbackTotal);
    if (checkoutTotal) checkoutTotal.textContent = String(Number(totals.items_total) || fallbackTotal);
    if (checkoutPointsApplied) checkoutPointsApplied.textContent = String(Number(totals.points_applied) || 0);
    if (checkoutBonusEarned) checkoutBonusEarned.textContent = String(Number(totals.bonus_earned) || 0);
    if (checkoutPayable) checkoutPayable.textContent = String(Number(totals.payable_total) || 0);

    renderPromoHighlight({
      promotionsApplied: Array.isArray(result.promotions_applied) ? result.promotions_applied : [],
      promoPoints: Number(result.promo_points) || 0,
      discountTotal: Number(result.discount_total) || 0,
    });
  };

  const normalizeCheckoutItem = (item) => {
    const id = Number(item.id);
    return {
      ...item,
      id,
      name: item.name || "Позиция",
      price: Number(item.price) || 0,
      qty: Number(item.qty) || 0,
      photo: item.photo || "",
    };
  };

  const getCheckoutCart = () =>
    loadCart()
      .map(normalizeCheckoutItem)
      .filter((item) => Number(item.qty) > 0);

  const resetGoToPaymentState = () => {
    if (!goToPayment) return;
    goToPayment.classList.remove("is-loading");
    goToPayment.textContent = goToPaymentDefaultText;
    const cartLength = getCheckoutCart().length;
    goToPayment.disabled = goToPaymentInitiallyDisabled || cartLength === 0;
  };

  const updateCommentCounter = () => {
    if (!checkoutComment || !checkoutCommentCount) return;
    checkoutCommentCount.textContent = String(checkoutComment.value.length);
  };

  const renderCheckout = () => {
    const cart = getCheckoutCart();
    const total = cart.reduce((sum, item) => sum + Number(item.qty) * Number(item.price), 0);

    if (checkoutItemsJson) {
      checkoutItemsJson.value = JSON.stringify(
        cart.map((item) => ({ id: Number(item.id), qty: Number(item.qty) }))
      );
    }

    if (checkoutEmpty) {
      checkoutEmpty.hidden = cart.length > 0;
      checkoutEmpty.style.display = cart.length > 0 ? "none" : "";
    }
    if (goToPayment) goToPayment.disabled = goToPaymentInitiallyDisabled || cart.length === 0;

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

    updateTotalsFromServer(cart);
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
      resetGoToPaymentState();
      return;
    }
    const customChecked = Boolean(
      checkoutForm.querySelector('input[name="serve_mode"][value="custom"]')?.checked
    );
    if (customChecked && serveCustomTime && !serveCustomTime.value) {
      event.preventDefault();
      resetGoToPaymentState();
      return;
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

  window.addEventListener("pageshow", () => {
    resetGoToPaymentState();
    renderCheckout();
  });

  const cards = Array.from(document.querySelectorAll(".checkout-main .checkout-card"));
  cards.forEach((card, index) => {
    card.classList.add("checkout-card--stagger");
    card.style.animationDelay = `${index * 60}ms`;
  });
  document.getElementById("checkoutHead")?.classList.add("checkout-head--show");
  document.getElementById("checkoutTotalPanel")?.classList.add("checkout-total--show");

  renderCheckout();
};

const setupPaymentPage = ({
  paymentConfirmForm,
  payNowButton,
  paymentCardMain,
  paymentSuccess,
  paymentError,
  retryPaymentButton,
  paymentHead,
  paymentTotalBlock,
}) => {
  if (paymentHead) paymentHead.classList.add("payment-head--show");
  if (paymentCardMain) paymentCardMain.classList.add("payment-card--show");
  if (paymentTotalBlock) paymentTotalBlock.classList.add("payment-total--show");
  Array.from(paymentCardMain?.querySelectorAll(".payment-block") || []).forEach((block, index) => {
    if (block.id === "paymentTotalBlock") return;
    block.classList.add("payment-block--stagger");
    block.style.animationDelay = `${index * 70}ms`;
  });

  if (!paymentConfirmForm || !payNowButton) {
    return;
  }

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

  const resetPaymentLoadingState = () => {
    const successVisible = paymentSuccess && !paymentSuccess.hasAttribute("hidden");
    if (successVisible) return;
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
      headers: {
        "X-Requested-With": "XMLHttpRequest",
        ...(getCsrfToken() ? { "X-CSRF-Token": getCsrfToken() } : {}),
      },
      body: new FormData(paymentConfirmForm),
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

  window.addEventListener("pageshow", () => {
    resetPaymentLoadingState();
  });

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) resetPaymentLoadingState();
  });
};

export { setupCheckoutPage, setupPaymentPage };
