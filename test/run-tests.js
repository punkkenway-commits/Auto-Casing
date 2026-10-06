#!/usr/bin/env node
/* BASIRA EDM verification suite.
   Loads BASIRA-EDM.html in headless Chromium, reads engine results, and compares them with
   (a) published API casing performance data and API 5C3 factor tables, and
   (b) reference calculations written independently here, in Node, from the textbook formulas.
   Writes test/TEST-REPORT.md and exits non-zero on any failure.

   Run:  node test/run-tests.js            (needs Playwright + Chromium; see test/README.md) */
const fs = require("fs");
const path = require("path");
const { openApp } = require("./harness");
const { API_PIPES, API_FACTORS, BASRAH_FORMATIONS } = require("./reference-data");

const FT = 3.28084, DEG = Math.PI / 180;
const G_REF = 9.80665 / 6.894757293 / FT;          // psi/ft per sg, from SI definitions
const results = [];                                 // {group, name, pass, detail}
const tables = {};                                  // markdown tables for the report
const check = (group, name, pass, detail) => results.push({ group, name, pass: !!pass, detail: detail || "" });
const near = (a, b, tol) => Math.abs(a - b) <= tol;
const rel = (a, b) => Math.abs(a - b) / Math.max(1e-12, Math.abs(b));
const fmt = (v, d = 0) => Number(v).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
const round10 = v => Math.round(v / 10) * 10;

/* ---------- independent reference implementations ---------- */
// minimum-curvature arc between two unit tangents, integrated numerically (no ratio factor used)
function tangent(inc, azi) { const i = inc * DEG, a = azi * DEG; return [Math.sin(i) * Math.cos(a), Math.sin(i) * Math.sin(a), Math.cos(i)]; }
function integrateArc(t1, t2, L, steps = 20000) {
  const beta = Math.acos(Math.max(-1, Math.min(1, t1[0] * t2[0] + t1[1] * t2[1] + t1[2] * t2[2])));
  const pos = [0, 0, 0];
  for (let k = 0; k < steps; k++) {
    const f = (k + 0.5) / steps;
    let t;
    if (beta < 1e-12) t = t1;
    else { const a = Math.sin((1 - f) * beta) / Math.sin(beta), b = Math.sin(f * beta) / Math.sin(beta); t = [a * t1[0] + b * t2[0], a * t1[1] + b * t2[1], a * t1[2] + b * t2[2]]; }
    for (let j = 0; j < 3; j++) pos[j] += t[j] * L / steps;
  }
  return { n: pos[0], e: pos[1], tvd: pos[2], beta };
}
// volumetric kick tolerance, textbook form (all in sg / ft / psi)
function ktRef({ S, D, mud, ki, frac, gasGrad, hole, dp, bha, bhaLenFt }) {
  const Sft = S * FT, Dft = D * FT, Gm = G_REF * mud;
  const Pf = G_REF * (mud + ki) * Dft, Pfr = G_REF * frac * Sft;
  const h = Math.min(Math.max(0, (Pfr - Pf + Gm * (Dft - Sft)) / (Gm - gasGrad)), Dft - Sft);
  const cap = d => (hole * hole - d * d) / 1029.4;
  const V1 = Math.min(h, bhaLenFt) * cap(bha) + Math.max(0, h - bhaLenFt) * cap(dp);
  const V2 = h * cap(dp) * Pfr / Pf;
  return { h, V1, V2, kt: Math.min(V1, V2) };
}
// API 5C3 collapse (written out again here, independently of the page)
function apiCollapseRef(D, d, yp, sa = 0) {
  let Y = yp;
  if (sa > 0) { const r = sa / yp; Y = yp * (Math.sqrt(1 - 0.75 * r * r) - 0.5 * r); }
  const A = 2.8762 + 0.10679e-5 * Y + 0.21301e-10 * Y * Y - 0.53132e-16 * Y ** 3;
  const B = 0.026233 + 0.50609e-6 * Y;
  const C = -465.93 + 0.030867 * Y - 0.10483e-7 * Y * Y + 0.36989e-13 * Y ** 3;
  const ba = B / A, x = 3 * ba / (2 + ba);
  const F = 46.95e6 * x ** 3 / (Y * (x - ba) * (1 - x) ** 2), G = F * B / A;
  const t = (D - d) / 2, dt = D / t;
  const dtyp = (Math.sqrt((A - 2) ** 2 + 8 * (B + C / Y)) + (A - 2)) / (2 * (B + C / Y));
  const dtpt = Y * (A - F) / (C + Y * (B - G)), dtte = (2 + ba) / (3 * ba);
  if (dt <= dtyp) return 2 * Y * (dt - 1) / dt ** 2;
  if (dt <= dtpt) return Y * (A / dt - B) - C;
  if (dt <= dtte) return Y * (F / dt - G);
  return 46.95e6 / (dt * (dt - 1) ** 2);
}

(async () => {
  const { browser, page, errors } = await openApp();
  const E = (fn, arg) => page.evaluate(fn, arg);

  /* ================= A. Published API ratings ================= */
  const eng = await E(list => list.map(([od, wt, g]) => {
    const p = pipeOf(od, wt), yp = GRADES[g].yp, c = collapseRating(p.od, p.id, yp, 0);
    return { id: p.id, coll: c.p, regime: c.regime, dt: c.dt, burst: burstRating(p.od, p.id, yp), py: bodyYield(p.od, p.id, yp) };
  }), API_PIPES);
  let rows = ["| Pipe | D/t | Regime | Collapse pub. | Collapse BASIRA | Δ % | Burst pub. | Burst BASIRA | Δ % | Yield pub. klbf | Yield BASIRA | Δ % |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"];
  API_PIPES.forEach(([od, wt, g, pc, pb, py], i) => {
    const e = eng[i], name = `${od}" ${wt}# ${g}`;
    const dc = rel(round10(e.coll), pc), db = rel(round10(e.burst), pb), dy = rel(Math.round(e.py / 1000), py);
    check("A. API ratings vs published tables", `${name} collapse`, dc <= 0.005, `${round10(e.coll)} vs ${pc} psi`);
    check("A. API ratings vs published tables", `${name} internal yield`, db <= 0.002, `${round10(e.burst)} vs ${pb} psi`);
    check("A. API ratings vs published tables", `${name} body yield`, Math.abs(Math.round(e.py / 1000) - py) <= 1, `${Math.round(e.py / 1000)} vs ${py} klbf`);
    rows.push(`| ${name} | ${e.dt.toFixed(2)} | ${e.regime} | ${fmt(pc)} | ${fmt(round10(e.coll))} | ${(100 * (round10(e.coll) - pc) / pc).toFixed(2)} | ${fmt(pb)} | ${fmt(round10(e.burst))} | ${(100 * (round10(e.burst) - pb) / pb).toFixed(2)} | ${fmt(py)} | ${fmt(Math.round(e.py / 1000))} | ${(100 * (Math.round(e.py / 1000) - py) / py).toFixed(2)} |`);
  });
  tables.api = rows.join("\n");

  /* ================= B. API 5C3 factors, regimes, combined loading ================= */
  const fac = await E(list => list.map(r => apiCollapseFactors(r[0])), API_FACTORS);
  rows = ["| Yield psi | A | B | C | F | G | (D/t)yp | (D/t)pt | (D/t)te |", "|---|---|---|---|---|---|---|---|---|"];
  API_FACTORS.forEach((r, i) => {
    const f = fac[i];
    const ok = near(f.A, r[1], 0.0015) && near(f.B, r[2], 0.00015) && near(f.C, r[3], 2) && near(f.F, r[4], 0.0015) &&
               near(f.G, r[5], 0.00015) && near(f.DTyp, r[6], 0.02) && near(f.DTpt, r[7], 0.02) && near(f.DTte, r[8], 0.03);
    check("B. API 5C3 formula internals", `Table 1 factors & D/t limits @ ${r[0]} psi`, ok,
          `A ${f.A.toFixed(3)} B ${f.B.toFixed(4)} C ${f.C.toFixed(0)} F ${f.F.toFixed(3)} G ${f.G.toFixed(4)} · ${f.DTyp.toFixed(2)} / ${f.DTpt.toFixed(2)} / ${f.DTte.toFixed(2)}`);
    rows.push(`| ${fmt(r[0])} | ${f.A.toFixed(3)} (${r[1]}) | ${f.B.toFixed(4)} (${r[2]}) | ${f.C.toFixed(0)} (${r[3]}) | ${f.F.toFixed(3)} (${r[4]}) | ${f.G.toFixed(4)} (${r[5]}) | ${f.DTyp.toFixed(2)} (${r[6]}) | ${f.DTpt.toFixed(2)} (${r[7]}) | ${f.DTte.toFixed(2)} (${r[8]}) |`);
  });
  tables.factors = rows.join("\n");
  // continuity of the four collapse equations at the regime boundaries (the API limits are where they intersect)
  const cont = await E(() => [55000, 80000, 110000].map(yp => {
    const k = apiCollapseFactors(yp), out = [];
    for (const dt of [k.DTyp, k.DTpt, k.DTte]) {
      const t = 1, D = dt, a = collapseRating(D, D - 2 * t * (1 - 1e-7), yp).p, b = collapseRating(D, D - 2 * t * (1 + 1e-7), yp).p;
      out.push(Math.abs(a - b) / b);
    }
    return out;
  }));
  check("B. API 5C3 formula internals", "Collapse continuous across yield/plastic/transition/elastic limits", cont.flat().every(x => x < 0.002),
        `max jump ${(100 * Math.max(...cont.flat())).toFixed(3)} %`);
  const ypa = await E(() => { const r = 0.3; return collapseRating(10, 9, 80000, 0.3 * 80000); });
  const ypaRef = apiCollapseRef(10, 9, 80000, 0.3 * 80000);
  check("B. API 5C3 formula internals", "Combined loading: Ypa = Yp[√(1−0.75r²) − 0.5r] at σa = 0.3 Yp", rel(ypa.p, ypaRef) < 1e-9,
        `${ypa.p.toFixed(1)} vs reference ${ypaRef.toFixed(1)} psi`);
  const vme = await E(() => {
    // envelope points must sit exactly on σVME = Y
    const od = 9.625, id = 8.681, Y = 80000, env = vmeEnvelope(od, id, Y), As = Math.PI / 4 * (od * od - id * id);
    const errB = env.burst.map(p => Math.abs(vmeStress(od, id, p.y, 0, p.x * 1000) - Y) / Y);
    const errC = env.collapse.map(p => Math.abs(vmeStress(od, id, 0, -p.y, p.x * 1000) - Y) / Y);
    return Math.max(...errB, ...errC);
  });
  check("B. API 5C3 formula internals", "von Mises envelope points satisfy σVME = Yp", vme < 1e-9, `max error ${vme.toExponential(2)}`);
  // Lamé inner-wall stresses against the closed form for one load state
  const lame = await E(() => stressParts(7, 6.094, 9000, 3000, 250000));
  {
    const ro = 3.5, ri = 3.047, As = Math.PI * (ro * ro - ri * ri);
    const sh = (9000 * (ri * ri + ro * ro) - 2 * 3000 * ro * ro) / (ro * ro - ri * ri), sr = -9000, sz = 250000 / As;
    const v = Math.sqrt(0.5 * ((sz - sh) ** 2 + (sh - sr) ** 2 + (sr - sz) ** 2));
    check("B. API 5C3 formula internals", "Lamé hoop / radial / axial and von Mises at the inner wall", rel(lame.vme, v) < 1e-12 && rel(lame.sh, sh) < 1e-12,
          `σh ${fmt(lame.sh)} σr ${fmt(lame.sr)} σa ${fmt(lame.sz)} → σVME ${fmt(lame.vme)} psi`);
  }

  /* ================= C. Units & hydrostatics ================= */
  const hyd = await E(() => ({ p: PSI(1, 1000), g: G_SG, sg10: toSG(10), bf: 1 - 1.2 / 7.84 }));
  check("C. Units & hydrostatics", "1 sg over 1,000 m = 1,422.33 psi (9.80665 kPa/m)", near(hyd.p, 1000 * FT * G_REF, 0.01), `${hyd.p.toFixed(3)} psi`);
  check("C. Units & hydrostatics", "ppg auto-conversion 10 ppg → 1.198 sg", near(hyd.sg10, 10 / 8.3454, 0.001), `${hyd.sg10} sg`);

  /* ================= D. Directional — minimum curvature ================= */
  const dirJ = await E(() => {
    well.survey = []; PATH = null;
    const rows = [[0, 0, 45], [500, 0, 45]];
    for (let md = 530; md <= 800; md += 30) rows.push([md, 3 * (md - 500) / 30, 45]);
    rows.push([3000, 30, 45]);
    well.survey = rows;
    const a = pathAt(3000), b = pathAt(615), c = pathAt(800);
    return { a, b, c, dls: getPath().st[3].dls, build: getPath().st[3].build, tf: getPath().st[3].tf, sb: bendingStress(9.625, 650) };
  });
  {
    const R = 30 * 180 / (Math.PI * 3);
    const tvdEOB = 500 + R * Math.sin(30 * DEG), hdEOB = R * (1 - Math.cos(30 * DEG));
    const tvdTD = tvdEOB + 2200 * Math.cos(30 * DEG), hdTD = hdEOB + 2200 * Math.sin(30 * DEG);
    const hd = p => Math.hypot(p.n, p.e);
    check("D. Directional (minimum curvature)", "Build section end: TVD = KOP + R·sinθ, departure = R(1 − cosθ)",
          near(dirJ.c.tvd, tvdEOB, 1e-6) && near(hd(dirJ.c), hdEOB, 1e-6), `TVD ${dirJ.c.tvd.toFixed(4)} (${tvdEOB.toFixed(4)}) · HD ${hd(dirJ.c).toFixed(4)} (${hdEOB.toFixed(4)}) m`);
    check("D. Directional (minimum curvature)", "J-profile at TD (3,000 m MD)", near(dirJ.a.tvd, tvdTD, 1e-6) && near(hd(dirJ.a), hdTD, 1e-6) && near(dirJ.a.n, dirJ.a.e, 1e-9),
          `TVD ${dirJ.a.tvd.toFixed(4)} (${tvdTD.toFixed(4)}) · HD ${hd(dirJ.a).toFixed(4)} (${hdTD.toFixed(4)}) m`);
    const i615 = 3 * 115 / 30, t615 = 500 + R * Math.sin(i615 * DEG), h615 = R * (1 - Math.cos(i615 * DEG));
    check("D. Directional (minimum curvature)", "Interpolation inside a survey interval lies on the arc (615 m MD)",
          near(dirJ.b.tvd, t615, 1e-6) && near(hd(dirJ.b), h615, 1e-6) && near(dirJ.b.inc, i615, 1e-9), `inc ${dirJ.b.inc.toFixed(4)}° TVD ${dirJ.b.tvd.toFixed(4)} HD ${hd(dirJ.b).toFixed(4)}`);
    check("D. Directional (minimum curvature)", "DLS and build rate of a 3°/30 m build", near(dirJ.dls, 3, 1e-9) && near(dirJ.build, 3, 1e-9) && dirJ.tf && near(dirJ.tf.deg, 0, 1e-6),
          `DLS ${dirJ.dls.toFixed(4)} · build ${dirJ.build.toFixed(4)} °/30 m · toolface ${dirJ.tf && dirJ.tf.deg.toFixed(3)}°`);
    const kappa = 3 * DEG / (30 * 39.3701), sb = 30e6 * (9.625 / 2) * kappa;
    check("D. Directional (minimum curvature)", "Dogleg bending σb = E·(OD/2)·κ (9-5/8\" at 3°/30 m)", rel(dirJ.sb, sb) < 1e-4, `${dirJ.sb.toFixed(1)} vs ${sb.toFixed(1)} psi`);
  }
  // 3-D (turning) arc against numerical integration
  const dir3 = await E(() => {
    well.survey = [[0, 0, 0], [1000, 20, 30], [1100, 35, 70]]; PATH = null;
    const s = getPath().st; return { a: s[1], b: s[2], dls: s[1].dls, turn: s[1].turn, build: s[1].build, tf: s[1].tf };
  });
  {
    const r = integrateArc(tangent(20, 30), tangent(35, 70), 100);
    const dn = dir3.b.n - dir3.a.n, de = dir3.b.e - dir3.a.e, dv = dir3.b.tvd - dir3.a.tvd;
    const cosb = Math.cos(15 * DEG) - Math.sin(20 * DEG) * Math.sin(35 * DEG) * (1 - Math.cos(40 * DEG));
    const dlsRef = Math.acos(cosb) / DEG / 100 * 30;
    check("D. Directional (minimum curvature)", "3-D turning arc (20°/30° → 35°/70° over 100 m) vs numerical integration",
          near(dn, r.n, 1e-4) && near(de, r.e, 1e-4) && near(dv, r.tvd, 1e-4), `ΔN ${dn.toFixed(4)} (${r.n.toFixed(4)}) ΔE ${de.toFixed(4)} (${r.e.toFixed(4)}) ΔTVD ${dv.toFixed(4)} (${r.tvd.toFixed(4)})`);
    check("D. Directional (minimum curvature)", "Dogleg: cosβ = cosΔI − sinI₁sinI₂(1 − cosΔA)", near(dir3.dls, dlsRef, 1e-9), `${dir3.dls.toFixed(4)} vs ${dlsRef.toFixed(4)} °/30 m`);
    check("D. Directional (minimum curvature)", "Build / turn rates of the 3-D interval", near(dir3.build, 4.5, 1e-9) && near(dir3.turn, 12, 1e-9),
          `build ${dir3.build.toFixed(3)} turn ${dir3.turn.toFixed(3)} °/30 m`);
    check("D. Directional (minimum curvature)", "Toolface of a build-and-turn-right arc lies between 0° and 90°", dir3.tf && dir3.tf.deg > 0 && dir3.tf.deg < 90 && !dir3.tf.mag,
          `${dir3.tf && dir3.tf.deg.toFixed(2)}°`);
  }
  const tfs = await E(() => {
    const seg = rows => { well.survey = rows; PATH = null; return getPath().st[1].tf; };
    return { drop: seg([[0, 0, 0], [1000, 30, 90], [1100, 20, 90]]), right: seg([[0, 0, 0], [1000, 30, 90], [1100, 30, 110]]),
             left: seg([[0, 0, 0], [1000, 30, 90], [1100, 30, 70]]), vert: seg([[0, 0, 0], [1000, 0, 0], [1100, 10, 135]]) };
  });
  // the start of a 0→10° kick-off at azimuth 135° has its curvature towards 135° (magnetic toolface)
  const tfVert = await E(() => { well.survey = [[0, 0, 0], [1000, 0, 0], [1100, 10, 135]]; PATH = null; return getPath().st[1].tf; });
  check("D. Directional (minimum curvature)", "Toolface: drop 180°, turn right 90°, turn left 270°, kick-off from vertical = magnetic azimuth",
        near(tfs.drop.deg, 180, 1e-6) && tfs.right.deg > 80 && tfs.right.deg < 100 && tfs.left.deg > 260 && tfs.left.deg < 280 && tfVert.mag && near(tfVert.deg, 135, 1e-6),
        `drop ${tfs.drop.deg.toFixed(2)} · right ${tfs.right.deg.toFixed(2)} · left ${tfs.left.deg.toFixed(2)} · kick-off ${tfVert.deg.toFixed(2)} M`);
  // plan to target
  const plan = await E(() => {
    well.survey = []; PATH = null;
    well.targets = [{ name: "T1", tvd: 2300, n: 650, e: 420, radius: 25 }];
    document.getElementById("ptKOP").value = 600; document.getElementById("ptBUR").value = 2.5; document.getElementById("ptTD").value = 3600;
    renderTargets(); planToTargetUI();
    const m = targetMiss(well.targets[0]), pl = planBuildHold(600, 2.5, well.targets[0]);
    const vs = vsOf(m.p.n, m.p.e), rt = mdAt(tvdAt(1777.7));
    const out = { miss: m.miss, md: m.md, pl, vs, rt, vsA: vsAzimuth(), cl: closureOf(m.p.n, m.p.e) };
    well.targets = []; return out;
  });
  {
    // independent: hold angle from tan(θ) = (H − R(1−cosθ)) / (D − R sinθ) solved by bisection
    const R = 30 * 180 / (Math.PI * 2.5), H = Math.hypot(650, 420), D = 2300 - 600;
    const f = th => (H - R * (1 - Math.cos(th))) * Math.cos(th) - (D - R * Math.sin(th)) * Math.sin(th);
    let lo = 1e-6, hi = Math.PI / 2; for (let k = 0; k < 200; k++) { const m = (lo + hi) / 2; if (f(lo) * f(m) <= 0) hi = m; else lo = m; }
    const th = (lo + hi) / 2 / DEG;
    check("D. Directional (minimum curvature)", "Plan to target (KOP 600 m, 2.5°/30 m): hold angle vs independent bisection", near(plan.pl.theta, th, 1e-6),
          `${plan.pl.theta.toFixed(6)}° vs ${th.toFixed(6)}°, azimuth ${plan.pl.A.toFixed(3)}°`);
    check("D. Directional (minimum curvature)", "Planned path hits the target centre", plan.miss < 0.01, `miss ${plan.miss.toFixed(4)} m at ${plan.md.toFixed(1)} m MD`);
    check("D. Directional (minimum curvature)", "Vertical section towards the target = closure at the target", near(plan.vs, plan.cl.dist, 1e-3) && near(plan.vsA, Math.atan2(420, 650) / DEG, 1e-9),
          `VS ${plan.vs.toFixed(3)} · closure ${plan.cl.dist.toFixed(3)} m @ ${plan.cl.azi.toFixed(2)}°`);
    check("D. Directional (minimum curvature)", "MD ↔ TVD inversion round-trip", near(plan.rt, 1777.7, 1e-6), `${plan.rt.toFixed(6)} m`);
  }

  /* ================= E. CasingSeat ================= */
  const seat = await E(fm => {
    well.survey = []; PATH = null; well.formations = fm.map(r => r.slice()); well.manualShoes = null;
    const set = (id, v) => { const e = document.getElementById(id); if (e.type === "checkbox") e.checked = v; else e.value = v; };
    const base = () => { set("csTD", 3800); set("csMinSurf", 100); set("csTrip", 0.04); set("csKickMargin", 0.06); set("csKI", 0.06);
      set("csDiffLimit", 2200); set("csEnforceDS", true); set("csKickBasis", "emw"); set("csMinKT", 25); set("csBHALen", 150); set("csMethod", "bottomup"); };
    const snap = () => well.seats.list.map(s => ({ shoe: s.shoe, next: s.nextTD, mud: s.mud, kick: s.kickEMW, lim: s.limitEMW, gov: s.gov,
      ob: s.ds && s.ds.ob, kt: s.kt && s.kt.bbl, deep: s.isDeepest }));
    const out = {};
    base(); runCasingSeat(); out.basrah = snap();
    const p = seatParams();
    out.edge = well.seats.list.filter(s => !s.isDeepest && s.gov === "Kick tolerance").map(s => {
      const z = s.shoe - 1, mud = maxPore(z, s.nextTD) + p.trip;
      return { shoe: s.shoe, shallowerFails: kickEMWatShoe(z, s.nextTD, mud, p.ki) > frac(z) - p.km };
    });
    set("csMethod", "topdown"); runCasingSeat(); out.topdown = snap(); set("csMethod", "bottomup");
    set("csKickBasis", "volume"); runCasingSeat(); out.volume = snap();
    out.volEdge = well.seats.list.filter(s => /volume/.test(s.gov)).map((s, i, a) => {
      const L = well.seats.list, k = L.indexOf(s), hole = defaultHole(L[k + 1].od);
      const mud = maxPore(s.shoe - 1, s.nextTD) + p.trip;
      return { kt: s.kt.bbl, shallower: kickTolerance(s.shoe - 1, s.nextTD, mud, { ...p, kickBasis: "volume" }, hole).bbl };
    });
    set("csKickBasis", "emw");
    // differential sticking: normally pressured to 2,000 m, then a steep ramp
    well.formations = [[0, 1.03, 1.45], [2000, 1.04, 1.90], [2100, 1.60, 2.00], [3500, 1.85, 2.25]];
    set("csTD", 3500); set("csDiffLimit", 1000);
    set("csEnforceDS", false); runCasingSeat(); out.dsOff = snap(); out.dsOffWorst = well.seats.worstDS;
    set("csEnforceDS", true); runCasingSeat(); out.dsOn = snap(); out.dsOnWorst = well.seats.worstDS;
    well.formations = fm.map(r => r.slice()); base(); runCasingSeat();
    return out;
  }, BASRAH_FORMATIONS);
  {
    const G = "E. CasingSeat (seat selection & kick tolerance)";
    const okAll = seat.basrah.filter(s => !s.deep).every(s => s.kick <= s.lim + 1e-6);
    check(G, "Basrah well, bottom-up: every shoe passes kick EMW ≤ frac − KM", okAll,
          seat.basrah.map(s => `${s.shoe} m${s.deep ? "" : ` (${s.kick.toFixed(3)} ≤ ${s.lim.toFixed(3)})`}`).join(" · "));
    check(G, "Kick-governed shoes sit on the criterion (1 m shallower fails)", seat.edge.length && seat.edge.every(e => e.shallowerFails),
          seat.edge.map(e => e.shoe + " m").join(", "));
    check(G, "Top-down method also yields a valid programme", seat.topdown.filter(s => !s.deep).every(s => s.kick <= s.lim + 1e-6),
          seat.topdown.map(s => `${s.shoe} m [${s.gov}]`).join(" · "));
    check(G, "Volume criterion: every governed shoe has KT ≥ 25 bbl, 1 m shallower < 25 bbl",
          seat.volEdge.length && seat.volEdge.every(e => e.kt >= 25 - 1e-6 && e.shallower < 25),
          seat.volEdge.map(e => `${e.kt.toFixed(2)} / ${e.shallower.toFixed(2)} bbl`).join(" · ") + " — " + seat.volume.map(s => s.shoe + " m").join(", "));
    check(G, "Sticking limit violated when not enforced (control case)", seat.dsOffWorst > 1000, `worst overbalance ${fmt(seat.dsOffWorst)} psi`);
    check(G, "Sticking enforced: a shoe is moved deeper and every open hole is within 1,000 psi",
          seat.dsOnWorst <= 1000 && seat.dsOn.some(s => s.gov === "Differential sticking"),
          seat.dsOn.map(s => `${s.shoe} m [${s.gov}]`).join(" · ") + ` — worst ${fmt(seat.dsOnWorst)} psi`);
    rows = ["| Shoe m TVD | Next TD m | Mud next hole sg | Kick EMW sg | Frac − KM sg | Overbalance psi | KT bbl | Governed by |", "|---|---|---|---|---|---|---|---|"];
    seat.basrah.forEach(s => rows.push(`| ${fmt(s.shoe)} | ${s.deep ? "—" : fmt(s.next)} | ${s.deep ? "—" : s.mud.toFixed(3)} | ${s.deep ? "—" : s.kick.toFixed(3)} | ${s.lim.toFixed(3)} | ${s.ob == null ? "—" : fmt(s.ob)} | ${s.kt == null ? "—" : s.kt.toFixed(1)} | ${s.gov} |`));
    tables.seats = rows.join("\n");
  }
  // kick tolerance against a hand calculation in field units (classic well-control example)
  const ktE = await E(() => {
    const keep = well.formations; well.survey = []; PATH = null;
    well.formations = [[0, 1.03, 14 / 8.3454], [6000, 1.03, 14 / 8.3454]];          // LOT 14.0 ppg at the shoe
    const r = kickTolerance(5000 / FT, 10000 / FT, 11 / 8.3454, { ki: 0.5 / 8.3454, gasGrad: 0.1, bhaLen: 600 / FT }, 8.5);
    well.formations = keep; return r;
  });
  {
    // hand calculation, 0.052 psi/ft/ppg: Pfrac 3,640 psi, Pf 5,980 psi, h = 520/0.472 = 1,101.7 ft,
    // V1 = 600 ft × 0.02914 + 501.7 ft × 0.04590 = 40.5 bbl, V2 = 1,101.7 × 0.04590 × 3,640/5,980 = 30.8 bbl
    const hand = 30.78;
    const ref = ktRef({ S: 5000 / FT, D: 10000 / FT, mud: 11 / 8.3454, ki: 0.5 / 8.3454, frac: 14 / 8.3454, gasGrad: 0.1, hole: 8.5, dp: 5, bha: 6.5, bhaLenFt: 600 });
    check("E. CasingSeat (seat selection & kick tolerance)", "Kick tolerance: 8-1/2\" hole, LOT 14.0 ppg @ 5,000 ft, 11.0 ppg mud to 10,000 ft, KI 0.5 ppg",
          rel(ktE.bbl, ref.kt) < 1e-6 && rel(ktE.bbl, hand) < 0.01,
          `BASIRA ${ktE.bbl.toFixed(2)} bbl (shut-in ${ktE.V1.toFixed(2)}, circulating ${ktE.V2.toFixed(2)}) · reference ${ref.kt.toFixed(2)} · hand calc ${hand} bbl`);
  }

  /* ================= F. StressCheck load cases — independent spot checks ================= */
  const sc = await E(() => {
    well.survey = []; PATH = null; seedDefaultStrings(); well.strings.forEach(normalizeString); syncChain();
    const prod = well.strings.find(s => s.role === "Production"), inter = well.strings.find(s => s.role === "Intermediate");
    const e = evaluateString(prod), ei = evaluateString(inter);
    const pick = (arr, name) => arr.find(c => c.name === name);
    const zi = z => e.zArr.indexOf(z);
    return {
      testP: prod.lc.testP, S: prod.shoe, mw: prod.mw, toc: prod.toc, cmtW: prod.lc.cmtW,
      evacShoe: pick(e.res.collapse, "Full evacuation").load[e.zArr.length - 1], evacMin: pick(e.res.collapse, "Full evacuation").min,
      testTop: pick(e.res.burst, "Pressure test").load[0], rih0: pick(e.res.axial, "Running in hole").load[0],
      post0: pick(e.res.axial, "Post-cement static").load[0], cRateShoe: e.cRate[e.zArr.length - 1], axInstShoe: e.axSvc[e.zArr.length - 1],
      leakTop: pick(e.res.burst, "Tubing leak").load[0], leak: { P: prod.lc.leakResP, D: prod.lc.leakResDepth, g: prod.lc.leakGasGrad, pk: prod.lc.leakPkrMW },
      buck: ei.buck.cases.find(c => c.name === "Pressure test"), interTestP: inter.lc.testP,
      pore3800: pore(3800), frac2100: frac(2100), pore2100: pore(2100),
    };
  });
  {
    const G = "F. StressCheck load cases (independent spot checks)";
    const S = 3800 * FT, P = v => G_REF * v;                       // gradient psi/ft
    // full evacuation of 7" 32# P-110 at the shoe: external = 1.61 sg mud, internal empty
    const evac = P(1.61) * S, cr = apiCollapseRef(7, 6.094, 110000, 0);
    check(G, "Full evacuation load at the shoe = mud hydrostatic (1.61 sg × 3,800 m)", rel(sc.evacShoe, evac) < 1e-6, `${fmt(sc.evacShoe)} vs ${fmt(evac)} psi`);
    check(G, "Full-evacuation collapse SF = API rating / load (shoe in axial compression → no derating)", rel(sc.evacMin, cr / evac) < 2e-3,
          `SF ${sc.evacMin.toFixed(4)} vs ${(cr / evac).toFixed(4)}`);
    check(G, "Pressure test at surface = test pressure (pp_sw backup is 0 at surface)", near(sc.testTop, sc.testP, 1e-6), `${fmt(sc.testTop)} psi`);
    // MASP default: min(frac@shoe − gas column, pore@next TD − gas column), rounded up to 100 psi
    // Running in hole at surface: buoyed weight + shock 0.9161·V·As·√(E·ρ)
    const As = Math.PI / 4 * (49 - 6.094 ** 2), W = 32 * S * (1 - 1.61 / 7.84), shock = 0.9161 * 2 * As * Math.sqrt(30e6 * 0.283);
    // tolerance 1e-5: the engine uses API's 0.7854 for π/4 (2·10⁻⁶ relative)
    check(G, "Running in hole at surface = buoyed weight + shock (2 ft/s)", rel(sc.rih0, W + shock) < 1e-5, `${fmt(sc.rih0)} vs ${fmt(W + shock)} lbf (shock ${fmt(shock)})`);
    // Post-cement static at surface: air weight + Pi·Ai − Pe·Ao at the shoe, slurry 1.90 below TOC 1,980 m
    const Ai = Math.PI / 4 * 6.094 ** 2, Ao = Math.PI / 4 * 49;
    const pe = P(1.61) * 1980 * FT + P(1.90) * (3800 - 1980) * FT, pi = P(1.61) * S;
    const post = 32 * S + pi * Ai - pe * Ao;
    check(G, "Post-cement static at surface = W_air + Pi·Ai − Pe·Ao (piston at the shoe)", rel(sc.post0, post) < 1e-5, `${fmt(sc.post0)} vs ${fmt(post)} lbf`);
    // tubing leak at surface: SITP = Pres − gas·D
    const sitp = sc.leak.P - sc.leak.g * sc.leak.D * FT, presRef = P(sc.pore3800) * S;
    check(G, "Tubing leak: Pres = pore at 3,800 m, SITP = Pres − 0.10 psi/ft × D at surface", rel(sc.leak.P, presRef) < 1e-3 && rel(sc.leakTop, sitp) < 1e-9,
          `Pres ${fmt(sc.leak.P)} psi · SITP ${fmt(sc.leakTop)} vs ${fmt(sitp)} psi`);
    // buckling of the 9-5/8" 47# intermediate under its pressure test, just above TOC (worked by hand in README)
    const b = sc.buck, I = Math.PI / 64 * (9.625 ** 4 - 8.681 ** 4), w = 47 / 12 * (1 - 1.34 / 7.84);
    const Fsin = 2.55 * Math.cbrt(30e6 * I * w * w);
    check(G, "Buckling, vertical well: Fsin = 2.55·(E·I·w²)^⅓ for 9-5/8\" 47# in 1.34 sg", rel(b.Fsin, Fsin) < 1e-9, `${fmt(b.Fsin)} vs ${fmt(Fsin)} lbf`);
    check(G, "Buckling: pressure test drives the free 9-5/8\" above TOC into helical buckling", b.state === "helical" && b.Feff < -b.Fhel,
          `Feff ${fmt(b.Feff)} lbf vs Fhel ${fmt(b.Fhel)} lbf at ${fmt(b.z)} m`);
  }

  /* ================= G. Real-data workflow: Basrah well, deviated, end to end ================= */
  const wf = await E(fm => {
    well.formations = fm.map(r => r.slice()); well.survey = []; PATH = null; well.manualShoes = null; well.targets = [];
    document.getElementById("csTD").value = 3800; document.getElementById("csKickBasis").value = "emw";
    document.getElementById("csEnforceDS").checked = true; document.getElementById("csDiffLimit").value = 2200;
    runCasingSeat(); applySeatsToDesign(true);
    // auto-select the lightest passing pipe for every string
    const picks = [];
    well.strings.forEach((st, i) => { document.getElementById("scString").value = i; onStringChange(); autoSelectPipe();
      picks.push({ role: roleLabel(st), tag: stringTag(st), shoe: st.shoe }); });
    const ev = evaluateWell(), df = DF();
    const sum = ev.map(e => ({ role: roleLabel(e.st), tag: stringTag(e.st), shoe: e.st.shoe, mw: e.st.mw,
      B: e.sc.res.mins.burst / df.burst, C: e.sc.res.mins.collapse / df.collapse, A: e.sc.res.mins.axial / df.tension, T: e.sc.res.mins.vme / df.vme,
      buck: e.sc.buck.status }));
    const checks = designChecks(ev).map(c => c.level + ": " + c.msg);
    // now make it deviated: plan to a target 700 m north-east of the rig at 3,000 m TVD
    well.targets = [{ name: "Reservoir", tvd: 3000, n: 500, e: 500, radius: 30 }];
    document.getElementById("ptKOP").value = 700; document.getElementById("ptBUR").value = 2; document.getElementById("ptTD").value = "";
    renderTargets(); planToTargetUI();
    const last = getPath().st[getPath().st.length - 1];
    document.getElementById("ptTD").value = Math.round(mdAt(3800)) + 1;
    planToTargetUI();
    runCasingSeat(); syncStringsFromSeats();
    const ev2 = evaluateWell();
    const sum2 = ev2.map(e => ({ role: roleLabel(e.st), shoeMD: e.st.shoe, shoeTVD: tvdAt(e.st.shoe),
      B: e.sc.res.mins.burst / df.burst, C: e.sc.res.mins.collapse / df.collapse, A: e.sc.res.mins.axial / df.tension, T: e.sc.res.mins.vme / df.vme,
      maxSb: Math.max(...e.sc.Fb.map((f, i) => f / e.sc.As[i])) }));
    const miss = targetMiss(well.targets[0]).miss, inc = getPath().st[getPath().st.length - 1].inc;
    return { picks, sum, checks, sum2, miss, inc, checks2: designChecks(ev2).map(c => c.level + ": " + c.msg), seats: well.seats.list.map(s => s.shoe) };
  }, BASRAH_FORMATIONS);
  {
    const G = "G. Basrah well — full workflow (vertical, then deviated)";
    check(G, "Vertical: CasingSeat → apply → auto-select pipe → every string meets every DF", wf.sum.every(s => s.B >= 1 && s.C >= 1 && s.A >= 1 && s.T >= 1),
          wf.sum.map(s => `${s.role} ${s.tag} @ ${fmt(s.shoe)} m`).join(" · "));
    check(G, "Vertical: no blocking design-check errors", !wf.checks.some(c => c.startsWith("bad")), wf.checks.join(" | ") || "none");
    check(G, "Deviated: planned well hits the reservoir target", wf.miss < 0.05, `miss ${wf.miss.toFixed(3)} m, hold ${wf.inc.toFixed(2)}°`);
    check(G, "Deviated: shoes keep their TVD after the survey is added", wf.sum2.every((s, i) => Math.abs(s.shoeTVD - wf.seats[i]) < 1.5),
          wf.sum2.map(s => `${fmt(s.shoeMD)} MD / ${fmt(s.shoeTVD)} TVD`).join(" · "));
    rows = ["| String | Pipe | Shoe m | MW sg | Burst | Collapse | Tension | Triaxial | Buckling |", "|---|---|---|---|---|---|---|---|---|"];
    wf.sum.forEach(s => rows.push(`| ${s.role} | ${s.tag} | ${fmt(s.shoe)} | ${s.mw} | ${s.B.toFixed(2)} | ${s.C.toFixed(2)} | ${s.A.toFixed(2)} | ${s.T.toFixed(2)} | ${s.buck} |`));
    tables.workflow = rows.join("\n");
    rows = ["| String | Shoe m MD | Shoe m TVD | Burst | Collapse | Tension | Triaxial | Max dogleg bending psi |", "|---|---|---|---|---|---|---|---|"];
    wf.sum2.forEach(s => rows.push(`| ${s.role} | ${fmt(s.shoeMD)} | ${fmt(s.shoeTVD)} | ${s.B.toFixed(2)} | ${s.C.toFixed(2)} | ${s.A.toFixed(2)} | ${s.T.toFixed(2)} | ${fmt(s.maxSb)} |`));
    tables.deviated = rows.join("\n");
    tables.devChecks = wf.checks2;
  }

  /* ================= H. Application integrity ================= */
  const integ = await E(async () => {
    const tabs = ["casingseat", "stresscheck", "schematic", "formation", "path", "summary", "report"];
    for (const t of tabs) { switchTab(t); await new Promise(r => requestAnimationFrame(() => setTimeout(r, 30))); }
    const before = evaluateWell().map(e => e.sc.res.mins);
    const json = JSON.stringify({ ...well, df: { ...DF(), normalized: sfIsNorm(), collapseMethod: collapseMethod(), collapseBasis: collapseBasis() }, seatParams: seatParamsForSave() });
    const w = JSON.parse(json); w.seats = null; w.strings.forEach(normalizeString); well = w; PATH = null; initAll();
    const after = evaluateWell().map(e => e.sc.res.mins);
    switchTab("report"); buildReport();
    // the Print path: render every hidden tab off-screen, then snapshot the plots into the report
    await new Promise(res => withAllViewsRendered(() => { renderReportFigures(); res(); }));
    const report = document.getElementById("reportArea").innerText.length;
    const figs = [...document.querySelectorAll("#rpFigs figure")];
    return { same: JSON.stringify(before) === JSON.stringify(after), report, figs: figs.filter(f => f.querySelector("img")).length, total: figs.length };
  });
  check("H. Application integrity", "All seven tabs render with no JavaScript errors", errors.length === 0, errors.join(" | ") || "no errors");
  check("H. Application integrity", "Project save → load round-trip reproduces every safety factor", integ.same, "");
  check("H. Application integrity", "Design report builds and every plot is captured for printing", integ.report > 2000 && integ.figs >= 7 && integ.figs === integ.total,
        `${fmt(integ.report)} chars, ${integ.figs}/${integ.total} figures captured`);

  await browser.close();

  /* ---------- report ---------- */
  const groups = [...new Set(results.map(r => r.group))];
  const nFail = results.filter(r => !r.pass).length;
  let md = `# BASIRA EDM v4.0 — verification report\n\nGenerated by \`node test/run-tests.js\` on ${new Date().toISOString().slice(0, 10)}. ` +
           `**${results.length - nFail} / ${results.length} checks pass.**\n\n` +
           `Engine values are read from the running app (headless Chromium). Every reference value is either published data ` +
           `(API casing tables, API 5C3 Table 1) or computed independently in \`test/run-tests.js\` from the textbook formula — ` +
           `never by calling the engine function under test.\n\n`;
  for (const g of groups) {
    md += `## ${g}\n\n| | Check | Detail |\n|---|---|---|\n`;
    results.filter(r => r.group === g).forEach(r => { md += `| ${r.pass ? "✅" : "❌"} | ${r.name} | ${String(r.detail).replace(/\|/g, "/")} |\n`; });
    md += "\n";
    if (g.startsWith("A.")) md += `### Published vs computed ratings\n\n${tables.api}\n\n`;
    if (g.startsWith("B.")) md += `### API 5C3 Table 1 (computed, published in brackets)\n\n${tables.factors}\n\n`;
    if (g.startsWith("E.")) md += `### Basrah well — automatic seats (bottom-up, KI 0.06 sg, KM 0.06 sg, trip 0.04 sg)\n\n${tables.seats}\n\n`;
    if (g.startsWith("G.")) md += `### Vertical well after auto-selection (normalized SF, pass ≥ 1.00)\n\n${tables.workflow}\n\n` +
      `### Same well deviated (KOP 700 m, 2°/30 m to a target 707 m away at 3,000 m TVD)\n\n${tables.deviated}\n\n` +
      `Design checks on the deviated well: ${tables.devChecks.length ? "\n\n" + tables.devChecks.map(c => "- " + c).join("\n") : "none"}\n\n`;
  }
  fs.writeFileSync(path.join(__dirname, "TEST-REPORT.md"), md);
  for (const g of groups) {
    const rs = results.filter(r => r.group === g);
    console.log(`\n${g}  (${rs.filter(r => r.pass).length}/${rs.length})`);
    rs.forEach(r => console.log(`  ${r.pass ? "PASS" : "FAIL"}  ${r.name}${r.pass ? "" : "  — " + r.detail}`));
  }
  console.log(`\n${results.length - nFail}/${results.length} checks pass. Report: test/TEST-REPORT.md`);
  process.exit(nFail ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });
