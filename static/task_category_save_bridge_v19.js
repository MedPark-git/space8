(() => {
  const nativeFetch = window.fetch.bind(window);
  const CATEGORY_REQUEST_RE = /^\/tasks\/new\?[^#]*category_manager=1/;
  const DIRECT_ADD_URL = "/tasks/work-categories/add";
  const ADMIN_ADD_URL = "/admin/work-categories";
  const currentRole = () => document.body.dataset.currentRole || "";
  const isAdmin = () => currentRole() === "관리자" || currentRole().includes("관리자");

  const jsonResponse = (payload, status = 200) => new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
  });

  const parseHtml = (html) => new DOMParser().parseFromString(html || "", "text/html");

  const readCatalogFromDocument = (doc) => {
    const node = doc?.getElementById("work-category-catalog");
    if (!node) return [];
    try {
      const rows = JSON.parse(node.textContent || "[]");
      return Array.isArray(rows) ? rows : [];
    } catch (_error) {
      return [];
    }
  };

  const refreshCatalog = async () => {
    const response = await nativeFetch(`/tasks/new?category_catalog_refresh=${Date.now()}`, {
      method: "GET",
      credentials: "same-origin",
      cache: "no-store",
      headers: { "X-Requested-With": "XMLHttpRequest" },
    });
    if (!response.ok) return [];
    const doc = parseHtml(await response.text());
    return readCatalogFromDocument(doc);
  };

  const normalizeFormData = (body) => {
    if (body instanceof FormData) return body;
    return null;
  };

  const runDirectAdd = async (data) => {
    const direct = new FormData();
    for (const key of ["csrf_token", "department_id", "middle_name", "small_name"]) {
      const value = data.get(key);
      if (value !== null) direct.set(key, value);
    }
    direct.set("return_to", "/tasks/new");

    return nativeFetch(DIRECT_ADD_URL, {
      method: "POST",
      body: direct,
      credentials: "same-origin",
      redirect: "follow",
      cache: "no-store",
      headers: {
        Accept: "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "X-MedPark-Category-Bridge": "v19",
      },
    });
  };

  const runAdminAdd = async (data) => {
    const adminData = new FormData();
    for (const key of ["csrf_token", "department_id", "middle_name", "small_name"]) {
      const value = data.get(key);
      if (value !== null) adminData.set(key, value);
    }

    const response = await nativeFetch(ADMIN_ADD_URL, {
      method: "POST",
      body: adminData,
      credentials: "same-origin",
      redirect: "follow",
      cache: "no-store",
    });

    if (response.url.includes("/login")) return response;

    const html = await response.text();
    const doc = parseHtml(html);
    const errorNode = doc.querySelector(".flash.error");
    const messageNode = doc.querySelector(".flash.success, .flash.info, .flash");
    const message = (errorNode || messageNode)?.textContent?.trim() || "";

    if (!response.ok || errorNode) {
      return jsonResponse({
        ok: false,
        message: message || `업무구분 저장에 실패했습니다. (HTTP ${response.status})`,
        transport: "admin-work-category-v19",
      }, response.ok ? 400 : response.status);
    }

    const categories = await refreshCatalog();
    const departmentId = String(data.get("department_id") || "");
    const middleName = String(data.get("middle_name") || "").trim();
    const smallName = String(data.get("small_name") || "").trim();
    const category = categories.find((row) =>
      String(row.department_id) === departmentId
      && String(row.middle_name || "") === middleName
      && String(row.small_name || "") === smallName
    ) || null;

    return jsonResponse({
      ok: true,
      message: message || (category ? "업무구분을 저장했습니다." : "업무구분 저장을 완료했습니다."),
      categories,
      category,
      transport: "admin-work-category-v19",
    });
  };

  window.fetch = async (input, init = {}) => {
    let url;
    try {
      url = typeof input === "string" ? input : (input?.url || "");
      const parsed = new URL(url, window.location.origin);
      url = parsed.pathname + parsed.search;
    } catch (_error) {
      return nativeFetch(input, init);
    }

    if (!CATEGORY_REQUEST_RE.test(url) || String(init.method || "GET").toUpperCase() !== "POST") {
      return nativeFetch(input, init);
    }

    const data = normalizeFormData(init.body);
    if (!data) return nativeFetch(input, init);

    const action = String(data.get("category_action") || new URL(url, window.location.origin).searchParams.get("category_action") || "").trim();
    if (action !== "add") return nativeFetch(input, init);

    try {
      const directResponse = await runDirectAdd(data);
      const contentType = (directResponse.headers.get("content-type") || "").toLowerCase();
      if (directResponse.url.includes("/login")) return directResponse;
      if (contentType.includes("application/json")) return directResponse;

      if (isAdmin()) {
        return await runAdminAdd(data);
      }

      const text = await directResponse.text().catch(() => "");
      const doc = parseHtml(text);
      const message = doc.querySelector(".flash.error, .flash")?.textContent?.trim();
      return jsonResponse({
        ok: false,
        message: message || "업무구분 전용 저장 API를 사용할 수 없습니다. 관리자에게 문의해 주세요.",
        transport: "direct-work-category-v19",
      }, directResponse.ok ? 400 : directResponse.status);
    } catch (error) {
      if (isAdmin()) {
        try { return await runAdminAdd(data); } catch (_fallbackError) {}
      }
      return jsonResponse({
        ok: false,
        message: String(error?.message || error || "업무구분 저장 중 오류가 발생했습니다."),
        transport: "category-bridge-v19",
      }, 500);
    }
  };

  window.__MEDPARK_CATEGORY_SAVE_BRIDGE__ = "v19";
})();
