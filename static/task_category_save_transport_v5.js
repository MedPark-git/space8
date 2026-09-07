(() => {
  const DIALOG = "#task-category-selector-manager-v3";
  const csrfToken = () => document.querySelector('meta[name="csrf-token"]')?.content || "";
  const currentDepartmentId = () => document.body.dataset.currentDepartmentId || "";
  const currentRole = () => document.body.dataset.currentRole || "";
  const isAdmin = () => currentRole() === "관리자" || currentRole().includes("관리자");
  const readCatalog = () => {
    const node = document.getElementById("work-category-catalog");
    if (!node) return [];
    try { return JSON.parse(node.textContent || "[]"); } catch (_error) { return []; }
  };
  const writeCatalog = (catalog) => {
    const node = document.getElementById("work-category-catalog");
    if (node) node.textContent = JSON.stringify(Array.isArray(catalog) ? catalog : []);
  };
  const activeSection = () => [...document.querySelectorAll("[data-work-category-form]")].find((node) => node.offsetParent !== null) || document.querySelector("[data-work-category-form]");
  const departmentId = () => isAdmin() ? (activeSection()?.querySelector("[data-work-department]")?.value || currentDepartmentId()) : currentDepartmentId();
  const requestCategory = async (action, values) => {
    const body = new URLSearchParams({ csrf_token: csrfToken(), ...Object.fromEntries(Object.entries(values).map(([k,v]) => [k, String(v ?? "")])) });
    const response = await fetch(`/tasks/new?category_action=${encodeURIComponent(action)}&_category_transport=v5`, {
      method: "POST",
      credentials: "same-origin",
      redirect: "follow",
      headers: { Accept: "application/json", "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8", "X-Requested-With": "XMLHttpRequest" },
      body,
    });
    const raw = await response.text();
    let result;
    try { result = JSON.parse(raw); } catch (_error) { result = null; }
    if (!result) throw new Error(`업무구분 저장 응답이 JSON이 아닙니다. (HTTP ${response.status})`);
    if (!response.ok || !result.ok) throw new Error(result.message || `업무구분 처리 실패 (HTTP ${response.status})`);
    return result;
  };
  const replaceOptions = (select, rows, placeholder, selected = "") => {
    if (!select) return;
    select.replaceChildren(new Option(placeholder, ""));
    rows.forEach(({value,label}) => select.append(new Option(label, String(value))));
    if (selected && [...select.options].some((o) => o.value === String(selected))) select.value = String(selected);
  };
  const refresh = (dialog, preferredMiddle = "", preferredSmallId = "") => {
    const catalog = readCatalog();
    const deptId = departmentId();
    const middle = dialog.querySelector("[data-existing-middle]");
    const small = dialog.querySelector("[data-existing-small]");
    const names = [...new Set(catalog.filter(i => String(i.department_id) === String(deptId)).map(i => i.middle_name).filter(Boolean))];
    replaceOptions(middle, names.map(n => ({value:n,label:n})), "중분류 선택", preferredMiddle || middle?.value || "");
    const rows = catalog.filter(i => String(i.department_id) === String(deptId) && i.middle_name === middle?.value && String(i.small_name || "").trim());
    replaceOptions(small, rows.map(i => ({value:i.id,label:i.small_name})), "소분류 선택", preferredSmallId || small?.value || "");
    document.querySelectorAll("[data-work-category-form]").forEach((section) => {
      const d = section.querySelector("[data-work-department]");
      const m = section.querySelector("[data-work-middle]");
      const s = section.querySelector("[data-work-category]");
      if (!d || !m || !s) return;
      if (!isAdmin() && currentDepartmentId()) d.value = currentDepartmentId();
      const dId = d.value || currentDepartmentId();
      const mids = [...new Set(catalog.filter(i => String(i.department_id) === String(dId)).map(i => i.middle_name).filter(Boolean))];
      replaceOptions(m, mids.map(n => ({value:n,label:n})), "미분류", preferredMiddle || m.value || "");
      const smalls = catalog.filter(i => String(i.department_id) === String(dId) && i.middle_name === m.value);
      replaceOptions(s, smalls.map(i => ({value:i.id,label:i.small_name || "소분류 없음"})), "미분류", preferredSmallId || s.value || "");
    });
  };
  document.addEventListener("submit", async (event) => {
    const form = event.target.closest(`${DIALOG} [data-category-operation-form]`);
    if (!form) return;
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    const op = form.querySelector("[data-operation]")?.value || "";
    const middle = form.querySelector("[data-existing-middle]")?.value || "";
    const smallId = form.querySelector("[data-existing-small]")?.value || "";
    const newNameInput = form.querySelector("[data-new-name]");
    const newName = newNameInput?.value.trim() || "";
    const status = form.querySelector(".task-category-operation-status");
    const submit = form.querySelector("button[type='submit']");
    const setStatus = (message, tone="") => { if (status) { status.textContent = message; status.className = "task-category-operation-status"; if (tone) status.classList.add(tone); } };
    const deptId = departmentId();
    if (!deptId) return setStatus("대분류(부서·팀)를 확인해 주세요.", "error");
    if (op !== "middle_add" && !middle) return setStatus("기존 중분류를 선택해 주세요.", "error");
    if (op === "small_rename" && !smallId) return setStatus("기존 소분류를 선택해 주세요.", "error");
    if (!newName) return setStatus("새 이름을 입력해 주세요.", "error");
    submit.disabled = true; setStatus("저장 중입니다.");
    try {
      let result, preferredMiddle = middle, preferredSmallId = smallId;
      if (op === "middle_add") { result = await requestCategory("add", {department_id:deptId,middle_name:newName,small_name:""}); preferredMiddle = newName; preferredSmallId = result.category?.id || ""; }
      else if (op === "small_add") { result = await requestCategory("add", {department_id:deptId,middle_name:middle,small_name:newName}); preferredSmallId = result.category?.id || ""; }
      else if (op === "middle_rename") { result = await requestCategory("rename_middle", {department_id:deptId,old_middle_name:middle,new_middle_name:newName}); preferredMiddle = newName; preferredSmallId = ""; }
      else if (op === "small_rename") { result = await requestCategory("rename_small", {work_category_id:smallId,new_small_name:newName}); }
      else throw new Error("지원하지 않는 작업입니다.");
      if (Array.isArray(result.categories)) writeCatalog(result.categories);
      if (newNameInput) newNameInput.value = "";
      refresh(form.closest("dialog"), preferredMiddle, preferredSmallId);
      setStatus(result.message || "업무구분을 저장했습니다.", "success");
    } catch (error) { setStatus(String(error.message || error), "error"); }
    finally { submit.disabled = false; }
  }, true);
})();
