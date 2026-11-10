const {test} = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const {Node, UIEvent, el, deferred, settle} = require("./dom.cjs");

function run(script, root, extras = {}) {
  root.documentElement = {lang: "vi"};
  root.body = root;
  root.getElementById = id => root.querySelector(`#${id}`);
  root.createElement = tag => new Node(tag);
  Object.defineProperty(root, "activeElement", {get: () => Node.active});
  const timers = new Map(), requests = [];
  const timer = fn => { const id = Symbol(); timers.set(id, fn); return id; };
  const window = new Node(); window.setTimeout = timer; window.confirm = () => true;
  const context = {document: root, window, Element: Node, AbortController,
    clearTimeout: id => timers.delete(id),
    fetch: (url, options) => { const d = deferred(); requests.push({url, options, ...d}); return d.promise; }, ...extras};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, `../../petcare/static/js/${script}`), "utf8"), context);
  return {window, requests, timers, tick() { const callbacks = [...timers.values()]; timers.clear(); callbacks.forEach(fn => fn()); }};
}

test("image/export POST locks only once and recovers on browser back", () => {
  const button = el("button", {attributes: {type: "submit"}, textContent: "Export"});
  const form = el("form", {dataset: {submitLock: "", submitLabel: "Working"}}, [button]);
  const root = el("document", {}, [form]); const h = run("app.js", root);
  const event = () => new UIEvent("submit", {target: form, submitter: button, bubbles: true});
  const first = event(); form.dispatchEvent(first);
  assert.equal(button.disabled, true); assert.equal(button.textContent, "Working");
  const second = event(); form.dispatchEvent(second); assert.equal(second.defaultPrevented, true);
  h.window.dispatchEvent(new UIEvent("pageshow"));
  assert.equal(button.disabled, false); assert.equal(button.textContent, "Export");
  assert.equal(form.getAttribute("aria-busy"), "false");
});

test("assistant blocks duplicate requests and Escape restores focus without stealing it on reply", async () => {
  const launcher = el("button", {id: "assistant-launcher"});
  const input = el("input", {id: "assistant-input", value: "Hôm nay còn mèo nào?"});
  const send = el("button", {attributes: {type: "submit"}});
  const form = el("form", {id: "assistant-form", action: "/assistant/chat"},
    [input, send, el("input", {attributes: {name: "csrf_token"}, value: "token"})]);
  const messages = el("div", {id: "assistant-messages"});
  const panel = el("aside", {id: "assistant-panel", hidden: true},
    [form, messages, el("button", {id: "assistant-close"}), el("button", {id: "assistant-clear"})]);
  const root = el("document", {}, [launcher, panel]); const h = run("assistant.js", root);
  launcher.focus(); launcher.click(); assert.equal(Node.active, input);
  form.dispatchEvent(new UIEvent("submit"));
  input.value = "Another question"; form.dispatchEvent(new UIEvent("submit"));
  assert.equal(h.requests.length, 1); assert.equal(send.disabled, true);
  root.dispatchEvent(new UIEvent("keydown", {key: "Escape"}));
  assert.equal(panel.hidden, true); assert.equal(Node.active, launcher);
  h.requests[0].resolve({ok: true, json: async () => ({reply: "Miu", mode: "local"})});
  await settle();
  assert.equal(send.disabled, false); assert.equal(Node.active, launcher);
});

test("export polling exposes the download once ready and stops scheduling", async () => {
  const root = el("document");
  const job = el("div", {dataset: {exportJob: "", poll: "true", statusUrl: "/exports/1"}});
  const download = el("a", {id: "export-download", hidden: true});
  const indicator = el("span", {dataset: {exportIndicator: ""}});
  root.append(job, download, indicator, el("p", {id: "export-job-message"}));
  const h = run("export-job.js", root); h.tick();
  assert.equal(h.requests.length, 1); assert.equal(job.getAttribute("aria-busy"), "true");
  h.requests[0].resolve({ok: true, json: async () => ({status: "ready", download_url: "/download/1"})});
  await settle();
  assert.equal(download.hidden, false); assert.equal(download.href, "/download/1");
  assert.equal(indicator.hidden, true); assert.equal(h.timers.size, 0);
});


test("assistant renders safe actionable catalog cards in local and AI replies", async () => {
  for (const mode of ["local", "ai"]) {
    const launcher = el("button", {id:"assistant-launcher"});
    const input = el("input", {id:"assistant-input", value:"mèo trắng"});
    const form = el("form", {id:"assistant-form", action:"/assistant/chat"},
      [input, el("button", {attributes:{type:"submit"}})]);
    const messages = el("div", {id:"assistant-messages"});
    const root = el("document", {}, [launcher, el("aside", {id:"assistant-panel",hidden:true}, [form,messages])]);
    const h = run("assistant.js", root); launcher.click(); form.dispatchEvent(new UIEvent("submit"));
    h.requests[0].resolve({ok:true,json:async()=>({reply:"One result",mode,catalog:{total:2,items:[
      {name:"<script>bad()</script>",code:"PET1",url:"/pets/1",photo_url:"/pets/photo/safe.jpg",status_label:"Đang bán",price_label:"10 VND",stock:1},
      {name:"Bad URL",url:"javascript:bad()",photo_url:"https://external.test/photo.jpg"}]}})});
    await settle();
    const cards=messages.querySelectorAll(".assistant-result-card"); assert.equal(cards.length,1);
    assert.equal(cards[0].querySelector("strong").textContent,"<script>bad()</script>");
    assert.equal(cards[0].querySelector("a").href,"/pets/1");
    assert.equal(cards[0].querySelector("img").src,"/pets/photo/safe.jpg");
  }
});

test("assistant renders top-product report facts as safe text with an allowlisted record link", async () => {
  const launcher = el("button", {id:"assistant-launcher"});
  const input = el("input", {id:"assistant-input", value:"Top products this week"});
  const form = el("form", {id:"assistant-form", action:"/assistant/chat"},
    [input, el("button", {attributes:{type:"submit"}})]);
  const messages = el("div", {id:"assistant-messages"});
  const root = el("document", {}, [launcher, el("aside", {id:"assistant-panel",hidden:true}, [form,messages])]);
  const h = run("assistant.js", root); h.window.PetCare = {icon: () => el("span")};
  launcher.click(); form.dispatchEvent(new UIEvent("submit"));
  h.requests[0].resolve({ok:true,json:async()=>({
    reply:"Top products for this week.", mode:"local",
    insight:{kind:"top_products",period:"week",start_date:"2026-11-09",end_date:"2026-11-10",items:[
      {name:"<img src=x onerror=bad()>",code:"QA-1",quantity_sold:3,revenue_label:"30,000 VND",url:"/products/23"},
      {name:"Untrusted URL",code:"QA-2",quantity_sold:2,revenue_label:"20,000 VND",url:"//evil.test/products/24"}
    ]}
  })});
  await settle();
  const cards=messages.querySelectorAll(".assistant-result-card"); assert.equal(cards.length,1);
  assert.equal(cards[0].querySelector("strong").textContent,"<img src=x onerror=bad()>");
  assert.equal(cards[0].querySelector("small").textContent,"QA-1 · 3 sản phẩm bán ròng");
  assert.equal(cards[0].querySelector("b").textContent,"30,000 VND");
  assert.equal(cards[0].querySelector("a").href,"/products/23");
  assert.match(messages.querySelector(".assistant-message-source").textContent,/Báo cáo bán hàng/);
});

test("assistant renders inventory and purchasing insights with safe text and same-origin links", async () => {
  const fixtures = [
    {
      prompt: "Gợi ý nhập hàng", kind: "inventory_restock", url: "/products/23",
      item: {product_id:23,name:"<img src=x onerror=bad()>",code:"QA-1",stock_qty:2,reorder_level:3,suggested_qty:9,days_left:"4.0",url:"/products/23"},
      source: /Service tồn kho chỉ đọc/,
    },
    {
      prompt: "Tình trạng đơn nhập?", kind: "purchase_status", url: "/purchasing/52",
      item: {purchase_order_id:52,supplier_name:"<script>bad()</script>",status:"partially_received",received_units:2,ordered_units:5,created_at:"2026-11-10 08:30",amount_label:"12.000 VND",url:"/purchasing/52"},
      source: /Service nhập hàng dành cho quản trị viên/,
    },
  ];
  for (const fixture of fixtures) {
    const launcher = el("button", {id:"assistant-launcher"});
    const input = el("input", {id:"assistant-input", value:fixture.prompt});
    const form = el("form", {id:"assistant-form", action:"/assistant/chat"}, [input,el("button",{attributes:{type:"submit"}})]);
    const messages = el("div", {id:"assistant-messages"});
    const root = el("document", {}, [launcher,el("aside",{id:"assistant-panel",hidden:true},[form,messages])]);
    const h = run("assistant.js",root); h.window.PetCare = {icon: () => el("span")};
    launcher.click(); form.dispatchEvent(new UIEvent("submit"));
    h.requests[0].resolve({ok:true,json:async()=>({reply:"Verified facts",mode:"local",insight:{kind:fixture.kind,total:1,target_days:14,status_counts:{ordered:0,partially_received:1,received:0,cancelled:0},items:[{...fixture.item,url:fixture.url}]}})});
    await settle();
    const card=messages.querySelector(".assistant-result-card");
    assert.ok(card);
    assert.equal(card.querySelector("strong").textContent,fixture.item.name || `Đơn #${fixture.item.purchase_order_id} · ${fixture.item.supplier_name}`);
    assert.equal(card.querySelector("a").href,fixture.url);
    assert.match(messages.querySelector(".assistant-message-source").textContent,fixture.source);
    assert.equal(messages.querySelectorAll("script").length,0);
  }
});

test("assistant exposes a keyboard-accessible retry action after a failed request", async () => {
  const launcher=el("button",{id:"assistant-launcher"});
  const input=el("input",{id:"assistant-input",value:"Restock suggestions"});
  const form=el("form",{id:"assistant-form",action:"/assistant/chat"},[input,el("button",{attributes:{type:"submit"}})]);
  const messages=el("div",{id:"assistant-messages"});
  const root=el("document",{},[launcher,el("aside",{id:"assistant-panel",hidden:true},[form,messages])]);
  const h=run("assistant.js",root);launcher.click();form.dispatchEvent(new UIEvent("submit"));
  h.requests[0].resolve({ok:false,json:async()=>({error:"Temporary failure"})});await settle();
  const retry=messages.querySelector("[data-assistant-retry]");
  assert.ok(retry);assert.equal(retry.textContent,"Thử lại");assert.equal(retry.dataset.message,"Restock suggestions");
  retry.click();assert.equal(h.requests.length,2);assert.equal(JSON.parse(h.requests[1].options.body).message,"Restock suggestions");
});

test("report export blocks duplicate clicks and unlocks after a failed network response", async () => {
  const button=el("button",{attributes:{type:"submit"},textContent:"Xuất Excel"});
  const form=el("form",{dataset:{reportExport:""},action:"/reports/export.xlsx"},[
    el("input",{attributes:{name:"csrf_token"},value:"token"}),el("input",{attributes:{name:"snapshot"},value:"signed"}),button]);
  class FormDataMock {constructor(node){this.node=node;} get(name){return this.node.querySelector(`[name="${name}"]`).value;}}
  const h=run("reports.js",el("document",{},[form]),{FormData:FormDataMock});
  const notices=[];h.window.PetCare={toast:(...args)=>notices.push(args)};
  form.dispatchEvent(new UIEvent("submit"));form.dispatchEvent(new UIEvent("submit"));
  assert.equal(h.requests.length,1);assert.equal(button.disabled,true);
  assert.equal(JSON.parse(h.requests[0].options.body).snapshot,"signed");
  h.requests[0].resolve({ok:false,json:async()=>({error:"Snapshot expired"})});await settle();
  assert.equal(button.disabled,false);assert.equal(button.textContent,"Xuất Excel");
  assert.equal(form.getAttribute("aria-busy"),"false");assert.deepEqual(notices,[["Snapshot expired","error"]]);
});

test("photo suggestions discard stale replies and preserve manually entered attributes", async () => {
  const input=el("input",{dataset:{suggestUrl:"/pets/suggest-attributes"},files:[{size:10}]});
  const species=el("input",{value:"Chó đã nhập"}),coat=el("input",{value:""});
  const apply=el("button",{dataset:{attributeApply:""},hidden:true});
  const retry=el("button",{dataset:{attributeRetry:""},hidden:true});
  const cancel=el("button",{dataset:{attributeCancel:""},hidden:true});
  const dismiss=el("button",{dataset:{attributeDismiss:""},hidden:true});
  const status=el("p",{dataset:{attributeStatus:""}}),values=el("div",{dataset:{attributeValues:""}});
  const panel=el("section",{dataset:{attributePanel:""}},[status,values,apply,retry,cancel,dismiss]);
  const form=el("form",{elements:{namedItem:name=>({species,coat_color:coat}[name])}},[
    input,panel,el("input",{attributes:{name:"csrf_token"},value:"token"})]);
  class FormDataMock {append(){}}
  const h=run("pet_attributes.js",el("document",{},[form]),{FormData:FormDataMock,Event:UIEvent});
  input.dispatchEvent(new UIEvent("change"));input.dispatchEvent(new UIEvent("change"));
  assert.equal(h.requests[0].options.signal.aborted,true);
  h.requests[1].resolve({ok:true,json:async()=>({mode:"local",suggestions:{species:"Mèo",coat_color:"trắng"}})});await settle();
  h.requests[0].resolve({ok:true,json:async()=>({mode:"vision",suggestions:{coat_color:"đen"}})});await settle();
  assert.match(status.textContent,/cục bộ/);
  apply.click();assert.equal(species.value,"Chó đã nhập");assert.equal(coat.value,"trắng");
  assert.equal(panel.getAttribute("aria-busy"),"false");assert.match(status.textContent,/điền/);
});


test("printing opens report details and restores their previous state afterwards", () => {
  const closed=el("details",{open:false}),opened=el("details",{open:true});
  const root=el("document",{},[el("div",{className:"report-document"},[closed,opened])]);
  const h=run("reports.js",root);
  h.window.dispatchEvent(new UIEvent("beforeprint"));assert.equal(closed.open,true);assert.equal(opened.open,true);
  h.window.dispatchEvent(new UIEvent("beforeprint"));
  h.window.dispatchEvent(new UIEvent("afterprint"));assert.equal(closed.open,false);assert.equal(opened.open,true);
});
