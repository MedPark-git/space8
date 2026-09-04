(() => {
  const CATALOG_ID = "work-category-catalog";
  const ADD_ENDPOINT = "/tasks/work-categories/add";

  const readCatalog = () => {
    const source = document.getElementById(CATALOG_ID);
    if (!source) return [];
    try {
      return JSON.parse(source.textContent || "[]");
    } catch (_error) {
      return [];
    }
  };

  const writeCatalog = (catalog) => {
    const source = document.getElementById(CATALOG_ID);
    if (source) source.textContent = JSON.stringify(catalog);
  };

  const updateCatalogItem = (item) => {
    const catalog = readCatalog();
    const index = catalog.findIndex((current) => String(current.id) === String(item.id));
    if (index >= 0) catalog[index] = item;
    else catalog.push(item);
    writeCatalog(catalog);
  };

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

  const departmentCatalog = (departmentId) => readCatalog().filter(
    (item) => String(item.department_id) === String(departmentId || "")
  );

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
    replaceOptions(
      middle,
      names.map((name) => ({ value: name, label: name })),
      "미분류",
      selectedMiddle,
    );
    rebuildSmall(section, selectedId);
  };

  const selectedDepartmentName = (select, departmentId) => {
    const option = [...(select?.options || [])].find(
      (item) => String(item.value) === String(departmentId || "")
    );
    return option?.textContent?.trim() || "소속 부서(팀)";
  };

  const updateMiddleSuggestions = (datalist, departmentId) => {
    datalist.replaceChildren();
    const names = [...new Set(departmentCatalog(departmentId).map((item) => item.middle_name))];
    names.forEach((name) => {
      const option = document.createElement("option");
      option.value = name;
      datalist.append(option);
    });
  };

  const createCategoryDialog = (section) => {
    const body = document.body;
    const role = body.dataset.currentRole || "";
    const currentDepartmentId = body.dataset.currentDepartmentId || "";
    const isAdmin = role === "관리자";
    const mainDepartment = section.querySelector("[data-work-department]");

    const dialog = document.createElement("dialog");
    dialog.className = "work-category-dialog";
    dialog.innerHTML = `
      <div class="work-category-dialog-card">
        <div class="work-category-dialog-head">
          <div>
            <span class="eyebrow">WORK CATEGORY</span>
            <h2>업무구분 추가</h2>
            <p>현재 구조는 대분류(부서(팀)) → 중분류 → 소분류의 3단계입니다.</p>
          </div>
          <button class="work-category-dialog-close" type="button" aria-label="닫기">×</button>
        </div>
        <form class="work-category-create-form">
          <div data-category-department-field></div>
          <label>중분류
            <input name="middle_name" list="work-category-middle-suggestions" maxlength="100" required placeholder="예: 정보화기기">
          </label>
          <datalist id="work-category-middle-suggestions"></datalist>
          <label>소분류
            <input name="small_name" maxlength="150" placeholder="예: 네트워크 (중분류만 만들 경우 비워도 됨)">
          </label>
          <p class="work-category-form-note">새 중분류를 만들거나 기존 중분류 이름을 선택해 그 아래 소분류를 추가할 수 있습니다. 대분류는 부서(팀) 자체이므로 별도로 생성하지 않습니다.</p>
          <p class="work-category-create-status" role="status" aria-live="polite"></p>
          <div class="work-category-dialog-actions">
            <button class="button ghost" type="button" data-category-cancel>취소</button>
            <button class="button primary" type="submit" data-category-submit>업무구분 저장</button>
          </div>
        </form>
      </div>
    `;

    const form = dialog.querySelector("form");
    const departmentField = dialog.querySelector("[data-category-department-field]");
    const datalist = dialog.querySelector("datalist");
    const status = dialog.querySelector(".work-category-create-status");
    const submit = dialog.querySelector("[data-category-submit]");

    if (isAdmin) {
      const label = document.createElement("label");
      label.textContent = "대분류 (부서(팀))";
      const select = document.createElement("select");
      select.name = "department_id";
      select.required = true;
      [...(mainDepartment?.options || [])].forEach((sourceOption) => {
        if (!sourceOption.value) return;
        const option = document.createElement("option");
        option.value = sourceOption.value;
        option.textContent = sourceOption.textContent;
        select.append(option);
      });
      select.value = mainDepartment?.value || currentDepartmentId;
      label.append(select);
      departmentField.append(label);
      updateMiddleSuggestions(datalist, select.value);
      select.addEventListener("change", () => updateMiddleSuggestions(datalist, select.value));
    } else {
      const departmentId = currentDepartmentId || mainDepartment?.value || "";
      const hidden = document.createElement("input");
      hidden.type = "hidden";
      hidden.name = "department_id";
      hidden.value = departmentId;
      const label = document.createElement("div");
      label.innerHTML = "<strong>대분류 (부서(팀))</strong>";
      const fixed = document.createElement("div");
      fixed.className = "work-category-fixed-department";
      fixed.textContent = selectedDepartmentName(mainDepartment, departmentId);
      departmentField.append(label, fixed, hidden);
      updateMiddleSuggestions(datalist, departmentId);
    }

    const close = () => {
      status.textContent = "";
      status.className = "work-category-create-status";
      dialog.close();
    };
    dialog.querySelector(".work-category-dialog-close").addEventListener("click", close);
    dialog.querySelector("[data-category-cancel]").addEventListener("click", close);
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) close();
    });

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      status.textContent = "";
      status.className = "work-category-create-status";
      submit.disabled = true;
      submit.textContent = "저장 중...";

      const formData = new FormData(form);
      formData.set("csrf_token", document.querySelector('meta[name="csrf-token"]')?.content || "");
      formData.set("return_to", `${window.location.pathname}${window.location.search}`);

      try {
        const response = await fetch(ADD_ENDPOINT, {
          method: "POST",
          body: formData,
          credentials: "same-origin",
          headers: {
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json",
          },
        });
        const result = await response.json().catch(() => ({}));
        if (!response.ok || !result.ok || !result.category) {
          throw new Error(result.message || "업무구분을 저장하지 못했습니다.");
        }

        updateCatalogItem(result.category);
        if (mainDepartment) mainDepartment.value = String(result.category.department_id);
        rebuildMiddle(section, result.category.middle_name, result.category.id);
        status.textContent = result.message || "업무구분을 저장했습니다.";
        status.classList.add("success");
        form.querySelector("input[name='middle_name']").value = "";
        form.querySelector("input[name='small_name']").value = "";
        window.setTimeout(close, 700);
      } catch (error) {
        status.textContent = error.message || "업무구분 저장 중 오류가 발생했습니다.";
        status.classList.add("error");
      } finally {
        submit.disabled = false;
        submit.textContent = "업무구분 저장";
      }
    });

    document.body.append(dialog);
    return dialog;
  };

  const setupCategoryManager = () => {
    if (!window.location.pathname.startsWith("/tasks")) return;
    const taskForm = document.querySelector("form.form-panel");
    const grid = taskForm?.querySelector(".form-grid");
    const section = grid?.querySelector(".work-category-form[data-work-category-form]");
    const titleInput = grid?.querySelector("input[name='title']");
    const titleLabel = titleInput?.closest("label");
    if (!taskForm || !grid || !section || !titleLabel) return;

    grid.insertBefore(section, titleLabel);

    titleLabel.childNodes.forEach((node) => {
      if (node.nodeType === Node.TEXT_NODE && node.nodeValue.includes("업무 제목")) {
        node.nodeValue = node.nodeValue.replace("업무 제목", "업무명");
      }
    });

    const legacyHelp = section.querySelector(".form-help");
    if (legacyHelp) {
      legacyHelp.textContent = "필요한 중분류·소분류가 없으면 같은 부서(팀)에서 직접 추가할 수 있습니다.";
    }

    if (!section.querySelector(".category-manager-head")) {
      const head = document.createElement("div");
      head.className = "category-manager-head";
      head.innerHTML = `
        <div class="category-manager-copy">
          <strong>업무구분 (대분류 → 중분류 → 소분류)</strong>
          <small>대분류는 부서(팀)이며, 소속 부서의 중분류·소분류를 직접 추가할 수 있습니다.</small>
        </div>
      `;
      const button = document.createElement("button");
      button.type = "button";
      button.className = "button ghost small category-manager-trigger";
      button.textContent = "+ 업무구분 추가";
      head.append(button);
      section.prepend(head);

      const dialog = createCategoryDialog(section);
      button.addEventListener("click", () => {
        const role = document.body.dataset.currentRole || "";
        if (role === "관리자") {
          const modalDepartment = dialog.querySelector("select[name='department_id']");
          const mainDepartment = section.querySelector("[data-work-department]");
          if (modalDepartment && mainDepartment?.value) {
            modalDepartment.value = mainDepartment.value;
            updateMiddleSuggestions(
              dialog.querySelector("datalist"),
              modalDepartment.value,
            );
          }
        }
        dialog.showModal();
        dialog.querySelector("input[name='middle_name']")?.focus();
      });
    }

    const department = section.querySelector("[data-work-department]");
    const middle = section.querySelector("[data-work-middle]");
    if (!section.dataset.dynamicCategoryManagerBound) {
      section.dataset.dynamicCategoryManagerBound = "true";
      department?.addEventListener("change", () => rebuildMiddle(section));
      middle?.addEventListener("change", () => rebuildSmall(section));
    }
  };

  document.addEventListener("DOMContentLoaded", setupCategoryManager);
})();
