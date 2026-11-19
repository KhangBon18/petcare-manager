(() => {
  const receiveForm = document.querySelector('[data-purchase-receive-form]');
  if (receiveForm) {
    const fillRemaining = receiveForm.querySelector('[data-fill-remaining]');
    const feedback = receiveForm.querySelector('[data-receive-feedback]');
    fillRemaining?.addEventListener('click', () => {
      let units = 0;
      receiveForm.querySelectorAll('input[name="quantity[]"]').forEach((input) => {
        if (input.disabled) return;
        const remaining = Number(input.max || 0);
        input.value = String(remaining);
        units += remaining;
      });
      if (feedback) {
        feedback.textContent = document.documentElement.lang === 'en'
          ? `Filled ${units} remaining unit${units === 1 ? '' : 's'}. Review before confirming.`
          : `Đã điền ${units.toLocaleString('vi-VN')} đơn vị còn thiếu. Hãy kiểm tra trước khi xác nhận.`;
      }
    });
  }

  const form = document.querySelector('[data-purchase-form]');
  if (!form) return;

  const query = form.querySelector('[data-product-query]');
  const results = form.querySelector('[data-product-results]');
  const status = form.querySelector('[data-product-status]');
  const body = form.querySelector('[data-order-lines]');
  const empty = form.querySelector('[data-lines-empty]');
  const lineCount = form.querySelector('[data-line-count]');
  const estimate = form.querySelector('[data-order-estimate]');
  const template = document.querySelector('#purchase-line-template');
  const currency = form.dataset.currency;
  let timer = 0;
  let requestNumber = 0;
  let controller = null;

  const selectedIds = () => new Set(
    [...body.querySelectorAll('input[name="product_id[]"]')].map((input) => input.value),
  );

  const updateTotals = () => {
    const rows = [...body.querySelectorAll('[data-order-line]')];
    const total = rows.reduce((sum, row) => {
      const quantity = Number(row.querySelector('input[name="quantity[]"]').value || 0);
      const cost = Number(row.querySelector('input[name="unit_cost[]"]').value || 0);
      return sum + quantity * cost;
    }, 0);
    lineCount.textContent = `${rows.length} ${document.documentElement.lang === 'en' ? 'items' : 'mặt hàng'}`;
    empty.hidden = rows.length > 0;
    try {
      estimate.textContent = new Intl.NumberFormat(
        document.documentElement.lang === 'en' ? 'en-US' : 'vi-VN',
        { style: 'currency', currency, maximumFractionDigits: 4 },
      ).format(total);
    } catch {
      estimate.textContent = `${total.toLocaleString()} ${currency}`;
    }
  };

  const renderResults = (items) => {
    const selected = selectedIds();
    results.replaceChildren();
    if (!items.length) {
      status.textContent = form.dataset.noResults;
      return;
    }
    status.textContent = document.documentElement.lang === 'en'
      ? 'Select an item to add it to this order.'
      : 'Chọn sản phẩm để thêm vào đơn.';
    for (const product of items) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'purchase-product-option';
      button.dataset.addProduct = '';
      button.dataset.productId = String(product.id);
      button.dataset.productCode = product.code;
      button.dataset.productName = product.name;
      const copy = document.createElement('span');
      copy.className = 'purchase-product-option-copy';
      const name = document.createElement('strong');
      name.textContent = product.name;
      const code = document.createElement('small');
      code.textContent = product.code;
      copy.append(name, code);
      const add = document.createElement('span');
      add.className = 'purchase-product-option-action';
      add.textContent = selected.has(String(product.id))
        ? (document.documentElement.lang === 'en' ? 'Added' : 'Đã có trong đơn')
        : (document.documentElement.lang === 'en' ? 'Add' : 'Thêm');
      button.disabled = selected.has(String(product.id));
      button.setAttribute('aria-label', `${add.textContent}: ${product.name} (${product.code})`);
      button.append(copy, add);
      results.append(button);
    }
  };

  const loadProducts = async () => {
    const currentRequest = ++requestNumber;
    if (controller) controller.abort();
    controller = new AbortController();
    status.textContent = form.dataset.loading;
    const url = new URL(form.dataset.productSearchUrl, window.location.origin);
    url.searchParams.set('q', query.value.trim());
    try {
      const response = await fetch(url, {
        credentials: 'same-origin',
        headers: { Accept: 'application/json' },
        signal: controller.signal,
      });
      const payload = await response.json();
      if (currentRequest !== requestNumber) return;
      if (!response.ok) throw new Error('catalog-unavailable');
      renderResults(Array.isArray(payload.items) ? payload.items : []);
    } catch (error) {
      if (error.name === 'AbortError' || currentRequest !== requestNumber) return;
      results.replaceChildren();
      status.textContent = form.dataset.searchError;
    }
  };

  const addLine = (button) => {
    const id = button.dataset.productId;
    if (selectedIds().has(id)) return;
    const rowCount = body.querySelectorAll('[data-order-line]').length;
    if (rowCount >= 100) {
      status.textContent = form.dataset.lineLimit;
      return;
    }
    const fragment = template.content.cloneNode(true);
    const row = fragment.querySelector('[data-order-line]');
    row.querySelector('[data-line-name]').textContent = button.dataset.productName;
    row.querySelector('[data-line-code]').textContent = button.dataset.productCode;
    row.querySelector('input[name="product_id[]"]').value = id;
    row.querySelector('input[name="product_label[]"]').value = button.dataset.productName;
    const unique = `${Date.now()}-${rowCount}`;
    const quantity = row.querySelector('input[name="quantity[]"]');
    const cost = row.querySelector('input[name="unit_cost[]"]');
    row.querySelector('[data-quantity-label]').htmlFor = `purchase-quantity-${unique}`;
    row.querySelector('[data-cost-label]').htmlFor = `purchase-cost-${unique}`;
    quantity.id = `purchase-quantity-${unique}`;
    cost.id = `purchase-cost-${unique}`;
    cost.setAttribute('aria-label', document.documentElement.lang === 'en'
      ? `Purchase cost for ${button.dataset.productName}`
      : `Giá nhập · ${button.dataset.productName}`);
    body.append(fragment);
    updateTotals();
    renderResults([...results.querySelectorAll('[data-add-product]')].map((option) => ({
      id: Number(option.dataset.productId),
      code: option.dataset.productCode,
      name: option.dataset.productName,
    })));
    quantity.focus();
  };

  query.addEventListener('input', () => {
    window.clearTimeout(timer);
    timer = window.setTimeout(loadProducts, 220);
  });
  results.addEventListener('click', (event) => {
    const button = event.target.closest('[data-add-product]');
    if (button && !button.disabled) addLine(button);
  });
  body.addEventListener('click', (event) => {
    const button = event.target.closest('[data-remove-line]');
    if (!button) return;
    button.closest('[data-order-line]').remove();
    updateTotals();
    renderResults([...results.querySelectorAll('[data-add-product]')].map((option) => ({
      id: Number(option.dataset.productId), code: option.dataset.productCode,
      name: option.dataset.productName,
    })));
  });
  body.addEventListener('input', (event) => {
    if (event.target.matches('input[name="quantity[]"], input[name="unit_cost[]"]')) updateTotals();
  });
  form.addEventListener('submit', (event) => {
    if (body.querySelectorAll('[data-order-line]').length) return;
    event.preventDefault();
    status.textContent = form.dataset.emptySubmit;
    query.focus();
  });

  updateTotals();
  loadProducts();
})();
