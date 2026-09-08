(() => {
  const DIALOG_ID = "task-category-selector-manager-v3";
  const currentVisibleTaskForm = () => {
    const section = [...document.querySelectorAll("[data-work-category-form]")].find((node) => node.offsetParent !== null)
      || document.querySelector("[data-work-category-form]");
    return section?.closest("form.form-panel") || null;
  };

  const addTaskTypePicker = (dialog) => {
    if (!dialog || dialog.id !== DIALOG_ID) return;
    const form = dialog.querySelector("[data-category-operation-form]");
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

    const sourceInputs = [...(currentVisibleTaskForm()?.querySelectorAll('input[name="task_types"]') || [])];
    const values = sourceInputs.length
      ? sourceInputs.map((input) => input.value)
      : ["대표이사님 수명업무", "루틴", "일반", "주요"];

    box.innerHTML = '<strong style="font-size:14px">업무분류 <small style="font-weight:400;color:#64748b">(현재 등록할 업무에 반영)</small></strong><div data-category-task-type-options style="display:flex;flex-wrap:wrap;gap:8px"></div><small style="color:#64748b">중·소분류 신규 등록 시 업무분류를 함께 선택하세요.</small>';
    const holder = box.querySelector("[data-category-task-type-options]");

    values.forEach((value) => {
      const source = sourceInputs.find((input) => input.value === value);
      const label = document.createElement("label");
      label.style.cssText = "display:inline-flex;align-items:center;gap:6px;padding:8px 10px;border:1px solid #cbd5e1;border-radius:8px;background:#fff;font-weight:600;cursor:pointer";
      const input = document.createElement("input");
      input.type = "checkbox";
      input.value = value;
      input.dataset.categoryTaskType = "1";
      input.checked = Boolean(source?.checked);
      label.append(input, document.createTextNode(value));
      holder.append(label);
    });

    const operation = form.querySelector("[data-operation]")?.value || "";
    box.hidden = !["middle_add", "small_add"].includes(operation);
    dialog.dataset.categoryTaskTypeUi = "v13";
  };

  const scan = () => {
    const dialog = document.getElementById(DIALOG_ID);
    if (dialog && dialog.dataset.categoryTaskTypeUi !== "v13") addTaskTypePicker(dialog);
  };

  const observer = new MutationObserver(scan);
  observer.observe(document.documentElement, { childList: true, subtree: true });

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", scan);
  else scan();
})();
