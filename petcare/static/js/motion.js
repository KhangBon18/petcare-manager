/* Optional presentation layer: content and business actions never wait for motion. */
(() => {
  const engine = window.gsap;
  if (!engine?.matchMedia || !engine?.timeline) return;
  const root = document.documentElement;
  const noop = () => {};
  const api = {reveal: noop, feedback: noop};
  window.PetCare = {...window.PetCare, motion: api};
  let media = null;
  let entered = false;

  function mount() {
    if (media) return;
    media = engine.matchMedia();
    media.add("screen and (prefers-reduced-motion: no-preference)", context => {
      const active = new Set();
      const owners = new WeakMap();
      const svgOriginals = new Map();
      const visible = node => {
        if (!node?.isConnected || node.closest("[hidden]")) return false;
        const box = node.getBoundingClientRect();
        return box.width > 0 && box.height > 0 && box.top < window.innerHeight && box.bottom > 0;
      };
      const targets = nodes => Array.from(nodes || []).filter(visible).slice(0, 12);
      function restore(animation) {
        active.delete(animation);
        // Revert original styles/attributes instead of leaving stale transforms.
        animation.revert();
        // SVG CSSPlugin initializes an identity matrix even when reverting.
        (svgOriginals.get(animation) || []).forEach(([node, attributes]) => {
          attributes.forEach(([name, value]) => {
            if (value === null) node.removeAttribute(name);
            else node.setAttribute(name, value);
          });
        });
        svgOriginals.delete(animation);
      }
      function finish() { [...active].forEach(restore); }
      function reserve(nodes) {
        nodes.forEach(node => {
          const previous = owners.get(node);
          if (active.has(previous)) restore(previous);
        });
      }
      function play(nodes, from, to = {}) {
        if (document.hidden) return;
        const list = targets(nodes);
        if (!list.length) return;
        reserve(list);
        const animation = engine.fromTo(list, from, {
          duration: 0.28, ease: "power2.out", overwrite: "auto", ...to,
          onComplete: () => restore(animation),
        });
        active.add(animation);
        list.forEach(node => owners.set(node, animation));
      }
      api.reveal = nodes => play(nodes, {y: 8, opacity: 0.72}, {
        y: 0, opacity: 1, stagger: {amount: 0.12},
      });
      api.feedback = nodes => play(nodes, {scale: 0.97}, {scale: 1, duration: 0.2});
      root.classList.add("motion-ready");

      if (!entered && !document.hidden) {
        entered = true;
        // Keep server-validation focus and every input stationary on error pages.
        if (!document.querySelector("[data-error-summary]")) {
          // The active set owns restoration, including SVG attributes. Avoid
          // a second automatic context revert after a completed entrance.
          context.ignore(() => {
            const entrance = engine.timeline({
              defaults: {duration: 0.38, ease: "power2.out"},
              onComplete: () => restore(entrance),
            });
            active.add(entrance);
            const steps = [
              [".page-heading, .login-art-copy, .login-card", 10, 0],
              [".stat-card", 14, 0.06],
              [".page-wrap > .panel, .pos-catalog, .pos-order, .art-pet", 10, 0.12],
            ];
            steps.forEach(([selector, y, position]) => {
              const list = targets(document.querySelectorAll(selector));
              if (list.length) {
                list.forEach(node => owners.set(node, entrance));
                entrance.fromTo(list, {y, opacity: 0.72}, {
                  y: 0, opacity: 1, stagger: {amount: 0.14},
                }, position);
              }
            });
            // SVG transforms keep the real paid amounts, labels and bar heights intact.
            const bars = Array.from(document.querySelectorAll(".revenue-bar")).filter(visible).slice(0, 60);
            if (bars.length) {
              svgOriginals.set(entrance, bars.map(node => [node,
                ["style", "transform", "data-svg-origin"].map(name => [name, node.getAttribute(name)]),
              ]));
              entrance.fromTo(bars, {
              scaleY: 0.06, transformOrigin: "50% 100%",
            }, {scaleY: 1, stagger: {amount: 0.22}, duration: 0.48}, 0.16);
            }
            if (!entrance.duration()) restore(entrance);
          });
        }
      }
      function onHidden() { if (document.hidden) finish(); }
      document.addEventListener("visibilitychange", onHidden);
      return () => {
        api.reveal = noop; api.feedback = noop;
        document.removeEventListener("visibilitychange", onHidden);
        finish();
        root.classList.remove("motion-ready");
      };
    });
  }
  function unmount() { media?.revert(); media = null; }
  window.addEventListener("pagehide", unmount);
  window.addEventListener("pageshow", event => { if (event.persisted) mount(); });
  window.addEventListener("beforeprint", unmount);
  window.addEventListener("afterprint", mount);
  mount();
})();
