// Reference data used by run-tests.js. Every value here is independent of the BASIRA engine.

/* Published API casing performance properties (API Bull. 5C2 / API TR 5C3 tables, as reproduced in
   OCTG manufacturer catalogues, e.g. Global Steel "Casing Performance Ratings – Imperial").
   [OD in, nominal weight lb/ft, grade, collapse psi, internal yield psi, pipe-body yield 1000 lbf]
   API rounds collapse and internal yield to the nearest 10 psi and body yield to the nearest 1000 lbf. */
const API_PIPES = [
  ["20",     94,   "K-55",   520,  2110, 1480],
  ["18.625", 87.5, "K-55",   630,  2250, 1367],
  ["16",     65,   "H-40",   630,  1640,  736],
  ["16",     75,   "K-55",  1020,  2630, 1178],
  ["16",     84,   "K-55",  1410,  2980, 1326],
  ["13.375", 54.5, "K-55",  1130,  2730,  853],
  ["13.375", 68,   "K-55",  1950,  3450, 1069],
  ["13.375", 68,   "L-80",  2260,  5020, 1556],
  ["13.375", 72,   "N-80",  2670,  5380, 1661],
  ["13.375", 72,   "P-110", 2880,  7400, 2284],
  ["9.625",  36,   "J-55",  2020,  3520,  564],
  ["9.625",  40,   "K-55",  2570,  3950,  630],
  ["9.625",  40,   "N-80",  3090,  5750,  916],
  ["9.625",  43.5, "N-80",  3810,  6330, 1005],
  ["9.625",  47,   "N-80",  4750,  6870, 1086],
  ["9.625",  47,   "P-110", 5300,  9440, 1493],
  ["9.625",  53.5, "P-110", 7950, 10900, 1710],
  ["7",      23,   "N-80",  3830,  6340,  532],
  ["7",      26,   "N-80",  5410,  7240,  604],
  ["7",      26,   "P-110", 6230,  9950,  830],
  ["7",      29,   "P-110", 8530, 11220,  929],
  ["7",      32,   "P-110",10780, 12460, 1025],
  ["7",      35,   "P-110",13020, 13700, 1119],
  ["5.5",    17,   "N-80",  6280,  7740,  397],
  ["5.5",    17,   "P-110", 7460, 10640,  546],
  ["5.5",    20,   "P-110",11100, 12640,  641],
  ["4.5",    11.6, "N-80",  6350,  7780,  267],
  ["4.5",    11.6, "P-110", 7580, 10690,  367],
];

/* API Bull. 5C3 Table 1 — empirical collapse factors and D/t regime limits by yield strength.
   [yield psi, A, B, C, F, G, (D/t)yp, (D/t)pt, (D/t)te] */
const API_FACTORS = [
  [ 55000, 2.991, 0.0541, 1206, 1.989, 0.0360, 14.81, 25.01, 37.21],
  [ 80000, 3.071, 0.0667, 1955, 1.998, 0.0434, 13.38, 22.47, 31.02],
  [110000, 3.181, 0.0819, 2852, 2.066, 0.0532, 12.44, 20.41, 26.22],
];

/* The Basrah-type development well shipped with the app (pore / fracture EMW, sg) */
const BASRAH_FORMATIONS = [
  [0, 1.03, 1.44], [450, 1.04, 1.58], [900, 1.08, 1.73], [1500, 1.13, 1.85],
  [2150, 1.25, 1.94], [2750, 1.39, 2.04], [3350, 1.51, 2.13], [3800, 1.57, 2.18]
];

module.exports = { API_PIPES, API_FACTORS, BASRAH_FORMATIONS };
