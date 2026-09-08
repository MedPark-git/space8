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

  const currentAdminPath = () => {
    const path = window.location.pathname.replace(/\/+$/, "") || "/";
    if (path === "/admin" || path === "/admin/work-categories") return path;
    return "/admin";
  };

  window.fetch = function medparkAdminWorkCategoryV6Fetch(input, init = {}) {
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

    const target = new URL(currentAdminPath(), window.location.origin);
    if (target.pathname === "/admin") target.searchParams.set("section", "work-categories");
    target.searchParams.set("awc", "1");
    target.searchParams.set("operation", operation);
    target.searchParams.set("v", "6");

    const headers = new Headers(init.headers || {});
    headers.set("Accept", "application/json");
    headers.set("X-Requested-With", "XMLHttpRequest");
    // No custom routing header: AI SPACE proxies may drop non-standard headers.

    return previousFetch(target.pathname + target.search, {
      ...init,
      method: "POST",
      body,
      credentials: "same-origin",
      redirect: "follow",
      headers,
    });
  };

  window.__MEDPARK_ADMIN_WORK_CATEGORY_TRANSPORT__ = "v6-query-marker";
})();
