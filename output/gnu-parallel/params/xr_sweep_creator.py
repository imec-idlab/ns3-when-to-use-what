import pandas as pd

# XR sweep. XR has no pMean; the only load axis is the headset count (nSta).
# Column name is `nSta` (job_script_xr.sh reads `nSta`, not IIoT's typeTwoNStations).
runs   = range(1, 11)              # 1..10
nSta   = [1, 2, 3, 4, 5, 6, 7, 8]       # headset counts (all verified crash-free at 80 MHz + ru-26-tone)

nRaRus = [0, 1, 2, 3, 4]
OCwMin = [1, 3, 7, 15, 31, 63]

# CMAB full sweep: 26 variants (matches the IIoT sweep families).
cmab_variants = (
    [("CUCB", r, c, 0.1, 0.1) for r in ("Binary", "FairnessWeighted")
                              for c in (0.5, 1.41421, 2.0, 2.5)]
  + [("EXP3M", r, 1.41421, 0.1, g) for r in ("Binary", "FairnessWeighted")
                                   for g in (0.05, 0.1, 0.2, 0.3)]
  + [("EpsilonGreedy", r, 1.41421, e, 0.1) for r in ("Binary", "FairnessWeighted")
                                           for e in (0.05, 0.1, 0.2, 0.3)]
  + [("ThompsonSampling", r, 1.41421, 0.1, 0.1) for r in ("Binary", "FairnessWeighted")]
)

# --- EDCA / A2P / A2PV2 : run, nSta ---------------------------------------
base = (pd.MultiIndex.from_product([runs, nSta], names=["run", "nSta"])
        .to_frame(index=False))
for name in ["edca", "a2p", "a2pv2"]:
    base.to_csv(f"{name}_xr_input.csv", index=False)
    print(f"wrote {name}_xr_input.csv  rows={len(base)}")

# --- UORA : run, nSta, nRaRus, OCwMin (full 6x6 cross) --------------------
uora = (pd.MultiIndex.from_product([runs, nSta, nRaRus, OCwMin],
                                   names=["run", "nSta", "nRaRus", "OCwMin"])
        .to_frame(index=False))
uora.to_csv("uora_xr_input.csv", index=False)
print(f"wrote uora_xr_input.csv  rows={len(uora)}")

# --- CMAB : run, nSta, algorithm, rewardType, ucbConstant, epsilon, exp3Gamma
rows = []
for run in runs:
    for n in nSta:
        for algo, rew, c, e, g in cmab_variants:
            rows.append((run, n, algo, rew, c, e, g))
cmab = pd.DataFrame(rows, columns=["run", "nSta", "algorithm", "rewardType",
                                   "ucbConstant", "epsilon", "exp3Gamma"])
cmab.to_csv("cmab_xr_input.csv", index=False)
print(f"wrote cmab_xr_input.csv  rows={len(cmab)}  ({len(cmab_variants)} variants)")
