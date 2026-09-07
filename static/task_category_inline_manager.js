(() => {
  const CATALOG_ID = "work-category-catalog";
  const currentDepartmentId = () => document.body.dataset.currentDepartmentId || "";
  const currentRole = () => document.body.dataset.currentRole || "";
  const csrfToken = () => document.querySelector('meta[name="csrf-token"]')?.content || "";
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

  const upsertCategory = (item) => {
    const catalog = readCatalog();
    const index = catalog.findIndex((current) => String(current.id) === String(item.id));
    if (index >= 0) catalog[index] = item;
    else catalog.push(item);
    writeCatalog(catalog);
  };

  const departmentCatalog = (departmentId) => readCatalog().filter(
    (item) => String(item.department_id) === String(departmentId || "")
  );

  const replaceOptions = (select, items, emptyLabel, selectedValue = "") => {
    if (!select) return;
    select.replaceChildren();
    const empty = document.createElement("option");
    empty.value = "";
    empty.textContent = emptyLabel;
    select.append(empty);
    items.forEach(({ value, label }) => {
      const option = document.createElement("option");
      option.value = String(value);
      option.textContent = label;
      option.selected = String(value) === String(selectedValue);
      select.append(option);
    });
  };

  const rebuildSmall = (section, selectedId = "") => {
    const department = section.querySelector("[data-work-department]");
    const middle = section.querySelector("[data-work-middle]");
    const small = section.querySelector("[data-work-category]");
    const items = departmentCatalog(department?.value)
      .filter((item) => item.middle_name === middle?.value)
      .map((item) => ({ value: item.id, label: item.small_name || "소분류 없음" }));
    replaceOptions(small, items, "미분류", selectedId);
  };

  const rebuildMiddle = (section, selectedMiddle = "", selectedId = "") => {
    const department = section.querySelector("[data-work-department]");
    const middle = section.querySelector("[data-work-middle]");
    const names = [...new Set(departmentCatalog(department?.value).map((item) => item.middle_name))];
    replaceOptions(middle, names.map((name) => ({ value: name, label: name })), "미분류", selectedMiddle);
    rebuildSmall(section, selectedId);
  };

  const ensureStyles = () => {
    if (document.getElementById("task-category-inline-manager-style")) return;
    const style = document.createElement("style");
    style.id = "task-category-inline-manager-style";
    style.textContent = `
      .task-category-inline-actions{grid-column:1/-1;display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:2px 0 10px;padding:10px 12px;border:1px solid #dbe4ef;border-radius:10px;background:#f8fafc}
      .task-category-inline-actions strong{margin-right:4px}.task-category-inline-actions small{color:#64748b;margin-right:auto}.task-category-inline-actions .button{white-space:nowrap}
      .task-category-inline-dialog{width:min(520px,calc(100vw - 28px));border:0;border-radius:14px;padding:0;overflow:hidden}.task-category-inline-dialog::backdrop{background:rgba(15,23,42,.45)}
      .task-category-inline-card{background:#fff;padding:20px}.task-category-inline-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;margin-bottom:18px}.task-category-inline-head h2{margin:4px 0 2px}.task-category-inline-head p{margin:0;color:#64748b;font-size:13px}
      .task-category-inline-close{border:0;background:transparent;font-size:26px;color:#64748b;cursor:pointer}.task-category-inline-form{display:grid;gap:14px}.task-category-inline-form label{display:grid;gap:6px;font-weight:700}.task-category-inline-form input{width:100%;padding:10px 11px;border:1px solid #cbd5e1;border-radius:8px;font:inherit}
      .task-category-inline-context{padding:10px 12px;border-radius:8px;background:#f8fafc;color:#334155;font-size:13px}.task-category-inline-status{min-height:20px;margin:0;font-size:13px}.task-category-inline-status.error{color:#b42318}.task-category-inline-status.success{color:#067647}.task-category-inline-buttons{display:flex;justify-content:flex-end;gap:8px}
    `;
    document.head.append(style);
  };

  const readResponse = async (response) => {
    if (response.redirected && /\/login(?:\?|$)/.test(new URL(response.url, window.location.origin).pathname + new URL(response.url, window.location.origin).search)) {
      throw new Error("로그인 세션이 만료되었습니다. 업무등록 화면을 새로고침한 후 다시 로그인해 주세요.");
    }

    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || !payload.ok) {
        const code = payload.code ? ` [${payload.code}]` : "";
        throw new Error(`${payload.message || `분류 저장 요청이 실패했습니다. (HTTP ${response.status})`}${code}`);
      }
      return payload;
    }

    const raw = (await response.text().catch(() => "")).replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
    if (response.status === 400) {
      throw new Error("요청 보안 검증에 실패했습니다. 업무등록 화면을 새로고침한 후 다시 시도해 주세요. [HTTP 400]");
    }
    if (response.status === 401 || response.status === 403) {
      throw new Error(`로그인 또는 권한 확인이 필요합니다. [HTTP ${response.status}]`);
    }
    if (!response.ok) {
      throw new Error(`${raw ? raw.slice(0, 120) : "분류 저장 중 서버 오류가 발생했습니다."} [HTTP ${response.status}]`);
    }
    throw new Error("서버 응답 형식을 확인할 수 없습니다. 업무등록 화면을 새로고침한 후 다시 시도해 주세요.");
  };

  const createDialog = (section) => {
    const dialog = document.createElement("dialog");
    dialog.className = "task-category-inline-dialog";
    dialog.innerHTML = `
      <div class="task-category-inline-card">
        <div class="task-category-inline-head">
          <div><span class="eyebrow">TASK CATEGORY</span><h2 data-inline-category-title>분류 추가</h2><p data-inline-category-help></p></div>
          <button type="button" class="task-category-inline-close" aria-label="닫기">×</button>
        </div>
        <form class="task-category-inline-form">
          <div class="task-category-inline-context" data-inline-category-context></div>
          <label data-inline-category-input-label>분류명 <input name="category_name" maxlength="150" required></label>
          <p class="task-category-inline-status" role="status" aria-live="polite"></p>
          <div class="task-category-inline-buttons"><button type="button" class="button ghost" data-inline-category-cancel>취소</button><button type="submit" class="button primary" data-inline-category-save>저장</button></div>
        </form>
      </div>`;

    const form = dialog.querySelector("form");
    const title = dialog.querySelector("[data-inline-category-title]");
    const help = dialog.querySelector("[data-inline-category-help]");
    const context = dialog.querySelector("[data-inline-category-context]");
    const inputLabel = dialog.querySelector("[data-inline-category-input-label]");
    const input = form.querySelector("input[name='category_name']");
    const status = dialog.querySelector(".task-category-inline-status");
    const save = dialog.querySelector("[data-inline-category-save]");
    let level = "middle";

    const department = () => section.querySelector("[data-work-department]");
    const middle = () => section.querySelector("[data-work-middle]");
    const departmentName = () => department()?.selectedOptions?.[0]?.textContent?.trim() || "-";

    const close = () => { status.textContent = ""; status.className = "task-category-inline-status"; dialog.close(); };
    dialog.querySelector(".task-category-inline-close").addEventListener("click", close);
    dialog.querySelector("[data-inline-category-cancel]").addEventListener("click", close);
    dialog.addEventListener("click", (event) => { if (event.target === dialog) close(); });

    dialog.openFor = (nextLevel) => {
      level = nextLevel;
      input.value = "";
      status.textContent = "";
      status.className = "task-category-inline-status";

      if (level === "department") {
        title.textContent = "대분류(부서/팀) 추가";
        help.textContent = "관리자만 새 부서(팀)를 만들 수 있습니다.";
        context.textContent = "새 대분류는 조직의 부서(팀)로 등록됩니다.";
        inputLabel.childNodes[0].nodeValue = "새 대분류명 ";
        input.maxLength = 100;
      } else if (level === "middle") {
        title.textContent = "중분류 추가";
        help.textContent = "선택한 대분류 아래에 새 중분류를 추가합니다.";
        context.textContent = `대분류: ${departmentName()}`;
        inputLabel.childNodes[0].nodeValue = "새 중분류명 ";
        input.maxLength = 100;
      } else {
        title.textContent = "소분류 추가";
        help.textContent = "선택한 중분류 아래에 새 소분류를 추가합니다.";
        context.textContent = `대분류: ${departmentName()} / 중분류: ${middle()?.value || "-"}`;
        inputLabel.childNodes[0].nodeValue = "새 소분류명 ";
        input.maxLength = 150;
      }
      dialog.showModal();
      input.focus();
    };

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const name = input.value.trim();
      if (!name) return;
      const dept = department();
      const deptId = dept?.value || "";
      const middleName = middle()?.value || "";

      if (level !== "department" && !deptId) {
        status.textContent = "대분류(부서(팀))를 먼저 선택해 주세요.";
        status.className = "task-category-inline-status error";
        return;
      }
      if (!isAdmin() && level !== "department" && String(deptId) !== String(currentDepartmentId())) {
        status.textContent = "본인 소속 부서(팀)의 중분류·소분류만 추가할 수 있습니다.";
        status.className = "task-category-inline-status error";
        return;
      }
      if (level === "small" && !middleName) {
        status.textContent = "중분류를 먼저 선택해 주세요.";
        status.className = "task-category-inline-status error";
        return;
      }

      save.disabled = true;
      save.textContent = "저장 중...";
      status.textContent = "";
      status.className = "task-category-inline-status";

      const token = csrfToken();
      const data = new FormData();
      data.set("csrf_token", token);

      let endpoint = "/tasks/work-categories/add";
      if (level === "department") {
        endpoint = "/tasks/departments/add";
        data.set("name", name);
      } else {
        data.set("department_id", deptId);
        data.set("middle_name", level === "middle" ? name : middleName);
        data.set("small_name", level === "small" ? name : "");
      }

      try {
        const response = await fetch(endpoint, {
          method: "POST",
          body: data,
          credentials: "same-origin",
          redirect: "follow",
          headers: {
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json",
            "X-CSRFToken": token,
          },
        });
        const result = await readResponse(response);

        if (level === "department") {
          const item = result.department;
          let option = [...dept.options].find((current) => String(current.value) === String(item.id));
          if (!option) {
            option = document.createElement("option");
            option.value = String(item.id);
            option.textContent = item.name;
            dept.append(option);
          }
          dept.value = String(item.id);
          rebuildMiddle(section);
          dept.dispatchEvent(new Event("change", { bubbles: true }));
        } else {
          const item = result.category;
          upsertCategory(item);
          if (level === "middle") rebuildMiddle(section, item.middle_name, item.id);
          else {
            if (middle()) middle().value = item.middle_name;
            rebuildSmall(section, item.id);
          }
        }

        status.textContent = result.message || "분류를 저장했습니다.";
        status.className = "task-category-inline-status success";
        window.setTimeout(close, 650);
      } catch (error) {
        status.textContent = error.message || "분류 저장 중 오류가 발생했습니다.";
        status.className = "task-category-inline-status error";
      } finally {
        save.disabled = false;
        save.textContent = "저장";
      }
    });

    document.body.append(dialog);
    return dialog;
  };

  const init = () => {
    if (window.location.pathname !== "/tasks/new") return;
    ensureStyles();
    const section = document.querySelector(".work-category-form[data-work-category-form]");
    if (!section || section.dataset.inlineCategoryManagerBound) return;
    section.dataset.inlineCategoryManagerBound = "true";

    const department = section.querySelector("[data-work-department]");
    const middle = section.querySelector("[data-work-middle]");
    const dialog = createDialog(section);

    const actions = document.createElement("div");
    actions.className = "task-category-inline-actions";
    actions.innerHTML = `<strong>분류 직접 추가</strong><small>필요한 대·중·소분류가 없으면 업무등록 화면에서 바로 추가할 수 있습니다.</small>`;

    if (isAdmin()) {
      const addDepartment = document.createElement("button");
      addDepartment.type = "button";
      addDepartment.className = "button ghost small";
      addDepartment.textContent = "+ 대분류 추가";
      addDepartment.addEventListener("click", () => dialog.openFor("department"));
      actions.append(addDepartment);
    }

    const addMiddle = document.createElement("button");
    addMiddle.type = "button";
    addMiddle.className = "button ghost small";
    addMiddle.textContent = "+ 중분류 추가";
    addMiddle.addEventListener("click", () => dialog.openFor("middle"));
    actions.append(addMiddle);

    const addSmall = document.createElement("button");
    addSmall.type = "button";
    addSmall.className = "button ghost small";
    addSmall.textContent = "+ 소분류 추가";
    addSmall.addEventListener("click", () => dialog.openFor("small"));
    actions.append(addSmall);

    section.prepend(actions);
    department?.addEventListener("change", () => rebuildMiddle(section));
    middle?.addEventListener("change", () => rebuildSmall(section));
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
