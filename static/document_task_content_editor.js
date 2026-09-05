(() => {
  const DAILY_AFTER_SAVE_KEY = "medpark-task-after-save-daily-document";

  const taskIdsFromQuery = () => {
    const params = new URLSearchParams(window.location.search);
    const ids = [];
    params.getAll("task_ids").forEach((value) => {
      String(value || "").split(",").forEach((item) => {
        const clean = item.trim();
        if (/^\d+$/.test(clean) && !ids.includes(clean)) ids.push(clean);
      });
    });
    return ids;
  };

  const buildJournalUrl = (documentType, taskIds) => {
    const url = new URL("/journals", window.location.origin);
    url.searchParams.set("compose", documentType);
    taskIds.forEach((id) => url.searchParams.append("task_ids", String(id)));
    return `${url.pathname}${url.search}`;
  };

  const selectedTaskIds = () => {
    const ids = [];
    const keys = new Set();
    document.querySelectorAll("[data-task-check]:checked:not(:disabled)").forEach((checkbox) => {
      const id = String(checkbox.value || "");
      if (!/^\d+$/.test(id)) return;
      const row = checkbox.closest("tr");
      const category = (row?.querySelector(".task-category-path")?.textContent || "")
        .replace(/\s+/g, " ").trim().toLocaleLowerCase("ko");
      const title = (row?.querySelector(".task-title")?.textContent || "")
        .replace(/\s+/g, " ").trim().toLocaleLowerCase("ko");
      const key = category && title ? `${category}|${title}` : `task:${id}`;
      if (keys.has(key)) return;
      keys.add(key);
      ids.push(id);
    });
    return ids;
  };

  const setupTaskListDailyTransfer = () => {
    if (window.location.pathname !== "/tasks") return;

    const bulk = document.querySelector("[data-bulk-journal]");
    if (bulk && !bulk.dataset.documentSnapshotBound) {
      bulk.dataset.documentSnapshotBound = "true";
      bulk.addEventListener("click", (event) => {
        if (bulk.disabled) return;
        const ids = selectedTaskIds();
        if (!ids.length) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        window.location.assign(buildJournalUrl("daily", ids));
      }, true);
    }

    document.querySelectorAll("[data-task-check]").forEach((checkbox) => {
      const taskId = String(checkbox.value || "");
      if (!/^\d+$/.test(taskId)) return;
      const row = checkbox.closest("tr");
      const actions = row?.querySelector("[data-row-document-actions]");
      if (!actions || actions.querySelector("[data-row-daily-document]")) return;
      const daily = document.createElement("a");
      daily.className = "button ghost small";
      daily.dataset.rowDailyDocument = "true";
      daily.href = buildJournalUrl("daily", [taskId]);
      daily.textContent = "일일업무 추가";
      actions.append(daily);
    });
  };

  const setupTaskDetailDailyTransfer = () => {
    const match = window.location.pathname.match(/^\/tasks\/(\d+)$/);
    if (!match) return;
    const heading = document.querySelector(".page-heading");
    const actions = heading?.querySelector(".button-row");
    if (!heading || !actions || actions.querySelector("[data-detail-daily-document]")) return;
    if ((heading.querySelector("h1")?.textContent || "").includes("비공개 업무")) return;

    const daily = document.createElement("a");
    daily.className = "button ghost";
    daily.dataset.detailDailyDocument = "true";
    daily.href = buildJournalUrl("daily", [match[1]]);
    daily.textContent = "일일업무 일지에 추가";
    actions.prepend(daily);

    try {
      const raw = sessionStorage.getItem(DAILY_AFTER_SAVE_KEY);
      if (!raw) return;
      const intent = JSON.parse(raw);
      sessionStorage.removeItem(DAILY_AFTER_SAVE_KEY);
      if (Date.now() - Number(intent?.createdAt || 0) > 5 * 60 * 1000) return;
      window.location.replace(buildJournalUrl("daily", [match[1]]));
    } catch (_error) {
      sessionStorage.removeItem(DAILY_AFTER_SAVE_KEY);
    }
  };

  const setupTaskCreateDailyTransfer = () => {
    if (window.location.pathname !== "/tasks/new") return;
    sessionStorage.removeItem(DAILY_AFTER_SAVE_KEY);
    const form = document.querySelector("form.form-panel");
    const actions = form?.querySelector(".form-actions");
    if (!form || !actions || actions.querySelector("[data-after-save-daily-document]")) return;

    const button = document.createElement("button");
    button.type = "submit";
    button.className = "button ghost";
    button.dataset.afterSaveDailyDocument = "true";
    button.textContent = "저장 후 일일업무 일지에 추가";
    const primary = actions.querySelector("button[type='submit']");
    actions.insertBefore(button, primary || null);

    form.addEventListener("submit", (event) => {
      if (event.submitter !== button) return;
      sessionStorage.setItem(
        DAILY_AFTER_SAVE_KEY,
        JSON.stringify({ createdAt: Date.now() }),
      );
    });
  };

  const markDailyQueryTasks = () => {
    if (window.location.pathname !== "/journals") return;
    const params = new URLSearchParams(window.location.search);
    if (params.get("compose") !== "daily") return;
    const ids = new Set(taskIdsFromQuery());
    const section = document.querySelector("[data-journal-fields='daily']");
    if (!section) return;
    section.querySelectorAll("input[name='task_ids']").forEach((checkbox) => {
      if (ids.has(String(checkbox.value))) {
        checkbox.checked = true;
        checkbox.dispatchEvent(new Event("change", { bubbles: true }));
      }
    });
    window.setTimeout(() => document.querySelector("[data-journal-compose='daily']")?.click(), 0);
  };

  const documentContext = () => {
    let match = window.location.pathname.match(/^\/meetings\/(\d+)\/edit$/);
    if (match) return { kind: "meeting", documentId: match[1], documentType: "" };
    if (window.location.pathname === "/meetings") return { kind: "meeting", documentId: "", documentType: "" };

    match = window.location.pathname.match(/^\/journals\/(\d+)\/edit$/);
    if (match) {
      const badge = document.querySelector(".journal-document-badge.major, .journal-document-badge.daily");
      const documentType = badge?.classList.contains("daily") ? "daily" : "major";
      return { kind: "journal", documentId: match[1], documentType };
    }
    if (window.location.pathname === "/journals") return { kind: "journal", documentId: "", documentType: "" };
    return null;
  };

  const stopLabelToggle = (node) => {
    ["click", "mousedown", "pointerdown"].forEach((eventName) => {
      node.addEventListener(eventName, (event) => event.stopPropagation());
    });
  };

  const createEditor = (row, checkbox) => {
    const taskId = String(checkbox.value || "");
    const editor = document.createElement("div");
    editor.className = "document-task-content-editor";
    editor.hidden = !checkbox.checked;
    editor.innerHTML = `
      <div class="document-task-content-editor-head">
        <strong>이번 문서 업무 내용</strong>
        <small>이 내용만 현재 문서에 저장되며 원본 업무 내용은 변경되지 않습니다.</small>
      </div>
      <textarea rows="3" maxlength="10000" disabled placeholder="이번 회의·주요업무·일일업무에 기록할 실제 업무 내용을 입력해 주세요."></textarea>
      <div class="document-task-content-editor-status" aria-live="polite">업무 내용을 불러오는 중...</div>
    `;
    const textarea = editor.querySelector("textarea");
    const status = editor.querySelector(".document-task-content-editor-status");
    textarea.dataset.taskId = taskId;
    row.append(editor);
    stopLabelToggle(editor);

    const syncEnabled = () => {
      editor.hidden = !checkbox.checked;
      textarea.disabled = !checkbox.checked || textarea.dataset.loaded !== "true";
    };
    checkbox.addEventListener("change", syncEnabled);
    editor._syncEnabled = syncEnabled;
    editor._textarea = textarea;
    editor._status = status;
    return editor;
  };

  const fetchEditorContents = async (rows, context, documentType) => {
    const items = rows.map((row) => {
      const checkbox = row.querySelector("input[name='task_ids']");
      if (!checkbox || !/^\d+$/.test(String(checkbox.value || ""))) return null;
      const editor = row.querySelector(".document-task-content-editor") || createEditor(row, checkbox);
      return { row, checkbox, editor, taskId: String(checkbox.value) };
    }).filter(Boolean);
    if (!items.length) return;

    const url = new URL("/document-task-content/metadata", window.location.origin);
    url.searchParams.set("kind", context.kind);
    if (context.documentId) url.searchParams.set("document_id", context.documentId);
    if (context.kind === "journal") url.searchParams.set("document_type", documentType || context.documentType || "major");
    items.forEach((item) => url.searchParams.append("task_ids", item.taskId));

    try {
      const response = await fetch(url, {
        credentials: "same-origin",
        headers: { "Accept": "application/json" },
      });
      const result = await response.json();
      if (!response.ok || !result.ok) throw new Error(result.message || "업무 내용을 불러오지 못했습니다.");

      items.forEach((item) => {
        const data = result.tasks?.[item.taskId];
        if (!data) {
          item.editor._status.textContent = "이 업무의 내용을 편집할 권한이 없습니다.";
          item.editor._status.classList.add("error");
          return;
        }
        const textarea = item.editor._textarea;
        textarea.value = data.content || "";
        textarea.name = `task_content_${item.taskId}`;
        textarea.dataset.loaded = "true";
        textarea.dataset.originalContent = data.original_content || "";
        item.editor._status.textContent = "원본 업무와 별도로 이번 문서 내용이 저장됩니다.";
        item.editor._status.classList.add("ready");
        item.editor._syncEnabled();
      });
    } catch (_error) {
      items.forEach((item) => {
        item.editor._status.textContent = "업무 내용을 불러오지 못했습니다. 원본 내용으로 저장됩니다.";
        item.editor._status.classList.add("error");
        item.editor._textarea.disabled = true;
      });
    }
  };

  const addGuidance = (container) => {
    if (!container || container.querySelector("[data-document-task-content-guide]")) return;
    const guide = document.createElement("div");
    guide.dataset.documentTaskContentGuide = "true";
    guide.className = "document-task-content-guide";
    guide.innerHTML = "<strong>업무 내용 수정 가능</strong><span>선택한 업무는 이 문서에 기록할 내용만 자유롭게 수정할 수 있습니다. 업무현황의 원본 내용은 그대로 유지됩니다.</span>";
    const selectionBar = container.querySelector(".meeting-task-selection-bar");
    if (selectionBar) selectionBar.insertAdjacentElement("afterend", guide);
    else container.prepend(guide);
  };

  const setupContentEditors = () => {
    const context = documentContext();
    if (!context) return;

    if (context.kind === "meeting") {
      const container = document.querySelector("#meeting-compose-dialog form, .meeting-edit-panel form");
      const rows = [...(container?.querySelectorAll("[data-meeting-task-row]") || [])];
      if (container && rows.length) {
        addGuidance(container.querySelector("[data-meeting-task-list]")?.parentElement || container);
        fetchEditorContents(rows, context, "");
      }
      return;
    }

    if (window.location.pathname === "/journals") {
      ["major", "daily"].forEach((documentType) => {
        const section = document.querySelector(`[data-journal-fields='${documentType}']`);
        const rows = [...(section?.querySelectorAll("[data-journal-task-row]") || [])];
        if (section && rows.length) {
          addGuidance(section.querySelector("[data-journal-task-picker]") || section);
          fetchEditorContents(rows, context, documentType);
        }
      });
    } else {
      const container = document.querySelector(".meeting-edit-panel form");
      const rows = [...(container?.querySelectorAll("[data-journal-task-row]") || [])];
      if (container && rows.length) {
        addGuidance(container.querySelector("[data-journal-task-picker]") || container);
        fetchEditorContents(rows, context, context.documentType);
      }
    }

    document.querySelectorAll("input[name='document_type']").forEach((radio) => {
      radio.addEventListener("change", () => {
        window.setTimeout(() => {
          document.querySelectorAll(".document-task-content-editor").forEach((editor) => editor._syncEnabled?.());
        }, 0);
      });
    });
  };

  document.addEventListener("DOMContentLoaded", () => {
    setupTaskListDailyTransfer();
    setupTaskCreateDailyTransfer();
    setupTaskDetailDailyTransfer();
    markDailyQueryTasks();
    setupContentEditors();
  });
})();
