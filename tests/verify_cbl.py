import json, sys, numpy as np
d=json.load(open(sys.argv[1])); att=sys.argv[2]=='att'; C=d['CAL']
z=np.array([r[0] for r in d['rows']]); raw=np.array([r[1] for r in d['rows']]); cbl=np.array([r[2] for r in d['rows']]); bi=np.array([r[3] for r in d['rows']]); cls=[r[4] for r in d['rows']]
if att: bi_i=np.clip((raw-C['af'])/(C['ab']-C['af']),0,1); cbl_i=C['f']*(C['b']/C['f'])**bi_i
else:   bi_i=np.clip(np.log(C['f']/np.maximum(raw,1e-3))/np.log(C['f']/C['b']),0,1); cbl_i=raw
E=np.log(80/10)/np.log(80/2); M=np.log(80/30)/np.log(80/2)
cls_i=np.where(bi_i>=E,'EXCELLENT',np.where(bi_i>=M,'MEDIUM',np.where(bi_i>=0.05,'POOR','FREE_PIPE')))
print('BI max|diff| %.2e  CBL(eq) max|diff| %.2e  class mismatches %d/%d  depth sorted %s' % (np.max(abs(bi-bi_i)), np.max(abs(cbl-cbl_i)), sum(a!=b for a,b in zip(cls,cls_i)), len(cls), bool(np.all(np.diff(z)>0))))
tr=np.loadtxt(sys.argv[3] if len(sys.argv)>3 else 'SYN_truth.csv',delimiter=',',skiprows=1); tbi=np.interp(z,tr[:,0],tr[:,1])
print('vs ground truth BI: mean abs error %.3f (calibration A_free %.1f / A_100 %.2f%s)' % (np.mean(abs(bi-tbi)), C['f'],C['b'], (', att %.1f/%.2f'%(C['af'],C['ab'])) if att else ''))
