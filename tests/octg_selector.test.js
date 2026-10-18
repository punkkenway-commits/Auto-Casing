/* Tests for the selection logic in octg_grade_selector.html. Run: npm test */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const html = fs.readFileSync(path.join(__dirname, "..", "octg_grade_selector.html"), "utf8");
const logic = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]).find(s => s.includes("Selection logic"));
const sandbox = { module: { exports: {} } };
vm.runInNewContext(logic, sandbox);
const S = sandbox.module.exports;

const near = (a, b, tol) => assert.ok(Math.abs(a - b) <= tol, `${a} not within ${tol} of ${b}`);

test("published cases give the expected result", () => {
  for (const c of S.CASES) {
    const v = S.caseInputs(c);
    const res = c.test(S.evaluate(v.co2, v.h2s, v.T, v.prof));
    assert.equal(res, c.id === "mb" ? "partial" : true, c.id);
  }
});

test("zone boundaries", () => {
  assert.equal(S.classify(2.89, 0), "Z1");
  assert.equal(S.classify(2.89, 0.0435), "Z2");
  assert.equal(S.classify(2.90, 0), "Z3");
  assert.equal(S.classify(100, 0.0435), "Z4");
  assert.equal(S.classify(100, 0.435), "Z5");
  assert.equal(S.classify(1450, 0.01), "Z5");
  assert.equal(S.classify(100, 1.45), "Z6");
  assert.equal(S.classify(100, 14.5), "Z7");
  assert.equal(S.classify(1450, 1450), "Z8");
});

test("ISO 15156-2 exemptions follow the static temperature profile", () => {
  const r = S.isoApiCheck({ Ts: 60, Tb: 260, z: 10000 });
  const g = name => r.find(a => a.g.startsWith(name));
  assert.equal(g("L80").status, "all");
  assert.equal(g("P110").status, "below");
  near(g("P110").from, 5750, 1e-6);
  near(g("Q125").from, 8250, 1e-6);
  assert.equal(S.isoApiCheck({ Ts: 60, Tb: 200, z: 10000 }).find(a => a.g.startsWith("Q125")).status, "never");
  assert.equal(S.isoApiCheck({ Ts: 180 }).find(a => a.g.startsWith("P110")).status, "all");
});

test("a hot well does not exempt P110 without a profile", () => {
  const r = S.evaluate(1, 0.5, 350, {});
  const p110 = r.iso.find(a => a.g.startsWith("P110"));
  assert.equal(p110.status, "needT");
  assert.equal(p110.ok, false);
});

test("ISO 15156-3 limits", () => {
  const kPa = k => k * 0.145038;
  assert.equal(S.iso3Check("SM 22CR-110, 125", kPa(9), 400).status, "ok");
  assert.equal(S.iso3Check("SM 22CR-110, 125", kPa(11), 200).reason, "h2s");
  assert.equal(S.iso3Check("SM 22CR-110, 125", kPa(5), 460).reason, "temp");
  assert.equal(S.iso3Check("SM 25CRW-125", kPa(15), 300).status, "ok");
  assert.equal(S.iso3Check("SM 13CRS-95, 110", kPa(10), null).status, "ok");
  assert.equal(S.iso3Check("SM 2535-110, 125", kPa(650), 420).status, "ok");      // 216°C ≤ 218°C at ≤700 kPa
  assert.equal(S.iso3Check("SM 2535-110, 125", kPa(2000), 300).reason, "temp");   // 149°C > 132°C at any pH2S
  assert.equal(S.iso3Check("SM 2550-110, 125", kPa(2000), 300).status, "ok");     // 149°C at any pH2S (4d)
  assert.equal(S.iso3Check("SM 2535-110, 125", kPa(2000), null).status, "needT");
  assert.equal(S.iso3Check("API L80 Type 1", 1, 100), null);
});

test("low-strength duplex in zone 6 is flagged against ISO 15156-3", () => {
  const r = S.evaluate(100, 5, 250);
  assert.equal(r.zone, "Z6");
  assert.ok(r.warnings.some(w => w.includes("outside the ISO 15156-3 default limits")));
});

test("total pressure units", () => {
  near(S.partialFromComposition(10000, "psig", 2.9, 40).co2, 10014.7 * 0.029, 1e-9);
  near(S.partialFromComposition(100, "barg", 10, 0).pAbs, 1465.08, 0.01);
  near(S.partialFromComposition(10, "MPa", 0, 0).pAbs, 1450.38, 0.01);
});

test("Peng-Robinson fugacity", () => {
  const low = S.prFugacity(14.7, 60, 0.05, 0.001);
  near(low.phiCO2, 1, 0.01);
  near(low.phiH2S, 1, 0.01);
  near(low.Z, 1, 0.01);
  const ch4 = S.prFugacity(1450.38, 80.33, 0, 0);      // methane, 10 MPa, 300 K (Tpr 1.57, Ppr 2.17): Standing-Katz Z about 0.835
  assert.ok(ch4.Z > 0.82 && ch4.Z < 0.85, String(ch4.Z));
  const hp = S.prFugacity(10014.7, 420, 0.029, 40e-6);
  assert.ok(hp.fCO2 > 0 && Number.isFinite(hp.fCO2));
  near(hp.fCO2, hp.phiCO2 * 0.029 * 10014.7, 1e-9);
});
