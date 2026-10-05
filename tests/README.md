# Verification harness

Checks `CBL_VDL_Tool_v2_with_Fracture_Pressure.html` in headless Chromium against
independent Python implementations and known ground truth.

## Requirements

- Node 18+ with Playwright (`npm i -g playwright`; or set `PLAYWRIGHT_MODULE` to its path)
- A Chromium build (`npx playwright install chromium`, or set `CHROME_PATH`)
- Python 3 with `numpy` and `lasio` (`pip install numpy lasio`)

## 1. PPFG (pore pressure / fracture gradient) on real wells

Each LAS is loaded into the PPFG document. The tool's per-depth results are then
recomputed with `lasio` + `numpy`: unit conversion, overburden integration, Eaton
Pp/Fg, the NCT and Matthews–Kelly.

```bash
node tests/fp_dump.js $PWD/CBL_VDL_Tool_v2_with_Fracture_Pressure.html <well.las> out.json [waterDepth_ft airGap_ft]
python3 tests/verify_ppfg.py <well.las> out.json [waterDepth_ft airGap_ft]
```

Public wells used (fetch them from these repositories):

| Well | Source | Units | Notes |
|---|---|---|---|
| Ungani-1, Canning Basin WA (Halliburton) | github.com/aliyusifov99/well-log-data-analysis `Well_1.las` | m, **kg/m³, µs/m, mm** | metric — exposed the unit bug |
| Volve 15/9-19 SR, North Sea (Statoil) | github.com/AryamaSinghParihar/LAS_files--log_data_analysis_and_evaluation | m, g/cc, µs/ft | offshore option tested |
| Pearson Family #1-35, Trego Co. KS | github.com/mjorden/LASanalysis `data/1046139243.las` | ft | NCT span gate |
| McGahan Farms 32-31, Laramie Co. WY (Schlumberger) | github.com/rockpyer/weller-logs `app/data/niobrara/2121045D.las` | ft | |

Results: the tool and the independent code agree exactly on all four wells, across
units, Sv, Pp, Fg, DTn and the Matthews–Kelly Fg. On Ungani-1 the previous version
"repaired" all 19,140 density samples to 2.4 g/cm³, because it read kg/m³ as g/cm³.
It then predicted a false 17–18 ppg pore pressure. The current version gives
8.3–8.9 ppg for most of the interval.

## 2. CBL / VDL engine with known ground truth

The real cased-hole datasets found during testing could not be downloaded from this
environment: Utah FORGE 78B-32 / 16A / 16B (Schlumberger CBL-VDL) and Equinor Volve
F-11 B. Instead, `make_synthetic_cbl.py` writes physics-based logs whose answer is
known: TOC at 1480 m, a channel at 1600–1640 m with a 120° arc, and a microannulus
at 1760–1790 m. It writes them in three vendor formats:

- `SYN_SLB_CBL_VDL_ft_bottomup.las`: Schlumberger CBL + VDL[0..239], **feet**, logged bottom-up, casing OD in `~P`.
- `SYN_BHI_SBT_m.las`: Baker Hughes SBT **attenuation** (ATAV, ATC1–6, dB/ft).
- `SYN_WFT_RBT_m.las`: Weatherford AM3F/AM5F, **BI in %**, AMMP[0..71] azimuthal map.

```bash
python3 tests/make_synthetic_cbl.py syn/
node tests/cbl_dump.js $PWD/CBL_VDL_Tool_v2_with_Fracture_Pressure.html syn/SYN_BHI_SBT_m.las bhi.json
python3 tests/verify_cbl.py bhi.json att syn/SYN_truth.csv      # use "amp" for amplitude files
```

Results: on all three formats the TOC comes out at 1480.06 m, against 1480 m in the
ground truth. The Bond Index and CBL class match the independent formulas at all
6,562 levels. The Weatherford channel is found at 1600.2–1639.9 m with a typical
120° arc. On the Baker file the previous version rated the free pipe as
good/excellent bond and the cemented pipe as poor bond. That happened because it
multiplied attenuation by 5 and read it as amplitude in mV.

## 3. DLIS reader

The DLIS reader was checked against `dlisio` on its own test corpus, including the
real UK well `206_05a-_3_DWL_DWL_WIRE_258276498.DLIS`. The previous reader stripped
one byte too many from each padded logical-record segment. It matched dlisio's
frame counts on 17 of 73 files. It now matches on 67 of 73. The six that still
differ were already wrong before the fix; they are exotic representation-code
fixtures. On the real file, all 47 scalar channels now decode identically to
dlisio, and depth no longer comes from the TIME index.
