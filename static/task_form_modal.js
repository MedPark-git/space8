(() => {
  const CREATE_PATH = "/tasks/new";
  const EDIT_PATTERN = /^\/tasks\/\d+\/edit\/?$/;

  const ensureStyles = () => {
    if (document.getElementById("task-form-modal-style")) return;
    const style = document.createElement("style");
    style.id = "task-form-modal-style";
    style.textContent = `
      .task-form-modal{width:min(1120px,calc(100vw - 28px));max-width:1120px;max-height:94vh;border:0;border-radius:16px;padding:0;overflow:hidden}
      .task-form-modal::backdrop{background:rgba(15,23,42,.5)}
      .task-form-modal-shell{display:flex;flex-direction:column;max-height:94vh;background:#f5f7fb}
      .task-form-modal-head{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;padding:18px 22px;background:#fff;border-bottom:1px solid #e2e8f0}
      .task-form-modal-head h2{margin:4px 0 2px;font-size:24px}.task-form-modal-head p{margin:0;color:#64748b;font-size:13px}
      .task-form-modal-close{border:0;background:transparent;font-size:30px;line-height:1;color:#64748b;cursor:pointer}
      .task-form-modal-body{overflow:auto;padding:18px 20px 24px}
      .task-form-modal-body .form-panel{margin:0;box-shadow:none}
      .task-form-modal-loading,.task-form-modal-error{padding:42px 20px;text-align:center;background:#fff;border:1px solid #e2e8f0;border-radius:12px}
      .task-form-modal-error strong{display:block;margin-bottom:8px;color:#b42318}.task-form-modal-error p{color:#64748b}
      .task-form-modal .modal-flash{margin:0 0 12px;padding:10px 12px;border-radius:8px;background:#fff4e5;color:#9a6700;font-size:13px}
      @media(max-width:720px){.task-form-modal{width:calc(100vw - 12px)}.task-form-modal-body{padding:10px}.task-form-modal-head{padding:14px 16px}}
    `;
    document.head.append(style);
  };

  const createDialog = () => {
    let dialog = document.getElementById("task-form-modal");
    if (dialog) return dialog;
    dialog = document.createElement("dialog");
    dialog.id = "task-form-modal";
    dialog.className = "task-form-modal";
    dialog.innerHTML = `
      <div class="task-form-modal-shell">
        <div class="task-form-modal-head">
          <div><span class="eyebrow">TASK EDITOR</span><h2 data-task-modal-title>업무 등록</h2><p>기존 업무 저장 기능을 그대로 사용합니다.</p></div>
          <button type="button" class="task-form-modal-close" aria-label="닫기">×</button>
        </div>
        <div class="task-form-modal-body" data-task-modal-body></div>
      </div>`;
    dialog.querySelector(".task-form-modal-close")?.addEventListener("click", () => dialog.close());
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) dialog.close();
    });
    document.body.append(dialog);
    return dialog;
  };

  const parseCatalog = (doc) => {
    const node = doc.getElementById("work-category-catalog");
    if (!node) return [];
    try { return JSON.parse(node.textContent || "[]"); } catch (_error) { return []; }
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

  const initCategoryForm = (form, catalog) => {
    const section = form.querySelector("[data-work-category-form]");
    if (!section) return;
    const department = section.querySelector("[data-work-department]");
    const middle = section.querySelector("[data-work-middle]");
    const small = section.querySelector("[data-work-category]");
    const initialCategoryId = section.dataset.selectedCategory || "";
    const initialCategory = catalog.find((item) => String(item.id) === String(initialCategoryId));

    const categoriesForDepartment = () => catalog.filter(
      (item) => String(item.department_id) === String(department?.value || "")
    );
    const rebuildSmall = (selectedId = "") => {
      const items = categoriesForDepartment()
        .filter((item) => item.middle_name === middle?.value)
        .map((item) => ({ value: item.id, label: item.small_name || "미분류" }));
      replaceOptions(small, items, "미분류", selectedId);
    };
    const rebuildMiddle = (selectedMiddle = "", selectedId = "") => {
      const names = [...new Set(categoriesForDepartment().map((item) => item.middle_name).filter(Boolean))];
      replaceOptions(middle, names.map((name) => ({ value: name, label: name })), "미분류", selectedMiddle);
      rebuildSmall(selectedId);
    };

    department?.addEventListener("change", () => rebuildMiddle());
    middle?.addEventListener("change", () => rebuildSmall());
    rebuildMiddle(initialCategory?.middle_name || "", initialCategoryId);
  };

  const normalizeTaskForm = (form, catalog, dialog) => {
    form.querySelectorAll("label").forEach((label) => {
      label.childNodes.forEach((node) => {
        if (node.nodeType === Node.TEXT_NODE && node.nodeValue.includes("업무 제목")) {
          node.nodeValue = node.nodeValue.replace("업무 제목", "업무명");
        }
      });
    });

    const grid = form.querySelector(".form-grid");
    const categoryBlock = grid?.querySelector(".work-category-form");
    const titleLabel = grid?.querySelector('input[name="title"]')?.closest("label");
    if (grid && categoryBlock && titleLabel) grid.insertBefore(categoryBlock, titleLabel);

    const cancel = form.querySelector(".form-actions a.button.ghost");
    if (cancel) {
      cancel.addEventListener("click", (event) => {
        event.preventDefault();
        dialog.close();
      });
    }
    initCategoryForm(form, catalog);
  };

  const getRouteType = (href) => {
    let url;
    try { url = new URL(href, window.location.origin); } catch (_error) { return null; }
    if (url.origin !== window.location.origin) return null;
    if (url.pathname === CREATE_PATH) return "create";
    if (EDIT_PATTERN.test(url.pathname)) return "edit";
    return null;
  };

  const renderError = (body, message, fallbackUrl) => {
    body.innerHTML = `<div class="task-form-modal-error"><strong>업무 화면을 불러오지 못했습니다.</strong><p>${String(message || "잠시 후 다시 시도해 주세요.")}</p><a class="button primary" href="${fallbackUrl}">기존 화면으로 열기</a></div>`;
  };

  const init = () => {
    ensureStyles();
    const dialog = createDialog();
    const body = dialog.querySelector("[data-task-modal-body]");
    const title = dialog.querySelector("[data-task-modal-title]");
    let sourceUrl = "";
    let routeType = "create";

    const bindFormSubmit = (form, catalog) => {
      normalizeTaskForm(form, catalog, dialog);
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const submit = event.submitter || form.querySelector('button[type="submit"]');
        if (submit) submit.disabled = true;
        try {
          const response = await fetch(sourceUrl, {
            method: "POST",
            body: new FormData(form),
            credentials: "same-origin",
            headers: { "X-Requested-With": "XMLHttpRequest" },
            redirect: "follow",
          });
          const finalUrl = new URL(response.url, window.location.origin);
          if (finalUrl.pathname === "/login") {
            window.location.assign(response.url);
            return;
          }
          const html = await response.text();
          if (!response.ok) throw new Error(`저장 중 오류가 발생했습니다. (HTTP ${response.status})`);

          if (response.redirected && finalUrl.pathname !== new URL(sourceUrl, window.location.origin).pathname) {
            dialog.close();
            window.location.reload();
            return;
          }

          const nextDoc = new DOMParser().parseFromString(html, "text/html");
          const nextForm = nextDoc.querySelector("form.panel.form-panel");
          if (!nextForm) {
            dialog.close();
            window.location.reload();
            return;
          }
          const flash = nextDoc.querySelector(".flash.error, .flash.warning, .flash.info");
          body.replaceChildren();
          if (flash) {
            const notice = document.createElement("div");
            notice.className = "modal-flash";
            notice.textContent = flash.textContent.trim();
            body.append(notice);
          }
          const imported = document.importNode(nextForm, true);
          body.append(imported);
          bindFormSubmit(imported, parseCatalog(nextDoc));
        } catch (error) {
          window.alert(error.message || "업무 저장 중 오류가 발생했습니다.");
        } finally {
          if (submit) submit.disabled = false;
        }
      });
    };

    const openTaskModal = async (href, type) => {
      sourceUrl = new URL(href, window.location.origin).href;
      routeType = type;
      title.textContent = type === "edit" ? "업무 수정" : "업무 등록";
      body.innerHTML = '<div class="task-form-modal-loading">업무 화면을 불러오는 중입니다.</div>';
      if (!dialog.open) dialog.showModal();
      try {
        const response = await fetch(sourceUrl, {
          credentials: "same-origin",
          headers: { "X-Requested-With": "XMLHttpRequest" },
        });
        if (new URL(response.url, window.location.origin).pathname === "/login") {
          window.location.assign(response.url);
          return;
        }
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const doc = new DOMParser().parseFromString(await response.text(), "text/html");
        const form = doc.querySelector("form.panel.form-panel");
        if (!form) throw new Error("업무 입력 폼을 찾을 수 없습니다.");
        body.replaceChildren();
        const imported = document.importNode(form, true);
        body.append(imported);
        bindFormSubmit(imported, parseCatalog(doc));
        imported.querySelector('input[name="title"]')?.focus();
      } catch (error) {
        renderError(body, error.message, sourceUrl);
      }
    };

    document.addEventListener("click", (event) => {
      if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const link = event.target.closest("a[href]");
      if (!link || link.target === "_blank" || link.hasAttribute("download")) return;
      const type = getRouteType(link.href);
      if (!type) return;
      const targetPath = new URL(link.href, window.location.origin).pathname;
      if (window.location.pathname === targetPath) return;
      event.preventDefault();
      openTaskModal(link.href, type);
    });
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
