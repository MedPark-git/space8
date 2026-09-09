(() => {
  const nativeFetch = window.fetch.bind(window);
  const csrfToken = () => document.querySelector('meta[name="csrf-token"]')?.content || '';
  const ACTION_MAP = {
    add_middle: 'add',
    add_small: 'add',
    rename_middle: 'rename_middle',
    rename_small: 'rename_small',
    delete: 'delete',
  };

  window.fetch = function medparkAdminWorkCategoryV40(input, init = {}) {
    const method = String(init.method || 'GET').toUpperCase();
    const body = init.body;
    let url;
    try {
      const raw = typeof input === 'string' ? input : input?.url;
      url = new URL(raw || '', window.location.href);
    } catch (_error) {
      return nativeFetch(input, init);
    }

    const operation = body instanceof FormData ? String(body.get('operation') || '').trim() : '';
    const action = ACTION_MAP[operation] || '';
    const isAdminWorkCategoryWrite = (
      method === 'POST'
      && body instanceof FormData
      && action
      && (
        url.pathname === '/awc-api-v24'
        || url.pathname === '/api/admin/work-category-v38'
        || (url.pathname === '/admin' && url.searchParams.get('section') === 'work-categories')
        || url.pathname === '/tasks/new'
      )
    );

    if (!isAdminWorkCategoryWrite) return nativeFetch(input, init);

    const data = new FormData();
    for (const [key, value] of body.entries()) {
      if (key === 'csrf_token') continue;
      data.set(key, value);
    }
    data.set('csrf_token', csrfToken());
    data.set('operation', operation);
    data.set('awc_operation', operation);
    data.set('category_action', action);
    data.set('awc_source', 'v40-category-manager');
    data.set('awc_response', 'json');

    const target = `/tasks/new?category_manager=1&category_transport=v14&category_action=${encodeURIComponent(action)}&awc_admin=v40`;
    return nativeFetch(target, {
      method: 'POST',
      body: data,
      credentials: 'same-origin',
      redirect: 'follow',
      cache: 'no-store',
      headers: {
        'Accept': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'X-MedPark-Category-JSON': '1',
        'X-Task-Category-Action': action,
      },
    });
  };

  window.__MEDPARK_ADMIN_WORK_CATEGORY_TRANSPORT__ = 'v40-category-manager';
})();
