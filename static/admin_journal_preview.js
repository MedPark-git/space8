(() => {
  if (document.body?.dataset.effectiveAdmin !== "true") return;
  if (window.location.pathname !== "/journals") return;

  const dialog = document.querySelector("#journal-preview-dialog");
  const content = dialog?.querySelector("[data-journal-preview-content]");
  if (!dialog || !content) return;

  // 관리자 미리보기는 기존 Flask 라우트(/journals/<id>/preview)만 사용한다.
  // legacy app.js가 같은 버튼에 중복 바인딩하지 않도록 먼저 점유한다.
  dialog.dataset.previewBound = "admin-original-route-controller";

  const bindClose = (root) => {
    root.querySelectorAll("[data-close]").forEach((button) => {
      if (button.dataset.adminCloseBound) return;
      button.dataset.adminCloseBound = "true";
      button.addEventListener("click", () => dialog.close());
    });
  };

  const bindPrint = (root) => {
    root.querySelectorAll("[data-print-journal]").forEach((button) => {
      if (button.dataset.adminPrintBound) return;
      button.dataset.adminPrintBound = "true";
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

  const loadPreview = async (url) => {
    const targetUrl = String(url || "");
    content.innerHTML = '<div class="meeting-preview-loading"><p>업무일지를 불러오는 중입니다.</p></div>';
    if (!dialog.open) dialog.showModal();

    let status = 0;
    try {
      const response = await fetch(targetUrl, {
        credentials: "same-origin",
        cache: "no-store",
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          "X-MedPark-Admin-Preview": "1",
        },
      });
      status = response.status;
      const body = await response.text();
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      content.innerHTML = body;
      bindClose(content);
      bindPrint(content);
    } catch (error) {
      const detail = status ? `HTTP ${status}` : (error?.message || "네트워크 오류");
      content.innerHTML = `<div class="meeting-preview-error"><strong>업무일지를 불러오지 못했습니다.</strong><p>오류코드: ${detail}</p><p>기존 업무일지 상세보기 경로에서 오류가 발생했습니다.</p><button class="button ghost" type="button" data-close>닫기</button></div>`;
      bindClose(content);
    }
  };

  document.querySelectorAll("[data-journal-preview]").forEach((button) => {
    button.dataset.previewBound = "admin-original-route-controller";
    button.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopImmediatePropagation();
      loadPreview(button.dataset.journalPreview);
    }, true);
  });

  const autoPreview = String(dialog.dataset.autoPreview || "");
  if (autoPreview) {
    dialog.dataset.autoPreview = "";
    loadPreview(autoPreview);
    const currentUrl = new URL(window.location.href);
    currentUrl.searchParams.delete("open");
    window.history.replaceState(null, "", currentUrl);
  }
})();
