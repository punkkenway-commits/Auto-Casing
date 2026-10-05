#!/usr/bin/env python3
"""Synthetic CBL/VDL logs with KNOWN ground truth, in three vendor formats.
Physics: casing amplitude A = A_free * (A_100/A_free)^BI (log bond-index law),
VDL = casing arrival (amp ∝ A) + formation arrival (amp ∝ coupling) + mud arrival.
Ground truth (MD, metres):
  1000-1480  free pipe (no cement)            BI 0.00-0.05
  1480       TOC
  1480-1600  good cement                      BI ~0.92
  1600-1640  channel (partial, irregular VDL) BI ~0.25 + noisy formation
  1640-1760  good cement                      BI ~0.90
  1760-1790  microannulus (low CBL, pipe VDL) BI ~0.70, strong pipe arrivals
  1790-2000  excellent cement                 BI ~0.97
"""
import numpy as np, sys, os
rng = np.random.default_rng(7)
OUT = sys.argv[1] if len(sys.argv) > 1 else '.'
A_FREE, A_100 = 61.0, 1.5          # 7" casing
z = np.arange(1000.0, 2000.0001, 0.1524)   # 0.5 ft sampling
n = len(z)
bi = np.zeros(n); zone = np.empty(n, dtype=object)
def setz(a, b, val, name, sd=0.02):
    m = (z >= a) & (z < b); bi[m] = np.clip(val + rng.normal(0, sd, m.sum()), 0, 1); zone[m] = name
setz(1000, 1480, 0.02, 'free', 0.015)
setz(1480, 1600, 0.92, 'good')
setz(1600, 1640, 0.25, 'channel', 0.08)
setz(1640, 1760, 0.90, 'good')
setz(1760, 1790, 0.70, 'microannulus', 0.03)
setz(1790, 2000.1, 0.97, 'excellent', 0.01)
amp = A_FREE * (A_100 / A_FREE) ** bi * (1 + rng.normal(0, 0.03, n))
gr = 60 + 45 * np.sin(z / 37.0) ** 2 + rng.normal(0, 4, n)
ccl = rng.normal(0, 0.05, n)
for c in np.arange(1003.0, 2000, 12.2):        # collars every 12.2 m
    i = np.argmin(abs(z - c)); ccl[max(0, i-1):i+2] += [1.2, 3.0, 1.2][:len(ccl[max(0, i-1):i+2])]
tt = 285 + rng.normal(0, 0.5, n)
tt[(z > 1700) & (z < 1712)] += 6 * np.sin(np.arange(((z > 1700) & (z < 1712)).sum()) / 2.0)   # decentralized patch
# VDL: 240 samples, 200-1200 us
t = np.linspace(200, 1200, 240)
def wavelet(t0, f=20e3, width=90):
    tt_ = (t - t0) * 1e-6
    return np.sin(2*np.pi*f*tt_) * np.exp(-((t - t0 - width/2) / width) ** 2) * (t >= t0 - 10)
vdl = np.zeros((n, 240))
for i in range(n):
    pipe = amp[i] / A_FREE
    if zone[i] == 'microannulus': pipe = max(pipe, 0.55)              # strong pipe ring despite low CBL
    coup = bi[i] if zone[i] != 'microannulus' else 0.15
    dtf = 115 + 25*np.sin(z[i]/53.0)                                    # formation slowness us/ft
    tf = 5*dtf + 120
    form = coup * (0.9 if zone[i] != 'channel' else rng.uniform(0.0, 1.2))
    w = 1.0*pipe*wavelet(250) + 0.8*pipe*wavelet(330, 21e3) + form*wavelet(tf, 12e3, 160) + 0.25*wavelet(1050, 9e3, 120)
    if zone[i] == 'channel': w += rng.normal(0, 0.25, 240) * (rng.random() < 0.5)
    vdl[i] = w * 100 + rng.normal(0, 1.0, 240)
truth = zone

def write(path, header, names, units, cols, desc=None, step=None):
    with open(path, 'w') as f:
        f.write(header)
        f.write('~Curve Information\n')
        for k, (nm, u) in enumerate(zip(names, units)):
            f.write(f' {nm:<10}.{u:<8} : {desc[k] if desc else nm}\n')
        f.write('~A\n')
        arr = np.column_stack(cols)
        for row in arr:
            f.write(' '.join(f'{v:.4f}' for v in row) + '\n')

# 1) Schlumberger-style, FEET, logged bottom-up, casing OD in ~P
order = np.argsort(-z)
zf = z / 0.3048
hdr = ('~Version Information\n VERS.  2.0 : CWLS LOG ASCII STANDARD - VERSION 2.0\n WRAP.  NO  :\n'
       '~Well Information\n'
       f' STRT.F {zf[order][0]:.4f} : START DEPTH\n STOP.F {zf[order][-1]:.4f} : STOP DEPTH\n STEP.F -0.5000 : STEP\n NULL.  -999.25 : NULL VALUE\n'
       ' COMP.  SYNTHETIC TEST OPERATOR : COMPANY\n WELL.  SYN-CBL-1 (synthetic ground truth) : WELL\n FLD .  TEST : FIELD\n SRVC.  Schlumberger : SERVICE COMPANY\n DATE.  2026-10-05 : LOG DATE\n'
       '~Parameter Information\n CSGO.IN 7.000 : Casing outside diameter\n BS  .IN 8.500 : Bit size\n')
names = ['DEPT', 'GR', 'CCL', 'TT', 'CBL'] + [f'VDL[{k}]' for k in range(240)]
units = ['F', 'GAPI', 'V', 'US', 'MV'] + ['MV'] * 240
cols = [zf[order], gr[order], ccl[order], tt[order], amp[order]] + [vdl[order, k] for k in range(240)]
write(os.path.join(OUT, 'SYN_SLB_CBL_VDL_ft_bottomup.las'), hdr, names, units, cols)

# 2) Baker Hughes SBT-style: attenuation in dB/ft (higher = better), metres, top-down
att_free, att_100 = 1.0, 12.0
atav = att_free + bi * (att_100 - att_free) + rng.normal(0, 0.15, n)
atc = np.column_stack([np.clip(atav + rng.normal(0, 0.4, n) - (k == 2) * ((zone == 'channel') * 7), 0, 20) for k in range(6)])
hdr2 = ('~Version Information\n VERS.  2.0 : CWLS LOG ASCII STANDARD - VERSION 2.0\n WRAP.  NO  :\n~Well Information\n'
        f' STRT.M {z[0]:.4f} : \n STOP.M {z[-1]:.4f} : \n STEP.M 0.1524 : \n NULL.  -999.25 : \n'
        ' COMP.  SYNTHETIC TEST OPERATOR : \n WELL.  SYN-SBT-1 (synthetic ground truth) : \n SRVC.  Baker Hughes : \n')
names2 = ['DEPT', 'GR', 'CCL', 'ATAV', 'ATMN', 'ATMX'] + [f'ATC{k+1}' for k in range(6)]
units2 = ['M', 'GAPI', 'V', 'DB/FT', 'DB/FT', 'DB/FT'] + ['DB/FT'] * 6
write(os.path.join(OUT, 'SYN_BHI_SBT_m.las'), hdr2, names2, units2, [z, gr, ccl, atav, atc.min(1), atc.max(1)] + [atc[:, k] for k in range(6)])

# 3) Weatherford RBT-style: BI in PERCENT, AM3F/AM5F, AMMP[0..71] azimuthal map
am3 = amp; am5 = amp * 10 ** (-(0.6 + 11 * bi) * 2 / 20)          # 2-ft extra path at α(BI)
bi_pct = np.clip(bi * 100 + rng.normal(0, 1.5, n), 0, 100)
ammp = np.tile(amp[:, None], (1, 72)) * (1 + rng.normal(0, 0.05, (n, 72)))
chan = zone == 'channel'
ammp[chan, 20:44] = A_FREE * 0.9                                    # 120° channel
ammp[~chan, :] = np.minimum(ammp[~chan, :], A_FREE)
hdr3 = ('~Version Information\n VERS.  2.0 : CWLS LOG ASCII STANDARD - VERSION 2.0\n WRAP.  NO  :\n~Well Information\n'
        f' STRT.M {z[0]:.4f} : \n STOP.M {z[-1]:.4f} : \n STEP.M 0.1524 : \n NULL.  -999.25 : \n'
        ' COMP.  SYNTHETIC TEST OPERATOR : \n WELL.  SYN-RBT-1 (synthetic ground truth) : \n SRVC.  Weatherford : \n')
names3 = ['DEPT', 'GR', 'CCL', 'TTAV', 'AM3F', 'AM5F', 'BI'] + [f'AMMP[{k}]' for k in range(72)]
units3 = ['M', 'GAPI', 'V', 'US', 'MV', 'MV', '%'] + ['MV'] * 72
write(os.path.join(OUT, 'SYN_WFT_RBT_m.las'), hdr3, names3, units3, [z, gr, ccl, tt, am3, am5, bi_pct] + [ammp[:, k] for k in range(72)])

np.savetxt(os.path.join(OUT, 'SYN_truth.csv'), np.column_stack([z, bi]), delimiter=',', header='depth_m,true_bi', comments='')
print('written', n, 'levels')
