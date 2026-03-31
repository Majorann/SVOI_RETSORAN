import { setupAuthTokenBridge } from "../modules/authToken.js";
import { setupBottomNavMotion } from "../modules/bottomNavMotion.js";

const runWhenDomReady = (callback) => {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", callback, { once: true });
    return;
  }
  callback();
};

const clearPaidFlowArtifacts = () => {
  const params = new URLSearchParams(window.location.search);
  if (params.get("paid") !== "1") return;
  localStorage.removeItem("cart");
  localStorage.removeItem("delivery_cart");
  sessionStorage.removeItem("checkout_comment");
};

let baseSetupPromise = null;

const ensureBasePageSetup = async () => {
  if (baseSetupPromise) {
    return baseSetupPromise;
  }
  baseSetupPromise = (async () => {
    clearPaidFlowArtifacts();
    const authSessionSyncPending = await setupAuthTokenBridge();
    if (authSessionSyncPending) return false;
    setupBottomNavMotion();
    return true;
  })();
  return baseSetupPromise;
};

const bootstrapPage = (initializer = () => {}) => {
  runWhenDomReady(async () => {
    const baseReady = await ensureBasePageSetup();
    if (!baseReady) return;
    await initializer();
  });
};

export { bootstrapPage };
