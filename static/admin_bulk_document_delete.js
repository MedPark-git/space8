(() => {
  const path = window.location.pathname;
  const config = path === "/meetings"
    ? {
        tableSelector: ".meeting-board-table",
        previewSelector: "[data-meeting-preview]",
        previewPattern: /\/meetings\/(\d+)\/preview/,
        action: "/document-control/meetings/bulk-delete",
        noun: "일일회의 문서",
      }
    : path === "/journals"
      ? {
          tableSelector: ".journal-board-table",
          previewSelector: "[data-journal-preview]",
          previewPattern: /\/journals\/(\d+)\/preview/,
          action: "/document-control/journals/bulk-delete",
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

  const submitDelete = (documentIds) => {
    if (!documentIds.length) return;
    const message = `선택한 ${config.noun} ${documentIds.length}건을 삭제하시겠습니까?\n연결된 각 부서(팀) 원본 업무는 삭제되지 않습니다.`;
    if (!window.confirm(message)) return;

    const form = document.createElement("form");
    form.method = "post";
    form.action = config.action;
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

  const setup = () => {
    const table = document.querySelector(config.tableSelector);
    const panel = table?.closest(".meeting-board-panel");
    const headRow = table?.querySelector("thead tr");
    const bodyRows = [...(table?.querySelectorAll("tbody tr") || [])];
    if (!table || !panel || !headRow || table.dataset.adminBulkDeleteBound) return;
    table.dataset.adminBulkDeleteBound = "true";

    const documentRows = bodyRows
      .map((row) => ({ row, documentId: extractDocumentId(row) }))
      .filter((item) => item.documentId);

    if (!documentRows.length) {
      const emptyCell = table.querySelector("tbody tr .empty");
      if (emptyCell) {
        const colspan = Number(emptyCell.getAttribute("colspan") || "0");
        if (colspan) emptyCell.setAttribute("colspan", String(colspan + 1));
      }
      return;
    }

    const selectHead = document.createElement("th");
    selectHead.className = "document-bulk-select";
    selectHead.style.width = "44px";
    const selectAll = document.createElement("input");
    selectAll.type = "checkbox";
    selectAll.setAttribute("aria-label", `현재 목록 ${config.noun} 전체 선택`);
    selectAll.title = "전체 선택";
    selectHead.append(selectAll);
    headRow.prepend(selectHead);

    const checkboxes = [];
    documentRows.forEach(({ row, documentId }) => {
      const cell = document.createElement("td");
      cell.className = "document-bulk-select";
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.value = documentId;
      checkbox.dataset.documentBulkCheck = "true";
      checkbox.setAttribute("aria-label", `${config.noun} 선택`);
      cell.append(checkbox);
      row.prepend(cell);
      checkboxes.push(checkbox);
    });

    const panelHead = panel.querySelector(":scope > .panel-head");
    const actions = document.createElement("div");
    actions.className = "button-row document-admin-bulk-actions";

    const selectedLabel = document.createElement("span");
    selectedLabel.className = "permission-muted";
    selectedLabel.textContent = "선택 0건";

    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "button danger small";
    deleteButton.disabled = true;
    deleteButton.innerHTML = '<svg class="button-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M9 7V4h6v3M7 7l1 13h8l1-13M10 11v5M14 11v5"/></svg><span>선택 문서 삭제</span>';

    actions.append(selectedLabel, deleteButton);
    panelHead?.append(actions);

    const selectedIds = () => checkboxes.filter((checkbox) => checkbox.checked).map((checkbox) => checkbox.value);
    const updateState = () => {
      const selected = selectedIds();
      deleteButton.disabled = selected.length === 0;
      selectedLabel.textContent = `선택 ${selected.length}건`;
      const buttonLabel = deleteButton.querySelector("span");
      if (buttonLabel) buttonLabel.textContent = selected.length ? `선택 ${selected.length}건 삭제` : "선택 문서 삭제";
      selectAll.checked = selected.length === checkboxes.length && checkboxes.length > 0;
      selectAll.indeterminate = selected.length > 0 && selected.length < checkboxes.length;
    };

    selectAll.addEventListener("change", () => {
      checkboxes.forEach((checkbox) => {
        checkbox.checked = selectAll.checked;
      });
      updateState();
    });
    checkboxes.forEach((checkbox) => checkbox.addEventListener("change", updateState));
    deleteButton.addEventListener("click", () => submitDelete(selectedIds()));
    updateState();
  };

  document.addEventListener("DOMContentLoaded", setup);
})();
