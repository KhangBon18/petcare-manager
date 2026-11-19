(() => {
  const input = document.querySelector("[data-suggest-url]");
  if (!input) return;
  const form = input.closest("form"), panel = form.querySelector("[data-attribute-panel]");
  const status = panel.querySelector("[data-attribute-status]");
  const values = panel.querySelector("[data-attribute-values]");
  const apply = panel.querySelector("[data-attribute-apply]");
  const retry = panel.querySelector("[data-attribute-retry]");
  const cancel = panel.querySelector("[data-attribute-cancel]");
  const dismiss = panel.querySelector("[data-attribute-dismiss]");
  const english = document.documentElement.lang === "en";
  const labels = english
    ? {species:"Species", breed:"Breed", coat_color:"Coat", eye_color:"Eyes", appearance_tags:"Traits"}
    : {species:"Loài", breed:"Giống", coat_color:"Màu lông", eye_color:"Mắt", appearance_tags:"Ngoại hình"};
  const messages = english
    ? {
        loading:"Analyzing appearance…", canceled:"Stopped waiting for this result. You can retry or enter attributes manually.",
        local:"Local color estimate · it may include the background. Species and eyes are not inferred.",
        providerUnavailable:"Vision provider unavailable · showing only the local color estimate, which may include the background.",
        observations:"Appearance suggestions · review them before applying.",
        partial:"Some unsupported fields were ignored. Review the remaining suggestions.",
        unrecognized:"No usable appearance suggestions were found. Enter attributes manually or try another image.",
        failed:"Analysis unavailable. Retry or enter attributes manually.",
        invalid:"This file is not a supported, readable image. Choose a JPEG, PNG or WebP image."
      }
    : {
        loading:"Đang đọc đặc điểm ảnh…", canceled:"Đã dừng chờ kết quả. Bạn có thể thử lại hoặc nhập thuộc tính thủ công.",
        local:"Ước lượng màu cục bộ · có thể gồm nền ảnh; không đoán loài hoặc màu mắt.",
        providerUnavailable:"Không kết nối được Vision · chỉ hiển thị ước lượng màu cục bộ, có thể gồm nền ảnh.",
        observations:"Gợi ý ngoại hình · hãy kiểm tra trước khi áp dụng.",
        partial:"Một số trường không hợp lệ đã được bỏ qua. Hãy kiểm tra các gợi ý còn lại.",
        unrecognized:"Chưa tìm thấy thuộc tính ngoại hình phù hợp. Hãy nhập thủ công hoặc thử ảnh khác.",
        failed:"Chưa phân tích được ảnh. Hãy thử lại hoặc nhập thuộc tính thủ công.",
        invalid:"Tệp không phải ảnh được hỗ trợ hoặc không đọc được. Hãy chọn ảnh JPEG, PNG hoặc WebP."
      };
  let controller = null, suggestions = {};

  function setBusy(busy) {
    panel.setAttribute("aria-busy", String(busy));
    cancel.hidden = !busy;
  }

  function clearResults() {
    suggestions = {};
    values.replaceChildren();
    apply.hidden = true;
    dismiss.hidden = true;
  }

  function requestError(payload) {
    const message = typeof payload?.error === "string" ? payload.error : "";
    return message || messages.failed;
  }

  function resultMessage(payload) {
    if (payload.status === "observations" || payload.mode === "vision") {
      return payload.provider_status === "partial" ? messages.partial : messages.observations;
    }
    if (payload.provider_status === "unavailable" || payload.status === "provider_unavailable") {
      return messages.providerUnavailable;
    }
    if (payload.status === "uncertain" || payload.mode === "local") return messages.local;
    if (payload.status === "unrecognized") return messages.unrecognized;
    return messages.failed;
  }

  async function analyze(file) {
    controller?.abort();
    const active = new AbortController();
    controller = active;
    clearResults();
    panel.hidden = false;
    retry.hidden = true;
    setBusy(true);
    status.textContent = messages.loading;

    const body = new FormData();
    body.append("photo", file);
    try {
      const response = await fetch(input.dataset.suggestUrl, {
        method:"POST", credentials:"same-origin", signal:active.signal,
        headers:{"X-CSRFToken":form.querySelector('[name="csrf_token"]').value}, body
      });
      const payload = await response.json().catch(() => null);
      if (active !== controller || active.signal.aborted) return;
      if (!response.ok) {
        if (payload?.status === "invalid_input") status.textContent = requestError(payload) || messages.invalid;
        else status.textContent = requestError(payload);
        retry.hidden = payload?.status === "invalid_input";
        return;
      }

      const raw = payload?.suggestions;
      if (raw && typeof raw === "object" && !Array.isArray(raw)) {
        for (const [key, value] of Object.entries(raw)) {
          if (!Object.prototype.hasOwnProperty.call(labels, key) || typeof value !== "string") continue;
          const cleaned = value.trim();
          if (!cleaned) continue;
          suggestions[key] = cleaned;
          const tag = document.createElement("span");
          tag.textContent = `${labels[key]}: ${cleaned}`;
          values.append(tag);
        }
      }
      status.textContent = resultMessage(payload || {});
      apply.hidden = Object.keys(suggestions).length === 0;
      dismiss.hidden = Object.keys(suggestions).length === 0;
      retry.hidden = payload?.status === "observations" && payload?.provider_status === "used";
    } catch (error) {
      if (active === controller && !active.signal.aborted) {
        status.textContent = error.name === "AbortError" ? messages.canceled : messages.failed;
        retry.hidden = false;
      }
    } finally {
      if (controller === active) setBusy(false);
    }
  }

  input.addEventListener("change", () => {
    controller?.abort();
    controller = null;
    clearResults();
    const file = input.files?.[0];
    if (!file) {
      panel.hidden = true;
      panel.setAttribute("aria-busy", "false");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      panel.hidden = false;
      setBusy(false);
      status.textContent = input.dataset.tooLargeMessage || messages.invalid;
      return;
    }
    void analyze(file);
  });

  retry.addEventListener("click", () => {
    const file = input.files?.[0];
    if (file) void analyze(file);
  });

  cancel.addEventListener("click", () => {
    if (!controller) return;
    const active = controller;
    controller = null;
    active.abort();
    setBusy(false);
    retry.hidden = false;
    status.textContent = messages.canceled;
  });

  dismiss.addEventListener("click", () => {
    controller?.abort();
    controller = null;
    clearResults();
    setBusy(false);
    retry.hidden = true;
    status.textContent = english
      ? "Suggestions dismissed. No form fields were changed."
      : "Đã bỏ qua gợi ý. Không có trường nào bị thay đổi.";
    input.focus();
  });

  apply.addEventListener("click", () => {
    for (const [key, value] of Object.entries(suggestions)) {
      if (!Object.prototype.hasOwnProperty.call(labels, key)) continue;
      const field = form.elements.namedItem(key);
      if (field && !field.value.trim()) {
        field.value = value;
        field.dispatchEvent(new Event("input", {bubbles:true}));
      }
    }
    status.textContent = english
      ? "Filled empty fields. Review them before saving."
      : "Đã điền các trường trống. Hãy kiểm tra trước khi lưu.";
    window.PetCare?.toast(english ? "Filled empty fields. Review before saving." : "Đã điền các trường trống. Kiểm tra lại trước khi lưu.");
  });

  window.addEventListener("pagehide", () => controller?.abort());
})();
