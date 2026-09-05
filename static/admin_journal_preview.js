(() => {
  if (document.body?.dataset.effectiveAdmin !== "true") return;
  if (window.location.pathname !== "/journals") return;

  const dialog = document.querySelector("#journal-preview-dialog");
  const content = dialog?.querySelector("[data-journal-preview-content]");
  if (!dialog || !content) return;

  // 관리자 업무일지는 기존 /journals/<id>/preview 경로만 사용합니다.
  // app.js의 기존 미리보기 초기화는 이 다이얼로그에 바인딩되지 않도록 차단합니다.
  dialog.dataset.previewBound = "admin-existing-route-controller";

  const previewUrl = (value) => {
    const match = String(value || "").match(/\/(?:admin-safe\/)?journals\/(\d+)\/preview/);
    return match ? `/journals/${match[1]}/preview` : String(value || "");
  };

  const bindLoadedContent = () => {
    try { initDialogs(content); } catch (_error) {}
    try { initMeetingImageDownload(content); } catch (_error) {}
    try { initMeetingPrint(content); } catch (_error) {}
  };

  const loadPreview = async (url) => {
    const targetUrl = previewUrl(url);
    content.innerHTML = '<div class="meeting-preview-loading"><p>업무일지를 불러오는 중입니다.</p></div>';
    if (!dialog.open) dialog.showModal();

    let status = 0;
    try {
      const response = await fetch(targetUrl, {
        credentials: "same-origin",
        cache: "no-store",
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          "X-MedPark-Admin-Preview": "existing-route",
        },
      });
      status = response.status;
      const body = await response.text();
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      content.innerHTML = body;
      bindLoadedContent();
    } catch (error) {
      const detail = status ? `HTTP ${status}` : (error?.message || "네트워크 오류");
      content.innerHTML = `<div class="meeting-preview-error"><strong>업무일지를 불러오지 못했습니다.</strong><p>오류코드: ${detail}</p><p>기존 업무일지 상세보기 경로에서 오류가 발생했습니다.</p><button class="button ghost" type="button" data-close>닫기</button></div>`;
      try { initDialogs(content); } catch (_error) {}
    }
  };

  document.querySelectorAll("[data-journal-preview]").forEach((button) => {
    button.dataset.previewBound = "admin-existing-route-controller";
    button.dataset.journalPreview = previewUrl(button.dataset.journalPreview);
    button.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopImmediatePropagation();
      loadPreview(button.dataset.journalPreview);
    }, true);
  });

  const autoPreview = previewUrl(dialog.dataset.autoPreview || "");
  if (autoPreview) {
    dialog.dataset.autoPreview = "";
    loadPreview(autoPreview);
    const currentUrl = new URL(window.location.href);
    currentUrl.searchParams.delete("open");
    window.history.replaceState(null, "", currentUrl);
  }
})();
