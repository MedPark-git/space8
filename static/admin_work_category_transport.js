(() => {
  const API_PATH = '/admin/work-categories/manage';
  const originalFetch = window.fetch.bind(window);

  window.fetch = (input, init = {}) => {
    try {
      const rawUrl = typeof input === 'string' ? input : input?.url;
      const url = new URL(rawUrl || '', window.location.origin);
      const isLegacyCategoryRequest =
        url.pathname === '/tasks/new' &&
        url.searchParams.get('category_manager') === '1';

      if (isLegacyCategoryRequest) {
        const headers = new Headers(init.headers || {});
        headers.set('Accept', 'application/json');
        headers.set('X-Requested-With', 'XMLHttpRequest');
        headers.set('X-MedPark-Work-Category-Transport', 'stable');
        return originalFetch(API_PATH, {
          ...init,
          headers,
          credentials: 'same-origin',
          redirect: 'follow',
          cache: 'no-store',
        });
      }
    } catch (_error) {
      // If URL inspection fails, keep the original request behavior.
    }
    return originalFetch(input, init);
  };

  window.__MEDPARK_ADMIN_WORK_CATEGORY_TRANSPORT__ = 'stable-single-endpoint';
})();
