const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
(async () => {
  const [html, las, out, wd, ag] = process.argv.slice(2);
  const browser = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
  const page = await browser.newPage({ viewport: { width: 1500, height: 950 } });
  await page.goto('file://' + html); await page.waitForTimeout(400);
  await page.setInputFiles('#fpInput', las);
  await page.waitForFunction(() => window.FP && FP.ready && FP.data && FP.data.length > 0, null, { timeout: 30000 });
  const r = await page.evaluate(async ([wd, ag]) => {
    if (wd) { document.getElementById('fpWD').value = wd; document.getElementById('fpAG').value = ag || 0; }
    FP.runCalculation(); await new Promise(r => setTimeout(r, 1500));
    return { nct: FP.nct, params: FP.params, rows: FP.data.map(d => [d.depth_m, d.depth_ft, d.rhob, d.dt, d.dtsm, d.dtn, d.sv_psi, d.ph_psi, d.pp_psi, d.fg_psi, d.kUsed, d.sv_grad_ppg, d.pp_grad_ppg, d.fg_grad_ppg, d.rhobRepaired ? 1 : 0, d.synthetic ? 1 : 0, d.fgAll ? d.fgAll.mk : null]) };
  }, [wd, ag]);
  require('fs').writeFileSync(out, JSON.stringify(r));
  await browser.close();
})();
