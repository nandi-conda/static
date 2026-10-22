// Prerender an static app: run its wasm in Node, render every page with
// view(), and print the HTML of each as a JSON array.
//
//   node prerender.mjs app.wasm N POP
//
// The imports mirror ultra.js, but build HTML strings instead of DOM nodes.
// Events, timers and storage do nothing here; the browser takes over on load.
import fs from "node:fs";

const [wasmPath, count, POP] = process.argv.slice(2).map((x, i) => (i ? +x : x));
const td = new TextDecoder();
let mem;
const str = (p) => {
  const dv = new DataView(mem.buffer);
  return td.decode(new Uint8Array(mem.buffer, dv.getInt32(p, true), dv.getInt32(p + 4, true)));
};

const VOID = new Set(["area", "base", "br", "col", "embed", "hr", "img", "input", "link",
                      "meta", "source", "track", "wbr"]);
const escT = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const escA = (s) => escT(s).replace(/"/g, "&quot;");

let stack, cur;
const node = (t) => ({ t, a: {}, cls: "", p: {}, c: [] });
const push = (v) => cur.c.push(v);
const txt = (s) => push(String(s));
const strs = [""];
const sNew = () => (strs.push(""), strs.length - 1);

const html = (v) => {
  if (typeof v === "string") return escT(v);
  let s = "<" + v.t;
  if (v.cls) s += ` class="${escA(v.cls)}"`;
  for (const k in v.a) s += ` ${k}="${escA(v.a[k])}"`;
  if (v.p.value) s += ` value="${escA(v.p.value)}"`;
  if (v.p.checked) s += " checked";
  s += ">";
  if (VOID.has(v.t)) return s;
  return s + v.c.map(html).join("") + `</${v.t}>`;
};

const known = {
  el: (p) => { const v = node(str(p)); push(v); stack.push(cur); cur = v; },
  end: () => { cur = stack.pop(); },
  text: (p) => txt(str(p)),
  num: (x) => txt(x),
  fnum: (x, d) => txt(x.toFixed(d)),
  text_ref: (h) => txt(strs[h] ?? ""),
  ch: (c) => txt(String.fromCharCode(c)),
  attr: (k, v) => { cur.a[str(k)] = str(v); },
  attr_num: (k, v) => { cur.a[str(k)] = String(v); },
  attr_ref: (k, h) => { cur.a[str(k)] = strs[h] ?? ""; },
  cls: (p) => { const c = str(p); if (c) cur.cls = cur.cls ? cur.cls + " " + c : c; },
  cls_if: (p, on) => { if (on) known.cls(p); },
  value_ref: (h) => { cur.p.value = strs[h] ?? ""; },
  checked: (on) => { cur.p.checked = !!on; },
  s_new: () => sNew(),
  s_dup: (h) => (strs.push(strs[h]), strs.length - 1),
  s_copy: (d, s) => { strs[d] = strs[s]; },
  s_clear: (h) => { strs[h] = ""; },
  s_set: (h, p) => { strs[h] = str(p); },
  s_add: (h, p) => { strs[h] += str(p); },
  s_add_ch: (h, c) => { strs[h] += String.fromCharCode(c); },
  s_add_num: (h, x) => { strs[h] += String(x); },
  s_add_ref: (h, s) => { strs[h] += strs[s] ?? ""; },
  s_len: (h) => (strs[h] ?? "").trim().length,
  s_eq: (a, b) => (strs[a] === strs[b] ? 1 : 0),
  s_has: (h, n) => ((strs[h] ?? "").toLowerCase().includes((strs[n] ?? "").trim().toLowerCase()) ? 1 : 0),
  load_i32: (k, d) => d,
  load_i32_at: (k, i, d) => d,
  now_ms: () => 0,
  route: () => 0,
};
const js = new Proxy(known, { get: (t, k) => t[k] ?? (() => 0) });
const wasi = new Proxy({}, { get: () => () => 0 });

const { instance } = await WebAssembly.instantiate(fs.readFileSync(wasmPath),
                                                   { js, wasi_snapshot_preview1: wasi });
const ex = instance.exports;
mem = ex.memory;
ex.__main__global_stmts();

const out = [];
for (let i = 0; i < count; i++) {
  ex.update(POP, i);
  const top = node("#root");
  stack = []; cur = top;
  ex.view();
  out.push(top.c.map(html).join(""));
}
process.stdout.write(JSON.stringify(out));
