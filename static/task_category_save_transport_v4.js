(() => {
  const API_PATH = "/api/work-categories";
  const DIALOG_SELECTOR = "#task-category-selector-manager-v3";

  const currentDepartmentId = () => document.body.dataset.currentDepartmentId || "";
  const currentRole = () => document.body.dataset.currentRole || "";
  const isAdmin = () => currentRole() === "관리자" || currentRole().includes("관리자");
  const csrfToken = () => document.querySelector('meta[name="csrf-token"]')?.content || "";

  const readCatalog = () => {
    const node = document.getElementById("work-category-catalog");
    if (!node) return [];
    try { return JSON.parse(node.textContent || "[]"); } catch (_error) { return []; }
  };

  const writeCatalog = (catalog) => {
    let node = document.getElementById("work-category-catalog");
    if (!node) {
      node = document.createElement("script");
      node.type = "application/json";
      node.id = "work-category-catalog";
      document.body.append(node);
    }
    node.textContent = JSON.stringify(Array.isArray(catalog) ? catalog : []);
  };

  const activeTaskCategorySection = () => {
    const sections = [...document.querySelectorAll("[data-work-category-form]")];
    return sections.find((section) => section.offsetParent !== null)
      || sections.find((section) => section.closest("#task-editor-modal"))
      || sections[0]
      || null;
  };

  const departmentId = () => {
    if (!isAdmin()) return currentDepartmentId();
    return activeTaskCategorySection()?.querySelector("[data-work-department]")?.value
      || currentDepartmentId();
  };

  const parseJsonBody = (raw) => {
    try {
      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === "object" ? parsed : null;
    } catch (_error) {
      return null;
    }
  };

  const requestCategory = async (action, values = {}) => {
    const response = await fetch(`${API_PATH}?category_action=${encodeURIComponent(action)}&_category_transport=v4`, {
      method: "POST",
      credentials: "same-origin",
      redirect: "follow",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRFToken": csrfToken(),
        "X-Task-Category-Action": action,
      },
      body: JSON.stringify({ category_action: action, ...values }),
    });

    if (response.url.includes("/login")) {
      window.location.assign(response.url);
      throw new Error("로그인이 필요합니다.");
    }

    const raw = await response.text();
    const result = parseJsonBody(raw);
    if (!result) {
      const type = response.headers.get("content-type") || "확인 불가";
      throw new Error(`업무구분 API가 JSON이 아닌 화면 응답을 반환했습니다. (HTTP ${response.status}, ${type})`);
    }

    if (response.ok && result.ok) return result;

    if (result.code === "CATEGORY_EXISTS") {
      const refreshed = await requestCategory("list");
      return {
        ok: true,
        message: "이미 등록된 업무구분입니다. 저장된 기초자료를 다시 불러왔습니다.",
        categories: refreshed.categories || [],
        duplicate: true,
      };
    }

    throw new Error(result.message || `업무구분 처리 실패 (HTTP ${response.status})`);
  };

  const replaceOptions = (select, rows, placeholder, selectedValue = "") => {
    if (!select) return;
    select.replaceChildren(new Option(placeholder, ""));
    rows.forEach(({ value, label }) => select.append(new Option(label, String(value))));
    if (selectedValue && [...select.options].some((option) => option.value === String(selectedValue))) {
      select.value = String(selectedValue);
    }
  };

  const middleNames = (catalog, deptId) => [
    ...new Set(
      catalog
        .filter((item) => String(item.department_id) === String(deptId))
        .map((item) => String(item.middle_name || "").trim())
        .filter(Boolean)
    ),
  ];

  const smallRows = (catalog, deptId, middleName) => catalog.filter(
    (item) => String(item.department_id) === String(deptId)
      && String(item.middle_name || "") === String(middleName || "")
  );

  const refreshDialog = (dialog, preferredMiddle = "", preferredSmallId = "") => {
    const catalog = readCatalog();
    const deptId = departmentId();
    const middle = dialog.querySelector("[data-existing-middle]");
    const small = dialog.querySelector("[data-existing-small]");
    const names = middleNames(catalog, deptId);
    const middleValue = preferredMiddle || middle?.value || "";

    replaceOptions(middle, names.map((name) => ({ value: name, label: name })), "중분류 선택", middleValue);
    const smallItems = smallRows(catalog, deptId, middle?.value)
      .filter((item) => String(item.small_name || "").trim())
      .map((item) => ({ value: item.id, label: item.small_name }));
    replaceOptions(small, smallItems, "소분류 선택", preferredSmallId || small?.value || "");

    const list = dialog.querySelector("[data-category-current-list]");
    const count = dialog.querySelector("[data-category-count]");
    const rows = catalog.filter((item) => String(item.department_id) === String(deptId));
    if (count) count.textContent = `${rows.length}건`;
    if (!list) return;
    if (!rows.length) {
      list.innerHTML = '<div class="task-category-current-empty">등록된 업무구분이 없습니다.</div>';
      return;
    }

    const groups = new Map();
    rows.forEach((item) => {
      if (!groups.has(item.middle_name)) groups.set(item.middle_name, []);
      groups.get(item.middle_name).push(item);
    });
    const esc = (value) => String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
    const body = [];
    [...groups.entries()].forEach(([middleName, items]) => {
      items.forEach((item, index) => {
        body.push(`<tr><td>${index === 0 ? esc(middleName) : "↳"}</td><td>${item.small_name ? esc(item.small_name) : '<span class="permission-muted">미지정</span>'}</td></tr>`);
      });
    });
    list.innerHTML = `<div class="table-wrap"><table class="task-category-current-table"><thead><tr><th>중분류</th><th>소분류</th></tr></thead><tbody>${body.join("")}</tbody></table></div>`;
  };

  const refreshTaskForms = (preferredMiddle = "", preferredCategoryId = "") => {
    const catalog = readCatalog();
    document.querySelectorAll("[data-work-category-form]").forEach((section) => {
      const dept = section.querySelector("[data-work-department]");
      const middle = section.querySelector("[data-work-middle]");
      const small = section.querySelector("[data-work-category]");
      if (!dept || !middle || !small) return;
      if (!isAdmin() && currentDepartmentId()) dept.value = currentDepartmentId();
      const deptId = dept.value || currentDepartmentId();
      const names = middleNames(catalog, deptId);
      const middleValue = preferredMiddle || middle.value || "";
      replaceOptions(middle, names.map((name) => ({ value: name, label: name })), "미분류", middleValue);
      const rows = smallRows(catalog, deptId, middle.value);
      replaceOptions(
        small,
        rows.map((item) => ({ value: item.id, label: item.small_name || "소분류 없음" })),
        "미분류",
        preferredCategoryId || small.value || "",
      );
      if (!small.value && middle.value) {
        const placeholder = rows.find((item) => !String(item.small_name || "").trim());
        if (placeholder) small.value = String(placeholder.id);
      }
    });
  };

  document.addEventListener("submit", async (event) => {
    const form = event.target.closest(`${DIALOG_SELECTOR} [data-category-operation-form]`);
    if (!form) return;

    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();

    const dialog = form.closest("dialog");
    const operation = form.querySelector("[data-operation]")?.value || "";
    const existingMiddle = form.querySelector("[data-existing-middle]")?.value || "";
    const existingSmall = form.querySelector("[data-existing-small]")?.value || "";
    const newNameInput = form.querySelector("[data-new-name]");
    const newName = newNameInput?.value.trim() || "";
    const status = form.querySelector(".task-category-operation-status");
    const submit = form.querySelector("button[type='submit']");
    const deptId = departmentId();

    const setStatus = (message, tone = "") => {
      if (!status) return;
      status.textContent = message;
      status.className = "task-category-operation-status";
      if (tone) status.classList.add(tone);
    };

    if (!deptId) return setStatus("대분류(부서·팀)를 확인해 주세요.", "error");
    if (operation !== "middle_add" && !existingMiddle) return setStatus("기존 중분류를 선택해 주세요.", "error");
    if (operation === "small_rename" && !existingSmall) return setStatus("기존 소분류를 선택해 주세요.", "error");
    if (!newName) return setStatus("새 이름을 입력해 주세요.", "error");

    submit.disabled = true;
    setStatus("저장 중입니다.");

    try {
      let result;
      let preferredMiddle = existingMiddle;
      let preferredSmallId = existingSmall;

      if (operation === "middle_add") {
        result = await requestCategory("add", { department_id: Number(deptId), middle_name: newName, small_name: "" });
        preferredMiddle = newName;
        preferredSmallId = result.category?.id || "";
      } else if (operation === "small_add") {
        result = await requestCategory("add", { department_id: Number(deptId), middle_name: existingMiddle, small_name: newName });
        preferredSmallId = result.category?.id || "";
      } else if (operation === "middle_rename") {
        result = await requestCategory("rename_middle", { department_id: Number(deptId), old_middle_name: existingMiddle, new_middle_name: newName });
        preferredMiddle = newName;
        preferredSmallId = "";
      } else if (operation === "small_rename") {
        result = await requestCategory("rename_small", { work_category_id: Number(existingSmall), new_small_name: newName });
      } else {
        throw new Error("지원하지 않는 업무구분 작업입니다.");
      }

      if (Array.isArray(result.categories)) writeCatalog(result.categories);
      if (newNameInput) newNameInput.value = "";
      refreshDialog(dialog, preferredMiddle, preferredSmallId);
      refreshTaskForms(preferredMiddle, preferredSmallId);
      setStatus(result.message || "업무구분을 저장했습니다.", "success");
    } catch (error) {
      setStatus(String(error.message || error), "error");
    } finally {
      submit.disabled = false;
    }
  }, true);
})();
