const {test} = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const {Node, UIEvent, el, deferred, settle} = require("./dom.cjs");

function cloneTree(node) {
  const copy = new Node(node.tagName);
  copy.id = node.id;
  copy.className = node.className;
  copy.textContent = node.textContent;
  copy.value = node.value;
  copy.hidden = node.hidden;
  copy.disabled = node.disabled;
  copy.dataset = {...node.dataset};
  copy.attributes = {...node.attributes};
  copy.cloneNode = () => cloneTree(copy);
  for (const child of node.children) {
    copy.append(cloneTree(child));
  }
  return copy;
}

function buildWorkspaceTree({lang = "en", initialScope = "workspace"} = {}) {
  const wsBtn = el("button", {dataset: {scopeValue: "workspace"}});
  const shopperBtn = el("button", {dataset: {scopeValue: "shopper_preview"}});
  const resetBtn = el("button", {id: "ai-workspace-reset"});
  const clearSlotsBtn = el("button", {id: "ai-clear-slots", hidden: true});
  const contextChips = el("div", {id: "ai-context-chips"});
  const compareCount = el("span", {id: "ai-compare-count"});
  const compareSubmit = el("button", {id: "ai-compare-submit"});
  const compareClear = el("button", {id: "ai-compare-clear"});
  const compareTray = el("div", {id: "ai-compare-tray", hidden: true}, [
    compareCount,
    compareSubmit,
    compareClear,
  ]);

  const starterBtn = el("button", {
    dataset: {aiPrompt: "I want a cat suitable for an apartment"},
    textContent: "Apartment cat",
  });
  const opsGroup = el("div", {dataset: {workspaceOnly: "true"}, attributes: {"data-workspace-only": "true"}});
  const bannerCopy = el("p", {id: "ai-scope-banner-copy"});
  const welcomePanel = el("section", {id: "ai-welcome-panel"}, [bannerCopy, starterBtn, opsGroup]);
  const stream = el("div", {id: "ai-workspace-messages"}, [welcomePanel]);

  const input = el("textarea", {id: "ai-workspace-input", value: ""});
  const sendBtn = el("button", {id: "ai-workspace-send", attributes: {type: "submit"}});
  const charCount = el("span", {id: "ai-char-count"});
  const csrfInput = el("input", {attributes: {name: "csrf_token"}, value: "csrf-test-123"});
  const form = el("form", {id: "ai-workspace-form", action: "/assistant/chat"}, [
    csrfInput,
    input,
    sendBtn,
    charCount,
  ]);

  const workspace = el("div", {
    id: "ai-workspace",
    dataset: {
      chatUrl: "/assistant/chat",
      resetUrl: "/assistant/reset",
      csrfToken: "csrf-test-123",
      initialScope,
      conversationId: "conv_initial_test",
    },
  }, [wsBtn, shopperBtn, resetBtn, clearSlotsBtn, contextChips, compareTray, stream, form]);

  const doc = el("document", {}, [workspace]);
  doc.documentElement = {lang};
  doc.body = doc;
  doc.getElementById = id => doc.querySelector(`#${id}`);
  doc.createElement = tag => {
    const n = new Node(tag);
    n.cloneNode = () => cloneTree(n);
    return n;
  };
  doc.createTextNode = txt => el("text", {textContent: String(txt)});
  welcomePanel.cloneNode = () => cloneTree(welcomePanel);
  Object.defineProperty(doc, "activeElement", {get: () => Node.active});

  const timers = new Map();
  const requests = [];
  const win = new Node();
  win.setTimeout = fn => {
    const id = Symbol("timer");
    timers.set(id, fn);
    return id;
  };

  const ctx = {
    document: doc,
    window: win,
    Element: Node,
    HTMLInputElement: Node,
    AbortController,
    URL: URL,
    setTimeout: win.setTimeout,
    clearTimeout: id => timers.delete(id),
    fetch: (url, options) => {
      const d = deferred();
      requests.push({url, options, ...d});
      return d.promise;
    },
  };

  const scriptPath = path.join(__dirname, "../../petcare/static/js/assistant_workspace.js");
  vm.runInNewContext(fs.readFileSync(scriptPath, "utf8"), ctx);

  return {
    doc,
    workspace,
    stream,
    input,
    sendBtn,
    form,
    wsBtn,
    shopperBtn,
    resetBtn,
    clearSlotsBtn,
    contextChips,
    compareTray,
    compareCount,
    compareSubmit,
    starterBtn,
    opsGroup,
    requests,
  };
}

test("starter prompt click sends chat turn, updates context chips, and escapes untrusted strings", async () => {
  const h = buildWorkspaceTree({lang: "en"});
  h.starterBtn.click();
  assert.equal(h.requests.length, 1);
  const body = JSON.parse(h.requests[0].options.body);
  assert.equal(body.message, "I want a cat suitable for an apartment");
  assert.equal(body.scope, "workspace");

  h.requests[0].resolve({
    ok: true,
    json: async () => ({
      reply: "Here is **Miu** matching your apartment preference.",
      response_type: "pet_recommendations",
      conversation_id: "conv_turn_1",
      context_state: {
        chips: [
          {slot: "species", label: "Cat"},
          {slot: "living_space", label: "Apartment"},
        ],
      },
      cards: [
        {
          kind: "pet",
          id: 1,
          code: "PET-001",
          name: "<img src=x onerror=bad()>",
          price_label: "6,200,000 VND",
          status_label: "Available",
          score: 88,
          max_score: 100,
          url: "/pets/1",
          photo_url: "javascript:evil()",
          reasons: ["Documented gentle trait"],
          warnings: ["Weight undocumented"],
          verified_attributes: {breed: "British Shorthair", age: "14 months"},
          score_breakdown: [{label: "Budget fit", points: 30, max_points: 30}],
        },
      ],
      follow_up_questions: ["Calm, below 5 million VND"],
    }),
  });
  await settle();

  const chips = h.contextChips.querySelectorAll(".ai-slot-chip");
  assert.equal(chips.length, 2);
  assert.equal(h.clearSlotsBtn.hidden, false);

  const cards = h.stream.querySelectorAll(".ai-rec-card");
  assert.equal(cards.length, 1);
  // Untrusted HTML stays inert textContent and javascript: photo URL is rejected
  assert.equal(cards[0].querySelector("img"), null);
  assert.equal(cards[0].querySelector(".ai-profile-link").href, "/pets/1");
});

test("Enter submits while Shift+Enter does not, and product compare tray builds comparison matrix", async () => {
  const h = buildWorkspaceTree({lang: "en"});
  h.input.value = "Recommend cat food";

  // Shift+Enter must NOT submit
  const shiftEnter = new UIEvent("keydown", {key: "Enter", shiftKey: true});
  h.input.dispatchEvent(shiftEnter);
  assert.equal(h.requests.length, 0);

  // Plain Enter submits
  const enterEvt = new UIEvent("keydown", {key: "Enter", shiftKey: false});
  h.input.dispatchEvent(enterEvt);
  assert.equal(enterEvt.defaultPrevented, true);
  assert.equal(h.requests.length, 1);

  h.requests[0].resolve({
    ok: true,
    json: async () => ({
      reply: "Top 2 cat foods:",
      response_type: "product_recommendations",
      cards: [
        {
          kind: "product",
          id: 10,
          code: "FOOD-001",
          name: "Indoor Cat Kibble 1.5kg",
          price_label: "330,000 VND",
          unit_price_display: "220,000 VND/kg",
          stock_qty: 8,
          score: 94,
          max_score: 100,
          url: "/products/10",
          reasons: ["Verified cat food"],
          warnings: [],
        },
        {
          kind: "product",
          id: 11,
          code: "FOOD-002",
          name: "Salmon Adult Cat 2kg",
          price_label: "320,000 VND",
          unit_price_display: "160,000 VND/kg",
          stock_qty: 6,
          score: 96,
          max_score: 100,
          url: "/products/11",
          reasons: ["Best unit value"],
          warnings: [],
        },
      ],
    }),
  });
  await settle();

  const checkboxes = h.stream.querySelectorAll("input[data-compare-code]");
  assert.equal(checkboxes.length, 2);
  assert.equal(h.compareTray.hidden, true);

  checkboxes[0].checked = true;
  checkboxes[0].dispatchEvent(new UIEvent("change", {bubbles: true}));
  assert.equal(h.compareTray.hidden, true);

  checkboxes[1].checked = true;
  checkboxes[1].dispatchEvent(new UIEvent("change", {bubbles: true}));
  assert.equal(h.compareTray.hidden, false);
  assert.equal(h.compareCount.textContent, "2 selected");

  h.compareSubmit.click();
  assert.equal(h.requests.length, 2);
  const cmpReq = JSON.parse(h.requests[1].options.body);
  assert.equal(cmpReq.message, "Compare FOOD-001, FOOD-002");

  h.requests[1].resolve({
    ok: true,
    json: async () => ({
      reply: "Side-by-side comparison:",
      response_type: "product_comparison",
      comparison: {
        items: [
          {id: 10, code: "FOOD-001", name: "Indoor Cat Kibble 1.5kg", url: "/products/10"},
          {id: 11, code: "FOOD-002", name: "Salmon Adult Cat 2kg", url: "/products/11"},
        ],
        rows: [
          {key: "price", label: "Price", values: ["330,000 VND", "320,000 VND"]},
          {key: "unit_price", label: "Unit price", values: ["220,000 VND/kg", "160,000 VND/kg"]},
        ],
      },
    }),
  });
  await settle();

  assert.equal(h.stream.querySelectorAll(".ai-comparison-table").length, 1);
  assert.equal(h.stream.querySelectorAll(".ai-comparison-mobile-card").length, 2);
});

test("knowledge citations enforce https allowlist and emergency safety banner renders steps", async () => {
  const h = buildWorkspaceTree({lang: "en", initialScope: "shopper_preview"});
  assert.equal(h.opsGroup.hidden, true);

  h.input.value = "My cat chewed a lily leaf!";
  h.form.dispatchEvent(new UIEvent("submit"));
  h.requests[0].resolve({
    ok: true,
    json: async () => ({
      reply: "Seek emergency veterinary care immediately.",
      response_type: "knowledge_answer",
      safety_notice: {
        severity: "emergency",
        title: "URGENT VETERINARY WARNING",
        message: "True lilies cause acute kidney injury in cats.",
        escalation_steps: ["Go to nearest emergency vet clinic now."],
      },
      citations: [
        {
          doc_id: "KB-SAFE-002",
          title: "Household Toxic Plants",
          source_name: "ASPCA",
          source_url: "https://www.aspca.org/pet-care",
          updated_at: "2025-08-01",
          version: "1.0.0",
        },
        {
          doc_id: "KB-BAD",
          title: "Untrusted Link",
          source_name: "Bad",
          source_url: "javascript:alert(1)",
          updated_at: "2025-01-01",
          version: "1.0.0",
        },
      ],
    }),
  });
  await settle();

  const safety = h.stream.querySelector(".ai-safety-banner");
  assert.notEqual(safety, null);
  const citationLinks = h.stream.querySelectorAll(".ai-citation-card a");
  assert.equal(citationLinks.length, 1);
  assert.equal(citationLinks[0].href, "https://www.aspca.org/pet-care");
  assert.equal(citationLinks[0].rel, "noopener noreferrer");
});

test("scope toggle resets conversation and network failure exposes working retry button", async () => {
  const h = buildWorkspaceTree({lang: "vi", initialScope: "workspace"});
  assert.equal(h.opsGroup.hidden, false);

  // Switch to Shopper Preview -> hides workspace-only group and calls /assistant/reset
  h.shopperBtn.click();
  assert.equal(h.opsGroup.hidden, true);
  assert.equal(h.requests.length, 1);
  assert.equal(h.requests[0].url, "/assistant/reset");
  h.requests[0].resolve({ok: true, json: async () => ({ok: true, conversation_id: "conv_shopper_new"})});
  await settle();

  // Trigger HTTP 503 failure -> retry button appears and re-submits exact prompt
  h.input.value = "Gợi ý thức ăn cho mèo trưởng thành";
  h.form.dispatchEvent(new UIEvent("submit"));
  assert.equal(h.requests.length, 2);
  h.requests[1].resolve({
    ok: false,
    status: 503,
    json: async () => ({error: "Dịch vụ tạm bận"}),
  });
  await settle();

  const retryBtn = h.stream.querySelector("[data-ai-retry]");
  assert.notEqual(retryBtn, null);
  retryBtn.click();
  assert.equal(h.requests.length, 3);
  assert.equal(JSON.parse(h.requests[2].options.body).message, "Gợi ý thức ăn cho mèo trưởng thành");
  h.requests[2].resolve({ok: true, json: async () => ({reply: "Đã phục hồi", response_type: "answer"})});
  await settle();
});

test("immediate submit during pending reset awaits fresh conversation_id and renders combined_operational insights", async () => {
  const h = buildWorkspaceTree({lang: "en", initialScope: "workspace"});

  // Click reset and immediately submit before /assistant/reset resolves
  h.resetBtn.click();
  assert.equal(h.requests.length, 1);
  assert.equal(h.requests[0].url, "/assistant/reset");

  h.input.value = "Show top-selling products and inventory forecast";
  h.form.dispatchEvent(new UIEvent("submit"));
  // Chat fetch waits until /assistant/reset resolves with fresh conversation_id
  assert.equal(h.requests.length, 1);

  h.requests[0].resolve({
    ok: true,
    json: async () => ({ok: true, conversation_id: "conv_fresh_after_reset"}),
  });
  await settle();

  assert.equal(h.requests.length, 2);
  assert.equal(h.requests[1].url, "/assistant/chat");
  assert.equal(JSON.parse(h.requests[1].options.body).conversation_id, "conv_fresh_after_reset");

  h.requests[1].resolve({
    ok: true,
    json: async () => ({
      reply: "Combined store operational summary:",
      response_type: "operational_insight",
      insight: {
        kind: "combined_operational",
        sections: [
          {
            kind: "top_products",
            period: "week",
            start_date: "2026-11-09",
            end_date: "2026-11-13",
            items: [{name: "Salmon Cat Food", code: "FOOD-002", quantity_sold: 4, revenue_label: "1,280,000 VND", url: "/products/11"}],
          },
          {
            kind: "inventory_forecast",
            target_days: 14,
            total: 1,
            items: [{name: "Tofu Cat Litter", code: "CARE-002", stock_qty: 2, suggested_qty: 6, url: "/products/15"}],
          },
        ],
      },
    }),
  });
  await settle();

  const opsSections = h.stream.querySelectorAll(".ai-ops-insight");
  assert.equal(opsSections.length, 2);
  assert.equal(h.stream.querySelectorAll(".ai-turn-bot").length, 1);
});
