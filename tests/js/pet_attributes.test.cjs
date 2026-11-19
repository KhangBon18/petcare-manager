const {test} = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const {Node, UIEvent, el, deferred, settle} = require("./dom.cjs");

function fixture() {
  const csrf = el("input", {attributes: {name: "csrf_token"}, value: "csrf-test"});
  const input = el("input", {dataset: {suggestUrl: "/pets/suggest-attributes"}, files: [{name: "synthetic.png", size: 20}]});
  const species = el("input", {value: ""});
  const coat = el("input", {value: "manual value"});
  const status = el("p", {dataset: {attributeStatus: ""}});
  const values = el("div", {dataset: {attributeValues: ""}});
  const apply = el("button", {dataset: {attributeApply: ""}, hidden: true});
  const retry = el("button", {dataset: {attributeRetry: ""}, hidden: true});
  const cancel = el("button", {dataset: {attributeCancel: ""}, hidden: true});
  const dismiss = el("button", {dataset: {attributeDismiss: ""}, hidden: true});
  const panel = el("section", {dataset: {attributePanel: ""}, hidden: true}, [status, values, apply, retry, cancel, dismiss]);
  const form = el("form", {elements: {namedItem: name => ({species, coat_color: coat}[name] || null)}}, [csrf, input, species, coat, panel]);
  const root = el("document", {}, [form]);
  root.documentElement = {lang: "en"};
  root.querySelector = selector => root.querySelectorAll(selector)[0] || null;
  root.createElement = tag => new Node(tag);
  const requests = [];
  const h = deferred();
  const window = new Node();
  const context = {
    document: root, window, AbortController, Event: UIEvent,
    FormData: class { constructor() { this.entries = []; } append(...args) { this.entries.push(args); } },
    fetch: (url, options) => { const pending = deferred(); requests.push({url, options, ...pending}); return pending.promise; }
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, "../../petcare/static/js/pet_attributes.js"), "utf8"), context);
  return {input, species, coat, status, values, apply, retry, cancel, dismiss, panel, requests, window, fireChange: () => input.dispatchEvent(new UIEvent("change"))};
}

test("vision suggestions render as text and apply only to blank form fields", async () => {
  const f = fixture();
  f.fireChange();
  assert.equal(f.panel.getAttribute("aria-busy"), "true");
  assert.equal(f.requests[0].options.headers["X-CSRFToken"], "csrf-test");
  f.requests[0].resolve({ok: true, json: async () => ({
    status: "observations", mode: "vision", provider_status: "used",
    suggestions: {species: "<b>cat</b>", coat_color: "black", confidence: "99%", url: "/admin"}
  })});
  await settle();
  assert.equal(f.status.textContent, "Appearance suggestions · review them before applying.");
  assert.equal(f.values.children.length, 2);
  assert.equal(f.values.children[0].textContent, "Species: <b>cat</b>");
  f.apply.click();
  assert.equal(f.species.value, "<b>cat</b>");
  assert.equal(f.coat.value, "manual value");
  assert.equal(f.status.textContent, "Filled empty fields. Review them before saving.");
});

test("reviewed suggestions can be rejected without changing fields", async () => {
  const f = fixture();
  f.fireChange();
  f.requests[0].resolve({ok: true, json: async () => ({
    status: "observations", mode: "vision", provider_status: "used",
    suggestions: {species: "cat", coat_color: "black"}
  })});
  await settle();
  assert.equal(f.dismiss.hidden, false);
  f.dismiss.click();
  assert.equal(f.species.value, "");
  assert.equal(f.coat.value, "manual value");
  assert.equal(f.values.children.length, 0);
  assert.equal(f.dismiss.hidden, true);
  assert.equal(f.input, Node.active);
  assert.match(f.status.textContent, /Suggestions dismissed/);
});

test("provider errors expose retry and local estimates are marked uncertain", async () => {
  const f = fixture();
  f.fireChange();
  f.requests[0].resolve({ok: false, json: async () => ({status: "processing_error", error: "Temporary error"})});
  await settle();
  assert.equal(f.retry.hidden, false);
  assert.equal(f.status.textContent, "Temporary error");
  f.retry.click();
  f.requests[1].resolve({ok: true, json: async () => ({
    status: "uncertain", mode: "local", provider_status: "unavailable",
    suggestions: {coat_color: "gray"}, warning: "ignored provider details"
  })});
  await settle();
  assert.equal(f.status.textContent, "Vision provider unavailable · showing only the local color estimate, which may include the background.");
  assert.equal(f.apply.hidden, false);
});

test("cancel aborts the current request and keeps a safe retry action", async () => {
  const f = fixture();
  f.fireChange();
  const pending = f.requests[0];
  f.cancel.click();
  assert.equal(pending.options.signal.aborted, true);
  assert.equal(f.panel.getAttribute("aria-busy"), "false");
  assert.equal(f.retry.hidden, false);
  assert.match(f.status.textContent, /Stopped waiting/);
});
