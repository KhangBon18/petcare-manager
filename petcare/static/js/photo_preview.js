(() => {
  const petInput = document.querySelector("[data-photo-input]");
  const searchInput = document.querySelector("[data-search-photo]");
  const URLStore = new Map();
  const english = document.documentElement.lang === "en";

  function statusFor(input) {
    return document.querySelector(
      input.matches("[data-photo-input]") ? "[data-photo-upload-status]" : "[data-search-upload-status]"
    );
  }

  function preview(input, wrapSelector, imageSelector) {
    const file = input?.files?.[0];
    const image = document.querySelector(imageSelector);
    const wrap = document.querySelector(wrapSelector);
    const status = statusFor(input);
    if (!image || !wrap || !status) return;
    if (!file) {
      wrap.hidden = true;
      status.textContent = "";
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      input.value = "";
      wrap.hidden = true;
      status.textContent = input.dataset.tooLargeMessage || (english ? "Choose an image under 5 MB." : "Hãy chọn ảnh nhỏ hơn 5 MB.");
      return;
    }

    const previous = URLStore.get(image);
    if (previous) URL.revokeObjectURL(previous);
    status.textContent = "";
    const url = URL.createObjectURL(file);
    URLStore.set(image, url);
    image.onload = () => {
      if (URLStore.get(image) !== url) return;
      wrap.hidden = false;
      const caption = wrap.querySelector("[data-preview-caption]");
      if (caption) caption.textContent = `${input.dataset.newCaption || (english ? "New image:" : "Ảnh mới:")} ${file.name}`;
    };
    image.onerror = () => {
      if (URLStore.get(image) !== url) return;
      wrap.hidden = true;
      URL.revokeObjectURL(url);
      URLStore.delete(image);
      status.textContent = english
        ? "The browser cannot preview this file. The server will validate its actual image format."
        : "Trình duyệt chưa xem trước được tệp. Máy chủ sẽ kiểm tra định dạng ảnh thực tế.";
    };
    image.src = url;
  }

  petInput?.addEventListener("change", () => {
    preview(petInput, "[data-preview-wrap]", "[data-photo-preview]");
  });
  searchInput?.addEventListener("change", () => {
    preview(searchInput, "[data-search-preview]", "[data-search-preview-image]");
  });
  window.addEventListener("pagehide", () => URLStore.forEach(url => URL.revokeObjectURL(url)));
})();
