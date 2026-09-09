(() => {
  const nativeFetch = window.fetch.bind(window);
  const TARGET = '/tasks/new';
  const csrfToken = () => document.querySelector('meta[name="csrf-token"]')?.content || '';

  window.fetch = function medparkAdminWorkCategoryV41(input, init = {}) {
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
    const isAdminWorkCategoryWrite = (
      method === 'POST'
      && body instanceof FormData
      && operation
      && (
        url.pathname === '/awc-api-v24'
        || url.pathname === '/api/admin/work-category-v38'
        || (url.pathname === '/admin' && url.searchParams.get('section') === 'work-categories')
        || (url.pathname === '/tasks/new' && (url.searchParams.get('awc_admin') || url.searchParams.get('category_manager')))
      )
    );

    if (!isAdminWorkCategoryWrite) return nativeFetch(input, init);

    const encoded = new URLSearchParams();
    for (const [key, value] of body.entries()) {
      if (key === 'csrf_token') continue;
      encoded.set(key, String(value ?? ''));
    }
    encoded.set('csrf_token', csrfToken());
    encoded.set('awc_admin', 'v41');
    encoded.set('operation', operation);
    encoded.set('awc_operation', operation);
    encoded.set('awc_source', 'v41-body');
    encoded.set('awc_response', 'json');

    return nativeFetch(TARGET, {
      method: 'POST',
      body: encoded.toString(),
      credentials: 'same-origin',
      redirect: 'follow',
      cache: 'no-store',
      headers: {
        'Accept': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
      },
    });
  };

  window.__MEDPARK_ADMIN_WORK_CATEGORY_TRANSPORT__ = 'v41-body-marker';
})();
