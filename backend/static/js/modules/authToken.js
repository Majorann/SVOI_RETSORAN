const setupAuthTokenBridge = async () => false;

const navigateWithAuth = (rawUrl, options = {}) => {
  if (!rawUrl) return;
  if (options.replace) {
    window.location.replace(rawUrl);
    return;
  }
  window.location.href = rawUrl;
};

export { navigateWithAuth, setupAuthTokenBridge };
