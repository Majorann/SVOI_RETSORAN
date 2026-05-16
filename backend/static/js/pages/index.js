import { stagger } from "../modules/core.js";
import { setupOrderStatusBar } from "../modules/orderStatusBar.js";
import { setupPointsBalanceCard } from "../modules/pointsBalanceCard.js";
import { bootstrapPage } from "../shared/basePage.js";
import { setupIndexFeaturedMenuCards, setupIndexNewsCards, setupPromoGalleryDialog } from "../shared/indexNewsCards.js?v=20260516b";

bootstrapPage(async () => {
  stagger(".news-card", 140);
  stagger(".menu-card", 120);
  setupPointsBalanceCard();
  setupOrderStatusBar();
  setupIndexNewsCards();
  setupIndexFeaturedMenuCards();
  setupPromoGalleryDialog();
});
