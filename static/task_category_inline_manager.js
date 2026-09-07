(() => {
  const currentRole = () => document.body.dataset.currentRole || "";
  const isAdmin = () => {
    const role = currentRole();
    return role === "관리자" || role === "시스템관리자" || role.includes("관리자");
  };

  const readCatalog = () => {
    const source = document.getElementById("work-category-catalog");
    if (!source) return [];
    try {
      return JSON.parse(source.textContent || "[]");
    } catch (_error) {
      return [];
    }
  };

  const ensureStyles = () => {
    if (document.getElementById("task-category-basics-link-style")) return;
    const style = document.createElement("style");
    style.id = "task-category-basics-link-style";
    style.textContent = `
      .task-category-basics-link{grid-column:1/-1;display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:2px 0 10px;padding:11px 12px;border:1px solid #dbe4ef;border-radius:10px;background:#f8fafc}
      .task-category-basics-link strong{margin-right:4px}.task-category-basics-link small{color:#64748b;margin-right:auto}.task-category-basics-link .button{white-space:nowrap}
    `;
    document.head.append(style);
  };

  const applyMiddleOnlyCategory = (section) => {
    const department = section.querySelector("[data-work-department]");
    const middle = section.querySelector("[data-work-middle]");
    const small = section.querySelector("[data-work-category]");
    if (!department?.value || !middle?.value || !small) return;

    const middleOnly = readCatalog().find((item) =>
      String(item.department_id) === String(department.value)
      && String(item.middle_name || "") === String(middle.value)
      && !String(item.small_name || "").trim()
    );
    if (!middleOnly) return;

    const option = [...small.options].find(
      (item) => String(item.value) === String(middleOnly.id)
    );
    if (!option) return;

    option.textContent = "소분류 미지정";
    if (!small.value) {
      small.value = String(middleOnly.id);
    }
  };

  const init = () => {
    if (window.location.pathname !== "/tasks/new") return;
    const section = document.querySelector(".work-category-form[data-work-category-form]");
    if (!section || section.dataset.categoryBasicsLinkBound) return;
    section.dataset.categoryBasicsLinkBound = "true";
    ensureStyles();

    const department = section.querySelector("[data-work-department]");
    const middle = section.querySelector("[data-work-middle]");

    const bar = document.createElement("div");
    bar.className = "task-category-basics-link";

    const copy = document.createElement("div");
    copy.innerHTML = `<strong>업무구분 기초자료</strong><small>${isAdmin() ? "관리자 업무구분 화면에서 전체 부서의 기초자료를 관리합니다." : "본인 부서(팀)의 중분류·소분류를 조회·등록·수정할 수 있습니다."}</small>`;
    bar.append(copy);

    const link = document.createElement("a");
    link.className = "button ghost small";
    link.textContent = isAdmin() ? "관리자 업무구분 관리" : "업무구분 등록·수정";
    if (isAdmin()) {
      link.href = "/admin?section=work-categories";
    } else {
      const returnTo = `${window.location.pathname}${window.location.search}`;
      link.href = `/task-categories?return_to=${encodeURIComponent(returnTo)}`;
    }
    bar.append(link);
    section.prepend(bar);

    // app.js가 중분류 변경 시 소분류 옵션을 먼저 재구성한 뒤,
    // 중분류 전용 항목(small_name='')을 자동 선택해 업무 저장 시 중분류가 유실되지 않게 한다.
    middle?.addEventListener("change", () => applyMiddleOnlyCategory(section));
    department?.addEventListener("change", () => window.setTimeout(() => applyMiddleOnlyCategory(section), 0));
    applyMiddleOnlyCategory(section);
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
