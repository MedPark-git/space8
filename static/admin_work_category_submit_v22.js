(() => {
  const TARGET = '/admin?section=work-categories';
  const csrfToken = () => document.querySelector('meta[name="csrf-token"]')?.content || '';

  const isWorkCategoryPage = () => {
    const params = new URLSearchParams(location.search);
    return location.pathname.startsWith('/admin') && (
      location.pathname.endsWith('/work-categories') ||
      params.get('section') === 'work-categories' ||
      [...document.querySelectorAll('.admin-tabs a')].some((a) =>
        a.classList.contains('active') && a.textContent.trim() === '업무구분'
      )
    );
  };

  const setStatus = (form, message, tone = 'error') => {
    const dialog = form.closest('dialog');
    const node = dialog?.querySelector('[data-awc-status]');
    if (!node) return;
    node.textContent = message;
    node.className = `awc-status ${tone}`;
  };

  const send = async (operation, payload = {}) => {
    const body = new FormData();
    body.set('csrf_token', csrfToken());
    body.set('operation', operation);
    body.set('awc_operation', operation);
    body.set('awc_source', 'v22-direct-submit');
    body.set('awc_response', 'json');
    Object.entries(payload).forEach(([key, value]) => body.set(key, value ?? ''));

    const response = await fetch(TARGET, {
      method: 'POST',
      body,
      credentials: 'same-origin',
      headers: {
        Accept: 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
      },
      redirect: 'manual',
    });

    const contentType = (response.headers.get('content-type') || '').toLowerCase();
    if (!contentType.includes('application/json')) {
      throw new Error(`업무구분 저장 응답이 JSON이 아닙니다. (HTTP ${response.status})`);
    }
    const result = await response.json();
    if (!response.ok || !result.ok) {
      throw new Error(result.message || `처리 실패 (HTTP ${response.status})`);
    }
    return result;
  };

  document.addEventListener('submit', async (event) => {
    if (!isWorkCategoryPage()) return;
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) return;

    let operation = '';
    let payload = {};

    if (form.matches('[data-add-middle]')) {
      operation = 'add_middle';
      payload = {
        department_id: form.elements.department_id?.value || '',
        middle_name: form.elements.middle_name?.value?.trim() || '',
      };
    } else if (form.matches('[data-add-small]')) {
      operation = 'add_small';
      payload = {
        department_id: form.elements.department_id?.value || '',
        middle_name: form.elements.middle_name?.value || '',
        small_name: form.elements.small_name?.value?.trim() || '',
      };
    } else if (form.matches('[data-rename-middle]')) {
      operation = 'rename_middle';
      payload = {
        department_id: form.elements.department_id?.value || '',
        old_middle_name: form.elements.old_middle_name?.value || '',
        new_middle_name: form.elements.new_middle_name?.value?.trim() || '',
      };
    } else if (form.matches('[data-rename-small]')) {
      operation = 'rename_small';
      payload = {
        work_category_id: form.elements.work_category_id?.value || '',
        new_small_name: form.elements.new_small_name?.value?.trim() || '',
      };
    } else {
      return;
    }

    event.preventDefault();
    event.stopImmediatePropagation();

    const button = form.querySelector('button[type="submit"]');
    if (button) {
      button.disabled = true;
      button.dataset.v22Text = button.textContent;
      button.textContent = '처리 중...';
    }
    setStatus(form, '저장 중입니다...', '');

    try {
      const result = await send(operation, payload);
      setStatus(form, result.message || '저장했습니다.', 'success');
      setTimeout(() => location.reload(), 250);
    } catch (error) {
      setStatus(form, error.message || '처리 중 오류가 발생했습니다.', 'error');
      if (button) {
        button.disabled = false;
        button.textContent = button.dataset.v22Text || button.textContent;
      }
    }
  }, true);

  document.addEventListener('click', async (event) => {
    if (!isWorkCategoryPage()) return;
    const button = event.target.closest('.awc-icon.delete');
    if (!button) return;

    event.preventDefault();
    event.stopImmediatePropagation();

    const row = button.closest('tr');
    const categoryId = row?.querySelector('input[name="work_category_id"]')?.value || row?.dataset.awcCategoryId || '';
    if (!categoryId) {
      alert('삭제할 업무구분 ID를 찾을 수 없습니다.');
      return;
    }
    if (!confirm('이 업무구분을 삭제하시겠습니까? 사용 중인 업무가 있으면 삭제되지 않습니다.')) return;

    button.disabled = true;
    try {
      const result = await send('delete', { work_category_id: categoryId });
      alert(result.message || '업무구분을 삭제했습니다.');
      location.reload();
    } catch (error) {
      alert(error.message || '삭제 중 오류가 발생했습니다.');
      button.disabled = false;
    }
  }, true);

  window.__MEDPARK_ADMIN_WORK_CATEGORY_TRANSPORT__ = 'v22-direct-submit';
})();
