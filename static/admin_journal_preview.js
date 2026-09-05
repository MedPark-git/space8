(() => {
  if (document.body?.dataset.effectiveAdmin !== "true") return;
  if (window.location.pathname !== "/journals") return;

  const dialog = document.querySelector("#journal-preview-dialog");
  const content = dialog?.querySelector("[data-journal-preview-content]");
  if (!dialog || !content) return;

  // Prevent the legacy journal preview initializer from binding to this dialog.
  dialog.dataset.previewBound = "admin-safe-controller";

  const safeUrl = (value) => {
    const match = String(value || "").match(/\/(?:admin-safe\/)?journals\/(\d+)\/preview/);
    return match ? `/admin-safe/journals/${match[1]}/preview` : String(value || "");
  };

  const bindClose = (root) => {
    root.querySelectorAll("[data-close]").forEach((button) => {
      button.addEventListener("click", () => dialog.close());
    });
  };

  const bindPrint = (root) => {
    root.querySelectorAll("[data-print-journal]").forEach((button) => {
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

  const copyComputedStyles = (source, clone) => {
    const sourceNodes = [source, ...source.querySelectorAll("*")];
    const cloneNodes = [clone, ...clone.querySelectorAll("*")];
    sourceNodes.forEach((sourceNode, index) => {
      const cloneNode = cloneNodes[index];
      if (!cloneNode) return;
      const computed = window.getComputedStyle(sourceNode);
      [...computed].forEach((property) => {
        cloneNode.style.setProperty(
          property,
          computed.getPropertyValue(property),
          computed.getPropertyPriority(property),
        );
      });
    });
  };

  const downloadElementAsPng = async (button) => {
    const target = document.getElementById(button.dataset.imageTarget || "");
    if (!target) throw new Error("이미지 대상 없음");
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
        canvas.toBlob((result) => result ? resolve(result) : reject(new Error("PNG 변환 실패")), "image/png");
      });
      const filename = (button.dataset.imageFilename || "업무일지")
        .replace(/[\\/:*?"<>|]+/g, "-")
        .trim();
      const downloadUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = downloadUrl;
      link.download = `${filename || "업무일지"}.png`;
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(downloadUrl), 1000);
    } finally {
      URL.revokeObjectURL(svgUrl);
    }
  };

  const bindDownload = (root) => {
    root.querySelectorAll("[data-download-image]").forEach((button) => {
      button.addEventListener("click", async () => {
        const original = button.textContent;
        button.disabled = true;
        button.textContent = "이미지 생성 중...";
        try {
          await downloadElementAsPng(button);
        } catch (_error) {
          window.alert("이미지를 저장하지 못했습니다. A4 인쇄에서 PDF 저장을 이용해 주세요.");
        } finally {
          button.disabled = false;
          button.textContent = original;
        }
      });
    });
  };

  const bindLoadedContent = () => {
    bindClose(content);
    bindPrint(content);
    bindDownload(content);
  };

  const loadPreview = async (url) => {
    const targetUrl = safeUrl(url);
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
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      content.innerHTML = body;
      bindLoadedContent();
    } catch (error) {
      const detail = status ? `HTTP ${status}` : (error?.message || "네트워크 오류");
      content.innerHTML = `<div class="meeting-preview-error"><strong>업무일지를 불러오지 못했습니다.</strong><p>오류코드: ${detail}</p><p>관리자 상세보기 경로에서 오류가 발생했습니다.</p><button class="button ghost" type="button" data-close>닫기</button></div>`;
      bindClose(content);
    }
  };

  document.querySelectorAll("[data-journal-preview]").forEach((button) => {
    button.dataset.previewBound = "admin-safe-controller";
    button.dataset.journalPreview = safeUrl(button.dataset.journalPreview);
    button.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopImmediatePropagation();
      loadPreview(button.dataset.journalPreview);
    }, true);
  });

  const autoPreview = safeUrl(dialog.dataset.autoPreview || "");
  if (autoPreview) {
    dialog.dataset.autoPreview = "";
    loadPreview(autoPreview);
    const currentUrl = new URL(window.location.href);
    currentUrl.searchParams.delete("open");
    window.history.replaceState(null, "", currentUrl);
  }
})();
