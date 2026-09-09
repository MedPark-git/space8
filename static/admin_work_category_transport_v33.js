(() => {
  const nativeFetch = window.fetch.bind(window);
  const ACTION_MAP = {
    add_middle: 'add',
    add_small: 'add',
    rename_middle: 'rename_middle',
    rename_small: 'rename_small',
    delete: 'delete',
  };

  window.fetch = function medparkAdminWorkCategoryV33(input, init = {}) {
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
        || (url.pathname === '/admin' && url.searchParams.get('section') === 'work-categories')
      )
    );

    if (!isAdminWorkCategoryWrite) {
      return nativeFetch(input, init);
    }

    const nextBody = new FormData();
    for (const [key, value] of body.entries()) {
      if (key === 'operation' || key === 'awc_operation' || key === 'awc_source' || key === 'awc_response') continue;
      nextBody.set(key, value);
    }

    const currentToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
    if (currentToken) nextBody.set('csrf_token', currentToken);
    nextBody.set('category_action', action);
    nextBody.set('awc_source', 'v33-task-category-wsgi');

    const target = `/tasks/new?category_manager=1&category_transport=v14&category_action=${encodeURIComponent(action)}&awc_admin=1`;
    const headers = new Headers(init.headers || {});
    headers.set('Accept', 'application/json');
    headers.set('X-Requested-With', 'XMLHttpRequest');
    headers.set('X-MedPark-Category-JSON', '1');
    headers.delete('Content-Type');

    return nativeFetch(target, {
      ...init,
      method: 'POST',
      body: nextBody,
      headers,
      credentials: 'same-origin',
      redirect: 'follow',
    });
  };

  window.__MEDPARK_ADMIN_WORK_CATEGORY_TRANSPORT__ = 'v33-task-category-wsgi';
})();
