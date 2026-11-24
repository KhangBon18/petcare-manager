const {test} = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const {Node, UIEvent, el} = require("./dom.cjs");

function runScript(script, root, extras = {}) {
  root.documentElement = {lang: "vi"};
  root.body = root;
  root.getElementById = id => root.querySelector(`#${id}`);
  root.createElement = tag => new Node(tag);
  Object.defineProperty(root, "activeElement", {get: () => Node.active, configurable: true});
  const timers = new Map();
  const timer = fn => { const id = Symbol(); timers.set(id, fn); return id; };
  const window = new Node();
  window.setTimeout = timer;
  window.confirm = () => true;
  window.location = {pathname: "/shop/checkout"};
  const context = {
    document: root,
    window,
    Element: Node,
    HTMLImageElement: Node,
    Event: UIEvent,
    clearTimeout: id => timers.delete(id),
    ...extras,
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, `../../petcare/static/js/${script}`), "utf8"), context);
  return {window, timers};
}

test("toast stacks sequential notices in-flow and Escape/close restores focus", () => {
  const region = el("div", {id: "toast-region"});
  const main = el("section", {id: "main-content"});
  const root = el("document", {}, [region, main]);
  const h = runScript("app.js", root);

  h.window.PetCare.toast("Đã lưu thay đổi", "success");
  h.window.PetCare.toast("Cần kiểm tra lại số điện thoại", "error");
  assert.equal(region.children.length, 2);

  const firstClose = region.children[0].querySelector(".toast-close");
  const secondClose = region.children[1].querySelector(".toast-close");
  assert.ok(firstClose && secondClose);
  firstClose.focus();
  firstClose.click();
  assert.equal(region.children.length, 1);
  assert.equal(Node.active, secondClose);

  root.dispatchEvent(new UIEvent("keydown", {key: "Escape"}));
  assert.equal(region.children.length, 0);
  assert.equal(Node.active, main);
});

test("storefront qty stepper clamps [min, max], pickup/COD toggles cleanly, and inline errors clear on input", () => {
  const stepMinus = el("button", {dataset: {sfQtyStep: "-1"}, attributes: {type: "button"}});
  const qtyInput = el("input", {id: "sf-prod-qty", value: "1", attributes: {type: "number", min: "1", max: "3"}});
  const stepPlus = el("button", {dataset: {sfQtyStep: "1"}, attributes: {type: "button"}});
  const stepper = el("div", {className: "sf-qty-stepper"}, [stepMinus, qtyInput, stepPlus]);

  const rPickup = el("input", {value: "pickup", checked: true, attributes: {type: "radio", name: "fulfillment_method"}});
  const rCod = el("input", {value: "cod_delivery", checked: false, attributes: {type: "radio", name: "fulfillment_method"}});
  const cardPickup = el("label", {className: "sf-check-inline sf-radio-card"}, [rPickup]);
  const cardCod = el("label", {className: "sf-check-inline sf-radio-card"}, [rCod]);
  const addrInput = el("input", {id: "checkout-address", value: ""});
  const addrGroup = el("div", {id: "checkout-address-group", hidden: true}, [addrInput]);
  const paymentLabel = el("div", {id: "checkout-payment-label", dataset: {storeText: "Tại quầy", codText: "COD khi nhận"}});

  const phoneErr = el("small", {className: "sf-field-error", hidden: false, textContent: "Số điện thoại chưa hợp lệ"});
  const phoneInp = el("input", {id: "checkout-phone", value: "123", attributes: {"aria-invalid": "true"}});
  const phoneField = el("div", {className: "sf-field sf-field-invalid"}, [phoneInp, phoneErr]);

  const submitBtn = el("button", {attributes: {type: "submit"}, textContent: "Đặt hàng ngay"});
  const checkoutForm = el("form", {dataset: {sfSubmitLock: "Đang gửi..."}}, [cardPickup, cardCod, addrGroup, paymentLabel, phoneField, submitBtn]);

  const root = el("document", {}, [stepper, checkoutForm]);
  const h = runScript("storefront.js", root);

  assert.equal(Node.active, phoneInp);
  assert.equal(cardPickup.classList.contains("is-selected"), true);
  assert.equal(cardCod.classList.contains("is-selected"), false);
  assert.equal(addrInput.disabled, true);
  assert.equal(paymentLabel.textContent, "Tại quầy");

  stepPlus.click(); stepPlus.click(); stepPlus.click();
  assert.equal(qtyInput.value, "3");
  stepMinus.click();
  assert.equal(qtyInput.value, "2");

  rPickup.checked = false; rCod.checked = true;
  rCod.dispatchEvent(new UIEvent("change"));
  assert.equal(cardPickup.classList.contains("is-selected"), false);
  assert.equal(cardCod.classList.contains("is-selected"), true);
  assert.equal(addrGroup.hidden, false);
  assert.equal(addrInput.required, true);
  assert.equal(addrInput.disabled, false);
  assert.equal(paymentLabel.textContent, "COD khi nhận");

  phoneInp.value = "0901234567";
  phoneInp.dispatchEvent(new UIEvent("input", {bubbles: true}));
  assert.equal(phoneInp.hasAttribute("aria-invalid"), false);
  assert.equal(phoneField.classList.contains("sf-field-invalid"), false);
  assert.equal(phoneErr.hidden, true);

  const sub1 = new UIEvent("submit", {target: checkoutForm, bubbles: true});
  checkoutForm.dispatchEvent(sub1);
  assert.equal(submitBtn.disabled, true);
  assert.equal(submitBtn.textContent, "Đang gửi...");
  const sub2 = new UIEvent("submit", {target: checkoutForm, bubbles: true});
  checkoutForm.dispatchEvent(sub2);
  assert.equal(sub2.defaultPrevented, true);

  h.window.dispatchEvent(new UIEvent("pageshow"));
  assert.equal(submitBtn.disabled, false);
  assert.equal(submitBtn.textContent, "Đặt hàng ngay");
});

test("storefront flash banner attaches close control and closes on click or Escape", () => {
  const flash = el("div", {className: "sf-flash sf-flash-success", dataset: {sfFlash: ""}}, [el("span", {textContent: "Đã thêm"})]);
  const main = el("main", {id: "sf-main-content"});
  const root = el("document", {}, [flash, main]);
  runScript("storefront.js", root);
  const closeBtn = flash.querySelector(".sf-flash-close");
  assert.ok(closeBtn);
  closeBtn.focus();
  root.dispatchEvent(new UIEvent("keydown", {key: "Escape"}));
  assert.equal(root.querySelectorAll("[data-sf-flash]").length, 0);
  assert.equal(Node.active, main);
});
