(() => {
  const nativeFetch = window.fetch.bind(window);
  const TARGET = '/admin?section=work-categories';
  const csrfToken = () => document.querySelector('meta[name="csrf-token"]')?.content || '';

  window.fetch = function medparkAdminWorkCategoryV35(input, init = {}) {
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
        || (url.pathname === '/admin' && url.searchParams.get('section') === 'work-categories')
        || (url.pathname === '/tasks/new' && url.searchParams.get('awc_admin') === '1')
      )
    );

    if (!isAdminWorkCategoryWrite) {
      return nativeFetch(input, init);
    }

    const encoded = new URLSearchParams();
    for (const [key, value] of body.entries()) {
      if (key === 'csrf_token') continue;
      encoded.set(key, String(value ?? ''));
    }
    const token = csrfToken();
    encoded.set('csrf_token', token);
    encoded.set('operation', operation);
    encoded.set('awc_operation', operation);
    encoded.set('awc_source', 'v35-admin-view');
    encoded.set('awc_response', 'json');

    const headers = new Headers();
    headers.set('Accept', 'application/json');
    headers.set('X-Requested-With', 'XMLHttpRequest');
    headers.set('Content-Type', 'application/x-www-form-urlencoded; charset=UTF-8');
    headers.set('X-MedPark-Admin-Operation', operation);
    if (token) headers.set('X-CSRFToken', token);

    return nativeFetch(TARGET, {
      method: 'POST',
      body: encoded.toString(),
      headers,
      credentials: 'same-origin',
      redirect: 'follow',
      cache: 'no-store',
    });
  };

  window.__MEDPARK_ADMIN_WORK_CATEGORY_TRANSPORT__ = 'v35-admin-view';
})();
