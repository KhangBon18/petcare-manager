(() => {
  const input = document.querySelector("[data-suggest-url]");
  if (!input) return;
  const form = input.closest("form"), panel = form.querySelector("[data-attribute-panel]");
  const status = panel.querySelector("[data-attribute-status]"), values = panel.querySelector("[data-attribute-values]");
  const apply = panel.querySelector("[data-attribute-apply]"), english = document.documentElement.lang === "en";
  const labels = english ? {species:"Species", coat_color:"Coat", eye_color:"Eyes", appearance_tags:"Traits"} : {species:"Loài", coat_color:"Màu lông", eye_color:"Màu mắt", appearance_tags:"Ngoại hình"};
  let controller = null, suggestions = {};
  input.addEventListener("change", async () => {
    controller?.abort(); const active = new AbortController(); controller = active;
    suggestions = {}; values.replaceChildren(); apply.hidden = true;
    const file = input.files?.[0]; if (!file || file.size > 5 * 1024 * 1024) {panel.hidden = true; return;}
    panel.hidden = false; panel.setAttribute("aria-busy", "true");
    status.textContent = english ? "Analyzing appearance…" : "Đang đọc đặc điểm ảnh…";
    const body = new FormData(); body.append("photo", file);
    try {
      const response = await fetch(input.dataset.suggestUrl, {method:"POST", credentials:"same-origin", signal:active.signal,
        headers:{"X-CSRFToken":form.querySelector('[name="csrf_token"]').value}, body});
      const payload = await response.json().catch(() => {throw new Error(english ? "Analysis unavailable. Enter attributes manually or try again." : "Chưa phân tích được. Nhập thuộc tính thủ công hoặc thử lại.");});
      if (active !== controller || active.signal.aborted) return;
      if (!response.ok) throw new Error(payload.error);
      suggestions = payload.suggestions || {};
      for (const [key, value] of Object.entries(suggestions)) {
        if (!labels[key]) continue;
        const tag = document.createElement("span"); tag.textContent = `${labels[key]}: ${value}`; values.append(tag);
      }
      status.textContent = payload.mode === "vision" ? (english ? "AI suggestions · review before applying." : "Gợi ý AI · kiểm tra trước khi áp dụng.")
        : (english ? "Local color estimate · may include background. Species and eyes are not inferred." : "Ước lượng màu cục bộ · có thể gồm nền ảnh; không đoán loài hoặc màu mắt.");
      if (payload.warning) status.textContent += " " + payload.warning;
      apply.hidden = Object.keys(suggestions).length === 0;
    } catch(error) { if (!active.signal.aborted && controller === active) status.textContent = (error.name === "TypeError" ? "" : error.message) || (english ? "Could not analyze. Enter attributes manually." : "Chưa phân tích được. Bạn vẫn có thể nhập thuộc tính thủ công."); }
    finally {if (controller === active) panel.setAttribute("aria-busy", "false");}
  });
  apply.addEventListener("click", () => {
    for (const [key, value] of Object.entries(suggestions)) {
      const field = form.elements.namedItem(key);
      if (labels[key] && field && !field.value.trim()) {field.value = value; field.dispatchEvent(new Event("input", {bubbles:true}));}
    }
    window.PetCare?.toast(english ? "Filled empty fields. Review before saving." : "Đã điền các trường trống. Kiểm tra lại trước khi lưu.");
  });
  window.addEventListener("pagehide", () => controller?.abort());
})();
