(() => {
  const STYLE_ID = "task-assignee-manager-style";
  const META_ENDPOINT = "/tasks/assignee-metadata";

  const ensureStyles = () => {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = `
      .task-assignee-editor{display:flex;align-items:center;gap:7px;flex-wrap:wrap;min-width:150px}
      .task-assignee-current{font-weight:700;color:#172033;line-height:1.35}
      .task-assignee-edit{border:1px solid #cbd5e1;background:#fff;color:#334155;border-radius:7px;padding:4px 8px;font-size:12px;font-weight:700;cursor:pointer}
      .task-assignee-edit:hover{border-color:#2563eb;color:#1d4ed8}
      .task-assignee-controls{display:flex;align-items:center;gap:6px;flex-wrap:wrap;width:100%}
      .task-assignee-controls[hidden]{display:none}
      .task-assignee-controls select{min-width:140px;max-width:210px;padding:7px 28px 7px 9px;border:1px solid #cbd5e1;border-radius:8px;background:#fff;font-size:13px}
      .task-assignee-save,.task-assignee-cancel{border:0;border-radius:7px;padding:6px 9px;font-size:12px;font-weight:800;cursor:pointer}
      .task-assignee-save{background:#2563eb;color:#fff}
      .task-assignee-cancel{background:#eef2f7;color:#475569}
      .task-assignee-save:disabled{opacity:.55;cursor:wait}
      .task-assignee-status{width:100%;font-size:12px;color:#64748b}
      .task-assignee-status.error{color:#b91c1c}
      .task-assignee-status.success{color:#047857}
      .task-assignee-detail-box{margin:14px 0 18px;padding:14px 16px;border:1px solid #dbe3ee;border-radius:12px;background:#f8fafc;display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap}
      .task-assignee-detail-copy{display:flex;flex-direction:column;gap:4px}
      .task-assignee-detail-copy small{color:#64748b;font-size:12px;font-weight:700}
      .task-assignee-detail-box .task-assignee-editor{min-width:240px;justify-content:flex-end}
      @media(max-width:760px){
        .task-assignee-detail-box{align-items:flex-start}
        .task-assignee-detail-box .task-assignee-editor{width:100%;justify-content:flex-start}
      }
    `;
    document.head.append(style);
  };

  const csrfToken = () => document.querySelector('meta[name="csrf-token"]')?.content || "";

  const fetchMetadata = async (taskIds) => {
    if (!taskIds.length) return { ok: true, tasks: {}, departments: {} };
    const url = new URL(META_ENDPOINT, window.location.origin);
    url.searchParams.set("task_ids", taskIds.join(","));
    const response = await fetch(url, {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    });
    if (!response.ok) throw new Error("담당자 정보를 불러오지 못했습니다.");
    return response.json();
  };

  const postAssignee = async (taskId, assigneeId) => {
    const formData = new FormData();
    formData.set("csrf_token", csrfToken());
    formData.set("assignee_id", String(assigneeId));
    const response = await fetch(`/tasks/${taskId}/assignee`, {
      method: "POST",
      body: formData,
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        "X-Requested-With": "XMLHttpRequest",
      },
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok || !result.ok) {
      throw new Error(result.message || "담당자를 변경하지 못했습니다.");
    }
    return result;
  };

  const makeOption = (value, label, selected = false) => {
    const option = document.createElement("option");
    option.value = String(value);
    option.textContent = label;
    option.selected = selected;
    return option;
  };

  const buildEditor = (info, employees, onSaved) => {
    const wrapper = document.createElement("div");
    wrapper.className = "task-assignee-editor";

    const current = document.createElement("span");
    current.className = "task-assignee-current";
    current.textContent = info.current_label || "-";

    const edit = document.createElement("button");
    edit.className = "task-assignee-edit";
    edit.type = "button";
    edit.textContent = "담당자 수정";

    const controls = document.createElement("div");
    controls.className = "task-assignee-controls";
    controls.hidden = true;

    const select = document.createElement("select");
    select.setAttribute("aria-label", "담당자 선택");

    let currentFound = false;
    (employees || []).forEach((employee) => {
      const selected = String(employee.id) === String(info.current_assignee_id);
      if (selected) currentFound = true;
      select.append(makeOption(employee.id, employee.label || employee.name, selected));
    });
    if (!currentFound && info.current_assignee_id) {
      select.prepend(
        makeOption(
          info.current_assignee_id,
          `현재 계정 · ${info.current_label || info.current_assignee_id}`,
          true,
        ),
      );
    }

    const save = document.createElement("button");
    save.type = "button";
    save.className = "task-assignee-save";
    save.textContent = "저장";

    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.className = "task-assignee-cancel";
    cancel.textContent = "취소";

    const status = document.createElement("span");
    status.className = "task-assignee-status";
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");

    controls.append(select, save, cancel, status);
    wrapper.append(current, edit, controls);

    const close = () => {
      controls.hidden = true;
      edit.hidden = false;
      status.textContent = "";
      status.className = "task-assignee-status";
      select.value = String(info.current_assignee_id || "");
    };

    edit.addEventListener("click", () => {
      edit.hidden = true;
      controls.hidden = false;
      select.focus();
    });

    cancel.addEventListener("click", close);

    save.addEventListener("click", async () => {
      if (!select.value) {
        status.textContent = "담당자를 선택해 주세요.";
        status.classList.add("error");
        return;
      }
      save.disabled = true;
      status.textContent = "변경 중...";
      status.className = "task-assignee-status";
      try {
        const result = await postAssignee(info.id, select.value);
        info.current_assignee_id = result.assignee_id;
        info.current_label = result.assignee_name;
        current.textContent = result.assignee_name;
        status.textContent = result.message || "담당자를 변경했습니다.";
        status.classList.add("success");
        onSaved?.(result, info);
        window.setTimeout(close, 650);
      } catch (error) {
        status.textContent = error.message || "담당자 변경 중 오류가 발생했습니다.";
        status.classList.add("error");
      } finally {
        save.disabled = false;
      }
    });

    return wrapper;
  };

  const initTaskList = async () => {
    const results = document.querySelector("[data-task-results]");
    const table = results?.querySelector("table");
    if (!table) return false;

    const headers = [...table.querySelectorAll("thead th")];
    const assigneeIndex = headers.findIndex((header) => header.textContent.trim() === "담당자");
    if (assigneeIndex < 0) return false;

    const rows = [...table.querySelectorAll("tbody tr")];
    const records = rows.map((row) => {
      const checkbox = row.querySelector("input[data-task-check]");
      if (!checkbox?.value) return null;
      const cells = row.querySelectorAll("td");
      return {
        row,
        taskId: Number(checkbox.value),
        cell: cells[assigneeIndex],
      };
    }).filter((record) => record && record.cell && Number.isFinite(record.taskId));

    if (!records.length) return true;

    let metadata;
    try {
      metadata = await fetchMetadata(records.map((record) => record.taskId));
    } catch (_error) {
      return true;
    }

    records.forEach((record) => {
      const info = metadata.tasks?.[String(record.taskId)];
      if (!info?.editable) return;
      const employees = metadata.departments?.[String(info.department_id)] || [];
      record.cell.replaceChildren(
        buildEditor(info, employees, (_result, nextInfo) => {
          record.cell.dataset.assigneeId = String(nextInfo.current_assignee_id || "");
        }),
      );
    });
    return true;
  };

  const detailTaskId = () => {
    const match = window.location.pathname.match(/^\/tasks\/(\d+)\/?$/);
    return match ? Number(match[1]) : null;
  };

  const initTaskDetail = async () => {
    const taskId = detailTaskId();
    if (!taskId) return false;

    let metadata;
    try {
      metadata = await fetchMetadata([taskId]);
    } catch (_error) {
      return true;
    }

    const info = metadata.tasks?.[String(taskId)];
    if (!info?.editable) return true;

    const category = document.querySelector(".task-category-detail");
    const article = category?.closest("article.panel");
    if (!category || !article || article.querySelector(".task-assignee-detail-box")) return true;

    const box = document.createElement("div");
    box.className = "task-assignee-detail-box";

    const copy = document.createElement("div");
    copy.className = "task-assignee-detail-copy";
    const label = document.createElement("small");
    label.textContent = "현재 담당자";
    const hint = document.createElement("strong");
    hint.textContent = `${info.department_name} 업무 담당자를 변경할 수 있습니다.`;
    copy.append(label, hint);

    const employees = metadata.departments?.[String(info.department_id)] || [];
    const editor = buildEditor(info, employees, (result) => {
      const headingMeta = document.querySelector(".page-heading p");
      if (headingMeta) headingMeta.textContent = `${info.department_name} · ${result.assignee_name}`;
    });

    box.append(copy, editor);
    category.insertAdjacentElement("afterend", box);
    return true;
  };

  const init = async () => {
    if (!window.location.pathname.startsWith("/tasks")) return;
    ensureStyles();
    await initTaskList();
    await initTaskDetail();
  };

  document.addEventListener("DOMContentLoaded", init);
})();
