const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
(async () => {
  const [html, las, out] = process.argv.slice(2);
  const browser = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
  const page = await browser.newPage({ viewport: { width: 1500, height: 950 } });
  await page.goto('file://' + html); await page.waitForTimeout(400);
  await page.setInputFiles('#fi', las);
  await page.waitForFunction(() => typeof allData!=='undefined' && allData.length > 0, null, { timeout: 30000 });
  const r = await page.evaluate(() => ({CAL:{f:CAL.freePipe,b:CAL.bonded,af:CAL.attFree,ab:CAL.attBond}, rows: allData.map(d => [d.depth, d.cblRaw, d.cbl, d.bondIndex, d.cblClass])}));
  require('fs').writeFileSync(out, JSON.stringify(r)); await browser.close();
})();
