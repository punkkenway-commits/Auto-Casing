import json, sys, numpy as np, lasio
las_path, dump, wd_ft, ag_ft = sys.argv[1], sys.argv[2], float(sys.argv[3] if len(sys.argv)>3 else 0), float(sys.argv[4] if len(sys.argv)>4 else 0)
d = json.load(open(dump)); R = np.array([[np.nan if v is None else v for v in r] for r in d['rows']], float)
zm, zft, rhob, dt, dtsm, dtn, sv, ph, pp, fg, K, svg, ppg, fgg, rep, syn, fgmk = R.T
L = lasio.read(las_path)
dep = L.index * (0.3048 if L.curves[0].unit.upper().startswith('F') else 1.0)
def col(*names):
    for n in names:
        if n in L.keys(): return L[n], L.curves[n].unit
    raise KeyError(names)
rho_raw, ru = col('RHOB','DEN','RHOZ'); dt_raw, du = col('DT','AC','DTCO')
rho_ind = rho_raw/1000 if 'KG' in ru.upper() else rho_raw
dt_ind = dt_raw*0.3048 if du.upper().endswith('/M') else dt_raw
# 1) unit normalization: tool RHOB/DT (un-repaired samples) must equal independent conversion at same depth
ok = (rep==0)&(syn==0)
ri = np.interp(zm[ok], dep[~np.isnan(rho_ind)], rho_ind[~np.isnan(rho_ind)])
ti = np.interp(zm[ok], dep[~np.isnan(dt_ind)], dt_ind[~np.isnan(dt_ind)])
print('units      : RHOB max |tool-indep| = %.4f g/cc ; DT max |tool-indep| = %.3f us/ft  (RHOB unit %r, DT unit %r)' % (np.nanmax(abs(rhob[ok]-ri)), np.nanmax(abs(dt[ok]-ti)), ru, du))
# 2) overburden: independent trapezoidal integration of the tool's QC'd density, same seed rule
sv_ind = np.zeros_like(sv)
sed_top = max(0, zft[0]-(ag_ft+wd_ft))
sv_ind[0] = 0.433*1.03*max(0, min(wd_ft, zft[0]-ag_ft)) + 0.433*((1.95+rhob[0])/2)*sed_top
for i in range(1, len(sv)): sv_ind[i] = sv_ind[i-1] + 0.433*(rhob[i]+rhob[i-1])/2*max(zft[i]-zft[i-1], 0.1)
print('overburden : max rel. diff Sv tool vs independent = %.2e ; Sv @TD = %.0f psi (%.2f ppg, %.3f psi/ft)' % (np.max(abs(sv-sv_ind)/sv_ind), sv[-1], svg[-1], sv[-1]/zft[-1]))
# 3) Eaton: Pp = Sv - (Sv - Ph) (DTn/DTsm)^3, ratio capped [0.3, 1] (hydrostatic floor), Biot alpha 1
ratio = np.clip(dtn/np.maximum(dtsm, 40), 0.3, 1.0)
pp_ind = np.maximum(sv - (sv-ph)*ratio**3, ph)
m = ~np.isnan(dtsm)
print('Eaton Pp   : max |tool-indep| = %.3f psi ; Pp range %.2f-%.2f ppg ; %%hydrostatic floor %.1f' % (np.nanmax(abs(pp[m]-pp_ind[m])), np.nanmin(ppg), np.nanmax(ppg), 100*np.mean(pp<=ph+1e-6)))
# 4) Fracture gradient (Eaton, nu=0.25): Fg = K (Sv - Pp) + Pp, K = nu/(1-nu)
fg_ind = (0.25/0.75)*(svg-ppg)+ppg
print('Eaton Fg   : max |tool-indep| = %.4f ppg ; Fg range %.2f-%.2f ppg' % (np.nanmax(abs(fgg-fg_ind)), np.nanmin(fgg), np.nanmax(fgg)))
# 5) NCT form
nct = d['nct']; dtn_ind = nct['DTm'] + (max(nct['DTml'], nct['DTm']+20)-nct['DTm'])*np.exp(-nct['c']*zft)
print('NCT        : max |DTn tool-indep| = %.4f us/ft (DTm %.1f, DTml %.1f, c %.5f/ft, calibrated %s, R2 %s, span %s m)' % (np.nanmax(abs(dtn-dtn_ind)), nct['DTm'], nct['DTml'], nct['c'], nct['calibrated'], None if nct['r2'] is None else round(nct['r2'],3), nct['spanM']))
# 6) Matthews-Kelly: K_i at equivalent depth (Sv-Pp)/0.535, polynomial K = A z^2 + B z + C
zi = np.maximum(1,(sv-pp)/0.535); Kmk = np.clip(-3.0e-9*zi**2 + 8.0e-5*zi + 0.2347, 0, 2)
fgmk_ind = Kmk*(svg-ppg)+ppg
print('M&K Fg     : max |tool-indep| = %.4f ppg ; mean Fg(M&K) %.2f ppg' % (np.nanmax(abs(fgmk-fgmk_ind)), np.nanmean(fgmk)))
