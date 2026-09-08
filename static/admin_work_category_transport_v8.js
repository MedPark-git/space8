(() => {
  const nativeFetch = window.fetch.bind(window);

  const isLegacyCrudUrl = (url) => {
    try {
      const parsed = new URL(url, window.location.origin);
      return parsed.pathname === "/admin/work-categories/manage"
        || parsed.pathname === "/admin/work-categories/delete-v2";
    } catch (_error) {
      return false;
    }
  };

  const currentAdminUrl = () => {
    const target = new URL(window.location.href);
    target.hash = "";
    if (!target.pathname.startsWith("/admin")) {
      target.pathname = "/admin";
      target.search = "?section=work-categories";
    }
    return target.pathname + target.search;
  };

  window.fetch = function medparkAdminWorkCategoryV8Fetch(input, init = {}) {
    const sourceUrl = typeof input === "string" ? input : input?.url;
    if (!sourceUrl || !isLegacyCrudUrl(sourceUrl)) {
      return nativeFetch(input, init);
    }

    const legacy = new URL(sourceUrl, window.location.origin);
    const sourceForm = init.body instanceof FormData ? init.body : new FormData();
    const params = new URLSearchParams();
    for (const [key, value] of sourceForm.entries()) {
      params.append(key, String(value));
    }

    let operation = String(params.get("operation") || "").trim();
    if (legacy.pathname.endsWith("/delete-v2")) {
      operation = "delete";
      params.set("operation", operation);
    }
    params.set("awc_operation", operation);
    params.set("awc_transport", "v8");

    return nativeFetch(currentAdminUrl(), {
      method: "POST",
      body: params,
      credentials: "same-origin",
      redirect: "follow",
      headers: {
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"
      }
    });
  };

  window.__MEDPARK_ADMIN_WORK_CATEGORY_TRANSPORT__ = "v8-urlencoded-body";
})();
