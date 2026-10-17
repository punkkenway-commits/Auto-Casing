"""
Balad Field unified PPFG - detailed method & calculations report (PDF)
=====================================================================

Recomputes everything with build_unified_ppfg.py and writes an HTML report that
Chromium prints to PDF.  Every number in the report comes from the same code
that produced Balad_Unified_PPFG.xlsx and the charts.

Usage:
    python make_method_report.py <Balad_PPFG__PT.xlsx> [output_dir]
"""
import sys, os, math, html, base64, subprocess, datetime
import numpy as np
import openpyxl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_unified_ppfg as b

CHROME = "/opt/pw-browsers/chromium"
E = html.escape


# ------------------------------------------------------------------ helpers
def f(v, n=2):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "&ndash;"
    return f"{v:.{n}f}"


def table(headers, rows, cls="", widths=None):
    h = "".join(f"<th>{x}</th>" for x in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<table class="{cls}"><thead><tr>{h}</tr></thead><tbody>{body}</tbody></table>'


def img(path, width="100%"):
    data = base64.b64encode(open(path, "rb").read()).decode()
    return f'<img src="data:image/png;base64,{data}" style="width:{width}">'


def at(arr, d):
    return float(arr[int(round(d / b.DZ))])


def raw_log_stats(path):
    """Counts of raw vs kept log samples (same QC rules as read_workbook)."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    out = {}
    for name in b.WELLS:
        ws = wb[f"{name} Final PPFG"]
        rows = ws.iter_rows(values_only=True)
        h1 = list(next(rows))
        dcols = [i for i, x in enumerate(h1) if x == "DEPTH"]
        i_dt, i_rb, i_dr = h1.index("DT"), h1.index("RHOB"), h1.index("DRHO")
        s = dict(dt_raw=0, dt_range=0, dt_casing=0, rb_raw=0, rb_range=0, rb_drho=0)
        for r in rows:
            if b.num(r[dcols[0]]) and b.num(r[i_dt]):
                s["dt_raw"] += 1
                if not 35 < r[i_dt] < 200:
                    s["dt_range"] += 1
                elif r[dcols[0]] < 1200 and r[i_dt] < 52:
                    s["dt_casing"] += 1
            if b.num(r[dcols[1]]) and b.num(r[i_rb]):
                s["rb_raw"] += 1
                if not 1.6 < r[i_rb] < 3.05:
                    s["rb_range"] += 1
                else:
                    dr = r[i_dr] if b.num(r[i_dr]) and r[i_dr] > -900 else 0.0
                    if abs(dr) > 0.15:
                        s["rb_drho"] += 1
        out[name] = s
    return out


# ------------------------------------------------------------------ report
def build_report(src, out_dir):
    wells, ebs = b.read_workbook(src)
    r = b.build(wells)
    raw = raw_log_stats(src)
    z = r["grid"]
    K = b.PSIM_PER_SG
    S = []                                   # html sections
    add = S.append

    # ============ title page
    zone_txt = "; ".join(f"{zn['top']:.0f}&ndash;{zn['base']:.0f} m: {zn['limit']:.2f} sg"
                         for zn in r["loss_zones"])
    add(f"""
<section class="cover">
  <div class="kicker">Balad Field &middot; Drilling Engineering</div>
  <h1>Unified Pore Pressure and Fracture Gradient (PPFG)</h1>
  <h2 class="sub">Method, calculations and results from nine offset wells (Balad-1 to Balad-9)</h2>
  <table class="meta">
    <tr><td>Input</td><td>Balad_PPFG__PT.xlsx &ndash; Final PPFG sheets of Balad-1 &hellip; Balad-9, EBS-1996 study table, Pressure Testing (casing) sheet</td></tr>
    <tr><td>Outputs</td><td>Balad_Unified_PPFG.xlsx, Balad_PPFG_Final.png, Balad_PPFG_Final_Wells.png, Balad_PPFG_QC_AllWells.png, Balad_OBG_QC.png</td></tr>
    <tr><td>Code</td><td>build_unified_ppfg.py (all numbers in this report are produced by it)</td></tr>
    <tr><td>Date</td><td>{datetime.date.today():%d %B %Y}</td></tr>
  </table>
  <div class="abstract">
    <h3>Summary</h3>
    <p>The nine wells' interpreted pore pressure (PP) tables were put on one unit (EMW, sg) and one 10 m depth grid.
    A new field overburden gradient (OBG) was integrated from QC'd density logs, replacing the workbook's constant-density OVB.
    At every depth the wells were combined into <b>PP P50</b> (median), <b>PP Design High</b> (maximum of the wells) and a
    min&ndash;max range, with the number of supporting wells shown as a confidence measure.</p>
    <p>Fracture gradient was computed for each well with Eaton's equation (&nu; = 0.25) and the field OBG, then calibrated
    with the drilling record because no LOT/FIT exist: mud weights drilled without losses raise a well's FG (lower bound),
    and loss events cap it (upper bound). <b>FG Design</b> is Eaton applied to PP Design High &ndash; the same pressure case, so the two design curves never cross &ndash; capped by the loss zones
    ({zone_txt}). Finally the mud-weight window was computed for each hole section with trip, surge and ECD allowances.</p>
  </div>
</section>""")

    # ============ 0. contents
    add("""
<section>
<h2>Contents</h2>
<ol class="toc">
<li>Input data</li><li>Units, datum and the common depth grid</li><li>Overburden gradient (OBG)</li>
<li>Unified pore pressure and number of wells</li><li>Fracture gradient and calibration</li>
<li>Mud-weight window per hole section</li><li>Final chart and how to read it</li>
<li>Limitations and data that would improve the result</li><li>References</li>
<li>Appendix A &ndash; Unified PPFG table (every 50 m)</li><li>Appendix B &ndash; Per-well PP and calibrated FG (every 100 m)</li>
<li>Appendix C &ndash; Drilling events used</li>
</ol>
<h3>Method flow</h3>
<div class="flow">
<div class="fbox">Final PPFG of 9 wells (PP, FG, OVB, MW, events) + RHOB/DT logs + casing depths</div><div class="arr">&darr;</div>
<div class="fbox">1. Units &amp; grid: EMW (sg) vs TVD-RT = MD, 10 m grid, interpolation in psi</div><div class="arr">&darr;</div>
<div class="frow"><div class="fbox">2. OBG = (1/z)&int;&rho;<sub>b</sub>dz from QC'd RHOB + Gardner(DT)</div>
<div class="fbox">3. PP statistics per depth: P50, High (max), Low (min), n wells</div></div><div class="arr">&darr;</div>
<div class="fbox">4. Eaton FG per well: FG = PP + &nu;/(1&minus;&nu;)(OBG &minus; PP), &nu; = 0.25</div><div class="arr">&darr;</div>
<div class="fbox">5. Calibration: MW drilled without losses (lower bound), loss zones (upper bound)</div><div class="arr">&darr;</div>
<div class="fbox key">Design curves: PP P50 &middot; PP Design High &middot; FG Design &middot; range &middot; confidence</div><div class="arr">&darr;</div>
<div class="fbox">6. Mud-weight window per hole section (trip, surge, ECD)</div>
</div>
</section>""")

    # ============ 1. input data
    cov = []
    for n in b.WELLS:
        w = wells[n]
        ev = [e["type"] for e in w["events"]]
        cov.append([n, f"{w['td']:.0f}", len(w["tab"]),
                    f"{w['dt'][:, 0].min():.0f}&ndash;{w['dt'][:, 0].max():.0f}",
                    f"{w['rhob'][:, 0].min():.0f}&ndash;{w['rhob'][:, 0].max():.0f}",
                    ev.count("Kick"), ev.count("Losses"), ev.count("Gas-cut mud")])
    add(f"""
<section>
<h2>1. Input data</h2>
<p>All inputs come from <b>Balad_PPFG__PT.xlsx</b>. Each of the nine sheets <i>Balad-N Final PPFG</i> holds the user's own
final interpretation for that well; this method takes those values as given and does not re-interpret logs for PP.</p>
<h3>1.1 What was read from each well sheet</h3>
<ul>
<li><b>Final PPFG table</b> (starting at row 10): Depth (m), PP (psi), OVB (psi), FP = fracture pressure (psi), MW (FWR) = mud weight actually used (sg).</li>
<li><b>Event notes</b> in the column left of <i>Depth</i>, and kill/resume mud weights to the right of the table. Notes are classified by keyword:
 &ldquo;kick&rdquo; &rarr; <b>Kick</b>; &ldquo;loss&rdquo; &rarr; <b>Losses</b>; &ldquo;gas cut&rdquo; or &ldquo;dropped&rdquo; &rarr; <b>Gas-cut mud</b>. TD notes are ignored.</li>
<li><b>Raw logs</b>: DT (&micro;s/ft) in the first depth block, RHOB (g/cc) and DRHO (g/cc) in the second depth block, 0.25 m sampling.</li>
</ul>
<h3>1.2 Coverage per well</h3>
{table(["Well", "TD (m)", "PPFG rows", "DT kept (m)", "RHOB kept (m)", "Kicks", "Losses", "Gas-cut"], cov)}
<h3>1.3 Other sheets used</h3>
<ul>
<li><b>EBS PPFG</b> &ndash; the 1996 East Baghdad study table (OBG, PP and FG in psi/ft every 100 m to 3500 m). Used only as a reference.</li>
<li><b>Pressure Testing</b> &ndash; casing float-collar depths (one well), used as the hole-section depths in Section 6.</li>
<li>Formation tops available: Hartha/Sa'adi 1980 m and Khasib 2325 m (Balad-1 sheet / 1996 study).</li>
</ul>
<h3>1.4 Not available</h3>
<p>No LOT/FIT, no MDT/RFT pressures, no RT/GL elevations, no complete formation tops and no per-well casing depths. These are old wells;
the consequences are handled in Sections 5&ndash;6 and listed in Section 8.</p>
</section>""")

    # ============ 2. units
    t2 = sorted(wells["Balad-2"]["tab"], key=lambda t: t["depth"])
    row = [t for t in t2 if t["depth"] == 2000][0]
    D = row["depth"]
    ex = []
    for lab, key in (("PP", "pp"), ("FP (fracture)", "fp"), ("OVB", "ovb")):
        P = row[key]
        sg = P / (D * K)
        ex.append([lab, f"{P:,.1f}", f"{P / (D * b.FT_PER_M):.4f}", f"{sg:.3f}", f"{sg * b.PPG_PER_SG:.2f}"])
    # interpolation example (Balad-1 between 1900 and 1980 m)
    t1 = sorted(wells["Balad-1"]["tab"], key=lambda t: t["depth"])
    a_, c_ = [t for t in t1 if t["depth"] == 1900][0], [t for t in t1 if t["depth"] == 1980][0]
    zi = 1950.0
    p_int = np.interp(zi, [a_["depth"], c_["depth"]], [a_["pp"], c_["pp"]])
    e_a, e_c = a_["pp"] / (a_["depth"] * K), c_["pp"] / (c_["depth"] * K)
    e_naive = np.interp(zi, [a_["depth"], c_["depth"]], [e_a, e_c])
    add(f"""
<section>
<h2>2. Units, datum and the common depth grid</h2>
<h3>2.1 Constants (same as the workbook)</h3>
{table(["Constant", "Value", "Note"], [
        ["Pressure gradient per ppg", f"{b.PSIFT_PER_PPG} psi/ft/ppg", "workbook factor"],
        ["ppg per sg", f"{b.PPG_PER_SG}", "workbook factor"],
        ["ft per m", f"{b.FT_PER_M}", "workbook factor"],
        ["psi/ft per sg", f"{b.PSIFT_PER_SG:.5f}", "0.0519 &times; 8.337"],
        ["psi/m per sg", f"{b.PSIM_PER_SG:.5f}", "0.43269 &times; 3.281"]])}
<h3>2.2 Conversion to equivalent mud weight</h3>
<div class="eq">EMW (sg) = P (psi) / [ D (m) &times; {b.PSIM_PER_SG:.4f} ]</div>
<p>Depth reference: the wells are vertical, so TVD = MD, and every depth stays on the well's own rotary table (RT) as recorded.
No RT elevations exist, so no TVDSS correction was applied.</p>
<p><b>Worked example &ndash; Balad-2 at {D:.0f} m</b> (row of the Final PPFG table):</p>
{table(["Quantity", "Pressure (psi)", "Gradient (psi/ft)", "EMW (sg)", "EMW (ppg)"], ex)}
<p>Example for PP: {row['pp']:,.1f} / ({D:.0f} &times; {K:.4f}) = <b>{row['pp'] / (D * K):.3f} sg</b>.</p>
<h3>2.3 Common 10 m grid and interpolation in pressure</h3>
<p>All wells are re-sampled to depths 0, 10, 20 &hellip; {z[-1]:.0f} m so that the nine wells are compared at identical depths.
Each well is used only between its first and last table depth. Interpolation is done on <b>pressure in psi</b>, then converted to EMW:
EMW = P/D is not linear in depth, and the tables contain step changes at kicks.</p>
<p><b>Worked example &ndash; Balad-1 at {zi:.0f} m</b>, between table rows {a_['depth']:.0f} m ({a_['pp']:,.1f} psi) and {c_['depth']:.0f} m ({c_['pp']:,.1f} psi):</p>
<div class="eq">P(1950) = {a_['pp']:,.1f} + ({zi:.0f} &minus; {a_['depth']:.0f}) / ({c_['depth']:.0f} &minus; {a_['depth']:.0f}) &times; ({c_['pp']:,.1f} &minus; {a_['pp']:,.1f}) = {p_int:,.1f} psi
&nbsp;&rarr;&nbsp; EMW = {p_int / (zi * K):.4f} sg</div>
<p>Interpolating the EMW values directly would give {e_naive:.4f} sg; the pressure route is the physically consistent one.</p>
<h3>2.4 Normal hydrostatic and datum sensitivity</h3>
<p>The reference line is the normal hydrostatic gradient 0.465 psi/ft = <b>{b.NORMAL_SG:.3f} sg</b>, measured from RT.
A datum error &Delta;D changes EMW by the factor D/(D+&Delta;D): a 10 m error at 1000 m changes 1.18 sg by
{1.18 - 1.18 * 1000 / 1010:.3f} sg (1%). The effect is negligible below a few hundred metres and largest near surface.</p>
</section>""")

    # ============ 3. OBG
    rb_bins, dt_bins = r["rb_bins"], None
    both_n = int(np.sum(~np.isnan(r["rb_bins"]) & ~np.isnan(r["rho_dt"])))
    qc = []
    for n in b.WELLS:
        s = raw[n]
        qc.append([n, f"{s['dt_raw']:,}", s["dt_range"], s["dt_casing"], f"{len(wells[n]['dt']):,}",
                   f"{s['rb_raw']:,}", s["rb_range"], s["rb_drho"], f"{len(wells[n]['rhob']):,}"])
    good = (np.sum(~np.isnan(r["rho_w"]), axis=0) >= 2)
    first_d = float(z[np.where(good)[0][0]])
    # worked integration at 1000 m in 250 m steps
    rho = r["rho"]
    cum = np.concatenate([[0], np.cumsum(0.5 * (rho[1:] + rho[:-1]) * np.diff(z))])
    wex = []
    prev = 0.0
    for d in (250, 500, 750, 1000):
        i = int(d / b.DZ)
        seg = cum[i] - prev
        wex.append([f"{d - 250:.0f}&ndash;{d:.0f}", f"{seg / 250:.3f}", f"{seg:,.1f}", f"{cum[i]:,.1f}", f"{cum[i] / d:.3f}"])
        prev = cum[i]
    OV = np.array([r["ovb_wb"][n] for n in b.WELLS])
    cmp_rows = []
    for d in (100, 500, 1000, 1500, 2000, 2500, 3000, 3500):
        i = int(d / b.DZ)
        e_ = np.interp(d, ebs[:, 0], ebs[:, 1] / b.PSIFT_PER_SG)
        cmp_rows.append([d, f(rho[i], 3), f(r["obg"][i], 3), f(e_, 3), f(r["obg"][i] - e_, 3),
                         f"{np.nanmin(OV[:, i]):.2f}&ndash;{np.nanmax(OV[:, i]):.2f}"])
    d_ebs = np.interp(ebs[:, 0], z, r["obg"]) - ebs[:, 1] / b.PSIFT_PER_SG
    add(f"""
<section>
<h2>3. Overburden gradient (OBG)</h2>
<p>The overburden stress is the weight of all rock and fluid above a depth. The workbook's OVB used a constant (or point) bulk density
times depth, which gives 2.35&ndash;2.54 sg from the surface and jumps with every density spike. Because FG depends directly on OBG,
a new field OBG was integrated from the density logs.</p>
<div class="eq">&sigma;<sub>v</sub>(z) = g &int;<sub>0</sub><sup>z</sup> &rho;<sub>b</sub>(z') dz' &nbsp;&nbsp;&rArr;&nbsp;&nbsp; OBG (sg) = (1/z) &int;<sub>0</sub><sup>z</sup> &rho;<sub>b</sub> dz &nbsp; (&rho;<sub>b</sub> in g/cc)</div>
<h3>3.1 Log QC</h3>
<ul>
<li>RHOB kept only if 1.6 &lt; RHOB &lt; 3.05 g/cc and |DRHO| &le; 0.15 g/cc (bad-hole / poor pad contact).</li>
<li>DT kept only if 35 &lt; DT &lt; 200 &micro;s/ft. Above 1200 m, DT &lt; 52 &micro;s/ft is rejected: values of 48&ndash;50 &micro;s/ft at the top
of Balad-3, Balad-4 and Balad-8 are readings inside casing, not formation. The first 20 m of each DT log is also dropped.</li>
</ul>
{table(["Well", "DT raw", "DT out of range", "DT in casing", "DT kept*", "RHOB raw", "RHOB out of range", "|DRHO|&gt;0.15", "RHOB kept"], qc, "small")}
<p class="note">* DT kept also excludes the first 20 m of each log.</p>
<h3>3.2 Density where RHOB is missing &ndash; Gardner calibrated on Balad</h3>
<p>RHOB starts at 1250&ndash;1875 m, but DT starts at 180&ndash;1100 m. Above the RHOB log, density is estimated from DT with Gardner et al. (1974):</p>
<div class="eq">&rho;<sub>b</sub> = a &middot; V<sup>0.25</sup>, &nbsp; V = 10<sup>6</sup> / DT (ft/s)</div>
<p>The coefficient was calibrated on the 10 m bins where both RHOB and DT exist ({both_n} bins over all wells):
a = median(RHOB / V<sup>0.25</sup>) = <b>{r['a_gardner']:.4f}</b> (textbook value 0.23).</p>
<h3>3.3 Field composite density</h3>
<ol>
<li>Each well: 10 m bin medians of RHOB; Gardner density where RHOB is missing.</li>
<li>Field density = median of the wells in each bin, used only where at least 2 wells have data.</li>
<li>Gaps filled linearly; 50 m running-median smoothing.</li>
<li>Above the first supported bin ({first_d:.0f} m) a linear trend from 1.95 g/cc at surface (assumed value for unconsolidated near-surface sediments).</li>
</ol>
<h3>3.4 Integration &ndash; worked example to 1000 m</h3>
<p>The integral is a cumulative trapezoid sum on the 10 m grid. The table groups it in 250 m intervals:</p>
{table(["Interval (m)", "Mean density (g/cc)", "&int;&rho;dz in interval (g/cc&middot;m)", "Cumulative &int;&rho;dz", "OBG at base (sg)"], wex)}
<p>OBG(1000 m) = {cum[100]:,.1f} / 1000 = <b>{r['obg'][100]:.3f} sg</b> = {r['obg'][100] * b.PSIFT_PER_SG:.3f} psi/ft.</p>
<h3>3.5 Comparison with the 1996 study and the workbook OVB</h3>
{table(["Depth (m)", "Field density (g/cc)", "Field OBG (sg)", "EBS-1996 OBG (sg)", "Difference (sg)", "Workbook OVB range (sg)"], cmp_rows)}
<p>Over the EBS-1996 depths the field OBG differs by {np.mean(d_ebs):+.3f} sg on average (maximum |difference| {np.max(np.abs(d_ebs)):.3f} sg, at shallow depth where the surface trend is assumed).
The workbook OVB scatters from {np.nanmin(OV):.2f} to {np.nanmax(OV):.2f} sg, which is why it was replaced.</p>
<div class="fig">{img(os.path.join(out_dir, 'Balad_OBG_QC.png'))}<div class="cap">Figure 1 &ndash; OBG QC: density inputs per well and field composite (left); field OBG vs EBS-1996 and workbook OVB (right).</div></div>
</section>""")

    # ============ 4. PP
    PP = np.array([r["pp"][n] for n in b.WELLS])
    sel = [1000, 2000, 3000, 3800, 4000, 4100]
    head = ["Depth (m)"] + [n.replace("Balad-", "Ba-") for n in b.WELLS] + ["n", "Low", "P50", "High"]
    rows4 = []
    for d in sel:
        i = int(d / b.DZ)
        rows4.append([d] + [f(PP[j, i]) for j in range(9)] +
                     [int(r["nw"][i]), f(r["pp_low"][i]), f(r["pp_ml"][i]), f(r["pp_high"][i])])
    conf_rows = []
    for (a0, a1), lab in [(seg, "High (&ge; 6 wells)") for seg in b.segments(r["nw"] >= b.CONF_HIGH)] + \
                         [(seg, "Medium (3&ndash;5 wells)") for seg in b.segments((r["nw"] >= b.CONF_MED) & (r["nw"] < b.CONF_HIGH))] + \
                         [(seg, "Low (&le; 2 wells)") for seg in b.segments((r["nw"] > 0) & (r["nw"] < b.CONF_MED))]:
        conf_rows.append((z[a0], [f"{z[a0]:.0f}&ndash;{z[a1]:.0f}", lab,
                                  f"{int(r['nw'][a0:a1 + 1].min())}&ndash;{int(r['nw'][a0:a1 + 1].max())}"]))
    conf_rows = [x[1] for x in sorted(conf_rows)]
    tops = []
    for n in ("Balad-1", "Balad-2", "Balad-3"):
        idx = np.where(r["pp"][n] > 1.3)[0]
        tops.append([n, f"{z[idx[0]]:.0f}" if idx.size else "&ndash;", f(np.nanmax(r["pp"][n]))])
    kicks = []
    for n in b.WELLS:
        for e in wells[n]["events"]:
            if e["type"] == "Kick":
                i = int(round(e["depth"] / b.DZ))
                kicks.append([n, f"{e['depth']:.0f}", f(e["mw"]), f(e["kill"]), f(r["pp_ml"][i]), f(r["pp_high"][i])])
    add(f"""
<section>
<h2>4. Unified pore pressure and number of wells</h2>
<p>At every grid depth the wells that have data there are combined (well count n):</p>
<ul>
<li><b>PP Low</b> = minimum of the wells.</li>
<li><b>PP P50</b> (most likely) = median of the wells, then a 5-point (50 m) running median to remove single-sample noise.</li>
<li><b>PP Design High</b> = maximum of the wells (the offset envelope), not smoothed. It is used for kick tolerance, burst loads and the minimum mud weight,
because a new well can meet the highest pressure seen in any offset (Bourgoyne et al., 1986; Zhang, 2011).</li>
</ul>
<h3>4.1 Worked example &ndash; each well's PP (sg) at selected depths</h3>
{table(head, rows4, "small")}
<h3>4.2 Confidence from the number of wells</h3>
{table(["Depth interval (m)", "Confidence", "Wells"], conf_rows)}
<h3>4.3 Transition to overpressure</h3>
<p>Only Balad-1, Balad-2 and Balad-3 reach the deep overpressure. The first depth where each well's PP exceeds 1.3 sg differs by several hundred metres,
so the High envelope rises earlier than any single well. This spread is the main reason for low confidence in the deep section:</p>
{table(["Well", "First depth with PP &gt; 1.3 sg (m)", "Maximum PP (sg)"], tops)}
<h3>4.4 Check against kicks</h3>
<p>A kick means PP exceeded the mud weight in use; the kill weight is an approximate upper bound. The unified curves at the kick depths:</p>
{table(["Well", "Depth (m)", "MW at kick (sg)", "Kill / max MW (sg)", "PP P50 (sg)", "PP Design High (sg)"], kicks, "small")}
<h3>4.5 Data features to note</h3>
<ul>
<li>Some wells carry PP below hydrostatic near surface (e.g. {f(np.nanmin(PP[:, 10]))} sg at 100 m) and others use 0.51 psi/ft (1.18 sg) from shallow depth,
taken from the 1996 study. Both come from the input tables.</li>
<li>Balad-2 has PP of about 0.99 sg at 3130&ndash;3200 m, inside the loss zone.</li>
</ul>
</section>""")

    # ============ 5. FG
    FGw, FGe, lift = r["FGw"], r["FGe"], r["lift"]
    d0 = 2000
    i0 = int(d0 / b.DZ)
    obg0, pp0 = r["obg"][i0], r["pp_ml"][i0]
    lift_rows = []
    for j, n in enumerate(b.WELLS):
        idx = np.where(lift[j])[0]
        if idx.size:
            segs = b.segments(lift[j])
            rng = ", ".join(f"{z[a]:.0f}&ndash;{z[c]:.0f}" for a, c in segs[:4]) + (" &hellip;" if len(segs) > 4 else "")
            mx = np.max(FGw[j, idx] - FGe[j, idx])
            lift_rows.append([n, idx.size, rng, f"{mx:.2f}"])
    zones = [[f"{zn['top']:.0f}&ndash;{zn['base']:.0f}", f"{zn['limit']:.2f}", ", ".join(zn["wells"])] for zn in r["loss_zones"]]
    fgex = []
    for d in (500, 1000, 2000, 2800, 3500, 3800, 4000, 4200):
        i = int(d / b.DZ)
        fgex.append([d, f(r["obg"][i]), f(r["pp_ml"][i]), f(r["pp_high"][i]), f(r["fg_ml"][i]), f(r["fg_low"][i]),
                     f(r["fg_env"][i]), f(r["loss_lim"][i]), f"<b>{f(r['fg_design'][i])}</b>",
                     f"{r['fg_design'][i] - r['pp_high'][i]:+.2f}"])
    i3 = int(3940 / b.DZ)
    PPw = np.array([r["pp"][n] for n in b.WELLS])
    cross_rows = []
    for n in ("Balad-1", "Balad-2", "Balad-3"):
        j = b.WELLS.index(n)
        cross_rows.append([n, f(PPw[j, i3]), f(FGw[j, i3])])
    cross_gap = np.nanmax(PPw[:, i3]) - np.nanmin(FGw[:, i3])
    fb = pp0 + 2 * b.NU / (1 - b.NU) * (obg0 - pp0)
    e2000 = np.interp(2000, ebs[:, 0], ebs[:, 3] / b.PSIFT_PER_SG)
    add(f"""
<section>
<h2>5. Fracture gradient and calibration</h2>
<h3>5.1 Eaton's equation</h3>
<div class="eq">FG = PP + [&nu; / (1 &minus; &nu;)] &middot; (OBG &minus; PP), &nbsp; &nu; = {b.NU} &nbsp;&rArr;&nbsp; &nu;/(1&minus;&nu;) = {b.K_EATON:.4f}</div>
<p>Eaton (1969) treats the minimum horizontal stress as the effective vertical stress scaled by &nu;/(1&minus;&nu;), plus pore pressure.
&nu; = 0.25 is the value used in the user's workbook. FG is computed for <b>each well</b> with its own PP and the <b>field</b> OBG, so the OVB noise of the workbook does not reach FG.</p>
<p><b>Worked example at {d0} m</b> (most-likely case): OBG = {obg0:.3f} sg, PP P50 = {pp0:.3f} sg</p>
<div class="eq">FG ML = {pp0:.3f} + {b.K_EATON:.4f} &times; ({obg0:.3f} &minus; {pp0:.3f}) = <b>{pp0 + b.K_EATON * (obg0 - pp0):.3f} sg</b></div>
<h3>5.2 Why the EBS-1996 FG is not used for design</h3>
<p>The 1996 study uses 2&nu;/(1&minus;&nu;) = 0.667 instead of 0.333. That form is the <b>breakdown</b> pressure of an intact, unfractured borehole
(Haimson &amp; Fairhurst, 1967), which is higher than the fracture propagation/closure pressure that controls lost circulation.
At {d0} m it would give {fb:.3f} sg with the field OBG (EBS-1996 table: {e2000:.3f} sg), against {pp0 + b.K_EATON * (obg0 - pp0):.3f} sg from Eaton.</p>
<h3>5.3 Calibration without LOT/FIT</h3>
<p><b>Lower bound &ndash; mud weight held without losses.</b> If a well was drilled through depth z with mud weight MW and had no losses within &plusmn;20 m,
the formation held MW, so that well's FG at z is at least MW (the use of offset drilling data in Daines, 1982). Where Eaton gives less, FG is raised to MW:</p>
<div class="eq">FG<sub>well</sub>(z) = max[ FG<sub>Eaton</sub>(z), MW<sub>no loss</sub>(z) ]</div>
{table(["Well", "Grid points raised", "Depth ranges (m)", "Largest raise (sg)"], lift_rows) if lift_rows else "<p>No points were raised.</p>"}
<p><b>Upper bound &ndash; loss zones.</b> Loss events of all wells are sorted by depth and grouped when consecutive events are less than 300 m apart.
Each zone runs from 20 m above the first to 20 m below the last event, and its limit is the lowest mud weight at which losses occurred:</p>
{table(["Loss zone (m)", "Limit (sg)", "Wells"], zones)}
<p>Losses in the 2610&ndash;3210 m carbonates may be vugular or natural-fracture losses rather than induced fractures.
Either way, they are a real ceiling for the mud weight in that interval.</p>
<h3>5.4 FG Design &ndash; same pressure case as PP Design High</h3>
<p>Within every single well PP is below FG at every depth (Eaton always gives FG &gt; PP because OBG &gt; PP). A crossover can only appear when the
highest PP of one well is plotted against the lowest FG of another well at the same depth. That is what happens in the transition zone,
because the overpressure top is at a different depth in each deep well. At 3940 m:</p>
{table(["Well", "PP (sg)", "Calibrated FG (sg)"], cross_rows)}
<p>Taking PP from the overpressured well and FG from the still-normal well would put PP above FG by {cross_gap:.2f} sg &ndash; a state no well shows.
The design FG is therefore taken from the <b>same pressure case</b> as PP Design High:</p>
<div class="eq">FG Design(z) = min[ PP<sub>High</sub>(z) + &nu;/(1&minus;&nu;) &middot; (OBG(z) &minus; PP<sub>High</sub>(z)), &nbsp; loss-zone limit(z) ]</div>
<p>FG Low (the weakest calibrated offset well) is kept as a dashed reference curve. It shows the risk in the transition zone:
if a new well is still normally pressured where the design weight is already high, the formation may break down at the FG Low value.
That is a casing-point and real-time pore-pressure-monitoring issue, not a curve to design the window on.</p>
{table(["Depth (m)", "OBG", "PP P50", "PP High", "FG ML", "FG Low (weakest well)", "FG on PP High", "Loss limit", "FG Design", "FG Design &minus; PP High"], fgex, "small")}
<p class="note">All values in sg. Note that Balad-1 and Balad-2 were drilled at about 2.25 sg below 4000 m; Eaton with &nu; = 0.25 may underestimate the deep FG,
which only LOT/FIT data can confirm.</p>
</section>""")

    # ============ 6. mud window
    csg = [[od, f"{ft:,.1f}", f"{ft / b.FT_PER_M:,.1f}"] for od, ft in b.CASING]
    secs = []
    for s in r["sections"]:
        secs.append([s["hole"], s["casing"], f"{s['top']:.0f}&ndash;{s['base']:.0f}", f"{s['n_min']}&ndash;{s['n_max']}",
                     f"{s['pp_max']:.2f} @ {s['pp_at']:.0f}", f"{s['fg_min']:.2f} @ {s['fg_at']:.0f}", f"{s['ecd']:.2f}",
                     f"{s['mw_lo']:.2f}", f"{s['mw_hi']:.2f}", f"{s['window']:+.2f}", f"{s['window_nl']:+.2f}",
                     f"<b>{s['rec_mw']:.2f}</b>", f"{s['hist_lo']:.2f}&ndash;{s['hist_hi']:.2f}"])
    st = {s["hole"]: s for s in r["sections"]}
    s12 = st['12-1/4"']
    add(f"""
<section>
<h2>6. Mud-weight window per hole section</h2>
<p>A mud weight must stay above pore pressure (with a margin for swab when tripping) and below the weakest fracture gradient in the open hole
(with a margin for surge and for the extra pressure of circulation, ECD).</p>
<div class="eq">Min MW = max<sub>section</sub>(PP Design High) + {b.TRIP_MARGIN_SG} sg (trip / swab, &asymp; 0.25 ppg)</div>
<div class="eq">Max static MW = min<sub>open hole</sub>(FG Design) &minus; {b.SURGE_MARGIN_SG} sg (surge) &minus; &Delta;ECD(hole size)</div>
<p>&Delta;ECD allowances are <b>assumed</b> typical values, not hydraulics results: 26&Prime; 0.02, 17-1/2&Prime; 0.03, 12-1/4&Prime; 0.04, 8-1/2&Prime; 0.06, 6&Prime; 0.07 sg.</p>
<h3>6.1 Hole sections from the casing depths</h3>
{table(["Casing", "Float collar (ft)", "Depth (m)"], csg)}
<h3>6.2 Section results (sg)</h3>
{table(["Hole", "Casing", "Interval (m)", "Wells", "Max PP High @ m", "Min FG Design @ m", "&Delta;ECD", "Min MW", "Max static MW", "Window", "Window excl. loss zones", "Recommended MW", "MW used in wells"], secs, "small")}
<p><b>Worked example &ndash; 12-1/4&Prime; section:</b> Min MW = {s12['pp_max']:.3f} + 0.03 = {s12['mw_lo']:.3f} sg.
Max static MW = {s12['fg_min']:.3f} &minus; 0.03 &minus; 0.04 = {s12['mw_hi']:.3f} sg (weakest point in the loss zone at {s12['fg_at']:.0f} m).
Window = {s12['window']:+.3f} sg. Outside the loss zones the weakest FG is {s12['fg_min_nl']:.3f} sg at {s12['fg_nl_at']:.0f} m, giving a window of {s12['window_nl']:+.3f} sg.</p>
<h3>6.3 Interpretation</h3>
<ul>
<li><b>26&Prime; &ndash; closed.</b> Some input tables assume 1.18 sg PP from about 100 m, while complete losses happened at 1.10&ndash;1.13 sg in the top 35 m
(Balad-3, -4, -6). The shallow PP is probably overstated; top hole is drilled at minimum weight with losses expected.</li>
<li><b>17-1/2&Prime; &ndash; open</b> ({st['17-1/2"']['window']:+.2f} sg).</li>
<li><b>12-1/4&Prime; &ndash; open except the 2610&ndash;3210 m loss zone.</b> Drill at the minimum weight with LCM ready, which matches the field history (MW 1.17&ndash;1.40 with losses).</li>
<li><b>8-1/2&Prime; &ndash; closed on paper.</b> The curves do not cross, but the 9-5/8&Prime; shoe at 3596 m lies above the overpressure top (3680&ndash;4000 m),
so the weakest open-hole FG ({st['8-1/2"']['fg_min']:.2f} sg at {st['8-1/2"']['fg_at']:.0f} m, just below the shoe) is far below the {st['8-1/2"']['mw_lo']:.2f} sg needed deeper in the same section. Balad-1 and Balad-2 actually drilled this interval at up to 2.25 sg, so either the 9-5/8&Prime; was deeper in those wells
or the real FG is higher than Eaton predicts. Per-well casing depths or a LOT at the shoe would settle it.</li>
<li><b>6&Prime; &ndash; closed by {st['6"']['window']:+.2f} sg</b> (only 1&ndash;2 wells; low confidence).</li>
</ul>
<p>&ldquo;Recommended MW&rdquo; is the minimum safe static mud weight rounded up to 0.01 sg. Where the window is closed it means: drill at the minimum,
expect losses, and plan LCM or a contingency string.</p>
</section>""")

    # ============ 7. chart
    add(f"""
<section>
<h2>7. Final chart and how to read it</h2>
<div class="fig">{img(os.path.join(out_dir, 'Balad_PPFG_Final.png'))}<div class="cap">Figure 2 &ndash; Balad field generic PPFG, design curves for approval.</div></div>
<div class="fig">{img(os.path.join(out_dir, 'Balad_PPFG_Final_Wells.png'))}<div class="cap">Figure 2b &ndash; The same design curves with the nine offset wells (each well's PP solid, actual MW dashed).</div></div>
{table(["Element", "Meaning"], [
        ["Top axis / left axis", "EMW in sg (0.6&ndash;2.6) / depth in m TVD-RT (= MD, vertical wells)"],
        ["Brown curve", "Field OBG integrated from RHOB/DT (Section 3)"],
        ["Cyan dashed", f"Normal hydrostatic 0.465 psi/ft ({b.NORMAL_SG:.2f} sg) from RT"],
        ["Blue solid / navy dashed", "PP P50 / PP Design High (Section 4)"],
        ["Red solid", "FG Design &ndash; Eaton on PP Design High, capped by loss zones (Section 5)"],
        ["Red dashed (thin)", "FG Low &ndash; weakest calibrated offset well, reference only"],
        ["Blue / red shaded bands", "Min&ndash;max range of the wells' PP / calibrated FG"],
        ["Green vertical bars + label", "Recommended mud weight for each hole section (Section 6)"],
        ["Dotted vertical lines", "Max static MW per section: green open, orange open except loss zone, red closed"],
        ["Orange dots / red crosses", "Losses at the MW in use / kicks at the kill MW"],
        ["Orange shaded bands", "Loss zones"],
        ["Hatched area, dashed curves", "Low confidence: 2 wells or fewer"],
        ["Right track", "Number of wells at each depth: green &ge; 6, orange 3&ndash;5, red &le; 2"],
        ["Black triangles / dotted lines", "Casing shoes (approx.) / formation tops"]])}
<h3>Using the curves for a new well</h3>
<ol>
<li>Read PP Design High and FG Design at the planned casing depths, and check the confidence track for those depths.</li>
<li>Use sheet <i>Design (ppg-psi)</i> of Balad_Unified_PPFG.xlsx as the PP/FG/OBG input to the casing-design software.</li>
<li>Use sheet <i>Hole-section window</i> for the planned mud weights, replacing the assumed &Delta;ECD with hydraulics results.</li>
<li>Update the curves when new LOT/FIT, casing-depth or pressure data become available (re-run build_unified_ppfg.py).</li>
</ol>
<div class="fig">{img(os.path.join(out_dir, 'Balad_PPFG_QC_AllWells.png'), '92%')}<div class="cap">Figure 3 &ndash; QC chart: all wells' mud weights and PP, EBS-1996 reference curves and drilling events.</div></div>
</section>""")

    # ============ 8 limitations, 9 references
    add(f"""
<section>
<h2>8. Limitations and data that would improve the result</h2>
{table(["Missing item", "What it limits today", "What it would change"], [
        ["LOT / FIT", "FG rests on Eaton (&nu; = 0.25) and drilling-event bounds", "Direct FG at each shoe; &nu; or stress ratio recalibrated, mainly below the 9-5/8&Prime; shoe"],
        ["Per-well casing depths", "Casing points from one well; open-hole exposure per well unknown", "Credit each well's open hole with the highest MW held; may reopen the 8-1/2&Prime; window"],
        ["MDT / RFT pressures", "PP is interpreted, not measured", "Measured points to anchor P50 and High"],
        ["RT / GL elevations", "Depths on each well's RT; no TVDSS", "Common datum; hydrostatic from ground level"],
        ["Formation tops for every well", "Wells compared at equal depth, not equal stratigraphy", "Stratigraphic alignment; narrows the 3680&ndash;4000 m overpressure-top spread"],
        ["Hydraulics (ECD)", "&Delta;ECD 0.02&ndash;0.07 sg assumed", "Real section windows"]])}
<p>Wells per depth: 9 wells from 100 to 2190 m; fewer below; 3 wells below 3320 m (Balad-1, -2, -3); 2 below 4270 m; only Balad-1 below 4370 m.
Values in the medium- and low-confidence intervals are provisional.</p>
<h2>9. References</h2>
<ol class="refs">{''.join(f'<li>{E(x[x.index(". ") + 2:])}</li>' for x in b.REFERENCES)}</ol>
</section>""")

    # ============ Appendix A
    rowsA = []
    for i in range(z.size):
        if z[i] <= 0 or z[i] % 50 or r["nw"][i] == 0:
            continue
        rowsA.append([f"{z[i]:.0f}", int(r["nw"][i]), str(r["conf"][i]), f(r["obg"][i]), f(r["pp_low"][i]), f(r["pp_ml"][i]),
                      f(r["pp_high"][i]), f(r["fg_ml"][i]), f(r["fg_low"][i]), f(r["loss_lim"][i]), f(r["fg_design"][i]),
                      f(r["mw_min"][i]), f(r["mw_max"][i])])
    add(f"""
<section>
<h2>Appendix A &ndash; Unified PPFG (every 50 m, EMW in sg)</h2>
<p class="note">Min MW = PP High + 0.03; Max MW = FG Design &minus; 0.03 &minus; &Delta;ECD of the section. The full 10 m table is in sheet <i>Unified PPFG (sg)</i>.</p>
{table(["Depth (m)", "n", "Conf.", "OBG", "PP Low", "PP P50", "PP High", "FG ML", "FG Low (weakest)", "Loss limit", "FG Design", "Min MW", "Max MW"], rowsA, "tiny")}
</section>""")

    # ============ Appendix B
    short = [n.replace("Balad-", "Ba-") for n in b.WELLS]
    rowsB = []
    for i in range(z.size):
        if z[i] <= 0 or z[i] % 100 or r["nw"][i] == 0:
            continue
        rowsB.append([f"{z[i]:.0f}"] + [f(PP[j, i]) for j in range(9)] + [f(FGw[j, i]) for j in range(9)])
    add(f"""
<section>
<h2>Appendix B &ndash; Per-well PP and calibrated FG (every 100 m, sg)</h2>
{table(["Depth (m)"] + [f"PP {s}" for s in short] + [f"FG {s}" for s in short], rowsB, "tiny")}
</section>""")

    # ============ Appendix C
    rowsC = []
    for n in b.WELLS:
        for e in wells[n]["events"]:
            rowsC.append([n, f"{e['depth']:.0f}", e["type"], f(e["mw"]), f(e["kill"]), E(e["note"])])
    add(f"""
<section>
<h2>Appendix C &ndash; Drilling events used</h2>
{table(["Well", "Depth (m)", "Type", "MW (sg)", "Kill / max MW (sg)", "Note (as recorded)"], rowsC, "small")}
</section>""")

    css = """
@page { size: A4; margin: 16mm 14mm 16mm 14mm; }
body { font-family: 'DejaVu Sans', Arial, sans-serif; font-size: 9.6pt; color: #1b1b1b; line-height: 1.38; }
h1 { font-size: 24pt; color: #1f3a93; margin: 0 0 6px; }
h2 { font-size: 14.5pt; color: #1f3a93; border-bottom: 2px solid #1f3a93; padding-bottom: 3px; margin: 0 0 10px; }
h3 { font-size: 11pt; color: #1f3a93; margin: 14px 0 6px; }
.sub { font-size: 13pt; color: #444; border: none; font-weight: normal; margin-bottom: 26px; }
section { page-break-after: always; }
section:last-child { page-break-after: auto; }
.cover { padding-top: 60px; }
.kicker { text-transform: uppercase; letter-spacing: 2px; color: #888; font-size: 9pt; margin-bottom: 10px; }
.meta { border: none; margin-bottom: 24px; }
.meta td { border: none; border-bottom: 1px solid #ddd; padding: 6px 8px; vertical-align: top; }
.meta td:first-child { font-weight: bold; width: 80px; color: #1f3a93; }
.abstract { background: #f3f6fb; border-left: 4px solid #1f3a93; padding: 10px 16px; }
table { border-collapse: collapse; width: 100%; margin: 6px 0 10px; page-break-inside: auto; }
tr { page-break-inside: avoid; }
th { background: #1f3a93; color: white; font-weight: bold; padding: 4px 5px; font-size: 8.6pt; text-align: center; }
td { border: 1px solid #c9d1e3; padding: 3px 5px; text-align: center; font-size: 8.8pt; }
tbody tr:nth-child(even) td { background: #f5f7fb; }
table.small td, table.small th { font-size: 7.8pt; padding: 2px 3px; }
table.tiny td, table.tiny th { font-size: 6.9pt; padding: 1px 2px; }
thead { display: table-header-group; }
.eq { background: #fbfaf2; border: 1px solid #e3dfc2; padding: 7px 12px; margin: 8px 0; font-family: 'DejaVu Serif', Georgia, serif; font-size: 10.2pt; }
.note { color: #555; font-size: 8.4pt; }
.fig { text-align: center; margin: 8px 0; page-break-inside: avoid; }
.cap { font-size: 8.4pt; color: #444; font-style: italic; margin-top: 3px; }
.toc li { margin: 3px 0; }
.flow { margin-top: 8px; }
.fbox { border: 1.3px solid #8a94a8; border-radius: 6px; padding: 6px 10px; text-align: center; margin: 0 auto; width: 78%; }
.fbox.key { border: 2px solid #1f3a93; background: #e8eefb; font-weight: bold; }
.frow { display: flex; gap: 12px; width: 84%; margin: 0 auto; }
.frow .fbox { width: auto; flex: 1; }
.arr { text-align: center; color: #8a94a8; font-size: 13pt; line-height: 1.1; }
.refs li { margin: 2px 0; font-size: 8.8pt; }
ul, ol { margin-top: 4px; }
td:first-child { white-space: nowrap; }
"""
    doc = f"<!doctype html><html><head><meta charset='utf-8'><title>Balad Unified PPFG - Method and Calculations</title><style>{css}</style></head><body>{''.join(S)}</body></html>"
    html_path = os.path.join(out_dir, "_report_tmp.html")
    open(html_path, "w").write(doc)
    pdf_path = os.path.join(out_dir, "Balad_PPFG_Method_Report.pdf")
    subprocess.run([CHROME, "--headless", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf_path}", "file://" + html_path], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.remove(html_path)
    return pdf_path


if __name__ == "__main__":
    src = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(os.path.abspath(__file__))
    print(build_report(src, out))
