(() => {
  const launcher = document.getElementById("assistant-launcher");
  const panel = document.getElementById("assistant-panel");
  const pageOpeners = document.querySelectorAll("[data-assistant-open]");
  const close = document.getElementById("assistant-close");
  const clear = document.getElementById("assistant-clear");
  const form = document.getElementById("assistant-form");
  const input = document.getElementById("assistant-input");
  const messages = document.getElementById("assistant-messages");
  if (!launcher || !panel || !form || !input || !messages) return;

  const english = document.documentElement.lang === "en";
  const history = [];
  const welcomeNodes = Array.from(messages.children, node => node.cloneNode(true));
  let activeRequest = null;
  let previousFocus = launcher;
  const csrf = form.querySelector('[name="csrf_token"]')?.value || "";

  function setOpen(open) {
    if (open) previousFocus = document.activeElement;
    panel.hidden = !open;
    launcher.setAttribute("aria-expanded", String(open));
    pageOpeners.forEach(button => button.setAttribute("aria-expanded", String(open)));
    if (open) { input.focus(); window.PetCare?.motion?.reveal([panel]); }
    else previousFocus?.focus();
  }

  function appendMessage(text, role) {
    const bubble = document.createElement("div");
    bubble.className = `assistant-message ${role === "user" ? "assistant-message-user" : "assistant-message-bot"}`;
    bubble.textContent = text;
    messages.append(bubble);
    window.PetCare?.motion?.reveal([bubble]);
    messages.scrollTop = messages.scrollHeight;
    return bubble;
  }

  function renderCards(catalog, parent) {
    if (!catalog || !Array.isArray(catalog.items)) return;
    const group = document.createElement("div"); group.className = "assistant-catalog"; group.setAttribute("role", "group");
    const heading = document.createElement("strong");
    heading.textContent = english ? `${catalog.total} database matches · showing ${catalog.items.length}` : `${catalog.total} kết quả từ MySQL · hiển thị ${catalog.items.length}`;
    group.append(heading);
    for (const item of catalog.items) {
      if (typeof item.url !== "string" || !/^\/(pets|products)\/\d+$/.test(item.url)) continue;
      const card = document.createElement("article"); card.className = "assistant-result-card";
      if (item.photo_url && /^\/(pets|products)\/photo\//.test(item.photo_url)) {
        const image = document.createElement("img"); image.width = 72; image.height = 84;
        image.src = item.photo_url; image.alt = item.name;
        image.loading = "lazy"; card.append(image);
      } else {
        const art = document.createElement("span"); art.className = "assistant-result-art";
        art.append(window.PetCare.icon(item.kind === "pet" ? "pets" : "products")); card.append(art);
      }
      const body = document.createElement("div");
      const title = document.createElement("strong"); title.textContent = item.name;
      const meta = document.createElement("small"); meta.textContent = `${item.code} · ${item.status_label} · ${english ? "stock" : "tồn"} ${item.stock}`;
      const price = document.createElement("b"); price.textContent = item.price_label;
      const link = document.createElement("a"); link.href = item.url;
      link.textContent = english ? "Open profile →" : "Mở hồ sơ →";
      body.append(title, meta, price, link); card.append(body); group.append(card);
    }
    parent.append(group);
    window.PetCare?.motion?.reveal(group.querySelectorAll(".assistant-result-card"));
  }

  function renderInsight(insight, parent) {
    if (!insight || insight.kind !== "top_products" || !Array.isArray(insight.items)) return;
    const periodLabels = english
      ? {today:"today", "7d":"the last 7 days", week:"this week", last_week:"last week", month:"this month", last_month:"last month"}
      : {today:"hôm nay", "7d":"7 ngày gần nhất", week:"tuần này", last_week:"tuần trước", month:"tháng này", last_month:"tháng trước"};
    const group = document.createElement("div");
    group.className = "assistant-catalog assistant-insight";
    group.setAttribute("role", "group");
    group.setAttribute("aria-label", english ? "Top product sales" : "Sản phẩm bán chạy");
    const heading = document.createElement("strong");
    heading.textContent = `${english ? "Sales report" : "Báo cáo bán hàng"} · ${periodLabels[insight.period] || insight.period} · ${insight.start_date} – ${insight.end_date}`;
    group.append(heading);
    if (!insight.items.length) {
      const empty = document.createElement("small");
      empty.textContent = english ? "No product sales in this period." : "Không có sản phẩm bán trong kỳ này.";
      group.append(empty);
    }
    for (const item of insight.items.slice(0, 5)) {
      if (typeof item.url !== "string" || !/^\/products\/\d+$/.test(item.url)) continue;
      const card = document.createElement("article"); card.className = "assistant-result-card";
      const art = document.createElement("span"); art.className = "assistant-result-art";
      art.append(window.PetCare.icon("products"));
      const body = document.createElement("div");
      const title = document.createElement("strong"); title.textContent = item.name || "";
      const meta = document.createElement("small");
      meta.textContent = `${item.code || ""} · ${item.quantity_sold} ${english ? "net units sold" : "sản phẩm bán ròng"}`;
      const revenue = document.createElement("b"); revenue.textContent = item.revenue_label || "";
      const link = document.createElement("a"); link.href = item.url;
      link.textContent = english ? "Open product →" : "Mở sản phẩm →";
      body.append(title, meta, revenue, link); card.append(art, body); group.append(card);
    }
    parent.append(group);
    window.PetCare?.motion?.reveal(group.querySelectorAll(".assistant-result-card"));
  }

  function renderOperationsOverview(insight, parent) {
    if (!insight || insight.kind !== "operations_overview") return;
    const group = document.createElement("div");
    group.className = "assistant-catalog assistant-insight assistant-operations-overview";
    group.setAttribute("role", "group");
    group.setAttribute("aria-label", english ? "Store operations overview" : "Tổng quan vận hành cửa hàng");
    const heading = document.createElement("strong");
    heading.textContent = english ? "Store overview · current tenant" : "Tổng quan cửa hàng · tenant hiện tại";
    group.append(heading);

    function section(title, source) {
      const node = document.createElement("section");
      node.className = "assistant-overview-section";
      node.setAttribute("aria-label", title);
      const sectionHeading = document.createElement("strong");
      sectionHeading.textContent = title;
      node.append(sectionHeading);
      const sourceLabel = document.createElement("small");
      sourceLabel.className = "assistant-overview-source";
      sourceLabel.textContent = source;
      node.append(sourceLabel);
      group.append(node);
      return node;
    }

    function empty(node, text) {
      const label = document.createElement("small");
      label.className = "assistant-overview-empty";
      label.textContent = text;
      node.append(label);
    }

    const inventory = insight.inventory;
    const inventoryNode = section(
      english ? "Restock priorities" : "Ưu tiên bổ sung tồn",
      english ? "Inventory service · 8-week weighted forecast" : "Service tồn kho · dự báo trọng số 8 tuần"
    );
    if (inventory?.status !== "available") {
      empty(inventoryNode, english ? "Inventory data could not be loaded. Retry the overview." : "Chưa tải được dữ liệu tồn kho. Hãy thử lại tổng quan.");
    } else {
      const count = document.createElement("small");
      count.textContent = english
        ? `${inventory.total} products meet the warning rules · target ${inventory.target_days} days`
        : `${inventory.total} sản phẩm đạt ngưỡng cảnh báo · mục tiêu ${inventory.target_days} ngày`;
      inventoryNode.append(count);
      if (!inventory.items?.length) empty(inventoryNode, english ? "No products currently need attention." : "Hiện không có sản phẩm cần chú ý.");
      for (const item of (inventory.items || []).slice(0, 5)) {
        if (typeof item.url !== "string" || !/^\/products\/\d+$/.test(item.url)) continue;
        const card = document.createElement("article"); card.className = "assistant-result-card";
        const body = document.createElement("div");
        const title = document.createElement("strong"); title.textContent = item.name || "";
        const meta = document.createElement("small");
        meta.textContent = `${item.code || ""} · ${english ? "stock" : "tồn"} ${item.stock_qty} · ${english ? "reorder at" : "ngưỡng"} ${item.reorder_level}`;
        const suggestion = document.createElement("b");
        suggestion.textContent = english ? `Suggested add: ${item.suggested_qty}` : `Gợi ý nhập thêm: ${item.suggested_qty}`;
        const remaining = document.createElement("small");
        remaining.textContent = item.days_left == null
          ? (english ? "No recent paid sales; based on reorder level." : "Chưa có doanh số đã thu; dựa theo ngưỡng nhập lại.")
          : (english ? `About ${item.days_left} days of stock left.` : `Còn khoảng ${item.days_left} ngày hàng.`);
        const link = document.createElement("a"); link.href = item.url;
        link.textContent = english ? "Review product →" : "Xem sản phẩm →";
        body.append(title, meta, suggestion, remaining, link); card.append(body); inventoryNode.append(card);
      }
      if (inventory.total > (inventory.items || []).length) {
        const capped = document.createElement("small");
        capped.textContent = english ? "Showing the 5 highest-priority products." : "Đang hiển thị tối đa 5 sản phẩm ưu tiên nhất.";
        inventoryNode.append(capped);
      }
    }

    const purchasing = insight.purchasing;
    const purchasingNode = section(
      english ? "Purchase orders awaiting action" : "Đơn nhập cần xử lý",
      english ? "Purchasing service · admin-only · ordered and partially received" : "Service nhập hàng · chỉ admin · trạng thái đang đặt và nhận một phần"
    );
    const purchaseListUrl = typeof purchasing?.url === "string" && /^\/purchasing\/?$/.test(purchasing.url)
      ? purchasing.url : null;
    if (purchasing?.status !== "available") {
      empty(purchasingNode, english ? "Purchase-order data could not be loaded." : "Chưa tải được dữ liệu đơn nhập.");
    } else {
      const count = document.createElement("small");
      const counts = purchasing.status_counts || {};
      count.textContent = english
        ? `${purchasing.open_total} open · ordered ${counts.ordered || 0} · partially received ${counts.partially_received || 0}`
        : `${purchasing.open_total} đơn mở · đang đặt ${counts.ordered || 0} · nhận một phần ${counts.partially_received || 0}`;
      purchasingNode.append(count);
      if (!purchasing.items?.length) empty(purchasingNode, english ? "No outstanding orders." : "Không có đơn nhập đang chờ xử lý.");
      for (const item of (purchasing.items || []).slice(0, 5)) {
        if (typeof item.url !== "string" || !/^\/purchasing\/\d+$/.test(item.url)) continue;
        const card = document.createElement("article"); card.className = "assistant-result-card";
        const body = document.createElement("div");
        const title = document.createElement("strong");
        title.textContent = `${english ? "PO" : "Đơn nhập"} #${item.purchase_order_id} · ${item.supplier_name || ""}`;
        const meta = document.createElement("small");
        const status = item.status === "partially_received"
          ? (english ? "partially received" : "nhận một phần")
          : (english ? "ordered" : "đang đặt");
        meta.textContent = `${status} · ${item.received_units}/${item.ordered_units} ${english ? "units received" : "sản phẩm đã nhận"} · ${item.created_at_label || item.created_at || ""}`;
        const link = document.createElement("a"); link.href = item.url;
        link.textContent = english ? "Review order →" : "Xem đơn nhập →";
        body.append(title, meta, link); card.append(body); purchasingNode.append(card);
      }
      if (purchaseListUrl) {
        const link = document.createElement("a"); link.href = purchaseListUrl;
        link.className = "assistant-overview-action";
        link.textContent = english ? "Open all purchase orders →" : "Mở danh sách đơn nhập →";
        purchasingNode.append(link);
      }
    }

    const sales = insight.sales;
    const salesNode = section(
      english ? "Recent sales context · last 7 days" : "Ngữ cảnh bán hàng · 7 ngày gần nhất",
      english ? "Sales report service · net units sold" : "Service báo cáo bán hàng · số lượng bán ròng"
    );
    if (sales?.status !== "available") {
      empty(salesNode, english ? "Recent sales data could not be loaded." : "Chưa tải được dữ liệu bán hàng gần đây.");
    } else {
      const dates = document.createElement("small");
      dates.textContent = `${sales.start_date} – ${sales.end_date}`;
      salesNode.append(dates);
      if (!sales.items?.length) empty(salesNode, english ? "No net product sales in this period." : "Kỳ này chưa có sản phẩm bán ròng.");
      for (const item of (sales.items || []).slice(0, 5)) {
        if (typeof item.url !== "string" || !/^\/products\/\d+$/.test(item.url)) continue;
        const card = document.createElement("article"); card.className = "assistant-result-card";
        const body = document.createElement("div");
        const title = document.createElement("strong"); title.textContent = item.name || "";
        const meta = document.createElement("small");
        meta.textContent = `${item.code || ""} · ${item.quantity_sold} ${english ? "net units" : "sản phẩm bán ròng"}`;
        const revenue = document.createElement("b"); revenue.textContent = item.revenue_label || "";
        const link = document.createElement("a"); link.href = item.url;
        link.textContent = english ? "Open product →" : "Mở sản phẩm →";
        body.append(title, meta, revenue, link); card.append(body); salesNode.append(card);
      }
      const reportUrl = typeof sales.url === "string"
        && /^\/reports\/\?start=\d{4}-\d{2}-\d{2}&end=\d{4}-\d{2}-\d{2}$/.test(sales.url)
        ? sales.url : null;
      if (reportUrl) {
        const link = document.createElement("a"); link.href = reportUrl;
        link.className = "assistant-overview-action";
        link.textContent = english ? "Inspect this sales report →" : "Mở báo cáo kỳ này →";
        salesNode.append(link);
      }
    }

    parent.append(group);
    window.PetCare?.motion?.reveal(group.querySelectorAll(".assistant-result-card"));
  }

  function renderModuleInsight(insight, parent) {
    if (!insight || !Array.isArray(insight.items)) return;
    const group = document.createElement("div");
    group.className = "assistant-catalog assistant-insight";
    group.setAttribute("role", "group");
    const heading = document.createElement("strong");
    if (insight.kind === "inventory_restock") {
      group.setAttribute("aria-label", english ? "Inventory restock priorities" : "Ưu tiên bổ sung tồn kho");
      heading.textContent = english
        ? `Inventory priorities · ${insight.total} products · ${insight.target_days}-day target`
        : `Ưu tiên tồn kho · ${insight.total} sản phẩm · mục tiêu ${insight.target_days} ngày`;
      group.append(heading);
      if (!insight.items.length) {
        const empty = document.createElement("small");
        empty.textContent = english ? "No products meet the current warning rules." : "Không có sản phẩm đạt ngưỡng cảnh báo hiện tại.";
        group.append(empty);
      }
      for (const item of insight.items.slice(0, 8)) {
        if (typeof item.url !== "string" || !/^\/products\/\d+$/.test(item.url)) continue;
        const card = document.createElement("article"); card.className = "assistant-result-card";
        const art = document.createElement("span"); art.className = "assistant-result-art";
        art.append(window.PetCare.icon("products"));
        const body = document.createElement("div");
        const title = document.createElement("strong"); title.textContent = item.name || "";
        const meta = document.createElement("small");
        meta.textContent = `${item.code || ""} · ${english ? "stock" : "tồn"} ${item.stock_qty} · ${english ? "reorder level" : "ngưỡng nhập lại"} ${item.reorder_level}`;
        const suggestion = document.createElement("b");
        suggestion.textContent = english ? `Suggested add: ${item.suggested_qty}` : `Gợi ý nhập thêm: ${item.suggested_qty}`;
        const basis = document.createElement("small");
        basis.textContent = item.days_left == null
          ? (english ? "No recent paid sales · based on reorder level" : "Chưa có doanh số đã thanh toán gần đây · dựa trên ngưỡng nhập lại")
          : (english ? `About ${item.days_left} days of stock left` : `Còn khoảng ${item.days_left} ngày hàng`);
        const link = document.createElement("a"); link.href = item.url;
        link.textContent = english ? "Open product →" : "Mở sản phẩm →";
        body.append(title, meta, suggestion, basis, link); card.append(art, body); group.append(card);
      }
    } else if (insight.kind === "purchase_status") {
      group.setAttribute("aria-label", english ? "Purchase order status" : "Trạng thái đơn nhập");
      heading.textContent = english
        ? `Purchase orders · ${insight.total} matching`
        : `Đơn nhập · ${insight.total} đơn phù hợp`;
      group.append(heading);
      const statusLabels = english
        ? {ordered:"ordered", partially_received:"partially received", received:"received", cancelled:"cancelled"}
        : {ordered:"đang đặt", partially_received:"nhận một phần", received:"đã nhận", cancelled:"đã hủy"};
      const counts = document.createElement("small");
      counts.textContent = Object.entries(insight.status_counts || {})
        .map(([status, count]) => `${statusLabels[status] || status}: ${count}`).join(" · ");
      group.append(counts);
      if (!insight.items.length) {
        const empty = document.createElement("small");
        empty.textContent = english ? "No matching purchase orders." : "Không tìm thấy đơn nhập phù hợp.";
        group.append(empty);
      }
      for (const item of insight.items.slice(0, 8)) {
        if (typeof item.url !== "string" || !/^\/purchasing\/\d+$/.test(item.url)) continue;
        const card = document.createElement("article"); card.className = "assistant-result-card";
        const art = document.createElement("span"); art.className = "assistant-result-art";
        art.append(window.PetCare.icon("products"));
        const body = document.createElement("div");
        const title = document.createElement("strong");
        title.textContent = `${english ? "PO" : "Đơn"} #${item.purchase_order_id} · ${item.supplier_name || ""}`;
        const meta = document.createElement("small");
        meta.textContent = `${statusLabels[item.status] || item.status} · ${item.received_units}/${item.ordered_units} ${english ? "units received" : "sản phẩm đã nhận"} · ${item.created_at_label || item.created_at || ""}`;
        const amount = document.createElement("b"); amount.textContent = item.amount_label || "";
        const link = document.createElement("a"); link.href = item.url;
        link.textContent = english ? "Open purchase order →" : "Mở đơn nhập →";
        body.append(title, meta, amount, link); card.append(art, body); group.append(card);
      }
    } else return;
    parent.append(group);
    window.PetCare?.motion?.reveal(group.querySelectorAll(".assistant-result-card"));
  }

  launcher.addEventListener("click", () => setOpen(panel.hidden));
  pageOpeners.forEach(button => button.addEventListener("click", () => setOpen(true)));
  messages.addEventListener("click", event => {
    const target = event.target instanceof Element ? event.target : null;
    const retry = target?.closest("[data-assistant-retry]");
    if (retry && messages.contains(retry)) {
      input.value = retry.dataset.message || "";
      form.requestSubmit();
      return;
    }
    const button = target
      ? target.closest("[data-assistant-prompt]")
      : null;
    if (!button || !messages.contains(button)) return;
    input.value = button.dataset.assistantPrompt || "";
    form.requestSubmit();
  });
  close?.addEventListener("click", () => setOpen(false));
  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && !panel.hidden && !document.querySelector("dialog[open]")) {
      event.preventDefault(); setOpen(false);
    }
  });
  function setBusy(busy) {
    form.setAttribute("aria-busy", String(busy));
    const submit = form.querySelector("button[type='submit']");
    if (submit) submit.disabled = busy;
  }
  clear?.addEventListener("click", () => {
    activeRequest?.abort();
    activeRequest = null;
    history.length = 0;
    messages.replaceChildren(...welcomeNodes.map(node => node.cloneNode(true)));
    input.value = "";
    const submit = form.querySelector("button[type='submit']");
    if (submit) submit.disabled = false;
    setBusy(false);
    input.focus();
  });
  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (activeRequest) return;
    const message = input.value.trim();
    if (!message) return;
    messages.querySelector("[data-assistant-suggestions]")?.remove();
    appendMessage(message, "user");
    input.value = "";
    const pending = appendMessage(english ? "Checking store data…" : "Đang xem dữ liệu cửa hàng…", "assistant");
    const submit = form.querySelector("button[type='submit']");
    if (submit) submit.disabled = true;
    const controller = new AbortController();
    activeRequest = controller;
    setBusy(true);
    try {
      const response = await fetch(form.action, {
        method: "POST",
        credentials: "same-origin",
        headers: {"Content-Type":"application/json", "X-CSRFToken":csrf, "Accept":"application/json"},
        body: JSON.stringify({message, history:history.slice(-8)}),
        signal: controller.signal
      });
      let payload;
      try {
        payload = await response.json();
      } catch (_parseError) {
        throw new Error(english
          ? "The assistant could not reach store data. Check the MySQL connection and try again."
          : "Trợ lý chưa truy cập được dữ liệu cửa hàng. Hãy kiểm tra kết nối MySQL rồi thử lại.");
      }
      if (!response.ok) throw new Error(english
        ? "The request could not be completed. Please try again."
        : payload.error || "Chưa gửi được câu hỏi.");
      if (activeRequest !== controller || controller.signal.aborted) return;
      pending.textContent = payload.reply;
      renderCards(payload.catalog, pending);
      renderInsight(payload.insight, pending);
      renderOperationsOverview(payload.insight, pending);
      renderModuleInsight(payload.insight, pending);
      if (payload.mode) {
        const source = document.createElement("span");
        source.className = "assistant-message-source";
        source.textContent = payload.status === "unavailable"
          ? (english ? "Store data is temporarily unavailable" : "Tạm thời không đọc được dữ liệu cửa hàng")
          : payload.status === "clarification"
          ? (english ? "Clarification · no store data queried" : "Cần làm rõ · chưa truy vấn dữ liệu cửa hàng")
          : payload.status === "forbidden"
          ? (english ? "Restricted · administrator permission required" : "Bị giới hạn · cần quyền quản trị viên")
          : payload.insight?.kind === "top_products"
          ? (english ? "Sales report · current tenant MySQL data" : "Báo cáo bán hàng · dữ liệu MySQL của cửa hàng hiện tại")
          : payload.insight?.kind === "inventory_restock"
          ? (english ? "Read-only inventory service · current tenant MySQL data" : "Service tồn kho chỉ đọc · dữ liệu MySQL của cửa hàng hiện tại")
          : payload.insight?.kind === "purchase_status"
          ? (english ? "Admin-only purchasing service · current tenant MySQL data" : "Service nhập hàng dành cho quản trị viên · dữ liệu MySQL của cửa hàng hiện tại")
          : payload.insight?.kind === "operations_overview"
          ? (payload.status === "partial"
            ? (english ? "Read-only overview · some data sources unavailable" : "Tổng quan chỉ đọc · một số nguồn dữ liệu chưa tải được")
            : (english ? "Read-only overview · current tenant business services" : "Tổng quan chỉ đọc · service nghiệp vụ của tenant hiện tại"))
          : payload.mode === "ai"
          ? (english ? "Generative AI · scoped store context" : "AI tạo sinh · tham chiếu dữ liệu cửa hàng liên quan")
          : (english ? "Local lookup · current MySQL data" : "Tra cứu cục bộ · dữ liệu MySQL hiện tại");
        pending.append(source);
      }
      history.push({role:"user", content:message});
      history.push({role:"assistant", content:payload.reply});
      history.splice(0, Math.max(0, history.length - 8));
    } catch (error) {
      if (!controller.signal.aborted) {
        pending.textContent = english
          ? (error.message || "The assistant could not connect. Please try again.")
          : (error.message || "Không kết nối được trợ lý. Vui lòng thử lại.");
        const retry = document.createElement("button");
        retry.type = "button";
        retry.className = "assistant-retry";
        retry.dataset.assistantRetry = "";
        retry.dataset.message = message;
        retry.textContent = english ? "Retry" : "Thử lại";
        pending.append(retry);
      }
    } finally {
      if (activeRequest === controller) {
        activeRequest = null;
        setBusy(false);
        messages.scrollTop = messages.scrollHeight;
        if (!panel.hidden) input.focus();
      }
    }
  });
})();
