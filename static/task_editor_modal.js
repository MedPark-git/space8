(() => {
  const CREATE_PATH = "/tasks/new";
  const EDIT_PATH_RE = /^\/tasks\/\d+\/edit\/?$/;
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
    source.textContent = JSON.stringify(catalog || []);
  };

  const ensureStyles = () => {
    if (document.getElementById("task-editor-modal-style")) return;
    const style = document.createElement("style");
    style.id = "task-editor-modal-style";
    style.textContent = `
      .task-registration-choice{margin:14px 0 18px;padding:16px;border:1px solid #dbe4ef;border-radius:14px;background:#fff;display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap}
      .task-registration-choice-copy{display:flex;align-items:center;gap:12px;min-width:240px}.task-registration-choice-icon{width:46px;height:46px;border-radius:12px;display:grid;place-items:center;background:#eff6ff;color:#1d4ed8}.task-registration-choice-icon svg{width:24px;height:24px;fill:none;stroke:currentColor;stroke-width:1.8}.task-registration-choice-copy strong{display:block;font-size:16px}.task-registration-choice-copy small{display:block;margin-top:3px;color:#64748b}
      .task-editor-modal{width:min(1080px,calc(100vw - 28px));max-height:94vh;border:0;border-radius:16px;padding:0;overflow:hidden;background:#f5f7fb;box-shadow:0 24px 60px rgba(15,23,42,.24)}
      .task-editor-modal::backdrop,.task-category-manager::backdrop{background:rgba(15,23,42,.52)}
      .task-editor-modal-shell{display:flex;flex-direction:column;max-height:94vh}.task-editor-modal-head{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;padding:20px 24px;background:#fff;border-bottom:1px solid #e2e8f0}.task-editor-modal-head h2{margin:4px 0 2px;font-size:24px;line-height:1.25}.task-editor-modal-head p{margin:0;color:#64748b;font-size:13px}.task-editor-modal-close{border:0;background:transparent;color:#64748b;font-size:30px;line-height:1;cursor:pointer;padding:0 2px}.task-editor-modal-body{overflow:auto;padding:20px}.task-editor-modal-loading,.task-editor-modal-error{padding:38px 20px;text-align:center;background:#fff;border:1px solid #e2e8f0;border-radius:12px}.task-editor-modal-error strong{display:block;margin-bottom:8px;color:#b42318}.task-editor-modal-error p{margin:0 0 14px;color:#64748b}.task-editor-modal .form-panel{margin:0;box-shadow:none}.task-editor-modal .form-panel>.form-section:first-child{margin-top:0}.task-editor-modal-status{display:none;margin:0 0 14px;padding:10px 12px;border-radius:9px;font-size:13px}.task-editor-modal-status.error{display:block;background:#fff1f0;color:#b42318;border:1px solid #fecdca}.task-editor-modal-status.info{display:block;background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe}.task-editor-modal .form-actions{position:sticky;bottom:-20px;background:#fff;padding:14px 0 2px;margin-top:18px;border-top:1px solid #e2e8f0;z-index:2}
      .task-category-tools{grid-column:1/-1;display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;margin:2px 0 8px;padding:10px 12px;border:1px dashed #cbd5e1;border-radius:10px;background:#f8fafc}.task-category-tools span{display:flex;align-items:center;gap:8px;font-weight:700}.task-category-tools svg{width:18px;height:18px;fill:none;stroke:currentColor;stroke-width:1.8}
      .task-category-manager{width:min(900px,calc(100vw - 28px));max-height:92vh;border:0;border-radius:16px;padding:0;overflow:hidden;background:#f8fafc}.task-category-manager-shell{display:flex;flex-direction:column;max-height:92vh}.task-category-manager-head{display:flex;justify-content:space-between;gap:14px;padding:20px 22px;background:#fff;border-bottom:1px solid #e2e8f0}.task-category-manager-head h2{margin:4px 0 3px;font-size:23px}.task-category-manager-head p{margin:0;color:#64748b}.task-category-manager-close{border:0;background:transparent;font-size:28px;line-height:1;color:#64748b;cursor:pointer}.task-category-manager-body{overflow:auto;padding:18px 20px 24px}.task-category-context{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:14px;padding:11px 13px;border:1px solid #dbe4ef;border-radius:10px;background:#fff}.task-category-context span{color:#64748b}.task-category-create-box{display:grid;grid-template-columns:minmax(180px,1fr) minmax(180px,1fr) auto;gap:10px;align-items:end;padding:15px;border:1px solid #dbe4ef;border-radius:12px;background:#fff;margin-bottom:16px}.task-category-create-box label{display:grid;gap:6px;font-weight:700}.task-category-create-box input{width:100%;padding:10px 11px;border:1px solid #cbd5e1;border-radius:8px;font:inherit}.task-category-create-help{grid-column:1/-1;color:#64748b;font-size:12px}.task-category-manager-status{grid-column:1/-1;min-height:20px;margin:0;font-size:13px}.task-category-manager-status.success{color:#067647}.task-category-manager-status.error{color:#b42318}.task-category-list-box{border:1px solid #dbe4ef;border-radius:12px;background:#fff;overflow:hidden}.task-category-list-head{display:flex;justify-content:space-between;gap:10px;align-items:center;padding:13px 15px;border-bottom:1px solid #e2e8f0}.task-category-list-head p{margin:0;color:#64748b;font-size:13px}.task-category-table{width:100%;border-collapse:collapse}.task-category-table th,.task-category-table td{padding:10px 11px;border-bottom:1px solid #eef2f6;text-align:left;vertical-align:middle}.task-category-table th{background:#f8fafc;color:#475569;font-size:12px}.task-category-table .button-row{display:flex;gap:6px;flex-wrap:wrap}.task-category-empty{padding:28px;text-align:center;color:#94a3b8}.permission-muted{color:#94a3b8}
      @media(max-width:760px){.task-editor-modal,.task-category-manager{width:calc(100vw - 14px);max-height:96vh}.task-editor-modal-head,.task-category-manager-head{padding:16px}.task-editor-modal-body,.task-category-manager-body{padding:10px}.task-editor-modal .form-grid{grid-template-columns:1fr}.task-editor-modal .span-2{grid-column:auto}.task-category-create-box{grid-template-columns:1fr}.task-category-create-help,.task-category-manager-status{grid-column:1}.task-category-table{min-width:680px}.task-category-list-box{overflow:auto}}
    `;
    document.head.append(style);
  };

  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

  const ensureEditorDialog = () => {
    let dialog = document.getElementById("task-editor-modal");
    if (dialog) return dialog;
    dialog = document.createElement("dialog");
    dialog.id = "task-editor-modal";
    dialog.className = "task-editor-modal";
    dialog.innerHTML = `
      <div class="task-editor-modal-shell">
        <div class="task-editor-modal-head">
          <div><span class="eyebrow">TASK EDITOR</span><h2 data-task-editor-title>업무 등록</h2><p>단건 업무를 현재 화면에서 등록·수정합니다.</p></div>
          <button type="button" class="task-editor-modal-close" aria-label="닫기">×</button>
        </div>
        <div class="task-editor-modal-body"><div class="task-editor-modal-status" data-task-editor-status></div><div data-task-editor-content></div></div>
      </div>`;
    document.body.append(dialog);
    dialog.querySelector(".task-editor-modal-close")?.addEventListener("click", () => dialog.close());
    dialog.addEventListener("click", (event) => { if (event.target === dialog) dialog.close(); });
    dialog.addEventListener("cancel", (event) => { event.preventDefault(); dialog.close(); });
    return dialog;
  };

  const setEditorStatus = (dialog, message = "", tone = "") => {
    const status = dialog.querySelector("[data-task-editor-status]");
    if (!status) return;
    status.textContent = message;
    status.className = "task-editor-modal-status";
    if (tone) status.classList.add(tone);
  };

  const rebuildCategorySection = (section, preferredMiddle = "", preferredCategoryId = "") => {
    if (!section) return;
    const catalog = readCatalog();
    const department = section.querySelector("[data-work-department]");
    const middle = section.querySelector("[data-work-middle]");
    const category = section.querySelector("[data-work-category]");
    if (!department || !middle || !category) return;

    if (!isAdmin() && currentDepartmentId()) department.value = currentDepartmentId();
    const deptCategories = catalog.filter((item) => String(item.department_id) === String(department.value || ""));
    const currentMiddle = preferredMiddle || middle.value || "";
    const middleNames = [...new Set(deptCategories.map((item) => item.middle_name))];
    middle.replaceChildren(new Option("미분류", ""));
    middleNames.forEach((name) => middle.append(new Option(name, name)));
    if (middleNames.includes(currentMiddle)) middle.value = currentMiddle;

    const currentCategory = preferredCategoryId || category.value || "";
    const smallItems = deptCategories.filter((item) => item.middle_name === middle.value);
    category.replaceChildren(new Option("미분류", ""));
    smallItems.forEach((item) => category.append(new Option(item.small_name || "소분류 없음", String(item.id))));
    if ([...category.options].some((option) => option.value === String(currentCategory))) {
      category.value = String(currentCategory);
    } else if (middle.value) {
      const placeholder = smallItems.find((item) => !String(item.small_name || "").trim());
      if (placeholder) category.value = String(placeholder.id);
    }
  };

  const bindFreshCategorySelectors = (section) => {
    if (!section || section.dataset.freshCategoryBound) return;
    section.dataset.freshCategoryBound = "true";
    const department = section.querySelector("[data-work-department]");
    const middle = section.querySelector("[data-work-middle]");
    department?.addEventListener("change", () => window.setTimeout(() => rebuildCategorySection(section), 0));
    middle?.addEventListener("change", () => window.setTimeout(() => rebuildCategorySection(section, middle.value), 0));
  };

  let activeCategorySection = null;

  const postCategoryAction = async (action, values) => {
    const data = new FormData();
    data.set("csrf_token", csrfToken());
    data.set("category_action", action);
    Object.entries(values || {}).forEach(([key, value]) => data.set(key, value ?? ""));
    const response = await fetch(CREATE_PATH, {
      method: "POST",
      body: data,
      credentials: "same-origin",
      headers: { Accept: "application/json", "X-Requested-With": "XMLHttpRequest" },
    });
    const contentType = response.headers.get("content-type") || "";
    const result = contentType.includes("application/json") ? await response.json().catch(() => ({})) : {};
    if (!response.ok || !result.ok) throw new Error(result.message || `업무구분 처리 실패 (HTTP ${response.status})`);
    if (Array.isArray(result.categories)) writeCatalog(result.categories);
    return result;
  };

  const ensureCategoryManager = () => {
    let dialog = document.getElementById("task-category-manager");
    if (dialog) return dialog;
    dialog = document.createElement("dialog");
    dialog.id = "task-category-manager";
    dialog.className = "task-category-manager";
    dialog.innerHTML = `
      <div class="task-category-manager-shell">
        <div class="task-category-manager-head">
          <div><span class="eyebrow">WORK CATEGORY</span><h2>중분류·소분류 등록·수정</h2><p>임직원은 본인 부서(팀)의 업무구분을 등록·수정할 수 있습니다.</p></div>
          <button type="button" class="task-category-manager-close" aria-label="닫기">×</button>
        </div>
        <div class="task-category-manager-body">
          <div class="task-category-context"><strong>대분류 (부서·팀)</strong><span data-category-department-name>-</span></div>
          <form class="task-category-create-box" data-category-create-form>
            <label>중분류<input name="middle_name" maxlength="100" required placeholder="예: 정보화기기"></label>
            <label>소분류<input name="small_name" maxlength="150" placeholder="비워두면 중분류만 등록"></label>
            <button class="button primary" type="submit">등록</button>
            <small class="task-category-create-help">중분류만 등록하려면 소분류를 비워두세요. 기존 중분류에 소분류를 추가할 때는 중분류명을 그대로 입력하고 새 소분류명을 입력합니다.</small>
            <p class="task-category-manager-status" role="status" aria-live="polite"></p>
          </form>
          <section class="task-category-list-box">
            <div class="task-category-list-head"><div><strong>등록된 업무구분</strong><p>조회·등록·수정만 가능합니다. 삭제·미사용 전환은 제공하지 않습니다.</p></div><strong data-category-count>0건</strong></div>
            <div data-category-list></div>
          </section>
        </div>
      </div>`;
    document.body.append(dialog);

    const status = dialog.querySelector(".task-category-manager-status");
    const createForm = dialog.querySelector("[data-category-create-form]");
    const middleInput = createForm.querySelector("input[name='middle_name']");
    const smallInput = createForm.querySelector("input[name='small_name']");
    const list = dialog.querySelector("[data-category-list]");
    const count = dialog.querySelector("[data-category-count]");
    const departmentName = dialog.querySelector("[data-category-department-name]");

    const getDepartmentId = () => {
      const sectionDepartment = activeCategorySection?.querySelector("[data-work-department]");
      if (!isAdmin()) return currentDepartmentId();
      return sectionDepartment?.value || currentDepartmentId();
    };

    const setStatus = (message = "", tone = "") => {
      status.textContent = message;
      status.className = "task-category-manager-status";
      if (tone) status.classList.add(tone);
    };

    const getDepartmentName = () => {
      const sectionDepartment = activeCategorySection?.querySelector("[data-work-department]");
      if (!isAdmin()) {
        const option = [...(sectionDepartment?.options || [])].find((item) => String(item.value) === String(currentDepartmentId()));
        return option?.textContent?.trim() || "본인 소속 부서(팀)";
      }
      return sectionDepartment?.selectedOptions?.[0]?.textContent?.trim() || "-";
    };

    const render = () => {
      const departmentId = getDepartmentId();
      departmentName.textContent = getDepartmentName();
      const categories = readCatalog().filter((item) => String(item.department_id) === String(departmentId));
      count.textContent = `${categories.length}건`;
      if (!categories.length) {
        list.innerHTML = '<div class="task-category-empty">등록된 업무구분이 없습니다.</div>';
        return;
      }
      const groups = new Map();
      categories.forEach((item) => {
        if (!groups.has(item.middle_name)) groups.set(item.middle_name, []);
        groups.get(item.middle_name).push(item);
      });
      const rows = [];
      [...groups.entries()].forEach(([middleName, items]) => {
        items.forEach((item, index) => {
          rows.push(`<tr>
            <td>${index === 0 ? `<strong>${escapeHtml(middleName)}</strong>` : '<span class="permission-muted">↳</span>'}</td>
            <td>${item.small_name ? escapeHtml(item.small_name) : '<span class="permission-muted">미지정</span>'}</td>
            <td><div class="button-row">
              ${index === 0 ? `<button class="button ghost small" type="button" data-category-action="rename-middle" data-middle="${escapeHtml(middleName)}">중분류 수정</button><button class="button ghost small" type="button" data-category-action="add-small" data-middle="${escapeHtml(middleName)}">소분류 추가</button>` : ""}
              ${item.small_name ? `<button class="button ghost small" type="button" data-category-action="rename-small" data-id="${item.id}" data-small="${escapeHtml(item.small_name)}">소분류 수정</button>` : ""}
            </div></td>
          </tr>`);
        });
      });
      list.innerHTML = `<div class="table-wrap"><table class="task-category-table"><thead><tr><th>중분류</th><th>소분류</th><th>수정</th></tr></thead><tbody>${rows.join("")}</tbody></table></div>`;
    };

    const refreshSection = (preferredMiddle = "", preferredCategoryId = "") => {
      if (!activeCategorySection) return;
      rebuildCategorySection(activeCategorySection, preferredMiddle, preferredCategoryId);
      bindFreshCategorySelectors(activeCategorySection);
    };

    createForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const departmentId = getDepartmentId();
      const middleName = middleInput.value.trim();
      const smallName = smallInput.value.trim();
      if (!departmentId || !middleName) return;
      const submit = createForm.querySelector("button[type='submit']");
      submit.disabled = true;
      setStatus("");
      try {
        const result = await postCategoryAction("add", { department_id: departmentId, middle_name: middleName, small_name: smallName });
        setStatus(result.message || "업무구분을 등록했습니다.", "success");
        middleInput.value = middleName;
        smallInput.value = "";
        render();
        refreshSection(middleName, result.category?.id || "");
      } catch (error) {
        setStatus(error.message, "error");
      } finally {
        submit.disabled = false;
      }
    });

    list.addEventListener("click", async (event) => {
      const button = event.target.closest("[data-category-action]");
      if (!button) return;
      const action = button.dataset.categoryAction;
      const departmentId = getDepartmentId();
      if (action === "add-small") {
        middleInput.value = button.dataset.middle || "";
        smallInput.value = "";
        smallInput.focus();
        createForm.scrollIntoView({ behavior: "smooth", block: "start" });
        setStatus("소분류명을 입력한 뒤 등록을 누르세요.");
        return;
      }
      try {
        if (action === "rename-middle") {
          const oldName = button.dataset.middle || "";
          const newName = window.prompt("새 중분류명을 입력해 주세요.", oldName);
          if (newName === null || !newName.trim() || newName.trim() === oldName) return;
          const result = await postCategoryAction("rename_middle", { department_id: departmentId, old_middle_name: oldName, new_middle_name: newName.trim() });
          setStatus(result.message || "중분류명을 수정했습니다.", "success");
          render();
          refreshSection(newName.trim());
          return;
        }
        if (action === "rename-small") {
          const oldName = button.dataset.small || "";
          const newName = window.prompt("새 소분류명을 입력해 주세요.", oldName);
          if (newName === null || !newName.trim() || newName.trim() === oldName) return;
          const result = await postCategoryAction("rename_small", { work_category_id: button.dataset.id || "", new_small_name: newName.trim() });
          setStatus(result.message || "소분류명을 수정했습니다.", "success");
          render();
          refreshSection();
        }
      } catch (error) {
        setStatus(error.message, "error");
      }
    });

    dialog.querySelector(".task-category-manager-close")?.addEventListener("click", () => dialog.close());
    dialog.addEventListener("click", (event) => { if (event.target === dialog) dialog.close(); });
    dialog.addEventListener("cancel", (event) => { event.preventDefault(); dialog.close(); });
    dialog.openFor = (section) => {
      activeCategorySection = section;
      if (!isAdmin() && currentDepartmentId()) {
        const department = section.querySelector("[data-work-department]");
        if (department) department.value = currentDepartmentId();
      }
      setStatus("");
      render();
      if (!dialog.open) dialog.showModal();
    };
    dialog.renderCurrent = render;
    return dialog;
  };

  const prepareCategoryTools = (root = document) => {
    root.querySelectorAll("[data-work-category-form]").forEach((section) => {
      bindFreshCategorySelectors(section);
      if (section.dataset.categoryManagerBound) return;
      section.dataset.categoryManagerBound = "true";
      const tools = document.createElement("div");
      tools.className = "task-category-tools";
      tools.innerHTML = `<span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M7 4v6M12 4v6M17 4v6M5 14h6M5 18h10"/></svg>업무구분 기초자료</span>`;
      const button = document.createElement("button");
      button.type = "button";
      button.className = "button ghost small";
      button.textContent = "중·소분류 등록·수정";
      button.addEventListener("click", () => ensureCategoryManager().openFor(section));
      tools.append(button);
      section.prepend(tools);
    });
  };

  const prepareForm = (form, endpoint) => {
    form.dataset.taskEditorEndpoint = endpoint;
    const formGrid = form.querySelector(".form-grid");
    const categoryBlock = formGrid?.querySelector(".work-category-form");
    const titleInput = formGrid?.querySelector("input[name='title']");
    const titleLabel = titleInput?.closest("label");
    if (formGrid && categoryBlock && titleLabel) formGrid.insertBefore(categoryBlock, titleLabel);
    if (titleLabel) {
      titleLabel.childNodes.forEach((node) => {
        if (node.nodeType === Node.TEXT_NODE && node.nodeValue.includes("업무 제목")) node.nodeValue = node.nodeValue.replace("업무 제목", "업무명");
      });
    }
    const cancelLink = form.querySelector(".form-actions a.button");
    if (cancelLink) {
      const cancelButton = document.createElement("button");
      cancelButton.type = "button";
      cancelButton.className = cancelLink.className;
      cancelButton.textContent = "취소";
      cancelButton.dataset.taskEditorCancel = "1";
      cancelLink.replaceWith(cancelButton);
    }
    if (typeof initWorkCategoryForm === "function") initWorkCategoryForm(form);
    prepareCategoryTools(form);
  };

  const renderReturnedForm = (dialog, html, endpoint) => {
    const sourceDoc = new DOMParser().parseFromString(html, "text/html");
    const incomingCatalog = sourceDoc.getElementById("work-category-catalog");
    if (incomingCatalog) {
      try { writeCatalog(JSON.parse(incomingCatalog.textContent || "[]")); } catch (_error) {}
    }
    const nextForm = sourceDoc.querySelector("form.form-panel");
    if (!nextForm) return false;
    const content = dialog.querySelector("[data-task-editor-content]");
    content.replaceChildren(nextForm);
    prepareForm(nextForm, endpoint);
    const flashMessages = [...sourceDoc.querySelectorAll(".flash")].map((node) => node.textContent.trim()).filter(Boolean);
    if (flashMessages.length) setEditorStatus(dialog, flashMessages.join(" · "), "error");
    return true;
  };

  const openEditor = async (href) => {
    ensureStyles();
    const dialog = ensureEditorDialog();
    const content = dialog.querySelector("[data-task-editor-content]");
    const title = dialog.querySelector("[data-task-editor-title]");
    const endpoint = new URL(href, window.location.origin).pathname;
    title.textContent = endpoint === CREATE_PATH ? "업무 등록" : "업무 수정";
    setEditorStatus(dialog, "");
    content.innerHTML = '<div class="task-editor-modal-loading"><p>업무 입력 화면을 불러오는 중입니다.</p></div>';
    if (!dialog.open) dialog.showModal();
    try {
      const response = await fetch(href, { credentials: "same-origin", headers: { "X-Requested-With": "XMLHttpRequest" } });
      if (response.url.includes("/login")) { window.location.assign(response.url); return; }
      if (!response.ok) throw new Error(`업무 입력 화면 조회 실패 (HTTP ${response.status})`);
      const html = await response.text();
      if (!renderReturnedForm(dialog, html, endpoint)) throw new Error("업무 입력 폼을 찾을 수 없습니다.");
    } catch (error) {
      content.innerHTML = `<div class="task-editor-modal-error"><strong>업무 입력 화면을 불러오지 못했습니다.</strong><p>${escapeHtml(error.message || error)}</p><a class="button ghost" href="${href}">기존 화면으로 열기</a></div>`;
    }
  };

  const submitEditor = async (form, dialog) => {
    const endpoint = form.dataset.taskEditorEndpoint || CREATE_PATH;
    const submitButton = form.querySelector("button[type='submit']");
    const originalLabel = submitButton?.textContent || "저장";
    if (submitButton) { submitButton.disabled = true; submitButton.textContent = "저장 중..."; }
    setEditorStatus(dialog, "저장 중입니다.", "info");
    try {
      const response = await fetch(endpoint, { method: "POST", body: new FormData(form), credentials: "same-origin", headers: { "X-Requested-With": "XMLHttpRequest" }, redirect: "follow" });
      if (response.url.includes("/login")) { window.location.assign(response.url); return; }
      const html = await response.text();
      if (response.redirected && response.ok && !response.url.endsWith(endpoint)) { dialog.close(); window.location.reload(); return; }
      if (!response.ok) {
        if (!renderReturnedForm(dialog, html, endpoint)) throw new Error(`저장 실패 (HTTP ${response.status})`);
        setEditorStatus(dialog, `저장 내용을 확인해 주세요. (HTTP ${response.status})`, "error");
        return;
      }
      if (renderReturnedForm(dialog, html, endpoint)) { setEditorStatus(dialog, "입력 내용을 확인해 주세요.", "error"); return; }
      dialog.close();
      window.location.reload();
    } catch (error) {
      setEditorStatus(dialog, String(error.message || error), "error");
    } finally {
      if (submitButton?.isConnected) { submitButton.disabled = false; submitButton.textContent = originalLabel; }
    }
  };

  const addRegistrationChoice = () => {
    if (window.location.pathname !== CREATE_PATH || document.querySelector("[data-task-editor-launch]")) return;
    const form = document.querySelector("form.form-panel");
    if (!form) return;
    const panel = document.createElement("section");
    panel.className = "task-registration-choice";
    panel.innerHTML = `<div class="task-registration-choice-copy"><span class="task-registration-choice-icon"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg></span><div><strong>단건 업무 등록</strong><small>엑셀 일괄등록은 위 화면을 그대로 사용하고, 한 건씩 등록할 때 이 버튼을 선택하세요.</small></div></div><button class="button primary" type="button" data-task-editor-launch>업무 등록</button>`;
    const divider = document.querySelector(".section-divider");
    if (divider) divider.insertAdjacentElement("afterend", panel);
    else form.insertAdjacentElement("beforebegin", panel);
  };

  document.addEventListener("click", (event) => {
    const cancel = event.target.closest("[data-task-editor-cancel]");
    if (cancel) { event.preventDefault(); cancel.closest("dialog")?.close(); return; }

    const launch = event.target.closest("[data-task-editor-launch]");
    if (launch) { event.preventDefault(); openEditor(CREATE_PATH); return; }

    const link = event.target.closest("a[href]");
    if (!link) return;
    let url;
    try { url = new URL(link.href, window.location.origin); } catch (_error) { return; }
    if (url.origin !== window.location.origin || !EDIT_PATH_RE.test(url.pathname)) return;
    if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button === 1) return;
    event.preventDefault();
    openEditor(link.href);
  });

  document.addEventListener("submit", (event) => {
    const form = event.target.closest("#task-editor-modal form.form-panel");
    if (!form) return;
    event.preventDefault();
    submitEditor(form, ensureEditorDialog());
  });

  const init = () => {
    ensureStyles();
    addRegistrationChoice();
    prepareCategoryTools(document);
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
