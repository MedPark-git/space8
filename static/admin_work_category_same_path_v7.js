(() => {
  const previousFetch = window.fetch.bind(window);

  const isLegacyCrudUrl = (url) => {
    try {
      const parsed = new URL(url, window.location.origin);
      return parsed.pathname === "/admin/work-categories/manage"
        || parsed.pathname === "/admin/work-categories/delete-v2";
    } catch (_error) {
      return false;
    }
  };

  const targetPath = () => {
    const path = window.location.pathname.replace(/\/+$/, "") || "/";
    return path === "/admin/work-categories" ? "/admin/work-categories" : "/admin";
  };

  window.fetch = function medparkAdminWorkCategoryV7Fetch(input, init = {}) {
    const sourceUrl = typeof input === "string" ? input : input?.url;
    if (!sourceUrl || !isLegacyCrudUrl(sourceUrl)) {
      return previousFetch(input, init);
    }

    const legacy = new URL(sourceUrl, window.location.origin);
    const body = init.body instanceof FormData ? init.body : new FormData();
    let operation = String(body.get("operation") || "").trim();
    if (legacy.pathname.endsWith("/delete-v2")) {
      operation = "delete";
      body.set("operation", operation);
    }
    body.set("awc_operation", operation);

    const headers = new Headers(init.headers || {});
    headers.set("Accept", "application/json");
    headers.set("X-Requested-With", "XMLHttpRequest");

    return previousFetch(targetPath(), {
      ...init,
      method: "POST",
      body,
      credentials: "same-origin",
      redirect: "follow",
      headers,
    });
  };

  window.__MEDPARK_ADMIN_WORK_CATEGORY_TRANSPORT__ = "v7-body-marker";
})();
