(() => {
  const CATALOG_ID = "work-category-catalog";
  const currentDepartmentId = () => document.body.dataset.currentDepartmentId || "";
  const currentRole = () => document.body.dataset.currentRole || "";
  const isAdmin = () => {
    const role = currentRole();
    return role === "관리자" || role === "시스템관리자" || role.includes("관리자");
  };

  const readCatalog = () => {
    const source = document.getElementById(CATALOG_ID);
    if (!source) return [];
    try { return JSON.parse(source.textContent || "[]"); } catch (_error) { return []; }
  };

  const writeCatalog = (catalog) => {
    const source = document.getElementById(CATALOG_ID);
    if (source) source.textContent = JSON.stringify(catalog);
  };

  const replaceDepartmentCatalog = (departmentId, categories) => {
    const kept = readCatalog().filter((item) => String(item.department_id) !== String(departmentId));
    writeCatalog([...kept, ...categories]);
  };

  const csrfToken = () => document.querySelector('meta[name="csrf-token"]')?.content || "";

  const apiRequest = async (url, options = {}) => {
    const response = await fetch(url, {
      credentials: "same-origin",
      ...options,
      headers: {
        Accept: "application/json",
        ...(options.body ? { "X-CSRFToken": csrfToken() } : {}),
        ...(options.headers || {}),
      },
    });
    const contentType = response.headers.get("content-type") || "";
    const result = contentType.includes("application/json")
      ? await response.json().catch(() => ({}))
      : { ok: false, message: `서버 응답 오류 (HTTP ${response.status})` };
    if (!response.ok || !result.ok) {
      throw new Error(result.message || `업무구분 처리 실패 (HTTP ${response.status})`);
    }
    return result;
  };

  const ensureStyles = () => {
    if (document.getElementById("task-category-modal-style")) return;
    const style = document.createElement("style");
    style.id = "task-category-modal-style";
    style.textContent = `
      .task-category-basics-link{grid-column:1/-1;display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:2px 0 10px;padding:11px 12px;border:1px solid #dbe4ef;border-radius:10px;background:#f8fafc}
      .task-category-basics-link strong{margin-right:4px}.task-category-basics-link small{color:#64748b;margin-right:auto}.task-category-basics-link .button{white-space:nowrap}
      .task-category-modal{width:min(1000px,calc(100vw - 28px));max-height:92vh;border:0;border-radius:16px;padding:0;overflow:hidden}
      .task-category-modal::backdrop{background:rgba(15,23,42,.48)}
      .task-category-modal-shell{display:flex;flex-direction:column;max-height:92vh;background:#f8fafc}
      .task-category-modal-head{display:flex;justify-content:space-between;align-items:flex-start;gap:14px;padding:20px 22px;background:#fff;border-bottom:1px solid #e2e8f0}
      .task-category-modal-head h2{margin:4px 0 3px;font-size:24px}.task-category-modal-head p{margin:0;color:#64748b}
      .task-category-modal-close{border:0;background:transparent;font-size:28px;line-height:1;color:#64748b;cursor:pointer}
      .task-category-modal-body{overflow:auto;padding:18px 20px 24px}
      .task-category-context{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:14px;padding:11px 13px;border:1px solid #dbe4ef;border-radius:10px;background:#fff}
      .task-category-context span{color:#64748b}.task-category-create-box{display:grid;grid-template-columns:minmax(180px,1fr) minmax(180px,1fr) auto;gap:10px;align-items:end;padding:15px;border:1px solid #dbe4ef;border-radius:12px;background:#fff;margin-bottom:16px}
      .task-category-create-box label{display:grid;gap:6px;font-weight:700}.task-category-create-box input{width:100%;padding:10px 11px;border:1px solid #cbd5e1;border-radius:8px;font:inherit}
      .task-category-create-help{grid-column:1/-1;color:#64748b;font-size:12px}.task-category-modal-status{grid-column:1/-1;min-height:20px;margin:0;font-size:13px}.task-category-modal-status.success{color:#067647}.task-category-modal-status.error{color:#b42318}
      .task-category-list-box{border:1px solid #dbe4ef;border-radius:12px;background:#fff;overflow:hidden}.task-category-list-head{display:flex;justify-content:space-between;gap:10px;align-items:center;padding:13px 15px;border-bottom:1px solid #e2e8f0}.task-category-list-head p{margin:0;color:#64748b;font-size:13px}
      .task-category-table{width:100%;border-collapse:collapse}.task-category-table th,.task-category-table td{padding:10px 11px;border-bottom:1px solid #eef2f6;text-align:left;vertical-align:middle}.task-category-table th{background:#f8fafc;color:#475569;font-size:12px}.task-category-table td small{color:#64748b}.task-category-table .button-row{display:flex;gap:6px;flex-wrap:wrap}
      .task-category-middle-row td{background:#fbfdff}.task-category-empty{padding:28px;text-align:center;color:#94a3b8}
      @media(max-width:760px){.task-category-create-box{grid-template-columns:1fr}.task-category-create-help,.task-category-modal-status{grid-column:1}.task-category-table{min-width:720px}.task-category-list-box{overflow:auto}}
    `;
    document.head.append(style);
  };

  const createModal = (section) => {
    const dialog = document.createElement("dialog");
    dialog.className = "task-category-modal";
    dialog.innerHTML = `
      <div class="task-category-modal-shell">
        <div class="task-category-modal-head">
          <div><span class="eyebrow">WORK CATEGORY BASICS</span><h2>업무구분 등록·수정</h2><p>현재 업무등록 화면에서 중분류·소분류를 바로 관리합니다.</p></div>
          <button type="button" class="task-category-modal-close" aria-label="닫기">×</button>
        </div>
        <div class="task-category-modal-body">
          <div class="task-category-context"><strong>대분류 (부서·팀)</strong><span data-category-department-name>-</span></div>
          <form class="task-category-create-box" data-category-create-form>
            <label>중분류<input name="middle_name" maxlength="100" required placeholder="예: T/F"></label>
            <label>소분류<input name="small_name" maxlength="150" placeholder="미지정 가능"></label>
            <button class="button primary" type="submit">등록</button>
            <small class="task-category-create-help">중분류만 만들려면 소분류를 비워두세요. 기존 중분류에 소분류를 추가하려면 중분류명을 그대로 입력하고 새 소분류명을 입력하세요.</small>
            <p class="task-category-modal-status" role="status" aria-live="polite"></p>
          </form>
          <section class="task-category-list-box">
            <div class="task-category-list-head"><div><strong>등록된 업무구분</strong><p>조회·등록·수정만 가능합니다. 삭제·미사용 전환 기능은 제공하지 않습니다.</p></div><strong data-category-count>0건</strong></div>
            <div data-category-list><div class="task-category-empty">업무구분을 불러오는 중입니다.</div></div>
          </section>
        </div>
      </div>`;

    const department = section.querySelector("[data-work-department]");
    const middle = section.querySelector("[data-work-middle]");
    const small = section.querySelector("[data-work-category]");
    const createForm = dialog.querySelector("[data-category-create-form]");
    const middleInput = createForm.querySelector("input[name='middle_name']");
    const smallInput = createForm.querySelector("input[name='small_name']");
    const status = dialog.querySelector(".task-category-modal-status");
    const list = dialog.querySelector("[data-category-list]");
    const count = dialog.querySelector("[data-category-count]");
    const departmentName = dialog.querySelector("[data-category-department-name]");
    let currentCategories = [];

    const getDepartmentId = () => {
      if (!isAdmin()) return currentDepartmentId();
      return department?.value || currentDepartmentId();
    };

    const setStatus = (message = "", tone = "") => {
      status.textContent = message;
      status.className = "task-category-modal-status";
      if (tone) status.classList.add(tone);
    };

    const selectedDepartmentName = () => {
      if (!isAdmin()) {
        const option = [...(department?.options || [])].find((item) => String(item.value) === String(currentDepartmentId()));
        return option?.textContent?.trim() || "소속 부서(팀)";
      }
      return department?.selectedOptions?.[0]?.textContent?.trim() || "-";
    };

    const refreshSelectors = (preferredMiddle = "", preferredCategoryId = "") => {
      if (!department || !middle || !small) return;
      if (!isAdmin() && currentDepartmentId()) department.value = currentDepartmentId();
      department.dispatchEvent(new Event("change", { bubbles: true }));
      if (preferredMiddle) {
        middle.value = preferredMiddle;
        middle.dispatchEvent(new Event("change", { bubbles: true }));
      }
      if (preferredCategoryId) small.value = String(preferredCategoryId);
    };

    const syncCatalog = (departmentId, categories) => {
      replaceDepartmentCatalog(departmentId, categories.map((item) => ({
        id: item.id,
        department_id: item.department_id,
        department_name: item.department_name,
        middle_name: item.middle_name,
        small_name: item.small_name || "",
      })));
    };

    const renderList = () => {
      count.textContent = `${currentCategories.length}건`;
      if (!currentCategories.length) {
        list.innerHTML = '<div class="task-category-empty">등록된 업무구분이 없습니다.</div>';
        return;
      }
      const groups = new Map();
      currentCategories.forEach((item) => {
        if (!groups.has(item.middle_name)) groups.set(item.middle_name, []);
        groups.get(item.middle_name).push(item);
      });
      const rows = [];
      [...groups.entries()].forEach(([middleName, items]) => {
        items.forEach((item, index) => {
          rows.push(`<tr class="${index === 0 ? "task-category-middle-row" : ""}">
            <td>${index === 0 ? `<strong>${escapeHtml(middleName)}</strong>` : '<span class="permission-muted">↳</span>'}</td>
            <td>${item.small_name ? escapeHtml(item.small_name) : '<span class="permission-muted">미지정</span>'}</td>
            <td>${Number(item.task_count || 0)}건</td>
            <td><div class="button-row">
              ${index === 0 ? `<button class="button ghost small" type="button" data-category-action="rename-middle" data-middle="${escapeAttr(middleName)}">중분류 수정</button><button class="button ghost small" type="button" data-category-action="add-small" data-middle="${escapeAttr(middleName)}">소분류 추가</button>` : ""}
              ${item.small_name ? `<button class="button ghost small" type="button" data-category-action="rename-small" data-id="${item.id}" data-small="${escapeAttr(item.small_name)}">소분류 수정</button>` : ""}
            </div></td>
          </tr>`);
        });
      });
      list.innerHTML = `<div class="table-wrap"><table class="task-category-table"><thead><tr><th>중분류</th><th>소분류</th><th>사용 업무</th><th>수정</th></tr></thead><tbody>${rows.join("")}</tbody></table></div>`;
    };

    const loadCategories = async (preferredMiddle = "", preferredCategoryId = "") => {
      const departmentId = getDepartmentId();
      departmentName.textContent = selectedDepartmentName();
      if (!departmentId) {
        currentCategories = [];
        renderList();
        setStatus("대분류(부서·팀)를 먼저 선택해 주세요.", "error");
        return;
      }
      list.innerHTML = '<div class="task-category-empty">업무구분을 불러오는 중입니다.</div>';
      try {
        const result = await apiRequest(`/tasks/work-categories/list?department_id=${encodeURIComponent(departmentId)}`);
        currentCategories = result.categories || [];
        syncCatalog(departmentId, currentCategories);
        renderList();
        refreshSelectors(preferredMiddle, preferredCategoryId);
      } catch (error) {
        currentCategories = [];
        renderList();
        setStatus(error.message, "error");
      }
    };

    createForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const departmentId = getDepartmentId();
      const middleName = middleInput.value.trim();
      const smallName = smallInput.value.trim();
      if (!departmentId || !middleName) return;
      const data = new FormData();
      data.set("csrf_token", csrfToken());
      data.set("department_id", departmentId);
      data.set("middle_name", middleName);
      data.set("small_name", smallName);
      const submit = createForm.querySelector("button[type='submit']");
      submit.disabled = true;
      setStatus("");
      try {
        const result = await apiRequest("/tasks/work-categories/add", { method: "POST", body: data });
        setStatus(result.message || "업무구분을 등록했습니다.", "success");
        const newId = result.category?.id || "";
        middleInput.value = middleName;
        smallInput.value = "";
        await loadCategories(middleName, newId);
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
      if (action === "rename-middle") {
        const oldName = button.dataset.middle || "";
        const newName = window.prompt("새 중분류명을 입력해 주세요.", oldName);
        if (newName === null || !newName.trim() || newName.trim() === oldName) return;
        const data = new FormData();
        data.set("csrf_token", csrfToken());
        data.set("department_id", departmentId);
        data.set("old_middle_name", oldName);
        data.set("new_middle_name", newName.trim());
        try {
          const result = await apiRequest("/tasks/work-categories/rename-middle", { method: "POST", body: data });
          setStatus(result.message || "중분류명을 수정했습니다.", "success");
          await loadCategories(newName.trim());
        } catch (error) { setStatus(error.message, "error"); }
        return;
      }
      if (action === "rename-small") {
        const oldName = button.dataset.small || "";
        const newName = window.prompt("새 소분류명을 입력해 주세요.", oldName);
        if (newName === null || !newName.trim() || newName.trim() === oldName) return;
        const data = new FormData();
        data.set("csrf_token", csrfToken());
        data.set("work_category_id", button.dataset.id || "");
        data.set("new_small_name", newName.trim());
        try {
          const result = await apiRequest("/tasks/work-categories/rename-small", { method: "POST", body: data });
          setStatus(result.message || "소분류명을 수정했습니다.", "success");
          await loadCategories();
        } catch (error) { setStatus(error.message, "error"); }
      }
    });

    const close = () => dialog.close();
    dialog.querySelector(".task-category-modal-close").addEventListener("click", close);
    dialog.addEventListener("click", (event) => { if (event.target === dialog) close(); });

    dialog.openManager = async () => {
      setStatus("");
      if (!isAdmin() && currentDepartmentId() && department) department.value = currentDepartmentId();
      departmentName.textContent = selectedDepartmentName();
      if (!dialog.open) dialog.showModal();
      await loadCategories(middle?.value || "", small?.value || "");
    };

    department?.addEventListener("change", () => {
      if (dialog.open) loadCategories();
    });

    return dialog;
  };

  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
  const escapeAttr = escapeHtml;

  const init = () => {
    if (window.location.pathname !== "/tasks/new") return;
    const section = document.querySelector(".work-category-form[data-work-category-form]");
    const taskForm = document.querySelector("form.form-panel");
    if (!section || !taskForm || section.dataset.categoryModalBound) return;
    section.dataset.categoryModalBound = "true";
    ensureStyles();

    const department = section.querySelector("[data-work-department]");
    const middle = section.querySelector("[data-work-middle]");
    const small = section.querySelector("[data-work-category]");
    const modal = createModal(section);

    const bar = document.createElement("div");
    bar.className = "task-category-basics-link";
    bar.innerHTML = `<strong>업무구분 기초자료</strong><small>${isAdmin() ? "선택한 부서(팀)의 중분류·소분류를 조회·등록·수정할 수 있습니다." : "본인 부서(팀)의 중분류·소분류를 조회·등록·수정할 수 있습니다."}</small>`;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "button ghost small";
    button.textContent = "업무구분 등록·수정";
    button.addEventListener("click", () => modal.openManager());
    bar.append(button);
    section.prepend(bar);

    const selectMiddlePlaceholder = () => {
      const deptId = department?.value || "";
      const middleName = middle?.value || "";
      if (!deptId || !middleName || !small) return;
      const placeholder = readCatalog().find((item) =>
        String(item.department_id) === String(deptId)
        && item.middle_name === middleName
        && !String(item.small_name || "").trim()
      );
      if (placeholder) {
        const option = [...small.options].find((item) => String(item.value) === String(placeholder.id));
        if (option && !small.value) small.value = String(placeholder.id);
      }
    };

    middle?.addEventListener("change", () => {
      window.setTimeout(selectMiddlePlaceholder, 0);
    });

    taskForm.addEventListener("submit", (event) => {
      if (event.defaultPrevented) return;
      if (middle?.value && !small?.value) selectMiddlePlaceholder();
      if (middle?.value && !small?.value) {
        event.preventDefault();
        window.alert("선택한 중분류에 '소분류 미지정' 기초자료가 없습니다. 업무구분 등록·수정에서 해당 중분류를 소분류 없이 한 번 등록해 주세요.");
      }
    });
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
