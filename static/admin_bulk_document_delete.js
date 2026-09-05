(() => {
  if (document.body?.dataset.effectiveAdmin !== "true") return;

  const path = window.location.pathname;
  const config = path === "/meetings"
    ? {
        tableSelector: ".meeting-board-table",
        previewSelector: "[data-meeting-preview]",
        previewPattern: /\/meetings\/(\d+)\/preview/,
        bulkAction: "/document-control/meetings/bulk-delete",
        singleAction: (id) => `/document-control/meetings/${id}/delete`,
        noun: "일일회의 문서",
      }
    : path === "/journals"
      ? {
          tableSelector: ".journal-board-table",
          previewSelector: "[data-journal-preview]",
          previewPattern: /\/journals\/(\d+)\/preview/,
          bulkAction: "/document-control/journals/bulk-delete",
          singleAction: (id) => `/document-control/journals/${id}/delete`,
          noun: "업무일지 문서",
        }
      : null;

  if (!config) return;

  const csrfToken = () => document.querySelector('meta[name="csrf-token"]')?.content || "";

  const extractDocumentId = (row) => {
    const preview = row.querySelector(config.previewSelector);
    if (!preview) return null;
    const value = preview.dataset.meetingPreview || preview.dataset.journalPreview || "";
    return value.match(config.previewPattern)?.[1] || null;
  };

  const postDelete = (action, documentIds = []) => {
    const form = document.createElement("form");
    form.method = "post";
    form.action = action;
    form.hidden = true;

    const csrf = document.createElement("input");
    csrf.type = "hidden";
    csrf.name = "csrf_token";
    csrf.value = csrfToken();
    form.append(csrf);

    documentIds.forEach((documentId) => {
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = "document_ids";
      input.value = String(documentId);
      form.append(input);
    });

    document.body.append(form);
    form.submit();
  };

  const makeTrashButton = (documentId) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "button danger small";
    button.title = "삭제";
    button.setAttribute("aria-label", `${config.noun} 삭제`);
    button.style.minWidth = "36px";
    button.style.padding = "7px 9px";
    button.innerHTML = '<svg class="button-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M9 7V4h6v3M7 7l1 13h8l1-13M10 11v5M14 11v5"/></svg>';
    button.addEventListener("click", () => {
      if (!window.confirm(`이 ${config.noun}를 삭제하시겠습니까?\n연결된 각 부서(팀) 원본 업무는 삭제되지 않습니다.`)) return;
      postDelete(config.singleAction(documentId));
    });
    return button;
  };

  const setup = () => {
    const table = document.querySelector(config.tableSelector);
    if (!table || table.dataset.adminDeleteReady === "true") return;
    table.dataset.adminDeleteReady = "true";

    const headRow = table.querySelector("thead tr");
    const bodyRows = [...table.querySelectorAll("tbody tr")];
    const panel = table.closest(".meeting-board-panel");
    const panelHead = panel?.querySelector(":scope > .panel-head");
    if (!headRow || !panel || !panelHead) return;

    const documentRows = bodyRows
      .map((row) => ({ row, documentId: extractDocumentId(row) }))
      .filter((item) => item.documentId);

    if (!documentRows.length) {
      const emptyCell = table.querySelector("tbody tr .empty");
      if (emptyCell) {
        const colspan = Number(emptyCell.getAttribute("colspan") || "0");
        if (colspan) emptyCell.setAttribute("colspan", String(colspan + 2));
      }
      return;
    }

    const selectHead = document.createElement("th");
    selectHead.style.width = "44px";
    const selectAll = document.createElement("input");
    selectAll.type = "checkbox";
    selectAll.title = "전체 선택";
    selectAll.setAttribute("aria-label", `${config.noun} 전체 선택`);
    selectHead.append(selectAll);
    headRow.prepend(selectHead);

    const manageHead = document.createElement("th");
    manageHead.textContent = "관리";
    manageHead.style.width = "60px";
    headRow.append(manageHead);

    const checkboxes = [];
    documentRows.forEach(({ row, documentId }) => {
      const selectCell = document.createElement("td");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.value = documentId;
      checkbox.dataset.adminDocumentCheck = "true";
      checkbox.setAttribute("aria-label", `${config.noun} 선택`);
      selectCell.append(checkbox);
      row.prepend(selectCell);
      checkboxes.push(checkbox);

      const manageCell = document.createElement("td");
      manageCell.append(makeTrashButton(documentId));
      row.append(manageCell);
    });

    const actionWrap = document.createElement("div");
    actionWrap.className = "button-row document-admin-bulk-actions";
    actionWrap.style.alignItems = "center";

    const selectedLabel = document.createElement("span");
    selectedLabel.className = "permission-muted";
    selectedLabel.textContent = "선택 0건";

    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "button danger small";
    deleteButton.disabled = true;
    deleteButton.innerHTML = '<svg class="button-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M9 7V4h6v3M7 7l1 13h8l1-13M10 11v5M14 11v5"/></svg><span>선택 문서 삭제</span>';

    actionWrap.append(selectedLabel, deleteButton);
    panelHead.append(actionWrap);

    const selectedIds = () => checkboxes.filter((checkbox) => checkbox.checked).map((checkbox) => checkbox.value);
    const updateState = () => {
      const selected = selectedIds();
      deleteButton.disabled = selected.length === 0;
      selectedLabel.textContent = `선택 ${selected.length}건`;
      const label = deleteButton.querySelector("span");
      if (label) label.textContent = selected.length ? `선택 ${selected.length}건 삭제` : "선택 문서 삭제";
      selectAll.checked = checkboxes.length > 0 && selected.length === checkboxes.length;
      selectAll.indeterminate = selected.length > 0 && selected.length < checkboxes.length;
    };

    selectAll.addEventListener("change", () => {
      checkboxes.forEach((checkbox) => {
        checkbox.checked = selectAll.checked;
      });
      updateState();
    });
    checkboxes.forEach((checkbox) => checkbox.addEventListener("change", updateState));
    deleteButton.addEventListener("click", () => {
      const ids = selectedIds();
      if (!ids.length) return;
      if (!window.confirm(`선택한 ${config.noun} ${ids.length}건을 삭제하시겠습니까?\n연결된 각 부서(팀) 원본 업무는 삭제되지 않습니다.`)) return;
      postDelete(config.bulkAction, ids);
    });

    updateState();
  };

  setup();
})();
