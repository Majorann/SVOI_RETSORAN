import { stagger } from "../modules/core.js";
import { setupOrderStatusBar } from "../modules/orderStatusBar.js";
import { setupPointsBalanceCard } from "../modules/pointsBalanceCard.js";
import { bootstrapPage } from "../shared/basePage.js";
import { setupIndexNewsCards } from "../shared/indexNewsCards.js";

bootstrapPage(async () => {
  stagger(".news-card", 140);
  stagger(".menu-card", 120);
  setupPointsBalanceCard();
  setupOrderStatusBar();
  setupIndexNewsCards();
});
