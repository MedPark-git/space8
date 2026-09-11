(() => {
  const SOURCE_PATH = '/tasks/new';
  const TARGET_PATH = '/admin/work-categories/manage-v48';
  const originalFetch = window.fetch.bind(window);

  window.fetch = (input, init = {}) => {
    try {
      const rawUrl = typeof input === 'string' ? input : input?.url;
      const url = new URL(rawUrl || '', window.location.origin);
      const isAdminCategoryRequest =
        url.pathname === SOURCE_PATH &&
        url.searchParams.get('category_manager') === '1';

      if (isAdminCategoryRequest) {
        const headers = new Headers(init.headers || {});
        headers.set('Accept', 'application/json');
        headers.set('X-Requested-With', 'XMLHttpRequest');
        headers.set('X-MedPark-Admin-Category-Transport', 'v48');

        return originalFetch(TARGET_PATH, {
          ...init,
          headers,
          credentials: 'same-origin',
          redirect: 'follow',
          cache: 'no-store',
        });
      }
    } catch (_error) {
      // If URL parsing fails, preserve the browser's original request behavior.
    }

    return originalFetch(input, init);
  };

  window.__MEDPARK_ADMIN_WORK_CATEGORY_TRANSPORT__ = 'v48-wsgi-dedicated-endpoint';
})();
