(() => {
  const nativeFetch = window.fetch.bind(window);

  window.fetch = function medparkAdminWorkCategoryV30Fetch(input, init = {}) {
    const method = String(init.method || 'GET').toUpperCase();
    const body = init.body;
    let url;
    try {
      const raw = typeof input === 'string' ? input : input?.url;
      url = new URL(raw || '', window.location.href);
    } catch (_error) {
      return nativeFetch(input, init);
    }

    if (method !== 'POST' || url.pathname !== '/awc-api-v24' || !(body instanceof FormData)) {
      return nativeFetch(input, init);
    }

    const encoded = new URLSearchParams();
    for (const [key, value] of body.entries()) {
      encoded.set(key, String(value ?? ''));
    }

    const csrfToken = String(encoded.get('csrf_token') || document.querySelector('meta[name="csrf-token"]')?.content || '');
    if (csrfToken) encoded.set('csrf_token', csrfToken);
    encoded.set('awc_source', 'v30-wsgi-admin');
    encoded.set('awc_response', 'json');

    const headers = new Headers(init.headers || {});
    headers.set('Accept', 'application/json');
    headers.set('X-Requested-With', 'XMLHttpRequest');
    headers.set('Content-Type', 'application/x-www-form-urlencoded; charset=UTF-8');
    if (csrfToken) headers.set('X-CSRFToken', csrfToken);

    return nativeFetch('/admin?section=work-categories&awc_transport=v30', {
      ...init,
      method: 'POST',
      body: encoded.toString(),
      headers,
      credentials: 'same-origin',
      redirect: 'manual',
    });
  };

  window.__MEDPARK_ADMIN_WORK_CATEGORY_TRANSPORT__ = 'v30-wsgi-admin';
})();
