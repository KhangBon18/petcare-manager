const test = require("node:test");
const assert = require("node:assert/strict");
const vm = require("node:vm");
const fs = require("node:fs");
const {Node, UIEvent, el} = require("./dom.cjs");
const script = fs.readFileSync("petcare/static/js/motion.js", "utf8");

function harness({reduced = false, library = true, webkit = false, error = false, cards = 0, bars = 0} = {}) {
  const root = el("document");
  const heading = el("h1", {className:"page-heading", textContent:"2.250.000 VND"});
  const input = el("input", {value:"2"});
  root.append(heading, input);
  for (let i = 0; i < cards; i++) root.append(el("article", {className:"stat-card"}));
  for (let i = 0; i < bars; i++) root.append(el("rect", {className:"revenue-bar"}));
  if (error) root.append(el("p", {dataset:{errorSummary:""}}));
  const query = Node.prototype.querySelectorAll;
  root.querySelectorAll = selector => [...new Set(selector.split(",").flatMap(s => query.call(root, s.trim())))];
  const nodes = [root, ...query.call(root, "h1"), input, ...query.call(root, "article"), ...query.call(root, "rect")];
  nodes.forEach(node => {
    node.isConnected = true; node.getBoundingClientRect = () => ({width:100,height:40,top:30,bottom:70});
    const attribute = node.getAttribute.bind(node); node.getAttribute = name => attribute(name) ?? null;
    node.hasAttribute = name => node.getAttribute(name) !== null;
  });
  root.documentElement = el("html"); root.hidden = false; input.focus();
  root.removeEventListener = (type, fn) => { root.listeners[type] = (root.listeners[type] || []).filter(item => item !== fn); };
  const window = new Node("window"); window.innerHeight = 800;
  const animations = []; const registrations = [];
  const make = (list, from, vars) => {
    const item = {list,from,vars,restored:false,revert() { this.restored = true; }};
    animations.push(item); return item;
  };
  const engine = {
    fromTo: make,
    timeline(vars) {
      const item = make([], {}, vars); item.steps = [];
      item.fromTo = (list, from, to, at) => { item.steps.push({list,from,to,at}); return item; };
      item.duration = () => item.steps.length ? 0.8 : 0;
      return item;
    },
    matchMedia() {
      const mm = {add(query, callback) { assert.match(query,/prefers-reduced-motion/); if (!reduced) this.cleanup = callback({ignore: fn => fn()}); },
        revert() { this.cleanup?.(); this.cleanup = null; }};
      registrations.push(mm); return mm;
    },
  };
  if (library) window.gsap = engine;
  vm.runInNewContext(script, {window,document:root,navigator:{vendor:webkit ? "Apple Computer, Inc." : "Google Inc."},Set,WeakMap,Map});
  return {root,window,heading,input,animations,registrations, motion:window.PetCare?.motion,
    event(name, args = {}) { window.dispatchEvent(new UIEvent(name,args)); }};
}

test("missing GSAP leaves HTML, focus, values and application namespace usable", () => {
  const h = harness({library:false});
  assert.equal(h.animations.length,0); assert.equal(h.root.documentElement.className,"");
  assert.equal(h.heading.textContent,"2.250.000 VND"); assert.equal(h.input.value,"2");
  assert.equal(Node.active,h.input);
});

test("Safari/WebKit skips CSP-blocked inline motion without changing content or focus", () => {
  const h = harness({webkit:true});
  assert.equal(h.animations.length,0);
  assert.equal(h.heading.textContent,"2.250.000 VND");
  assert.equal(h.input.value,"2");
  assert.equal(Node.active,h.input);
});

test("reduced motion has no entrance, feedback or delayed form interaction", () => {
  const h = harness({reduced:true});
  h.motion.reveal([h.heading]); h.motion.feedback([h.heading]);
  assert.equal(h.animations.length,0); assert.equal(Node.active,h.input);
  assert.equal(h.input.value,"2"); assert.equal(h.root.documentElement.className,"");
});

test("entrance bounds card work and chart stagger, never tweens business values", () => {
  const h = harness({cards:70,bars:366});
  const entrance = h.animations[0];
  assert.equal(entrance.steps.find(step => step.list[0]?.className === "stat-card").list.length,12);
  const chart = entrance.steps.find(step => step.list[0]?.className === "revenue-bar");
  assert.equal(chart.list.length,60); assert.ok(chart.to.stagger.amount <= 0.3);
  for (const step of entrance.steps) {
    assert.equal(step.from.textContent,undefined); assert.equal(step.to.value,undefined);
    assert.equal(step.to.width,undefined); assert.equal(step.to.height,undefined);
    assert.equal(step.from.opacity,undefined); assert.equal(step.to.opacity,undefined);
  }
  assert.equal(h.heading.textContent,"2.250.000 VND"); assert.equal(Node.active,h.input);
  entrance.vars.onComplete(); assert.equal(entrance.restored,true);
});

test("content reveal preserves full text contrast while moving into place", () => {
  const h = harness({error:true});
  h.motion.reveal([h.heading]);
  const animation = h.animations[0];
  assert.equal(animation.from.opacity,undefined);
  assert.equal(animation.vars.opacity,undefined);
  assert.equal(animation.from.y,8);
  assert.equal(animation.vars.y,0);
});

test("server-validation page does not move the focused form or its heading", () => {
  const h = harness({error:true});
  assert.equal(h.animations.length,0); assert.equal(Node.active,h.input);
});

test("rapid feedback reverts previous tween and excludes hidden or detached targets", () => {
  const h = harness({error:true});
  h.motion.feedback([h.heading]); const first = h.animations.at(-1);
  h.motion.feedback([h.heading]); assert.equal(first.restored,true);
  const last = h.animations.at(-1); last.vars.onComplete(); assert.equal(last.restored,true);
  const hidden = el("div", {hidden:true,attributes:{hidden:""}}); hidden.append(h.heading);
  const count = h.animations.length; h.motion.reveal([h.heading]); assert.equal(h.animations.length,count);
  assert.equal(Node.active,h.input); assert.equal(h.input.value,"2");
});

test("print and BFCache cleanup finish animations, restore SVG attributes and do not replay entrance", () => {
  const h = harness({bars:3});
  const bars = h.root.querySelectorAll(".revenue-bar");
  bars.forEach(node => { node.setAttribute("transform","matrix(1,0,0,1,0,0)"); node.setAttribute("style","transform-origin:0 0"); });
  h.event("beforeprint");
  assert.ok(h.animations.every(a => a.restored)); assert.equal(h.root.documentElement.className,"");
  bars.forEach(node => { assert.equal(node.getAttribute("transform"),null); assert.equal(node.getAttribute("style"),null); });
  const count = h.animations.length; h.event("afterprint"); assert.equal(h.animations.length,count);
  h.motion.feedback([h.heading]); h.event("pagehide"); assert.ok(h.animations.at(-1).restored);
  h.event("pageshow",{persisted:true}); assert.equal(h.registrations.length,3);
  assert.equal(h.root.listeners.visibilitychange.length,1);
});

test("live preference cleanup and backgrounding restore styles without changing data", () => {
  const h = harness({error:true});
  h.motion.reveal([h.heading]); h.root.hidden = true;
  h.root.dispatchEvent(new UIEvent("visibilitychange")); assert.ok(h.animations.at(-1).restored);
  const count = h.animations.length; h.motion.feedback([h.heading]); assert.equal(h.animations.length,count);
  h.root.hidden = false; h.registrations[0].revert();
  h.motion.reveal([h.heading]); assert.equal(h.animations.length,count);
  assert.equal(h.root.listeners.visibilitychange.length,0); assert.equal(Node.active,h.input);
});
