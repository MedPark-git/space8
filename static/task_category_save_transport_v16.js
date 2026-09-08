(() => {
  const DIALOG = "#task-category-selector-manager-v3";
  const SAVE_URL = "/tasks/new";
  const csrfToken = () => document.querySelector('meta[name="csrf-token"]')?.content || "";
  const currentDepartmentId = () => document.body.dataset.currentDepartmentId || "";
  const currentRole = () => document.body.dataset.currentRole || "";
  const isAdmin = () => currentRole() === "관리자" || currentRole().includes("관리자");

  window.__MEDPARK_CATEGORY_TRANSPORT__ = "v16-html-json-dual";

  const activeSection = () =>
    [...document.querySelectorAll("[data-work-category-form]")].find((node) => node.offsetParent !== null)
    || document.querySelector("[data-work-category-form]");

  const departmentId = () => {
    const section = activeSection();
    const selected = section?.querySelector("[data-work-department]")?.value || "";
    return isAdmin() ? (selected || currentDepartmentId()) : currentDepartmentId();
  };

  const readCatalog = () => {
    const source = document.getElementById("work-category-catalog");
    if (!source) return [];
    try {
      const rows = JSON.parse(source.textContent || "[]");
      return Array.isArray(rows) ? rows : [];
    } catch (_error) {
      return [];
    }
  };

  const writeCatalog = (rows) => {
    let source = document.getElementById("work-category-catalog");
    if (!source) {
      source = document.createElement("script");
      source.type = "application/json";
      source.id = "work-category-catalog";
      document.body.append(source);
    }
    source.textContent = JSON.stringify(Array.isArray(rows) ? rows : []);
  };

  const setStatus = (form, message, tone = "") => {
    const status = form.querySelector(".task-category-operation-status");
    if (!status) return;
    status.textContent = message;
    status.className = "task-category-operation-status";
    if (tone) status.classList.add(tone);
  };

  const syncTaskTypes = (dialog) => {
    const picked = [...dialog.querySelectorAll("[data-category-task-type]:checked")].map((item) => item.value);
    const taskForm = activeSection()?.closest("form.form-panel");
    taskForm?.querySelectorAll('input[name="task_types"]').forEach((item) => {
      item.checked = picked.includes(item.value);
    });
    return picked;
  };

  const parseHtmlResult = async (response) => {
    const html = await response.text();
    const doc = new DOMParser().parseFromString(html, "text/html");
    const catalogNode = doc.getElementById("work-category-catalog");
    let categories = [];
    if (catalogNode) {
      try {
        const rows = JSON.parse(catalogNode.textContent || "[]");
        if (Array.isArray(rows)) categories = rows;
      } catch (_error) {}
    }

    let finalUrl;
    try {
      finalUrl = new URL(response.url || window.location.href, window.location.origin);
    } catch (_error) {
      finalUrl = new URL(window.location.href);
    }

    const flash = doc.querySelector(".flash-stack .flash, .flash");
    const message = flash?.textContent?.trim() || "";
    const resultTone = finalUrl.searchParams.get("category_result") || "";
    const categoryId = finalUrl.searchParams.get("category_id") || "";
    const middleName = finalUrl.searchParams.get("category_middle") || "";
    const category = categoryId
      ? categories.find((row) => String(row.id) === String(categoryId)) || null
      : null;
    const ok = resultTone ? resultTone !== "error" : !doc.querySelector(".flash.error");

    return {
      ok,
      message: message || (ok ? "업무구분을 저장했습니다." : "업무구분 저장 중 오류가 발생했습니다."),
      categories,
      category,
      middle_name: middleName,
      transport: "html-fallback-v16",
    };
  };

  const saveCategory = async (action, values) => {
    const data = new FormData();
    data.set("csrf_token", csrfToken());
    data.set("category_action", action);
    Object.entries(values).forEach(([key, value]) => data.set(key, value ?? ""));

    const url = `${SAVE_URL}?category_manager=1&category_transport=v9&category_action=${encodeURIComponent(action)}`;
    const response = await fetch(url, {
      method: "POST",
      body: data,
      credentials: "same-origin",
      redirect: "follow",
      headers: {
        Accept: "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "X-MedPark-Category-JSON": "1",
      },
    });

    if (response.url.includes("/login")) {
      window.location.assign(response.url);
      throw new Error("로그인이 필요합니다.");
    }

    const contentType = (response.headers.get("content-type") || "").toLowerCase();
    let result;
    if (contentType.includes("application/json")) {
      result = await response.json().catch(() => ({}));
    } else if (contentType.includes("text/html")) {
      result = await parseHtmlResult(response);
    } else {
      throw new Error(`업무구분 저장 응답 형식을 확인할 수 없습니다. (HTTP ${response.status})`);
    }

    if (!response.ok && result.ok !== true) {
      throw new Error(result.message || `업무구분 처리 실패 (HTTP ${response.status})`);
    }
    if (!result.ok) {
      throw new Error(result.message || "업무구분 저장에 실패했습니다.");
    }
    return result;
  };

  const replaceOptions = (select, items, placeholder) => {
    if (!select) return;
    select.replaceChildren(new Option(placeholder, ""));
    items.forEach(({ value, label }) => select.append(new Option(label, String(value))));
  };

  const refreshTaskSection = (categories, preferredMiddle = "", preferredCategoryId = "") => {
    const section = activeSection();
    if (!section) return;
    const dept = section.querySelector("[data-work-department]");
    const middle = section.querySelector("[data-work-middle]");
    const small = section.querySelector("[data-work-category]");
    if (!dept || !middle || !small) return;

    const deptId = dept.value || currentDepartmentId();
    const rows = (categories || readCatalog()).filter((row) => String(row.department_id) === String(deptId));
    const middleNames = [...new Set(rows.map((row) => row.middle_name).filter(Boolean))];
    replaceOptions(middle, middleNames.map((name) => ({ value: name, label: name })), "미분류");
    if (preferredMiddle && middleNames.includes(preferredMiddle)) middle.value = preferredMiddle;
    const smallRows = rows.filter((row) => row.middle_name === middle.value);
    replaceOptions(small, smallRows.map((row) => ({ value: row.id, label: row.small_name || "소분류 없음" })), "미분류");
    if (preferredCategoryId && [...small.options].some((option) => option.value === String(preferredCategoryId))) {
      small.value = String(preferredCategoryId);
    }
  };

  const refreshDialog = (dialog, categories, preferredMiddle = "", preferredSmallId = "") => {
    const rows = (categories || readCatalog()).filter((row) => String(row.department_id) === String(departmentId()));
    const middleSelect = dialog.querySelector("[data-existing-middle]");
    const smallSelect = dialog.querySelector("[data-existing-small]");
    const middleNames = [...new Set(rows.map((row) => row.middle_name).filter(Boolean))];
    const currentMiddle = preferredMiddle || middleSelect?.value || "";
    replaceOptions(middleSelect, middleNames.map((name) => ({ value: name, label: name })), "중분류 선택");
    if (middleSelect && middleNames.includes(currentMiddle)) middleSelect.value = currentMiddle;
    const smallRows = rows.filter((row) => row.middle_name === (middleSelect?.value || "") && String(row.small_name || "").trim());
    replaceOptions(smallSelect, smallRows.map((row) => ({ value: row.id, label: row.small_name })), "소분류 선택");
    if (smallSelect && preferredSmallId && [...smallSelect.options].some((option) => option.value === String(preferredSmallId))) {
      smallSelect.value = String(preferredSmallId);
    }
  };

  document.addEventListener("submit", async (event) => {
    const form = event.target.closest(`${DIALOG} [data-category-operation-form]`);
    if (!form) return;

    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();

    const dialog = form.closest(DIALOG);
    const operation = form.querySelector("[data-operation]")?.value || "";
    const middle = form.querySelector("[data-existing-middle]")?.value || "";
    const smallId = form.querySelector("[data-existing-small]")?.value || "";
    const newName = form.querySelector("[data-new-name]")?.value.trim() || "";
    const deptId = departmentId();

    if (!deptId) return setStatus(form, "대분류(부서·팀)를 확인해 주세요.", "error");
    if (operation !== "middle_add" && !middle) return setStatus(form, "기존 중분류를 선택해 주세요.", "error");
    if (operation === "small_rename" && !smallId) return setStatus(form, "기존 소분류를 선택해 주세요.", "error");
    if (!newName) return setStatus(form, "새 이름을 입력해 주세요.", "error");

    if (["middle_add", "small_add"].includes(operation)) {
      const picked = syncTaskTypes(dialog);
      if (!picked.length) return setStatus(form, "업무분류를 하나 이상 선택해 주세요.", "error");
    }

    const submit = form.querySelector('button[type="submit"]');
    if (submit) submit.disabled = true;
    setStatus(form, "저장 중입니다...");

    try {
      let action;
      let values;
      if (operation === "middle_add") {
        action = "add";
        values = { ...(isAdmin() ? { department_id: deptId } : {}), middle_name: newName, small_name: "" };
      } else if (operation === "small_add") {
        action = "add";
        values = { ...(isAdmin() ? { department_id: deptId } : {}), middle_name: middle, small_name: newName };
      } else if (operation === "middle_rename") {
        action = "rename_middle";
        values = { ...(isAdmin() ? { department_id: deptId } : {}), old_middle_name: middle, new_middle_name: newName };
      } else if (operation === "small_rename") {
        action = "rename_small";
        values = { ...(isAdmin() ? { department_id: deptId } : {}), work_category_id: smallId, new_small_name: newName };
      } else {
        throw new Error("지원하지 않는 작업입니다.");
      }

      const result = await saveCategory(action, values);
      if (Array.isArray(result.categories) && result.categories.length) writeCatalog(result.categories);
      const preferredMiddle = operation === "middle_add" || operation === "middle_rename" ? newName : middle;
      const preferredSmallId = result.category?.id || (operation === "small_rename" ? smallId : "");
      refreshTaskSection(result.categories, preferredMiddle, preferredSmallId);
      refreshDialog(dialog, result.categories, preferredMiddle, preferredSmallId);
      form.querySelector("[data-new-name]").value = "";
      setStatus(form, result.message || "업무구분을 저장했습니다.", "success");
    } catch (error) {
      setStatus(form, String(error.message || error), "error");
    } finally {
      if (submit) submit.disabled = false;
    }
  }, true);
})();
