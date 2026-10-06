// Loads BASIRA-EDM.html in headless Chromium so Node tests can call the engine directly.
const path = require("path");
const { chromium } = require(require.resolve("playwright", { paths: [process.cwd(), "/opt/node-tools/node_modules"] }));

async function openApp(file) {
  const browser = await chromium.launch({ timeout: 30000 });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  const errors = [];
  page.on("pageerror", e => errors.push(String(e)));
  page.on("dialog", d => d.accept());
  await page.goto("file://" + path.resolve(file || path.join(__dirname, "..", "BASIRA-EDM.html")), { timeout: 30000 });
  await page.waitForFunction(() => typeof well !== "undefined" && well.seats, null, { timeout: 30000 });
  return { browser, page, errors };
}
module.exports = { openApp };
