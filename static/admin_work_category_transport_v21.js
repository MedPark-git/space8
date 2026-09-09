(() => {
  const nativeFetch = window.fetch.bind(window);

  const isLegacyWorkCategoryUrl = (input) => {
    try {
      const raw = typeof input === 'string' ? input : input?.url;
      if (!raw) return '';
      const url = new URL(raw, window.location.origin);
      if (url.pathname === '/admin/work-categories/manage') return 'manage';
      if (url.pathname === '/admin/work-categories/delete-v2') return 'delete';
      return '';
    } catch (_error) {
      return '';
    }
  };

  const currentAdminUrl = () => {
    if (window.location.pathname.startsWith('/admin')) {
      return window.location.pathname + window.location.search;
    }
    return '/admin?section=work-categories';
  };

  window.fetch = function medparkAdminWorkCategoryV21Fetch(input, init = {}) {
    const kind = isLegacyWorkCategoryUrl(input);
    if (!kind) return nativeFetch(input, init);

    let body = init.body;
    if (body instanceof FormData) {
      if (kind === 'delete') body.set('operation', 'delete');
      body.set('awc_source', 'v21-v2-direct-admin');
      body.set('awc_response', 'json');
    }

    const headers = new Headers(init.headers || {});
    headers.set('Accept', 'application/json');
    headers.set('X-Requested-With', 'XMLHttpRequest');

    return nativeFetch(currentAdminUrl(), {
      ...init,
      method: 'POST',
      body,
      headers,
      credentials: 'same-origin',
      redirect: 'follow',
    });
  };

  window.__MEDPARK_ADMIN_WORK_CATEGORY_TRANSPORT__ = 'v21-json-body-marker';
})();
