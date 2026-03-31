import { setupTableTooltip } from "../modules/tableTooltip.js";
import { bootstrapPage } from "../shared/basePage.js";

bootstrapPage(async () => {
  setupTableTooltip();
});
