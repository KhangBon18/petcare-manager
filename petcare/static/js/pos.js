(() => {
  const form = document.querySelector("[data-pos]");
  if (!form?.invoiceUI) return;
  const english = form.dataset.locale === "en";
  const copy = english ? {
    add: "Add", added: "Selected", left: "left", product: "Product", pet: "Pet",
    loading: "Loading catalog…", error: "Could not load the catalog. Try again.",
    empty: "No matching items. Try another name or code.", saving: "Saving customer…",
    customerError: "Could not save the customer. Please try again.",
    customerSaved: "Customer added to this order.", unavailable: "Item unavailable",
    loadMore: "Show more", ready: "Select an item to add it to the order.",
  } : {
    add: "Thêm", added: "Đã chọn", left: "còn", product: "Sản phẩm", pet: "Thú cưng",
    loading: "Đang tải danh mục…", error: "Không tải được danh mục. Vui lòng thử lại.",
    empty: "Chưa có mặt hàng phù hợp. Thử tên hoặc mã khác.", saving: "Đang lưu khách hàng…",
    customerError: "Không lưu được khách hàng. Vui lòng thử lại.",
    customerSaved: "Đã thêm khách hàng vào đơn hiện tại.", unavailable: "Mặt hàng không còn khả dụng",
    loadMore: "Hiển thị thêm", ready: "Chọn mặt hàng để thêm vào đơn.",
  };
  const lines = document.getElementById("invoice-lines");
  const results = form.querySelector("[data-pos-results]");
  const search = form.querySelector("[data-pos-search]");
  const status = form.querySelector("[data-pos-status]");
  const retry = form.querySelector("[data-pos-retry]");
  const skeleton = form.querySelector("[data-pos-skeleton]");
  const empty = form.querySelector("[data-pos-empty]");
  const cartEmpty = form.querySelector("[data-cart-empty]");
  const mobileCartCount = form.querySelector("[data-pos-mobile-count]");
  const mobileCartTotal = form.querySelector("[data-pos-mobile-total]");
  const estimate = document.getElementById("estimate");
  const more = form.querySelector("[data-pos-more]");
  const submit = document.getElementById("invoice-submit");
  const catalog = new Map();
  const money = form.invoiceUI.formatMoney;
  let filter = "all";
  let controller = null;
  let timer;
  let busy = false;
  form.classList.add("pos-enabled");

  function remember(card) {
    const item = {...card.dataset};
    item.stock = Number(item.stock);
    catalog.set(item.selection, item);
  }
  results.querySelectorAll("[data-pos-item]").forEach(remember);
  lines.querySelectorAll(".invoice-line").forEach(row => {
    if (!row.querySelector(".item-select").value && !row.querySelector("[data-server-error]")) row.remove();
  });

  function paintCartRow(row) {
    const select = row.querySelector(".item-select");
    const info = row.querySelector("[data-cart-info]");
    if (!select.value) return;
    const item = catalog.get(select.value);
    info.hidden = false;
    info.querySelector("[data-cart-name]").textContent = item?.name || copy.unavailable;
    info.querySelector("[data-cart-detail]").textContent = item
      ? `${money(item.price)} · ${copy.left} ${item.stock}` : select.value;
    const image = info.querySelector("[data-cart-image]");
    image.dataset.kind = item?.kind || "pet";
    if (item?.photo && image.dataset.photo !== item.photo) {
      const img = document.createElement("img"); img.width = 640; img.height = 352;
      img.src = item.photo; img.alt = item.name;
      image.replaceChildren(img); image.dataset.photo = item.photo;
    } else if (!item?.photo) {
      const icon = window.PetCare.icon(item?.kind === "product" ? "products" : "pets");
      if (icon) image.replaceChildren(icon);
      delete image.dataset.photo;
    }
    const quantity = row.querySelector(".quantity-input");
    if (item && select.selectedOptions[0]) select.selectedOptions[0].dataset.price = item.price;
    if (item && !quantity.dataset.serverError) quantity.max = String(item.stock);
  }

  function updateCart() {
    const rows = [...lines.querySelectorAll(".invoice-line")];
    const quantities = new Map(rows.map(row => [row.querySelector(".item-select").value,
      Number(row.querySelector(".quantity-input").value)]));
    rows.forEach(paintCartRow);
    form.invoiceUI.refresh();
    cartEmpty.hidden = rows.length > 0;
    submit.disabled = rows.length === 0;
    const itemCount = rows.reduce((total, row) => {
      const selected = Boolean(row.querySelector(".item-select").value);
      const quantity = Number(row.querySelector(".quantity-input").value);
      return selected && Number.isSafeInteger(quantity) && quantity > 0 ? total + quantity : total;
    }, 0);
    if (mobileCartCount) {
      mobileCartCount.textContent = english
        ? `${itemCount} item${itemCount === 1 ? "" : "s"} in order`
        : `${itemCount} mặt hàng trong đơn`;
    }
    if (mobileCartTotal && estimate) mobileCartTotal.textContent = estimate.textContent;
    results.querySelectorAll("[data-pos-item]").forEach(card => {
      const chosen = quantities.get(card.dataset.selection) || 0;
      const exhausted = Number(card.dataset.stock) <= chosen;
      card.disabled = exhausted;
      card.classList.toggle("pos-card-selected", chosen > 0);
      card.querySelector("[data-pos-action]").textContent = chosen > 0 ? `${copy.added} · ${chosen}` : copy.add;
    });
  }

  function filterCards() {
    const cards = [...results.querySelectorAll("[data-pos-item]")];
    cards.forEach(card => { card.hidden = filter !== "all" && card.dataset.kind !== filter; });
    const visible = cards.filter(card => !card.hidden).length;
    empty.hidden = busy || visible > 0;
    more.hidden = !((filter !== "pet" && more.dataset.productHasMore === "true") ||
      (filter !== "product" && more.dataset.petHasMore === "true"));
    if (!busy) status.textContent = visible ? `${visible} ${english ? "items" : "mặt hàng"} · ${copy.ready}` : copy.empty;
    updateCart();
  }

  function makeCard(item) {
    const card = document.createElement("button"); card.type = "button"; card.className = "pos-card";
    Object.assign(card.dataset, item, {posItem: ""});
    const art = document.createElement("span"); art.className = "pos-card-image";
    if (item.photo) {
      const img = document.createElement("img"); img.src = item.photo; img.alt = item.name; img.loading = "lazy";
      art.append(img);
    } else {
      const icon = window.PetCare.icon(item.kind === "product" ? "products" : "pets");
      if (icon) art.append(icon);
    }
    const kind = document.createElement("span"); kind.className = "pos-kind";
    kind.textContent = item.kind === "pet" ? copy.pet : copy.product; art.append(kind);
    const body = document.createElement("span"); body.className = "pos-card-copy";
    for (const [tag, text] of [["small", item.code], ["strong", item.name], ["b", money(item.price)]]) {
      const node = document.createElement(tag); node.textContent = text; body.append(node);
    }
    const stock = document.createElement("span"); stock.className = "pos-card-stock";
    stock.append(document.createTextNode(`${copy.left} ${item.stock} · `));
    const action = document.createElement("span"); action.dataset.posAction = ""; action.textContent = copy.add;
    stock.append(action); body.append(stock); card.append(art, body); return card;
  }

  function setLoading(loading) {
    busy = loading;
    results.setAttribute("aria-busy", String(loading));
    skeleton.hidden = !loading;
    results.hidden = loading;
    more.disabled = loading;
    more.textContent = loading ? copy.loading : copy.loadMore;
    if (retry) retry.hidden = true;
    if (loading) { empty.hidden = true; status.textContent = copy.loading; }
  }

  async function load(append = false) {
    controller?.abort();
    const active = new AbortController(); controller = active;
    const productMore = more.dataset.productHasMore === "true" && filter !== "pet";
    const petMore = more.dataset.petHasMore === "true" && filter !== "product";
    const query = new URLSearchParams({q: search.value.trim(),
      product_page: String(append ? Number(more.dataset.productPage) + Number(productMore) : 1),
      pet_page: String(append ? Number(more.dataset.petPage) + Number(petMore) : 1)});
    setLoading(true);
    try {
      const response = await fetch(`${search.dataset.source}?${query}`, {
        credentials: "same-origin", headers: {Accept: "application/json"}, signal: active.signal,
      });
      if (!response.ok) throw new Error(copy.error);
      const payload = await response.json();
      if (controller !== active || active.signal.aborted) return;
      if (!append) results.replaceChildren();
      const shown = new Set([...results.querySelectorAll("[data-pos-item]")].map(card => card.dataset.selection));
      for (const [kind, rows] of [["product", !append || productMore ? payload.products : []],
                                ["pet", !append || petMore ? payload.pets : []]]) {
        for (const row of rows) {
          const item = {selection: `${kind}:${row.id}`, kind, name: row.name, code: row.code,
            price: String(kind === "pet" ? row.sale_price : row.unit_price),
            stock: kind === "pet" ? 1 : row.stock_qty, photo: row.photo_url || ""};
          catalog.set(item.selection, item);
          if (!shown.has(item.selection)) { results.append(makeCard(item)); shown.add(item.selection); }
        }
      }
      for (const kind of ["product", "pet"]) {
        more.dataset[`${kind}Page`] = String(payload[`${kind}_pagination`].page);
        more.dataset[`${kind}HasMore`] = String(payload[`${kind}_pagination`].has_next);
      }
      setLoading(false); filterCards();
      window.PetCare?.motion?.reveal(results.querySelectorAll("[data-pos-item]"));
    } catch (error) {
      if (controller !== active || active.signal.aborted) return;
      setLoading(false); filterCards(); status.textContent = copy.error;
      if (retry) retry.hidden = false;
    }
  }

  results.addEventListener("click", event => {
    const card = event.target.closest("[data-pos-item]");
    if (!card || card.disabled || busy) return;
    const item = catalog.get(card.dataset.selection);
    let row = [...lines.querySelectorAll(".invoice-line")].find(line => line.querySelector(".item-select").value === item.selection);
    if (row) {
      const quantity = row.querySelector(".quantity-input");
      if (item.kind === "pet") return;
      quantity.value = String(Math.min(item.stock, Number(quantity.value || 0) + 1));
      quantity.dispatchEvent(new Event("input", {bubbles: true}));
    } else {
      document.getElementById("add-item").click();
      row = lines.lastElementChild;
      const select = row.querySelector(".item-select");
      const option = new Option(item.name, item.selection);
      Object.assign(option.dataset, {price: item.price, kind: item.kind, name: item.name});
      select.add(option); select.value = item.selection;
      row.querySelector(".quantity-input").value = "1";
      select.dispatchEvent(new Event("change", {bubbles: true}));
    }
    paintCartRow(row); updateCart();
    window.PetCare?.motion?.feedback([row.querySelector("[data-cart-image]"), document.getElementById("estimate")]);
    row.querySelector(".quantity-input").focus();
  });
  search.addEventListener("input", () => {
    clearTimeout(timer); controller?.abort(); controller = null;
    setLoading(true); timer = setTimeout(() => load(), 250);
  });
  more.addEventListener("click", () => load(true));
  retry?.addEventListener("click", () => load());
  form.querySelectorAll("[data-pos-filter]").forEach(button => button.addEventListener("click", () => {
    filter = button.dataset.posFilter;
    form.querySelectorAll("[data-pos-filter]").forEach(tab => tab.setAttribute("aria-pressed", String(tab === button)));
    filterCards();
  }));
  for (const name of ["input", "change", "click"]) lines.addEventListener(name, updateCart);
  window.addEventListener("pagehide", () => {
    clearTimeout(timer); controller?.abort(); controller = null;
    setLoading(false); filterCards();
  });
  form.invoiceUI.refresh(); filterCards();

  const dialog = document.getElementById("quick-customer-dialog");
  const quickForm = document.getElementById("quick-customer-form");
  const open = form.querySelector("[data-quick-customer-open]");
  let saving = false;
  let closeFocus = open;
  open.addEventListener("click", () => { closeFocus = open; dialog.showModal(); quickForm.querySelector('[name="full_name"]').focus(); window.PetCare?.motion?.reveal([dialog]); });
  dialog.querySelectorAll("[data-quick-customer-close]").forEach(button => button.addEventListener("click", () => dialog.close()));
  dialog.addEventListener("close", () => closeFocus.focus());
  quickForm.addEventListener("submit", async event => {
    event.preventDefault(); if (saving) return;
    saving = true;
    const save = quickForm.querySelector('[type="submit"]'); const label = save.textContent;
    save.disabled = true; save.textContent = copy.saving; quickForm.setAttribute("aria-busy", "true");
    const feedback = quickForm.querySelector("[data-quick-error]"); feedback.hidden = true;
    quickForm.querySelectorAll(".field-error").forEach(node => { node.hidden = true; });
    quickForm.querySelectorAll('[aria-invalid="true"]').forEach(node => node.removeAttribute("aria-invalid"));
    const values = Object.fromEntries(new FormData(quickForm));
    try {
      const response = await fetch(quickForm.action, {method: "POST", credentials: "same-origin",
        headers: {"Content-Type": "application/json", "X-CSRFToken": values.csrf_token, Accept: "application/json"},
        body: JSON.stringify({full_name: values.full_name, phone: values.phone, address: values.address})});
      const payload = await response.json();
      if (!response.ok) {
        feedback.textContent = payload.error || copy.customerError; feedback.hidden = false;
        for (const [field, message] of Object.entries(payload.errors || {})) {
          const input = quickForm.elements.namedItem(field); const error = document.getElementById(`quick-${field}-error`);
          if (!input || !error) continue;
          input.setAttribute("aria-invalid", "true"); input.setAttribute("aria-describedby", error.id);
          error.textContent = message; error.hidden = false;
        }
        (quickForm.querySelector('[aria-invalid="true"]') || feedback).focus(); return;
      }
      const customer = payload.customer;
      const select = document.getElementById("customer_id");
      select.closest("[data-lookup-widget]").dispatchEvent(new Event("lookup-dispose"));
      select.add(new Option(`${customer.full_name} · ${customer.phone}`, String(customer.id)));
      select.value = String(customer.id); select.dispatchEvent(new Event("change", {bubbles: true}));
      quickForm.reset(); closeFocus = select; dialog.close();
      if (window.PetCare?.toast) window.PetCare.toast(copy.customerSaved);
    } catch (_error) { feedback.textContent = copy.customerError; feedback.hidden = false; }
    finally { saving = false; save.disabled = false; save.textContent = label; quickForm.setAttribute("aria-busy", "false"); }
  });
})();
