(() => {
  const english = document.documentElement.lang === "en";
  let printDetails = [];
  window.addEventListener("beforeprint", () => {
    if (printDetails.length) return;
    printDetails = [...document.querySelectorAll(".report-document details")].map(node => [node, node.open]);
    printDetails.forEach(([node]) => {node.open = true;});
  });
  window.addEventListener("afterprint", () => {
    printDetails.forEach(([node, wasOpen]) => {node.open = wasOpen;}); printDetails = [];
  });
  document.querySelector("[data-print-report]")?.addEventListener("click", () => window.print());
  const form = document.querySelector("[data-report-export]");
  if (!form) return;
  let busy = false;
  form.addEventListener("submit", async event => {
    event.preventDefault(); if (busy) return;
    busy = true;
    const button = form.querySelector('button[type="submit"]'), label = button.textContent;
    button.disabled = true; button.textContent = english ? "Preparing Excel…" : "Đang tạo Excel…";
    form.setAttribute("aria-busy", "true");
    try {
      const data = new FormData(form);
      const response = await fetch(form.action, {method: "POST", credentials: "same-origin",
        headers: {"Content-Type": "application/json", "X-CSRFToken": data.get("csrf_token")},
        body: JSON.stringify({snapshot: data.get("snapshot")})});
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.error || (english ? "Export unavailable. Reload the report and try again." : "Chưa xuất được. Tải lại báo cáo rồi thử lại."));
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob), link = document.createElement("a");
      link.href = url; link.download = response.headers.get("Content-Disposition")?.match(/filename="?([^";]+)"?/)?.[1] || "PetCare-report.xlsx";
      document.body.append(link); link.click(); link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      window.PetCare?.toast(english ? "Excel report downloaded." : "Đã tải báo cáo Excel.");
    } catch (error) { window.PetCare?.toast((error.name === "TypeError" ? "" : error.message) || (english ? "Could not connect. Your report is unchanged; try again." : "Không kết nối được. Báo cáo vẫn được giữ; hãy thử lại."), "error"); }
    finally { busy = false; button.disabled = false; button.textContent = label; form.setAttribute("aria-busy", "false"); }
  });
})();
