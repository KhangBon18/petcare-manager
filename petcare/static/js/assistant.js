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
    const group = document.createElement("div"); group.className = "assistant-catalog";
    const heading = document.createElement("strong");
    heading.textContent = english ? `${catalog.total} database matches · showing ${catalog.items.length}` : `${catalog.total} kết quả từ MySQL · hiển thị ${catalog.items.length}`;
    group.append(heading);
    for (const item of catalog.items) {
      if (typeof item.url !== "string" || !/^\/(pets|products)\/\d+$/.test(item.url)) continue;
      const card = document.createElement("article"); card.className = "assistant-result-card";
      if (item.photo_url && /^\/(pets|products)\/photo\//.test(item.photo_url)) {
        const image = document.createElement("img"); image.src = item.photo_url; image.alt = item.name;
        image.loading = "lazy"; card.append(image);
      } else { const art = document.createElement("span"); art.className = "assistant-result-art"; art.textContent = item.kind === "pet" ? "🐾" : "▦"; card.append(art); }
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

  launcher.addEventListener("click", () => setOpen(panel.hidden));
  pageOpeners.forEach(button => button.addEventListener("click", () => setOpen(true)));
  messages.addEventListener("click", event => {
    const button = event.target instanceof Element
      ? event.target.closest("[data-assistant-prompt]")
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
      if (payload.mode) {
        const source = document.createElement("span");
        source.className = "assistant-message-source";
        source.textContent = payload.mode === "ai"
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
