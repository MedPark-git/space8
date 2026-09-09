(() => {
  const nativeFetch = window.fetch.bind(window);
  const ENDPOINT = '/__internal/admin-work-category-v37';

  const makeHeaders = (xhr) => {
    const map = new Map();
    String(xhr.getAllResponseHeaders() || '').trim().split(/[\r\n]+/).forEach((line) => {
      if (!line) return;
      const index = line.indexOf(':');
      if (index < 0) return;
      map.set(line.slice(0, index).trim().toLowerCase(), line.slice(index + 1).trim());
    });
    return {
      get(name) { return map.get(String(name || '').toLowerCase()) || null; },
    };
  };

  const xhrPost = (operation, sourceBody) => new Promise((resolve, reject) => {
    const body = new FormData();
    for (const [key, value] of sourceBody.entries()) {
      if (key === 'csrf_token' || key === 'awc_source' || key === 'awc_response') continue;
      body.set(key, value);
    }
    body.set('operation', operation);
    body.set('awc_operation', operation);
    body.set('awc_source', 'v37-direct-xhr');
    body.set('awc_response', 'json');

    const xhr = new XMLHttpRequest();
    xhr.open('POST', ENDPOINT, true);
    xhr.withCredentials = true;
    xhr.setRequestHeader('Accept', 'application/json');
    xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
    xhr.setRequestHeader('X-MedPark-Admin-Category', 'v37');
    xhr.setRequestHeader('X-MedPark-Admin-Operation', operation);

    xhr.onload = () => {
      const response = {
        ok: xhr.status >= 200 && xhr.status < 300,
        status: xhr.status,
        statusText: xhr.statusText,
        url: `${window.location.origin}${ENDPOINT}`,
        headers: makeHeaders(xhr),
        text: async () => xhr.responseText || '',
        json: async () => {
          try { return JSON.parse(xhr.responseText || '{}'); }
          catch (_error) { return {}; }
        },
      };
      resolve(response);
    };
    xhr.onerror = () => reject(new Error('업무구분 서버 연결에 실패했습니다.'));
    xhr.ontimeout = () => reject(new Error('업무구분 서버 응답 시간이 초과되었습니다.'));
    xhr.timeout = 20000;
    xhr.send(body);
  });

  window.fetch = function medparkAdminWorkCategoryV37(input, init = {}) {
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
        || url.pathname === ENDPOINT
      )
    );

    if (!isAdminWorkCategoryWrite) return nativeFetch(input, init);
    return xhrPost(operation, body);
  };

  window.__MEDPARK_ADMIN_WORK_CATEGORY_TRANSPORT__ = 'v37-direct-xhr';
})();
