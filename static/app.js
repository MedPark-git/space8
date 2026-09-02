document.addEventListener("DOMContentLoaded", () => {
  const nav = document.querySelector(".main-nav");
  document.querySelector(".nav-toggle")?.addEventListener("click", () => nav?.classList.toggle("open"));
  document.querySelectorAll("[data-dialog]").forEach((button) =>
    button.addEventListener("click", () => document.getElementById(button.dataset.dialog)?.showModal())
  );
  document.querySelectorAll("[data-close]").forEach((button) =>
    button.addEventListener("click", () => button.closest("dialog")?.close())
  );
  document.querySelectorAll("dialog").forEach((dialog) =>
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) dialog.close();
    })
  );

  const selectAll = document.querySelector("[data-check-all]");
  const taskChecks = [...document.querySelectorAll("[data-task-check]:not(:disabled)")];
  const bulkButton = document.querySelector("[data-bulk-journal]");
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

  setTimeout(() => document.querySelectorAll(".flash").forEach((item) => item.remove()), 6000);
});
