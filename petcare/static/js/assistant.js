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
  const csrf = form.querySelector('[name="csrf_token"]')?.value || "";

  function setOpen(open) {
    panel.hidden = !open;
    launcher.setAttribute("aria-expanded", String(open));
    pageOpeners.forEach(button => button.setAttribute("aria-expanded", String(open)));
    if (open) input.focus();
  }

  function appendMessage(text, role) {
    const bubble = document.createElement("div");
    bubble.className = `assistant-message ${role === "user" ? "assistant-message-user" : "assistant-message-bot"}`;
    bubble.textContent = text;
    messages.append(bubble);
    messages.scrollTop = messages.scrollHeight;
    return bubble;
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
  clear?.addEventListener("click", () => {
    activeRequest?.abort();
    activeRequest = null;
    history.length = 0;
    messages.replaceChildren(...welcomeNodes.map(node => node.cloneNode(true)));
    input.value = "";
    const submit = form.querySelector("button[type='submit']");
    if (submit) submit.disabled = false;
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
      pending.textContent = payload.reply;
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
        if (submit) submit.disabled = false;
        messages.scrollTop = messages.scrollHeight;
        input.focus();
      }
    }
  });
})();
