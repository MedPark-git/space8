(() => {
  const nativeFetch = window.fetch.bind(window);
  const csrfToken = () => document.querySelector('meta[name="csrf-token"]')?.content || '';

  window.fetch = function medparkAdminWorkCategoryV36(input, init = {}) {
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
    encoded.set('awc_source', 'v36-query-operation');
    encoded.set('awc_response', 'json');

    const target = `/admin?section=work-categories&awc_operation=${encodeURIComponent(operation)}&awc_transport=v36`;
    const headers = new Headers();
    headers.set('Accept', 'application/json');
    headers.set('X-Requested-With', 'XMLHttpRequest');
    headers.set('Content-Type', 'application/x-www-form-urlencoded; charset=UTF-8');
    headers.set('X-MedPark-Admin-Operation', operation);
    if (token) headers.set('X-CSRFToken', token);

    return nativeFetch(target, {
      method: 'POST',
      body: encoded.toString(),
      headers,
      credentials: 'same-origin',
      redirect: 'follow',
      cache: 'no-store',
    });
  };

  window.__MEDPARK_ADMIN_WORK_CATEGORY_TRANSPORT__ = 'v36-query-operation';
})();
