(() => {
  const lines = document.getElementById("invoice-lines");
  const template = document.getElementById("line-template");
  const addButton = document.getElementById("add-item");
  const count = document.getElementById("line-count");
  const estimate = document.getElementById("estimate");
  const form = document.getElementById("invoice-form");
  const feedback = document.getElementById("invoice-form-feedback");
  const submitButton = document.getElementById("invoice-submit");
  const customers = document.querySelector("[data-lookup-kind='customers']");
  const english = form?.dataset.locale === "en";
  const copy = english ? {
    duplicatePet: "A pet can appear only once on an invoice. Choose another pet or remove the duplicate row.",
    duplicateItem: "This item is already on another row. Update its quantity there, then remove the duplicate row.",
    selectOne: "Choose an item",
    noResults: "No results found. Try a code or another search term.",
    showing: "Showing",
    options: "options",
    moreHint: "Load more or enter a narrower search term.",
    more: "Show more",
    searching: "Searching…",
    loadingMore: "Loading more…",
    loadError: "Could not load the list. Please try again.",
    left: "left",
    submitting: "Creating invoice…",
  } : {
    duplicatePet: "Thú cưng chỉ có thể xuất hiện một lần trong hóa đơn. Hãy chọn cá thể khác hoặc xóa dòng trùng.",
    duplicateItem: "Mặt hàng đã có ở dòng khác. Hãy cộng số lượng vào dòng đã có rồi xóa dòng trùng.",
    selectOne: "Chọn một mục",
    noResults: "Không tìm thấy kết quả. Thử mã hoặc từ khóa khác.",
    showing: "Đang hiển thị",
    options: "lựa chọn",
    moreHint: "Có thể tải thêm hoặc nhập từ khóa cụ thể hơn.",
    more: "Hiển thị thêm",
    searching: "Đang tìm…",
    loadingMore: "Đang tải thêm…",
    loadError: "Không tải được danh sách. Hãy thử lại.",
    left: "còn",
    submitting: "Đang lập hóa đơn…",
  };

  if (!lines || !template || !addButton) return;

  const currencyCode = form.dataset.currency || "VND";
  const currencyPrecision = Number(form.dataset.currencyPrecision || 0);
  const numberLocale = english ? "en-US" : "vi-VN";
  const integerFormatter = new Intl.NumberFormat(numberLocale, { maximumFractionDigits: 0 });
  const decimalSeparator = new Intl.NumberFormat(numberLocale)
    .formatToParts(1.1).find(part => part.type === "decimal")?.value || ",";
  const minorScale = 10n ** BigInt(currencyPrecision);

  function toMinorUnits(value) {
    const [whole = "0", fraction = ""] = String(value).split(".");
    const normalizedFraction = currencyPrecision
      ? fraction.slice(0, currencyPrecision).padEnd(currencyPrecision, "0")
      : "0";
    return BigInt(whole || "0") * minorScale + BigInt(normalizedFraction || "0");
  }

  function formatMoney(amount) {
    const minorUnits = typeof amount === "bigint" ? amount : toMinorUnits(amount);
    const whole = currencyPrecision ? minorUnits / minorScale : minorUnits;
    const fraction = currencyPrecision
      ? `${decimalSeparator}${String(minorUnits % minorScale).padStart(currencyPrecision, "0")}`
      : "";
    return `${integerFormatter.format(whole)}${fraction}\u00a0${currencyCode}`;
  }

  function refresh() {
    const rows = [...lines.querySelectorAll(".invoice-line")];
    const selectedValues = new Set();
    let total = 0n;
    for (const row of rows) {
      const select = row.querySelector(".item-select");
      const quantity = row.querySelector(".quantity-input");
      const option = select.options[select.selectedIndex];
      const isPet = option && option.dataset.kind === "pet";
      const duplicate = Boolean(select.value && selectedValues.has(select.value));
      if (select.value) selectedValues.add(select.value);
      select.classList.toggle("field-invalid", duplicate);
      if (duplicate) select.setAttribute("aria-invalid", "true");
      else select.removeAttribute("aria-invalid");
      if (isPet && quantity) {
        quantity.value = "1";
        quantity.readOnly = true;
      } else if (quantity) {
        quantity.readOnly = false;
      }
      if (option && option.dataset.price) {
        const quantityValue = Math.max(1, Number.parseInt(quantity.value, 10) || 1);
        total += toMinorUnits(option.dataset.price) * BigInt(quantityValue);
      }
      const remove = row.querySelector(".remove-line");
      if (remove) remove.disabled = rows.length === 1;
    }
    count.textContent = String(rows.length);
    estimate.textContent = formatMoney(total);
    const duplicateSelect = rows.map(row => row.querySelector(".item-select"))
      .find(select => select?.getAttribute("aria-invalid") === "true");
    const duplicateExists = Boolean(duplicateSelect);
    feedback.hidden = !duplicateExists;
    if (duplicateExists) {
      feedback.textContent = duplicateSelect.selectedOptions[0]?.dataset.kind === "pet"
        ? copy.duplicatePet
        : copy.duplicateItem;
    }
  }

  function resetOptions(widget) {
    const select = widget.querySelector("[data-lookup-select]");
    const placeholder = select.options[0]?.textContent || copy.selectOne;
    select.replaceChildren(new Option(placeholder, ""));
  }

  function appendLookupOptions(widget, payload, append) {
    const select = widget.querySelector("[data-lookup-select]");
    const kind = widget.dataset.lookupKind;
    if (!append) resetOptions(widget);
    if (kind === "customers") {
      for (const customer of payload.items || []) {
        select.add(new Option(
          `${customer.full_name} · ${customer.phone}`,
          String(customer.id),
        ));
      }
      return;
    }

    const groups = {};
    const productLabel = widget.dataset.productLabel || "Sản phẩm";
    const petLabel = widget.dataset.petLabel || "Thú cưng đang bán";
    for (const label of [productLabel, petLabel]) {
      let group = [...select.querySelectorAll("optgroup")].find(item => item.label === label);
      if (!group) {
        group = document.createElement("optgroup");
        group.label = label;
        select.append(group);
      }
      groups[label] = group;
    }
    for (const product of payload.products || []) {
      const option = new Option(
        `${product.code} · ${product.name} · ${formatMoney(product.unit_price)} (${copy.left} ${product.stock_qty})`,
        `product:${product.id}`,
      );
      option.dataset.kind = "product";
      option.dataset.price = String(product.unit_price);
      option.dataset.name = product.name;
      groups[productLabel].append(option);
    }
    for (const pet of payload.pets || []) {
      const option = new Option(
        `${pet.code} · ${pet.name} · ${formatMoney(pet.sale_price)}`,
        `pet:${pet.id}`,
      );
      option.dataset.kind = "pet";
      option.dataset.price = String(pet.sale_price);
      option.dataset.name = pet.name;
      groups[petLabel].append(option);
    }
  }

  function describeLookup(widget, payload, append) {
    const status = widget.querySelector("[data-lookup-status]");
    const more = widget.querySelector("[data-lookup-more]");
    const loaded = [...widget.querySelectorAll("[data-lookup-select] option")]
      .filter(option => option.value).length;
    let total;
    let hasMore;
    if (widget.dataset.lookupKind === "customers") {
      total = payload.pagination.total;
      hasMore = payload.pagination.has_next;
      widget.dataset.lookupPage = String(payload.pagination.page);
    } else {
      total = payload.product_pagination.total + payload.pet_pagination.total;
      hasMore = payload.product_pagination.has_next || payload.pet_pagination.has_next;
      widget.dataset.productPage = String(payload.product_pagination.page);
      widget.dataset.petPage = String(payload.pet_pagination.page);
      widget.dataset.productHasMore = String(payload.product_pagination.has_next);
      widget.dataset.petHasMore = String(payload.pet_pagination.has_next);
    }
    if (status) {
      status.textContent = total === 0
        ? copy.noResults
        : english
          ? `${copy.showing} ${loaded} of ${total} ${copy.options}${hasMore ? `. ${copy.moreHint}` : "."}`
          : `${copy.showing} ${loaded} / ${total} ${copy.options}${hasMore ? `. ${copy.moreHint}` : "."}`;
    }
    if (more) {
      more.hidden = !hasMore;
      more.disabled = false;
      more.textContent = copy.more;
    }
  }

  function bindLookup(widget, autoload = false) {
    const input = widget.querySelector("[data-lookup-search]");
    const select = widget.querySelector("[data-lookup-select]");
    const status = widget.querySelector("[data-lookup-status]");
    const more = widget.querySelector("[data-lookup-more]");
    if (!input || !select || widget.dataset.lookupBound === "true") return;
    widget.dataset.lookupBound = "true";
    let timer;
    let controller;
    let query = "";

    async function load(append = false) {
      if (controller) controller.abort();
      controller = new AbortController();
      const activeController = controller;
      const params = new URLSearchParams({q: query});
      if (widget.dataset.lookupKind === "customers") {
        const page = append ? Number(widget.dataset.lookupPage || 1) + 1 : 1;
        params.set("page", String(page));
      } else {
        const productPage = append
          ? Number(widget.dataset.productPage || 1) + Number(widget.dataset.productHasMore === "true")
          : 1;
        const petPage = append
          ? Number(widget.dataset.petPage || 1) + Number(widget.dataset.petHasMore === "true")
          : 1;
        params.set("product_page", String(productPage));
        params.set("pet_page", String(petPage));
      }
      select.disabled = true;
      if (more) more.disabled = true;
      if (status) status.textContent = append ? copy.loadingMore : copy.searching;
      try {
        const response = await fetch(`${widget.dataset.source}?${params}`, {
          credentials: "same-origin",
          headers: {"Accept": "application/json"},
          signal: activeController.signal,
        });
        if (!response.ok) throw new Error(copy.loadError);
        let payload = await response.json();
        if (append && widget.dataset.lookupKind === "items") {
          payload = {
            ...payload,
            products: widget.dataset.productHasMore === "true" ? payload.products : [],
            pets: widget.dataset.petHasMore === "true" ? payload.pets : [],
          };
        }
        appendLookupOptions(widget, payload, append);
        describeLookup(widget, payload, append);
      } catch (error) {
        if (error.name !== "AbortError" && status) {
          status.textContent = error.message || copy.loadError;
        }
      } finally {
        if (controller === activeController) {
          select.disabled = false;
          if (more) more.disabled = false;
        }
      }
    }

    input.addEventListener("input", () => {
      query = input.value.trim();
      widget.dataset.lookupPage = "0";
      widget.dataset.productPage = "0";
      widget.dataset.petPage = "0";
      resetOptions(widget);
      select.disabled = true;
      if (more) {
        more.hidden = true;
        more.disabled = true;
      }
      clearTimeout(timer);
      timer = setTimeout(() => load(false), 250);
    });
    more?.addEventListener("click", () => load(true));
    if (autoload) load(false);
  }

  addButton.addEventListener("click", () => {
    lines.append(template.content.cloneNode(true));
    const row = lines.lastElementChild;
    bindLookup(row.querySelector("[data-lookup-widget]"), true);
    refresh();
    row.querySelector("[data-lookup-search]")?.focus();
  });

  lines.addEventListener("click", event => {
    const button = event.target.closest(".remove-line");
    if (button && lines.querySelectorAll(".invoice-line").length > 1) {
      button.closest(".invoice-line").remove();
      refresh();
    }
  });

  customers && bindLookup(customers);
  lines.querySelectorAll("[data-lookup-widget]").forEach(widget => bindLookup(widget));
  lines.addEventListener("change", refresh);
  lines.addEventListener("input", refresh);
  form?.addEventListener("submit", event => {
    const customerSelect = customers?.querySelector("[data-lookup-select]");
    const selected = [...lines.querySelectorAll(".item-select")];
    const duplicate = selected.find(select => select.getAttribute("aria-invalid") === "true");
    if (!customerSelect?.value || selected.some(select => !select.value) || duplicate) {
      event.preventDefault();
      if (!customerSelect?.value) customers?.querySelector("[data-lookup-search]")?.focus();
      else (duplicate || selected.find(select => !select.value))?.focus();
      return;
    }
    if (submitButton) {
      submitButton.disabled = true;
      submitButton.textContent = copy.submitting;
    }
  });
  refresh();
})();
