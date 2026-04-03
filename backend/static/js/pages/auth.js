import { setupFormEnhancements } from "../modules/formEnhancements.js";
import { bootstrapPage } from "../shared/basePage.js";

bootstrapPage(() => {
  setupFormEnhancements({
    phoneInputs: Array.from(document.querySelectorAll('input[name="phone"]')),
  });
});
