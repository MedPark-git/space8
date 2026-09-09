(() => {
  const nativeFetch = window.fetch.bind(window);
  const BASE = '/admin?section=work-categories';

  const makeHidden = (name, value) => {
    const input = document.createElement('input');
    input.type = 'hidden';
    input.name = name;
    input.value = String(value ?? '');
    return input;
  };

  const submitNative = (body) => {
    const operation = String(body.get('operation') || '').trim();
    if (!operation) return false;

    const form = document.createElement('form');
    form.method = 'post';
    form.action = `${BASE}&wcop=${encodeURIComponent(operation)}`;
    form.enctype = 'application/x-www-form-urlencoded';
    form.acceptCharset = 'UTF-8';
    form.noValidate = true;
    form.style.display = 'none';

    const skip = new Set(['csrf_token', 'operation', 'awc_operation', 'awc_source', 'awc_response']);
    for (const [key, value] of body.entries()) {
      if (skip.has(key)) continue;
      form.append(makeHidden(key, value));
    }

    const currentToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
    form.append(makeHidden('csrf_token', currentToken));
    form.append(makeHidden('operation', operation));
    form.append(makeHidden('awc_operation', operation));
    form.append(makeHidden('awc_source', 'v32-native-form'));
    form.append(makeHidden('awc_response', 'html'));

    document.body.append(form);
    HTMLFormElement.prototype.submit.call(form);
    return true;
  };

  window.fetch = function medparkAdminWorkCategoryNativeV32(input, init = {}) {
    const method = String(init.method || 'GET').toUpperCase();
    const body = init.body;
    let url;
    try {
      const raw = typeof input === 'string' ? input : input?.url;
      url = new URL(raw || '', window.location.href);
    } catch (_error) {
      return nativeFetch(input, init);
    }

    const isWorkCategoryWrite = (
      method === 'POST'
      && body instanceof FormData
      && String(body.get('operation') || '').trim()
      && (
        url.pathname === '/awc-api-v24'
        || (url.pathname === '/admin' && url.searchParams.get('section') === 'work-categories')
      )
    );

    if (!isWorkCategoryWrite) {
      return nativeFetch(input, init);
    }

    if (submitNative(body)) {
      return new Promise(() => {});
    }
    return nativeFetch(input, init);
  };

  window.__MEDPARK_ADMIN_WORK_CATEGORY_TRANSPORT__ = 'v32-native-form';
})();
