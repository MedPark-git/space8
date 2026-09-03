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
  });
};

const initBulkJournal = (root = document) => {
  const selectAll = root.querySelector("[data-check-all]");
  const taskChecks = [...root.querySelectorAll("[data-task-check]:not(:disabled)")];
  const bulkButton = root.querySelector("[data-bulk-journal]");
  const updateBulkState = () => {
    const selectedCount = taskChecks.filter((checkbox) => checkbox.checked).length;
    if (bulkButton) {
      bulkButton.disabled = selectedCount === 0;
      bulkButton.textContent = selectedCount ? `선택 ${selectedCount}건 업무일지에 담기` : "업무일지에 일괄 담기";
    }
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

document.addEventListener("DOMContentLoaded", () => {
  const nav = document.querySelector(".main-nav");
  document.querySelector(".nav-toggle")?.addEventListener("click", () => nav?.classList.toggle("open"));
  initDialogs();
  initBulkJournal();
  initCadenceFiltering();

  setTimeout(() => document.querySelectorAll(".flash").forEach((item) => item.remove()), 6000);
});
