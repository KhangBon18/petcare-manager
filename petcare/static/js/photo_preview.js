(() => {
  const petInput = document.querySelector("[data-photo-input]");
  const searchInput = document.querySelector("[data-search-photo]");
  const URLStore = new Map();

  function preview(input, wrapSelector, imageSelector) {
    const file = input?.files?.[0];
    const image = document.querySelector(imageSelector);
    const wrap = document.querySelector(wrapSelector);
    if (!file || !image || !wrap) return;
    if (!file.type.startsWith("image/")) return;
    if (file.size > 5 * 1024 * 1024) {
      input.value = "";
      window.alert(input.dataset.tooLargeMessage || "The image must be smaller than 5 MB.");
      return;
    }
    const previous = URLStore.get(image);
    if (previous) URL.revokeObjectURL(previous);
    const url = URL.createObjectURL(file);
    URLStore.set(image, url);
    image.src = url;
    wrap.hidden = false;
    const caption = wrap.querySelector("[data-preview-caption]");
    if (caption) caption.textContent = `${input.dataset.newCaption || "New image:"} ${file.name}`;
  }

  petInput?.addEventListener("change", () => {
    preview(petInput, "[data-preview-wrap]", "[data-photo-preview]");
  });
  searchInput?.addEventListener("change", () => {
    preview(searchInput, "[data-search-preview]", "[data-search-preview-image]");
  });
  window.addEventListener("pagehide", () => URLStore.forEach(url => URL.revokeObjectURL(url)));
})();
