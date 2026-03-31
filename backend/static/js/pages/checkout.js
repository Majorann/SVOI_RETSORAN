import { setupCheckoutPage } from "../modules/checkoutPaymentFlow.js";
import { bootstrapPage } from "../shared/basePage.js";
import { loadCart } from "../shared/checkoutCart.js";

bootstrapPage(async () => {
  setupCheckoutPage({
    checkoutForm: document.getElementById("checkoutForm"),
    checkoutItemsNode: document.getElementById("checkoutItems"),
    checkoutItemsTotal: document.getElementById("checkoutItemsTotal"),
    checkoutTotal: document.getElementById("checkoutTotal"),
    checkoutItemsJson: document.getElementById("checkoutItemsJson"),
    checkoutEmpty: document.getElementById("checkoutEmpty"),
    checkoutSummaryList: document.getElementById("checkoutSummaryList"),
    checkoutComment: document.getElementById("checkoutComment"),
    checkoutCommentCount: document.getElementById("checkoutCommentCount"),
    usePoints: document.getElementById("usePoints"),
    availablePoints: document.getElementById("availablePoints"),
    checkoutPointsApplied: document.getElementById("checkoutPointsApplied"),
    checkoutBonusEarned: document.getElementById("checkoutBonusEarned"),
    checkoutPayable: document.getElementById("checkoutPayable"),
    checkoutPromoHighlight: document.getElementById("checkoutPromoHighlight"),
    checkoutPromoList: document.getElementById("checkoutPromoList"),
    checkoutPromoMeta: document.getElementById("checkoutPromoMeta"),
    checkoutPromoChip: document.getElementById("checkoutPromoChip"),
    goToPayment: document.getElementById("goToPayment"),
    serveCustomTime: document.getElementById("serveCustomTime"),
    loadCart,
  });
});
