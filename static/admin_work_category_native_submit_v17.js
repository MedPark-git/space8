(() => {
  const csrfToken = () => document.querySelector('meta[name="csrf-token"]')?.content || '';

  const isWorkCategoryPage = () => {
    const params = new URLSearchParams(window.location.search);
    return window.location.pathname.startsWith('/admin') && (
      window.location.pathname.endsWith('/work-categories') ||
      params.get('section') === 'work-categories' ||
      [...document.querySelectorAll('.admin-tabs a')].some((a) =>
        a.classList.contains('active') && a.textContent.trim() === '업무구분'
      )
    );
  };

  const submitNative = (operation, payload = {}) => {
    const form = document.createElement('form');
    form.method = 'post';
    form.action = window.location.pathname + window.location.search;
    form.style.display = 'none';

    const values = {
      csrf_token: csrfToken(),
      awc_operation: operation,
      operation,
      awc_source: 'v17',
      ...payload,
    };

    Object.entries(values).forEach(([name, value]) => {
      const input = document.createElement('input');
      input.type = 'hidden';
      input.name = name;
      input.value = value == null ? '' : String(value);
      form.appendChild(input);
    });

    document.body.appendChild(form);
    HTMLFormElement.prototype.submit.call(form);
  };

  document.addEventListener('submit', (event) => {
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
      button.textContent = '처리 중...';
    }
    submitNative(operation, payload);
  }, true);

  document.addEventListener('click', (event) => {
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
    submitNative('delete', { work_category_id: categoryId });
  }, true);

  window.__MEDPARK_ADMIN_WORK_CATEGORY_TRANSPORT__ = 'v17-operation-fallback';
})();
