const getAuthStorageKey = () => window.__AUTH_STORAGE_KEY || "auth_token";
const getAuthQueryParam = () => window.__AUTH_QUERY_PARAM || "auth_token";

const getAuthToken = () => {
  try {
    return window.localStorage.getItem(getAuthStorageKey()) || "";
  } catch {
    return "";
  }
};

const setAuthToken = (token) => {
  try {
    if (!token) {
      window.localStorage.removeItem(getAuthStorageKey());
      return;
    }
    window.localStorage.setItem(getAuthStorageKey(), token);
  } catch {
    // Ignore storage errors in private / restricted modes.
  }
};

const clearAuthToken = () => {
  setAuthToken("");
};

const getCsrfToken = () =>
  document.querySelector('meta[name="csrf-token"]')?.getAttribute("content") || "";

const ensureFormTokenField = (form, token = getAuthToken()) => {
  if (!form) return;
  let field = form.querySelector(`input[name="${getAuthQueryParam()}"]`);
  if (!token) {
    field?.remove();
    return;
  }

  if (!field) {
    field = document.createElement("input");
    field.type = "hidden";
    field.name = getAuthQueryParam();
    form.appendChild(field);
  }
  field.value = token;
};

const decorateInternalLinks = () => {
  const token = getAuthToken();
  if (!token) return;

  document.querySelectorAll("a[href]").forEach((link) => {
    const href = link.getAttribute("href");
    if (!href) return;
    const nextHref = buildUrlWithToken(href, token);
    if (nextHref && nextHref !== href) {
      link.setAttribute("href", nextHref);
    }
  });
};

const decorateForms = () => {
  document.querySelectorAll("form").forEach((form) => {
    ensureFormTokenField(form);
  });
};

const buildUrlWithToken = (rawUrl, token = getAuthToken()) => {
  if (!rawUrl || !token) return rawUrl;
  if (rawUrl.startsWith("#") || rawUrl.startsWith("mailto:") || rawUrl.startsWith("tel:")) {
    return rawUrl;
  }

  let url;
  try {
    url = new URL(rawUrl, window.location.origin);
  } catch {
    return rawUrl;
  }

  if (url.origin !== window.location.origin) return rawUrl;
  url.searchParams.set(getAuthQueryParam(), token);
  return `${url.pathname}${url.search}${url.hash}`;
};

const patchFetch = () => {
  if (window.__AUTH_FETCH_PATCHED) return;
  window.__AUTH_FETCH_PATCHED = true;

  const originalFetch = window.fetch.bind(window);
  window.fetch = (input, init = {}) => {
    const token = getAuthToken();
    if (!token) return originalFetch(input, init);

    if (input instanceof Request) {
      const url = new URL(input.url, window.location.origin);
      if (url.origin !== window.location.origin) return originalFetch(input, init);
      const headers = new Headers(input.headers);
      const initHeaders = new Headers(init.headers || {});
      initHeaders.forEach((value, key) => headers.set(key, value));
      headers.set("Authorization", `Bearer ${token}`);
      return originalFetch(new Request(input, { ...init, headers }));
    }

    const url = new URL(String(input), window.location.origin);
    if (url.origin !== window.location.origin) return originalFetch(input, init);
    const headers = new Headers(init.headers || {});
    headers.set("Authorization", `Bearer ${token}`);
    return originalFetch(input, { ...init, headers });
  };
};

const bootstrapPageAuthFromToken = () => {
  if (window.__SESSION_USER_ID) return false;

  const token = getAuthToken();
  if (!token) return false;

  const current = new URL(window.location.href);
  if (current.searchParams.get(getAuthQueryParam())) return false;

  const nextUrl = buildUrlWithToken(`${current.pathname}${current.search}${current.hash}`, token);
  if (!nextUrl) return false;
  if (nextUrl === `${current.pathname}${current.search}${current.hash}`) return false;

  document.body.classList.add("auth-sync-pending");
  window.location.replace(nextUrl);
  return true;
};

const stripAuthTokenFromAddressBar = () => {
  const current = new URL(window.location.href);
  const queryParam = getAuthQueryParam();
  const tokenFromUrl = current.searchParams.get(queryParam);
  if (!tokenFromUrl) return;
  setAuthToken(tokenFromUrl);
  current.searchParams.delete(queryParam);
  window.history.replaceState({}, document.title, `${current.pathname}${current.search}${current.hash}`);
};

const patchDocumentNavigation = () => {
  if (window.__AUTH_NAV_PATCHED) return;
  window.__AUTH_NAV_PATCHED = true;

  document.addEventListener(
    "click",
    (event) => {
      const link = event.target.closest("a[href]");
      if (!link) return;
      if (link.hasAttribute("download")) return;
      if (link.target && link.target !== "_self") return;
      if (event.defaultPrevented) return;
      if (event.button !== 0) return;
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const href = link.getAttribute("href");
      if (!href) return;
      const nextHref = buildUrlWithToken(href);
      if (nextHref && nextHref !== href) {
        link.setAttribute("href", nextHref);
      }
    },
    true
  );

  document.addEventListener(
    "submit",
    (event) => {
      const form = event.target;
      if (!(form instanceof HTMLFormElement)) return;
      ensureFormTokenField(form);
    },
    true
  );
};

const observeAuthTargets = () => {
  if (window.__AUTH_TARGET_OBSERVER) return;
  const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      for (const node of mutation.addedNodes) {
        if (!(node instanceof Element)) continue;
        if (node.matches("a[href]")) {
          const href = node.getAttribute("href");
          const nextHref = buildUrlWithToken(href);
          if (nextHref && nextHref !== href) {
            node.setAttribute("href", nextHref);
          }
        }
        if (node.matches("form")) {
          ensureFormTokenField(node);
        }
        node.querySelectorAll?.("a[href]").forEach((link) => {
          const href = link.getAttribute("href");
          const nextHref = buildUrlWithToken(href);
          if (nextHref && nextHref !== href) {
            link.setAttribute("href", nextHref);
          }
        });
        node.querySelectorAll?.("form").forEach((form) => {
          ensureFormTokenField(form);
        });
      }
    }
  });
  observer.observe(document.documentElement, { childList: true, subtree: true });
  window.__AUTH_TARGET_OBSERVER = observer;
};

const syncSessionFromStoredToken = async () => {
  if (window.__SESSION_USER_ID) return false;

  const token = getAuthToken();
  if (!token) return false;

  const currentUrl = new URL(window.location.href);
  if (currentUrl.searchParams.get(getAuthQueryParam())) return false;

  if (window.__AUTH_SESSION_SYNC_STARTED) {
    return true;
  }
  window.__AUTH_SESSION_SYNC_STARTED = true;

  document.body.classList.add("auth-sync-pending");
  window.__AUTH_SESSION_SYNC_PENDING = true;

  const headers = {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };
  const csrfToken = getCsrfToken();
  if (csrfToken) {
    headers["X-CSRF-Token"] = csrfToken;
  }

  try {
    const response = await window.fetch("/api/auth/session", {
      method: "POST",
      credentials: "same-origin",
      headers,
      body: JSON.stringify({ token }),
    });
    if (!response.ok) {
      throw new Error(`sync_failed_${response.status}`);
    }
    const payload = await response.json().catch(() => ({}));
    if (!payload?.ok) {
      throw new Error("sync_not_ok");
    }
    window.__AUTH_SESSION_SYNC_STARTED = false;
    window.location.reload();
    return true;
  } catch {
    window.__AUTH_SESSION_SYNC_STARTED = false;
    document.body.classList.remove("auth-sync-pending");
    window.__AUTH_SESSION_SYNC_PENDING = false;
    return false;
  }
};

const setupAuthTokenBridge = async () => {
  if (bootstrapPageAuthFromToken()) {
    return true;
  }
  stripAuthTokenFromAddressBar();
  patchFetch();
  decorateForms();
  decorateInternalLinks();
  patchDocumentNavigation();
  observeAuthTargets();
  return syncSessionFromStoredToken();
};

const navigateWithAuth = (rawUrl, options = {}) => {
  const nextUrl = buildUrlWithToken(rawUrl);
  if (!nextUrl) return;
  if (options.replace) {
    window.location.replace(nextUrl);
    return;
  }
  window.location.href = nextUrl;
};

export {
  clearAuthToken,
  decorateForms,
  decorateInternalLinks,
  getAuthQueryParam,
  getAuthStorageKey,
  getAuthToken,
  navigateWithAuth,
  setAuthToken,
  setupAuthTokenBridge,
};
