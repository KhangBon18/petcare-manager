// Minimal DOM boundary for state/async UI tests; visual layout is checked in-browser.
class Node {
  constructor(tag = "div") {
    this.tagName = tag; this.children = []; this.dataset = {}; this.attributes = {};
    this.listeners = {}; this.hidden = false; this.disabled = false; this.value = "";
    this.textContent = ""; this.className = "";
    this.classList = {
      contains: name => this.className.split(" ").includes(name),
      add: name => { if (!this.classList.contains(name)) this.className += ` ${name}`; },
      remove: name => { this.className = this.className.split(" ").filter(n => n !== name).join(" "); },
      toggle: (name, yes) => yes ? this.classList.add(name) : this.classList.remove(name),
    };
  }
  append(...nodes) { for (const node of nodes) { node.parent = this; this.children.push(node); } }
  replaceChildren(...nodes) { this.children = []; this.append(...nodes); }
  remove() { if (this.parent) this.parent.children = this.parent.children.filter(n => n !== this); }
  get lastElementChild() { return this.children.at(-1); }
  get options() { return this.children.filter(node => node.tagName === "option"); }
  get selectedOptions() { return this.options.filter(node => node.value === this.value); }
  add(option) { this.append(option); }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  getAttribute(name) {
    if (name === "id") return this.id;
    if (name.startsWith("data-")) return this.dataset[name.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase())];
    return this.attributes[name];
  }
  removeAttribute(name) { delete this.attributes[name]; }
  hasAttribute(name) { return this.getAttribute(name) !== undefined; }
  matches(selector) {
    const descendant = selector.match(/^(\.[\w-]+) (\w+)$/);
    if (descendant) return this.tagName === descendant[2] && Boolean(this.parent?.closest(descendant[1]));
    const combined = selector.match(/^(\w+)(\[.*\])$/);
    if (combined) return this.tagName === combined[1] && this.matches(combined[2]);
    const attributes = selector.match(/\[[^\]]+\]/g);
    if (attributes?.length > 1) return attributes.every(attribute => this.matches(attribute));
    if (selector.startsWith(".")) return this.classList.contains(selector.slice(1));
    if (selector.startsWith("#")) return this.id === selector.slice(1);
    const attribute = selector.match(/^\[([^=\]]+)(?:=['"]([^'"]*)['"])?\]$/);
    if (attribute) return attribute[2] === undefined ? this.hasAttribute(attribute[1]) : this.getAttribute(attribute[1]) === attribute[2];
    return this.tagName === selector;
  }
  querySelectorAll(selector) {
    return this.children.flatMap(child => [child, ...child.querySelectorAll(selector)]).filter(node => node.matches(selector));
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  closest(selector) { return this.matches(selector) ? this : this.parent?.closest(selector); }
  contains(node) { for (let current = node; current; current = current.parent) if (current === this) return true; return false; }
  requestSubmit() { this.dispatchEvent(new UIEvent("submit", {bubbles: true})); }
  addEventListener(type, callback) { (this.listeners[type] ||= []).push(callback); }
  dispatchEvent(event) {
    if (!event.target) event.target = this;
    for (const callback of this.listeners[event.type] || []) callback(event);
    if (event.bubbles && this.parent) this.parent.dispatchEvent(event);
  }
  click() { if (!this.disabled) this.dispatchEvent(new UIEvent("click", {bubbles: true})); }
  focus() { Node.active = this; }
  showModal() { this.open = true; }
  close() { this.open = false; this.dispatchEvent(new UIEvent("close")); }
  reset() { this.querySelectorAll("input").forEach(node => { node.value = ""; }); }
}
class UIEvent {
  constructor(type, options = {}) { this.type = type; Object.assign(this, options); }
  preventDefault() { this.defaultPrevented = true; }
}
function el(tag, data = {}, children = []) {
  const node = new Node(tag); Object.assign(node, data); node.append(...children); return node;
}
function deferred() { let resolve; const promise = new Promise(r => { resolve = r; }); return {promise, resolve}; }
async function settle() { for (let i = 0; i < 10; i++) await Promise.resolve(); }
module.exports = {Node, UIEvent, el, deferred, settle};
