import { setupFormEnhancements } from "../modules/formEnhancements.js?v=20260408b";
import { setupPaymentAddAccordion } from "../modules/paymentAddAccordion.js?v=20260408b";
import { setupProfileNameFit } from "../modules/profileNameFit.js?v=20260408b";
import { bootstrapPage } from "../shared/basePage.js?v=20260408b";

bootstrapPage(async () => {
  setupPaymentAddAccordion();
  setupProfileNameFit();
  setupFormEnhancements({
    cardNumberInput: document.querySelector('input[name="card_number"]'),
    expiryInput: document.querySelector('input[name="expiry"]'),
    holderInput: document.querySelector('input[name="holder"]'),
    phoneInputs: Array.from(document.querySelectorAll('input[name="phone"]')),
  });
});
