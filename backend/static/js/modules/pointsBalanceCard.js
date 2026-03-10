const setupPointsBalanceCard = () => {
  const balanceNode = document.getElementById("pointsBalanceValue");
  if (!balanceNode) return;
  const pointsCard = balanceNode.closest(".secondary-card--points");

  const targetValue = Number.parseInt(balanceNode.dataset.value || "0", 10);
  if (!Number.isFinite(targetValue) || targetValue < 0) return;

  const formatPoints = (value) =>
    new Intl.NumberFormat("ru-RU").format(value).replace(/\u00A0|\u202F/g, " ");

  const applyValue = (value) => {
    balanceNode.textContent = formatPoints(value);
  };

  const applyLengthClasses = (value) => {
    if (!pointsCard) return;
    const digits = Math.abs(Math.trunc(value)).toString().length;
    pointsCard.classList.toggle("is-balance-long", digits >= 5);
    pointsCard.classList.toggle("is-balance-xlong", digits >= 6);
  };

  applyLengthClasses(targetValue);

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reducedMotion || targetValue === 0) {
    applyValue(targetValue);
    balanceNode.classList.add("is-ready");
    return;
  }

  const durationMs = 620;
  const startedAt = performance.now();
  const tick = (now) => {
    const progress = Math.min(1, (now - startedAt) / durationMs);
    const eased = 1 - (1 - progress) * (1 - progress);
    applyValue(Math.round(targetValue * eased));
    if (progress < 1) {
      window.requestAnimationFrame(tick);
    } else {
      balanceNode.classList.add("is-ready");
    }
  };

  applyValue(0);
  window.requestAnimationFrame(tick);
};
export { setupPointsBalanceCard };