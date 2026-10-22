// Browser test for the example site. BASE is the server's URL.
//   node tests/e2e.cjs   (run through `pixi run test`, which builds and serves first)
const { chromium } = require("playwright");
const assert = require("node:assert/strict");

const BASE = process.env.BASE || "http://localhost:8000";
const SHOTS = process.env.SHOTS;

(async () => {
  const browser = await chromium.launch(
    process.env.CHROMIUM ? { executablePath: process.env.CHROMIUM } : {});
  const page = await browser.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));

  // 1. Prerendered HTML is there before any script runs.
  await page.route("**/*.js", (r) => r.abort());
  await page.goto(BASE + "/posts/how-it-works/");
  assert.equal(await page.textContent(".page h1"), "How it works");
  assert.match(await page.textContent("pre code"), /def page_3\(\) -> None:/);
  await page.unroute("**/*.js");
  errors.length = 0; // the aborted scripts

  // 2. With the wasm loaded, the home page hydrates and the island mounts.
  await page.goto(BASE + "/");
  await page.waitForSelector(".island .counter-value");
  assert.equal(await page.textContent(".page h1"), "Markdown in, WebAssembly out");
  assert.equal(await page.title(), "static");
  const plus = page.locator(".island").getByRole("button", { name: "+", exact: true });
  await plus.click();
  await plus.click();
  await page.waitForFunction(() => document.querySelector(".counter-value").textContent === "2");
  if (SHOTS) await page.screenshot({ path: SHOTS + "/home.png", fullPage: true });

  // 3. In-app navigation: no reload, URL and title follow.
  await page.evaluate(() => (window.__marker = 1));
  await page.click("nav a:has-text('Posts')");
  await page.waitForSelector(".listing");
  assert.equal(new URL(page.url()).pathname, "/posts/");
  assert.equal(await page.title(), "Posts · static");
  assert.equal(await page.evaluate(() => window.__marker), 1, "page reloaded");
  const items = await page.$$eval(".listing a", (as) => as.map((a) => a.textContent));
  assert.deepEqual(items, ["How it works", "Hello, ultra"]); // newest first
  assert.equal(await page.getAttribute("nav a.active", "href"), "/posts/");

  await page.click(".listing a:has-text('Hello, ultra')");
  await page.waitForSelector("h1:has-text('Hello, ultra')");
  // a relative .md link resolved to the other post
  await page.click(".page a:has-text('how it works')");
  await page.waitForSelector("h1:has-text('How it works')");
  assert.equal(new URL(page.url()).pathname, "/posts/how-it-works/");

  // 4. Back button.
  await page.goBack();
  await page.waitForSelector("h1:has-text('Hello, ultra')");
  assert.equal(await page.evaluate(() => window.__marker), 1, "page reloaded on back");

  // 5. Search runs in wasm.
  await page.fill(".search input", "backslash");
  await page.waitForSelector(".results a");
  const hits = await page.$$eval(".results a", (as) => as.map((a) => a.textContent));
  assert.ok(hits.includes("How it works"), "search hits: " + hits);
  await page.fill(".search input", "zzzz");
  await page.waitForSelector(".results .none:has-text('No matches')");
  await page.fill(".search input", "docs");
  await page.click(".results a:has-text('Docs')");
  await page.waitForSelector("h1:has-text('Docs')");
  assert.equal(await page.$(".results"), null);

  // 6. Tricky literals made it through LPython intact.
  const p = await page.textContent(".page p:last-of-type");
  assert.ok(p.includes("C:\\Users\\v") && p.includes(`"it's"`), p);
  if (SHOTS) await page.screenshot({ path: SHOTS + "/docs.png", fullPage: true });

  // 7. Island survives a page round trip (re-mounted fresh).
  await page.click("nav a:has-text('Home')");
  await page.waitForSelector(".island .counter-value");

  assert.deepEqual(errors, []);
  await browser.close();
  console.log("e2e ok");
})().catch((e) => { console.error(e); process.exit(1); });
