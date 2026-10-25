// No test dependencies: exercise the shipped script with a small DOM adapter
// and controlled network/timer boundaries, including responses that ignore abort.
const {test} = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

class Element {
  constructor() {
    this.dataset = {};
    this.listeners = {};
    this.attributes = {};
    this.textContent = "";
    this.hidden = false;
    this.disabled = false;
    this.classList = {toggle() {}, remove() {}};
  }
  addEventListener(type, callback) { (this.listeners[type] ||= []).push(callback); }
  dispatchEvent(event) { for (const callback of this.listeners[event.type] || []) callback(event); }
  setAttribute(key, value) { this.attributes[key] = value; }
  getAttribute(key) { return this.attributes[key]; }
  removeAttribute(key) { delete this.attributes[key]; }
  focus() { this.focused = true; }
}

class Option extends Element {
  constructor(text, value) { super(); this.textContent = text; this.value = value; }
}

class Select extends Element {
  constructor() { super(); this.children = [new Option("Choose", "")]; this.selectedIndex = 0; }
  get options() { return this.children.flatMap(child => child instanceof Option ? [child] : child.children); }
  get selectedOptions() { return [this.options[this.selectedIndex]].filter(Boolean); }
  get value() { return this.options[this.selectedIndex]?.value || ""; }
  set value(value) { this.selectedIndex = this.options.findIndex(option => option.value === value); }
  replaceChildren(...children) { this.children = children; this.selectedIndex = 0; }
  append(child) { this.children.push(child); }
  add(child) { this.append(child); }
  querySelectorAll(selector) { return selector === "optgroup" ? this.children.filter(c => !(c instanceof Option)) : []; }
}

function widget(kind) {
  const result = new Element();
  result.dataset = {lookupKind: kind, source: `/lookups/${kind}`, productPage: "1", petPage: "1",
                    productHasMore: "false", petHasMore: "false", lookupPage: "1"};
  result.input = new Element();
  result.select = new Select();
  result.status = new Element();
  result.more = new Element();
  result.querySelector = selector => ({
    "[data-lookup-search]": result.input, "[data-lookup-select]": result.select,
    "[data-lookup-status]": result.status, "[data-lookup-more]": result.more,
  })[selector];
  result.querySelectorAll = () => result.select.options;
  return result;
}

function harness() {
  const items = widget("items");
  const customer = widget("customers");
  customer.select.add(new Option("Customer", "7"));
  customer.select.value = "7";
  const original = new Option("Original", "product:9");
  original.dataset = {price: "100000", kind: "product"};
  items.select.add(original);
  items.select.value = "product:9";
  const quantity = new Element();
  quantity.value = "2";
  const row = new Element();
  const remove = new Element();
  row.querySelector = selector => ({".item-select": items.select, ".quantity-input": quantity,
    ".remove-line": remove, "[data-lookup-widget]": items})[selector];
  const lines = new Element();
  lines.querySelectorAll = selector => selector === ".invoice-line" ? [row]
    : selector === ".item-select" ? [items.select] : [items];
  const form = new Element();
  form.dataset = {locale: "vi", currency: "VND", currencyPrecision: "0"};
  form.querySelectorAll = () => [items, customer];
  const estimate = new Element();
  const count = new Element();
  const feedback = new Element();
  const nodes = {"invoice-lines": lines, "line-template": new Element(), "add-item": new Element(),
    "line-count": count, estimate, "invoice-form": form, "invoice-form-feedback": feedback,
    "invoice-submit": new Element()};
  const timers = new Map();
  const requests = [];
  const window = new Element();
  const context = {
    document: {
      getElementById: id => nodes[id],
      querySelector: () => customer,
      createElement: () => ({children: [], append(child) { this.children.push(child); }}),
    },
    window, Option, AbortController, URLSearchParams, Event,
    setTimeout: callback => { const id = Symbol(); timers.set(id, callback); return id; },
    clearTimeout: id => timers.delete(id),
    fetch: (url, options) => new Promise(resolve => requests.push({url, options, resolve})),
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, "../../petcare/static/js/invoice.js"), "utf8"), context);
  return {items, customer, quantity, estimate, feedback, form, nodes, requests, window,
    input(value) { items.input.value = value; items.input.dispatchEvent({type: "input"}); },
    runTimers() { const callbacks = [...timers.values()]; timers.clear(); callbacks.forEach(callback => callback()); },
  };
}

const page = {page: 1, total: 1, has_next: false};
const payload = (name = "New") => ({products: [{id: 12, code: "P12", name, unit_price: "150000", stock_qty: 5}],
  pets: [], product_pagination: page, pet_pagination: {...page, total: 0}});
const settle = async () => { for (let i = 0; i < 8; i++) await Promise.resolve(); };

test("resetting lookup selection immediately recalculates the invoice total", () => {
  const h = harness();
  assert.match(h.estimate.textContent, /200\.000/);
  h.input("cat");
  assert.equal(h.items.select.value, "");
  assert.match(h.estimate.textContent, /^0\sVND$/);
});

test("aborts on the first keystroke and ignores an obsolete decoded response", async () => {
  const h = harness();
  h.input("old"); h.runTimers();
  let finishJson;
  h.requests[0].resolve({ok: true, json: () => new Promise(resolve => { finishJson = resolve; })});
  await settle();
  h.input("new");
  assert.equal(h.requests[0].options.signal.aborted, true);
  finishJson(payload("Obsolete"));
  await settle();
  assert.equal(h.items.select.options.length, 1);
  assert.equal(h.items.select.disabled, true);
  h.runTimers();
  h.requests[1].resolve({ok: true, json: async () => payload("Current")});
  await settle();
  assert.match(h.items.select.options[1].textContent, /Current/);
  assert.equal(h.items.select.disabled, false);
});

test("a result update refreshes totals and does not retain a stale estimate", async () => {
  const h = harness();
  h.input("cat"); h.runTimers();
  // Simulate an estimate from an earlier selection while the response is pending.
  h.estimate.textContent = "stale";
  h.requests[0].resolve({ok: true, json: async () => payload()});
  await settle();
  assert.match(h.estimate.textContent, /^0\sVND$/);
});

test("rapid input produces one request with the latest query", () => {
  const h = harness();
  h.input("a"); h.input("ab"); h.input("abc"); h.runTimers();
  assert.equal(h.requests.length, 1);
  assert.match(h.requests[0].url, /q=abc/);
});

test("loading another page does not duplicate a restored selection", async () => {
  const h = harness();
  h.items.dataset.productHasMore = "true";
  h.items.more.dispatchEvent({type: "click"});
  const result = payload();
  result.products.push({id: 9, code: "P9", name: "Restored", unit_price: "100000", stock_qty: 10});
  h.requests[0].resolve({ok: true, json: async () => result});
  await settle();
  assert.equal(h.items.select.options.filter(option => option.value === "product:9").length, 1);
  assert.equal(h.items.select.value, "product:9");
});

test("cannot submit while lookup fields are disabled", () => {
  const h = harness();
  h.items.select.disabled = true;
  let prevented = false;
  h.form.dispatchEvent({type: "submit", preventDefault() { prevented = true; }});
  assert.equal(prevented, true);
  assert.equal(h.feedback.hidden, false);
});

test("leaving the page cancels requests and scheduled searches", () => {
  const h = harness();
  h.input("old"); h.runTimers();
  h.window.dispatchEvent({type: "pagehide"});
  assert.equal(h.requests[0].options.signal.aborted, true);
  h.input("new");
  h.window.dispatchEvent({type: "pagehide"});
  h.runTimers();
  assert.equal(h.requests.length, 1);
});

test("server validation state survives initial invoice refresh", () => {
  const h = harness();
  h.items.select.dataset.serverError = "true";
  h.items.select.setAttribute("aria-invalid", "true");
  h.quantity.dataset.serverError = "true";
  h.quantity.value = "3";
  h.items.select.options[1].dataset.kind = "pet";
  h.nodes["invoice-lines"].dispatchEvent({type: "change"});
  assert.equal(h.items.select.getAttribute("aria-invalid"), "true");
  assert.equal(h.quantity.value, "3");
  assert.equal(h.quantity.readOnly, false);
});

test("form autofocus chooses the first invalid field, and corrections clear its error", () => {
  const listeners = {};
  const field = new Element(); field.id = "phone"; field.dataset.serverError = "true";
  field.setAttribute("aria-invalid", "true");
  const error = new Element();
  const summary = new Element(); summary.closest = () => ({querySelector: () => field});
  const document = {querySelector: () => summary, querySelectorAll: () => [],
    getElementById: id => id === "toast-region" ? null : error,
    addEventListener(type, handler, capture) { (listeners[type] ||= []).push({handler, capture}); }};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, "../../petcare/static/js/app.js"), "utf8"), {document, window: new Element()});
  assert.equal(field.focused, true);
  const validation = listeners.input.find(listener => listener.capture === true);
  validation.handler({target: field});
  assert.equal(field.getAttribute("aria-invalid"), undefined);
  assert.equal(error.hidden, true);
});
