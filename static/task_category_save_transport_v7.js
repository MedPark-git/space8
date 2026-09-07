(() => {
  const DIALOG = "#task-category-selector-manager-v3";
  const csrfToken = () => document.querySelector('meta[name="csrf-token"]')?.content || "";
  const currentDepartmentId = () => document.body.dataset.currentDepartmentId || "";
  const currentRole = () => document.body.dataset.currentRole || "";
  const isAdmin = () => currentRole() === "관리자" || currentRole().includes("관리자");

  const activeSection = () =>
    [...document.querySelectorAll("[data-work-category-form]")].find((node) => node.offsetParent !== null)
    || document.querySelector("[data-work-category-form]");

  const departmentId = () =>
    isAdmin()
      ? (activeSection()?.querySelector("[data-work-department]")?.value || currentDepartmentId())
      : currentDepartmentId();

  const hidden = (form, name, value) => {
    let input = form.querySelector(`input[type="hidden"][name="${name}"]`);
    if (!input) {
      input = document.createElement("input");
      input.type = "hidden";
      input.name = name;
      form.append(input);
    }
    input.value = String(value ?? "");
  };

  const prepareNativePost = (form, action, values) => {
    form.method = "post";
    form.action = "/tasks/new?category_manager=1";
    hidden(form, "csrf_token", csrfToken());
    hidden(form, "_category_transport", "v7");
    hidden(form, "category_action", action);
    Object.entries(values).forEach(([name, value]) => hidden(form, name, value));
  };

  document.addEventListener("submit", (event) => {
    const form = event.target.closest(`${DIALOG} [data-category-operation-form]`);
    if (!form) return;

    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();

    const operation = form.querySelector("[data-operation]")?.value || "";
    const middle = form.querySelector("[data-existing-middle]")?.value || "";
    const smallId = form.querySelector("[data-existing-small]")?.value || "";
    const newName = form.querySelector("[data-new-name]")?.value.trim() || "";
    const status = form.querySelector(".task-category-operation-status");
    const deptId = departmentId();

    const setStatus = (message, tone = "") => {
      if (!status) return;
      status.textContent = message;
      status.className = "task-category-operation-status";
      if (tone) status.classList.add(tone);
    };

    if (!deptId) return setStatus("대분류(부서·팀)를 확인해 주세요.", "error");
    if (operation !== "middle_add" && !middle) return setStatus("기존 중분류를 선택해 주세요.", "error");
    if (operation === "small_rename" && !smallId) return setStatus("기존 소분류를 선택해 주세요.", "error");
    if (!newName) return setStatus("새 이름을 입력해 주세요.", "error");

    if (operation === "middle_add") {
      prepareNativePost(form, "add", {
        department_id: deptId,
        middle_name: newName,
        small_name: "",
      });
    } else if (operation === "small_add") {
      prepareNativePost(form, "add", {
        department_id: deptId,
        middle_name: middle,
        small_name: newName,
      });
    } else if (operation === "middle_rename") {
      prepareNativePost(form, "rename_middle", {
        department_id: deptId,
        old_middle_name: middle,
        new_middle_name: newName,
      });
    } else if (operation === "small_rename") {
      prepareNativePost(form, "rename_small", {
        work_category_id: smallId,
        new_small_name: newName,
      });
    } else {
      return setStatus("지원하지 않는 작업입니다.", "error");
    }

    setStatus("저장 중입니다...");
    HTMLFormElement.prototype.submit.call(form);
  }, true);

  const reopenManager = () => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("category_manager") !== "1") return;

    const openDialog = () => {
      const button = document.querySelector(".task-category-tools button");
      if (!button) return false;
      button.click();
      window.setTimeout(() => {
        const dialog = document.querySelector(DIALOG);
        const status = dialog?.querySelector(".task-category-operation-status");
        const flash = document.querySelector(".flash-stack .flash");
        if (status && flash) {
          status.textContent = flash.textContent.trim();
          status.className = "task-category-operation-status";
          status.classList.add(flash.classList.contains("error") ? "error" : "success");
        }
        const preferredMiddle = params.get("category_middle") || "";
        const middle = dialog?.querySelector("[data-existing-middle]");
        if (middle && preferredMiddle && [...middle.options].some((option) => option.value === preferredMiddle)) {
          middle.value = preferredMiddle;
          middle.dispatchEvent(new Event("change", { bubbles: true }));
        }
      }, 50);
      return true;
    };

    if (openDialog()) return;
    let attempts = 0;
    const timer = window.setInterval(() => {
      attempts += 1;
      if (openDialog() || attempts > 20) window.clearInterval(timer);
    }, 100);
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", reopenManager);
  } else {
    reopenManager();
  }
})();
