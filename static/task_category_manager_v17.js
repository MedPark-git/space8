(() => {
  const DIALOG_ID = "task-category-manager-v17";
  const SAVE_URL = "/tasks/new";
  const TASK_TYPES = ["대표이사님 수명업무", "루틴", "일반", "주요"];

  let sourceSection = null;

  const csrfToken = () => document.querySelector('meta[name="csrf-token"]')?.content || "";
  const currentDepartmentId = () => document.body.dataset.currentDepartmentId || "";
  const currentRole = () => document.body.dataset.currentRole || "";
  const isAdmin = () => currentRole() === "관리자" || currentRole().includes("관리자");

  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

  const readCatalog = () => {
    const node = document.getElementById("work-category-catalog");
    if (!node) return [];
    try {
      const rows = JSON.parse(node.textContent || "[]");
      return Array.isArray(rows) ? rows : [];
    } catch (_error) {
      return [];
    }
  };

  const writeCatalog = (rows) => {
    if (!Array.isArray(rows)) return;
    let node = document.getElementById("work-category-catalog");
    if (!node) {
      node = document.createElement("script");
      node.type = "application/json";
      node.id = "work-category-catalog";
      document.body.append(node);
    }
    node.textContent = JSON.stringify(rows);
  };

  const taskForm = () => sourceSection?.closest("form.form-panel") || null;
  const departmentSelect = () => sourceSection?.querySelector("[data-work-department]") || null;
  const departmentId = () => {
    const selected = departmentSelect()?.value || "";
    return isAdmin() ? (selected || currentDepartmentId()) : currentDepartmentId();
  };
  const departmentName = () => {
    const select = departmentSelect();
    if (!select) return "본인 소속 부서(팀)";
    if (!isAdmin()) {
      const option = [...select.options].find((item) => String(item.value) === String(currentDepartmentId()));
      return option?.textContent?.trim() || "본인 소속 부서(팀)";
    }
    return select.selectedOptions?.[0]?.textContent?.trim() || "-";
  };

  const rowsForDepartment = () => readCatalog().filter(
    (row) => String(row.department_id) === String(departmentId())
  );

  const setStatus = (dialog, message = "", tone = "") => {
    const node = dialog.querySelector("[data-v17-status]");
    if (!node) return;
    node.textContent = message;
    node.className = "task-category-operation-status";
    if (tone) node.classList.add(tone);
  };

  const replaceOptions = (select, items, placeholder) => {
    if (!select) return;
    const previous = select.value;
    select.replaceChildren(new Option(placeholder, ""));
    items.forEach(({ value, label }) => select.append(new Option(label, String(value))));
    if ([...select.options].some((option) => option.value === previous)) select.value = previous;
  };

  const syncTaskTypesToSource = (dialog) => {
    const picked = [...dialog.querySelectorAll('[data-v17-task-type]:checked')].map((item) => item.value);
    taskForm()?.querySelectorAll('input[name="task_types"]').forEach((input) => {
      input.checked = picked.includes(input.value);
    });
    return picked;
  };

  const renderTaskTypes = (dialog) => {
    const holder = dialog.querySelector("[data-v17-task-types]");
    if (!holder) return;
    const sourceInputs = [...(taskForm()?.querySelectorAll('input[name="task_types"]') || [])];
    const values = sourceInputs.length ? sourceInputs.map((input) => input.value) : TASK_TYPES;
    holder.innerHTML = "";
    values.forEach((value) => {
      const label = document.createElement("label");
      label.className = "v17-task-type";
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.value = value;
      checkbox.dataset.v17TaskType = "1";
      checkbox.checked = Boolean(sourceInputs.find((input) => input.value === value)?.checked);
      checkbox.addEventListener("change", () => syncTaskTypesToSource(dialog));
      label.append(checkbox, document.createTextNode(value));
      holder.append(label);
    });
  };

  const renderCurrent = (dialog) => {
    const rows = rowsForDepartment();
    const count = dialog.querySelector("[data-v17-count]");
    const list = dialog.querySelector("[data-v17-list]");
    if (count) count.textContent = `${rows.length}건`;
    if (!list) return;
    if (!rows.length) {
      list.innerHTML = '<div class="task-category-current-empty">등록된 업무구분이 없습니다.</div>';
      return;
    }
    const grouped = new Map();
    rows.forEach((row) => {
      if (!grouped.has(row.middle_name)) grouped.set(row.middle_name, []);
      grouped.get(row.middle_name).push(row);
    });
    const body = [];
    [...grouped.entries()].forEach(([middleName, items]) => {
      items.forEach((item, index) => {
        body.push(`<tr><td>${index === 0 ? `<strong>${escapeHtml(middleName)}</strong>` : "↳"}</td><td>${item.small_name ? escapeHtml(item.small_name) : '<span class="permission-muted">미지정</span>'}</td></tr>`);
      });
    });
    list.innerHTML = `<div class="table-wrap"><table class="task-category-current-table"><thead><tr><th>중분류</th><th>소분류</th></tr></thead><tbody>${body.join("")}</tbody></table></div>`;
  };

  const refreshSelectors = (dialog, preferredMiddle = "", preferredSmallId = "") => {
    const rows = rowsForDepartment();
    const middle = dialog.querySelector("[data-v17-middle]");
    const small = dialog.querySelector("[data-v17-small]");
    const names = [...new Set(rows.map((row) => String(row.middle_name || "").trim()).filter(Boolean))];
    replaceOptions(middle, names.map((name) => ({ value: name, label: name })), "중분류 선택");
    if (preferredMiddle && names.includes(preferredMiddle)) middle.value = preferredMiddle;
    const smallRows = rows.filter((row) => row.middle_name === middle.value && String(row.small_name || "").trim());
    replaceOptions(small, smallRows.map((row) => ({ value: row.id, label: row.small_name })), "소분류 선택");
    if (preferredSmallId && [...small.options].some((option) => option.value === String(preferredSmallId))) {
      small.value = String(preferredSmallId);
    }
  };

  const refreshSourceSection = (preferredMiddle = "", preferredCategoryId = "") => {
    if (!sourceSection) return;
    const dept = sourceSection.querySelector("[data-work-department]");
    const middle = sourceSection.querySelector("[data-work-middle]");
    const small = sourceSection.querySelector("[data-work-category]");
    if (!dept || !middle || !small) return;
    if (!isAdmin() && currentDepartmentId()) dept.value = currentDepartmentId();
    const rows = readCatalog().filter((row) => String(row.department_id) === String(dept.value || currentDepartmentId()));
    const names = [...new Set(rows.map((row) => row.middle_name).filter(Boolean))];
    replaceOptions(middle, names.map((name) => ({ value: name, label: name })), "미분류");
    if (preferredMiddle && names.includes(preferredMiddle)) middle.value = preferredMiddle;
    const smallRows = rows.filter((row) => row.middle_name === middle.value);
    replaceOptions(small, smallRows.map((row) => ({ value: row.id, label: row.small_name || "소분류 없음" })), "미분류");
    if (preferredCategoryId && [...small.options].some((option) => option.value === String(preferredCategoryId))) {
      small.value = String(preferredCategoryId);
    }
  };

  const applyOperationUi = (dialog) => {
    const op = dialog.querySelector("[data-v17-operation]")?.value || "small_add";
    const middleWrap = dialog.querySelector("[data-v17-middle-wrap]");
    const smallWrap = dialog.querySelector("[data-v17-small-wrap]");
    const newLabel = dialog.querySelector("[data-v17-new-label]");
    const newInput = dialog.querySelector("[data-v17-new-name]");
    const help = dialog.querySelector("[data-v17-help]");
    const taskTypeBox = dialog.querySelector("[data-v17-task-type-box]");

    middleWrap.hidden = op === "middle_add";
    smallWrap.hidden = op !== "small_rename";
    taskTypeBox.hidden = !["middle_add", "small_add"].includes(op);

    if (op === "middle_add") {
      newLabel.textContent = "새 중분류명";
      newInput.maxLength = 100;
      help.textContent = "새 중분류명을 입력하세요.";
    } else if (op === "small_add") {
      newLabel.textContent = "새 소분류명";
      newInput.maxLength = 150;
      help.textContent = "저장된 중분류를 선택한 뒤 새 소분류명만 입력하세요.";
    } else if (op === "middle_rename") {
      newLabel.textContent = "새 중분류명";
      newInput.maxLength = 100;
      help.textContent = "수정할 중분류를 선택하고 변경할 이름을 입력하세요.";
    } else {
      newLabel.textContent = "새 소분류명";
      newInput.maxLength = 150;
      help.textContent = "중분류와 수정할 소분류를 선택하고 변경할 이름을 입력하세요.";
    }
    setStatus(dialog, "");
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
    try { finalUrl = new URL(response.url || window.location.href, window.location.origin); }
    catch (_error) { finalUrl = new URL(window.location.href); }
    const flash = doc.querySelector(".flash-stack .flash, .flash");
    const message = flash?.textContent?.trim() || "";
    const resultTone = finalUrl.searchParams.get("category_result") || "";
    const categoryId = finalUrl.searchParams.get("category_id") || "";
    const category = categoryId ? categories.find((row) => String(row.id) === String(categoryId)) || null : null;
    const taskValidation = /업무\s*분류를 하나 이상 선택/.test(message);
    const ok = !taskValidation && (resultTone ? resultTone !== "error" : !doc.querySelector(".flash.error"));
    return {
      ok,
      message: taskValidation
        ? "업무구분 저장 요청이 기존 업무등록 검증으로 잘못 처리되었습니다. 화면을 새로고침한 뒤 다시 시도해 주세요."
        : (message || (ok ? "업무구분을 저장했습니다." : "업무구분 저장 중 오류가 발생했습니다.")),
      categories,
      category,
    };
  };

  const saveCategory = async (action, values) => {
    const data = new FormData();
    data.set("csrf_token", csrfToken());
    data.set("category_action", action);
    Object.entries(values).forEach(([key, value]) => data.set(key, value ?? ""));
    const response = await fetch(
      `${SAVE_URL}?category_manager=1&category_transport=v9&category_action=${encodeURIComponent(action)}`,
      {
        method: "POST",
        body: data,
        credentials: "same-origin",
        redirect: "follow",
        headers: {
          Accept: "application/json",
          "X-Requested-With": "XMLHttpRequest",
          "X-MedPark-Category-JSON": "1",
        },
      },
    );
    if (response.url.includes("/login")) {
      window.location.assign(response.url);
      throw new Error("로그인이 필요합니다.");
    }
    const contentType = (response.headers.get("content-type") || "").toLowerCase();
    let result;
    if (contentType.includes("application/json")) result = await response.json().catch(() => ({}));
    else result = await parseHtmlResult(response);
    if (!response.ok && result.ok !== true) throw new Error(result.message || `업무구분 처리 실패 (HTTP ${response.status})`);
    if (!result.ok) throw new Error(result.message || "업무구분 저장에 실패했습니다.");
    if (Array.isArray(result.categories)) writeCatalog(result.categories);
    return result;
  };

  const ensureStyles = () => {
    if (document.getElementById("task-category-v17-style")) return;
    const style = document.createElement("style");
    style.id = "task-category-v17-style";
    style.textContent = `
      .task-category-v17{width:min(940px,calc(100vw - 28px));max-height:92vh;border:0;border-radius:16px;padding:0;overflow:hidden;background:#f8fafc;box-shadow:0 24px 60px rgba(15,23,42,.24)}
      .task-category-v17::backdrop{background:rgba(15,23,42,.52)}
      .v17-shell{display:flex;flex-direction:column;max-height:92vh}.v17-head{display:flex;justify-content:space-between;gap:14px;padding:20px 22px;background:#fff;border-bottom:1px solid #e2e8f0}.v17-head h2{margin:4px 0 3px;font-size:23px}.v17-head p{margin:0;color:#64748b}.v17-close{border:0;background:transparent;font-size:30px;line-height:1;color:#64748b;cursor:pointer}.v17-body{overflow:auto;padding:18px 20px 24px}
      .v17-context{display:flex;align-items:center;gap:10px;margin-bottom:14px;padding:11px 13px;border:1px solid #dbe4ef;border-radius:10px;background:#fff}.v17-form{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:16px;border:1px solid #dbe4ef;border-radius:12px;background:#fff}.v17-form label{display:grid;gap:6px;font-weight:700}.v17-form select,.v17-form input[type=text]{width:100%;padding:10px 11px;border:1px solid #cbd5e1;border-radius:8px;background:#fff;font:inherit}.v17-span-2{grid-column:1/-1}.v17-task-types{display:flex;flex-wrap:wrap;gap:8px}.v17-task-type{display:inline-flex!important;grid-template-columns:auto 1fr!important;align-items:center;gap:6px!important;padding:8px 10px;border:1px solid #cbd5e1;border-radius:8px;background:#fff;cursor:pointer}.v17-task-type input{margin:0}.v17-help{margin:0;color:#64748b;font-size:12px}.task-category-operation-status{min-height:20px;margin:0;font-size:13px}.task-category-operation-status.success{color:#067647}.task-category-operation-status.error{color:#b42318}.v17-actions{display:flex;justify-content:flex-end}.v17-current{margin-top:16px;border:1px solid #dbe4ef;border-radius:12px;background:#fff;overflow:hidden}.v17-current-head{display:flex;justify-content:space-between;align-items:center;padding:13px 15px;border-bottom:1px solid #e2e8f0}.v17-current-head p{margin:0;color:#64748b;font-size:13px}.task-category-current-table{width:100%;border-collapse:collapse}.task-category-current-table th,.task-category-current-table td{padding:10px 11px;border-bottom:1px solid #eef2f6;text-align:left}.task-category-current-table th{background:#f8fafc;color:#475569;font-size:12px}
      @media(max-width:760px){.task-category-v17{width:calc(100vw - 14px);max-height:96vh}.v17-body{padding:10px}.v17-form{grid-template-columns:1fr}.v17-span-2{grid-column:1}}
    `;
    document.head.append(style);
  };

  const ensureDialog = () => {
    let dialog = document.getElementById(DIALOG_ID);
    if (dialog) return dialog;
    ensureStyles();
    dialog = document.createElement("dialog");
    dialog.id = DIALOG_ID;
    dialog.className = "task-category-v17";
    dialog.innerHTML = `
      <div class="v17-shell">
        <div class="v17-head"><div><span class="eyebrow">WORK CATEGORY</span><h2>중분류·소분류 등록·수정</h2><p>기존 분류는 선택하고, 새 이름만 입력합니다.</p></div><button type="button" class="v17-close" aria-label="닫기">×</button></div>
        <div class="v17-body">
          <div class="v17-context"><strong>대분류 (부서·팀)</strong><span data-v17-dept-name>-</span></div>
          <form class="v17-form" data-v17-form>
            <label class="v17-span-2">작업 선택<select data-v17-operation><option value="small_add">기존 중분류에 소분류 추가</option><option value="middle_add">중분류 신규 등록</option><option value="middle_rename">기존 중분류 수정</option><option value="small_rename">기존 소분류 수정</option></select></label>
            <label data-v17-middle-wrap>기존 중분류<select data-v17-middle><option value="">중분류 선택</option></select></label>
            <label data-v17-small-wrap hidden>기존 소분류<select data-v17-small><option value="">소분류 선택</option></select></label>
            <label><span data-v17-new-label>새 소분류명</span><input type="text" data-v17-new-name maxlength="150" autocomplete="off"></label>
            <div class="v17-span-2" data-v17-task-type-box><strong>업무분류 <small style="font-weight:400;color:#64748b">(현재 등록할 업무에 반영)</small></strong><div class="v17-task-types" data-v17-task-types></div><small style="color:#64748b">선택한 업무분류는 단건 업무등록 화면에 그대로 반영됩니다.</small></div>
            <p class="v17-span-2 v17-help" data-v17-help></p>
            <p class="v17-span-2 task-category-operation-status" data-v17-status role="status" aria-live="polite"></p>
            <div class="v17-span-2 v17-actions"><button class="button primary" type="submit">저장</button></div>
          </form>
          <section class="v17-current"><div class="v17-current-head"><div><strong>현재 등록된 업무구분</strong><p>저장된 중·소분류를 확인합니다.</p></div><strong data-v17-count>0건</strong></div><div data-v17-list></div></section>
        </div>
      </div>`;
    document.body.append(dialog);

    dialog.querySelector(".v17-close").addEventListener("click", () => dialog.close());
    dialog.addEventListener("click", (event) => { if (event.target === dialog) dialog.close(); });
    dialog.addEventListener("cancel", (event) => { event.preventDefault(); dialog.close(); });
    dialog.querySelector("[data-v17-operation]").addEventListener("change", () => applyOperationUi(dialog));
    dialog.querySelector("[data-v17-middle]").addEventListener("change", () => refreshSelectors(dialog, dialog.querySelector("[data-v17-middle]").value));
    dialog.querySelector("[data-v17-form]").addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const op = dialog.querySelector("[data-v17-operation]").value;
      const middle = dialog.querySelector("[data-v17-middle]").value;
      const smallId = dialog.querySelector("[data-v17-small]").value;
      const newName = dialog.querySelector("[data-v17-new-name]").value.trim();
      const deptId = departmentId();

      if (!deptId) return setStatus(dialog, "대분류(부서·팀)를 확인해 주세요.", "error");
      if (op !== "middle_add" && !middle) return setStatus(dialog, "기존 중분류를 선택해 주세요.", "error");
      if (op === "small_rename" && !smallId) return setStatus(dialog, "기존 소분류를 선택해 주세요.", "error");
      if (!newName) return setStatus(dialog, "새 이름을 입력해 주세요.", "error");

      // 업무분류는 분류 마스터의 필수값이 아니라 현재 등록 업무의 속성입니다.
      // 선택값이 있으면 단건 업무등록 폼에 동기화하되, 분류 생성 자체를 막지는 않습니다.
      syncTaskTypesToSource(dialog);

      let action = "";
      let values = { department_id: deptId };
      if (op === "middle_add") { action = "add"; values = { ...values, middle_name: newName, small_name: "" }; }
      else if (op === "small_add") { action = "add"; values = { ...values, middle_name: middle, small_name: newName }; }
      else if (op === "middle_rename") { action = "rename_middle"; values = { ...values, old_middle_name: middle, new_middle_name: newName }; }
      else if (op === "small_rename") { action = "rename_small"; values = { ...values, work_category_id: smallId, new_small_name: newName }; }

      const submit = form.querySelector('button[type="submit"]');
      submit.disabled = true;
      setStatus(dialog, "저장 중입니다...");
      try {
        const result = await saveCategory(action, values);
        const preferredMiddle = op === "middle_add" || op === "middle_rename" ? newName : middle;
        const preferredSmallId = result.category?.id || (op === "small_rename" ? smallId : "");
        refreshSourceSection(preferredMiddle, preferredSmallId);
        refreshSelectors(dialog, preferredMiddle, preferredSmallId);
        renderCurrent(dialog);
        dialog.querySelector("[data-v17-new-name]").value = "";
        setStatus(dialog, result.message || "업무구분을 저장했습니다.", "success");
      } catch (error) {
        setStatus(dialog, String(error.message || error), "error");
      } finally {
        submit.disabled = false;
      }
    });
    return dialog;
  };

  const openDialogFor = (section) => {
    sourceSection = section;
    const dialog = ensureDialog();
    dialog.querySelector("[data-v17-dept-name]").textContent = departmentName();
    dialog.querySelector("[data-v17-operation]").value = "small_add";
    dialog.querySelector("[data-v17-new-name]").value = "";
    renderTaskTypes(dialog);
    refreshSelectors(dialog, sourceSection.querySelector("[data-work-middle]")?.value || "");
    renderCurrent(dialog);
    applyOperationUi(dialog);
    if (!dialog.open) dialog.showModal();
  };

  // Capture phase: this is intentionally earlier than legacy bubble handlers in task_editor_modal.js.
  document.addEventListener("click", (event) => {
    const button = event.target.closest(".task-category-tools button");
    if (!button) return;
    const section = button.closest("[data-work-category-form]");
    if (!section) return;
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    openDialogFor(section);
  }, true);

  window.__MEDPARK_CATEGORY_MANAGER__ = "v17-unified";
})();
