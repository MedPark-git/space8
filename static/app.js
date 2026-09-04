const initDialogs = (root = document) => {
  root.querySelectorAll("[data-dialog]").forEach((button) => {
    if (button.dataset.dialogBound) return;
    button.dataset.dialogBound = "true";
    button.addEventListener("click", () => document.getElementById(button.dataset.dialog)?.showModal());
  });
  root.querySelectorAll("[data-close]").forEach((button) => {
    if (button.dataset.closeBound) return;
    button.dataset.closeBound = "true";
    button.addEventListener("click", () => button.closest("dialog")?.close());
  });
  root.querySelectorAll("dialog").forEach((dialog) => {
    if (dialog.dataset.backdropBound) return;
    dialog.dataset.backdropBound = "true";
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) dialog.close();
    });
    if (dialog.hasAttribute("data-open-on-load") && !dialog.open) dialog.showModal();
  });
};

const initBulkJournal = (root = document) => {
  const selectAll = root.querySelector("[data-check-all]");
  const taskChecks = [...root.querySelectorAll("[data-task-check]:not(:disabled)")];
  const bulkButton = root.querySelector("[data-bulk-journal]");
  const calendarButton = root.querySelector("[data-bulk-calendar]");
  const calendarRemoveButton = root.querySelector("[data-bulk-calendar-remove]");
  const majorButton = root.querySelector("[data-bulk-major]");
  const deleteButton = root.querySelector("[data-bulk-delete]");
  const actions = [
    { button: bulkButton, permission: "journalSelectable", emptyLabel: "일일업무 일지에 일괄 담기", selectedLabel: "일일업무 일지에 담기" },
    { button: calendarButton, permission: "calendarSelectable", emptyLabel: "일정(캘린더) 등록", selectedLabel: "캘린더 등록" },
    { button: calendarRemoveButton, permission: "calendarRemovable", emptyLabel: "일정(캘린더) 삭제", selectedLabel: "캘린더 삭제" },
    { button: majorButton, permission: "majorSelectable", emptyLabel: "주요업무 등록", selectedLabel: "주요업무 등록" },
    { button: deleteButton, permission: "deletable", emptyLabel: "선택 업무 삭제", selectedLabel: "삭제" },
  ];
  const updateBulkState = () => {
    const selected = taskChecks.filter((checkbox) => checkbox.checked);
    const selectedCount = selected.length;
    actions.forEach(({ button, permission, emptyLabel, selectedLabel }) => {
      if (!button) return;
      button.disabled = selectedCount === 0 || selected.some((checkbox) => checkbox.dataset[permission] !== "true");
      const label = button.querySelector("[data-bulk-label]");
      if (label) label.textContent = selectedCount ? `선택 ${selectedCount}건 ${selectedLabel}` : emptyLabel;
    });
    if (selectAll) {
      selectAll.checked = taskChecks.length > 0 && selectedCount === taskChecks.length;
      selectAll.indeterminate = selectedCount > 0 && selectedCount < taskChecks.length;
    }
  };
  selectAll?.addEventListener("change", () => {
    taskChecks.forEach((checkbox) => {
      checkbox.checked = selectAll.checked;
    });
    updateBulkState();
  });
  taskChecks.forEach((checkbox) => checkbox.addEventListener("change", updateBulkState));
  actions.forEach(({ button }) => {
    if (!button?.dataset.confirm || button.dataset.confirmBound) return;
    button.dataset.confirmBound = "true";
    button.addEventListener("click", (event) => {
      if (!window.confirm(button.dataset.confirm)) event.preventDefault();
    });
  });
  updateBulkState();
};

const initCadenceFiltering = () => {
  const form = document.querySelector("[data-cadence-form]");
  if (!form || form.dataset.cadenceBound) return;
  form.dataset.cadenceBound = "true";

  form.addEventListener("submit", async (event) => {
    const submitter = event.submitter;
    if (!submitter?.matches("button[name='cadence']")) return;
    event.preventDefault();

    const targetUrl = new URL(form.action || window.location.href, window.location.origin);
    targetUrl.search = "";
    targetUrl.hash = "";
    const formData = new FormData(form);
    formData.set("cadence", submitter.value);
    formData.forEach((value, key) => {
      if (String(value)) targetUrl.searchParams.append(key, String(value));
    });

    const scrollPosition = { left: window.scrollX, top: window.scrollY };
    const buttons = [...form.querySelectorAll("button[name='cadence']")];
    form.setAttribute("aria-busy", "true");
    buttons.forEach((button) => {
      button.disabled = true;
    });

    try {
      const response = await fetch(targetUrl, {
        credentials: "same-origin",
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });
      if (!response.ok) throw new Error(`업무 목록 조회 실패: ${response.status}`);

      const nextDocument = new DOMParser().parseFromString(await response.text(), "text/html");
      const selectors = ["[data-cadence-form]", "[data-task-filter-panel]", "[data-task-results]"];
      const replacements = selectors.map((selector) => [
        document.querySelector(selector),
        nextDocument.querySelector(selector),
      ]);
      if (replacements.some(([currentNode, nextNode]) => !currentNode || !nextNode)) {
        throw new Error("갱신할 업무 목록 영역을 찾을 수 없습니다.");
      }
      replacements.forEach(([currentNode, nextNode]) => currentNode.replaceWith(nextNode));

      window.history.replaceState(null, "", targetUrl);
      initCadenceFiltering();
      const results = document.querySelector("[data-task-results]");
      if (results) {
        initBulkJournal(results);
        initDialogs(results);
      }
      document.querySelector("[data-cadence-form] button.active")?.focus({ preventScroll: true });
      window.requestAnimationFrame(() => window.scrollTo(scrollPosition));
    } catch (_error) {
      window.location.assign(targetUrl);
    }
  });
};

const initEmployeeSearch = (root = document) => {
  const search = root.querySelector("[data-employee-search]");
  const rows = [...root.querySelectorAll("[data-employee-row]")];
  const emptyRow = root.querySelector("[data-employee-search-empty]");
  if (!search || search.dataset.searchBound) return;
  search.dataset.searchBound = "true";

  search.addEventListener("input", () => {
    const keyword = search.value.trim().toLocaleLowerCase("ko");
    let visibleCount = 0;
    rows.forEach((row) => {
      const visible = !keyword || (row.dataset.searchText || "").toLocaleLowerCase("ko").includes(keyword);
      row.hidden = !visible;
      if (visible) visibleCount += 1;
    });
    if (emptyRow) emptyRow.hidden = visibleCount > 0;
  });
};

const initMeetingDocumentForms = (root = document) => {
  root.querySelectorAll("[data-meeting-document-form]").forEach((form) => {
    if (form.dataset.meetingBound) return;
    form.dataset.meetingBound = "true";
    const radios = [...form.querySelectorAll("input[name='document_type']")];
    const fieldGroups = [...form.querySelectorAll("[data-meeting-fields]")];
    const updateFields = () => {
      const selectedType = radios.find((radio) => radio.checked)?.value || "agenda";
      fieldGroups.forEach((group) => {
        const active = group.dataset.meetingFields === selectedType;
        group.hidden = !active;
        group.querySelectorAll("input, textarea, select").forEach((control) => {
          control.disabled = !active;
        });
      });
      radios.forEach((radio) => {
        radio.closest(".meeting-type-card")?.classList.toggle("active", radio.checked);
      });
    };
    radios.forEach((radio) => radio.addEventListener("change", updateFields));
    updateFields();
  });
};

const initMeetingTaskFilters = (root = document) => {
  root.querySelectorAll("[data-meeting-task-filter]").forEach((filters) => {
    if (filters.dataset.taskFilterBound) return;
    filters.dataset.taskFilterBound = "true";
    const form = filters.closest("form");
    const list = form?.querySelector("[data-meeting-task-list]");
    const rows = [...(list?.querySelectorAll("[data-meeting-task-row]") || [])];
    const empty = list?.querySelector("[data-task-filter-empty]");
    const search = filters.querySelector("[data-task-search]");
    const department = filters.querySelector("[data-task-department]");
    const status = filters.querySelector("[data-task-status]");
    const taskChecks = [...rows.map((row) => row.querySelector("input[name='task_ids']")).filter(Boolean)];
    const selectedCount = form?.querySelector("[data-meeting-selected-count]");
    const clearButton = form?.querySelector("[data-meeting-clear-tasks]");
    const updateSelectedCount = () => {
      const count = taskChecks.filter((checkbox) => checkbox.checked).length;
      if (selectedCount) selectedCount.textContent = String(count);
      if (clearButton) clearButton.disabled = count === 0;
    };
    const update = () => {
      const keyword = (search?.value || "").trim().toLocaleLowerCase("ko");
      let visibleCount = 0;
      rows.forEach((row) => {
        const matches = (!keyword || (row.dataset.searchText || "").toLocaleLowerCase("ko").includes(keyword))
          && (!department?.value || row.dataset.department === department.value)
          && (!status?.value || row.dataset.status === status.value);
        row.hidden = !matches;
        if (matches) visibleCount += 1;
      });
      if (empty) empty.hidden = visibleCount > 0;
    };
    search?.addEventListener("input", update);
    department?.addEventListener("change", update);
    status?.addEventListener("change", update);
    taskChecks.forEach((checkbox) => checkbox.addEventListener("change", updateSelectedCount));
    clearButton?.addEventListener("click", () => {
      taskChecks.forEach((checkbox) => {
        checkbox.checked = false;
      });
      updateSelectedCount();
    });
    updateSelectedCount();
  });
};

const initMeetingCompose = (root = document) => {
  const dialog = root.querySelector("#meeting-compose-dialog");
  if (!dialog) return;
  root.querySelectorAll("[data-meeting-compose]").forEach((button) => {
    if (button.dataset.composeBound) return;
    button.dataset.composeBound = "true";
    button.addEventListener("click", () => {
      const radio = dialog.querySelector(`input[name='document_type'][value='${button.dataset.meetingCompose}']`);
      if (radio) {
        radio.checked = true;
        radio.dispatchEvent(new Event("change", { bubbles: true }));
      }
      if (!dialog.open) dialog.showModal();
      dialog.querySelector("input[name='meeting_date']")?.focus();
    });
  });
};

const initMeetingPrint = (root = document) => {
  root.querySelectorAll("[data-print-meeting], [data-print-journal]").forEach((button) => {
    if (button.dataset.printBound) return;
    button.dataset.printBound = "true";
    button.addEventListener("click", () => {
      const target = document.getElementById(button.dataset.printTarget || "");
      if (!target) return;
      const cleanup = () => {
        document.body.classList.remove("meeting-modal-print");
        target.classList.remove("meeting-print-target");
      };
      document.body.classList.add("meeting-modal-print");
      target.classList.add("meeting-print-target");
      window.addEventListener("afterprint", cleanup, { once: true });
      window.print();
      window.setTimeout(cleanup, 1000);
    });
  });
};

const initJournalDocumentForms = (root = document) => {
  root.querySelectorAll("[data-journal-document-form]").forEach((form) => {
    if (form.dataset.journalBound) return;
    form.dataset.journalBound = "true";
    const radios = [...form.querySelectorAll("input[name='document_type']")];
    const fieldGroups = [...form.querySelectorAll("[data-journal-fields]")];
    const privacyNote = form.querySelector("[data-journal-privacy-note]");
    const updateFields = () => {
      const selectedType = radios.find((radio) => radio.checked)?.value || "major";
      fieldGroups.forEach((group) => {
        const active = group.dataset.journalFields === selectedType;
        group.hidden = !active;
        group.querySelectorAll("input, textarea, select").forEach((control) => {
          control.disabled = !active;
        });
      });
      radios.forEach((radio) => {
        radio.closest(".journal-type-card")?.classList.toggle("active", radio.checked);
      });
      if (privacyNote) privacyNote.hidden = selectedType !== "daily";
    };
    radios.forEach((radio) => radio.addEventListener("change", updateFields));
    updateFields();
  });
};

const initJournalTaskPickers = (root = document) => {
  root.querySelectorAll("[data-journal-task-picker]").forEach((picker) => {
    if (picker.dataset.taskPickerBound) return;
    picker.dataset.taskPickerBound = "true";
    const rows = [...picker.querySelectorAll("[data-journal-task-row]")];
    const search = picker.querySelector("[data-journal-task-search]");
    const status = picker.querySelector("[data-journal-task-status]");
    const empty = picker.querySelector("[data-journal-task-empty]");
    const taskChecks = rows.map((row) => row.querySelector("input[name='task_ids']")).filter(Boolean);
    const selectedCount = picker.querySelector("[data-journal-selected-count]");
    const clearButton = picker.querySelector("[data-journal-clear-tasks]");
    const updateSelectedCount = () => {
      const count = taskChecks.filter((checkbox) => checkbox.checked).length;
      if (selectedCount) selectedCount.textContent = String(count);
      if (clearButton) clearButton.disabled = count === 0;
    };
    const updateRows = () => {
      const keyword = (search?.value || "").trim().toLocaleLowerCase("ko");
      let visibleCount = 0;
      rows.forEach((row) => {
        const visible = (!keyword || (row.dataset.searchText || "").toLocaleLowerCase("ko").includes(keyword))
          && (!status?.value || row.dataset.status === status.value);
        row.hidden = !visible;
        if (visible) visibleCount += 1;
      });
      if (empty) empty.hidden = visibleCount > 0;
    };
    search?.addEventListener("input", updateRows);
    status?.addEventListener("change", updateRows);
    taskChecks.forEach((checkbox) => checkbox.addEventListener("change", updateSelectedCount));
    clearButton?.addEventListener("click", () => {
      taskChecks.forEach((checkbox) => {
        checkbox.checked = false;
      });
      updateSelectedCount();
    });
    updateRows();
    updateSelectedCount();
  });
};

const initJournalCompose = (root = document) => {
  const dialog = root.querySelector("#journal-compose-dialog");
  if (!dialog) return;
  root.querySelectorAll("[data-journal-compose]").forEach((button) => {
    if (button.dataset.composeBound) return;
    button.dataset.composeBound = "true";
    button.addEventListener("click", () => {
      const radio = dialog.querySelector(`input[name='document_type'][value='${button.dataset.journalCompose}']`);
      if (radio) {
        radio.checked = true;
        radio.dispatchEvent(new Event("change", { bubbles: true }));
      }
      if (!dialog.open) dialog.showModal();
      dialog.querySelector("input[name='work_date']")?.focus();
    });
  });
};

const initJournalBoard = (root = document) => {
  const dialog = root.querySelector("#journal-preview-dialog");
  const content = dialog?.querySelector("[data-journal-preview-content]");
  if (!dialog || !content || dialog.dataset.previewBound) return;
  dialog.dataset.previewBound = "true";
  const loadPreview = async (url) => {
    content.innerHTML = '<div class="meeting-preview-loading"><p>업무일지를 불러오는 중입니다.</p></div>';
    if (!dialog.open) dialog.showModal();
    try {
      const response = await fetch(url, {
        credentials: "same-origin",
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });
      if (!response.ok) throw new Error(`업무일지 조회 실패: ${response.status}`);
      content.innerHTML = await response.text();
      initDialogs(content);
      initMeetingImageDownload(content);
      initMeetingPrint(content);
    } catch (_error) {
      content.innerHTML = '<div class="meeting-preview-error"><strong>업무일지를 불러오지 못했습니다.</strong><p>열람 권한을 확인하거나 창을 닫고 다시 선택해 주세요.</p><button class="button ghost" type="button" data-close>닫기</button></div>';
      initDialogs(content);
    }
  };
  root.querySelectorAll("[data-journal-preview]").forEach((button) => {
    if (button.dataset.previewBound) return;
    button.dataset.previewBound = "true";
    button.addEventListener("click", () => loadPreview(button.dataset.journalPreview));
  });
  const autoPreview = dialog.dataset.autoPreview;
  if (autoPreview) {
    loadPreview(autoPreview);
    const currentUrl = new URL(window.location.href);
    currentUrl.searchParams.delete("open");
    window.history.replaceState(null, "", currentUrl);
  }
};

const initMeetingBoard = (root = document) => {
  const dialog = root.querySelector("#meeting-preview-dialog");
  const content = dialog?.querySelector("[data-meeting-preview-content]");
  if (!dialog || !content || dialog.dataset.previewBound) return;
  dialog.dataset.previewBound = "true";
  const loadPreview = async (url) => {
    content.innerHTML = '<div class="meeting-preview-loading"><p>문서를 불러오는 중입니다.</p></div>';
    if (!dialog.open) dialog.showModal();
    try {
      const response = await fetch(url, {
        credentials: "same-origin",
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });
      if (!response.ok) throw new Error(`문서 조회 실패: ${response.status}`);
      content.innerHTML = await response.text();
      initDialogs(content);
      initMeetingImageDownload(content);
      initMeetingPrint(content);
    } catch (_error) {
      content.innerHTML = '<div class="meeting-preview-error"><strong>문서를 불러오지 못했습니다.</strong><p>창을 닫고 다시 선택해 주세요.</p><button class="button ghost" type="button" data-close>닫기</button></div>';
      initDialogs(content);
    }
  };
  root.querySelectorAll("[data-meeting-preview]").forEach((button) => {
    button.addEventListener("click", () => loadPreview(button.dataset.meetingPreview));
  });
  const autoPreview = dialog.dataset.autoPreview;
  if (autoPreview) {
    loadPreview(autoPreview);
    const currentUrl = new URL(window.location.href);
    currentUrl.searchParams.delete("open");
    window.history.replaceState(null, "", currentUrl);
  }
};

const copyComputedStyles = (source, clone) => {
  const sourceNodes = [source, ...source.querySelectorAll("*")];
  const cloneNodes = [clone, ...clone.querySelectorAll("*")];
  sourceNodes.forEach((sourceNode, index) => {
    const cloneNode = cloneNodes[index];
    if (!cloneNode) return;
    const computed = window.getComputedStyle(sourceNode);
    [...computed].forEach((property) => {
      cloneNode.style.setProperty(property, computed.getPropertyValue(property), computed.getPropertyPriority(property));
    });
  });
};

const downloadElementAsPng = async (button) => {
  const target = document.getElementById(button.dataset.imageTarget || "");
  if (!target) throw new Error("이미지로 저장할 문서를 찾을 수 없습니다.");
  await document.fonts?.ready;
  const width = Math.ceil(target.scrollWidth);
  const height = Math.ceil(target.scrollHeight);
  const clone = target.cloneNode(true);
  copyComputedStyles(target, clone);
  clone.style.margin = "0";
  clone.style.width = `${width}px`;
  clone.style.maxWidth = "none";
  const markup = new XMLSerializer().serializeToString(clone);
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}"><foreignObject width="100%" height="100%"><div xmlns="http://www.w3.org/1999/xhtml">${markup}</div></foreignObject></svg>`;
  const svgUrl = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml;charset=utf-8" }));
  try {
    const image = new Image();
    image.decoding = "async";
    image.src = svgUrl;
    await image.decode();
    const scale = Math.min(2, 12000 / width, 12000 / height);
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.floor(width * scale));
    canvas.height = Math.max(1, Math.floor(height * scale));
    const context = canvas.getContext("2d");
    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise((resolve, reject) => {
      canvas.toBlob((result) => result ? resolve(result) : reject(new Error("PNG 변환에 실패했습니다.")), "image/png");
    });
    const filename = (button.dataset.imageFilename || "일일회의")
      .replace(/[\\/:*?"<>|]+/g, "-")
      .trim();
    const downloadUrl = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = downloadUrl;
    link.download = `${filename || "일일회의"}.png`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(downloadUrl), 1000);
  } finally {
    URL.revokeObjectURL(svgUrl);
  }
};

const initMeetingImageDownload = (root = document) => {
  root.querySelectorAll("[data-download-image]").forEach((button) => {
    if (button.dataset.imageBound) return;
    button.dataset.imageBound = "true";
    button.addEventListener("click", async () => {
      const originalLabel = button.textContent;
      button.disabled = true;
      button.textContent = "이미지 생성 중...";
      try {
        await downloadElementAsPng(button);
      } catch (_error) {
        window.alert("이미지를 저장하지 못했습니다. A4 인쇄에서 PDF 저장을 이용해 주세요.");
      } finally {
        button.disabled = false;
        button.textContent = originalLabel;
      }
    });
  });
};

document.addEventListener("DOMContentLoaded", () => {
  const nav = document.querySelector(".main-nav");
  document.querySelector(".nav-toggle")?.addEventListener("click", () => nav?.classList.toggle("open"));
  initDialogs();
  initBulkJournal();
  initCadenceFiltering();
  initEmployeeSearch();
  initMeetingDocumentForms();
  initMeetingTaskFilters();
  initMeetingCompose();
  initMeetingBoard();
  initMeetingPrint();
  initMeetingImageDownload();
  initJournalDocumentForms();
  initJournalTaskPickers();
  initJournalCompose();
  initJournalBoard();

  setTimeout(() => document.querySelectorAll(".flash").forEach((item) => item.remove()), 6000);
});
