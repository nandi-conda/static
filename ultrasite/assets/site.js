// ultrasite browser runtime: mounts the site's ultra app over the prerendered
// page, keeps the address bar in sync, and mounts islands (their own ultra apps).
import { mount } from "./ultra.js";
import { base, pages, POP } from "./routes.js";

const root = document.querySelector("#app");
const indexOf = (path) => {
  const i = pages.findIndex((p) => p.url === path || p.url === path + "/");
  return i < 0 ? 0 : i;
};

const islands = new WeakSet();
const mountIslands = () => {
  for (const el of root.querySelectorAll("[data-island]")) {
    if (islands.has(el)) continue;
    islands.add(el);
    const name = el.dataset.island;
    // Both apps delegate events from their mount point, so an island's events
    // must not bubble on to the site's (its messages would mean something else there).
    for (const t of ["click", "dblclick", "input", "keydown", "pointerdown", "pointermove",
                     "pointerup", "pointercancel", "pointerleave", "contextmenu"]) {
      el.addEventListener(t, (e) => e.stopPropagation());
    }
    mount(el, `${base}islands/${name}.wasm`).catch((e) => console.error("island", name, e));
  }
};

let scrollTo = null;
const app = await mount(root, `${base}app.wasm`, {
  imports: ({ text, strs }) => ({
    ch: (c) => text(String.fromCharCode(c)),
    s_add_ch: (h, c) => { strs[h] += String.fromCharCode(c); },
    route: () => indexOf(location.pathname),
    go: (i) => {
      const p = pages[i];
      if (location.pathname !== p.url) history.pushState(null, "", p.url);
      document.title = p.title;
      scrollTo = 0;
    },
  }),
  onRender: () => {
    mountIslands();
    if (scrollTo !== null) { window.scrollTo(0, scrollTo); scrollTo = null; }
  },
});

// Links the app handles itself carry data-go; let the browser do the rest
// (new tab, external links, fragments).
root.addEventListener("click", (e) => {
  if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) {
    if (e.target.closest("a[data-go]")) e.stopImmediatePropagation();
    return;
  }
  if (e.target.closest("a[data-go]")) e.preventDefault();
}, true);

addEventListener("popstate", () => {
  const i = indexOf(location.pathname);
  document.title = pages[i].title;
  app.dispatch(POP, i);
});
