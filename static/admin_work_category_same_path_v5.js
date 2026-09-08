(() => {
  const originalFetch = window.fetch.bind(window);
  const TARGET = "/admin?section=work-categories";

  const isOldManageUrl = (url) => {
    try {
      const parsed = new URL(url, window.location.origin);
      return parsed.pathname === "/admin/work-categories/manage"
        || parsed.pathname === "/admin/work-categories/delete-v2";
    } catch (_error) {
      return false;
    }
  };

  window.fetch = function medparkAdminWorkCategoryFetch(input, init = {}) {
    const sourceUrl = typeof input === "string" ? input : input?.url;
    if (!sourceUrl || !isOldManageUrl(sourceUrl)) {
      return originalFetch(input, init);
    }

    const parsed = new URL(sourceUrl, window.location.origin);
    const body = init.body;
    if (body instanceof FormData && parsed.pathname.endsWith("/delete-v2")) {
      body.set("operation", "delete");
    }

    const headers = new Headers(init.headers || {});
    headers.set("Accept", "application/json");
    headers.set("X-Requested-With", "XMLHttpRequest");
    headers.set("X-MedPark-Admin-Work-Category", "v5");

    return originalFetch(TARGET, {
      ...init,
      method: "POST",
      body,
      credentials: "same-origin",
      headers,
    });
  };

  window.__MEDPARK_ADMIN_WORK_CATEGORY_TRANSPORT__ = "v5-same-admin-path";
})();
