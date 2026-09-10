(() => {
  const SAVE_BASE = '/tasks/new';
  const ACTION_MAP = {
    add_middle: 'add',
    add_small: 'add',
    rename_middle: 'rename_middle',
    rename_small: 'rename_small',
    delete: 'delete',
  };

  const csrfToken = () => document.querySelector('meta[name="csrf-token"]')?.content || '';
  const isTargetPage = () => {
    const params = new URLSearchParams(location.search);
    return location.pathname.startsWith('/admin') && (
      location.pathname.endsWith('/work-categories') ||
      params.get('section') === 'work-categories' ||
      [...document.querySelectorAll('.admin-tabs a')].some((a) => a.classList.contains('active') && a.textContent.trim() === '업무구분')
    );
  };
  const escapeHtml = (value) => String(value ?? '')
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#039;');

  const ensureStyles = () => {
    if (document.getElementById('awc-v42-style')) return;
    const style = document.createElement('style');
    style.id = 'awc-v42-style';
    style.textContent = `
      .awc42-expanded{grid-column:1/-1!important;width:100%!important;max-width:none!important}
      .awc42-original-add{display:none!important}.awc42-toolbar{display:flex;gap:8px;margin-left:auto}
      .awc42-icons{display:flex;align-items:center;gap:6px;white-space:nowrap}.awc42-icons form{margin:0;display:inline-flex}
      .awc42-icon{width:38px;height:38px;border:1px solid #d6dfec;border-radius:10px;background:#fff;display:inline-grid;place-items:center;cursor:pointer;padding:0;font-size:16px}.awc42-icon.edit{color:#2563eb}.awc42-icon.delete{color:#dc2626}
      .awc42-dialog{width:min(760px,calc(100vw - 28px));max-height:92vh;border:0;border-radius:16px;padding:0;overflow:hidden;background:#f8fafc;box-shadow:0 24px 60px rgba(15,23,42,.24)}
      .awc42-dialog::backdrop{background:rgba(15,23,42,.52)}.awc42-shell{display:flex;flex-direction:column;max-height:92vh}
      .awc42-head{display:flex;justify-content:space-between;gap:14px;padding:20px 22px;background:#fff;border-bottom:1px solid #e2e8f0}.awc42-head h2{margin:4px 0 3px;font-size:23px}.awc42-head p{margin:0;color:#64748b}.awc42-close{border:0;background:transparent;font-size:30px;color:#64748b;cursor:pointer}
      .awc42-body{overflow:auto;padding:18px 20px 24px}.awc42-tabs{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:14px}.awc42-tab{border:1px solid #cbd5e1;background:#fff;border-radius:10px;padding:12px;font-weight:800;cursor:pointer}.awc42-tab.active{border-color:#2563eb;background:#eff6ff;color:#1d4ed8}.awc42-tab:disabled{opacity:.45;cursor:not-allowed}
      .awc42-panel{display:none}.awc42-panel.active{display:block}.awc42-form{display:grid;gap:12px;padding:16px;border:1px solid #dbe4ef;border-radius:12px;background:#fff}.awc42-form label{display:grid;gap:6px;font-weight:700}.awc42-form select,.awc42-form input{width:100%;padding:11px;border:1px solid #cbd5e1;border-radius:8px;background:#fff;font:inherit}.awc42-form input[readonly]{background:#f8fafc;color:#475569}
      .awc42-status{min-height:20px;margin:0;font-size:13px;white-space:pre-wrap;word-break:break-word}.awc42-status.success{color:#067647}.awc42-status.error{color:#b42318}.awc42-status.pending{color:#475569}.awc42-actions{display:flex;justify-content:flex-end;gap:8px}.awc42-summary{padding:12px 14px;margin-bottom:14px;border:1px solid #dbe4ef;border-radius:10px;background:#fff}.awc42-summary small{display:block;margin-top:4px;color:#64748b}
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

  const setStatus = (form, message = '', tone = '') => {
    const node = form?.querySelector('[data-awc42-status]');
    if (!node) return;
    node.textContent = message;
    node.className = `awc42-status${tone ? ` ${tone}` : ''}`;
  };
  const fillDepartments = (select, state) => {
    select.replaceChildren(new Option('선택', ''));
    state.departments.forEach((d) => select.append(new Option(d.name, d.id)));
  };
  const middleNames = (state, departmentId) => [...new Set(
    state.rows.filter((r) => String(r.departmentId) === String(departmentId)).map((r) => r.middleName).filter(Boolean)
  )].sort((a, b) => a.localeCompare(b, 'ko'));
  const fillMiddles = (select, state, departmentId) => {
    select.replaceChildren(new Option('중분류 선택', ''));
    middleNames(state, departmentId).forEach((name) => select.append(new Option(name, name)));
  };

  const post = async (payload) => {
    const operation = String(payload.operation || '').trim();
    const action = ACTION_MAP[operation] || '';
    if (!action) throw new Error('지원하지 않는 업무구분 작업입니다.');

    const data = new FormData();
    data.set('csrf_token', csrfToken());
    data.set('operation', operation);
    data.set('awc_operation', operation);
    data.set('awc_admin', 'v42');
    data.set('category_action', action);
    data.set('category_manager', '1');
    data.set('awc_response', 'json');
    Object.entries(payload).forEach(([key, value]) => {
      if (key !== 'operation') data.set(key, value ?? '');
    });

    const url = `${SAVE_BASE}?category_manager=1&category_transport=v14&category_action=${encodeURIComponent(action)}&awc_admin=v42`;
    const response = await window.fetch(url, {
      method: 'POST',
      body: data,
      credentials: 'same-origin',
      redirect: 'follow',
      cache: 'no-store',
      headers: {
        Accept: 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'X-MedPark-Category-JSON': '1',
        'X-Task-Category-Action': action,
      },
    });

    const contentType = (response.headers.get('content-type') || '').toLowerCase();
    if (!contentType.includes('application/json')) {
      const text = await response.text().catch(() => '');
      const detail = text.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 220);
      throw new Error(`요청 URL: ${response.url || url}\nHTTP: ${response.status}\nContent-Type: ${contentType || '-'}\n서버응답: ${detail || 'JSON이 아닌 응답'}`);
    }
    const result = await response.json().catch(() => ({}));
    if (!response.ok || !result.ok) {
      throw new Error(`요청 URL: ${response.url || url}\nHTTP: ${response.status}\n${result.message || '처리 실패'}`);
    }
    return result;
  };

  const bindClose = (dialog) => {
    dialog.querySelectorAll('[data-awc42-close]').forEach((button) => button.addEventListener('click', () => dialog.close()));
    dialog.addEventListener('click', (event) => { if (event.target === dialog) dialog.close(); });
  };

  const submitForm = async (form, payload) => {
    const button = form.querySelector('button[type="submit"]');
    const original = button?.textContent || '';
    if (button) { button.disabled = true; button.textContent = '처리 중...'; }
    setStatus(form, '저장 중입니다...', 'pending');
    try {
      const result = await post(payload);
      setStatus(form, result.message || '저장했습니다.', 'success');
      window.setTimeout(() => location.reload(), 300);
    } catch (error) {
      setStatus(form, error.message || '처리 중 오류가 발생했습니다.', 'error');
      if (button) { button.disabled = false; button.textContent = original; }
    }
  };

  const ensureAddDialog = (state) => {
    let dialog = document.getElementById('awc42-add');
    if (dialog) return dialog;
    dialog = document.createElement('dialog');
    dialog.id = 'awc42-add';
    dialog.className = 'awc42-dialog';
    dialog.innerHTML = `
      <div class="awc42-shell"><div class="awc42-head"><div><span class="eyebrow">WORK CATEGORY</span><h2>업무구분 추가</h2><p>중분류와 소분류를 나누어 등록합니다.</p></div><button type="button" class="awc42-close" data-awc42-close>×</button></div>
      <div class="awc42-body"><div class="awc42-tabs"><button type="button" class="awc42-tab active" data-tab="middle">중분류 추가</button><button type="button" class="awc42-tab" data-tab="small">소분류 추가</button></div>
      <section class="awc42-panel active" data-panel="middle"><form class="awc42-form" data-add-middle><label>대분류 (부서·팀)<select name="department_id" required></select></label><label>새 중분류명<input name="middle_name" maxlength="100" required></label><p class="awc42-status" data-awc42-status></p><div class="awc42-actions"><button type="button" class="button ghost" data-awc42-close>취소</button><button type="submit" class="button primary">중분류 저장</button></div></form></section>
      <section class="awc42-panel" data-panel="small"><form class="awc42-form" data-add-small><label>대분류 (부서·팀)<select name="department_id" required></select></label><label>기존 중분류<select name="middle_name" required></select></label><label>새 소분류명<input name="small_name" maxlength="150" required></label><p class="awc42-status" data-awc42-status></p><div class="awc42-actions"><button type="button" class="button ghost" data-awc42-close>취소</button><button type="submit" class="button primary">소분류 저장</button></div></form></section></div></div>`;
    document.body.append(dialog);
    bindClose(dialog);
    const middleForm = dialog.querySelector('[data-add-middle]');
    const smallForm = dialog.querySelector('[data-add-small]');
    const switchTab = (name) => {
      dialog.querySelectorAll('[data-tab]').forEach((b) => b.classList.toggle('active', b.dataset.tab === name));
      dialog.querySelectorAll('[data-panel]').forEach((p) => p.classList.toggle('active', p.dataset.panel === name));
      setStatus(middleForm, ''); setStatus(smallForm, '');
    };
    dialog.querySelectorAll('[data-tab]').forEach((b) => b.addEventListener('click', () => switchTab(b.dataset.tab)));
    smallForm.department_id.addEventListener('change', () => fillMiddles(smallForm.middle_name, state, smallForm.department_id.value));
    middleForm.addEventListener('submit', (event) => {
      event.preventDefault();
      submitForm(middleForm, { operation: 'add_middle', department_id: middleForm.department_id.value, middle_name: middleForm.middle_name.value.trim() });
    });
    smallForm.addEventListener('submit', (event) => {
      event.preventDefault();
      submitForm(smallForm, { operation: 'add_small', department_id: smallForm.department_id.value, middle_name: smallForm.middle_name.value, small_name: smallForm.small_name.value.trim() });
    });
    dialog.openFor = () => {
      middleForm.reset(); smallForm.reset();
      fillDepartments(middleForm.department_id, state); fillDepartments(smallForm.department_id, state); fillMiddles(smallForm.middle_name, state, '');
      switchTab('middle');
      if (!dialog.open) dialog.showModal();
    };
    return dialog;
  };

  const ensureEditDialog = () => {
    let dialog = document.getElementById('awc42-edit');
    if (dialog) return dialog;
    dialog = document.createElement('dialog');
    dialog.id = 'awc42-edit';
    dialog.className = 'awc42-dialog';
    dialog.innerHTML = `
      <div class="awc42-shell"><div class="awc42-head"><div><span class="eyebrow">WORK CATEGORY</span><h2>업무구분 수정</h2><p>업무 연결 ID는 유지하고 분류명만 변경합니다.</p></div><button type="button" class="awc42-close" data-awc42-close>×</button></div>
      <div class="awc42-body"><div class="awc42-summary" data-summary></div><div class="awc42-tabs"><button type="button" class="awc42-tab active" data-edit-tab="middle">중분류 수정</button><button type="button" class="awc42-tab" data-edit-tab="small">소분류 수정</button></div>
      <section class="awc42-panel active" data-edit-panel="middle"><form class="awc42-form" data-rename-middle><input type="hidden" name="department_id"><input type="hidden" name="old_middle_name"><label>현재 중분류<input data-old-middle readonly></label><label>새 중분류명<input name="new_middle_name" maxlength="100" required></label><p class="awc42-status" data-awc42-status></p><div class="awc42-actions"><button type="button" class="button ghost" data-awc42-close>취소</button><button type="submit" class="button primary">중분류 수정</button></div></form></section>
      <section class="awc42-panel" data-edit-panel="small"><form class="awc42-form" data-rename-small><input type="hidden" name="work_category_id"><label>현재 소분류<input data-old-small readonly></label><label>새 소분류명<input name="new_small_name" maxlength="150" required></label><p class="awc42-status" data-awc42-status></p><div class="awc42-actions"><button type="button" class="button ghost" data-awc42-close>취소</button><button type="submit" class="button primary">소분류 수정</button></div></form></section></div></div>`;
    document.body.append(dialog);
    bindClose(dialog);
    let current = null;
    const middleForm = dialog.querySelector('[data-rename-middle]');
    const smallForm = dialog.querySelector('[data-rename-small]');
    const switchTab = (name) => {
      if (name === 'small' && current && !current.smallName) return;
      dialog.querySelectorAll('[data-edit-tab]').forEach((b) => b.classList.toggle('active', b.dataset.editTab === name));
      dialog.querySelectorAll('[data-edit-panel]').forEach((p) => p.classList.toggle('active', p.dataset.editPanel === name));
      setStatus(middleForm, ''); setStatus(smallForm, '');
    };
    dialog.querySelectorAll('[data-edit-tab]').forEach((b) => b.addEventListener('click', () => switchTab(b.dataset.editTab)));
    middleForm.addEventListener('submit', (event) => {
      event.preventDefault();
      submitForm(middleForm, { operation: 'rename_middle', department_id: middleForm.department_id.value, old_middle_name: middleForm.old_middle_name.value, new_middle_name: middleForm.new_middle_name.value.trim() });
    });
    smallForm.addEventListener('submit', (event) => {
      event.preventDefault();
      submitForm(smallForm, { operation: 'rename_small', work_category_id: smallForm.work_category_id.value, new_small_name: smallForm.new_small_name.value.trim() });
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
      dialog.querySelector('[data-edit-tab="small"]').disabled = !item.smallName;
      switchTab('middle');
      if (!dialog.open) dialog.showModal();
    };
    return dialog;
  };

  const applyManagement = (state) => {
    state.rows.forEach((item) => {
      const cell = item.tr.querySelectorAll('td')[5];
      if (!cell || cell.dataset.awc42) return;
      cell.dataset.awc42 = '1';
      const originalForm = cell.querySelector('form');
      const originalButton = originalForm?.querySelector('button');
      const wrap = document.createElement('div');
      wrap.className = 'awc42-icons';

      const edit = document.createElement('button');
      edit.type = 'button'; edit.className = 'awc42-icon edit'; edit.title = '수정'; edit.textContent = '✎';
      edit.addEventListener('click', () => ensureEditDialog().openFor(item));
      wrap.append(edit);

      const del = document.createElement('button');
      del.type = 'button'; del.className = 'awc42-icon delete'; del.title = '삭제'; del.textContent = '🗑';
      del.addEventListener('click', async () => {
        if (!confirm('이 업무구분을 삭제하시겠습니까? 사용 중인 업무가 있으면 삭제되지 않습니다.')) return;
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
        originalButton.className = 'awc42-icon';
        originalButton.title = originalButton.title || '사용여부 변경';
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
    state.originalAdd.classList.add('awc42-original-add');
    state.listPanel.classList.add('awc42-expanded');
    const head = state.listPanel.querySelector('.panel-head');
    if (head && !head.querySelector('[data-awc42-add]')) {
      const toolbar = document.createElement('div'); toolbar.className = 'awc42-toolbar';
      const button = document.createElement('button'); button.type = 'button'; button.className = 'button primary'; button.dataset.awc42Add = '1'; button.textContent = '+ 업무구분 추가';
      button.addEventListener('click', () => ensureAddDialog(state).openFor());
      toolbar.append(button); head.append(toolbar);
    }
    applyManagement(state);
    window.__MEDPARK_ADMIN_WORK_CATEGORY__ = 'v42-runtime-hook';
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
