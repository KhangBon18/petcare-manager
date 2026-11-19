/* Storefront progressive enhancement (strictly externalized for CSP) */
(function () {
  "use strict";

  function applyImageFallback(img) {
    if (!img || img.tagName !== "IMG") return;
    var fallback = img.getAttribute("data-fallback-src");
    if (!fallback || img.getAttribute("data-fallback-applied") === "1") return;
    img.setAttribute("data-fallback-applied", "1");
    img.setAttribute("src", fallback);
  }

  document.addEventListener(
    "error",
    function (event) {
      applyImageFallback(event.target);
    },
    true
  );

  // Catch any <img> whose initial src already failed before this deferred script ran.
  document.querySelectorAll("img[data-fallback-src]").forEach(function (img) {
    if (img.complete && img.naturalWidth === 0) {
      applyImageFallback(img);
    }
  });

  var langSelect = document.querySelector("[data-shop-lang]");
  if (langSelect && langSelect.form) {
    langSelect.addEventListener("change", function () {
      langSelect.form.submit();
    });
  }

  var fulfillmentInputs = document.querySelectorAll('input[name="fulfillment_method"]');
  var addressInput = document.getElementById("checkout-address");
  var paymentLabel = document.getElementById("checkout-payment-label");
  function syncCheckoutFulfillment() {
    if (!fulfillmentInputs.length) return;
    var selected = "pickup";
    fulfillmentInputs.forEach(function (inp) {
      if (inp.checked) selected = inp.value;
    });
    if (addressInput) {
      addressInput.required = selected === "cod_delivery";
    }
    if (paymentLabel) {
      var storeText = paymentLabel.getAttribute("data-store-text") || "";
      var codText = paymentLabel.getAttribute("data-cod-text") || "";
      paymentLabel.textContent = selected === "cod_delivery" ? codText : storeText;
    }
  }
  fulfillmentInputs.forEach(function (inp) {
    inp.addEventListener("change", syncCheckoutFulfillment);
  });
  syncCheckoutFulfillment();

  // Public Image Search preview & 5MB size check
  var imageInput = document.getElementById("sf-image-input");
  var imageStatus = document.getElementById("sf-image-file-note");
  if (imageInput && imageStatus) {
    imageInput.addEventListener("change", function () {
      var file = imageInput.files && imageInput.files[0];
      if (!file) return;
      if (file.size > 5 * 1024 * 1024) {
        imageStatus.textContent = imageStatus.getAttribute("data-too-large") || "File exceeds 5 MB limit.";
        imageInput.value = "";
      } else {
        imageStatus.textContent = file.name;
      }
    });
  }

  // Public Shopping AI Assistant
  var chatRoot = document.getElementById("sf-ai-root");
  if (chatRoot) {
    var stream = document.getElementById("sf-ai-stream");
    var form = document.getElementById("sf-ai-form");
    var input = document.getElementById("sf-ai-question");
    var sendBtn = document.getElementById("sf-ai-send");
    var endpoint = chatRoot.getAttribute("data-chat-url");
    var addCartUrl = chatRoot.getAttribute("data-add-cart-url");
    var csrf = chatRoot.getAttribute("data-csrf-token");
    var locale = chatRoot.getAttribute("data-locale") || "vi";
    var history = [];
    var busy = false;

    function createCardNode(card) {
      var box = document.createElement("article");
      box.className = "sf-card";
      var media = document.createElement("div");
      media.className = "sf-card-media" + (card.kind === "product" ? " sf-card-media-product" : "");
      var img = document.createElement("img");
      img.src = card.photo_url || card.fallback_url || "";
      if (card.fallback_url) img.setAttribute("data-fallback-src", card.fallback_url);
      img.alt = card.name || "";
      media.appendChild(img);
      box.appendChild(media);

      var body = document.createElement("div");
      body.className = "sf-card-body";
      var title = document.createElement("h3");
      title.className = "sf-card-title";
      var link = document.createElement("a");
      link.href = card.url || "#";
      link.textContent = card.name || "";
      title.appendChild(link);
      body.appendChild(title);

      var meta = document.createElement("div");
      meta.className = "sf-card-meta";
      meta.textContent = [card.code, card.status_label].filter(Boolean).join(" · ");
      body.appendChild(meta);

      var price = document.createElement("div");
      price.className = "sf-card-price";
      price.textContent = card.price_label || "";
      body.appendChild(price);

      if (card.can_add_to_cart && addCartUrl) {
        var actions = document.createElement("div");
        actions.className = "sf-card-actions";
        var cartForm = document.createElement("form");
        cartForm.method = "post";
        cartForm.action = addCartUrl;
        [
          ["csrf_token", csrf],
          ["item_type", card.kind],
          ["item_id", String(card.id)],
          ["quantity", "1"],
          ["next", window.location.pathname],
        ].forEach(function (pair) {
          var hid = document.createElement("input");
          hid.type = "hidden";
          hid.name = pair[0];
          hid.value = pair[1];
          cartForm.appendChild(hid);
        });
        var btn = document.createElement("button");
        btn.type = "submit";
        btn.className = "sf-btn sf-btn-primary sf-btn-sm";
        btn.textContent = locale === "en" ? "Add to cart" : "Thêm vào giỏ";
        cartForm.appendChild(btn);
        actions.appendChild(cartForm);
        body.appendChild(actions);
      }
      box.appendChild(body);
      return box;
    }

    function appendMessage(role, text, data) {
      var wrap = document.createElement("div");
      wrap.className = "sf-msg " + (role === "user" ? "sf-msg-user" : "sf-msg-bot");
      var noticeMsg = data && data.safety_notice && data.safety_notice.message
        ? data.safety_notice.message.trim()
        : "";
      var trimmedText = (text || "").trim();
      if (!noticeMsg || noticeMsg !== trimmedText) {
        var p = document.createElement("div");
        p.textContent = text || "";
        wrap.appendChild(p);
      }
      if (noticeMsg) {
        var notice = document.createElement("div");
        notice.className = "sf-notice";
        notice.textContent = noticeMsg;
        wrap.appendChild(notice);
      }

      if (data && Array.isArray(data.cards) && data.cards.length) {
        var grid = document.createElement("div");
        grid.className = "sf-ai-cards";
        data.cards.forEach(function (card) {
          grid.appendChild(createCardNode(card));
        });
        wrap.appendChild(grid);
      }
      stream.appendChild(wrap);
      stream.scrollTop = stream.scrollHeight;
    }

    function submitQuestion(text) {
      var trimmed = (text || "").trim();
      if (!trimmed || busy) return;
      busy = true;
      if (sendBtn) sendBtn.disabled = true;
      appendMessage("user", trimmed);
      history.push({ role: "user", content: trimmed });

      fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrf,
        },
        body: JSON.stringify({ question: trimmed, history: history.slice(-8) }),
      })
        .then(function (resp) {
          return resp.json().then(function (body) {
            return { ok: resp.ok, body: body };
          });
        })
        .then(function (res) {
          if (!res.ok) {
            appendMessage("bot", (res.body && res.body.error) || "Không thể xử lý câu hỏi lúc này.");
            return;
          }
          var replyText = res.body.reply || "";
          history.push({ role: "assistant", content: replyText });
          appendMessage("bot", replyText, res.body);
        })
        .catch(function () {
          appendMessage("bot", locale === "en" ? "Connection error. Please try again." : "Lỗi kết nối. Vui lòng thử lại.");
        })
        .finally(function () {
          busy = false;
          if (sendBtn) sendBtn.disabled = false;
        });
    }

    if (form && input) {
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        var val = input.value;
        input.value = "";
        submitQuestion(val);
      });
    }
    document.querySelectorAll("[data-sf-prompt]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        submitQuestion(btn.getAttribute("data-sf-prompt"));
      });
    });

    var initQ = chatRoot.getAttribute("data-initial-prompt");
    if (initQ) submitQuestion(initQ);
  }
  document.querySelectorAll("form[data-sf-confirm]").forEach(function (cfmForm) {
    cfmForm.addEventListener("submit", function (e) {
      var msg = cfmForm.getAttribute("data-sf-confirm");
      if (msg && !window.confirm(msg)) {
        e.preventDefault();
      }
    });
  });

  document.querySelectorAll("form[data-sf-submit-lock]").forEach(function (lockForm) {
    lockForm.addEventListener("submit", function (e) {
      if (lockForm.getAttribute("data-sf-submitting") === "1") {
        e.preventDefault();
        return;
      }
      lockForm.setAttribute("data-sf-submitting", "1");
      var btn = lockForm.querySelector('button[type="submit"]');
      if (btn) {
        btn.disabled = true;
        var label = lockForm.getAttribute("data-sf-submit-lock");
        if (label) btn.textContent = label;
      }
    });
  });
})();

