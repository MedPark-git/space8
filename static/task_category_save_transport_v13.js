(() => {
  const DIALOG = "#task-category-selector-manager-v3";
  const SAVE_URL = "/tasks/new";
  const currentDepartmentId = () => document.body.dataset.currentDepartmentId || "";
  const currentRole = () => document.body.dataset.currentRole || "";
  const isAdmin = () => currentRole() === "관리자" || currentRole().includes("관리자");
  const csrfToken = () => document.querySelector('meta[name="csrf-token"]')?.content || "";

  window.__MEDPARK_CATEGORY_TRANSPORT__ = "v13-existing-task-path";

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
    try { return JSON.parse(source.textContent || "[]"); } catch (_error) { return []; }
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

  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

  const setStatus = (form, message, tone = "") => {
    const status = form.querySelector(".task-category-operation-status");
    if (!status) return;
    status.textContent = message;
    status.className = "task-category-operation-status";
    if (tone) status.classList.add(tone);
  };

  const taskForm = () => activeSection()?.closest("form.form-panel") || null;
  const taskTypeInputs = () => [...(taskForm()?.querySelectorAll('input[name="task_types"]') || [])];

  const ensureTaskTypePicker = (dialog) => {
    const form = dialog?.querySelector("[data-category-operation-form]");
    if (!form) return;
    let box = form.querySelector("[data-category-task-types]");
    if (!box) {
      box = document.createElement("div");
      box.dataset.categoryTaskTypes = "1";
      box.className = "span-2 task-category-task-types";
      box.style.cssText = "display:grid;gap:8px;padding:12px;border:1px solid #dbe4ef;border-radius:10px;background:#f8fafc";
      const help = form.querySelector("[data-operation-help]");
      if (help) form.insertBefore(box, help);
      else form.append(box);
    }

    const options = taskTypeInputs();
    box.innerHTML = `
      <strong style="font-size:14px">업무분류 <small style="font-weight:400;color:#64748b">(등록할 업무에 반영)</small></strong>
      <div style="display:flex;flex-wrap:wrap;gap:8px" data-category-task-type-options></div>
      <small style="color:#64748b">소분류를 새로 등록할 때 해당 업무의 업무분류를 함께 선택하세요.</small>`;
    const holder = box.querySelector("[data-category-task-type-options]");
    const fallback = ["대표이사님 수명업무", "루틴", "일반", "주요"];
    const values = options.length ? options.map((item) => item.value) : fallback;
    values.forEach((value) => {
      const parent = options.find((item) => item.value === value);
      const label = document.createElement("label");
      label.style.cssText = "display:inline-flex;align-items:center;gap:6px;padding:8px 10px;border:1px solid #cbd5e1;border-radius:8px;background:#fff;font-weight:600";
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.value = value;
      checkbox.dataset.categoryTaskType = "1";
      checkbox.checked = Boolean(parent?.checked);
      label.append(checkbox, document.createTextNode(value));
      holder.append(label);
    });
    updateTaskTypeVisibility(dialog);
  };

  const updateTaskTypeVisibility = (dialog) => {
    const form = dialog?.querySelector("[data-category-operation-form]");
    const box = form?.querySelector("[data-category-task-types]");
    const op = form?.querySelector("[data-operation]")?.value || "";
    if (box) box.hidden = !["middle_add", "small_add"].includes(op);
  };

  const syncTaskTypesToTaskForm = (dialog) => {
    const picked = [...dialog.querySelectorAll("[data-category-task-type]:checked")].map((item) => item.value);
    taskTypeInputs().forEach((item) => { item.checked = picked.includes(item.value); });
    return picked;
  };

  const rowsForDepartment = (deptId) => readCatalog().filter((row) => String(row.department_id) === String(deptId));

  const replaceOptions = (select, items, placeholder) => {
    if (!select) return;
    select.replaceChildren(new Option(placeholder, ""));
    items.forEach(({ value, label }) => select.append(new Option(label, String(value))));
  };

  const refreshTaskSection = (middleName = "", categoryId = "") => {
    const section = activeSection();
    if (!section) return;
    const dept = section.querySelector("[data-work-department]");
    const middle = section.querySelector("[data-work-middle]");
    const small = section.querySelector("[data-work-category]");
    if (!dept || !middle || !small) return;
    if (!isAdmin() && currentDepartmentId()) dept.value = currentDepartmentId();
    const rows = rowsForDepartment(dept.value || currentDepartmentId());
    const middleNames = [...new Set(rows.map((row) => row.middle_name).filter(Boolean))];
    replaceOptions(middle, middleNames.map((name) => ({ value: name, label: name })), "미분류");
    if (middleName && middleNames.includes(middleName)) middle.value = middleName;
    const smallRows = rows.filter((row) => row.middle_name === middle.value);
    replaceOptions(small, smallRows.map((row) => ({ value: row.id, label: row.small_name || "소분류 없음" })), "미분류");
    if (categoryId && [...small.options].some((option) => option.value === String(categoryId))) {
      small.value = String(categoryId);
    } else {
      const placeholder = smallRows.find((row) => !String(row.small_name || "").trim());
      if (placeholder) small.value = String(placeholder.id);
    }
  };

  const refreshDialog = (dialog, preferredMiddle = "", preferredSmallId = "") => {
    if (!dialog) return;
    const rows = rowsForDepartment(departmentId());
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

    const count = dialog.querySelector("[data-category-count]");
    if (count) count.textContent = `${rows.length}건`;
    const list = dialog.querySelector("[data-category-current-list]");
    if (list) {
      if (!rows.length) {
        list.innerHTML = '<div class="task-category-current-empty">등록된 업무구분이 없습니다.</div>';
      } else {
        const grouped = new Map();
        rows.forEach((row) => {
          if (!grouped.has(row.middle_name)) grouped.set(row.middle_name, []);
          grouped.get(row.middle_name).push(row);
        });
        const body = [];
        [...grouped.entries()].forEach(([middleName, items]) => {
          items.forEach((item, index) => {
            body.push(`<tr><td>${index === 0 ? escapeHtml(middleName) : "↳"}</td><td>${item.small_name ? escapeHtml(item.small_name) : '<span class="permission-muted">미지정</span>'}</td></tr>`);
          });
        });
        list.innerHTML = `<div class="table-wrap"><table class="task-category-current-table"><thead><tr><th>중분류</th><th>소분류</th></tr></thead><tbody>${body.join("")}</tbody></table></div>`;
      }
    }
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
      headers: { Accept: "application/json", "X-Requested-With": "XMLHttpRequest" },
    });
    if (response.url.includes("/login")) {
      window.location.assign(response.url);
      throw new Error("로그인이 필요합니다.");
    }
    const contentType = response.headers.get("content-type") || "";
    if (!contentType.includes("application/json")) {
      throw new Error(`업무구분 저장 응답이 JSON이 아닙니다. (HTTP ${response.status})`);
    }
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.message || `업무구분 처리 실패 (HTTP ${response.status})`);
    if (Array.isArray(result.categories)) writeCatalog(result.categories);
    return result;
  };

  document.addEventListener("click", (event) => {
    if (!event.target.closest(".task-category-tools button")) return;
    window.setTimeout(() => {
      const dialog = document.querySelector(DIALOG);
      if (!dialog) return;
      dialog.dataset.categoryTransport = "v13";
      ensureTaskTypePicker(dialog);
      refreshDialog(dialog);
    }, 0);
  }, true);

  document.addEventListener("change", (event) => {
    const dialog = event.target.closest(DIALOG);
    if (!dialog) return;
    if (event.target.matches("[data-operation]")) updateTaskTypeVisibility(dialog);
    if (event.target.matches("[data-existing-middle]")) refreshDialog(dialog, event.target.value);
  }, true);

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
      const picked = syncTaskTypesToTaskForm(dialog);
      if (!picked.length) return setStatus(form, "업무분류를 하나 이상 선택해 주세요.", "error");
    }

    const submit = form.querySelector('button[type="submit"]');
    if (submit) submit.disabled = true;
    setStatus(form, "저장 중입니다...");

    try {
      let action = "";
      let values = {};
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
      const preferredMiddle = operation === "middle_add" || operation === "middle_rename" ? newName : middle;
      const preferredSmallId = result.category?.id || (operation === "small_rename" ? smallId : "");
      refreshTaskSection(preferredMiddle, preferredSmallId);
      refreshDialog(dialog, preferredMiddle, preferredSmallId);
      form.querySelector("[data-new-name]").value = "";
      setStatus(form, result.message || "업무구분을 저장했습니다.", "success");
    } catch (error) {
      setStatus(form, String(error.message || error), "error");
    } finally {
      if (submit) submit.disabled = false;
    }
  }, true);
})();
