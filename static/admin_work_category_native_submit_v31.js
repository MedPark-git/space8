(() => {
  const nativeFetch = window.fetch.bind(window);
  const TARGET = '/admin?section=work-categories&awc_native=v31';

  const makeHidden = (name, value) => {
    const input = document.createElement('input');
    input.type = 'hidden';
    input.name = name;
    input.value = String(value ?? '');
    return input;
  };

  const submitNative = (body) => {
    const form = document.createElement('form');
    form.method = 'post';
    form.action = TARGET;
    form.style.display = 'none';

    const seen = new Set();
    for (const [key, value] of body.entries()) {
      if (seen.has(key)) continue;
      seen.add(key);
      if (key === 'awc_source') {
        form.append(makeHidden(key, 'v31-native-form'));
      } else if (key === 'awc_response') {
        form.append(makeHidden(key, 'html'));
      } else {
        form.append(makeHidden(key, value));
      }
    }

    if (!seen.has('csrf_token')) {
      const token = document.querySelector('meta[name="csrf-token"]')?.content || '';
      form.append(makeHidden('csrf_token', token));
    }
    if (!seen.has('awc_source')) form.append(makeHidden('awc_source', 'v31-native-form'));
    if (!seen.has('awc_response')) form.append(makeHidden('awc_response', 'html'));

    document.body.append(form);
    HTMLFormElement.prototype.submit.call(form);
  };

  window.fetch = function medparkAdminWorkCategoryNativeV31(input, init = {}) {
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
      && (
        url.pathname === '/awc-api-v24'
        || (url.pathname === '/admin' && url.searchParams.get('section') === 'work-categories')
      )
      && String(body.get('operation') || '')
    );

    if (!isWorkCategoryWrite) {
      return nativeFetch(input, init);
    }

    submitNative(body);
    return new Promise(() => {});
  };

  window.__MEDPARK_ADMIN_WORK_CATEGORY_TRANSPORT__ = 'v31-native-form';
})();
