const {test} = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const {Node, UIEvent, el, deferred, settle} = require("./dom.cjs");

function harness() {
  const root = new Node();
  const lines = el("div", {id: "invoice-lines"});
  const results = el("div", {dataset: {posResults: ""}});
  function card(kind, id, stock) {
    return el("button", {dataset: {posItem: "", selection: `${kind}:${id}`, kind,
      name: kind, code: String(id), price: "100000", stock: String(stock), photo: ""}},
      [el("span", {dataset: {posAction: ""}})]);
  }
  const product = card("product", 9, 3); const pet = card("pet", 11, 1);
  results.append(product, pet);
  const search = el("input", {dataset: {posSearch: "", source: "/lookups/items"}});
  const more = el("button", {dataset: {posMore: "", productHasMore: "false", petHasMore: "false", productPage: "1", petPage: "1"}});
  const add = el("button", {id: "add-item"});
  const submit = el("button", {id: "invoice-submit"});
  const estimate = el("strong", {id: "estimate"});
  const mobileCount = el("span", {dataset: {posMobileCount: ""}});
  const mobileTotal = el("strong", {dataset: {posMobileTotal: ""}});
  const mobileCart = el("a", {dataset: {posMobileCart: ""}}, [mobileCount, mobileTotal]);
  const retry = el("button", {dataset: {posRetry: ""}, hidden: true});
  const open = el("button", {dataset: {quickCustomerOpen: ""}});
  const customer = el("select", {id: "customer_id"});
  const customerWidget = el("div", {dataset: {lookupWidget: ""}}, [customer]);
  const form = el("form", {dataset: {pos: "true", locale: "vi"}, invoiceUI: {
    formatMoney: value => `${value} VND`, refresh() {
      const total = [...lines.querySelectorAll(".invoice-line")].reduce((sum, row) => {
        const option = row.querySelector(".item-select").selectedOptions[0];
        return sum + (option ? Number(option.dataset.price) * Number(row.querySelector(".quantity-input").value) : 0);
      }, 0);
      estimate.textContent = `${total} VND`;
    },
  }}, [results, search, more, retry, lines, add, submit, estimate, mobileCart, open, customerWidget,
     el("p", {dataset: {posStatus: ""}}), el("div", {dataset: {posSkeleton: ""}}),
     el("div", {dataset: {posEmpty: ""}}), el("div", {dataset: {cartEmpty: ""}})]);
  const fields = ["full_name", "phone", "address"].map(name => el("input", {attributes: {name}}));
  const save = el("button", {attributes: {type: "submit"}, textContent: "Save"});
  const quick = el("form", {id: "quick-customer-form", action: "/customers/quick",
    elements: {namedItem: name => fields.find(field => field.attributes.name === name)}},
    [...fields, save, el("p", {dataset: {quickError: ""}}), el("button", {dataset: {quickCustomerClose: ""}})]);
  const dialog = el("dialog", {id: "quick-customer-dialog"}, [quick]);
  root.append(form, dialog);
  add.addEventListener("click", () => {
    const select = el("select", {className: "item-select"});
    const info = el("div", {dataset: {cartInfo: ""}}, [
      el("span", {dataset: {cartName: ""}}), el("small", {dataset: {cartDetail: ""}}),
      el("span", {dataset: {cartImage: ""}})]);
    lines.append(el("div", {className: "invoice-line"}, [select, info, el("input", {className: "quantity-input", value: "1"})]));
  });
  const requests = [], timers = new Map();
  class FakeOption extends Node { constructor(text, value) { super("option"); this.textContent = text; this.value = value; } }
  class FormData {
    *[Symbol.iterator]() { for (const field of fields) yield [field.attributes.name, field.value]; yield ["csrf_token", "token"]; }
  }
  const window = new Node();
  window.PetCare = {icon: () => null};
  const context = {
    document: {querySelector: selector => root.querySelector(selector), getElementById: id => root.querySelector(`#${id}`),
      createElement: tag => new Node(tag), createTextNode: text => el("text", {textContent: text})},
    window, Event: UIEvent, Option: FakeOption, FormData, AbortController, URLSearchParams,
    setTimeout: fn => { const id = Symbol(); timers.set(id, fn); return id; }, clearTimeout: id => timers.delete(id),
    fetch: (url, options) => { const d = deferred(); requests.push({url, options, ...d}); return d.promise; },
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, "../../petcare/static/js/pos.js"), "utf8"), context);
  return {form, lines, results, product, pet, open, dialog, quick, fields, save, requests, search, customer, retry,
    mobileCount, mobileTotal,
    timers() { const all = [...timers.values()]; timers.clear(); all.forEach(fn => fn()); }};
}

test("POS increases products only to stock and allows one row for each pet", () => {
  const h = harness();
  for (let i = 0; i < 5; i++) h.product.click();
  h.pet.click(); h.pet.click();
  const rows = h.lines.querySelectorAll(".invoice-line");
  assert.equal(rows.length, 2);
  assert.equal(rows[0].querySelector(".quantity-input").value, "3");
  assert.equal(rows[1].querySelector(".quantity-input").value, "1");
  assert.equal(h.product.disabled, true); assert.equal(h.pet.disabled, true);
});

test("mobile cart preview follows selected quantities and server-formatted estimate", () => {
  const h = harness();
  h.product.click(); h.product.click(); h.pet.click();
  assert.equal(h.mobileCount.textContent, "3 mặt hàng trong đơn");
  assert.equal(h.mobileTotal.textContent, "300000 VND");
});

test("catalog search preserves the cart and aborts on a new keystroke", async () => {
  const h = harness(); h.product.click();
  h.search.value = "old"; h.search.dispatchEvent(new UIEvent("input")); h.timers();
  h.search.value = "new"; h.search.dispatchEvent(new UIEvent("input"));
  assert.equal(h.requests[0].options.signal.aborted, true);
  h.requests[0].resolve({ok: true, json: async () => ({products: [], pets: [], product_pagination: {}, pet_pagination: {}})});
  await settle();
  assert.equal(h.lines.querySelectorAll(".invoice-line").length, 1);
  assert.equal(h.product.parent.children.includes(h.product), true);
});

test("catalog failure exposes a retry action and recovers without losing the cart", async () => {
  const h = harness(); h.product.click();
  h.search.value = "food"; h.search.dispatchEvent(new UIEvent("input")); h.timers();
  assert.equal(h.form.querySelector("[data-pos-skeleton]").hidden, false);
  assert.equal(h.results.hidden, true);
  h.requests[0].resolve({ok: false, json: async () => ({})});
  await settle();
  assert.equal(h.retry.hidden, false);
  assert.match(h.form.querySelector("[data-pos-status]").textContent, /Không tải được danh mục/);
  assert.equal(h.lines.querySelectorAll(".invoice-line").length, 1);
  h.retry.click();
  assert.equal(h.retry.hidden, true);
  assert.equal(h.requests.length, 2);
  h.requests[1].resolve({ok: true, json: async () => ({products: [], pets: [], product_pagination: {}, pet_pagination: {}})});
  await settle();
  assert.equal(h.retry.hidden, true);
  assert.equal(h.lines.querySelectorAll(".invoice-line").length, 1);
});

test("quick customer locks duplicate submits, selects the saved customer and keeps the cart", async () => {
  const h = harness(); h.product.click(); h.pet.click(); h.open.click();
  h.fields[0].value = "New customer"; h.fields[1].value = "0901234567";
  h.quick.dispatchEvent(new UIEvent("submit")); h.quick.dispatchEvent(new UIEvent("submit"));
  assert.equal(h.requests.length, 1); assert.equal(h.save.disabled, true);
  h.requests[0].resolve({ok: true, json: async () => ({customer: {id: 77, full_name: "New customer", phone: "0901234567"}})});
  await settle();
  assert.equal(h.customer.value, "77"); assert.equal(h.dialog.open, false);
  assert.equal(h.lines.querySelectorAll(".invoice-line").length, 2);
  assert.equal(h.save.disabled, false);
});
