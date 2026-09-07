(() => {
  const CREATE_PATH = "/tasks/new";
  const EDIT_PATH_RE = /^\/tasks\/\d+\/edit\/?$/;

  const isTaskEditorUrl = (href) => {
    try {
      const url = new URL(href, window.location.origin);
      return url.origin === window.location.origin && (url.pathname === CREATE_PATH || EDIT_PATH_RE.test(url.pathname));
    } catch (_error) {
      return false;
    }
  };

  const ensureStyles = () => {
    if (document.getElementById("task-editor-modal-style")) return;
    const style = document.createElement("style");
    style.id = "task-editor-modal-style";
    style.textContent = `
      .task-editor-modal{width:min(1080px,calc(100vw - 28px));max-height:94vh;border:0;border-radius:16px;padding:0;overflow:hidden;background:#f5f7fb;box-shadow:0 24px 60px rgba(15,23,42,.24)}
      .task-editor-modal::backdrop{background:rgba(15,23,42,.52)}
      .task-editor-modal-shell{display:flex;flex-direction:column;max-height:94vh}
      .task-editor-modal-head{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;padding:20px 24px;background:#fff;border-bottom:1px solid #e2e8f0}
      .task-editor-modal-head h2{margin:4px 0 2px;font-size:24px;line-height:1.25}.task-editor-modal-head p{margin:0;color:#64748b;font-size:13px}
      .task-editor-modal-close{border:0;background:transparent;color:#64748b;font-size:30px;line-height:1;cursor:pointer;padding:0 2px}
      .task-editor-modal-body{overflow:auto;padding:20px}
      .task-editor-modal-loading,.task-editor-modal-error{padding:38px 20px;text-align:center;background:#fff;border:1px solid #e2e8f0;border-radius:12px}
      .task-editor-modal-error strong{display:block;margin-bottom:8px;color:#b42318}.task-editor-modal-error p{margin:0 0 14px;color:#64748b}
      .task-editor-modal .form-panel{margin:0;box-shadow:none}
      .task-editor-modal .form-panel>.form-section:first-child{margin-top:0}
      .task-editor-modal-status{display:none;margin:0 0 14px;padding:10px 12px;border-radius:9px;font-size:13px}
      .task-editor-modal-status.error{display:block;background:#fff1f0;color:#b42318;border:1px solid #fecdca}
      .task-editor-modal-status.info{display:block;background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe}
      .task-editor-modal .form-actions{position:sticky;bottom:-20px;background:#fff;padding:14px 0 2px;margin-top:18px;border-top:1px solid #e2e8f0;z-index:2}
      @media(max-width:760px){.task-editor-modal{width:calc(100vw - 14px);max-height:96vh}.task-editor-modal-head{padding:16px}.task-editor-modal-body{padding:10px}.task-editor-modal .form-grid{grid-template-columns:1fr}.task-editor-modal .span-2{grid-column:auto}}
    `;
    document.head.append(style);
  };

  const ensureDialog = () => {
    let dialog = document.getElementById("task-editor-modal");
    if (dialog) return dialog;

    dialog = document.createElement("dialog");
    dialog.id = "task-editor-modal";
    dialog.className = "task-editor-modal";
    dialog.innerHTML = `
      <div class="task-editor-modal-shell">
        <div class="task-editor-modal-head">
          <div><span class="eyebrow">TASK EDITOR</span><h2 data-task-editor-title>업무 등록</h2><p>기존 업무 등록·수정 기능을 현재 화면에서 처리합니다.</p></div>
          <button type="button" class="task-editor-modal-close" aria-label="닫기">×</button>
        </div>
        <div class="task-editor-modal-body">
          <div class="task-editor-modal-status" data-task-editor-status></div>
          <div data-task-editor-content></div>
        </div>
      </div>`;
    document.body.append(dialog);

    const close = () => dialog.close();
    dialog.querySelector(".task-editor-modal-close")?.addEventListener("click", close);
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) close();
    });
    dialog.addEventListener("cancel", (event) => {
      event.preventDefault();
      close();
    });
    return dialog;
  };

  const setStatus = (dialog, message = "", tone = "") => {
    const status = dialog.querySelector("[data-task-editor-status]");
    if (!status) return;
    status.textContent = message;
    status.className = "task-editor-modal-status";
    if (tone) status.classList.add(tone);
  };

  const syncCatalog = (sourceDoc) => {
    const incoming = sourceDoc.getElementById("work-category-catalog");
    if (!incoming) return;
    let current = document.getElementById("work-category-catalog");
    if (!current) {
      current = document.createElement("script");
      current.type = "application/json";
      current.id = "work-category-catalog";
      document.body.append(current);
    }
    current.textContent = incoming.textContent || "[]";
  };

  const prepareForm = (form, endpoint) => {
    form.dataset.taskEditorEndpoint = endpoint;

    const formGrid = form.querySelector(".form-grid");
    const categoryBlock = formGrid?.querySelector(".work-category-form");
    const titleInput = formGrid?.querySelector("input[name='title']");
    const titleLabel = titleInput?.closest("label");
    if (formGrid && categoryBlock && titleLabel) formGrid.insertBefore(categoryBlock, titleLabel);

    if (titleLabel) {
      titleLabel.childNodes.forEach((node) => {
        if (node.nodeType === Node.TEXT_NODE && node.nodeValue.includes("업무 제목")) {
          node.nodeValue = node.nodeValue.replace("업무 제목", "업무명");
        }
      });
    }

    const cancelLink = form.querySelector(".form-actions a.button");
    if (cancelLink) {
      const cancelButton = document.createElement("button");
      cancelButton.type = "button";
      cancelButton.className = cancelLink.className;
      cancelButton.textContent = "취소";
      cancelButton.dataset.taskEditorCancel = "1";
      cancelLink.replaceWith(cancelButton);
    }

    if (typeof initWorkCategoryForm === "function") initWorkCategoryForm(form);
    if (typeof initDialogs === "function") initDialogs(form);
  };

  const renderReturnedForm = (dialog, html, endpoint) => {
    const sourceDoc = new DOMParser().parseFromString(html, "text/html");
    syncCatalog(sourceDoc);
    const nextForm = sourceDoc.querySelector("form.form-panel");
    if (!nextForm) return false;

    const content = dialog.querySelector("[data-task-editor-content]");
    content.replaceChildren(nextForm);
    prepareForm(nextForm, endpoint);

    const flashMessages = [...sourceDoc.querySelectorAll(".flash")].map((node) => node.textContent.trim()).filter(Boolean);
    if (flashMessages.length) setStatus(dialog, flashMessages.join(" · "), "error");
    return true;
  };

  const openEditor = async (href) => {
    ensureStyles();
    const dialog = ensureDialog();
    const content = dialog.querySelector("[data-task-editor-content]");
    const title = dialog.querySelector("[data-task-editor-title]");
    const endpoint = new URL(href, window.location.origin).pathname;

    title.textContent = endpoint === CREATE_PATH ? "업무 등록" : "업무 수정";
    setStatus(dialog, "");
    content.innerHTML = '<div class="task-editor-modal-loading"><p>업무 입력 화면을 불러오는 중입니다.</p></div>';
    if (!dialog.open) dialog.showModal();

    try {
      const response = await fetch(href, {
        credentials: "same-origin",
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });
      if (response.url.includes("/login")) {
        window.location.assign(response.url);
        return;
      }
      if (!response.ok) throw new Error(`업무 입력 화면 조회 실패 (HTTP ${response.status})`);
      const html = await response.text();
      if (!renderReturnedForm(dialog, html, endpoint)) throw new Error("업무 입력 폼을 찾을 수 없습니다.");
    } catch (error) {
      content.innerHTML = `<div class="task-editor-modal-error"><strong>업무 입력 화면을 불러오지 못했습니다.</strong><p>${String(error.message || error)}</p><a class="button ghost" href="${href}">기존 화면으로 열기</a></div>`;
    }
  };

  const submitEditor = async (form, dialog) => {
    const endpoint = form.dataset.taskEditorEndpoint || CREATE_PATH;
    const submitButton = form.querySelector("button[type='submit']");
    const originalLabel = submitButton?.textContent || "저장";
    if (submitButton) {
      submitButton.disabled = true;
      submitButton.textContent = "저장 중...";
    }
    setStatus(dialog, "저장 중입니다.", "info");

    try {
      const response = await fetch(endpoint, {
        method: "POST",
        body: new FormData(form),
        credentials: "same-origin",
        headers: { "X-Requested-With": "XMLHttpRequest" },
        redirect: "follow",
      });
      if (response.url.includes("/login")) {
        window.location.assign(response.url);
        return;
      }

      const html = await response.text();
      if (response.redirected && response.ok && !response.url.endsWith(endpoint)) {
        dialog.close();
        window.location.reload();
        return;
      }

      if (!response.ok) {
        if (!renderReturnedForm(dialog, html, endpoint)) {
          throw new Error(`저장 실패 (HTTP ${response.status})`);
        }
        setStatus(dialog, `저장 내용을 확인해 주세요. (HTTP ${response.status})`, "error");
        return;
      }

      if (renderReturnedForm(dialog, html, endpoint)) {
        setStatus(dialog, "입력 내용을 확인해 주세요.", "error");
        return;
      }

      dialog.close();
      window.location.reload();
    } catch (error) {
      setStatus(dialog, String(error.message || error), "error");
    } finally {
      if (submitButton?.isConnected) {
        submitButton.disabled = false;
        submitButton.textContent = originalLabel;
      }
    }
  };

  document.addEventListener("click", (event) => {
    const cancel = event.target.closest("[data-task-editor-cancel]");
    if (cancel) {
      event.preventDefault();
      cancel.closest("dialog")?.close();
      return;
    }

    const link = event.target.closest("a[href]");
    if (!link || !isTaskEditorUrl(link.href)) return;
    if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button === 1) return;
    event.preventDefault();
    openEditor(link.href);
  });

  document.addEventListener("submit", (event) => {
    const form = event.target.closest("#task-editor-modal form.form-panel");
    if (!form) return;
    event.preventDefault();
    submitEditor(form, ensureDialog());
  });
})();
