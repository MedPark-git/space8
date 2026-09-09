(() => {
  const API_URL = '/awc-api-v24';
  const nativeFetch = window.fetch.bind(window);

  window.fetch = function medparkAdminWorkCategoryApiV24Fetch(input, init = {}) {
    const method = String(init.method || 'GET').toUpperCase();
    const body = init.body;
    let url;
    try {
      const raw = typeof input === 'string' ? input : input?.url;
      url = new URL(raw || '', window.location.href);
    } catch (_error) {
      return nativeFetch(input, init);
    }

    const isV23WorkCategoryRequest = (
      method === 'POST'
      && body instanceof FormData
      && String(body.get('awc_source') || '') === 'v23-direct-manager'
      && url.pathname === '/admin'
      && url.searchParams.get('section') === 'work-categories'
    );

    if (!isV23WorkCategoryRequest) {
      return nativeFetch(input, init);
    }

    body.set('awc_source', 'v24-dedicated-api');
    body.set('awc_response', 'json');

    const headers = new Headers(init.headers || {});
    headers.set('Accept', 'application/json');
    headers.set('X-Requested-With', 'XMLHttpRequest');

    return nativeFetch(API_URL, {
      ...init,
      method: 'POST',
      body,
      headers,
      credentials: 'same-origin',
      redirect: 'follow',
    });
  };

  window.__MEDPARK_ADMIN_WORK_CATEGORY_TRANSPORT__ = 'v24-dedicated-api';
})();
