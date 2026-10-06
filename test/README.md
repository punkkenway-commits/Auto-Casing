# BASIRA EDM verification suite

```
node test/run-tests.js
```

Loads `BASIRA-EDM.html` in headless Chromium (Playwright), reads the engine's results and compares them
with published data and with reference calculations written independently in `run-tests.js`. It prints
PASS/FAIL per check, writes `test/TEST-REPORT.md`, and exits non-zero on any failure.

Requires Node 18+ and Playwright with Chromium (`npm i -D playwright && npx playwright install chromium`
if they are not already installed).

| Group | What is checked | Reference |
|---|---|---|
| A | Collapse, internal yield and body yield of 28 API pipes (20″ to 4-1/2″, H-40 to P-110) | Published API 5C2 / TR 5C3 performance tables |
| B | API 5C3 empirical factors and D/t limits, regime continuity, combined loading, Lamé / von Mises | API 5C3 Table 1; closed-form equations |
| C | Hydrostatic gradient and ppg conversion | SI definitions |
| D | Minimum-curvature path, interpolation, DLS / build / turn / toolface, plan to target | Exact arc geometry; numerical integration |
| E | Seat selection (kick, sticking, kick volume), kick tolerance | Criterion boundaries; field-unit hand calculation |
| F | Load-case spot values (evacuation, pressure test, RIH, post-cement, tubing leak, buckling) | Hand formulas |
| G | Basrah well end to end: seats → strings → auto-select → deviated re-plan | Every DF met; target hit; shoe TVD preserved |
| H | All tabs render, save/load round trip, report with all figures | — |

## Adding your own StressCheck benchmark

To compare against a StressCheck run of a real well, save the project from BASIRA (💾 Save), then add a
check to `run-tests.js` that loads it (`well = JSON.parse(...)`, `initAll()`) and compares
`evaluateWell()` minima with the StressCheck Well Summary. Use the same display mode (normalized vs
absolute SF), the same external profile and the same collapse load basis in both programs.
