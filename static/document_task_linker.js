(() => {
  const AFTER_SAVE_KEY = "medpark-task-after-save-document";

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

  const buildDocumentUrl = (kind, taskIds) => {
    const url = new URL(kind === "meeting" ? "/meetings" : "/journals", window.location.origin);
    url.searchParams.set("compose", kind === "meeting" ? "agenda" : "major");
    taskIds.forEach((id) => url.searchParams.append("task_ids", String(id)));
    return `${url.pathname}${url.search}`;
  };

  const selectedTaskIds = (root = document) => {
    const ids = [];
    const businessKeys = new Set();
    root.querySelectorAll("[data-task-check]:checked:not(:disabled)").forEach((checkbox) => {
      const value = checkbox.value;
      if (!/^\d+$/.test(value)) return;
      const row = checkbox.closest("tr");
      const category = (row?.querySelector(".task-category-path")?.textContent || "")
        .replace(/\s+/g, " ")
        .trim()
        .toLocaleLowerCase("ko");
      const title = (row?.querySelector(".task-title")?.textContent || "")
        .replace(/\s+/g, " ")
        .trim()
        .toLocaleLowerCase("ko");
      const businessKey = category && title ? `${category}|${title}` : `task:${value}`;
      if (businessKeys.has(businessKey)) return;
      businessKeys.add(businessKey);
      ids.push(value);
    });
    return ids;
  };

  const navigateWithSelectedTasks = (kind, root = document) => {
    const ids = selectedTaskIds(root);
    if (!ids.length) {
      window.alert("추가할 업무를 먼저 선택해 주세요.");
      return;
    }
    window.location.assign(buildDocumentUrl(kind, ids));
  };

  const makeActionButton = (label, className, onClick) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = className;
    button.textContent = label;
    button.addEventListener("click", onClick);
    return button;
  };

  const setupTaskListDocumentActions = () => {
    if (window.location.pathname !== "/tasks") return;
    sessionStorage.removeItem(AFTER_SAVE_KEY);
    const actionBar = document.querySelector(".task-bulk-actions");
    if (!actionBar || actionBar.dataset.documentLinkerBound) return;
    actionBar.dataset.documentLinkerBound = "true";

    const meetingButton = makeActionButton(
      "일일회의에 추가",
      "button ghost small",
      () => navigateWithSelectedTasks("meeting"),
    );
    const majorButton = makeActionButton(
      "주요 업무 문서에 추가",
      "button major small",
      () => navigateWithSelectedTasks("major"),
    );
    meetingButton.dataset.documentBulkMeeting = "true";
    majorButton.dataset.documentBulkMajor = "true";
    meetingButton.disabled = true;
    majorButton.disabled = true;
    actionBar.prepend(majorButton);
    actionBar.prepend(meetingButton);

    const updateButtons = () => {
      const count = selectedTaskIds().length;
      meetingButton.disabled = count === 0;
      majorButton.disabled = count === 0;
      meetingButton.textContent = count ? `선택 ${count}건 일일회의에 추가` : "일일회의에 추가";
      majorButton.textContent = count ? `선택 ${count}건 주요 업무 문서에 추가` : "주요 업무 문서에 추가";
    };
    document.querySelectorAll("[data-task-check]:not(:disabled)").forEach((checkbox) => {
      checkbox.addEventListener("change", updateButtons);
    });
    document.querySelector("[data-check-all]")?.addEventListener("change", () => window.setTimeout(updateButtons, 0));
    updateButtons();

    document.querySelectorAll("[data-task-check]").forEach((checkbox) => {
      const taskId = checkbox.value;
      if (!/^\d+$/.test(taskId)) return;
      const row = checkbox.closest("tr");
      const managementCell = row?.querySelector("td:last-child");
      if (!managementCell || managementCell.querySelector("[data-row-document-actions]")) return;
      const actions = document.createElement("div");
      actions.dataset.rowDocumentActions = "true";
      actions.className = "button-row";
      actions.style.marginTop = "6px";
      const meetingLink = document.createElement("a");
      meetingLink.className = "button ghost small";
      meetingLink.textContent = "회의 추가";
      meetingLink.href = buildDocumentUrl("meeting", [taskId]);
      const majorLink = document.createElement("a");
      majorLink.className = "button ghost small";
      majorLink.textContent = "주요 업무 추가";
      majorLink.href = buildDocumentUrl("major", [taskId]);
      actions.append(meetingLink, majorLink);
      managementCell.append(actions);
    });
  };

  const setupTaskDetailDocumentActions = () => {
    const match = window.location.pathname.match(/^\/tasks\/(\d+)$/);
    if (!match) return;
    const heading = document.querySelector(".page-heading");
    if (!heading || heading.querySelector("[data-detail-document-actions]")) return;
    if ((heading.querySelector("h1")?.textContent || "").includes("비공개 업무")) return;
    const taskId = match[1];
    let actions = heading.querySelector(".button-row");
    if (!actions) {
      actions = document.createElement("div");
      actions.className = "button-row";
      heading.append(actions);
    }
    const wrap = document.createElement("span");
    wrap.dataset.detailDocumentActions = "true";
    wrap.className = "button-row";
    const meeting = document.createElement("a");
    meeting.className = "button ghost";
    meeting.href = buildDocumentUrl("meeting", [taskId]);
    meeting.textContent = "일일회의에 추가";
    const major = document.createElement("a");
    major.className = "button major";
    major.href = buildDocumentUrl("major", [taskId]);
    major.textContent = "주요 업무 문서에 추가";
    wrap.append(meeting, major);
    actions.prepend(wrap);

    try {
      const raw = sessionStorage.getItem(AFTER_SAVE_KEY);
      if (!raw) return;
      const intent = JSON.parse(raw);
      sessionStorage.removeItem(AFTER_SAVE_KEY);
      if (!intent?.kind || Date.now() - Number(intent.createdAt || 0) > 5 * 60 * 1000) return;
      window.location.replace(buildDocumentUrl(intent.kind, [taskId]));
    } catch (_error) {
      sessionStorage.removeItem(AFTER_SAVE_KEY);
    }
  };

  const setupTaskCreateAfterSaveActions = () => {
    if (window.location.pathname !== "/tasks/new") return;
    sessionStorage.removeItem(AFTER_SAVE_KEY);
    const form = document.querySelector("form.form-panel");
    const actions = form?.querySelector(".form-actions");
    if (!form || !actions || form.dataset.afterSaveDocumentBound) return;
    form.dataset.afterSaveDocumentBound = "true";

    const meeting = document.createElement("button");
    meeting.type = "submit";
    meeting.className = "button ghost";
    meeting.dataset.afterSaveDocument = "meeting";
    meeting.textContent = "저장 후 일일회의에 추가";
    const major = document.createElement("button");
    major.type = "submit";
    major.className = "button major";
    major.dataset.afterSaveDocument = "major";
    major.textContent = "저장 후 주요 업무 문서에 추가";
    const primarySave = actions.querySelector("button[type='submit']");
    actions.insertBefore(meeting, primarySave || null);
    actions.insertBefore(major, primarySave || null);

    form.addEventListener("submit", (event) => {
      const kind = event.submitter?.dataset.afterSaveDocument;
      if (!kind) {
        sessionStorage.removeItem(AFTER_SAVE_KEY);
        return;
      }
      sessionStorage.setItem(AFTER_SAVE_KEY, JSON.stringify({ kind, createdAt: Date.now() }));
    });
  };

  const markQueryTasksChecked = (root) => {
    const ids = new Set(taskIdsFromQuery());
    if (!ids.size) return;
    root.querySelectorAll("input[name='task_ids']").forEach((checkbox) => {
      if (ids.has(String(checkbox.value))) {
        checkbox.checked = true;
        checkbox.dispatchEvent(new Event("change", { bubbles: true }));
      }
    });
  };

  const replaceEmptyMessage = (root, text) => {
    root.querySelectorAll(".select-task-list > .empty").forEach((item) => {
      if (!item.hasAttribute("data-task-filter-empty") && !item.hasAttribute("data-journal-task-empty")) {
        item.textContent = text;
      }
    });
  };

  const setupMeetingCompose = () => {
    const dialog = document.querySelector("#meeting-compose-dialog");
    if (!dialog || dialog.dataset.externalTaskSourceBound) return;
    dialog.dataset.externalTaskSourceBound = "true";
    markQueryTasksChecked(dialog);

    dialog.querySelector(".meeting-task-filters")?.setAttribute("hidden", "");
    const headText = dialog.querySelector(".meeting-task-head p");
    if (headText) {
      headText.textContent = "각 부서(팀) 업무 현황 또는 업무등록에서 선택한 업무만 관련 업무로 추가됩니다.";
    }
    const composeText = dialog.querySelector(".meeting-compose-head p");
    if (composeText) {
      composeText.textContent = "관련 업무는 업무 현황·업무등록에서 먼저 선택하며, 이 작성창은 선택된 업무만 표시합니다.";
    }
    replaceEmptyMessage(
      dialog,
      "아직 추가된 관련 업무가 없습니다. 각 부서(팀) 업무 현황 또는 업무등록에서 업무를 선택해 추가해 주세요.",
    );

    const params = new URLSearchParams(window.location.search);
    const compose = params.get("compose");
    if (compose === "agenda" || compose === "minutes") {
      window.setTimeout(() => document.querySelector(`[data-meeting-compose='${compose}']`)?.click(), 0);
    }
  };

  const setupMajorJournalCompose = () => {
    const dialog = document.querySelector("#journal-compose-dialog");
    if (!dialog || dialog.dataset.externalTaskSourceBound) return;
    dialog.dataset.externalTaskSourceBound = "true";
    const majorSection = dialog.querySelector("[data-journal-fields='major']");
    if (majorSection) {
      markQueryTasksChecked(majorSection);
      majorSection.querySelector(".journal-task-filter")?.setAttribute("hidden", "");
      const headText = majorSection.querySelector(".meeting-task-head p");
      if (headText) {
        headText.textContent = "각 부서(팀) 업무 현황 또는 업무등록에서 선택한 업무만 관련 업무로 추가됩니다.";
      }
      replaceEmptyMessage(
        majorSection,
        "아직 추가된 관련 업무가 없습니다. 각 부서(팀) 업무 현황 또는 업무등록에서 업무를 선택해 추가해 주세요.",
      );
    }
    const composeText = dialog.querySelector(".meeting-compose-head p");
    if (composeText) {
      composeText.textContent = "주요 업무는 전사 등록업무에서 선택하고, 일일업무 일지는 기존처럼 본인 담당 업무 기준으로 작성합니다.";
    }

    const params = new URLSearchParams(window.location.search);
    if (params.get("compose") === "major") {
      window.setTimeout(() => document.querySelector("[data-journal-compose='major']")?.click(), 0);
    }
  };

  document.addEventListener("DOMContentLoaded", () => {
    setupTaskListDocumentActions();
    setupTaskCreateAfterSaveActions();
    setupTaskDetailDocumentActions();
    setupMeetingCompose();
    setupMajorJournalCompose();
  });
})();
