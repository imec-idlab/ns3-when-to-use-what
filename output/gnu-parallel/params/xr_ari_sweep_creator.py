import pandas as pd

# XR Access Request Interval (ARI) sweep, for every scheme that reads
# --muSchedAccessReqInterval (A2P, A2PV2, UORA, CMAB). EDCA has no OFDMA
# scheduler and is therefore excluded. Mirrors the IIoT ARI investigation
# ([[ari-selection]] memory) for the XR scenario.
#
# Output goes to a SEPARATE data root (xr_data_ari/, wired in job_script_xr.sh
# via the "<mode>_ari" MODE suffix -- see run_xr.sh) so it never collides with
# the baseline xr_data/ sweep, which already fixed ARI per scheme.

runs = range(1, 11)                          # 1..10
nSta = [1, 2, 3, 4, 5, 6, 7, 8]               # headset counts
ari  = [16, 32, 64, 128, 256, 512, 1024]      # muSchedAccessReqInterval (us)

# --- A2P / A2PV2 : run, nSta, ari -------------------------------------------
base = (pd.MultiIndex.from_product([runs, nSta, ari], names=["run", "nSta", "ari"])
        .to_frame(index=False))
for name in ["a2p", "a2pv2"]:
    base.to_csv(f"{name}_ari_xr_input.csv", index=False)
    print(f"wrote {name}_ari_xr_input.csv  rows={len(base)}")

# --- UORA : run, nSta, ari, nRaRus, OCwMin (full cross) ---------------------
# The best (nRaRus, OCwMin) per (ari, nSta) is picked in post-analysis (min
# pose deadline loss), the same selection rule as the baseline UORA sweep, so
# every combination must actually be simulated here rather than pre-selected.
nRaRus, OCwMin = [0, 1, 2, 3, 4], [1, 3, 7, 15, 31, 63]
uora = (pd.MultiIndex.from_product([runs, nSta, ari, nRaRus, OCwMin],
                                   names=["run", "nSta", "ari", "nRaRus", "OCwMin"])
        .to_frame(index=False))
uora.to_csv("uora_ari_xr_input.csv", index=False)
print(f"wrote uora_ari_xr_input.csv  rows={len(uora)}")

# --- CMAB : run, nSta, ari, algorithm, rewardType, ucbConstant, epsilon, exp3Gamma
# Full 26-variant grid crossed with ari (not restricted to the already-chosen
# CUCB/FairnessWeighted winner, per the explicit request to check whether ARI
# changes which variant wins).
cmab_variants = (
    [("CUCB", r, c, 0.1, 0.1) for r in ("Binary", "FairnessWeighted")
                              for c in (0.5, 1.41421, 2.0, 2.5)]
  + [("EXP3M", r, 1.41421, 0.1, g) for r in ("Binary", "FairnessWeighted")
                                   for g in (0.05, 0.1, 0.2, 0.3)]
  + [("EpsilonGreedy", r, 1.41421, e, 0.1) for r in ("Binary", "FairnessWeighted")
                                           for e in (0.05, 0.1, 0.2, 0.3)]
  + [("ThompsonSampling", r, 1.41421, 0.1, 0.1) for r in ("Binary", "FairnessWeighted")]
)
rows = []
for run in runs:
    for n in nSta:
        for a in ari:
            for algo, rew, c, e, g in cmab_variants:
                rows.append((run, n, a, algo, rew, c, e, g))
cmab = pd.DataFrame(rows, columns=["run", "nSta", "ari", "algorithm", "rewardType",
                                   "ucbConstant", "epsilon", "exp3Gamma"])
cmab.to_csv("cmab_ari_xr_input.csv", index=False)
print(f"wrote cmab_ari_xr_input.csv  rows={len(cmab)}  "
      f"({len(cmab_variants)} variants x {len(ari)} ari values)")
