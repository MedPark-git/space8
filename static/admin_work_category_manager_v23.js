(() => {
  const TARGET = '/admin?section=work-categories';
  const csrfToken = () => document.querySelector('meta[name="csrf-token"]')?.content || '';

  const isTargetPage = () => {
    const params = new URLSearchParams(location.search);
    return location.pathname.startsWith('/admin') && (
      location.pathname.endsWith('/work-categories') ||
      params.get('section') === 'work-categories' ||
      [...document.querySelectorAll('.admin-tabs a')].some((a) =>
        a.classList.contains('active') && a.textContent.trim() === '업무구분'
      )
    );
  };

  const escapeHtml = (value) => String(value ?? '')
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#039;');

  const icon = (type) => ({
    edit: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20h4l10.5-10.5a2.8 2.8 0 0 0-4-4L4 16v4Zm9-13 4 4"/></svg>',
    delete: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M9 7V4h6v3M7 7l1 13h8l1-13M10 11v5M14 11v5"/></svg>',
    toggle: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 8h12M6 12h12M6 16h12"/></svg>',
  })[type] || '';

  const ensureStyles = () => {
    if (document.getElementById('awc-v23-style')) return;
    const style = document.createElement('style');
    style.id = 'awc-v23-style';
    style.textContent = `
      .awc-expanded-list{grid-column:1/-1!important;width:100%!important;max-width:none!important}.awc-expanded-list .table-wrap{max-height:none}.awc-original-add{display:none!important}
      .awc-toolbar{display:flex;align-items:center;gap:8px}.awc-manage-icons{display:flex;align-items:center;gap:6px;white-space:nowrap}.awc-manage-icons form{margin:0;display:inline-flex}
      .awc-icon{width:38px;height:38px;border:1px solid #d6dfec;border-radius:10px;background:#fff;display:inline-grid;place-items:center;cursor:pointer;color:#475569;padding:0;transition:.15s}.awc-icon:hover{background:#f8fafc;border-color:#9fb3ca}.awc-icon svg{width:18px;height:18px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}.awc-icon.edit{color:#2563eb}.awc-icon.delete{color:#dc2626}.awc-icon.toggle{color:#64748b}
      .awc-dialog{width:min(760px,calc(100vw - 28px));max-height:92vh;border:0;border-radius:16px;padding:0;overflow:hidden;background:#f8fafc;box-shadow:0 24px 60px rgba(15,23,42,.24)}.awc-dialog::backdrop{background:rgba(15,23,42,.52)}
      .awc-shell{display:flex;flex-direction:column;max-height:92vh}.awc-head{display:flex;justify-content:space-between;gap:14px;padding:20px 22px;background:#fff;border-bottom:1px solid #e2e8f0}.awc-head h2{margin:4px 0 3px;font-size:23px}.awc-head p{margin:0;color:#64748b}.awc-close{border:0;background:transparent;font-size:30px;line-height:1;color:#64748b;cursor:pointer}.awc-body{overflow:auto;padding:18px 20px 24px}
      .awc-tabs{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:14px}.awc-tab{border:1px solid #cbd5e1;background:#fff;border-radius:10px;padding:12px;font-weight:800;cursor:pointer}.awc-tab.active{border-color:#2563eb;background:#eff6ff;color:#1d4ed8}.awc-tab:disabled{opacity:.45;cursor:not-allowed}
      .awc-panel{display:none}.awc-panel.active{display:block}.awc-form{display:grid;gap:12px;padding:16px;border:1px solid #dbe4ef;border-radius:12px;background:#fff}.awc-form label{display:grid;gap:6px;font-weight:700}.awc-form select,.awc-form input{width:100%;padding:11px;border:1px solid #cbd5e1;border-radius:8px;background:#fff;font:inherit}.awc-form input[readonly]{background:#f8fafc;color:#475569}.awc-help{margin:0;color:#64748b;font-size:12px;line-height:1.55}.awc-status{min-height:20px;margin:0;font-size:13px}.awc-status.success{color:#067647}.awc-status.error{color:#b42318}.awc-status.pending{color:#475569}.awc-actions{display:flex;justify-content:flex-end;gap:8px}.awc-summary{padding:12px 14px;margin-bottom:14px;border:1px solid #dbe4ef;border-radius:10px;background:#fff}.awc-summary strong{display:block}.awc-summary small{display:block;margin-top:4px;color:#64748b}
      @media(max-width:720px){.awc-dialog{width:calc(100vw - 14px);max-height:96vh}.awc-body{padding:10px}.awc-icon{width:34px;height:34px}}
    `;
    document.head.append(style);
  };

  const parseState = () => {
    const panels = [...document.querySelectorAll('.panel')];
    const listPanel = panels.find((p) => p.querySelector('h2')?.textContent.includes('업무구분 기초자료'));
    const originalAdd = panels.find((p) => p.querySelector('h2')?.textContent.trim() === '업무구분 추가');
    if (!listPanel || !originalAdd) return null;

    const departmentSelect = originalAdd.querySelector('select[name="department_id"]');
    const departments = [...(departmentSelect?.options || [])]
      .filter((o) => o.value)
      .map((o) => ({ id: o.value, name: o.textContent.trim() }));
    const deptByName = new Map(departments.map((d) => [d.name, d.id]));
    const rows = [];

    listPanel.querySelectorAll('tbody tr').forEach((tr) => {
      const categoryId = tr.querySelector('input[name="work_category_id"]')?.value;
      const cells = tr.querySelectorAll('td');
      if (!categoryId || cells.length < 6) return;
      const departmentName = cells[0].textContent.trim();
      const middleName = cells[1].textContent.trim();
      const smallText = cells[2].textContent.trim();
      const taskText = cells[3].textContent.trim();
      rows.push({
        id: categoryId,
        departmentId: deptByName.get(departmentName) || '',
        departmentName,
        middleName,
        smallName: smallText === '미분류' ? '' : smallText,
        taskCount: Number((taskText.match(/\d+/) || ['0'])[0]),
        tr,
      });
    });
    return { listPanel, originalAdd, departments, rows };
  };

  const fillDepartments = (select, state, placeholder = '선택') => {
    select.replaceChildren(new Option(placeholder, ''));
    state.departments.forEach((d) => select.append(new Option(d.name, d.id)));
  };

  const middleNames = (state, departmentId) => [...new Set(
    state.rows
      .filter((r) => String(r.departmentId) === String(departmentId))
      .map((r) => r.middleName)
      .filter(Boolean)
  )].sort((a, b) => a.localeCompare(b, 'ko'));

  const fillMiddles = (select, state, departmentId) => {
    select.replaceChildren(new Option('중분류 선택', ''));
    middleNames(state, departmentId).forEach((name) => select.append(new Option(name, name)));
  };

  const setStatus = (form, message = '', tone = '') => {
    const node = form?.querySelector('[data-awc-status]');
    if (!node) return;
    node.textContent = message;
    node.className = 'awc-status' + (tone ? ` ${tone}` : '');
  };

  const post = async (payload) => {
    const data = new FormData();
    data.set('csrf_token', csrfToken());
    data.set('awc_source', 'v23-direct-manager');
    data.set('awc_response', 'json');
    Object.entries(payload).forEach(([key, value]) => data.set(key, value ?? ''));

    const response = await fetch(TARGET, {
      method: 'POST',
      body: data,
      credentials: 'same-origin',
      headers: {
        Accept: 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
      },
      redirect: 'follow',
    });

    const contentType = (response.headers.get('content-type') || '').toLowerCase();
    if (!contentType.includes('application/json')) {
      const text = await response.text().catch(() => '');
      const detail = text.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 180);
      throw new Error(detail ? `서버가 JSON 대신 화면을 반환했습니다: ${detail}` : `업무구분 저장 응답이 JSON이 아닙니다. (HTTP ${response.status})`);
    }

    const result = await response.json();
    if (!response.ok || !result.ok) {
      throw new Error(result.message || `처리 실패 (HTTP ${response.status})`);
    }
    return result;
  };

  const bindClose = (dialog) => {
    dialog.querySelectorAll('[data-awc-close]').forEach((button) => button.addEventListener('click', () => dialog.close()));
    dialog.addEventListener('click', (event) => { if (event.target === dialog) dialog.close(); });
  };

  const submitForm = async (form, payload) => {
    const button = form.querySelector('button[type="submit"]');
    const originalText = button?.textContent || '';
    if (button) {
      button.disabled = true;
      button.textContent = '처리 중...';
    }
    setStatus(form, '저장 중입니다...', 'pending');
    try {
      const result = await post(payload);
      setStatus(form, result.message || '저장했습니다.', 'success');
      setTimeout(() => location.reload(), 350);
    } catch (error) {
      setStatus(form, error.message || '처리 중 오류가 발생했습니다.', 'error');
      if (button) {
        button.disabled = false;
        button.textContent = originalText;
      }
    }
  };

  const ensureAddDialog = (state) => {
    let dialog = document.getElementById('awc-v23-add');
    if (dialog) return dialog;
    dialog = document.createElement('dialog');
    dialog.id = 'awc-v23-add';
    dialog.className = 'awc-dialog';
    dialog.innerHTML = `
      <div class="awc-shell">
        <div class="awc-head"><div><span class="eyebrow">WORK CATEGORY</span><h2>업무구분 추가</h2><p>중분류와 소분류를 탭으로 나누어 등록합니다.</p></div><button type="button" class="awc-close" data-awc-close>×</button></div>
        <div class="awc-body">
          <div class="awc-tabs"><button type="button" class="awc-tab active" data-tab="middle">중분류 추가</button><button type="button" class="awc-tab" data-tab="small">소분류 추가</button></div>
          <section class="awc-panel active" data-panel="middle"><form class="awc-form" data-v23-add-middle><label>대분류 (부서·팀)<select name="department_id" required></select></label><label>새 중분류명<input name="middle_name" maxlength="100" required placeholder="예: 정보화 기기"></label><p class="awc-help">중분류만 먼저 생성합니다. 소분류는 별도 탭에서 기존 중분류를 선택해 추가합니다.</p><p class="awc-status" data-awc-status></p><div class="awc-actions"><button type="button" class="button ghost" data-awc-close>취소</button><button type="submit" class="button primary">중분류 저장</button></div></form></section>
          <section class="awc-panel" data-panel="small"><form class="awc-form" data-v23-add-small><label>대분류 (부서·팀)<select name="department_id" required></select></label><label>기존 중분류<select name="middle_name" required></select></label><label>새 소분류명<input name="small_name" maxlength="150" required placeholder="예: 네트워크"></label><p class="awc-help">대분류를 선택하면 저장된 중분류만 선택할 수 있습니다.</p><p class="awc-status" data-awc-status></p><div class="awc-actions"><button type="button" class="button ghost" data-awc-close>취소</button><button type="submit" class="button primary">소분류 저장</button></div></form></section>
        </div>
      </div>`;
    document.body.append(dialog);
    bindClose(dialog);

    const middleForm = dialog.querySelector('[data-v23-add-middle]');
    const smallForm = dialog.querySelector('[data-v23-add-small]');
    fillDepartments(middleForm.department_id, state);
    fillDepartments(smallForm.department_id, state);
    fillMiddles(smallForm.middle_name, state, '');

    const switchTab = (name) => {
      dialog.querySelectorAll('[data-tab]').forEach((b) => b.classList.toggle('active', b.dataset.tab === name));
      dialog.querySelectorAll('[data-panel]').forEach((p) => p.classList.toggle('active', p.dataset.panel === name));
      setStatus(middleForm, '');
      setStatus(smallForm, '');
    };
    dialog.querySelectorAll('[data-tab]').forEach((b) => b.addEventListener('click', () => switchTab(b.dataset.tab)));
    smallForm.department_id.addEventListener('change', () => fillMiddles(smallForm.middle_name, state, smallForm.department_id.value));

    middleForm.addEventListener('submit', (event) => {
      event.preventDefault();
      submitForm(middleForm, {
        operation: 'add_middle',
        department_id: middleForm.department_id.value,
        middle_name: middleForm.middle_name.value.trim(),
      });
    });
    smallForm.addEventListener('submit', (event) => {
      event.preventDefault();
      submitForm(smallForm, {
        operation: 'add_small',
        department_id: smallForm.department_id.value,
        middle_name: smallForm.middle_name.value,
        small_name: smallForm.small_name.value.trim(),
      });
    });

    dialog.openFor = () => {
      middleForm.reset();
      smallForm.reset();
      fillDepartments(middleForm.department_id, state);
      fillDepartments(smallForm.department_id, state);
      fillMiddles(smallForm.middle_name, state, '');
      switchTab('middle');
      if (!dialog.open) dialog.showModal();
    };
    return dialog;
  };

  const ensureEditDialog = () => {
    let dialog = document.getElementById('awc-v23-edit');
    if (dialog) return dialog;
    dialog = document.createElement('dialog');
    dialog.id = 'awc-v23-edit';
    dialog.className = 'awc-dialog';
    dialog.innerHTML = `
      <div class="awc-shell">
        <div class="awc-head"><div><span class="eyebrow">WORK CATEGORY</span><h2>업무구분 수정</h2><p>기존 업무 연결 ID는 유지하고 분류명만 변경합니다.</p></div><button type="button" class="awc-close" data-awc-close>×</button></div>
        <div class="awc-body">
          <div class="awc-summary" data-summary></div>
          <div class="awc-tabs"><button type="button" class="awc-tab active" data-edit-tab="middle">중분류 수정</button><button type="button" class="awc-tab" data-edit-tab="small">소분류 수정</button></div>
          <section class="awc-panel active" data-edit-panel="middle"><form class="awc-form" data-v23-rename-middle><input type="hidden" name="department_id"><input type="hidden" name="old_middle_name"><label>현재 중분류<input data-old-middle readonly></label><label>새 중분류명<input name="new_middle_name" maxlength="100" required></label><p class="awc-help">같은 중분류의 모든 소분류에 함께 반영됩니다.</p><p class="awc-status" data-awc-status></p><div class="awc-actions"><button type="button" class="button ghost" data-awc-close>취소</button><button type="submit" class="button primary">중분류 수정</button></div></form></section>
          <section class="awc-panel" data-edit-panel="small"><form class="awc-form" data-v23-rename-small><input type="hidden" name="work_category_id"><label>현재 소분류<input data-old-small readonly></label><label>새 소분류명<input name="new_small_name" maxlength="150" required></label><p class="awc-help">선택한 소분류 한 건의 이름만 변경합니다.</p><p class="awc-status" data-awc-status></p><div class="awc-actions"><button type="button" class="button ghost" data-awc-close>취소</button><button type="submit" class="button primary">소분류 수정</button></div></form></section>
        </div>
      </div>`;
    document.body.append(dialog);
    bindClose(dialog);

    let current = null;
    const middleForm = dialog.querySelector('[data-v23-rename-middle]');
    const smallForm = dialog.querySelector('[data-v23-rename-small]');

    const switchTab = (name) => {
      if (name === 'small' && current && !current.smallName) return;
      dialog.querySelectorAll('[data-edit-tab]').forEach((b) => b.classList.toggle('active', b.dataset.editTab === name));
      dialog.querySelectorAll('[data-edit-panel]').forEach((p) => p.classList.toggle('active', p.dataset.editPanel === name));
      setStatus(middleForm, '');
      setStatus(smallForm, '');
    };
    dialog.querySelectorAll('[data-edit-tab]').forEach((b) => b.addEventListener('click', () => switchTab(b.dataset.editTab)));

    middleForm.addEventListener('submit', (event) => {
      event.preventDefault();
      submitForm(middleForm, {
        operation: 'rename_middle',
        department_id: middleForm.department_id.value,
        old_middle_name: middleForm.old_middle_name.value,
        new_middle_name: middleForm.new_middle_name.value.trim(),
      });
    });
    smallForm.addEventListener('submit', (event) => {
      event.preventDefault();
      submitForm(smallForm, {
        operation: 'rename_small',
        work_category_id: smallForm.work_category_id.value,
        new_small_name: smallForm.new_small_name.value.trim(),
      });
    });

    dialog.openFor = (item) => {
      current = item;
      dialog.querySelector('[data-summary]').innerHTML = `<strong>${escapeHtml(item.departmentName)} → ${escapeHtml(item.middleName)}${item.smallName ? ` → ${escapeHtml(item.smallName)}` : ''}</strong><small>사용 업무 ${item.taskCount}건 · 연결 ID 유지</small>`;
      middleForm.department_id.value = item.departmentId;
      middleForm.old_middle_name.value = item.middleName;
      middleForm.querySelector('[data-old-middle]').value = item.middleName;
      middleForm.new_middle_name.value = item.middleName;
      smallForm.work_category_id.value = item.id;
      smallForm.querySelector('[data-old-small]').value = item.smallName || '소분류 없음';
      smallForm.new_small_name.value = item.smallName || '';
      const smallTab = dialog.querySelector('[data-edit-tab="small"]');
      smallTab.disabled = !item.smallName;
      switchTab('middle');
      if (!dialog.open) dialog.showModal();
    };
    return dialog;
  };

  const applyManagementIcons = (state) => {
    state.rows.forEach((item) => {
      const cell = item.tr.querySelectorAll('td')[5];
      if (!cell || cell.dataset.awcV23) return;
      cell.dataset.awcV23 = '1';
      const originalForm = cell.querySelector('form');
      const originalButton = originalForm?.querySelector('button');
      const wrap = document.createElement('div');
      wrap.className = 'awc-manage-icons';

      const edit = document.createElement('button');
      edit.type = 'button';
      edit.className = 'awc-icon edit';
      edit.title = '수정';
      edit.setAttribute('aria-label', '수정');
      edit.innerHTML = icon('edit');
      edit.addEventListener('click', () => ensureEditDialog().openFor(item));
      wrap.append(edit);

      const del = document.createElement('button');
      del.type = 'button';
      del.className = 'awc-icon delete';
      del.title = item.taskCount ? `사용 중 ${item.taskCount}건 - 삭제 시 차단됩니다` : '삭제';
      del.setAttribute('aria-label', '삭제');
      del.innerHTML = icon('delete');
      del.addEventListener('click', async () => {
        const warning = item.taskCount
          ? `이 업무구분은 현재 ${item.taskCount}개 업무에서 사용 중입니다. 삭제 요청 시 안전하게 차단됩니다. 계속 확인하시겠습니까?`
          : `${item.departmentName} → ${item.middleName}${item.smallName ? ` → ${item.smallName}` : ''} 을(를) 삭제하시겠습니까?`;
        if (!confirm(warning)) return;
        del.disabled = true;
        try {
          const result = await post({ operation: 'delete', work_category_id: item.id });
          alert(result.message || '업무구분을 삭제했습니다.');
          location.reload();
        } catch (error) {
          alert(error.message || '삭제 중 오류가 발생했습니다.');
          del.disabled = false;
        }
      });
      wrap.append(del);

      if (originalForm && originalButton) {
        originalButton.className = 'awc-icon toggle';
        originalButton.title = originalButton.textContent.trim();
        originalButton.setAttribute('aria-label', originalButton.textContent.trim());
        originalButton.innerHTML = icon('toggle');
        wrap.append(originalForm);
      }
      cell.replaceChildren(wrap);
    });
  };

  const init = () => {
    if (!isTargetPage()) return;
    ensureStyles();
    const state = parseState();
    if (!state) return;

    state.originalAdd.classList.add('awc-original-add');
    state.listPanel.classList.add('awc-expanded-list');
    const head = state.listPanel.querySelector('.panel-head');
    if (head && !head.querySelector('[data-awc-v23-add]')) {
      const toolbar = document.createElement('div');
      toolbar.className = 'awc-toolbar';
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'button primary';
      button.dataset.awcV23Add = '1';
      button.textContent = '+ 업무구분 추가';
      button.addEventListener('click', () => ensureAddDialog(state).openFor());
      toolbar.append(button);
      head.append(toolbar);
    }
    applyManagementIcons(state);
    window.__MEDPARK_ADMIN_WORK_CATEGORY__ = 'v23-direct-manager';
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
