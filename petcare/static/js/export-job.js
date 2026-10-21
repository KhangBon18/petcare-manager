(() => {
  const root = document.querySelector("[data-export-job][data-poll='true']");
  if (!root) return;

  const message = document.getElementById("export-job-message");
  const download = document.getElementById("export-download");
  const copy = {
    pending: "Yêu cầu đang chờ worker xử lý.",
    processing: "Đang đóng gói dữ liệu và ảnh của cửa hàng. Trạng thái sẽ tự cập nhật.",
    failed: "Không thể tạo bản xuất. Hãy yêu cầu tạo lại hoặc liên hệ quản trị hệ thống.",
    expired: "Bản xuất đã hết hạn và được xóa khỏi hệ thống.",
  };
  let stopped = false;
  let failures = 0;

  async function refresh() {
    if (stopped) return;
    try {
      const response = await fetch(root.dataset.statusUrl, {
        credentials: "same-origin",
        cache: "no-store",
        headers: { Accept: "application/json" },
      });
      if (!response.ok) throw new Error("status_unavailable");
      const state = await response.json();
      failures = 0;
      message.textContent = copy[state.status] || copy.processing;
      if (state.status === "ready" && state.download_url) {
        download.href = state.download_url;
        download.hidden = false;
        stopped = true;
        return;
      }
      if (["failed", "expired"].includes(state.status)) {
        stopped = true;
        return;
      }
    } catch (_error) {
      failures += 1;
      if (failures >= 3) {
        message.textContent = "Chưa lấy được trạng thái mới. Trang sẽ thử lại tự động.";
      }
    }
    window.setTimeout(refresh, Math.min(15000, 3000 * (failures + 1)));
  }

  window.setTimeout(refresh, 1500);
})();
