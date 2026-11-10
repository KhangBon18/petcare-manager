const {test} = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const {Node, el} = require("./dom.cjs");

function receiveHarness() {
  const receiveForm = el("form", {dataset: {purchaseReceiveForm: ""}});
  const fill = el("button", {dataset: {fillRemaining: ""}});
  const feedback = el("p", {dataset: {receiveFeedback: ""}});
  const first = el("input", {attributes: {name: "quantity[]"}, value: "0", max: "4", disabled: false});
  const zeroRemaining = el("input", {attributes: {name: "quantity[]"}, value: "0", max: "0", disabled: false});
  const completed = el("input", {attributes: {name: "quantity[]"}, value: "0", max: "0", disabled: true});
  receiveForm.append(first, zeroRemaining, completed, fill, feedback);
  const context = {
    document: {
      querySelector: selector => selector === "[data-purchase-receive-form]" ? receiveForm : null,
      documentElement: {lang: "vi"},
    },
  };
  vm.runInNewContext(
    fs.readFileSync(path.join(__dirname, "../../petcare/static/js/purchasing.js"), "utf8"),
    context,
  );
  return {fill, feedback, first, zeroRemaining, completed};
}

test("fill remaining populates eligible order lines and announces the total before confirmation", () => {
  const h = receiveHarness();
  h.fill.click();
  assert.equal(h.first.value, "4");
  assert.equal(h.zeroRemaining.value, "0");
  assert.equal(h.completed.value, "0");
  assert.equal(h.feedback.textContent, "Đã điền 4 đơn vị còn thiếu. Hãy kiểm tra trước khi xác nhận.");
});
