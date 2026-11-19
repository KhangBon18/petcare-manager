(() => {
  const root = document.querySelector("[data-export-job][data-poll='true']");
  if (!root) return;

  const message = document.getElementById("export-job-message");
  const download = document.getElementById("export-download");
  const indicator = document.querySelector("[data-export-indicator]");
  const english = document.documentElement.lang === "en";
  const copy = english ? {
    pending: "Waiting for an export worker.", processing: "Packaging store data and images…",
    ready: "Your export is ready to download.", failed: "The export failed. Create another request or contact an administrator.",
    expired: "This export has expired and was removed.", retry: "Could not refresh the status. Retrying automatically…",
  } : {
    pending: "Yêu cầu đang chờ worker xử lý.",
    processing: "Đang đóng gói dữ liệu và ảnh của cửa hàng. Trạng thái sẽ tự cập nhật.",
    failed: "Không thể tạo bản xuất. Hãy yêu cầu tạo lại hoặc liên hệ quản trị hệ thống.",
    expired: "Bản xuất đã hết hạn và được xóa khỏi hệ thống.",
    ready: "Bản xuất đã sẵn sàng. Hãy tải về trước thời hạn lưu trữ.",
    retry: "Chưa lấy được trạng thái mới. Trang sẽ thử lại tự động.",
  };
  let stopped = false;
  let failures = 0;
  let controller;
  let timer;

  async function refresh() {
    if (stopped) return;
    controller = new AbortController();
    root.setAttribute("aria-busy", "true");
    try {
      const response = await fetch(root.dataset.statusUrl, {
        credentials: "same-origin",
        cache: "no-store",
        headers: { Accept: "application/json" },
        signal: controller.signal,
      });
      if (!response.ok) throw new Error("status_unavailable");
      const state = await response.json();
      if (stopped) return;
      failures = 0;
      message.textContent = copy[state.status] || copy.processing;
      if (state.status === "ready" && state.download_url) {
        download.href = state.download_url;
        download.hidden = false;
        stopped = true;
        root.setAttribute("aria-busy", "false");
        if (indicator) indicator.hidden = true;
        return;
      }
      if (["failed", "expired"].includes(state.status)) {
        stopped = true;
        root.setAttribute("aria-busy", "false");
        if (indicator) indicator.hidden = true;
        return;
      }
    } catch (_error) {
      failures += 1;
      if (failures >= 3) {
        message.textContent = copy.retry;
      }
    }
    if (!stopped) timer = window.setTimeout(refresh, Math.min(15000, 3000 * (failures + 1)));
  }

  timer = window.setTimeout(refresh, 1500);
  window.addEventListener("pagehide", () => { stopped = true; clearTimeout(timer); controller?.abort(); });
})();
