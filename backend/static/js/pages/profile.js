import { setupFormEnhancements } from "../modules/formEnhancements.js";
import { setupPaymentAddAccordion } from "../modules/paymentAddAccordion.js";
import { setupProfileNameFit } from "../modules/profileNameFit.js";
import { bootstrapPage } from "../shared/basePage.js";

bootstrapPage(async () => {
  setupPaymentAddAccordion();
  setupProfileNameFit();
  setupFormEnhancements({
    phoneInputs: Array.from(document.querySelectorAll('input[name="phone"]')),
  });
});
