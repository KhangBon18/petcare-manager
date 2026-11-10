(() => {
  const english = document.documentElement?.lang === "en";
  const region = document.getElementById("toast-region");
  const svgNamespace = "http://www.w3.org/2000/svg";
  const iconShapes = {
    pets: [
      ["ellipse", {cx: "12", cy: "15.5", rx: "5.2", ry: "4.1"}],
      ["ellipse", {cx: "5.7", cy: "10.4", rx: "1.6", ry: "2"}],
      ["ellipse", {cx: "10", cy: "6.8", rx: "1.6", ry: "2"}],
      ["ellipse", {cx: "14.3", cy: "6.8", rx: "1.6", ry: "2"}],
      ["ellipse", {cx: "18.4", cy: "10.4", rx: "1.6", ry: "2"}],
    ],
    products: [
      ["path", {d: "m12 3 8.5 4.5v9L12 21l-8.5-4.5v-9L12 3Z"}],
      ["path", {d: "m3.8 7.7 8.2 4.5 8.2-4.5M12 12.2V21"}],
    ],
  };
  function createIcon(name, className = "ui-icon") {
    const shapes = iconShapes[name];
    if (!shapes) return null;
    const svg = document.createElementNS(svgNamespace, "svg");
    for (const [key, value] of Object.entries({
      class: className, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor",
      "stroke-width": "1.8", "stroke-linecap": "round", "stroke-linejoin": "round",
      "aria-hidden": "true", focusable: "false",
    })) svg.setAttribute(key, value);
    for (const [tag, attributes] of shapes) {
      const shape = document.createElementNS(svgNamespace, tag);
      for (const [key, value] of Object.entries(attributes)) shape.setAttribute(key, value);
      svg.append(shape);
    }
    return svg;
  }
  function decorateToast(node, category) {
    node.classList.add("toast");
    node.setAttribute("role", category === "error" ? "alert" : "status");
    const close = document.createElement("button");
    close.type = "button"; close.className = "toast-close";
    close.setAttribute("aria-label", english ? "Dismiss notification" : "Đóng thông báo");
    close.textContent = "×"; close.addEventListener("click", () => node.remove());
    node.append(close);
    region.append(node);
    window.PetCare?.motion?.reveal([node]);
    if (category === "success") window.setTimeout(() => node.remove(), 6000);
  }
  window.PetCare = {
    ...window.PetCare,
    icon: createIcon,
    toast(message, category = "success") {
      if (!region) return;
      const node = document.createElement("div");
      node.className = `flash flash-${category}`;
      node.textContent = message; decorateToast(node, category);
    },
  };
  if (region) document.querySelectorAll(".flash-stack .flash").forEach(node => {
    const category = ["error", "warning", "success", "info"].find(name => node.classList.contains(`flash-${name}`));
    decorateToast(node, category);
  });
  function imageFallback(image) {
    if (image.tagName !== "IMG" || !image.closest(".pos-card-image, .cart-item-image")) return;
    image.hidden = true;
    const placeholder = document.createElement("span");
    placeholder.className = "image-fallback-icon";
    const kind = image.closest(".pos-card")?.dataset.kind || image.parentElement?.dataset.kind;
    placeholder.append(createIcon(kind === "product" ? "products" : "pets"));
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

  const tableScrollHint = english
    ? "Scrollable table. Focus here, then use the left and right arrow keys to view more columns."
    : "Bảng có thể cuộn ngang. Đưa tiêu điểm vào đây rồi dùng phím mũi tên trái/phải để xem thêm cột.";
  let tableRegionNumber = 0;
  document.querySelectorAll(".table-scroll").forEach(region => {
    const table = region.querySelector("table");
    if (!table) return;
    const original = {
      tabindex: region.getAttribute("tabindex"),
      role: region.getAttribute("role"),
      label: region.getAttribute("aria-label"),
      describedBy: region.getAttribute("aria-describedby")
    };
    let hint = null;
    const updateScrollAccess = () => {
      const overflows = region.scrollWidth > region.clientWidth + 1;
      if (overflows && !hint) {
        const sectionTitle = region.querySelector("caption")?.textContent.trim()
          || region.closest("section, article")?.querySelector("h2")?.textContent.trim();
        const contextLabel = sectionTitle || original.label?.trim();
        const regionLabel = contextLabel ? `${contextLabel}. ${tableScrollHint}` : tableScrollHint;
        hint = document.createElement("p");
        hint.className = "table-scroll-hint";
        hint.id = `table-scroll-hint-${++tableRegionNumber}`;
        hint.textContent = english ? "Scroll horizontally to see all columns." : "Cuộn ngang để xem đầy đủ các cột.";
        region.setAttribute("tabindex", "0");
        region.setAttribute("role", "region");
        region.setAttribute("aria-label", regionLabel);
        region.setAttribute("aria-describedby", hint.id);
        region.insertAdjacentElement("afterend", hint);
      } else if (!overflows && hint) {
        hint.remove();
        hint = null;
        for (const [name, value] of Object.entries({
          tabindex: original.tabindex,
          role: original.role,
          "aria-label": original.label,
          "aria-describedby": original.describedBy
        })) {
          if (value === null) region.removeAttribute(name);
          else region.setAttribute(name, value);
        }
      }
    };
    updateScrollAccess();
    if ("ResizeObserver" in window) new ResizeObserver(updateScrollAccess).observe(region);
    else window.addEventListener("resize", updateScrollAccess, {passive: true});
  });

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
