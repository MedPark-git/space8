(() => {
  if (window.__MEDPARK_ADMIN_WORK_CATEGORY_V2__) return;
  window.__MEDPARK_ADMIN_WORK_CATEGORY_V2__ = "active";

  const API = "/admin/work-categories/manage";
  const DELETE_API = "/admin/work-categories/delete-v2";
  const csrfToken = () => document.querySelector('meta[name="csrf-token"]')?.content || "";

  const isTargetPage = () => {
    const params = new URLSearchParams(window.location.search);
    return window.location.pathname.endsWith("/admin/work-categories")
      || (window.location.pathname === "/admin" && params.get("section") === "work-categories")
      || [...document.querySelectorAll(".admin-tabs a")].some((a) => a.classList.contains("active") && a.textContent.trim() === "업무구분");
  };

  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

  const icon = (name) => {
    const paths = {
      edit: '<path d="M4 20h4l10.5-10.5a2.1 2.1 0 0 0-3-3L5 17v3Z"/><path d="m13.5 8.5 3 3"/>',
      trash: '<path d="M4 7h16M9 7V4h6v3M7 7l1 13h8l1-13M10 11v5M14 11v5"/>',
      pause: '<path d="M8 5v14M16 5v14"/>',
      restore: '<path d="M4 12a8 8 0 1 0 2.3-5.7L4 8.6M4 4v4.6h4.6"/>',
    };
    return `<svg viewBox="0 0 24 24" aria-hidden="true">${paths[name] || ""}</svg>`;
  };

  const ensureStyles = () => {
    if (document.getElementById("admin-work-category-manager-v2-style")) return;
    const style = document.createElement("style");
    style.id = "admin-work-category-manager-v2-style";
    style.textContent = `
      .awc-original-add{display:none!important}
      .awc-toolbar{display:flex;align-items:center;gap:8px;margin-left:auto}
      .awc-manage-icons{display:flex;align-items:center;gap:7px;flex-wrap:wrap}
      .awc-manage-icons form{margin:0}
      .awc-icon-button{width:34px;height:34px;display:inline-grid;place-items:center;padding:0!important;border-radius:9px!important;background:#fff!important;border:1px solid #d8e0eb!important;cursor:pointer;transition:.15s ease}
      .awc-icon-button svg{width:17px;height:17px;fill:none;stroke:currentColor;stroke-width:1.9;stroke-linecap:round;stroke-linejoin:round}
      .awc-icon-button.edit{color:#2563eb}.awc-icon-button.edit:hover{background:#eff6ff!important;border-color:#93c5fd!important}
      .awc-icon-button.delete{color:#dc2626}.awc-icon-button.delete:hover{background:#fef2f2!important;border-color:#fecaca!important}
      .awc-icon-button.toggle{color:#64748b}.awc-icon-button.toggle:hover{background:#f8fafc!important;border-color:#cbd5e1!important}
      .awc-dialog{width:min(760px,calc(100vw - 28px));max-height:92vh;border:0;border-radius:16px;padding:0;overflow:hidden;background:#f8fafc;box-shadow:0 24px 60px rgba(15,23,42,.24)}
      .awc-dialog::backdrop{background:rgba(15,23,42,.52)}
      .awc-shell{display:flex;flex-direction:column;max-height:92vh}.awc-head{display:flex;justify-content:space-between;gap:14px;padding:20px 22px;background:#fff;border-bottom:1px solid #e2e8f0}.awc-head h2{margin:4px 0 3px;font-size:23px}.awc-head p{margin:0;color:#64748b}.awc-close{border:0;background:transparent;font-size:30px;line-height:1;color:#64748b;cursor:pointer}.awc-body{overflow:auto;padding:18px 20px 24px}
      .awc-tabs{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:14px}.awc-tab{border:1px solid #cbd5e1;background:#fff;border-radius:10px;padding:11px 12px;font-weight:800;cursor:pointer}.awc-tab.active{border-color:#2563eb;background:#eff6ff;color:#1d4ed8}.awc-tab:disabled{opacity:.45;cursor:not-allowed}.awc-panel{display:none}.awc-panel.active{display:block}
      .awc-form{display:grid;gap:12px;padding:16px;border:1px solid #dbe4ef;border-radius:12px;background:#fff}.awc-form label{display:grid;gap:6px;font-weight:700}.awc-form select,.awc-form input{width:100%;padding:10px 11px;border:1px solid #cbd5e1;border-radius:8px;background:#fff;font:inherit}.awc-help{margin:0;color:#64748b;font-size:12px;line-height:1.55}.awc-status{min-height:20px;margin:0;font-size:13px}.awc-status.success{color:#067647}.awc-status.error{color:#b42318}.awc-actions{display:flex;justify-content:flex-end;gap:8px}.awc-summary{padding:12px 14px;margin-bottom:14px;border:1px solid #dbe4ef;border-radius:10px;background:#fff}.awc-summary strong{display:block}.awc-summary small{color:#64748b}
      @media(max-width:720px){.awc-dialog{width:calc(100vw - 14px);max-height:96vh}.awc-body{padding:10px}.awc-manage-icons{gap:4px}}
    `;
    document.head.append(style);
  };

  const parsePage = () => {
    const panels = [...document.querySelectorAll(".panel")];
    const listPanel = panels.find((panel) => panel.querySelector("h2")?.textContent.includes("업무구분 기초자료"));
    const originalAdd = panels.find((panel) => panel.querySelector("h2")?.textContent.trim() === "업무구분 추가");
    if (!listPanel || !originalAdd) return null;

    const deptSelect = originalAdd.querySelector('select[name="department_id"]');
    const departments = [...(deptSelect?.options || [])]
      .filter((o) => o.value)
      .map((o) => ({ id: o.value, name: o.textContent.trim() }));
    const deptByName = new Map(departments.map((item) => [item.name, item.id]));

    const rows = [];
    listPanel.querySelectorAll("tbody tr").forEach((tr) => {
      const categoryId = tr.querySelector('input[name="work_category_id"]')?.value;
      const cells = tr.querySelectorAll("td");
      if (!categoryId || cells.length < 6) return;
      const departmentName = cells[0].textContent.trim();
      const middleName = cells[1].textContent.trim();
      const smallText = cells[2].textContent.trim();
      const smallName = smallText === "미분류" ? "" : smallText;
      const statusText = cells[4].textContent.trim();
      const item = {
        id: categoryId,
        departmentId: deptByName.get(departmentName) || "",
        departmentName,
        middleName,
        smallName,
        active: !statusText.includes("미사용"),
        tr,
      };
      rows.push(item);
    });
    return { listPanel, originalAdd, departments, rows };
  };

  const post = async (url, payload) => {
    const data = new FormData();
    data.set("csrf_token", csrfToken());
    Object.entries(payload).forEach(([key, value]) => data.set(key, value ?? ""));
    const response = await fetch(url, {
      method: "POST",
      body: data,
      credentials: "same-origin",
      headers: { Accept: "application/json", "X-Requested-With": "XMLHttpRequest" },
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok || !result.ok) throw new Error(result.message || `처리 실패 (HTTP ${response.status})`);
    return result;
  };

  const optionHtml = (departments) => departments.map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.name)}<[REDACTED]>`).join("");
  const middleNames = (state, departmentId) => [...new Set(
    state.rows.filter((row) => String(row.departmentId) === String(departmentId)).map((row) => row.middleName).filter(Boolean)
  )].sort((a, b) => a.localeCompare(b, "ko"));

  const setStatus = (dialog, message = "", tone = "") => {
    const node = dialog.querySelector("[data-awc-status]");
    if (!node) return;
    node.textContent = message;
    node.className = "awc-status";
    if (tone) node.classList.add(tone);
  };

  const ensureAddDialog = (state) => {
    let dialog = document.getElementById("awc-add-dialog-v2");
    if (dialog) return dialog;
    dialog = document.createElement("dialog");
    dialog.id = "awc-add-dialog-v2";
    dialog.className = "awc-dialog";
    dialog.innerHTML = `
      <div class="awc-shell">
        <div class="awc-head"><div><span class="eyebrow">WORK CATEGORY</span><h2>업무구분 추가</h2><p>중분류와 소분류를 탭으로 나누어 등록합니다.</p></div><button type="button" class="awc-close" data-awc-close>×</button></div>
        <div class="awc-body">
          <div class="awc-tabs"><button type="button" class="awc-tab active" data-awc-tab="middle">중분류 추가</button><button type="button" class="awc-tab" data-awc-tab="small">소분류 추가</button></div>
          <section class="awc-panel active" data-awc-panel="middle">
            <form class="awc-form" data-awc-add-middle>
              <label>대분류 (부서·팀)<select name="department_id" required><option value="">선택<[REDACTED]>${optionHtml(state.departments)}</select></label>
              <label>새 중분류명<input name="middle_name" maxlength="100" required placeholder="예: 정보화 기기"></label>
              <p class="awc-help">중분류만 먼저 생성합니다. 소분류는 별도 탭에서 기존 중분류를 선택해 추가합니다.</p><p class="awc-status" data-awc-status></p>
              <div class="awc-actions"><button type="button" class="button ghost" data-awc-close>취소</button><button type="submit" class="button primary">중분류 저장</button></div>
            </form>
          </section>
          <section class="awc-panel" data-awc-panel="small">
            <form class="awc-form" data-awc-add-small>
              <label>대분류 (부서·팀)<select name="department_id" required><option value="">선택<[REDACTED]>${optionHtml(state.departments)}</select></label>
              <label>기존 중분류<select name="middle_name" required><option value="">중분류 선택<[REDACTED]></select></label>
              <label>새 소분류명<input name="small_name" maxlength="150" required placeholder="예: 네트워크"></label>
              <p class="awc-help">대분류를 고르면 현재 저장된 중분류만 선택할 수 있습니다.</p><p class="awc-status" data-awc-status></p>
              <div class="awc-actions"><button type="button" class="button ghost" data-awc-close>취소</button><button type="submit" class="button primary">소분류 저장</button></div>
            </form>
          </section>
        </div>
      </div>`;
    document.body.append(dialog);

    const switchTab = (name) => {
      dialog.querySelectorAll("[data-awc-tab]").forEach((button) => button.classList.toggle("active", button.dataset.awcTab === name));
      dialog.querySelectorAll("[data-awc-panel]").forEach((panel) => panel.classList.toggle("active", panel.dataset.awcPanel === name));
      setStatus(dialog, "");
    };
    dialog.querySelectorAll("[data-awc-tab]").forEach((button) => button.addEventListener("click", () => switchTab(button.dataset.awcTab)));
    dialog.querySelectorAll("[data-awc-close]").forEach((button) => button.addEventListener("click", () => dialog.close()));
    dialog.addEventListener("click", (event) => { if (event.target === dialog) dialog.close(); });

    const smallForm = dialog.querySelector("[data-awc-add-small]");
    const smallDept = smallForm.querySelector('select[name="department_id"]');
    const smallMiddle = smallForm.querySelector('select[name="middle_name"]');
    const refreshMiddleOptions = () => {
      const names = middleNames(state, smallDept.value);
      smallMiddle.replaceChildren(new Option("중분류 선택", ""));
      names.forEach((name) => smallMiddle.append(new Option(name, name)));
    };
    smallDept.addEventListener("change", refreshMiddleOptions);

    dialog.querySelector("[data-awc-add-middle]").addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const button = form.querySelector('button[type="submit"]');
      button.disabled = true; setStatus(dialog, "저장 중입니다...");
      try {
        const result = await post(API, { operation: "add_middle", department_id: form.department_id.value, middle_name: form.middle_name.value.trim() });
        setStatus(dialog, result.message, "success"); window.setTimeout(() => window.location.reload(), 300);
      } catch (error) { setStatus(dialog, error.message, "error"); }
      finally { button.disabled = false; }
    });

    smallForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const button = form.querySelector('button[type="submit"]');
      button.disabled = true; setStatus(dialog, "저장 중입니다...");
      try {
        const result = await post(API, { operation: "add_small", department_id: form.department_id.value, middle_name: form.middle_name.value, small_name: form.small_name.value.trim() });
        setStatus(dialog, result.message, "success"); window.setTimeout(() => window.location.reload(), 300);
      } catch (error) { setStatus(dialog, error.message, "error"); }
      finally { button.disabled = false; }
    });

    dialog.openFor = () => {
      dialog.querySelectorAll("form").forEach((form) => form.reset());
      refreshMiddleOptions(); switchTab("middle");
      if (!dialog.open) dialog.showModal();
    };
    return dialog;
  };

  const ensureEditDialog = () => {
    let dialog = document.getElementById("awc-edit-dialog-v2");
    if (dialog) return dialog;
    dialog = document.createElement("dialog");
    dialog.id = "awc-edit-dialog-v2";
    dialog.className = "awc-dialog";
    dialog.innerHTML = `
      <div class="awc-shell">
        <div class="awc-head"><div><span class="eyebrow">WORK CATEGORY</span><h2>업무구분 수정</h2><p>기존 업무 연결 ID는 유지하고 분류명만 변경합니다.</p></div><button type="button" class="awc-close" data-awc-close>×</button></div>
        <div class="awc-body">
          <div class="awc-summary" data-awc-edit-summary></div>
          <div class="awc-tabs"><button type="button" class="awc-tab active" data-awc-edit-tab="middle">중분류 수정</button><button type="button" class="awc-tab" data-awc-edit-tab="small">소분류 수정</button></div>
          <section class="awc-panel active" data-awc-edit-panel="middle"><form class="awc-form" data-awc-rename-middle><input type="hidden" name="department_id"><input type="hidden" name="old_middle_name"><label>현재 중분류<input data-awc-old-middle readonly></label><label>새 중분류명<input name="new_middle_name" maxlength="100" required></label><p class="awc-help">동일 중분류에 속한 모든 소분류에도 함께 반영됩니다.</p><p class="awc-status" data-awc-status></p><div class="awc-actions"><button type="button" class="button ghost" data-awc-close>취소</button><button type="submit" class="button primary">중분류 수정</button></div></form></section>
          <section class="awc-panel" data-awc-edit-panel="small"><form class="awc-form" data-awc-rename-small><input type="hidden" name="work_category_id"><label>현재 소분류<input data-awc-old-small readonly></label><label>새 소분류명<input name="new_small_name" maxlength="150" required></label><p class="awc-help">선택한 소분류 한 건의 이름만 변경합니다.</p><p class="awc-status" data-awc-status></p><div class="awc-actions"><button type="button" class="button ghost" data-awc-close>취소</button><button type="submit" class="button primary">소분류 수정</button></div></form></section>
        </div>
      </div>`;
    document.body.append(dialog);

    let current = null;
    const switchTab = (name) => {
      if (name === "small" && current && !current.smallName) return;
      dialog.querySelectorAll("[data-awc-edit-tab]").forEach((button) => button.classList.toggle("active", button.dataset.awcEditTab === name));
      dialog.querySelectorAll("[data-awc-edit-panel]").forEach((panel) => panel.classList.toggle("active", panel.dataset.awcEditPanel === name));
      setStatus(dialog, "");
    };
    dialog.querySelectorAll("[data-awc-edit-tab]").forEach((button) => button.addEventListener("click", () => switchTab(button.dataset.awcEditTab)));
    dialog.querySelectorAll("[data-awc-close]").forEach((button) => button.addEventListener("click", () => dialog.close()));
    dialog.addEventListener("click", (event) => { if (event.target === dialog) dialog.close(); });

    const middleForm = dialog.querySelector("[data-awc-rename-middle]");
    middleForm.addEventListener("submit", async (event) => {
      event.preventDefault(); const button = middleForm.querySelector('button[type="submit"]'); button.disabled = true; setStatus(dialog, "저장 중입니다...");
      try {
        const result = await post(API, { operation: "rename_middle", department_id: middleForm.department_id.value, old_middle_name: middleForm.old_middle_name.value, new_middle_name: middleForm.new_middle_name.value.trim() });
        setStatus(dialog, result.message, "success"); window.setTimeout(() => window.location.reload(), 300);
      } catch (error) { setStatus(dialog, error.message, "error"); } finally { button.disabled = false; }
    });

    const smallForm = dialog.querySelector("[data-awc-rename-small]");
    smallForm.addEventListener("submit", async (event) => {
      event.preventDefault(); const button = smallForm.querySelector('button[type="submit"]'); button.disabled = true; setStatus(dialog, "저장 중입니다...");
      try {
        const result = await post(API, { operation: "rename_small", work_category_id: smallForm.work_category_id.value, new_small_name: smallForm.new_small_name.value.trim() });
        setStatus(dialog, result.message, "success"); window.setTimeout(() => window.location.reload(), 300);
      } catch (error) { setStatus(dialog, error.message, "error"); } finally { button.disabled = false; }
    });

    dialog.openFor = (item) => {
      current = item;
      dialog.querySelector("[data-awc-edit-summary]").innerHTML = `<strong>${escapeHtml(item.departmentName)} → ${escapeHtml(item.middleName)}${item.smallName ? ` → ${escapeHtml(item.smallName)}` : ""}</strong><small>기존 업무 연결은 유지됩니다.</small>`;
      middleForm.department_id.value = item.departmentId; middleForm.old_middle_name.value = item.middleName; middleForm.querySelector("[data-awc-old-middle]").value = item.middleName; middleForm.new_middle_name.value = item.middleName;
      smallForm.work_category_id.value = item.id; smallForm.querySelector("[data-awc-old-small]").value = item.smallName || "소분류 없음"; smallForm.new_small_name.value = item.smallName || "";
      const smallTab = dialog.querySelector('[data-awc-edit-tab="small"]'); smallTab.disabled = !item.smallName; smallTab.title = item.smallName ? "" : "소분류가 없는 중분류 전용 항목입니다.";
      switchTab("middle"); if (!dialog.open) dialog.showModal();
    };
    return dialog;
  };

  const init = () => {
    if (!isTargetPage()) return;
    ensureStyles();
    const state = parsePage();
    if (!state) return;

    state.originalAdd.classList.add("awc-original-add");
    const head = state.listPanel.querySelector(".panel-head");
    if (head && !head.querySelector("[data-awc-add-button]")) {
      const toolbar = document.createElement("div"); toolbar.className = "awc-toolbar";
      const button = document.createElement("button"); button.type = "button"; button.className = "button primary"; button.dataset.awcAddButton = "1"; button.textContent = "+ 업무구분 추가"; button.addEventListener("click", () => ensureAddDialog(state).openFor());
      toolbar.append(button); head.append(toolbar);
    }

    state.rows.forEach((item) => {
      const cells = item.tr.querySelectorAll("td");
      const manageCell = cells[5];
      if (!manageCell || manageCell.dataset.awcV2Ready === "1") return;
      manageCell.dataset.awcV2Ready = "1";

      const oldToggleForm = manageCell.querySelector("form");
      const wrapper = document.createElement("div"); wrapper.className = "awc-manage-icons";

      const editButton = document.createElement("button"); editButton.type = "button"; editButton.className = "awc-icon-button edit"; editButton.title = "수정"; editButton.setAttribute("aria-label", "업무구분 수정"); editButton.innerHTML = icon("edit"); editButton.addEventListener("click", () => ensureEditDialog().openFor(item));

      const deleteButton = document.createElement("button"); deleteButton.type = "button"; deleteButton.className = "awc-icon-button delete"; deleteButton.title = "삭제"; deleteButton.setAttribute("aria-label", "업무구분 삭제"); deleteButton.innerHTML = icon("trash"); deleteButton.addEventListener("click", async () => {
        const label = `${item.departmentName} → ${item.middleName}${item.smallName ? ` → ${item.smallName}` : ""}`;
        if (!window.confirm(`${label}\n\n이 업무구분을 삭제하시겠습니까?\n사용 중인 업무가 있으면 삭제되지 않고 미사용 전환을 안내합니다.`)) return;
        deleteButton.disabled = true;
        try {
          const result = await post(DELETE_API, { work_category_id: item.id });
          window.alert(result.message); window.location.reload();
        } catch (error) { window.alert(error.message); }
        finally { deleteButton.disabled = false; }
      });

      wrapper.append(editButton, deleteButton);
      if (oldToggleForm) {
        const toggleButton = oldToggleForm.querySelector("button");
        if (toggleButton) {
          toggleButton.className = "awc-icon-button toggle";
          toggleButton.title = item.active ? "미사용 전환" : "다시 사용";
          toggleButton.setAttribute("aria-label", item.active ? "업무구분 미사용 전환" : "업무구분 다시 사용");
          toggleButton.innerHTML = icon(item.active ? "pause" : "restore");
        }
        wrapper.append(oldToggleForm);
      }
      manageCell.replaceChildren(wrapper);
    });
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
