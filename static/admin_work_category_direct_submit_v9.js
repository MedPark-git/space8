(() => {
  const csrfToken = () => document.querySelector('meta[name="csrf-token"]')?.content || "";

  const isAdminWorkCategoryPage = () => {
    const params = new URLSearchParams(window.location.search);
    return window.location.pathname.startsWith('/admin') && (
      window.location.pathname.endsWith('/work-categories') ||
      params.get('section') === 'work-categories' ||
      [...document.querySelectorAll('.admin-tabs a')].some((a) => a.classList.contains('active') && a.textContent.trim() === '업무구분')
    );
  };

  const endpoint = () => {
    const url = new URL(window.location.href);
    url.hash = '';
    if (!url.pathname.startsWith('/admin')) {
      url.pathname = '/admin';
      url.search = '?section=work-categories';
    }
    return url.pathname + url.search;
  };

  const directPost = async (operation, payload = {}) => {
    const params = new URLSearchParams();
    params.set('csrf_token', csrfToken());
    params.set('awc_operation', operation);
    params.set('operation', operation);
    Object.entries(payload).forEach(([key, value]) => params.set(key, value ?? ''));

    const response = await window.fetch(endpoint(), {
      method: 'POST',
      body: params.toString(),
      credentials: 'same-origin',
      redirect: 'follow',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'
      }
    });

    const text = await response.text();
    let result = null;
    try { result = JSON.parse(text); } catch (_error) {}
    if (!result || typeof result.ok === 'undefined') {
      throw new Error(`업무구분 저장 응답이 JSON이 아닙니다. (HTTP ${response.status})`);
    }
    if (!response.ok || !result.ok) {
      throw new Error(result.message || `처리 실패 (HTTP ${response.status})`);
    }
    return result;
  };

  const setStatus = (form, message, tone = '') => {
    const dialog = form.closest('dialog');
    const status = form.querySelector('[data-awc-status]') || dialog?.querySelector('[data-awc-status]');
    if (!status) return;
    status.textContent = message || '';
    status.className = 'awc-status' + (tone ? ` ${tone}` : '');
  };

  const submitHandler = async (event) => {
    if (!isAdminWorkCategoryPage()) return;
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) return;

    let operation = '';
    let payload = {};
    if (form.matches('[data-add-middle]')) {
      operation = 'add_middle';
      payload = {
        department_id: form.elements.department_id?.value || '',
        middle_name: form.elements.middle_name?.value?.trim() || ''
      };
    } else if (form.matches('[data-add-small]')) {
      operation = 'add_small';
      payload = {
        department_id: form.elements.department_id?.value || '',
        middle_name: form.elements.middle_name?.value || '',
        small_name: form.elements.small_name?.value?.trim() || ''
      };
    } else if (form.matches('[data-rename-middle]')) {
      operation = 'rename_middle';
      payload = {
        department_id: form.elements.department_id?.value || '',
        old_middle_name: form.elements.old_middle_name?.value || '',
        new_middle_name: form.elements.new_middle_name?.value?.trim() || ''
      };
    } else if (form.matches('[data-rename-small]')) {
      operation = 'rename_small';
      payload = {
        work_category_id: form.elements.work_category_id?.value || '',
        new_small_name: form.elements.new_small_name?.value?.trim() || ''
      };
    } else {
      return;
    }

    event.preventDefault();
    event.stopImmediatePropagation();

    const button = form.querySelector('button[type="submit"]');
    if (button) button.disabled = true;
    setStatus(form, '처리 중입니다...');
    try {
      const result = await directPost(operation, payload);
      setStatus(form, result.message || '저장했습니다.', 'success');
      window.setTimeout(() => window.location.reload(), 250);
    } catch (error) {
      setStatus(form, error.message || '처리 중 오류가 발생했습니다.', 'error');
    } finally {
      if (button) button.disabled = false;
    }
  };

  const deleteHandler = async (event) => {
    if (!isAdminWorkCategoryPage()) return;
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
      const result = await directPost('delete', { work_category_id: categoryId });
      alert(result.message || '삭제했습니다.');
      window.location.reload();
    } catch (error) {
      alert(error.message || '삭제 중 오류가 발생했습니다.');
    } finally {
      button.disabled = false;
    }
  };

  document.addEventListener('submit', submitHandler, true);
  document.addEventListener('click', deleteHandler, true);
  window.__MEDPARK_ADMIN_WORK_CATEGORY_TRANSPORT__ = 'v9-direct-submit';
})();
