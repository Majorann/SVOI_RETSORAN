import { setupPaymentPage } from "../modules/checkoutPaymentFlow.js";
import { bootstrapPage } from "../shared/basePage.js";

bootstrapPage(async () => {
  setupPaymentPage({
    paymentConfirmForm: document.getElementById("paymentConfirmForm"),
    payNowButton: document.getElementById("payNowButton"),
    paymentCardMain: document.getElementById("paymentCardMain"),
    paymentSuccess: document.getElementById("paymentSuccess"),
    paymentError: document.getElementById("paymentError"),
    retryPaymentButton: document.getElementById("retryPaymentButton"),
    paymentHead: document.getElementById("paymentHead"),
    paymentTotalBlock: document.getElementById("paymentTotalBlock"),
  });
});
