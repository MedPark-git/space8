(() => {
  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

  const nl2br = (value) => escapeHtml(value || "").replace(/\r?\n/g, "<br>");
  const fieldValue = (form, name) => form.querySelector(`[name='${name}']`)?.value?.trim() || "";
  const selectedOptionText = (form, name) => {
    const select = form.querySelector(`select[name='${name}']`);
    return select?.selectedOptions?.[0]?.textContent?.trim() || "-";
  };

  const currentUserName = () => document.querySelector(".user-profile-link strong")?.textContent?.trim() || "작성자";

  const getSelectedTasks = (form) => [...form.querySelectorAll("input[name='task_ids']:checked")]
    .filter((checkbox) => !checkbox.disabled)
    .map((checkbox) => {
      const row = checkbox.closest("[data-meeting-task-row], [data-journal-task-row], label");
      return {
        title: row?.querySelector("strong")?.textContent?.trim() || `업무 #${checkbox.value}`,
        meta: row?.querySelector("small")?.textContent?.trim() || "",
        status: row?.querySelector(".status")?.textContent?.trim() || "",
        department: row?.dataset?.department || "",
      };
    });

  const getCheckedPeople = (form) => [...form.querySelectorAll("input[name='attendee_ids']:checked")]
    .map((checkbox) => checkbox.closest("label")?.textContent?.replace(/\s+/g, " ")?.trim())
    .filter(Boolean);

  const ensureStyles = () => {
    if (document.getElementById("live-document-preview-style")) return;
    const style = document.createElement("style");
    style.id = "live-document-preview-style";
    style.textContent = `
      .live-document-preview-dialog{width:min(1120px,calc(100vw - 32px));max-width:1120px;max-height:92vh;border:0;border-radius:16px;padding:0;overflow:hidden}
      .live-document-preview-dialog::backdrop{background:rgba(16,24,40,.48)}
      .live-preview-shell{display:flex;flex-direction:column;max-height:92vh;background:#f5f7fb}
      .live-preview-head{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;padding:18px 22px;background:#fff;border-bottom:1px solid #e2e8f0}
      .live-preview-head h2{margin:4px 0 2px;font-size:20px}.live-preview-head p{margin:0;color:#64748b;font-size:13px}
      .live-preview-head button{border:0;background:transparent;font-size:28px;line-height:1;cursor:pointer;color:#64748b}
      .live-preview-body{overflow:auto;padding:22px}
      .live-preview-sheet{background:#fff;border:1px solid #dce4ef;border-radius:12px;padding:24px;box-shadow:0 6px 20px rgba(15,23,42,.06)}
      .live-preview-brand{font-size:12px;font-weight:900;letter-spacing:1.5px;color:#2563eb}.live-preview-title{margin:6px 0 14px;font-size:28px;line-height:1.25}
      .live-preview-note{display:inline-block;margin-bottom:14px;padding:5px 9px;border-radius:999px;background:#eef4ff;color:#2457a7;font-size:12px;font-weight:800}
      .live-preview-meta{display:flex;flex-wrap:wrap;gap:8px 18px;padding:12px 0 16px;border-bottom:1px solid #e7ebf2;font-size:13px;color:#475569}
      .live-preview-meta b{color:#0f172a;margin-right:5px}.live-preview-section{margin-top:22px}.live-preview-section h3{font-size:16px;margin:0 0 10px}.live-preview-text{white-space:normal;line-height:1.65;background:#f8fafc;border-radius:9px;padding:12px;color:#334155;min-height:44px}
      .live-preview-table-wrap{overflow:auto}.live-preview-table{width:100%;border-collapse:collapse;min-width:720px}.live-preview-table th,.live-preview-table td{padding:10px 9px;border:1px solid #e2e8f0;text-align:left;font-size:12px;vertical-align:top}.live-preview-table th{background:#f8fafc;color:#475569}.live-preview-empty{color:#94a3b8}
      .live-preview-footer{margin-top:24px;padding-top:12px;border-top:1px solid #e7ebf2;color:#94a3b8;font-size:11px;text-align:right}
      @media(max-width:700px){.live-document-preview-dialog{width:calc(100vw - 16px)}.live-preview-body{padding:10px}.live-preview-sheet{padding:16px}.live-preview-title{font-size:22px}}
    `;
    document.head.append(style);
  };

  const ensureDialog = (kind) => {
    const id = `${kind}-live-document-preview-dialog`;
    let dialog = document.getElementById(id);
    if (dialog) return dialog;
    dialog = document.createElement("dialog");
    dialog.id = id;
    dialog.className = "live-document-preview-dialog";
    dialog.innerHTML = `
      <div class="live-preview-shell">
        <div class="live-preview-head">
          <div><span class="eyebrow">LIVE PREVIEW</span><h2>작성 중 미리보기</h2><p>저장되지 않은 현재 입력 내용을 실시간으로 확인합니다.</p></div>
          <button type="button" data-live-preview-close aria-label="미리보기 닫기">×</button>
        </div>
        <div class="live-preview-body" data-live-preview-content></div>
      </div>`;
    dialog.querySelector("[data-live-preview-close]")?.addEventListener("click", () => dialog.close());
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) dialog.close();
    });
    document.body.append(dialog);
    return dialog;
  };

  const taskTable = (tasks, includeDepartment = false) => {
    if (!tasks.length) return '<div class="live-preview-text live-preview-empty">선택한 관련 업무가 없습니다.</div>';
    return `<div class="live-preview-table-wrap"><table class="live-preview-table"><thead><tr><th>No.</th>${includeDepartment ? "<th>부서(팀)</th>" : ""}<th>업무명</th><th>업무 정보</th><th>상태</th></tr></thead><tbody>${tasks.map((task, index) => `<tr><td>${index + 1}</td>${includeDepartment ? `<td>${escapeHtml(task.department || "-")}</td>` : ""}<td><strong>${escapeHtml(task.title)}</strong></td><td>${escapeHtml(task.meta || "-")}</td><td>${escapeHtml(task.status || "-")}</td></tr>`).join("")}</tbody></table></div>`;
  };

  const textSection = (title, content) => `<section class="live-preview-section"><h3>${escapeHtml(title)}</h3><div class="live-preview-text">${content ? nl2br(content) : '<span class="live-preview-empty">작성된 내용이 없습니다.</span>'}</div></section>`;

  const renderMeeting = (form) => {
    const type = form.querySelector("input[name='document_type']:checked")?.value || "agenda";
    const isAgenda = type === "agenda";
    const label = isAgenda ? "일일 회의 아젠다" : "일일 회의 회의록";
    const meetingDate = fieldValue(form, "meeting_date") || "미지정";
    const duration = fieldValue(form, "duration_minutes") || "-";
    const title = fieldValue(form, "title") || `${meetingDate} ${label}`;
    const author = selectedOptionText(form, "author_id");
    const reporter = selectedOptionText(form, "reporter_id");
    const attendees = getCheckedPeople(form);
    const tasks = getSelectedTasks(form);
    const agendaContent = fieldValue(form, "agenda_content");
    const discussionNotes = fieldValue(form, "discussion_notes");
    const decisions = fieldValue(form, "decisions");
    const actionItems = fieldValue(form, "action_items");
    const specialNotes = fieldValue(form, "special_notes");

    return `
      <article class="live-preview-sheet">
        <div class="live-preview-brand">MEDPARK</div>
        <div class="live-preview-note">미리보기 전용 · 아직 저장되지 않은 문서</div>
        <h1 class="live-preview-title">${escapeHtml(title)}</h1>
        <div class="live-preview-meta"><span><b>문서구분</b>${escapeHtml(label)}</span><span><b>회의일자</b>${escapeHtml(meetingDate)}</span><span><b>회의시간</b>${escapeHtml(duration)}${duration === "-" ? "" : "분"}</span><span><b>작성자</b>${escapeHtml(author)}</span><span><b>보고자</b>${escapeHtml(reporter)}</span><span><b>참석자</b>${escapeHtml(attendees.join(", ") || "-")}</span></div>
        ${agendaContent ? textSection(isAgenda ? "아젠다 및 사전 공유사항" : "회의 아젠다 보충내용", agendaContent) : ""}
        <section class="live-preview-section"><h3>관련 업무</h3>${taskTable(tasks, true)}</section>
        ${textSection(isAgenda ? "상세 아젠다" : "주요 논의사항", discussionNotes)}
        ${textSection(isAgenda ? "예상 결론" : "결정사항", decisions)}
        ${textSection(isAgenda ? "추진사항" : "후속 조치사항", actionItems)}
        ${specialNotes ? textSection("특이사항", specialNotes) : ""}
        <div class="live-preview-footer">작성 중 미리보기 · 실제 저장 문서는 저장 시점의 내용을 기준으로 생성됩니다.</div>
      </article>`;
  };

  const journalTypeForForm = (form) => {
    const checked = form.querySelector("input[name='document_type']:checked")?.value;
    if (checked) return checked;
    const badge = form.querySelector(".journal-document-badge");
    if (badge?.classList.contains("daily")) return "daily";
    return "major";
  };

  const renderJournal = (form) => {
    const type = journalTypeForForm(form);
    const isMajor = type === "major";
    const label = isMajor ? "주요 업무" : "일일업무 일지";
    const workDate = fieldValue(form, "work_date") || "미지정";
    const title = fieldValue(form, "title") || `${workDate} ${label} - ${currentUserName()}`;
    const tasks = getSelectedTasks(form);
    const summary = fieldValue(form, "work_summary");
    const nextPlan = fieldValue(form, "next_plan");
    const specialNotes = fieldValue(form, "special_notes");

    return `
      <article class="live-preview-sheet">
        <div class="live-preview-brand">MEDPARK</div>
        <div class="live-preview-note">미리보기 전용 · 아직 저장되지 않은 문서</div>
        <h1 class="live-preview-title">${escapeHtml(title)}</h1>
        <div class="live-preview-meta"><span><b>문서구분</b>${escapeHtml(label)}</span><span><b>작성일</b>${escapeHtml(workDate)}</span><span><b>작성자</b>${escapeHtml(currentUserName())}</span></div>
        <section class="live-preview-section"><h3>${isMajor ? "주요 업무 현황" : "일일업무 현황"}</h3>${taskTable(tasks)}</section>
        ${textSection(isMajor ? "주요 업무 진행 요약" : "금일 진행 내용", summary)}
        ${textSection(isMajor ? "향후 추진 계획" : "익일·향후 계획", nextPlan)}
        ${specialNotes ? textSection("특이사항", specialNotes) : ""}
        <div class="live-preview-footer">작성 중 미리보기 · 실제 저장 문서는 저장 시점의 내용을 기준으로 생성됩니다.</div>
      </article>`;
  };

  const bindPreview = (form, kind) => {
    if (!form || form.dataset.liveDocumentPreviewBound) return;
    form.dataset.liveDocumentPreviewBound = "true";
    const actions = form.querySelector(".form-actions");
    if (!actions) return;

    const button = document.createElement("button");
    button.type = "button";
    button.className = "button ghost";
    button.textContent = "작성 중 미리보기";
    button.dataset.liveDocumentPreview = kind;

    const submitButton = actions.querySelector("button[type='submit']");
    if (submitButton) actions.insertBefore(button, submitButton);
    else actions.append(button);

    const dialog = ensureDialog(kind);
    const content = dialog.querySelector("[data-live-preview-content]");
    const render = () => {
      if (!content) return;
      content.innerHTML = kind === "meeting" ? renderMeeting(form) : renderJournal(form);
    };

    button.addEventListener("click", () => {
      render();
      if (!dialog.open) dialog.showModal();
    });
    form.addEventListener("input", () => { if (dialog.open) render(); });
    form.addEventListener("change", () => { if (dialog.open) render(); });
  };

  const initLiveDocumentPreview = () => {
    ensureStyles();
    document.querySelectorAll("[data-meeting-document-form]").forEach((form) => bindPreview(form, "meeting"));
    document.querySelectorAll("[data-journal-document-form]").forEach((form) => bindPreview(form, "journal"));

    if (/^\/journals\/\d+\/edit\/?$/.test(window.location.pathname)) {
      const journalEditForm = document.querySelector(".meeting-edit-panel form");
      if (journalEditForm) bindPreview(journalEditForm, "journal");
    }
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initLiveDocumentPreview);
  else initLiveDocumentPreview();
})();
