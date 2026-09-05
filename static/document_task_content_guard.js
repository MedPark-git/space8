(() => {
  const uncheckHiddenMajorTasksForDailyCompose = () => {
    if (window.location.pathname !== "/journals") return;
    const params = new URLSearchParams(window.location.search);
    if (params.get("compose") !== "daily") return;
    const ids = new Set();
    params.getAll("task_ids").forEach((value) => {
      String(value || "").split(",").forEach((item) => {
        const clean = item.trim();
        if (/^\d+$/.test(clean)) ids.add(clean);
      });
    });
    const major = document.querySelector("[data-journal-fields='major']");
    major?.querySelectorAll("input[name='task_ids']").forEach((checkbox) => {
      if (!ids.has(String(checkbox.value))) return;
      checkbox.checked = false;
      checkbox.dispatchEvent(new Event("change", { bubbles: true }));
    });
  };

  const syncEditorState = () => {
    document.querySelectorAll(".document-task-content-editor").forEach((editor) => {
      const row = editor.closest("[data-journal-task-row], [data-meeting-task-row]");
      const checkbox = row?.querySelector("input[name='task_ids']");
      const textarea = editor.querySelector("textarea[data-task-id]");
      if (!checkbox || !textarea) return;
      const group = editor.closest("[data-journal-fields]");
      const inactiveGroup = Boolean(group && (group.hidden || checkbox.disabled));
      const loaded = textarea.dataset.loaded === "true";
      textarea.disabled = inactiveGroup || !checkbox.checked || !loaded;
      editor.hidden = !checkbox.checked;
    });
  };

  document.addEventListener("DOMContentLoaded", () => {
    uncheckHiddenMajorTasksForDailyCompose();
    window.setTimeout(syncEditorState, 0);

    document.addEventListener("change", (event) => {
      if (
        event.target.matches("input[name='document_type'], input[name='task_ids']")
      ) {
        window.setTimeout(syncEditorState, 0);
      }
    });

    const observer = new MutationObserver(() => syncEditorState());
    observer.observe(document.body, {
      subtree: true,
      attributes: true,
      attributeFilter: ["data-loaded", "disabled", "hidden"],
    });
  });
})();
