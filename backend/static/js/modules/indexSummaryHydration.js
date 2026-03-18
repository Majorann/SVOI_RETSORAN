const formatPoints = (value) =>
  new Intl.NumberFormat("ru-RU").format(value).replace(/\u00A0|\u202F/g, " ");

const applyPointsBalance = (pointsValue, pointsFormatted) => {
  const balanceNode = document.getElementById("pointsBalanceValue");
  if (!balanceNode) return;

  const numericValue = Number.parseInt(String(pointsValue ?? 0), 10);
  const safeValue = Number.isFinite(numericValue) && numericValue > 0 ? numericValue : 0;
  const renderedValue = pointsFormatted || formatPoints(safeValue);
  balanceNode.dataset.value = String(safeValue);
  balanceNode.textContent = renderedValue;
  balanceNode.setAttribute("aria-label", `Баланс баллов ${renderedValue}`);

  const pointsCard = balanceNode.closest(".secondary-card--points");
  if (!pointsCard) return;
  const digits = Math.abs(Math.trunc(safeValue)).toString().length;
  pointsCard.classList.toggle("is-balance-long", digits >= 5);
  pointsCard.classList.toggle("is-balance-xlong", digits >= 6);
}

const applyOrderStatuses = (orderStatuses, setupOrderStatusBar) => {
  const section = document.getElementById("orderStatusSection");
  const bar = document.getElementById("orderStatusBar");
  if (!section || !bar) return;

  const statuses = Array.isArray(orderStatuses) ? orderStatuses : [];
  if (!statuses.length) {
    section.hidden = true;
    bar.hidden = true;
    return;
  }

  section.hidden = false;
  bar.hidden = false;
  bar.dataset.orders = JSON.stringify(statuses);
  setupOrderStatusBar();
}

const setupIndexSummaryHydration = async (setupOrderStatusBar) => {
  if (!document.body.classList.contains("page-index")) return;
  if (window.__INDEX_SUMMARY_HYDRATED) return;
  window.__INDEX_SUMMARY_HYDRATED = true;

  try {
    const response = await window.fetch("/api/index-summary", {
      method: "GET",
      cache: "no-store",
      headers: {
        Accept: "application/json",
      },
    });
    if (!response.ok) return;

    const payload = await response.json().catch(() => null);
    if (!payload?.ok || !payload.authenticated) return;

    applyPointsBalance(payload.points_balance, payload.points_balance_formatted);
    applyOrderStatuses(payload.order_statuses, setupOrderStatusBar);
  } catch {
    // Silent fallback: the page still works with server-rendered values.
  }
}

export { setupIndexSummaryHydration };
