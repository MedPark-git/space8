(() => {
  const nativeFetch = window.fetch.bind(window);
  const TARGET = '/api/admin/work-category-v38';

  const xhrRequest = (body, operation) => new Promise((resolve, reject) => {
    const encoded = new URLSearchParams();
    for (const [key, value] of body.entries()) {
      if (key === 'csrf_token') continue;
      encoded.set(key, String(value ?? ''));
    }
    encoded.set('operation', operation);
    encoded.set('awc_operation', operation);
    encoded.set('awc_source', 'v38-xhr');
    encoded.set('awc_response', 'json');

    const xhr = new XMLHttpRequest();
    xhr.open('POST', TARGET, true);
    xhr.withCredentials = true;
    xhr.setRequestHeader('Accept', 'application/json');
    xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded; charset=UTF-8');
    xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
    xhr.setRequestHeader('X-MedPark-Admin-Category', 'v38');
    xhr.setRequestHeader('X-MedPark-Admin-Operation', operation);

    xhr.onload = () => {
      const contentType = xhr.getResponseHeader('Content-Type') || 'application/json';
      const response = new Response(xhr.responseText || '', {
        status: xhr.status || 500,
        statusText: xhr.statusText || '',
        headers: { 'Content-Type': contentType },
      });
      try {
        Object.defineProperty(response, 'url', { value: new URL(TARGET, location.origin).href });
      } catch (_error) {}
      resolve(response);
    };
    xhr.onerror = () => reject(new TypeError('업무구분 요청 중 네트워크 오류가 발생했습니다.'));
    xhr.ontimeout = () => reject(new TypeError('업무구분 요청 시간이 초과되었습니다.'));
    xhr.timeout = 15000;
    xhr.send(encoded.toString());
  });

  window.fetch = function medparkAdminWorkCategoryV38(input, init = {}) {
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
        || (url.pathname === '/tasks/new' && url.searchParams.get('awc_admin') === '1')
      )
    );

    if (!isAdminWorkCategoryWrite) return nativeFetch(input, init);
    return xhrRequest(body, operation);
  };

  window.__MEDPARK_ADMIN_WORK_CATEGORY_TRANSPORT__ = 'v38-xhr';
})();
