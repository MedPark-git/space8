(() => {
  const loadCategorySaveBridge = () => {
    if (!window.location.pathname.startsWith("/tasks")) return;
    if (window.__MEDPARK_CATEGORY_SAVE_BRIDGE__ === "v19") return;
    if (document.querySelector('script[data-category-save-bridge="v19"]')) return;

    const script = document.createElement("script");
    script.src = "/static/task_category_save_bridge_v19.js?v=20260908-v19-direct-category-api";
    script.async = false;
    script.dataset.categorySaveBridge = "v19";
    document.head.append(script);
  };

  const init = () => {
    loadCategorySaveBridge();

    if (window.location.pathname !== "/tasks/new") return;

    // Keep the Excel bulk-registration section and the single-task launch card visible,
    // but hide the long direct-entry form from the full page. The modal still fetches
    // the original /tasks/new HTML and uses this form inside the popup.
    const directForm = document.querySelector("form.form-panel");
    if (directForm) directForm.hidden = true;

    const divider = document.querySelector(".section-divider");
    if (divider) divider.hidden = true;
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
