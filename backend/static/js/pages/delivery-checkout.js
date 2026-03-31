import { setupDeliveryFlow } from "../modules/deliveryFlow.js";
import { setupFormEnhancements } from "../modules/formEnhancements.js";
import { bootstrapPage } from "../shared/basePage.js";

bootstrapPage(async () => {
  setupFormEnhancements({
    cardNumberInput: null,
    expiryInput: null,
    holderInput: null,
    phoneInputs: Array.from(document.querySelectorAll('input[name="delivery_phone"], input[name="phone"]')),
  });
  setupDeliveryFlow();
});
