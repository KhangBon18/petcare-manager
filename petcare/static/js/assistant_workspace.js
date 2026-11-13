(() => {
  const root = document.getElementById("ai-workspace");
  if (!root) return;

  const english = document.documentElement.lang === "en";
  const stream = document.getElementById("ai-workspace-messages");
  const welcomePanel = document.getElementById("ai-welcome-panel");
  const form = document.getElementById("ai-workspace-form");
  const input = document.getElementById("ai-workspace-input");
  const sendBtn = document.getElementById("ai-workspace-send");
  const charCount = document.getElementById("ai-char-count");
  const resetBtn = document.getElementById("ai-workspace-reset");
  const clearSlotsBtn = document.getElementById("ai-clear-slots");
  const contextChipsWrap = document.getElementById("ai-context-chips");
  const scopeBannerCopy = document.getElementById("ai-scope-banner-copy");
  const compareTray = document.getElementById("ai-compare-tray");
  const compareCount = document.getElementById("ai-compare-count");
  const compareSubmitBtn = document.getElementById("ai-compare-submit");
  const compareClearBtn = document.getElementById("ai-compare-clear");
  const scopeButtons = Array.from(root.querySelectorAll("[data-scope-value]"));

  if (!stream || !form || !input) return;

  const chatUrl = root.dataset.chatUrl || form.action || "/assistant/chat";
  const resetUrl = root.dataset.resetUrl || "/assistant/reset";
  const csrf = root.dataset.csrfToken || form.querySelector('[name="csrf_token"]')?.value || "";
  const REQUEST_TIMEOUT_MS = 20000;

  let currentScope = root.dataset.initialScope === "shopper_preview" ? "shopper_preview" : "workspace";
  let conversationId = root.dataset.conversationId || `conv_${Date.now()}`;
  let activeController = null;
  let activeReset = null;
  const history = [];
  const selectedCompareCodes = new Set();
  const welcomeSnapshot = welcomePanel ? welcomePanel.cloneNode(true) : null;

  function appendFormattedText(container, text) {
    const raw = String(text || "");
    const parts = raw.split(/(\*\*[^*]+\*\*)/g);
    for (const part of parts) {
      if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
        const strong = document.createElement("strong");
        strong.textContent = part.slice(2, -2);
        container.append(strong);
      } else if (part) {
        container.append(document.createTextNode(part));
      }
    }
  }

  function renderReplyBody(parent, replyText) {
    const body = document.createElement("div");
    body.className = "ai-reply-text";
    const lines = String(replyText || "").split("\n").filter(line => line.trim().length > 0);
    for (const line of lines) {
      const p = document.createElement("p");
      appendFormattedText(p, line);
      body.append(p);
    }
    parent.append(body);
  }

  function updateCharCounter() {
    if (charCount) {
      charCount.textContent = `${input.value.length} / 1000`;
    }
  }

  function updateCompareTray() {
    if (!compareTray || !compareCount) return;
    const count = selectedCompareCodes.size;
    compareCount.textContent = english ? `${count} selected` : `Đã chọn ${count}`;
    compareTray.hidden = count < 2;
    if (compareSubmitBtn) {
      compareSubmitBtn.disabled = count < 2 || count > 4;
    }
  }

  function updateContextChips(contextState) {
    if (!contextChipsWrap) return;
    contextChipsWrap.replaceChildren();
    const chips = Array.isArray(contextState?.chips) ? contextState.chips : [];
    if (!chips.length) {
      const empty = document.createElement("span");
      empty.className = "ai-context-empty";
      empty.textContent = english
        ? "No preference filters pinned in this session yet."
        : "Chưa có bộ lọc ưu tiên nào được ghim trong phiên này.";
      contextChipsWrap.append(empty);
      if (clearSlotsBtn) clearSlotsBtn.hidden = true;
      return;
    }
    for (const chip of chips) {
      const badge = document.createElement("span");
      badge.className = "ai-slot-chip";
      badge.dataset.slot = chip.slot || "";
      badge.textContent = chip.label || "";
      contextChipsWrap.append(badge);
    }
    if (clearSlotsBtn) clearSlotsBtn.hidden = false;
  }

  function syncScopeUI(scope) {
    currentScope = scope === "shopper_preview" ? "shopper_preview" : "workspace";
    for (const btn of scopeButtons) {
      const active = btn.dataset.scopeValue === currentScope;
      btn.classList.toggle("is-active", active);
      btn.setAttribute("aria-pressed", String(active));
    }
    const wsOnlyNodes = stream.querySelectorAll('[data-workspace-only="true"]');
    wsOnlyNodes.forEach(node => {
      node.hidden = currentScope === "shopper_preview";
    });
    const banner = stream.querySelector("#ai-scope-banner-copy") || scopeBannerCopy;
    if (banner) {
      banner.textContent = currentScope === "shopper_preview"
        ? (english
          ? "Shopper Preview (QA) active: strictly scoped to available pets, active products, and reviewed pet-care knowledge. Internal store KPIs and purchase orders are blocked."
          : "Đang ở chế độ Xem thử khách mua (QA): chỉ truy cập thú cưng đang bán, sản phẩm còn hoạt động và kho tri thức chăm sóc. Doanh thu, tồn kho nội bộ và đơn nhập hàng được khóa.")
        : (english
          ? "Combines explainable pet matching, normalized unit-price product recommendations & comparisons, cited pet-care articles, and role-scoped store insights."
          : "Kết hợp tư vấn chọn thú cưng có giải thích điểm, gợi ý & so sánh sản phẩm theo đơn giá quy đổi, kiến thức chăm sóc có nguồn duyệt và tra cứu vận hành theo quyền hiện tại.");
    }
  }

  function setBusy(busy) {
    form.setAttribute("aria-busy", String(busy));
    if (sendBtn) sendBtn.disabled = busy;
  }

  function safeInternalUrl(url) {
    return typeof url === "string" && /^\/(pets|products|purchasing|reports)\b/.test(url) ? url : null;
  }

  function safePhotoUrl(url) {
    return typeof url === "string" && /^\/(pets|products)\/photo\//.test(url) ? url : null;
  }

  function safeExternalCitationUrl(url) {
    return typeof url === "string" && /^https:\/\/[a-z0-9.-]+\//i.test(url) ? url : null;
  }

  function renderSafetyNotice(notice, parent) {
    if (!notice || typeof notice !== "object") return;
    const box = document.createElement("section");
    const sev = ["emergency", "medical_boundary", "policy_boundary", "disclaimer"].includes(notice.severity)
      ? notice.severity
      : "disclaimer";
    box.className = `ai-safety-banner ai-safety-banner--${sev}`;
    box.setAttribute("role", sev === "emergency" ? "alert" : "note");

    const title = document.createElement("strong");
    title.textContent = notice.title || "";
    const msg = document.createElement("p");
    appendFormattedText(msg, notice.message || "");
    box.append(title, msg);

    if (Array.isArray(notice.escalation_steps) && notice.escalation_steps.length) {
      const ul = document.createElement("ul");
      for (const step of notice.escalation_steps) {
        const li = document.createElement("li");
        li.textContent = step;
        ul.append(li);
      }
      box.append(ul);
    }
    parent.append(box);
  }

  function renderReasoning(summaryText, parent) {
    if (!summaryText) return;
    const box = document.createElement("div");
    box.className = "ai-reasoning-box";
    const label = document.createElement("strong");
    label.textContent = english ? "Why & how ranked: " : "Cơ sở lọc & chấm điểm: ";
    const copy = document.createElement("span");
    copy.textContent = summaryText;
    box.append(label, copy);
    parent.append(box);
  }

  function renderRecommendationCards(cards, parent) {
    if (!Array.isArray(cards) || !cards.length) return;
    const grid = document.createElement("div");
    grid.className = "ai-rec-grid";
    grid.setAttribute("role", "group");
    grid.setAttribute("aria-label", english ? "Recommendations" : "Danh sách gợi ý");

    for (const item of cards) {
      const card = document.createElement("article");
      card.className = `ai-rec-card${item.is_alternative ? " ai-rec-card--alt" : ""}`;

      const top = document.createElement("div");
      top.className = "ai-rec-top";

      const photoUrl = safePhotoUrl(item.photo_url);
      if (photoUrl) {
        const img = document.createElement("img");
        img.className = "ai-rec-photo";
        img.src = photoUrl;
        img.alt = item.name || "";
        img.width = 84;
        img.height = 84;
        img.loading = "lazy";
        top.append(img);
      } else {
        const placeholder = document.createElement("span");
        placeholder.className = "ai-rec-art";
        if (window.PetCare?.icon) {
          placeholder.append(window.PetCare.icon(item.kind === "pet" ? "pets" : "products"));
        } else {
          placeholder.textContent = item.kind === "pet" ? "🐾" : "📦";
        }
        top.append(placeholder);
      }

      const headMeta = document.createElement("div");
      headMeta.className = "ai-rec-head";

      const badgesRow = document.createElement("div");
      badgesRow.className = "ai-rec-badges";
      const codePill = document.createElement("span");
      codePill.className = "ai-code-pill";
      codePill.textContent = item.code || "";
      badgesRow.append(codePill);

      if (item.is_alternative) {
        const altPill = document.createElement("span");
        altPill.className = "ai-alt-pill";
        altPill.textContent = english ? "In-stock alternative" : "Gợi ý thay thế còn hàng";
        badgesRow.append(altPill);
      }

      const scorePill = document.createElement("span");
      scorePill.className = "ai-score-pill";
      scorePill.textContent = `${english ? "Fit" : "Điểm"} ${item.score ?? 0}/${item.max_score ?? 100}`;
      badgesRow.append(scorePill);

      const title = document.createElement("h3");
      title.textContent = item.name || "";
      const sub = document.createElement("small");
      sub.className = "ai-rec-sub";
      const stockBit = item.kind === "product" && item.stock_qty != null
        ? ` · ${english ? "Stock" : "Tồn kho"}: ${item.stock_qty}`
        : ` · ${item.status_label || ""}`;
      sub.textContent = `${item.subtitle || ""}${stockBit}`;

      const priceRow = document.createElement("div");
      priceRow.className = "ai-rec-pricing";
      const priceStrong = document.createElement("strong");
      priceStrong.textContent = item.price_label || `${item.price} ${item.currency_code || "VND"}`;
      priceRow.append(priceStrong);
      if (item.unit_price_display) {
        const unitBadge = document.createElement("span");
        unitBadge.className = "ai-unit-pill";
        unitBadge.textContent = item.unit_price_display;
        priceRow.append(unitBadge);
      }

      headMeta.append(badgesRow, title, sub, priceRow);
      top.append(headMeta);
      card.append(top);

      if (Array.isArray(item.reasons) && item.reasons.length) {
        const ul = document.createElement("ul");
        ul.className = "ai-rec-reasons";
        for (const r of item.reasons.slice(0, 3)) {
          const li = document.createElement("li");
          li.textContent = r;
          ul.append(li);
        }
        card.append(ul);
      }

      if (Array.isArray(item.warnings) && item.warnings.length) {
        const warnBox = document.createElement("div");
        warnBox.className = "ai-rec-warnings";
        for (const w of item.warnings.slice(0, 2)) {
          const p = document.createElement("p");
          p.textContent = `⚠ ${w}`;
          warnBox.append(p);
        }
        card.append(warnBox);
      }

      if (Array.isArray(item.score_breakdown) && item.score_breakdown.length) {
        const details = document.createElement("details");
        details.className = "ai-score-details";
        const sum = document.createElement("summary");
        sum.textContent = english ? "Inspect transparent score breakdown" : "Xem chi tiết chấm điểm & thuộc tính xác thực";
        details.append(sum);

        const list = document.createElement("dl");
        list.className = "ai-breakdown-dl";
        for (const comp of item.score_breakdown) {
          const dt = document.createElement("dt");
          dt.textContent = `${comp.label} (${comp.points}/${comp.max_points})`;
          const dd = document.createElement("dd");
          dd.textContent = comp.detail || "";
          list.append(dt, dd);
        }
        details.append(list);
        card.append(details);
      }

      const actions = document.createElement("div");
      actions.className = "ai-rec-actions";
      const profileUrl = safeInternalUrl(item.url);
      if (profileUrl) {
        const link = document.createElement("a");
        link.className = "ai-profile-link";
        link.href = profileUrl;
        link.textContent = item.kind === "pet"
          ? (english ? "Open pet profile →" : "Mở hồ sơ thú cưng →")
          : (english ? "Open product details →" : "Mở chi tiết sản phẩm →");
        actions.append(link);
      }

      if (item.kind === "product" && item.code) {
        const label = document.createElement("label");
        label.className = "ai-compare-check";
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.value = item.code;
        checkbox.checked = selectedCompareCodes.has(item.code);
        checkbox.dataset.compareCode = item.code;
        const span = document.createElement("span");
        span.textContent = english ? "Compare" : "Chọn so sánh";
        label.append(checkbox, span);
        actions.append(label);
      }

      card.append(actions);
      grid.append(card);
    }
    parent.append(grid);
  }

  function renderComparisonMatrix(comparison, parent) {
    if (!comparison || !Array.isArray(comparison.items) || comparison.items.length < 2) return;
    const wrap = document.createElement("div");
    wrap.className = "ai-comparison-wrap";
    wrap.setAttribute("role", "region");
    wrap.setAttribute("aria-label", english ? "Product comparison table" : "Bảng so sánh sản phẩm");

    // Desktop/Tablet accessible table
    const tableScroll = document.createElement("div");
    tableScroll.className = "ai-comparison-table-wrap";
    const table = document.createElement("table");
    table.className = "ai-comparison-table";

    const thead = document.createElement("thead");
    const headRow = document.createElement("tr");
    const corner = document.createElement("th");
    corner.scope = "col";
    corner.textContent = english ? "Criterion" : "Tiêu chí";
    headRow.append(corner);

    for (const item of comparison.items) {
      const th = document.createElement("th");
      th.scope = "col";
      const url = safeInternalUrl(item.url);
      if (url) {
        const link = document.createElement("a");
        link.href = url;
        link.textContent = item.name || item.code || "";
        th.append(link);
      } else {
        th.textContent = item.name || item.code || "";
      }
      headRow.append(th);
    }
    thead.append(headRow);
    table.append(thead);

    const tbody = document.createElement("tbody");
    for (const row of comparison.rows || []) {
      const tr = document.createElement("tr");
      const rHead = document.createElement("th");
      rHead.scope = "row";
      rHead.textContent = row.label || "";
      tr.append(rHead);
      for (const val of row.values || []) {
        const td = document.createElement("td");
        td.textContent = val || "—";
        tr.append(td);
      }
      tbody.append(tr);
    }
    table.append(tbody);
    tableScroll.append(table);
    wrap.append(tableScroll);

    // Mobile stacked cards (zero horizontal overflow at 320px!)
    const mobileStack = document.createElement("div");
    mobileStack.className = "ai-comparison-mobile";
    comparison.items.forEach((item, idx) => {
      const mCard = document.createElement("article");
      mCard.className = "ai-comparison-mobile-card";
      const mTitle = document.createElement("strong");
      mTitle.textContent = `${item.name} (${item.code})`;
      mCard.append(mTitle);
      const dl = document.createElement("dl");
      for (const row of comparison.rows || []) {
        if (row.key === "code") continue;
        const dt = document.createElement("dt");
        dt.textContent = row.label || "";
        const dd = document.createElement("dd");
        dd.textContent = (row.values && row.values[idx]) || "—";
        dl.append(dt, dd);
      }
      mCard.append(dl);
      const url = safeInternalUrl(item.url);
      if (url) {
        const a = document.createElement("a");
        a.className = "ai-profile-link";
        a.href = url;
        a.textContent = english ? "Open product →" : "Mở sản phẩm →";
        mCard.append(a);
      }
      mobileStack.append(mCard);
    });
    wrap.append(mobileStack);
    parent.append(wrap);
  }

  function renderLegacyCatalog(catalog, hasRichCards, parent) {
    if (hasRichCards || !catalog || !Array.isArray(catalog.items) || !catalog.items.length) return;
    const wrap = document.createElement("div");
    wrap.className = "ai-legacy-catalog";
    const head = document.createElement("strong");
    head.textContent = english
      ? `${catalog.total} catalog matches · showing ${catalog.items.length}`
      : `${catalog.total} kết quả danh mục · hiển thị ${catalog.items.length}`;
    wrap.append(head);

    const list = document.createElement("div");
    list.className = "ai-legacy-grid";
    for (const item of catalog.items) {
      const url = safeInternalUrl(item.url);
      if (!url) continue;
      const row = document.createElement("a");
      row.className = "ai-legacy-item";
      row.href = url;
      const name = document.createElement("strong");
      name.textContent = item.name || "";
      const meta = document.createElement("small");
      meta.textContent = `${item.code || ""} · ${item.price_label || ""}`;
      row.append(name, meta);
      list.append(row);
    }
    wrap.append(list);
    parent.append(wrap);
  }

  function renderOperationalInsight(insight, parent) {
    if (!insight || typeof insight !== "object") return;
    if (insight.kind === "combined_operational" && Array.isArray(insight.sections)) {
      for (const section of insight.sections) {
        renderOperationalInsight(section, parent);
      }
      return;
    }
    const box = document.createElement("div");
    box.className = "ai-ops-insight";

    if (insight.kind === "inventory_forecast" && Array.isArray(insight.items)) {
      const h = document.createElement("strong");
      h.textContent = english
        ? `8-Week Weighted Demand Forecast · ${insight.warning_count} warnings`
        : `Dự báo nhu cầu gia quyền 8 tuần · ${insight.warning_count} mặt hàng cảnh báo`;
      box.append(h);
      for (const item of insight.items) {
        const row = document.createElement("div");
        row.className = "ai-ops-row";
        const name = document.createElement("strong");
        name.textContent = `${item.name} (${item.code})`;
        const stats = document.createElement("small");
        const vel = item.daily_rate ? `${item.daily_rate}/d` : (english ? "no sales" : "chưa có doanh số");
        stats.textContent = english
          ? `Stock ${item.stock_qty} (+${item.incoming_qty} incoming) · Velocity ${vel} · Suggested +${item.suggested_qty}`
          : `Tồn ${item.stock_qty} (+${item.incoming_qty} đang về) · Tốc độ ${vel} · Gợi ý nhập +${item.suggested_qty}`;
        row.append(name, stats);
        const url = safeInternalUrl(item.url);
        if (url) {
          const link = document.createElement("a");
          link.href = url;
          link.textContent = english ? "Inspect SKU →" : "Xem sản phẩm →";
          row.append(link);
        }
        box.append(row);
      }
      parent.append(box);
      return;
    }

    if (Array.isArray(insight.items) && insight.items.length) {
      for (const item of insight.items.slice(0, 6)) {
        const row = document.createElement("div");
        row.className = "ai-ops-row";
        const title = document.createElement("strong");
        title.textContent = item.name || (item.purchase_order_id ? `PO #${item.purchase_order_id} · ${item.supplier_name || ""}` : "");
        const sub = document.createElement("small");
        if (insight.kind === "top_products") {
          sub.textContent = `${item.code || ""} · ${item.quantity_sold} ${english ? "net sold" : "bán ròng"} · ${item.revenue_label || ""}`;
        } else if (insight.kind === "inventory_restock") {
          sub.textContent = `${item.code || ""} · ${english ? "stock" : "tồn"} ${item.stock_qty} · +${item.suggested_qty}`;
        } else if (insight.kind === "purchase_status") {
          sub.textContent = `${item.status} · ${item.received_units}/${item.ordered_units} · ${item.amount_label || ""}`;
        }
        row.append(title, sub);
        const url = safeInternalUrl(item.url);
        if (url) {
          const a = document.createElement("a");
          a.href = url;
          a.textContent = english ? "Open →" : "Mở →";
          row.append(a);
        }
        box.append(row);
      }
      parent.append(box);
    }
  }

  function renderCitations(citations, parent) {
    if (!Array.isArray(citations) || !citations.length) return;
    const section = document.createElement("section");
    section.className = "ai-citations";
    section.setAttribute("aria-label", english ? "Reviewed knowledge sources" : "Nguồn tài liệu tham khảo đã kiểm duyệt");

    const title = document.createElement("strong");
    title.className = "ai-citations-heading";
    title.textContent = english ? "Reviewed Sources & Citations" : "Nguồn trích dẫn đã kiểm duyệt";
    section.append(title);

    const list = document.createElement("div");
    list.className = "ai-citation-list";
    for (const cite of citations) {
      const item = document.createElement("article");
      item.className = "ai-citation-card";
      const head = document.createElement("div");
      const badge = document.createElement("span");
      badge.className = "ai-code-pill";
      badge.textContent = `${cite.doc_id} · v${cite.version || "1.0"}`;
      const docTitle = document.createElement("strong");
      docTitle.textContent = cite.title || "";
      head.append(badge, docTitle);

      const meta = document.createElement("small");
      meta.textContent = `${cite.source_name || ""} · ${english ? "Updated" : "Cập nhật"} ${cite.updated_at || ""}`;
      item.append(head, meta);

      const extUrl = safeExternalCitationUrl(cite.source_url);
      if (extUrl) {
        const a = document.createElement("a");
        a.href = extUrl;
        a.target = "_blank";
        a.rel = "noopener noreferrer";
        a.textContent = english ? "Reference source ↗" : "Xem nguồn gốc ↗";
        item.append(a);
      }
      list.append(item);
    }
    section.append(list);
    parent.append(section);
  }

  function renderMissingData(notes, parent) {
    if (!Array.isArray(notes) || !notes.length) return;
    const note = document.createElement("p");
    note.className = "ai-missing-note";
    note.textContent = notes[0];
    parent.append(note);
  }

  function renderFollowUps(prompts, parent) {
    if (!Array.isArray(prompts) || !prompts.length) return;
    const wrap = document.createElement("div");
    wrap.className = "ai-followups";
    wrap.setAttribute("aria-label", english ? "Suggested follow-ups" : "Câu hỏi tiếp theo gợi ý");
    for (const text of prompts.slice(0, 4)) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "ai-followup-chip";
      btn.dataset.aiPrompt = text;
      btn.textContent = text;
      wrap.append(btn);
    }
    parent.append(wrap);
  }

  function renderProvenanceFooter(payload, parent) {
    const foot = document.createElement("footer");
    foot.className = "ai-turn-footer";
    const parts = [];
    parts.push(
      payload.engine_mode === "real_llm"
        ? (english ? "Approved LLM + MySQL Grounded" : "AI tạo sinh phê duyệt + MySQL xác thực")
        : (english ? "Offline Python Engine · MySQL Grounded" : "Offline Python Engine · Dữ liệu MySQL xác thực")
    );
    parts.push(
      payload.scope === "shopper_preview"
        ? (english ? "Scope: Shopper Preview (QA)" : "Phạm vi: Khách mua (QA)")
        : (english ? "Scope: Store Workspace" : "Phạm vi: Cửa hàng")
    );
    if (Array.isArray(payload.tool_trace) && payload.tool_trace.length) {
      const tools = payload.tool_trace.map(t => `${t.tool_name} (${t.duration_ms}ms)`).join(", ");
      parts.push(`${english ? "Tools" : "Công cụ"}: ${tools}`);
    }
    foot.textContent = parts.join(" · ");
    parent.append(foot);
  }

  function appendUserBubble(message) {
    stream.querySelector("#ai-welcome-panel")?.classList.add("ai-welcome-compact");
    const bubble = document.createElement("div");
    bubble.className = "ai-turn ai-turn-user";
    const p = document.createElement("p");
    p.textContent = message;
    bubble.append(p);
    stream.append(bubble);
    stream.scrollTop = stream.scrollHeight;
  }

  function appendPendingBotCard() {
    const card = document.createElement("div");
    card.className = "ai-turn ai-turn-bot is-loading";
    card.textContent = english
      ? "Analyzing preferences and querying verified store records…"
      : "Đang phân tích nhu cầu và đối chiếu dữ liệu xác thực…";
    stream.append(card);
    stream.scrollTop = stream.scrollHeight;
    return card;
  }

  async function submitPrompt(rawMessage) {
    if (activeController) return;
    const message = String(rawMessage || "").trim();
    if (!message) return;

    appendUserBubble(message);
    input.value = "";
    updateCharCounter();
    const botCard = appendPendingBotCard();

    if (activeReset) {
      await activeReset;
    }

    const controller = new AbortController();
    activeController = controller;
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, REQUEST_TIMEOUT_MS);
    setBusy(true);

    try {
      const response = await fetch(chatUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json",
          "X-CSRFToken": csrf,
        },
        body: JSON.stringify({
          message,
          scope: currentScope,
          conversation_id: conversationId,
          history: history.slice(-8),
        }),
        signal: controller.signal,
      });

      let payload;
      try {
        payload = await response.json();
      } catch (_err) {
        throw new Error(
          english
            ? "Could not parse the assistant response. Check your connection and try again."
            : "Không đọc được phản hồi từ trợ lý. Vui lòng kiểm tra kết nối và thử lại."
        );
      }

      if (!response.ok) {
        throw new Error(
          payload?.error || (english ? "Request could not be completed. Please try again." : "Chưa xử lý được yêu cầu. Vui lòng thử lại.")
        );
      }

      if (activeController !== controller) return;
      botCard.classList.remove("is-loading");
      botCard.replaceChildren();

      if (payload.conversation_id) {
        conversationId = payload.conversation_id;
      }
      if (payload.context_state) {
        updateContextChips(payload.context_state);
      }

      renderSafetyNotice(payload.safety_notice, botCard);
      renderReplyBody(botCard, payload.reply || "");
      renderReasoning(payload.reasoning_summary, botCard);
      const hasCards = Array.isArray(payload.cards) && payload.cards.length > 0;
      renderRecommendationCards(payload.cards, botCard);
      renderComparisonMatrix(payload.comparison, botCard);
      renderLegacyCatalog(payload.catalog, hasCards, botCard);
      renderOperationalInsight(payload.insight, botCard);
      renderCitations(payload.citations, botCard);
      renderMissingData(payload.missing_data, botCard);
      renderFollowUps(payload.follow_up_questions, botCard);
      renderProvenanceFooter(payload, botCard);

      history.push({ role: "user", content: message });
      history.push({ role: "assistant", content: String(payload.reply || "").slice(0, 800) });
      if (history.length > 8) {
        history.splice(0, history.length - 8);
      }
    } catch (error) {
      botCard.classList.remove("is-loading");
      botCard.classList.add("is-error");
      botCard.replaceChildren();
      const errP = document.createElement("p");
      if (timedOut) {
        errP.textContent = english
          ? "The request timed out before store services responded. You can safely retry."
          : "Yêu cầu quá thời gian chờ phản hồi. Dữ liệu không bị thay đổi — bạn có thể bấm Thử lại.";
      } else {
        errP.textContent = error?.message || (english ? "Connection interrupted. Please try again." : "Kết nối gián đoạn. Vui lòng thử lại.");
      }
      const retryBtn = document.createElement("button");
      retryBtn.type = "button";
      retryBtn.className = "button button-light button-small ai-retry-btn";
      retryBtn.dataset.aiRetry = message;
      retryBtn.textContent = english ? "Retry question" : "Thử lại câu hỏi";
      botCard.append(errP, retryBtn);
    } finally {
      clearTimeout(timer);
      if (activeController === controller) {
        activeController = null;
        setBusy(false);
        stream.scrollTop = stream.scrollHeight;
      }
    }
  }

  async function resetConversation({ keepWelcomeOnly = true } = {}) {
    if (activeController) {
      activeController.abort();
      activeController = null;
      setBusy(false);
    }
    const prevConv = conversationId;
    history.length = 0;
    selectedCompareCodes.clear();
    updateCompareTray();
    updateContextChips({ chips: [] });

    if (keepWelcomeOnly && welcomeSnapshot) {
      const freshWelcome = welcomeSnapshot.cloneNode(true);
      freshWelcome.classList.remove("ai-welcome-compact");
      stream.replaceChildren(freshWelcome);
      syncScopeUI(currentScope);
    }
    input.focus();

    const resetTask = (async () => {
      try {
        const res = await fetch(resetUrl, {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-CSRFToken": csrf,
          },
          body: JSON.stringify({
            scope: currentScope,
            conversation_id: prevConv,
          }),
        });
        if (res.ok) {
          const data = await res.json();
          if (data?.conversation_id) {
            conversationId = data.conversation_id;
          }
        }
      } catch (_ignore) {
        conversationId = `conv_${Date.now()}`;
      }
    })();
    activeReset = resetTask;
    try {
      await resetTask;
    } finally {
      if (activeReset === resetTask) {
        activeReset = null;
      }
    }
  }

  // Event listeners
  form.addEventListener("submit", event => {
    event.preventDefault();
    submitPrompt(input.value);
  });

  input.addEventListener("input", updateCharCounter);
  input.addEventListener("keydown", event => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      submitPrompt(input.value);
    }
  });

  stream.addEventListener("click", event => {
    const target = event.target instanceof Element ? event.target : null;
    if (!target) return;

    const promptBtn = target.closest("[data-ai-prompt]");
    if (promptBtn && stream.contains(promptBtn)) {
      submitPrompt(promptBtn.dataset.aiPrompt || "");
      return;
    }

    const retryBtn = target.closest("[data-ai-retry]");
    if (retryBtn && stream.contains(retryBtn)) {
      submitPrompt(retryBtn.dataset.aiRetry || "");
    }
  });

  stream.addEventListener("change", event => {
    const target = event.target;
    if (!(target instanceof HTMLInputElement) || !target.dataset.compareCode) return;
    const code = target.dataset.compareCode;
    if (target.checked) {
      if (selectedCompareCodes.size >= 4) {
        target.checked = false;
        return;
      }
      selectedCompareCodes.add(code);
    } else {
      selectedCompareCodes.delete(code);
    }
    updateCompareTray();
  });

  compareSubmitBtn?.addEventListener("click", () => {
    const codes = Array.from(selectedCompareCodes);
    if (codes.length < 2) return;
    const query = english
      ? `Compare ${codes.join(", ")}`
      : `So sánh ${codes.join(", ")}`;
    selectedCompareCodes.clear();
    stream.querySelectorAll("input[data-compare-code]").forEach(cb => {
      if (cb instanceof HTMLInputElement) cb.checked = false;
    });
    updateCompareTray();
    submitPrompt(query);
  });

  compareClearBtn?.addEventListener("click", () => {
    selectedCompareCodes.clear();
    stream.querySelectorAll("input[data-compare-code]").forEach(cb => {
      if (cb instanceof HTMLInputElement) cb.checked = false;
    });
    updateCompareTray();
  });

  resetBtn?.addEventListener("click", () => {
    resetConversation({ keepWelcomeOnly: true });
  });

  clearSlotsBtn?.addEventListener("click", () => {
    submitPrompt(english ? "Reset preferences" : "Xóa ngữ cảnh");
  });

  for (const btn of scopeButtons) {
    btn.addEventListener("click", () => {
      const nextScope = btn.dataset.scopeValue === "shopper_preview" ? "shopper_preview" : "workspace";
      if (nextScope === currentScope) return;
      syncScopeUI(nextScope);
      resetConversation({ keepWelcomeOnly: true });
    });
  }

  syncScopeUI(currentScope);
  updateCharCounter();

  const autoPrompt = (root.dataset.initialPrompt || "").trim();
  if (autoPrompt) {
    submitPrompt(autoPrompt);
  }
})();
