(() => {
  const SOURCE_PATH = '/tasks/new';
  const TARGET_PATH = '/admin/work-categories/manage';
  const originalFetch = window.fetch.bind(window);

  window.fetch = (input, init = {}) => {
    try {
      const rawUrl = typeof input === 'string' ? input : input?.url;
      const url = new URL(rawUrl || '', window.location.origin);
      const isAdminCategoryV42 =
        url.pathname === SOURCE_PATH &&
        url.searchParams.get('category_manager') === '1' &&
        url.searchParams.get('awc_admin') === 'v42';

      if (isAdminCategoryV42) {
        const headers = new Headers(init.headers || {});
        headers.set('Accept', 'application/json');
        headers.set('X-Requested-With', 'XMLHttpRequest');
        headers.set('X-MedPark-Admin-Category-Transport', 'v46');
        return originalFetch(TARGET_PATH, {
          ...init,
          headers,
          redirect: 'follow',
          cache: 'no-store',
        });
      }
    } catch (_error) {
      // Fall through to the original request if URL inspection fails.
    }
    return originalFetch(input, init);
  };

  window.__MEDPARK_ADMIN_WORK_CATEGORY_TRANSPORT__ = 'v46-dedicated-endpoint';
})();
