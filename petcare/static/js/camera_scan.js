(() => {
  const startButton = document.querySelector("[data-camera-start]");
  const preview = document.querySelector("[data-camera-preview]");
  const video = document.querySelector("[data-camera-video]");
  const captureButton = document.querySelector("[data-camera-capture]");
  const stopButton = document.querySelector("[data-camera-stop]");
  const status = document.querySelector("[data-camera-status]");
  const fileInput = document.querySelector("[data-search-photo]");

  if (!startButton || !preview || !video || !captureButton || !fileInput) return;

  let stream = null;

  function stopCamera() {
    if (stream) stream.getTracks().forEach((track) => track.stop());
    stream = null;
    video.srcObject = null;
    preview.hidden = true;
    startButton.hidden = false;
  }

  function cameraErrorMessage(error) {
    if (error.name === "NotAllowedError" || error.name === "SecurityError") {
      return status.dataset.cameraErrorPermission;
    }
    if (error.name === "NotFoundError" || error.name === "DevicesNotFoundError") {
      return status.dataset.cameraErrorMissing;
    }
    if (error.name === "NotReadableError" || error.name === "TrackStartError") {
      return status.dataset.cameraErrorBusy;
    }
    return status.dataset.cameraErrorGeneric;
  }

  startButton.addEventListener("click", async () => {
    status.textContent = "";
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      status.textContent = status.dataset.cameraUnsupported;
      return;
    }

    startButton.disabled = true;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: { facingMode: { ideal: "environment" } },
      });
      video.srcObject = stream;
      await video.play();
      preview.hidden = false;
      startButton.hidden = true;
    } catch (error) {
      stopCamera();
      status.textContent = cameraErrorMessage(error);
    } finally {
      startButton.disabled = false;
    }
  });

  captureButton.addEventListener("click", () => {
    if (!video.videoWidth || !video.videoHeight) {
      status.textContent = status.dataset.cameraNotReady;
      return;
    }

    const scale = Math.min(1, 1800 / Math.max(video.videoWidth, video.videoHeight));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(video.videoWidth * scale);
    canvas.height = Math.round(video.videoHeight * scale);
    canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
    captureButton.disabled = true;
    canvas.toBlob((blob) => {
      if (!blob) {
        status.textContent = status.dataset.cameraCaptureError;
        captureButton.disabled = false;
        return;
      }

      const file = new File([blob], `camera-scan-${Date.now()}.jpg`, { type: "image/jpeg" });
      const transfer = new DataTransfer();
      transfer.items.add(file);
      fileInput.files = transfer.files;
      stopCamera();
      fileInput.form.requestSubmit();
    }, "image/jpeg", 0.9);
  });

  stopButton?.addEventListener("click", stopCamera);
  window.addEventListener("pagehide", stopCamera);
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) stopCamera();
  });
})();
