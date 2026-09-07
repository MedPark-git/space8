(() => {
  const init = () => {
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
