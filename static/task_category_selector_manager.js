(() => {
  const CREATE_PATH = "/tasks/new";
  const DIALOG_ID = "task-category-selector-manager-v3";
  const currentDepartmentId = () => document.body.dataset.currentDepartmentId || "";
  const currentRole = () => document.body.dataset.currentRole || "";
  const isAdmin = () => currentRole() === "관리자" || currentRole().includes("관리자");
  const csrfToken = () => document.querySelector('meta[name="csrf-token"]')?.content || "";

  const readCatalog = () => {
    const source = document.getElementById("work-category-catalog");
    if (!source) return [];
    try { return JSON.parse(source.textContent || "[]"); } catch (_error) { return []; }
  };

  const writeCatalog = (catalog) => {
    let source = document.getElementById("work-category-catalog");
    if (!source) {
      source = document.createElement("script");
      source.type = "application/json";
      source.id = "work-category-catalog";
      document.body.append(source);
    }
    source.textContent = JSON.stringify(Array.isArray(catalog) ? catalog : []);
  };

  const uniqueMiddleNames = (departmentId) => [
    ...new Set(
      readCatalog()
        .filter((item) => String(item.department_id) === String(departmentId))
        .map((item) => String(item.middle_name || "").trim())
        .filter(Boolean)
    ),
  ];

  const categoriesForMiddle = (departmentId, middleName) => readCatalog().filter(
    (item) => String(item.department_id) === String(departmentId)
      && String(item.middle_name || "") === String(middleName || "")
  );

  const replaceOptions = (select, rows, placeholder) => {
    if (!select) return;
    const previous = select.value;
    select.replaceChildren(new Option(placeholder, ""));
    rows.forEach(({ value, label }) => select.append(new Option(label, String(value))));
    if ([...select.options].some((option) => option.value === previous)) select.value = previous;
  };

  const rebuildTaskCategorySection = (section, preferredMiddle = "", preferredCategoryId = "") => {
    if (!section) return;
    const department = section.querySelector("[data-work-department]");
    const middle = section.querySelector("[data-work-middle]");
    const small = section.querySelector("[data-work-category]");
    if (!department || !middle || !small) return;

    if (!isAdmin() && currentDepartmentId()) department.value = currentDepartmentId();
    const departmentId = department.value || currentDepartmentId();
    const middleNames = uniqueMiddleNames(departmentId);
    const selectedMiddle = preferredMiddle || middle.value || "";
    replaceOptions(middle, middleNames.map((name) => ({ value: name, label: name })), "미분류");
    if (middleNames.includes(selectedMiddle)) middle.value = selectedMiddle;

    const rows = categoriesForMiddle(departmentId, middle.value);
    replaceOptions(
      small,
      rows.map((item) => ({ value: item.id, label: item.small_name || "소분류 없음" })),
      "미분류",
    );

    if (preferredCategoryId && [...small.options].some((option) => option.value === String(preferredCategoryId))) {
      small.value = String(preferredCategoryId);
    } else if (middle.value) {
      const placeholder = rows.find((item) => !String(item.small_name || "").trim());
      if (placeholder) small.value = String(placeholder.id);
    }
  };

  const bindFreshTaskSelectors = (section) => {
    if (!section || section.dataset.categorySelectorFreshBound) return;
    section.dataset.categorySelectorFreshBound = "true";
    const department = section.querySelector("[data-work-department]");
    const middle = section.querySelector("[data-work-middle]");
    department?.addEventListener("change", () => window.setTimeout(() => rebuildTaskCategorySection(section), 0));
    middle?.addEventListener("change", () => window.setTimeout(() => rebuildTaskCategorySection(section, middle.value), 0));
  };

  const postCategoryAction = async (action, values = {}) => {
    const payload = { category_action: action, ...values };
    const response = await fetch(`${CREATE_PATH}?category_action=${encodeURIComponent(action)}`, {
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
      body: JSON.stringify(payload),
    });

    if (response.url.includes("/login")) {
      window.location.assign(response.url);
      throw new Error("로그인이 필요합니다.");
    }

    const dispatch = response.headers.get("X-Task-Category-Dispatch") || "";
    const contentType = response.headers.get("content-type") || "";
    const result = contentType.includes("application/json")
      ? await response.json().catch(() => ({}))
      : {};

    if (!dispatch) {
      throw new Error(`업무구분 저장 요청이 일반 업무등록 화면으로 처리되었습니다. (HTTP ${response.status})`);
    }
    if (!response.ok || !result.ok) {
      throw new Error(result.message || `업무구분 처리 실패 (HTTP ${response.status})`);
    }
    if (Array.isArray(result.categories)) writeCatalog(result.categories);
    return result;
  };

  const ensureStyles = () => {
    if (document.getElementById("task-category-selector-manager-style-v3")) return;
    const style = document.createElement("style");
    style.id = "task-category-selector-manager-style-v3";
    style.textContent = `
      .task-category-selector-manager{width:min(940px,calc(100vw - 28px));max-height:92vh;border:0;border-radius:16px;padding:0;overflow:hidden;background:#f8fafc;box-shadow:0 24px 60px rgba(15,23,42,.24)}
      .task-category-selector-manager::backdrop{background:rgba(15,23,42,.52)}
      .task-category-selector-shell{display:flex;flex-direction:column;max-height:92vh}
      .task-category-selector-head{display:flex;justify-content:space-between;gap:14px;padding:20px 22px;background:#fff;border-bottom:1px solid #e2e8f0}
      .task-category-selector-head h2{margin:4px 0 3px;font-size:23px}.task-category-selector-head p{margin:0;color:#64748b}.task-category-selector-close{border:0;background:transparent;font-size:28px;line-height:1;color:#64748b;cursor:pointer}
      .task-category-selector-body{overflow:auto;padding:18px 20px 24px}.task-category-selector-context{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:14px;padding:11px 13px;border:1px solid #dbe4ef;border-radius:10px;background:#fff}.task-category-selector-context span{color:#64748b}
      .task-category-operation-box{display:grid;grid-template-columns:repeat(2,minmax(220px,1fr));gap:12px;padding:16px;border:1px solid #dbe4ef;border-radius:12px;background:#fff}.task-category-operation-box label{display:grid;gap:6px;font-weight:700}.task-category-operation-box select,.task-category-operation-box input{width:100%;padding:10px 11px;border:1px solid #cbd5e1;border-radius:8px;background:#fff;font:inherit}.task-category-operation-box .span-2{grid-column:1/-1}.task-category-operation-help{grid-column:1/-1;margin:0;color:#64748b;font-size:12px}.task-category-operation-status{grid-column:1/-1;min-height:20px;margin:0;font-size:13px}.task-category-operation-status.success{color:#067647}.task-category-operation-status.error{color:#b42318}.task-category-operation-actions{grid-column:1/-1;display:flex;justify-content:flex-end;gap:8px}
      .task-category-current-box{margin-top:16px;border:1px solid #dbe4ef;border-radius:12px;background:#fff;overflow:hidden}.task-category-current-head{display:flex;justify-content:space-between;gap:10px;align-items:center;padding:13px 15px;border-bottom:1px solid #e2e8f0}.task-category-current-head p{margin:0;color:#64748b;font-size:13px}.task-category-current-table{width:100%;border-collapse:collapse}.task-category-current-table th,.task-category-current-table td{padding:10px 11px;border-bottom:1px solid #eef2f6;text-align:left}.task-category-current-table th{background:#f8fafc;color:#475569;font-size:12px}.task-category-current-empty{padding:26px;text-align:center;color:#94a3b8}
      @media(max-width:760px){.task-category-selector-manager{width:calc(100vw - 14px);max-height:96vh}.task-category-selector-head{padding:16px}.task-category-selector-body{padding:10px}.task-category-operation-box{grid-template-columns:1fr}.task-category-operation-box .span-2,.task-category-operation-help,.task-category-operation-status,.task-category-operation-actions{grid-column:1}.task-category-current-table{min-width:620px}.task-category-current-box{overflow:auto}}
    `;
    document.head.append(style);
  };

  let activeSection = null;

  const ensureDialog = () => {
    let dialog = document.getElementById(DIALOG_ID);
    if (dialog) return dialog;

    dialog = document.createElement("dialog");
    dialog.id = DIALOG_ID;
    dialog.className = "task-category-selector-manager";
    dialog.innerHTML = `
      <div class="task-category-selector-shell">
        <div class="task-category-selector-head">
          <div><span class="eyebrow">WORK CATEGORY</span><h2>중분류·소분류 등록·수정</h2><p>기존 분류는 목록에서 선택하고, 새 이름만 입력합니다.</p></div>
          <button type="button" class="task-category-selector-close" aria-label="닫기">×</button>
        </div>
        <div class="task-category-selector-body">
          <div class="task-category-selector-context"><strong>대분류 (부서·팀)</strong><span data-department-name>-</span></div>
          <form class="task-category-operation-box" data-category-operation-form>
            <label class="span-2">작업 선택
              <select name="operation" data-operation>
                <option value="small_add">기존 중분류에 소분류 추가</option>
                <option value="middle_add">중분류 신규 등록</option>
                <option value="middle_rename">기존 중분류 수정</option>
                <option value="small_rename">기존 소분류 수정</option>
              </select>
            </label>
            <label data-existing-middle-wrap>기존 중분류
              <select data-existing-middle><option value="">중분류 선택</option></select>
            </label>
            <label data-existing-small-wrap hidden>기존 소분류
              <select data-existing-small><option value="">소분류 선택</option></select>
            </label>
            <label data-new-name-wrap>새 소분류명
              <input data-new-name maxlength="150" autocomplete="off">
            </label>
            <p class="task-category-operation-help" data-operation-help>저장된 중분류를 선택한 뒤 새 소분류명만 입력하세요.</p>
            <p class="task-category-operation-status" role="status" aria-live="polite"></p>
            <div class="task-category-operation-actions"><button class="button primary" type="submit">저장</button></div>
          </form>
          <section class="task-category-current-box">
            <div class="task-category-current-head"><div><strong>현재 등록된 업무구분</strong><p>기존 분류 확인용입니다. 수정 대상은 위 선택창에서 고릅니다.</p></div><strong data-category-count>0건</strong></div>
            <div data-category-current-list></div>
          </section>
        </div>
      </div>`;
    document.body.append(dialog);

    const operation = dialog.querySelector("[data-operation]");
    const existingMiddleWrap = dialog.querySelector("[data-existing-middle-wrap]");
    const existingMiddle = dialog.querySelector("[data-existing-middle]");
    const existingSmallWrap = dialog.querySelector("[data-existing-small-wrap]");
    const existingSmall = dialog.querySelector("[data-existing-small]");
    const newNameWrap = dialog.querySelector("[data-new-name-wrap]");
    const newName = dialog.querySelector("[data-new-name]");
    const help = dialog.querySelector("[data-operation-help]");
    const status = dialog.querySelector(".task-category-operation-status");
    const departmentName = dialog.querySelector("[data-department-name]");
    const count = dialog.querySelector("[data-category-count]");
    const currentList = dialog.querySelector("[data-category-current-list]");
    const form = dialog.querySelector("[data-category-operation-form]");

    const departmentId = () => {
      const select = activeSection?.querySelector("[data-work-department]");
      return isAdmin() ? (select?.value || currentDepartmentId()) : currentDepartmentId();
    };

    const selectedDepartmentName = () => {
      const select = activeSection?.querySelector("[data-work-department]");
      if (!isAdmin()) {
        const option = [...(select?.options || [])].find((item) => String(item.value) === String(currentDepartmentId()));
        return option?.textContent?.trim() || "본인 소속 부서(팀)";
      }
      return select?.selectedOptions?.[0]?.textContent?.trim() || "-";
    };

    const setStatus = (message = "", tone = "") => {
      status.textContent = message;
      status.className = "task-category-operation-status";
      if (tone) status.classList.add(tone);
    };

    const rebuildExistingSmall = () => {
      const rows = categoriesForMiddle(departmentId(), existingMiddle.value)
        .filter((item) => String(item.small_name || "").trim())
        .map((item) => ({ value: item.id, label: item.small_name }));
      replaceOptions(existingSmall, rows, "소분류 선택");
    };

    const rebuildSelectors = (preferredMiddle = "", preferredSmallId = "") => {
      const names = uniqueMiddleNames(departmentId());
      replaceOptions(existingMiddle, names.map((name) => ({ value: name, label: name })), "중분류 선택");
      if (preferredMiddle && names.includes(preferredMiddle)) existingMiddle.value = preferredMiddle;
      rebuildExistingSmall();
      if (preferredSmallId && [...existingSmall.options].some((option) => option.value === String(preferredSmallId))) {
        existingSmall.value = String(preferredSmallId);
      }
    };

    const renderCurrent = () => {
      const rows = readCatalog().filter((item) => String(item.department_id) === String(departmentId()));
      count.textContent = `${rows.length}건`;
      if (!rows.length) {
        currentList.innerHTML = '<div class="task-category-current-empty">등록된 업무구분이 없습니다.</div>';
        return;
      }
      const grouped = new Map();
      rows.forEach((item) => {
        if (!grouped.has(item.middle_name)) grouped.set(item.middle_name, []);
        grouped.get(item.middle_name).push(item);
      });
      const body = [];
      [...grouped.entries()].forEach(([middleName, items]) => {
        items.forEach((item, index) => {
          body.push(`<tr><td>${index === 0 ? String(middleName).replaceAll("&", "&amp;").replaceAll("<", "&lt;") : "↳"}</td><td>${item.small_name ? String(item.small_name).replaceAll("&", "&amp;").replaceAll("<", "&lt;") : '<span class="permission-muted">미지정</span>'}</td></tr>`);
        });
      });
      currentList.innerHTML = `<div class="table-wrap"><table class="task-category-current-table"><thead><tr><th>중분류</th><th>소분류</th></tr></thead><tbody>${body.join("")}</tbody></table></div>`;
    };

    const applyOperation = () => {
      const value = operation.value;
      existingMiddleWrap.hidden = value === "middle_add";
      existingSmallWrap.hidden = value !== "small_rename";
      newName.value = "";
      if (value === "middle_add") {
        newNameWrap.childNodes[0].nodeValue = "새 중분류명";
        newName.maxLength = 100;
        help.textContent = "새 중분류명을 입력합니다. 기존 중분류 선택은 필요하지 않습니다.";
      } else if (value === "small_add") {
        newNameWrap.childNodes[0].nodeValue = "새 소분류명";
        newName.maxLength = 150;
        help.textContent = "저장된 중분류를 선택한 뒤 새 소분류명만 입력하세요.";
      } else if (value === "middle_rename") {
        newNameWrap.childNodes[0].nodeValue = "새 중분류명";
        newName.maxLength = 100;
        help.textContent = "수정할 기존 중분류를 선택한 뒤 변경할 새 이름만 입력하세요.";
      } else {
        newNameWrap.childNodes[0].nodeValue = "새 소분류명";
        newName.maxLength = 150;
        help.textContent = "기존 중분류와 소분류를 순서대로 선택한 뒤 변경할 새 이름만 입력하세요.";
      }
      setStatus("");
    };

    operation.addEventListener("change", applyOperation);
    existingMiddle.addEventListener("change", rebuildExistingSmall);

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const department = departmentId();
      const op = operation.value;
      const middle = existingMiddle.value;
      const smallId = existingSmall.value;
      const nextName = newName.value.trim();
      if (!department) { setStatus("대분류(부서·팀)를 확인해 주세요.", "error"); return; }
      if (op !== "middle_add" && !middle) { setStatus("기존 중분류를 선택해 주세요.", "error"); return; }
      if (op === "small_rename" && !smallId) { setStatus("기존 소분류를 선택해 주세요.", "error"); return; }
      if (!nextName) { setStatus("새 이름을 입력해 주세요.", "error"); return; }

      const submit = form.querySelector("button[type='submit']");
      submit.disabled = true;
      setStatus("저장 중입니다.");
      try {
        let result;
        if (op === "middle_add") {
          result = await postCategoryAction("add", { department_id: Number(department), middle_name: nextName, small_name: "" });
          rebuildSelectors(nextName);
          operation.value = "small_add";
          applyOperation();
          existingMiddle.value = nextName;
        } else if (op === "small_add") {
          result = await postCategoryAction("add", { department_id: Number(department), middle_name: middle, small_name: nextName });
          rebuildSelectors(middle, result.category?.id || "");
          existingMiddle.value = middle;
        } else if (op === "middle_rename") {
          result = await postCategoryAction("rename_middle", { department_id: Number(department), old_middle_name: middle, new_middle_name: nextName });
          rebuildSelectors(nextName);
          existingMiddle.value = nextName;
        } else {
          result = await postCategoryAction("rename_small", { work_category_id: Number(smallId), new_small_name: nextName });
          rebuildSelectors(middle, smallId);
          existingMiddle.value = middle;
          rebuildExistingSmall();
          if ([...existingSmall.options].some((option) => option.value === String(smallId))) existingSmall.value = String(smallId);
        }
        newName.value = "";
        renderCurrent();
        rebuildTaskCategorySection(activeSection, existingMiddle.value, result.category?.id || smallId || "");
        bindFreshTaskSelectors(activeSection);
        setStatus(result.message || "업무구분을 저장했습니다.", "success");
      } catch (error) {
        setStatus(String(error.message || error), "error");
      } finally {
        submit.disabled = false;
      }
    });

    dialog.querySelector(".task-category-selector-close")?.addEventListener("click", () => dialog.close());
    dialog.addEventListener("click", (event) => { if (event.target === dialog) dialog.close(); });
    dialog.addEventListener("cancel", (event) => { event.preventDefault(); dialog.close(); });

    dialog.openFor = (section) => {
      activeSection = section;
      if (!isAdmin() && currentDepartmentId()) {
        const department = section.querySelector("[data-work-department]");
        if (department) department.value = currentDepartmentId();
      }
      bindFreshTaskSelectors(section);
      departmentName.textContent = selectedDepartmentName();
      operation.value = "small_add";
      rebuildSelectors(section.querySelector("[data-work-middle]")?.value || "");
      applyOperation();
      renderCurrent();
      if (!dialog.open) dialog.showModal();
    };

    return dialog;
  };

  const openForButton = (button) => {
    const section = button.closest("[data-work-category-form]");
    if (!section) return;
    ensureStyles();
    ensureDialog().openFor(section);
  };

  document.addEventListener("click", (event) => {
    const button = event.target.closest(".task-category-tools button");
    if (!button) return;
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    openForButton(button);
  }, true);

  const init = () => {
    ensureStyles();
    document.querySelectorAll("[data-work-category-form]").forEach(bindFreshTaskSelectors);
    const oldDialog = document.getElementById("task-category-manager");
    if (oldDialog?.open) oldDialog.close();
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
