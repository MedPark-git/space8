(() => {
  const nativeFetch = window.fetch.bind(window);
  const TARGET = '/tasks/new/awc-v42';

  const csrfToken = () => (
    document.querySelector('form input[name="csrf_token"]')?.value
    || document.querySelector('meta[name="csrf-token"]')?.content
    || ''
  );

  window.fetch = function medparkAdminWorkCategoryV42(input, init = {}) {
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
        || url.pathname.startsWith('/api/admin/work-category')
        || (url.pathname === '/admin' && url.searchParams.get('section') === 'work-categories')
        || url.pathname.startsWith('/tasks/new')
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
    data.set('awc_source', 'v42-exact-path');
    data.set('awc_response', 'json');

    return nativeFetch(TARGET, {
      method: 'POST',
      body: data,
      credentials: 'same-origin',
      redirect: 'manual',
      cache: 'no-store',
      headers: {
        'Accept': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
      },
    });
  };

  window.__MEDPARK_ADMIN_WORK_CATEGORY_TRANSPORT__ = 'v42-exact-path';
})();
