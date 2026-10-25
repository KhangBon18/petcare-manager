(() => {
  const english = document.documentElement?.lang === "en";
  const region = document.getElementById("toast-region");
  function decorateToast(node, category) {
    node.classList.add("toast");
    node.setAttribute("role", category === "error" ? "alert" : "status");
    const close = document.createElement("button");
    close.type = "button"; close.className = "toast-close";
    close.setAttribute("aria-label", english ? "Dismiss notification" : "Đóng thông báo");
    close.textContent = "×"; close.addEventListener("click", () => node.remove());
    node.append(close);
    region.append(node);
    if (category === "success") window.setTimeout(() => node.remove(), 6000);
  }
  window.PetCare = {...window.PetCare, toast(message, category = "success") {
    if (!region) return;
    const node = document.createElement("div");
    node.className = `flash flash-${category}`;
    node.textContent = message; decorateToast(node, category);
  }};
  if (region) document.querySelectorAll(".flash-stack .flash").forEach(node => {
    const category = ["error", "warning", "success", "info"].find(name => node.classList.contains(`flash-${name}`));
    decorateToast(node, category);
  });
  function imageFallback(image) {
    if (image.tagName !== "IMG" || !image.closest(".pos-card-image, .cart-item-image")) return;
    image.hidden = true;
    const placeholder = document.createElement("span");
    placeholder.textContent = "🐾";
    placeholder.setAttribute("aria-hidden", "true");
    if (!image.parentElement.querySelector("[data-image-fallback]")) {
      placeholder.dataset.imageFallback = ""; image.parentElement.append(placeholder);
    }
  }
  document.addEventListener("error", event => imageFallback(event.target), true);
  document.querySelectorAll("img").forEach(image => {
    if (image.complete && image.naturalWidth === 0) imageFallback(image);
  });
  const summary = document.querySelector("[data-error-summary]");
  if (summary) {
    const form = summary.closest("form");
    (form?.querySelector('[aria-invalid="true"]') || summary).focus();
  }

  function clearFieldError(event) {
    const field = event.target;
    if (!field.dataset?.serverError) return;
    delete field.dataset.serverError;
    field.removeAttribute("aria-invalid");
    field.classList.remove("field-invalid");
    const error = document.getElementById(`${field.id}-error`);
    if (error) error.hidden = true;
  }
  document.addEventListener("input", clearFieldError, true);
  document.addEventListener("change", clearFieldError, true);
  document.addEventListener("keydown", event => {
    if (event.key !== "Escape") return;
    document.querySelectorAll("[data-mobile-menu][open]").forEach(menu => {
      menu.open = false; menu.querySelector("summary").focus();
    });
  });

  document.addEventListener("click", event => {
    if (event.target.closest("[data-reload-page]")) window.location.reload();
  });

  document.addEventListener("submit", event => {
    if (event.defaultPrevented) return;
    const message = event.target.dataset.confirm;
    if (message && !window.confirm(message)) { event.preventDefault(); return; }
    const form = event.target;
    if (!form.hasAttribute("data-submit-lock")) return;
    if (form.dataset.submitting) { event.preventDefault(); return; }
    form.dataset.submitting = "true"; form.setAttribute("aria-busy", "true");
    const button = event.submitter || form.querySelector('[type="submit"]');
    if (button) {
      button.dataset.idleLabel = button.textContent;
      button.textContent = form.dataset.submitLabel || (english ? "Processing…" : "Đang xử lý…");
      button.disabled = true;
    }
  });
  window.addEventListener("pageshow", () => {
    document.querySelectorAll('[data-submitting="true"]').forEach(form => {
      delete form.dataset.submitting; form.setAttribute("aria-busy", "false");
      form.querySelectorAll("[data-idle-label]").forEach(button => {
        button.textContent = button.dataset.idleLabel; button.disabled = false;
      });
    });
  });
})();
