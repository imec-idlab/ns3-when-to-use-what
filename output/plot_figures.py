#!/usr/bin/env python3
"""Generate the figures of the paper from the simulation results.

Usage
    python3 plot_figures.py                 # every section
    python3 plot_figures.py paper           # only the figures used in the paper
    python3 plot_figures.py conf            # one scenario: conf | iiot | xr
    python3 plot_figures.py xr_results iiot_t1_throughput
    python3 plot_figures.py --list          # list the sections

The script reads the per-run result directories (conf_data/, iiot_data/,
xr_data/, xr_data_ari_dlfirst/) and writes the figures to fig/. All paths are
relative to --data-dir, which defaults to the directory of this script.

Each section below is one self-contained plotting block. A section that
reuses the definitions of another one pulls it in automatically.
"""

import argparse
import os
import sys
import time
import traceback
import warnings
from pathlib import Path

SECTIONS = {
    'conf_e2e_delay_box'        : 'End-to-end delay box plot',
    'conf_wakeup_delay'         : 'Average wake-up delay',
    'conf_packet_loss'          : 'Packet loss ratio',
    'conf_results_row'          : 'Delay, wake-up delay and loss in one row',
    'conf_video_delay'          : 'Uplink video delay',
    'conf_video_heatmap'        : 'Uplink video heat maps',
    'conf_cmab_tuning_voice'    : 'CMAB hyper-parameter sweep, voice traffic',
    'conf_cmab_tuning_video'    : 'CMAB hyper-parameter sweep, video traffic',
    'iiot_cmab_tuning'          : 'CMAB hyper-parameter sweep',
    'iiot_ari'                  : 'Access request interval sweep (A2P, A2PV2)',
    'iiot_pmean_delay_tput'     : 'Traffic-intensity sweep: delay box plot and throughput',
    'iiot_pmean_loss'           : 'Traffic-intensity sweep: packet loss',
    'iiot_pmean_type1'          : 'Traffic-intensity sweep: type-1 delay and throughput',
    'iiot_pmean_grid'           : 'Traffic-intensity sweep: summary grid',
    'iiot_pmean_type1_grid'     : 'Traffic-intensity sweep: type-1 throughput grid',
    'iiot_type1_box_bars'       : 'Type-1 stations: box plots and bars',
    'iiot_type2_box_bars'       : 'Type-2 stations: box plots and bars',
    'iiot_type1_lines'          : 'Type-1 stations: line plots',
    'iiot_type2_lines'          : 'Type-2 stations: line plots',
    'iiot_box_per_sta'          : 'Per-station mean delay, side by side',
    'iiot_box_loss_grid'        : 'Per-packet delay and loss grid',
    'iiot_t1_throughput'        : 'Type-1 throughput',
    'xr_results'                : 'Pose delay, deadline misses and video throughput',
    'xr_cmab_tuning'            : 'CMAB hyper-parameter sweep',
    'xr_ari_cmab'               : 'Access request interval selection, CMAB',
    'xr_ari_uora'               : 'Access request interval selection, UORA',
    'xr_ari_a2p'                : 'Access request interval selection, A2P and A2PV2',
}

GROUPS = {
    "all":   list(SECTIONS),
    "paper": ['conf_results_row', 'conf_video_delay', 'conf_cmab_tuning_voice', 'iiot_box_loss_grid', 'iiot_t1_throughput', 'xr_results'],
    "conf":  [s for s in SECTIONS if s.startswith("conf_")],
    "iiot":  [s for s in SECTIONS if s.startswith("iiot_")],
    "xr":    [s for s in SECTIONS if s.startswith("xr_")],
}

# A section listed here needs the definitions of the sections it maps to.
DEPENDS = {'iiot_t1_throughput': ['iiot_box_loss_grid']}


def _parse_args():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("sections", nargs="*", default=["all"],
                   help="section or group names (default: all)")
    p.add_argument("--list", action="store_true", help="list the sections and exit")
    p.add_argument("--data-dir", default=Path(__file__).resolve().parent,
                   help="directory that holds the result directories and fig/")
    p.add_argument("--show", action="store_true",
                   help="open the figures in windows instead of only saving them")
    args = p.parse_args()
    if args.list:
        for name, text in SECTIONS.items():
            print(f"{name:26s} {text}")
        print("\ngroups: " + ", ".join(GROUPS))
        sys.exit(0)
    selected = []
    for item in args.sections:
        if item not in GROUPS and item not in SECTIONS:
            p.error(f"unknown section or group '{item}' (see --list)")
        for name in GROUPS.get(item, [item]):
            for need in DEPENDS.get(name, []) + [name]:
                if need not in selected:
                    selected.append(need)
    # Keep the order of the file, which is the order dependencies need.
    args.selected = [s for s in SECTIONS if s in selected]
    return args


_ARGS = _parse_args()
os.chdir(_ARGS.data_dir)

import matplotlib
if not _ARGS.show:
    matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

warnings.filterwarnings("ignore", message=".*non-interactive.*")

# Create the output directory of a figure when it does not exist yet.
_savefig = Figure.savefig
def _savefig_mkdir(self, fname, *args, **kwargs):
    if isinstance(fname, (str, os.PathLike)):
        Path(fname).parent.mkdir(parents=True, exist_ok=True)
    return _savefig(self, fname, *args, **kwargs)
Figure.savefig = _savefig_mkdir

_FAILED = []
_T0 = [0.0]

def _run(name):
    """Return True when the section is selected, and announce it."""
    if name not in _ARGS.selected:
        return False
    print(f"\n=== {name}: {SECTIONS[name]}", flush=True)
    _T0[0] = time.time()
    return True

def _done(name, error=None):
    if error is not None:
        _FAILED.append(name)
        traceback.print_exception(error)
    if not _ARGS.show:
        plt.close("all")
    state = "FAILED" if error is not None else "done"
    print(f"=== {name}: {state} in {time.time() - _T0[0]:.0f} s", flush=True)


# ============================================================================
# Conferencing scenario
# ============================================================================

# ---- conf_e2e_delay_box: End-to-end delay box plot ----
if _run("conf_e2e_delay_box"):
    try:
        from pathlib import Path
        import pandas as pd
        import matplotlib.pyplot as plt
        import seaborn as sns


        # ---------------- IEEE plot styling ----------------
        plt.rcParams.update({
            "font.size":        8,
            "axes.labelsize":   8,
            "xtick.labelsize":  7,
            "ytick.labelsize":  7,
            "legend.fontsize":  6,
            "lines.linewidth":  1.2,
            "lines.markersize": 4,
            "axes.linewidth":   0.6,
            "grid.linewidth":   0.4,
            "pdf.fonttype":     42,     # embed TrueType (no Type-3)
            "ps.fonttype":      42,
        })

        TEXTWIDTH_IN = 7.16                  # two-column figure* width; generate at 1:1


        # ---------------- Configuration ----------------
        RUNS = range(1, 7)
        NSTA_VALUES = range(8, 31)
        SELECTED_STAS = [8, 13, 18, 24, 30]

        nRaRus = [0, 1, 5, 9, 13, 18]
        OCwMin = [0, 1, 3, 7, 15, 31, 63]

        BASE_DIRS = {
            "EDCA":  Path("conf_data/edca"),
            "A2P":   Path("conf_data/a2p"),
            "A2PV2": Path("conf_data/a2pv2"),
        }

        # CMAB winner picked from fig/conference/cmab_hp_sweep_figs:
        # CUCB + Binary + c=0.5  -- lowest packet loss among HP-tunable algos
        # combined with ~70 ms video UL delay (lower than TS-Binary).
        CMAB_DIR     = Path("conf_data/cmab")
        CMAB_VARIANT = "CUCB_Binary_c0.5"
        CMAB_LABEL   = "CUCB"

        OUTPUT_CSV = "sns_data.csv"


        # ---------------- Helpers ----------------
        def read_csv(path: Path):
            if not path.exists():
                return None
            df = pd.read_csv(path, delimiter="\t")
            if df.dropna(how="all").empty:
                return None
            return df

        def e2e_path(method, run, nsta):
            return BASE_DIRS[method] / f"{run}_run-{nsta}_sta" / "all_packets_e2e.out"

        def uora_path(run, nsta, raru, ocw):
            return Path("conf_data/uora") / f"ocwMin_{ocw}" / f"{run}_run-{nsta}_sta-{raru}_rarus" / "all_packets_e2e.out"

        def cmab_path(run, nsta):
            return CMAB_DIR / CMAB_VARIANT / f"{run}_run-{nsta}_sta" / "all_packets_e2e.out"


        # ---------------- Processing standard methods ----------------
        def process_method(method):
            rows = []
            for run in RUNS:
                for nsta in NSTA_VALUES:
                    df = read_csv(e2e_path(method, run, nsta))
                    if df is None or "E2E_Delay_ms" not in df.columns:
                        continue
                    df = df[["E2E_Delay_ms"]].copy()
                    df["nSta"] = nsta
                    df["Method"] = method
                    rows.append(df)
            return rows


        # ---------------- Processing UORA (raru=0 doubles as SA OFDMA) ----------------
        def process_uora():
            rows = []
            for run in RUNS:
                for nsta in NSTA_VALUES:
                    for raru in nRaRus:
                        for ocw in OCwMin:
                            # OCW only matters when there's a random-access path:
                            #   raru==0 -> only read ocwMin_0/ (placeholder OCW)
                            #   raru>0  -> skip ocwMin_0/, sweep the real OCWs
                            if (raru == 0) != (ocw == 0):
                                continue
                            df = read_csv(uora_path(run, nsta, raru, ocw))
                            if df is None or "E2E_Delay_ms" not in df.columns:
                                continue
                            df = df[["E2E_Delay_ms"]].copy()
                            df["nSta"]   = nsta
                            df["Method"] = "SA_OFDMA" if raru == 0 else "UORA"
                            df["RA_RU"]  = raru
                            df["OCW"]    = ocw
                            rows.append(df)
            return rows


        # ---------------- Processing CMAB (winner only) ----------------
        def process_cmab():
            rows = []
            for run in RUNS:
                for nsta in NSTA_VALUES:
                    df = read_csv(cmab_path(run, nsta))
                    if df is None or "E2E_Delay_ms" not in df.columns:
                        continue
                    df = df[["E2E_Delay_ms"]].copy()
                    df["nSta"] = nsta
                    df["Method"] = "CMAB"
                    rows.append(df)
            return rows


        # ---------------- Run all ----------------
        all_rows = []
        for method in BASE_DIRS:
            print(f"[INFO] Processing {method}")
            all_rows.extend(process_method(method))

        print("[INFO] Processing UORA (incl. SA OFDMA at raru=0)")
        all_rows.extend(process_uora())

        print(f"[INFO] Processing CMAB ({CMAB_VARIANT})")
        all_rows.extend(process_cmab())

        if not all_rows:
            raise RuntimeError("No data collected.")

        dplt = pd.concat(all_rows, ignore_index=True)


        # ---------------- Save CSV ----------------
        dplt.to_csv(OUTPUT_CSV, index=False)
        print(f"[OK] CSV written to {OUTPUT_CSV}")


        # ---------------- For UORA only: pick best OCW per (nSta, RA_RU) ----------------
        # SA OFDMA has no OCW dependence (no random access), so we take all its rows
        # directly. UORA (raru>0) still gets the best-OCW selection per (nSta, raru).
        uora_only = dplt[dplt["Method"] == "UORA"]
        if not uora_only.empty:
            grouped = (
                uora_only
                .groupby(["nSta", "RA_RU", "OCW"])["E2E_Delay_ms"]
                .median()
                .reset_index()
            )
            idx = grouped.groupby(["nSta", "RA_RU"])["E2E_Delay_ms"].idxmin()
            best_uora_keys = grouped.loc[idx][["nSta", "RA_RU", "OCW"]]
            uora_best = uora_only.merge(best_uora_keys, on=["nSta", "RA_RU", "OCW"], how="inner")
        else:
            uora_best = pd.DataFrame(columns=["nSta", "RA_RU", "OCW", "E2E_Delay_ms", "Method"])
            print("[WARN] No UORA rows.")

        # SA OFDMA: only one OCW (placeholder 0), so just pass through.
        sa_best = dplt[dplt["Method"] == "SA_OFDMA"].copy()


        # ---------------- Combine datasets ----------------
        std_df = dplt[dplt["Method"].isin(list(BASE_DIRS) + ["CMAB"])].copy()
        std_df["Label"] = std_df["Method"].replace({"CMAB": CMAB_LABEL})

        sa_best["Label"] = "SA OFDMA"

        uora_best = uora_best.copy()
        if not uora_best.empty:
            uora_best["Label"] = uora_best["RA_RU"].apply(
                lambda x: f"{int(x)} RA RU" if x == 1 else f"{int(x)} RA RUs"
            )

        combined_df = pd.concat([std_df, sa_best, uora_best], ignore_index=True)


        # ---------------- Filter STAs ----------------
        combined_df = combined_df[combined_df["nSta"].isin(SELECTED_STAS)]


        # ---------------- Plot ----------------
        fig, ax = plt.subplots(figsize=(3.5, 2.6))

        sns.boxplot(
            data=combined_df,
            x="nSta",
            y="E2E_Delay_ms",
            hue="Label",
            showfliers=True,
            whis=3.0,
            width=0.8,
            linewidth=0.5,          # thin box outlines
            fliersize=1.2,          # small outlier markers
            palette="tab10",
            saturation=1.0,
            ax=ax,
        )

        ax.set_xlabel("Number of active STAs")
        ax.set_ylabel("End-to-end delay (ms)")

        # ----- y-axis: show only the min label, dotted grid at 6/8/10/12 -----
        YMIN = 4                                     # lower bound
        ax.set_ylim(bottom=YMIN)
        ax.set_yticks([YMIN, 5, 6, 7, 8, 9, 10, 11, 12])
        ax.set_yticklabels([str(YMIN), "", "6", "", "8", "", "10", "", "12"])

        # dashed x-grid, dotted y-grid at the ticks above
        ax.grid(False)
        ax.grid(True, axis="x", linestyle="--", linewidth=0.4)
        ax.grid(True, axis="y", linestyle=":",  linewidth=0.6, alpha=0.7)


        ax.legend(title=None, ncol=2, loc="best")

        fig.savefig("fig/conference/conf_boxplot_e2e_delay.pdf", bbox_inches="tight")
        plt.show()
        plt.close()

        print("[OK] Filtered boxplot saved (PDF).")
        _done("conf_e2e_delay_box")
    except Exception as _err:
        _done("conf_e2e_delay_box", _err)

# ---- conf_wakeup_delay: Average wake-up delay ----
if _run("conf_wakeup_delay"):
    try:
        from pathlib import Path
        import pandas as pd
        import numpy as np
        import matplotlib.pyplot as plt

        # ---------------- IEEE plot styling (single column) ----------------
        plt.rcParams.update({
            "font.size":        8,
            "axes.labelsize":   8,
            "xtick.labelsize":  7,
            "ytick.labelsize":  7,
            "legend.fontsize":  6,
            "lines.linewidth":  1.2,
            "lines.markersize": 4,
            "axes.linewidth":   0.6,
            "grid.linewidth":   0.4,
            "pdf.fonttype":     42,     # embed TrueType (no Type-3)
            "ps.fonttype":      42,
        })
        COLWIDTH_IN = 3.5              # single-column IEEE width; generate at 1:1

        # ---------------- Configuration ----------------
        BASE_DIRS = {
            "EDCA":  Path("conf_data/edca"),
            "A2P":   Path("conf_data/a2p"),
            "A2PV2": Path("conf_data/a2pv2"),      # fixed path (was "2pv2")
        }

        RUNS = range(1, 7)
        NSTA_VALUES = range(1, 101)

        nRaRus = [0, 1, 5, 9, 13, 18]
        OCwMin = [0, 1, 3, 7, 15, 31, 63]

        # CMAB winner picked from fig/conference/cmab_hp_sweep_figs:
        # CUCB + Binary + c=0.5 -- lowest packet loss among HP-tunable algos
        # combined with ~70 ms video UL delay (lower than TS-Binary).
        CMAB_DIR     = Path("conf_data/cmab")
        CMAB_VARIANT = "CUCB_Binary_c0.5"
        CMAB_LABEL   = "CUCB"

        OUT_FIG    = Path("fig/conference/conf_AverageWakeupDelay.pdf")
        OUT_STATS  = Path("fig/conference/conf_AverageWakeupDelay_stats.csv")
        ERROR_KIND = "std"   # "std" or "sem"; both columns are written to the CSV

        # ---------------- Helpers ----------------
        def read_csv(path: Path):
            if not path.exists():
                return None
            df = pd.read_csv(path, delimiter="\t")
            if df.dropna(how="all").empty:
                return None
            return df

        def uora_path(run, nsta, raru, ocw):
            return Path("conf_data/uora") / f"ocwMin_{ocw}" / f"{run}_run-{nsta}_sta-{raru}_rarus" / "wakeup_packet_stats"

        def cmab_path(run, nsta):
            return CMAB_DIR / CMAB_VARIANT / f"{run}_run-{nsta}_sta" / "wakeup_packet_stats"

        def aggregate(per_run_df, group_cols):
            """Aggregate a frame of one-mean-per-run across runs."""
            g = per_run_df.groupby(group_cols)["Delay_ms"]
            out = g.agg(
                mean="mean", std="std", n="count", median="median",
                p25=lambda s: s.quantile(0.25),
                p75=lambda s: s.quantile(0.75),
            ).reset_index()
            out["sem"] = out["std"] / np.sqrt(out["n"].clip(lower=1))
            return out

        # ---------------- Collect data ----------------
        all_rows = []

        for method, base_path in BASE_DIRS.items():
            for run in RUNS:
                for nSta in NSTA_VALUES:
                    df = read_csv(base_path / f"{run}_run-{nSta}_sta" / "wakeup_packet_stats")
                    if df is None or "Delay_ms" not in df.columns:
                        continue
                    df["nSta"], df["Run"], df["Method"] = nSta, run, method
                    all_rows.append(df)

        for run in RUNS:
            for nSta in NSTA_VALUES:
                df = read_csv(cmab_path(run, nSta))
                if df is None or "Delay_ms" not in df.columns:
                    continue
                df["nSta"], df["Run"], df["Method"] = nSta, run, "CMAB"
                all_rows.append(df)

        for run in RUNS:
            for nSta in NSTA_VALUES:
                for raru in nRaRus:
                    for ocw in OCwMin:
                        if (raru == 0) != (ocw == 0):     # OCW only matters with a RA path
                            continue
                        df = read_csv(uora_path(run, nSta, raru, ocw))
                        if df is None or "Delay_ms" not in df.columns:
                            continue
                        df["nSta"], df["Run"], df["Method"] = nSta, run, "UORA"
                        df["RA_RU"], df["OCW"] = raru, ocw
                        all_rows.append(df)

        if not all_rows:
            raise RuntimeError("No wakeup data found!")

        data = pd.concat(all_rows, ignore_index=True)

        # ---------------- Per-run means ----------------
        per_run_std = (data[data["Method"] != "UORA"]
                       .groupby(["Method", "nSta", "Run"], as_index=False)["Delay_ms"].mean())
        agg_std = aggregate(per_run_std, ["Method", "nSta"])

        per_run_uora = (data[data["Method"] == "UORA"]
                        .groupby(["nSta", "RA_RU", "OCW", "Run"], as_index=False)["Delay_ms"].mean())

        if not per_run_uora.empty:
            median_per_cell = (per_run_uora
                               .groupby(["nSta", "RA_RU", "OCW"], as_index=False)["Delay_ms"].median())
            idx = median_per_cell.groupby(["nSta", "RA_RU"])["Delay_ms"].idxmin()
            best_keys = median_per_cell.loc[idx][["nSta", "RA_RU", "OCW"]]
            per_run_best = per_run_uora.merge(best_keys, on=["nSta", "RA_RU", "OCW"], how="inner")
            agg_uora = aggregate(per_run_best, ["nSta", "RA_RU"])
        else:
            agg_uora = pd.DataFrame(columns=["nSta", "RA_RU", "mean", "std", "n", "median", "p25", "p75", "sem"])
            print("[WARN] No UORA wakeup rows found")

        # ---------------- Write per-curve stats ----------------
        out_csv = []
        for _, row in agg_std.iterrows():
            out_csv.append({"curve": row["Method"], "nSta": row["nSta"],
                            "mean": row["mean"], "std": row["std"], "sem": row["sem"],
                            "median": row["median"], "p25": row["p25"], "p75": row["p75"], "n_runs": row["n"]})
        for _, row in agg_uora.iterrows():
            curve = "SA OFDMA" if row["RA_RU"] == 0 else (
                f"{int(row['RA_RU'])} RA RU" if row["RA_RU"] == 1 else f"{int(row['RA_RU'])} RA RUs")
            out_csv.append({"curve": curve, "nSta": row["nSta"],
                            "mean": row["mean"], "std": row["std"], "sem": row["sem"],
                            "median": row["median"], "p25": row["p25"], "p75": row["p75"], "n_runs": row["n"]})
        OUT_STATS.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(out_csv).to_csv(OUT_STATS, index=False)
        print(f"[OK] Stats written to {OUT_STATS}")

        # ---------------- Plot ----------------
        fig, ax = plt.subplots(figsize=(COLWIDTH_IN, 2.6))

        def yerr(df):
            return df[ERROR_KIND]

        standard_markers = {
            "EDCA":  ("o", "EDCA"),
            "A2P":   ("s", "A2P"),
            "A2PV2": ("D", "A2PV2"),
            "CMAB":  ("*", CMAB_LABEL),
        }
        for method, (marker, label) in standard_markers.items():
            df_m = agg_std[agg_std["Method"] == method].sort_values("nSta")
            if df_m.empty:
                continue
            ax.errorbar(df_m["nSta"], df_m["mean"], yerr=yerr(df_m),
                        marker=marker, linewidth=1.2,
                        markersize=5 if method == "CMAB" else 4,
                        capsize=2, label=label)

        sa_ofdma = agg_uora[agg_uora["RA_RU"] == 0].sort_values("nSta")
        if not sa_ofdma.empty:
            ax.errorbar(sa_ofdma["nSta"], sa_ofdma["mean"], yerr=yerr(sa_ofdma),
                        marker="^", linewidth=1.2, markersize=4, capsize=2, label="SA OFDMA")

        for raru in nRaRus:
            if raru == 0:
                continue
            df_u = agg_uora[agg_uora["RA_RU"] == raru].sort_values("nSta")
            if df_u.empty:
                continue
            ax.errorbar(df_u["nSta"], df_u["mean"], yerr=yerr(df_u),
                        linestyle="--", marker="o", markersize=3, linewidth=1.2, capsize=1.5,
                        label=f"{raru} RA RU" if raru == 1 else f"{raru} RA RUs")

        # ---------------- Styling ----------------
        ax.set_xlabel("Number of active STAs")
        ax.set_ylabel("Average wake-up delay (ms)")
        ax.grid(True, linestyle="--", linewidth=0.4)
        ax.set_xticks(list(range(9, 30, 2)))

        ax.legend(ncol=2, loc="best", fontsize=6)

        fig.savefig(OUT_FIG, bbox_inches="tight")
        plt.show()
        plt.close()

        print(f"[OK] Figure saved to {OUT_FIG}")
        _done("conf_wakeup_delay")
    except Exception as _err:
        _done("conf_wakeup_delay", _err)

# ---- conf_packet_loss: Packet loss ratio ----
if _run("conf_packet_loss"):
    try:
        from pathlib import Path
        import pandas as pd
        import numpy as np
        import matplotlib.pyplot as plt

        # ---------------- IEEE plot styling (single column) ----------------
        plt.rcParams.update({
            "font.size":        8,
            "axes.labelsize":   8,
            "xtick.labelsize":  7,
            "ytick.labelsize":  7,
            "legend.fontsize":  6,
            "lines.linewidth":  1.2,
            "lines.markersize": 4,
            "axes.linewidth":   0.6,
            "grid.linewidth":   0.4,
            "pdf.fonttype":     42,     # embed TrueType (no Type-3)
            "ps.fonttype":      42,
        })
        COLWIDTH_IN = 3.5              # single-column IEEE width; generate at 1:1

        # ---------------- Configuration ----------------
        BASE_DIRS = {
            "EDCA":  Path("conf_data/edca"),
            "A2P":   Path("conf_data/a2p"),
            "A2PV2": Path("conf_data/a2pv2"),
            # OFDMA removed -- now lives inside uora/ as the raru=0 case.
        }

        RUNS = range(1, 7)
        NSTA_VALUES = range(1, 101)
        AP_MAC = "00:00:00:00:00:65"
        OUT_FIG    = Path("fig/conference/conf_PacketLossRatio.pdf")
        OUT_STATS  = Path("fig/conference/conf_PacketLossRatio_stats.csv")
        ERROR_KIND = "std"   # "std" or "sem"

        nRaRus = [0, 1, 5, 9, 13, 18]
        OCwMin = [0, 1, 3, 7, 15, 31, 63]

        # CMAB winner picked from fig/conference/cmab_hp_sweep_figs:
        # CUCB + Binary + c=0.5 -- lowest packet loss among HP-tunable algos
        # combined with ~70 ms video UL delay (lower than TS-Binary).
        CMAB_DIR     = Path("conf_data/cmab")
        CMAB_VARIANT = "CUCB_Binary_c0.5"
        CMAB_LABEL   = "CUCB"

        # ---------------- Helpers ----------------
        def read_csv(path: Path):
            if not path.exists():
                return None
            df = pd.read_csv(path, delimiter="\t")
            if df.dropna(how="all").empty:
                return None
            return df

        def uora_path(run, nsta, raru, ocw):
            return Path("conf_data/uora") / f"ocwMin_{ocw}" / f"{run}_run-{nsta}_sta-{raru}_rarus" / "per_sta_stats.out"

        def cmab_path(run, nsta):
            return CMAB_DIR / CMAB_VARIANT / f"{run}_run-{nsta}_sta" / "per_sta_stats.out"

        def aggregate(per_run_df, group_cols, metric="Packet_loss_ratio"):
            """Per-run values → mean / std / sem / median / p25 / p75 / n across runs."""
            g = per_run_df.groupby(group_cols)[metric]
            out = g.agg(
                mean="mean", std="std", n="count", median="median",
                p25=lambda s: s.quantile(0.25),
                p75=lambda s: s.quantile(0.75),
            ).reset_index()
            out["sem"] = out["std"] / np.sqrt(out["n"].clip(lower=1))
            return out

        # ---------------- Collect data (one AP row per run) ----------------
        all_rows = []

        for method, base_path in BASE_DIRS.items():
            for run in RUNS:
                for nSta in NSTA_VALUES:
                    df = read_csv(base_path / f"{run}_run-{nSta}_sta" / "per_sta_stats.out")
                    if df is None:
                        continue
                    df_ap = df[df["MAC-addr"] == AP_MAC].copy()
                    if df_ap.empty:
                        continue
                    df_ap["nSta"], df_ap["Run"], df_ap["Method"] = nSta, run, method
                    all_rows.append(df_ap)

        for run in RUNS:
            for nSta in NSTA_VALUES:
                df = read_csv(cmab_path(run, nSta))
                if df is None:
                    continue
                df_ap = df[df["MAC-addr"] == AP_MAC].copy()
                if df_ap.empty:
                    continue
                df_ap["nSta"], df_ap["Run"], df_ap["Method"] = nSta, run, "CMAB"
                all_rows.append(df_ap)

        for run in RUNS:
            for nSta in NSTA_VALUES:
                for raru in nRaRus:
                    for ocw in OCwMin:
                        if (raru == 0) != (ocw == 0):        # OCW only matters with a RA path
                            continue
                        df = read_csv(uora_path(run, nSta, raru, ocw))
                        if df is None:
                            continue
                        df_ap = df[df["MAC-addr"] == AP_MAC].copy()
                        if df_ap.empty:
                            continue
                        df_ap["nSta"], df_ap["Run"], df_ap["Method"] = nSta, run, "UORA"
                        df_ap["RA_RU"], df_ap["OCW"] = raru, ocw
                        all_rows.append(df_ap)

        if not all_rows:
            raise RuntimeError("No per_sta_stats.out data found for AP MAC!")

        data = pd.concat(all_rows, ignore_index=True)
        data["Packet_loss_ratio"] = pd.to_numeric(data["Packet_loss_ratio"], errors="coerce")

        # ---------------- Aggregate standard methods + CMAB ----------------
        agg_std = aggregate(data[data["Method"] != "UORA"], ["Method", "nSta"])

        # ---------------- Aggregate UORA: best OCW per (nSta, RA_RU) by MEAN ----------------
        uora_only = data[data["Method"] == "UORA"]
        if not uora_only.empty:
            mean_per_cell = (uora_only
                             .groupby(["nSta", "RA_RU", "OCW"], as_index=False)["Packet_loss_ratio"].mean())
            idx = mean_per_cell.groupby(["nSta", "RA_RU"])["Packet_loss_ratio"].idxmin()
            best_keys = mean_per_cell.loc[idx][["nSta", "RA_RU", "OCW"]]
            uora_best_runs = uora_only.merge(best_keys, on=["nSta", "RA_RU", "OCW"], how="inner")
            agg_uora = aggregate(uora_best_runs, ["nSta", "RA_RU"])
        else:
            agg_uora = pd.DataFrame(columns=["nSta", "RA_RU", "mean", "std", "n", "median", "p25", "p75", "sem"])
            print("[WARN] No UORA rows.")

        # ---------------- Write per-curve stats ----------------
        out_csv = []
        for _, row in agg_std.iterrows():
            out_csv.append({"curve": row["Method"], "nSta": row["nSta"],
                            "mean": row["mean"], "std": row["std"], "sem": row["sem"],
                            "median": row["median"], "p25": row["p25"], "p75": row["p75"], "n_runs": row["n"]})
        for _, row in agg_uora.iterrows():
            curve = "SA OFDMA" if row["RA_RU"] == 0 else (
                f"{int(row['RA_RU'])} RA RU" if row["RA_RU"] == 1 else f"{int(row['RA_RU'])} RA RUs")
            out_csv.append({"curve": curve, "nSta": row["nSta"],
                            "mean": row["mean"], "std": row["std"], "sem": row["sem"],
                            "median": row["median"], "p25": row["p25"], "p75": row["p75"], "n_runs": row["n"]})
        OUT_STATS.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(out_csv).to_csv(OUT_STATS, index=False)
        print(f"[OK] Stats written to {OUT_STATS}")

        # ---------------- Plot ----------------
        fig, ax = plt.subplots(figsize=(COLWIDTH_IN, 2.6))

        def yerr(df):
            return df[ERROR_KIND]

        standard_markers = {
            "EDCA":  ("o", "EDCA"),
            "A2P":   ("s", "A2P"),
            "A2PV2": ("D", "A2PV2"),
            "CMAB":  ("*", CMAB_LABEL),
        }
        for method, (marker, label) in standard_markers.items():
            df_m = agg_std[agg_std["Method"] == method].sort_values("nSta")
            if df_m.empty:
                continue
            ax.errorbar(df_m["nSta"], df_m["mean"], yerr=yerr(df_m),
                        marker=marker, linewidth=1.2,
                        markersize=5 if method == "CMAB" else 4,
                        capsize=2, label=label)

        sa_ofdma = agg_uora[agg_uora["RA_RU"] == 0].sort_values("nSta")
        if not sa_ofdma.empty:
            ax.errorbar(sa_ofdma["nSta"], sa_ofdma["mean"], yerr=yerr(sa_ofdma),
                        marker="^", linewidth=1.2, markersize=4, capsize=2, label="SA OFDMA")

        for raru in nRaRus:
            if raru == 0:
                continue
            df_u = agg_uora[agg_uora["RA_RU"] == raru].sort_values("nSta")
            if df_u.empty:
                continue
            ax.errorbar(df_u["nSta"], df_u["mean"], yerr=yerr(df_u),
                        linestyle="--", marker="o", markersize=3, linewidth=1.2, capsize=1.5,
                        label=f"{raru} RA RU" if raru == 1 else f"{raru} RA RUs")

        # ---------------- Styling ----------------
        ax.set_xlabel("Number of active STAs")
        ax.set_ylabel("Average packet loss ratio")
        ax.grid(True, linestyle="--", linewidth=0.4)
        ax.set_xticks([8, 13, 19, 25, 30])

        ax.legend(ncol=2, loc="best", fontsize=6)

        fig.savefig(OUT_FIG, bbox_inches="tight")
        plt.show()
        plt.close()

        print(f"[OK] Figure saved to {OUT_FIG}")
        _done("conf_packet_loss")
    except Exception as _err:
        _done("conf_packet_loss", _err)

# ---- conf_results_row: Delay, wake-up delay and loss in one row ----
if _run("conf_results_row"):
    try:
        from pathlib import Path
        import numpy as np
        import pandas as pd
        import matplotlib.pyplot as plt
        import seaborn as sns
        from matplotlib.lines import Line2D

        # ---------------- IEEE styling ----------------
        plt.rcParams.update({
            "font.size":        8,
            "axes.labelsize":   8,
            "axes.titlesize":   8,
            "xtick.labelsize":  7,
            "ytick.labelsize":  7,
            "legend.fontsize":  7,
            "lines.linewidth":  0.9,     # thinner lines
            "lines.markersize": 3,       # smaller markers
            "axes.linewidth":   0.6,
            "grid.linewidth":   0.4,
            "pdf.fonttype":     42,
            "ps.fonttype":      42,
        })
        TEXTWIDTH_IN = 7.16                       # two-column figure* width (1:1)

        # ---------------- Configuration ----------------
        A2PV2_DIR = "a2pv2"                       # NOTE: your loss script used "QoSNullinBasicTfa2pv2" -- set the right one
        BASE_DIRS = {
            "EDCA":  Path("conf_data/edca"),
            "A2P":   Path("conf_data/a2p"),
            "A2S": Path(f"conf_data/{A2PV2_DIR}"),
        }
        RUNS = range(1, 7)
        NSTA_VALUES = range(1, 101)
        SELECTED_STAS = [8, 13, 18, 24, 30]       # boxplot groups + line x-range
        AP_MAC = "00:00:00:00:00:65"
        ERROR_KIND = "std"                        # "std" or "sem"

        nRaRus = [0, 1, 5, 9, 13, 18]             # trim to e.g. [0, 1, 18] to declutter
        OCwMin = [0, 1, 3, 7, 15, 31, 63]

        CMAB_DIR     = Path("conf_data/cmab")
        CMAB_VARIANT = "CUCB_Binary_c0.5"
        CMAB_LABEL   = "CUCB"

        OUT_FIG = Path("fig/conference/conf_results_row.pdf")

        # ---------------- Consistent scheme styling ----------------
        LABEL_ORDER = ["EDCA", "A2P", "A2S", CMAB_LABEL, "SA OFDMA",
                       "1 RA RU", "5 RA RUs", "9 RA RUs", "13 RA RUs", "18 RA RUs"]
        _cols  = plt.get_cmap("tab10").colors
        COLORS = {lbl: _cols[i % 10] for i, lbl in enumerate(LABEL_ORDER)}
        MARKER = {"EDCA": "o", "A2P": "s", "A2S": "D", CMAB_LABEL: "*", "SA OFDMA": "^"}

        def line_style(lbl):
            if lbl in MARKER:                     # standard methods + SA OFDMA -> solid
                return dict(color=COLORS[lbl], marker=MARKER[lbl], linestyle="-")
            return dict(color=COLORS[lbl], marker="o", linestyle="--")   # UORA RA-RUs -> dashed

        def raru_label(x):
            return "SA OFDMA" if x == 0 else (f"{int(x)} RA RU" if x == 1 else f"{int(x)} RA RUs")

        # ---------------- IO helpers ----------------
        def read_csv(path: Path):
            if not path.exists():
                return None
            df = pd.read_csv(path, delimiter="\t")
            return None if df.dropna(how="all").empty else df

        def std_path(base, run, n, fname):   return base / f"{run}_run-{n}_sta" / fname
        def cmab_path(run, n, fname):        return CMAB_DIR / CMAB_VARIANT / f"{run}_run-{n}_sta" / fname
        def uora_path(run, n, raru, ocw, fname):
            return Path("conf_data/uora") / f"ocwMin_{ocw}" / f"{run}_run-{n}_sta-{raru}_rarus" / fname

        # ---------------- Scalar-metric curves (wake-up, loss) ----------------
        def scalar_curves(fname, extract, best_by):
            """Return DataFrame[Label, nSta, mean, err] for all schemes."""
            srows, urows = [], []
            def add(label, pathf):
                for run in RUNS:
                    for n in NSTA_VALUES:
                        v = extract(read_csv(pathf(run, n)))
                        if v is not None and not np.isnan(v):
                            srows.append({"Label": label, "nSta": n, "Run": run, "val": v})
            for m, base in BASE_DIRS.items():
                add(m, lambda r, n, base=base: std_path(base, r, n, fname))
            add(CMAB_LABEL, lambda r, n: cmab_path(r, n, fname))
            for run in RUNS:
                for n in NSTA_VALUES:
                    for raru in nRaRus:
                        for ocw in OCwMin:
                            if (raru == 0) != (ocw == 0):
                                continue
                            v = extract(read_csv(uora_path(run, n, raru, ocw, fname)))
                            if v is not None and not np.isnan(v):
                                urows.append({"nSta": n, "RA_RU": raru, "OCW": ocw, "Run": run, "val": v})

            def agg(df, keys):
                a = df.groupby(keys)["val"].agg(mean="mean", std="std", n="count").reset_index()
                a["sem"] = a["std"] / np.sqrt(a["n"].clip(lower=1))
                a["err"] = a["std"] if ERROR_KIND == "std" else a["sem"]
                return a

            out = []
            s = pd.DataFrame(srows)
            if not s.empty:
                for _, r in agg(s, ["Label", "nSta"]).iterrows():
                    out.append({"Label": r["Label"], "nSta": r["nSta"], "mean": r["mean"], "err": r["err"]})
            u = pd.DataFrame(urows)
            if not u.empty:
                cell = u.groupby(["nSta", "RA_RU", "OCW"])["val"].agg(best_by).reset_index()
                idx = cell.groupby(["nSta", "RA_RU"])["val"].idxmin()
                best = u.merge(cell.loc[idx][["nSta", "RA_RU", "OCW"]], on=["nSta", "RA_RU", "OCW"])
                for _, r in agg(best, ["nSta", "RA_RU"]).iterrows():
                    out.append({"Label": raru_label(r["RA_RU"]), "nSta": r["nSta"],
                                "mean": r["mean"], "err": r["err"]})
            return pd.DataFrame(out)

        def extract_wakeup(d):
            if d is None or "Delay_ms" not in d.columns:
                return np.nan
            s = d["Delay_ms"].dropna()
            return float(s.mean()) if not s.empty else np.nan

        def extract_loss(d):
            if d is None or "MAC-addr" not in d.columns:
                return np.nan
            ap = d[d["MAC-addr"] == AP_MAC]
            if ap.empty:
                return np.nan
            return float(pd.to_numeric(ap["Packet_loss_ratio"], errors="coerce").iloc[0])

        # ---------------- E2E delay distribution (boxplot) ----------------
        def e2e_boxdata():
            rows, urows = [], []
            def add(label, pathf):
                for run in RUNS:
                    for n in SELECTED_STAS:
                        d = read_csv(pathf(run, n))
                        if d is None or "E2E_Delay_ms" not in d.columns:
                            continue
                        s = d[["E2E_Delay_ms"]].copy(); s["nSta"] = n; s["Label"] = label
                        rows.append(s)
            for m, base in BASE_DIRS.items():
                add(m, lambda r, n, base=base: std_path(base, r, n, "all_packets_e2e.out"))
            add(CMAB_LABEL, lambda r, n: cmab_path(r, n, "all_packets_e2e.out"))
            for run in RUNS:
                for n in SELECTED_STAS:
                    for raru in nRaRus:
                        for ocw in OCwMin:
                            if (raru == 0) != (ocw == 0):
                                continue
                            d = read_csv(uora_path(run, n, raru, ocw, "all_packets_e2e.out"))
                            if d is None or "E2E_Delay_ms" not in d.columns:
                                continue
                            s = d[["E2E_Delay_ms"]].copy()
                            s["nSta"] = n; s["RA_RU"] = raru; s["OCW"] = ocw
                            urows.append(s)
            box = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
            u = pd.concat(urows, ignore_index=True) if urows else pd.DataFrame()
            if not u.empty:
                med = u.groupby(["nSta", "RA_RU", "OCW"])["E2E_Delay_ms"].median().reset_index()
                idx = med.groupby(["nSta", "RA_RU"])["E2E_Delay_ms"].idxmin()
                ub = u.merge(med.loc[idx][["nSta", "RA_RU", "OCW"]], on=["nSta", "RA_RU", "OCW"])
                ub["Label"] = ub["RA_RU"].apply(raru_label)
                box = pd.concat([box, ub[["E2E_Delay_ms", "nSta", "Label"]]], ignore_index=True)
            return box

        # ---------------- Collect ----------------
        print("[INFO] e2e delay (boxplot)")
        box_df = e2e_boxdata()
        print("[INFO] wake-up delay")
        wake_df = scalar_curves("wakeup_packet_stats", extract_wakeup, best_by="median")
        print("[INFO] packet loss")
        loss_df = scalar_curves("per_sta_stats.out", extract_loss, best_by="mean")

        present = [l for l in LABEL_ORDER
                   if l in set(box_df.get("Label", [])) | set(wake_df.get("Label", [])) | set(loss_df.get("Label", []))]

        # ---------------- Plot 1x3 ----------------
        fig, axes = plt.subplots(1, 3, figsize=(TEXTWIDTH_IN, 2.7))

        # (a) packet loss ratio -- lines
        for lbl in present:
            sub = loss_df[loss_df["Label"] == lbl].sort_values("nSta")
            if not sub.empty:
                axes[0].errorbar(sub["nSta"], sub["mean"], yerr=sub["err"],
                                 markersize=4 if lbl == CMAB_LABEL else 3,
                                 elinewidth=0.6, capsize=1.0, capthick=0.6, **line_style(lbl))
        axes[0].set_ylabel("Packet loss ratio")
        axes[0].set_xticks(SELECTED_STAS); axes[0].set_xlim(min(SELECTED_STAS) - 1, max(SELECTED_STAS) + 1)

        # (b) wake-up delay -- lines
        for lbl in present:
            sub = wake_df[wake_df["Label"] == lbl].sort_values("nSta")
            if not sub.empty:
                axes[1].errorbar(sub["nSta"], sub["mean"], yerr=sub["err"],
                                 markersize=4 if lbl == CMAB_LABEL else 3,
                                 elinewidth=0.6, capsize=1.0, capthick=0.6, **line_style(lbl))
        axes[1].set_ylabel("Average wake-up delay (ms)")
        axes[1].set_xticks(SELECTED_STAS); axes[1].set_xlim(min(SELECTED_STAS) - 1, max(SELECTED_STAS) + 1)

        # (c) E2E delay -- boxplot
        sns.boxplot(
            data=box_df[box_df["nSta"].isin(SELECTED_STAS)],
            x="nSta", y="E2E_Delay_ms", hue="Label",
            hue_order=present, palette=COLORS, saturation=1.0,
            showfliers=True, fliersize=1.0, whis=3.0, width=0.85, linewidth=0.4, ax=axes[2],
        )
        if axes[2].get_legend() is not None:
            axes[2].get_legend().remove()
        axes[2].set_ylabel("End-to-end delay (ms)")
        axes[2].set_ylim(4, 12)

        # panel captions just below each axis; no per-panel x-labels
        captions = ["(a) Packet loss ratio.", "(b) Average wake-up delay.", "(c) End-to-end delay."]
        for ax, cap in zip(axes, captions):
            ax.set_xlabel("")
            ax.grid(True, linestyle="--", linewidth=0.4)
            ax.text(0.5, -0.15, cap, transform=ax.transAxes, ha="center", va="top", fontsize=7)

        # single, centered x-label close under the captions
        fig.text(0.5, -0.02, "Number of active STAs", ha="center", va="bottom", fontsize=8)

        # tight margins: legend hugs the top, captions/x-label hug the bottom
        fig.subplots_adjust(left=0.07, right=0.99, top=0.86, bottom=0.20, wspace=0.28)

        # ---- shared legend just above the panels ----
        handles = [Line2D([0], [0], markersize=4, lw=1.0, **line_style(l)) for l in present]
        fig.legend(handles, present, ncol=min(5, len(present)),
                   loc="upper center", bbox_to_anchor=(0.5, 1.0),
                   frameon=False, columnspacing=1.0, handlelength=1.4,
                   handletextpad=0.4, labelspacing=0.2, borderaxespad=0.1)

        OUT_FIG.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(OUT_FIG, bbox_inches="tight")
        plt.show()
        plt.close()
        print(f"[OK] Figure saved to {OUT_FIG}")
        _done("conf_results_row")
    except Exception as _err:
        _done("conf_results_row", _err)

# ---- conf_video_delay: Uplink video delay ----
if _run("conf_video_delay"):
    try:
        from pathlib import Path
        import pandas as pd
        import numpy as np
        import matplotlib.pyplot as plt

        # ---------------- IEEE plot styling (single column) ----------------
        plt.rcParams.update({
            "font.size":        8,
            "axes.labelsize":   8,
            "xtick.labelsize":  7,
            "ytick.labelsize":  7,
            "legend.fontsize":  6,
            "lines.linewidth":  0.9,
            "lines.markersize": 3,
            "axes.linewidth":   0.6,
            "grid.linewidth":   0.4,
            "pdf.fonttype":     42,     # embed TrueType (no Type-3)
            "ps.fonttype":      42,
        })
        COLWIDTH_IN = 0.8 * 3.5              # single-column IEEE width; generate at 1:1

        # ---------------- Configuration ----------------
        RUNS = range(1, 7)
        NSTA_VALUES = range(8, 31)
        SELECTED_STAS = [8, 13, 18, 24, 30]

        nRaRus = [0, 1, 5, 9, 13, 18]
        OCwMin = [0, 1, 3, 7, 15, 31, 63]

        BASE_DIRS = {
            "EDCA":  Path("conf_data/edca"),
            "A2P":   Path("conf_data/a2p"),
            "A2S": Path("conf_data/a2pv2"),
        }

        # CMAB winner picked from fig/conference/cmab_hp_sweep_figs:
        # CUCB + Binary + c=0.5 -- lowest packet loss among HP-tunable algos
        # combined with ~70 ms video UL delay (lower than TS-Binary).
        CMAB_DIR     = Path("conf_data/cmab")
        CMAB_VARIANT = "CUCB_Binary_c0.5"
        CMAB_LABEL   = "CUCB"

        METRIC      = "Video_avg_delay_ms"
        OUT_FIG     = Path("fig/conference/conf_video_delay.pdf")
        OUT_STATS   = Path("fig/conference/conf_video_delay_stats.csv")
        ERROR_KIND  = "std"   # "std" (run-to-run dispersion) or "sem" (uncertainty in mean)

        # ---------------- Helpers ----------------
        def read_csv(path: Path):
            if not path.exists():
                return None
            df = pd.read_csv(path, delimiter="\t")
            if df.dropna(how="all").empty:
                return None
            return df

        def per_sta_path_std(method, run, nsta):
            return BASE_DIRS[method] / f"{run}_run-{nsta}_sta" / "per_sta_stats.out"

        def per_sta_path_uora(run, nsta, raru, ocw):
            return Path("conf_data/uora") / f"ocwMin_{ocw}" / f"{run}_run-{nsta}_sta-{raru}_rarus" / "per_sta_stats.out"

        def per_sta_path_cmab(run, nsta):
            return CMAB_DIR / CMAB_VARIANT / f"{run}_run-{nsta}_sta" / "per_sta_stats.out"

        def video_row(path: Path):
            """Return one-row DataFrame with the camera's Video_avg_delay_ms, or None."""
            df = read_csv(path)
            if df is None or "Video_pkts" not in df.columns or METRIC not in df.columns:
                return None
            cam = df[df["Video_pkts"] > 0]
            if cam.empty:
                return None
            return cam.iloc[[0]][[METRIC]].copy()

        def aggregate(df, group_cols, metric=METRIC):
            """Across-runs mean / std / sem / median / p25 / p75 / n per group."""
            g = df.groupby(group_cols)[metric]
            out = g.agg(
                mean="mean", std="std", n="count", median="median",
                p25=lambda s: s.quantile(0.25),
                p75=lambda s: s.quantile(0.75),
            ).reset_index()
            out["sem"] = out["std"] / np.sqrt(out["n"].clip(lower=1))
            return out

        # ---------------- Collect data ----------------
        all_rows = []

        for method in BASE_DIRS:
            for run in RUNS:
                for nsta in NSTA_VALUES:
                    r = video_row(per_sta_path_std(method, run, nsta))
                    if r is None:
                        continue
                    r["nSta"], r["Run"], r["Method"] = nsta, run, method
                    all_rows.append(r)

        for run in RUNS:
            for nsta in NSTA_VALUES:
                r = video_row(per_sta_path_cmab(run, nsta))
                if r is None:
                    continue
                r["nSta"], r["Run"], r["Method"] = nsta, run, "CMAB"
                all_rows.append(r)

        for run in RUNS:
            for nsta in NSTA_VALUES:
                for raru in nRaRus:
                    for ocw in OCwMin:
                        if (raru == 0) != (ocw == 0):
                            continue
                        r = video_row(per_sta_path_uora(run, nsta, raru, ocw))
                        if r is None:
                            continue
                        r["nSta"], r["Run"], r["Method"] = nsta, run, "UORA"
                        r["RA_RU"], r["OCW"] = raru, ocw
                        all_rows.append(r)

        if not all_rows:
            raise RuntimeError("No video data collected.")

        data = pd.concat(all_rows, ignore_index=True)
        data[METRIC] = pd.to_numeric(data[METRIC], errors="coerce")

        # ---------------- Aggregate ----------------
        agg_std = aggregate(data[data["Method"] != "UORA"], ["Method", "nSta"])

        uora_only = data[data["Method"] == "UORA"]
        if not uora_only.empty:
            median_per_cell = (uora_only
                               .groupby(["nSta", "RA_RU", "OCW"], as_index=False)[METRIC].median())
            idx = median_per_cell.groupby(["nSta", "RA_RU"])[METRIC].idxmin()
            best_keys = median_per_cell.loc[idx][["nSta", "RA_RU", "OCW"]]
            per_run_best = uora_only.merge(best_keys, on=["nSta", "RA_RU", "OCW"], how="inner")
            agg_uora = aggregate(per_run_best, ["nSta", "RA_RU"])
        else:
            agg_uora = pd.DataFrame(columns=["nSta", "RA_RU", "mean", "std", "n", "median", "p25", "p75", "sem"])
            print("[WARN] No UORA rows.")

        # ---------------- Write per-curve stats ----------------
        out_csv = []
        for _, row in agg_std.iterrows():
            out_csv.append({"curve": row["Method"], "nSta": row["nSta"],
                            "mean": row["mean"], "std": row["std"], "sem": row["sem"],
                            "median": row["median"], "p25": row["p25"], "p75": row["p75"], "n_runs": row["n"]})
        for _, row in agg_uora.iterrows():
            curve = "SA OFDMA" if row["RA_RU"] == 0 else (
                f"{int(row['RA_RU'])} RA RU" if row["RA_RU"] == 1 else f"{int(row['RA_RU'])} RA RUs")
            out_csv.append({"curve": curve, "nSta": row["nSta"],
                            "mean": row["mean"], "std": row["std"], "sem": row["sem"],
                            "median": row["median"], "p25": row["p25"], "p75": row["p75"], "n_runs": row["n"]})
        OUT_STATS.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(out_csv).to_csv(OUT_STATS, index=False)
        print(f"[OK] Stats written to {OUT_STATS}")

        # ---------------- Plot ----------------
        fig, ax = plt.subplots(figsize=(COLWIDTH_IN, 2.6))

        def yerr(df):
            return df[ERROR_KIND]

        standard_markers = {
            "EDCA":  ("o", "EDCA"),
            "A2P":   ("s", "A2P"),
            "A2S": ("D", "A2S"),
            "CMAB":  ("*", CMAB_LABEL),
        }
        for method, (marker, label) in standard_markers.items():
            df_m = agg_std[agg_std["Method"] == method].sort_values("nSta")
            if df_m.empty:
                continue
            ax.errorbar(df_m["nSta"], df_m["mean"], yerr=yerr(df_m),
                        marker=marker, markersize=4 if method == "CMAB" else 3,
                        elinewidth=0.6, capsize=1.0, capthick=0.6, label=label)

        sa_ofdma = agg_uora[agg_uora["RA_RU"] == 0].sort_values("nSta")
        if not sa_ofdma.empty:
            ax.errorbar(sa_ofdma["nSta"], sa_ofdma["mean"], yerr=yerr(sa_ofdma),
                        marker="^", markersize=3, elinewidth=0.6, capsize=1.0, capthick=0.6,
                        label="SA OFDMA")

        for raru in nRaRus:
            if raru == 0:
                continue
            df_u = agg_uora[agg_uora["RA_RU"] == raru].sort_values("nSta")
            if df_u.empty:
                continue
            ax.errorbar(df_u["nSta"], df_u["mean"], yerr=yerr(df_u),
                        linestyle="--", marker="o", markersize=2.5,
                        elinewidth=0.6, capsize=1.0, capthick=0.6,
                        label=f"{raru} RA RU" if raru == 1 else f"{raru} RA RUs")

        # ---------------- Styling ----------------
        ax.set_xlabel("Number of active STAs")
        ax.set_ylabel("Video UL delay (ms)")
        ax.grid(True, linestyle="--", linewidth=0.4)
        ax.set_xticks(SELECTED_STAS)
        ax.set_xlim(min(NSTA_VALUES) - 1, max(NSTA_VALUES) + 1)

        ax.legend(ncol=2, loc="best", fontsize=6)

        OUT_FIG.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(OUT_FIG, bbox_inches="tight")
        plt.show()
        plt.close()
        print(f"[OK] Video line plot saved to {OUT_FIG}")
        _done("conf_video_delay")
    except Exception as _err:
        _done("conf_video_delay", _err)

# ---- conf_video_heatmap: Uplink video heat maps ----
if _run("conf_video_heatmap"):
    try:
        from pathlib import Path
        import pandas as pd
        import numpy as np
        import matplotlib.pyplot as plt
        import seaborn as sns

        # ---------------- IEEE styling ----------------
        plt.rcParams.update({
            "font.size":        8,
            "axes.labelsize":   8,
            "xtick.labelsize":  7,
            "ytick.labelsize":  7,
            "pdf.fonttype":     42,     # embed TrueType (no Type-3)
            "ps.fonttype":      42,
        })

        # ---------------- Configuration ----------------
        RUNS = range(1, 7)
        NSTA_VALUES = range(8, 31)
        SELECTED_STAS = [8, 13, 18, 24, 30]        # heatmap columns

        nRaRus = [0, 1, 5, 9, 13, 18]
        OCwMin = [0, 1, 3, 7, 15, 31, 63]

        BASE_DIRS = {
            "EDCA":  Path("conf_data/edca"),
            "A2P":   Path("conf_data/a2p"),
            "A2PV2": Path("conf_data/a2pv2"),
        }

        CMAB_DIR     = Path("conf_data/cmab")
        CMAB_VARIANT = "CUCB_Binary_c0.5"
        CMAB_LABEL   = "CUCB"

        # --- Window / reference values from camera config ---
        SIM_TIME_S           = 30
        STATS_WINDOW_SECONDS = SIM_TIME_S
        CAMERA_NOMINAL_MBPS  = 1.633        # Fps=30, Gop=15, I=80KB, P=1.5KB (+SeqTsHeader)

        OUT_DIR   = Path("fig/conference")
        OUT_STATS = OUT_DIR / "conf_video_heatmap_stats.csv"

        METRIC       = "delivery_fraction"      # "delivery_fraction" | "delivered_mbps" | "loss_fraction"
        METRIC_LABEL = "Delivery fraction"
        VMIN, VMAX   = 0.85, 1.0
        CMAP         = "RdYlGn"                  # red=low, green=high
        ANNOT_FMT    = ".2f"

        # ---------------- Helpers ----------------
        def read_csv(path: Path):
            if not path.exists():
                return None
            df = pd.read_csv(path, delimiter="\t")
            if df.dropna(how="all").empty:
                return None
            return df

        def per_sta_path_std(method, run, nsta):
            return BASE_DIRS[method] / f"{run}_run-{nsta}_sta" / "per_sta_stats.out"

        def per_sta_path_uora(run, nsta, raru, ocw):
            return Path("conf_data/uora") / f"ocwMin_{ocw}" / f"{run}_run-{nsta}_sta-{raru}_rarus" / "per_sta_stats.out"

        def per_sta_path_cmab(run, nsta):
            return CMAB_DIR / CMAB_VARIANT / f"{run}_run-{nsta}_sta" / "per_sta_stats.out"

        def video_metrics(path: Path):
            """One-row DataFrame with camera video metrics; delivery fraction capped at 1.0."""
            df = read_csv(path)
            if df is None or "Video_pkts" not in df.columns or "Video_RX_bytes" not in df.columns:
                return None
            cam = df[df["Video_pkts"] > 0]
            if cam.empty:
                return None
            row = cam.iloc[0]
            out = cam.iloc[[0]][["Video_RX_bytes", "Video_pkts"]].copy()
            out["delivered_mbps"] = float(row["Video_RX_bytes"]) * 8 / 1e6 / STATS_WINDOW_SECONDS

            # exact fraction if the run logged the generated count; else nominal-rate ratio
            if "Video_gen" in cam.columns and float(row["Video_gen"]) > 0:
                frac = float(row["Video_pkts"]) / float(row["Video_gen"])
            else:
                frac = out["delivered_mbps"].iloc[0] / CAMERA_NOMINAL_MBPS

            frac = min(frac, 1.0)                       # <-- never exceed 1.00
            out["delivery_fraction"] = frac
            out["loss_fraction"]     = 1.0 - frac
            return out

        # ---------------- Collect data ----------------
        all_rows = []
        for method in BASE_DIRS:
            for run in RUNS:
                for nsta in NSTA_VALUES:
                    r = video_metrics(per_sta_path_std(method, run, nsta))
                    if r is None: continue
                    r["nSta"], r["Run"], r["Method"] = nsta, run, method
                    all_rows.append(r)

        for run in RUNS:
            for nsta in NSTA_VALUES:
                r = video_metrics(per_sta_path_cmab(run, nsta))
                if r is None: continue
                r["nSta"], r["Run"], r["Method"] = nsta, run, "CMAB"
                all_rows.append(r)

        for run in RUNS:
            for nsta in NSTA_VALUES:
                for raru in nRaRus:
                    for ocw in OCwMin:
                        if (raru == 0) != (ocw == 0):
                            continue
                        r = video_metrics(per_sta_path_uora(run, nsta, raru, ocw))
                        if r is None: continue
                        r["nSta"], r["Run"], r["Method"] = nsta, run, "UORA"
                        r["RA_RU"], r["OCW"] = raru, ocw
                        all_rows.append(r)

        if not all_rows:
            raise RuntimeError("No video data collected.")

        data = pd.concat(all_rows, ignore_index=True)
        data = data[data["nSta"].isin(SELECTED_STAS)]          # keep only the selected columns
        print(f"[INFO] loaded {len(data)} rows. CAMERA_NOMINAL_MBPS = {CAMERA_NOMINAL_MBPS}")

        # ---------------- Build the pivot ----------------
        agg_std = (data[data["Method"] != "UORA"]
                   .groupby(["Method", "nSta"], as_index=False)[METRIC].mean())
        agg_std["row_label"] = agg_std["Method"].replace({"CMAB": CMAB_LABEL})

        agg_sa = (data[(data["Method"] == "UORA") & (data["RA_RU"] == 0)]
                  .groupby(["nSta"], as_index=False)[METRIC].mean())
        agg_sa["row_label"] = "SA OFDMA"

        uora_only = data[(data["Method"] == "UORA") & (data["RA_RU"] != 0)]
        if not uora_only.empty:
            mean_per_cell = uora_only.groupby(["nSta", "RA_RU", "OCW"], as_index=False)[METRIC].mean()
            idx = mean_per_cell.groupby(["nSta", "RA_RU"])[METRIC].idxmax()   # best cell = highest delivery
            agg_uora = mean_per_cell.loc[idx][["nSta", "RA_RU", METRIC]].copy()
            agg_uora["row_label"] = agg_uora["RA_RU"].apply(
                lambda x: f"{int(x)} RA RU" if x == 1 else f"{int(x)} RA RUs")
        else:
            agg_uora = pd.DataFrame(columns=["nSta", "RA_RU", METRIC, "row_label"])

        long_df = pd.concat([agg_std[["row_label", "nSta", METRIC]],
                             agg_sa [["row_label", "nSta", METRIC]],
                             agg_uora[["row_label", "nSta", METRIC]]], ignore_index=True)

        pivot = long_df.pivot_table(index="row_label", columns="nSta", values=METRIC)
        pivot = pivot.clip(upper=1.0)                          # <-- guarantee no cell > 1.00

        row_order = ["EDCA", "A2P", "A2PV2", CMAB_LABEL, "SA OFDMA",
                     "1 RA RU", "5 RA RUs", "9 RA RUs", "13 RA RUs", "18 RA RUs"]
        pivot = pivot.reindex([r for r in row_order if r in pivot.index])

        # ---------------- Save stats CSV ----------------
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        long_df.to_csv(OUT_STATS, index=False)
        print(f"[OK] stats written to {OUT_STATS}")

        # ---------------- Heatmap ----------------
        n_rows, n_cols = pivot.shape
        fig, ax = plt.subplots(figsize=(0.8 * 3.5, 0.32 * n_rows + 1.2))   # ~column width

        sns.heatmap(
            pivot,
            vmin=VMIN, vmax=VMAX,
            cmap=CMAP,
            annot=True, fmt=ANNOT_FMT, annot_kws={"size": 6},
            cbar_kws={"label": METRIC_LABEL, "pad": 0.02},
            linewidths=0.4, linecolor="white",
            ax=ax,
        )
        ax.set_xlabel("Number of active STAs")
        ax.set_ylabel("")
        plt.setp(ax.get_xticklabels(), rotation=0)
        plt.setp(ax.get_yticklabels(), rotation=0)

        out_fig = OUT_DIR / f"conf_video_{METRIC}_heatmap.pdf"
        fig.savefig(out_fig, bbox_inches="tight")
        plt.show()
        plt.close()
        print(f"[OK] heatmap saved to {out_fig}")
        _done("conf_video_heatmap")
    except Exception as _err:
        _done("conf_video_heatmap", _err)

# ---- conf_cmab_tuning_voice: CMAB hyper-parameter sweep, voice traffic ----
if _run("conf_cmab_tuning_voice"):
    try:
        # %% imports
        import re
        from pathlib import Path

        import matplotlib.pyplot as plt
        import numpy as np
        import pandas as pd

        # --- IEEE journal styling ---
        plt.rcParams.update({
            "font.size":        8,
            "axes.labelsize":   8,
            "axes.titlesize":   8,
            "xtick.labelsize":  8,
            "ytick.labelsize":  8,
            "legend.fontsize":  7,
            "lines.linewidth":  1.0,
            "lines.markersize": 3,
            "axes.linewidth":   0.6,
            "grid.linewidth":   0.4,
            "pdf.fonttype":     42,              # embed TrueType (no Type-3; IEEE-compliant)
            "ps.fonttype":      42,
        })

        TEXTWIDTH_IN = 7.16   # IEEE two-column text width

        # %% config
        ROOT = Path("conf_data/cmab")
        SAVE_FIGS = False
        FIG_DIR   = Path("./fig/conference/cmab_hp_sweep_figs")

        ALGOS    = ["CUCB", "EpsilonGreedy", "EXP3M", "ThompsonSampling"]
        HP_GLYPH = {"CUCB": "c", "EpsilonGreedy": r"$\varepsilon$", "EXP3M": r"$\gamma$"}

        ALGO_DEFAULT = {
            "CUCB":          np.sqrt(2),
            "EpsilonGreedy": 0.1,
            "EXP3M":         0.1,
        }

        # Only the two metrics we report.
        METRIC_LABELS = {
            "loss_ratio":    "Packet loss ratio",
            "wakeup_avg_ms": "Avg. wake-up delay (ms)",
        }

        # Fixed y-axis limit per metric (applied to every subplot of that figure).
        METRIC_YLIM = {
            "loss_ratio":    0.4,
            "wakeup_avg_ms": 40,
        }

        RE_ALGO_DIR = re.compile(
            r"^(?P<algo>CUCB|EpsilonGreedy|EXP3M|ThompsonSampling)"
            r"_(?P<reward>Binary|FairnessWeighted)"
            r"(?:_(?P<hp>[ceg])(?P<val>[\d.]+))?$"
        )
        RE_RUN_DIR = re.compile(r"^(?P<run>\d+)_run-(?P<nSta>\d+)_sta$")


        # %% parsers / loaders
        def parse_dirs(algo_dir: Path, run_dir: Path):
            m1, m2 = RE_ALGO_DIR.match(algo_dir.name), RE_RUN_DIR.match(run_dir.name)
            if not (m1 and m2):
                return None
            return {
                "algorithm":  m1["algo"],
                "rewardType": m1["reward"],
                "hp_value":   float(m1["val"]) if m1["hp"] else np.nan,
                "run":        int(m2["run"]),
                "nSta":       int(m2["nSta"]),
            }


        def load_run(run_dir: Path):
            m = {k: np.nan for k in METRIC_LABELS}

            if (p := run_dir / "per_sta_stats.out").is_file():
                try:
                    d = pd.read_csv(p, sep="\t")
                    ap_row = d.loc[d["RX_bytes"].idxmax()]      # AP = node with most RX
                    m["loss_ratio"] = float(ap_row["Packet_loss_ratio"])
                except Exception:
                    pass

            if (p := run_dir / "wakeup_packet_stats").is_file():
                try:
                    w = pd.read_csv(p, sep="\t")["Delay_ms"].dropna()
                    if not w.empty:
                        m["wakeup_avg_ms"] = float(w.mean())
                except Exception:
                    pass

            return m


        # %% walk the tree
        rows = []
        for algo_dir in sorted(ROOT.iterdir()):
            if not algo_dir.is_dir():
                continue
            for run_dir in sorted(algo_dir.iterdir()):
                if not run_dir.is_dir():
                    continue
                meta = parse_dirs(algo_dir, run_dir)
                if meta is None:
                    continue
                meta.update(load_run(run_dir))
                rows.append(meta)

        df = pd.DataFrame(rows)
        df = df[df["algorithm"].isin(ALGOS)].reset_index(drop=True)
        print(f"loaded {len(df)} runs from {ROOT}")


        # %% aggregation helper
        def agg_mean_sem(sub, group_cols, metric):
            g   = sub.groupby(group_cols)[metric]
            out = g.agg(["mean", "std", "count"]).reset_index()
            out["sem"] = out["std"] / np.sqrt(out["count"].clip(lower=1))
            return out


        # %% plot -- metric vs nSta (one PDF per metric)
        rewards = sorted(df["rewardType"].dropna().unique())
        cmap    = plt.get_cmap("viridis")

        if SAVE_FIGS:
            FIG_DIR.mkdir(parents=True, exist_ok=True)

        for metric, ylabel in METRIC_LABELS.items():
            fig, axes = plt.subplots(
                len(rewards), len(ALGOS),
                figsize=(TEXTWIDTH_IN, 1.4 * len(rewards) + 0.5),
                sharex=True, sharey="row",
                squeeze=False, layout="constrained",
            )

            for r, reward in enumerate(rewards):
                for c, algo in enumerate(ALGOS):
                    ax  = axes[r][c]
                    sub = df[(df["algorithm"] == algo) & (df["rewardType"] == reward)]
                    if sub.empty or sub[metric].dropna().empty:
                        ax.text(0.5, 0.5, "no data",
                                ha="center", va="center", transform=ax.transAxes)
                        if r == 0:
                            ax.set_title(algo)
                        continue

                    hp_vals = sorted(sub["hp_value"].dropna().unique())

                    if hp_vals:                                   # CUCB / EpsilonGreedy / EXP3M
                        default = ALGO_DEFAULT.get(algo)
                        for i, hp in enumerate(hp_vals):
                            g = agg_mean_sem(
                                sub[sub["hp_value"] == hp], ["nSta"], metric
                            ).sort_values("nSta")
                            if g.empty:
                                continue
                            is_default = default is not None and np.isclose(hp, default)
                            ax.errorbar(
                                g["nSta"], g["mean"], yerr=g["sem"],
                                marker="o", capsize=1.5,
                                color=cmap(i / max(1, len(hp_vals) - 1)),
                                lw=1.8 if is_default else 0.9,
                                label=f"{HP_GLYPH[algo]}={hp:g}",
                                      #+ (" (default)" if is_default else ""),
                            )
                    else:                                         # ThompsonSampling — single curve
                        g = agg_mean_sem(sub, ["nSta"], metric).sort_values("nSta")
                        if not g.empty:
                            ax.errorbar(
                                g["nSta"], g["mean"], yerr=g["sem"],
                                marker="o", capsize=1.5, color="tab:red", lw=1.8,
                                label=algo,
                            )

                    if r == 0:
                        if algo == "EpsilonGreedy":
                            ax.set_title(r"$\varepsilon$-Greedy")
                        elif algo == "ThompsonSampling":
                            ax.set_title("Thompson Sampling")
                        else:
                            ax.set_title(algo)
                    if c == 0:
                        ax.set_ylabel(f"{reward}\n{ylabel}")
                    ax.grid(True, alpha=0.3)
                    ax.legend(loc="best", frameon=False, handlelength=1.5)

            # same y scale on every subplot of this figure
            for ax in axes.flat:
                top = METRIC_YLIM[metric]
                ax.set_ylim(-0.05 * top, top)

            fig.supxlabel("Number of active STAs", fontsize=8)

            if SAVE_FIGS:
                fig.savefig(FIG_DIR / f"cmab_sweep_{metric}.pdf", bbox_inches="tight")

            plt.show()
        _done("conf_cmab_tuning_voice")
    except Exception as _err:
        _done("conf_cmab_tuning_voice", _err)

# ---- conf_cmab_tuning_video: CMAB hyper-parameter sweep, video traffic ----
if _run("conf_cmab_tuning_video"):
    try:
        # %% imports
        import re
        from pathlib import Path

        import matplotlib.pyplot as plt
        import numpy as np
        import pandas as pd

        plt.rcParams.update({
          "font.size": 14,            # default is 10
          "axes.labelsize": 14,
          "xtick.labelsize": 12,
          "ytick.labelsize": 12,
          "legend.fontsize": 12,
        })

        # %% config
        ROOT = Path("conf_data/cmab")
        SAVE_FIGS = True
        FIG_DIR   = Path("./fig/conference/cmab_video_sweep")

        ALGOS    = ["CUCB", "EpsilonGreedy", "EXP3M", "ThompsonSampling"]  # <-- TS added
        HP_GLYPH = {"CUCB": "c", "EpsilonGreedy": "ε", "EXP3M": "γ"}       # no glyph for TS

        ALGO_DEFAULT = {
          "CUCB":          np.sqrt(2),
          "EpsilonGreedy": 0.1,
          "EXP3M":         0.1,
        }

        # Video-STA uplink delay only (mean + percentiles)
        METRIC_LABELS = {
          "video_avg_ms": "Avg. UL delay (ms)",
        }

        RE_ALGO_DIR = re.compile(
          r"^(?P<algo>CUCB|EpsilonGreedy|EXP3M|ThompsonSampling)"
          r"_(?P<reward>Binary|FairnessWeighted)"
          r"(?:_(?P<hp>[ceg])(?P<val>[\d.]+))?$"
        )
        RE_RUN_DIR = re.compile(r"^(?P<run>\d+)_run-(?P<nSta>\d+)_sta$")


        # %% parsers / loaders
        def parse_dirs(algo_dir: Path, run_dir: Path):
          m1, m2 = RE_ALGO_DIR.match(algo_dir.name), RE_RUN_DIR.match(run_dir.name)
          if not (m1 and m2):
              return None
          return {
              "algorithm":  m1["algo"],
              "rewardType": m1["reward"],
              "hp_value":   float(m1["val"]) if m1["hp"] else np.nan,
              "run":        int(m2["run"]),
              "nSta":       int(m2["nSta"]),
          }


        def load_run(run_dir: Path):
          m = {k: np.nan for k in METRIC_LABELS}

          if (p := run_dir / "video_packet_stats").is_file():
              try:
                  d = pd.read_csv(p, sep="\t")["Delay_ms"].dropna()
                  if not d.empty:
                      m["video_avg_ms"] = float(d.mean())
              except Exception:
                  pass

          if np.isnan(m["video_avg_ms"]) and (p := run_dir / "per_sta_stats.out").is_file():
              try:
                  d = pd.read_csv(p, sep="\t")
                  if "Video_pkts" in d.columns:
                      vid = d[d["Video_pkts"] > 0]
                      if not vid.empty:
                          m["video_avg_ms"] = float(vid["Video_avg_delay_ms"].iloc[0])
              except Exception:
                  pass

          return m


        # %% walk the tree
        rows = []
        for algo_dir in sorted(ROOT.iterdir()):
          if not algo_dir.is_dir():
              continue
          for run_dir in sorted(algo_dir.iterdir()):
              if not run_dir.is_dir():
                  continue
              meta = parse_dirs(algo_dir, run_dir)
              if meta is None:
                  continue
              meta.update(load_run(run_dir))
              rows.append(meta)

        df = pd.DataFrame(rows)
        df = df[df["algorithm"].isin(ALGOS)].reset_index(drop=True)
        print(f"loaded {len(df)} runs from {ROOT}")
        df.head()


        # %% sanity -- which runs actually loaded the mean
        (df.assign(has_video=df["video_avg_ms"].notna())
         .groupby(["algorithm", "rewardType", "has_video"])
         .size()
         .unstack(fill_value=0))


        # %% aggregation helper
        def agg_mean_sem(sub, group_cols, metric):
          g   = sub.groupby(group_cols)[metric]
          out = g.agg(["mean", "std", "count"]).reset_index()
          out["sem"] = out["std"] / np.sqrt(out["count"].clip(lower=1))
          return out


        # %% plot -- video UL delay vs nSta
        rewards = sorted(df["rewardType"].dropna().unique())
        cmap    = plt.get_cmap("viridis")

        if SAVE_FIGS:
          FIG_DIR.mkdir(parents=True, exist_ok=True)

        for metric, ylabel in METRIC_LABELS.items():
          fig, axes = plt.subplots(
              len(rewards), len(ALGOS),
              figsize=(4 * len(ALGOS), 1.6 * len(rewards)),
              sharex=True, sharey="row",
              squeeze=False,
          )

          for r, reward in enumerate(rewards):
              for c, algo in enumerate(ALGOS):
                  ax  = axes[r][c]
                  sub = df[(df["algorithm"] == algo) & (df["rewardType"] == reward)]
                  if sub.empty or sub[metric].dropna().empty:
                      ax.text(0.5, 0.5, "no data",
                              ha="center", va="center", transform=ax.transAxes)
                      if r == 0: ax.set_title(algo)
                      continue

                  hp_vals = sorted(sub["hp_value"].dropna().unique())

                  if hp_vals:
                      # CUCB / EpsilonGreedy / EXP3M — one curve per HP value
                      default = ALGO_DEFAULT.get(algo)
                      for i, hp in enumerate(hp_vals):
                          g = agg_mean_sem(
                              sub[sub["hp_value"] == hp], ["nSta"], metric
                          ).sort_values("nSta")
                          if g.empty:
                              continue
                          is_default = default is not None and np.isclose(hp, default)
                          color = cmap(i / max(1, len(hp_vals) - 1))
                          ax.errorbar(
                              g["nSta"], g["mean"], yerr=g["sem"],
                              marker="o", capsize=2,
                              color=color,
                              lw=2.2 if is_default else 1.2,
                              label=f"{HP_GLYPH[algo]}={hp:g}"
                                    + ("  (default)" if is_default else ""),
                          )
                  else:
                      # ThompsonSampling — no scalar HP, single curve per panel
                      g = agg_mean_sem(sub, ["nSta"], metric).sort_values("nSta")
                      if not g.empty:
                          ax.errorbar(
                              g["nSta"], g["mean"], yerr=g["sem"],
                              marker="o", capsize=2,
                              color="tab:red", lw=2.2,
                              label=algo,
                          )

                  if r == 0: ax.set_title(algo)
                  if c == 0: ax.set_ylabel(f"{reward}\n{ylabel}")
                  #if r == len(rewards) - 1: ax.set_xlabel("Number of Active STAs")
                  ax.grid(True, alpha=0.3)
                  ax.legend(loc="best")

          fig.suptitle(f"{ylabel} vs. number of active STAs (video STA only)")
          fig.supxlabel("Number of Active STAs", y=0.03)
          fig.tight_layout()

          if SAVE_FIGS:
              fig.savefig(FIG_DIR / f"{metric}.png", dpi=300, bbox_inches="tight")
          plt.show()
        _done("conf_cmab_tuning_video")
    except Exception as _err:
        _done("conf_cmab_tuning_video", _err)

# ============================================================================
# Industrial IoT scenario
# ============================================================================

# ---- iiot_cmab_tuning: CMAB hyper-parameter sweep ----
if _run("iiot_cmab_tuning"):
    try:
        # %% imports
        import re
        from pathlib import Path
        import matplotlib.pyplot as plt
        import numpy as np
        import pandas as pd

        plt.rcParams.update({
          "font.size": 14, "axes.labelsize": 14, "xtick.labelsize": 12,
          "ytick.labelsize": 12, "legend.fontsize": 12,
        })

        # %% config
        ROOT        = Path("iiot_data/iiot_data_pmean/cmab")
        PMEANS      = [0.05, 0.025]
        DEADLINE_MS = 20
        SAVE_FIGS   = False
        FIG_DIR     = Path("./fig/iiot/cmab_hp_sweep_figs")

        ALGOS    = ["CUCB", "EpsilonGreedy", "EXP3M", "ThompsonSampling"]
        HP_GLYPH = {"CUCB": "c", "EpsilonGreedy": "ε", "EXP3M": "γ"}
        ALGO_DEFAULT = {"CUCB": np.sqrt(2), "EpsilonGreedy": 0.1, "EXP3M": 0.1}

        METRIC_LABELS = {
          "t2_delivered": "T2 delivered fraction",
          "t2_loss":      "T2 deadline loss",
          "tp_mbps":      "T2 throughput (Mbps)",
          "t2_mean_ms":   "T2 mean UL delay (ms)",
          "t2_p95_ms":    "T2 P95 UL delay (ms)",
          "t2_p99_ms":    "T2 P99 UL delay (ms)",
        }
        DELAY_METRICS = {"t2_mean_ms", "t2_p50_ms", "t2_p95_ms", "t2_p99_ms"}

        RE_ALGO_DIR = re.compile(
          r"^(?P<algo>CUCB|EpsilonGreedy|EXP3M|ThompsonSampling)"
          r"_(?P<reward>Binary|FairnessWeighted)"
          r"(?:_(?P<hp>[ceg])(?P<val>[\d.]+))?$")
        RE_RUN_DIR = re.compile(
          r"^(?P<run>\d+)_run-(?P<nSta>\d+)_sta(?:_pMean-(?P<pmean>[\d.]+))?$")

        # %% parsers / loaders
        def parse_dirs(algo_dir, run_dir):
          m1, m2 = RE_ALGO_DIR.match(algo_dir.name), RE_RUN_DIR.match(run_dir.name)
          if not (m1 and m2):
              return None
          return {
              "algorithm": m1["algo"], "rewardType": m1["reward"],
              "hp_value":  float(m1["val"]) if m1["hp"] else np.nan,
              "run": int(m2["run"]), "nSta": int(m2["nSta"]),
              "pMean": float(m2["pmean"]) if m2["pmean"] else 0.1,
          }

        def load_run(run_dir):
          m = {k: np.nan for k in METRIC_LABELS}

          total_tp = np.nan
          if (p := run_dir / "throughput.out").is_file():
              try:
                  lines = p.read_text().splitlines()
                  if len(lines) >= 2:
                      total_tp = float(lines[1].split()[3])
              except Exception:
                  pass

          # type-2 delivery counts + byte share (from per-STA)
          t2_gen = t2_rx = t2_bytes = tot_bytes = np.nan
          if (p := run_dir / "per_sta_stats.out").is_file():
              try:
                  s = pd.read_csv(p, sep="\t")
                  if "Class" in s.columns:
                      t2 = s[s["Class"] == 2]
                      t2_gen    = float(t2["TX_pkts"].sum())
                      t2_rx     = float(t2["RX_pkts"].sum())
                      t2_bytes  = float(t2["RX_bytes"].sum())
                      tot_bytes = float(s["RX_bytes"].sum())
              except Exception:
                  pass

          # type-2 UL delays over *received* packets + on-time count
          ontime = np.nan
          if (p := run_dir / "type2_packets.out").is_file():
              try:
                  d = pd.read_csv(p, sep="\t")["delay_ms"].dropna()
                  if not d.empty:
                      m["t2_mean_ms"] = float(d.mean())
                      m["t2_p95_ms"]  = float(d.quantile(0.95))
                      m["t2_p99_ms"]  = float(d.quantile(0.99))
                      ontime = float((d <= DEADLINE_MS).sum())
              except Exception:
                  pass

          # derived: delivered fraction (raw), deadline loss, type-2 throughput
          if np.isfinite(t2_gen) and t2_gen > 0:
              m["t2_delivered"] = min(1.0, t2_rx / t2_gen)          # received / generated
              if np.isfinite(ontime):
                  m["t2_loss"] = max(0.0, 1 - ontime / t2_gen)      # (drops + late) / generated
          if np.isfinite(total_tp) and np.isfinite(tot_bytes) and tot_bytes > 0:
              m["tp_mbps"] = total_tp * (t2_bytes / tot_bytes)      # type-2 share of aggregate

          return m

        # %% walk the tree
        rows = []
        for algo_dir in sorted(ROOT.iterdir()):
          if not algo_dir.is_dir():
              continue
          for run_dir in sorted(algo_dir.iterdir()):
              if not run_dir.is_dir():
                  continue
              meta = parse_dirs(algo_dir, run_dir)
              if meta is None:
                  continue
              meta.update(load_run(run_dir))
              rows.append(meta)

        df = pd.DataFrame(rows)
        df = df[df["algorithm"].isin(ALGOS)].reset_index(drop=True)
        print(f"loaded {len(df)} runs; pMeans: {sorted(df['pMean'].unique())}")

        # %% aggregation helper
        def agg_mean_sem(sub, group_cols, metric):
          g   = sub.groupby(group_cols)[metric]
          out = g.agg(["mean", "std", "count"]).reset_index()
          out["sem"] = out["std"] / np.sqrt(out["count"].clip(lower=1))
          return out

        # %% plot -- one grid per (pMean, metric)
        rewards = sorted(df["rewardType"].dropna().unique())
        cmap    = plt.get_cmap("viridis")
        for pmean in PMEANS:
          dfp = df[np.isclose(df["pMean"], pmean)]
          for metric, ylabel in METRIC_LABELS.items():
              fig, axes = plt.subplots(
                  len(rewards), len(ALGOS),
                  figsize=(4 * len(ALGOS), 3.2 * len(rewards)),
                  sharex=True, sharey="row", squeeze=False)
              for r, reward in enumerate(rewards):
                  for c, algo in enumerate(ALGOS):
                      ax  = axes[r][c]
                      sub = dfp[(dfp["algorithm"] == algo) & (dfp["rewardType"] == reward)]
                      if sub.empty or sub[metric].dropna().empty:
                          ax.text(0.5, 0.5, "no data", ha="center", va="center",
                                  transform=ax.transAxes)
                          if r == 0: ax.set_title(algo)
                          continue
                      hp_vals = sorted(sub["hp_value"].dropna().unique())
                      if hp_vals:
                          default = ALGO_DEFAULT.get(algo)
                          for i, hp in enumerate(hp_vals):
                              g = agg_mean_sem(sub[sub["hp_value"] == hp], ["nSta"], metric).sort_values("nSta")
                              if g.empty: continue
                              is_default = default is not None and np.isclose(hp, default)
                              ax.errorbar(g["nSta"], g["mean"], yerr=g["sem"], marker="o", capsize=2,
                                          color=cmap(i / max(1, len(hp_vals) - 1)),
                                          lw=2.2 if is_default else 1.2,
                                          label=f"{HP_GLYPH[algo]}={hp:g}" + ("  (default)" if is_default else ""))
                      else:
                          g = agg_mean_sem(sub, ["nSta"], metric).sort_values("nSta")
                          if not g.empty:
                              ax.errorbar(g["nSta"], g["mean"], yerr=g["sem"], marker="o",
                                          capsize=2, color="tab:red", lw=2.2, label=algo)
                      if metric in DELAY_METRICS:
                          ax.axhline(DEADLINE_MS, ls="--", color="k", lw=1, alpha=0.6)
                      if metric == "t2_delivered":
                          ax.set_ylim(0, 1.05)
                      if r == 0: ax.set_title(algo)
                      if c == 0: ax.set_ylabel(f"{reward}\n{ylabel}")
                      ax.grid(True, alpha=0.3); ax.legend(loc="best", fontsize=9)
              fig.suptitle(f"{ylabel} vs. STAs  —  pMean = {int(round(pmean*1000))} ms")
              fig.supxlabel("Number of Stochastic STAs", y=0.02)
              if SAVE_FIGS:
                  FIG_DIR.mkdir(parents=True, exist_ok=True)
                  fig.savefig(FIG_DIR / f"{metric}_pMean{pmean}.png", dpi=300, bbox_inches="tight")
              plt.show()
        _done("iiot_cmab_tuning")
    except Exception as _err:
        _done("iiot_cmab_tuning", _err)

# ---- iiot_ari: Access request interval sweep (A2P, A2PV2) ----
if _run("iiot_ari"):
    try:
        from pathlib import Path
        import pandas as pd, numpy as np
        import matplotlib.pyplot as plt

        plt.rcParams.update({"font.size": 11, "pdf.fonttype": 42, "ps.fonttype": 42})

        RUNS         = range(1, 11)
        NSTA_VALUES  = [1, 30, 60, 90]
        PMEANS       = [0.025, 0.05]
        ARI_VALUES   = [64, 128, 256, 512, 1024]      # us
        SCHEMES      = {"A2P": "iiot_data/iiot_data_ari/a2p", "A2PV2": "iiot_data/iiot_data_ari/a2pv2"}
        DEADLINE_MS  = 20
        PS, T2, TP   = "per_sta_stats.out", "type2_packets.out", "throughput.out"

        def ptag(p): return "" if abs(p - 0.1) < 1e-9 else f"_pMean-{p}"

        def ari_dir(base, run, n, p, ari):
            return Path(base)/f"{run}_run-{n}_sta{ptag(p)}_ari{ari}"

        def delays(d):
            q = d/T2
            if not q.exists(): return None
            v = pd.read_csv(q, sep="\t")["delay_ms"].dropna().values
            return v if len(v) else None

        def metrics(d):
            ps = d/PS
            if not ps.exists(): return None
            s = pd.read_csv(ps, sep="\t")
            if "Class" not in s.columns: return None
            c2, c1 = s[s["Class"] == 2], s[s["Class"] == 1]
            gen = float(c2["TX_pkts"].sum())
            if gen <= 0: return None
            dl = delays(d)
            loss = deliv = p99 = mean = np.nan
            if dl is not None:
                loss  = max(0.0, 1 - float((dl <= DEADLINE_MS).sum())/gen)
                p99   = float(np.percentile(dl, 99)); mean = float(dl.mean())
            deliv = min(1.0, float(c2["RX_pkts"].sum())/gen)
            t1_tp = t2_tp = np.nan
            tp = d/TP
            if tp.exists():
                ln = tp.read_text().splitlines()
                if len(ln) >= 2:
                    tot = float(s["RX_bytes"].sum()); agg = float(ln[1].split()[3])
                    if tot > 0:
                        t1_tp = agg * float(c1["RX_bytes"].sum())/tot
                        t2_tp = agg * float(c2["RX_bytes"].sum())/tot
            return dict(loss=loss, deliv=deliv, p99=p99, mean=mean, t1_tp=t1_tp, t2_tp=t2_tp)

        # ---- collect ----
        recs = []
        for sch, base in SCHEMES.items():
            for p in PMEANS:
                for n in NSTA_VALUES:
                    for a in ARI_VALUES:
                        per = [m for run in RUNS if (m := metrics(ari_dir(base, run, n, p, a)))]
                        if not per: continue
                        agg = {k: np.nanmean([d[k] for d in per]) for k in per[0]}
                        recs.append({"scheme": sch, "pMean": p, "nSta": n, "ari": a, "n_ok": len(per), **agg})
        df = pd.DataFrame(recs)
        if df.empty:
            raise SystemExit("No data found — fix ari_dir() to match your output directory naming.")

        METRICS = [("loss","Type-2 deadline loss"), ("p99","Type-2 P99 delay (ms)"),
                   ("mean","Type-2 mean delay (ms)"), ("deliv","Type-2 delivered fraction"),
                   ("t1_tp","Type-1 throughput (Mbps)"), ("t2_tp","Type-2 throughput (Mbps)")]
        BAR_METRICS = {"t1_tp", "t2_tp"}                 # <-- these rows drawn as grouped bars
        cmap = plt.cm.viridis(np.linspace(0, 1, len(NSTA_VALUES)))
        x = np.arange(len(ARI_VALUES))                    # categorical positions (shared by lines & bars)
        w = 0.8 / len(NSTA_VALUES)                        # bar width per nSta

        Path("fig/iiot/ari").mkdir(parents=True, exist_ok=True)
        for sch in SCHEMES:
            fig, ax = plt.subplots(len(METRICS), len(PMEANS),
                                   figsize=(4*len(PMEANS), 2.4*len(METRICS)), sharex=True, squeeze=False)
            for r,(mk,ml) in enumerate(METRICS):
                for c,p in enumerate(PMEANS):
                    a = ax[r][c]
                    for i,n in enumerate(NSTA_VALUES):
                        d = (df[(df.scheme==sch)&(df.pMean==p)&(df.nSta==n)]
                             .set_index("ari").reindex(ARI_VALUES))
                        if d[mk].isna().all(): continue
                        if mk in BAR_METRICS:
                            a.bar(x + (i-(len(NSTA_VALUES)-1)/2)*w, d[mk].values, w,
                                  color=cmap[i], label=f"{n} STA")
                        else:
                            a.plot(x, d[mk].values, marker="o", color=cmap[i], label=f"{n} STA")
                    if mk in ("p99","mean"): a.axhline(DEADLINE_MS, ls="--", color="k", lw=0.8, alpha=0.6)
                    a.set_xticks(x); a.set_xticklabels(ARI_VALUES)
                    a.grid(True, axis="y" if mk in BAR_METRICS else "both", alpha=0.4)
                    if r==0: a.set_title(f"{sch}  —  pMean = {int(p*1000)} ms")
                    if c==0: a.set_ylabel(ml)
            ax[-1][0].set_xlabel("ARI (µs)"); ax[-1][1].set_xlabel("ARI (µs)")
            h,l = ax[0][0].get_legend_handles_labels()
            fig.legend(h, l, loc="upper center", ncol=len(NSTA_VALUES), bbox_to_anchor=(0.5, 1.02), frameon=False)
            fig.tight_layout()
            fig.savefig(f"fig/iiot/ari/ari_sweep_{sch}.pdf", bbox_inches="tight")
            plt.show()

        # ---- quick numeric read: how much each metric moves across ARI (bigger = more selective) ----
        print("metric sensitivity to ARI (mean over pMean,nSta of max-min across ARI):")
        for mk,ml in METRICS:
            spread = (df.groupby(["scheme","pMean","nSta"])[mk]
                        .agg(lambda s: s.max()-s.min()).groupby(level=0).mean())
            print(f"  {ml:30s} " + "  ".join(f"{k}:{v:.3g}" for k,v in spread.items()))
        _done("iiot_ari")
    except Exception as _err:
        _done("iiot_ari", _err)

# ---- iiot_pmean_delay_tput: Traffic-intensity sweep: delay box plot and throughput ----
if _run("iiot_pmean_delay_tput"):
    try:
        from pathlib import Path
        import pandas as pd
        import numpy as np
        import matplotlib.pyplot as plt
        import seaborn as sns

        # ---------------- Configuration ----------------
        RUNS = range(1, 11)
        NSTA = 90                            # pMean sweep is at 90 stochastic STAs only
        PMEAN_VALUES = [0.00625, 0.0125, 0.025 , 0.05]      # exp. mean of type-2 generation interval (s)

        nRaRus = [0, 1, 5, 9, 13, 18]
        OCwMin = [1, 3, 7, 15, 31, 63]

        BASE_DIRS = {
          "EDCA":  Path("iiot_data/iiot_data_pmean/edca"),
          "A2P":   Path("iiot_data/iiot_data_pmean/a2p"),
          "A2PV2": Path("iiot_data/iiot_data_pmean/a2pv2"),
        }
        CMAB_DIR     = Path("iiot_data/iiot_data_pmean/cmab")
        CMAB_VARIANT = "EXP3M_Binary_g0.3"
        CMAB_LABEL   = "EXP3M"

        OUTPUT_CSV = "iiot_pmean_per_sta_data.csv"
        PER_STA_COL  = "Avg_delay_ms"
        PER_STA_FILE = "per_sta_stats.out"
        TP_FILE      = "throughput.out"
        ERROR_KIND   = "std"   # "std" or "sem"

        # ---- pMean -> path tag (must match job_script_iiot.sh: 0.1 => no tag) -------
        def ptag(pmean):
          return "" if abs(pmean - 0.1) < 1e-9 else f"_pMean-{pmean}"

        # ---------------- Helpers ----------------
        def read_csv(path: Path):
          if not path.exists():
              return None
          df = pd.read_csv(path, delimiter="\t")
          if df.dropna(how="all").empty:
              return None
          return df

        def per_sta_path(method, run, pmean):
          return BASE_DIRS[method] / f"{run}_run-{NSTA}_sta{ptag(pmean)}" / PER_STA_FILE

        def uora_per_sta_path(run, pmean, raru, ocw):
          return (Path("iiot_data/iiot_data_pmean/uora") / f"ocwMin_{ocw}"
                  / f"{run}_run-{NSTA}_sta-{raru}_rarus{ptag(pmean)}" / PER_STA_FILE)

        def cmab_per_sta_path(run, pmean):
          return CMAB_DIR / CMAB_VARIANT / f"{run}_run-{NSTA}_sta{ptag(pmean)}" / PER_STA_FILE

        def tp_path(method, run, pmean):
          return BASE_DIRS[method] / f"{run}_run-{NSTA}_sta{ptag(pmean)}" / TP_FILE

        def uora_tp_path(run, pmean, raru, ocw):
          return (Path("iiot_data/iiot_data_pmean/uora") / f"ocwMin_{ocw}"
                  / f"{run}_run-{NSTA}_sta-{raru}_rarus{ptag(pmean)}" / TP_FILE)

        def cmab_tp_path(run, pmean):
          return CMAB_DIR / CMAB_VARIANT / f"{run}_run-{NSTA}_sta{ptag(pmean)}" / TP_FILE

        # ---------------- Per-STA delay loaders ----------------
        def _load_per_sta(path, extra_cols):
          df = read_csv(path)
          if df is None or PER_STA_COL not in df.columns:
              return None
          if "Class" in df.columns:
              df = df[df["Class"] == 2]
          if "RX_bytes" in df.columns:
              df = df[df["RX_bytes"] > 0]
          if df.empty:
              return None
          out = df[[PER_STA_COL]].copy()
          for k, v in extra_cols.items():
              out[k] = v
          return out

        def process_method_per_sta(method):
          rows = []
          for run in RUNS:
              for pmean in PMEAN_VALUES:
                  d = _load_per_sta(per_sta_path(method, run, pmean),
                                    {"pMean": pmean, "Run": run, "Method": method})
                  if d is not None:
                      rows.append(d)
          return rows

        def process_uora_per_sta():
          rows = []
          for run in RUNS:
              for pmean in PMEAN_VALUES:
                  for raru in nRaRus:
                      for ocw in OCwMin:
                          d = _load_per_sta(
                              uora_per_sta_path(run, pmean, raru, ocw),
                              {"pMean": pmean, "Run": run, "RA_RU": raru, "OCW": ocw, "Method": "UORA"})
                          if d is not None:
                              rows.append(d)
          return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()

        def process_cmab_per_sta():
          rows = []
          for run in RUNS:
              for pmean in PMEAN_VALUES:
                  d = _load_per_sta(cmab_per_sta_path(run, pmean),
                                    {"pMean": pmean, "Run": run, "Method": "CMAB"})
                  if d is not None:
                      rows.append(d)
          return rows

        def read_tp(path: Path):
          if not path.exists():
              return None
          try:
              df = pd.read_csv(path, delimiter="\t")
          except Exception:
              return None
          if "Throughput_Mbps" not in df.columns or df["Throughput_Mbps"].empty:
              return None
          return df

        # ---------------- Load per-STA delay ----------------
        per_sta_rows = []
        for method in BASE_DIRS:
          print(f"[INFO] Processing {method} per-STA")
          per_sta_rows.extend(process_method_per_sta(method))
        print(f"[INFO] Processing CMAB per-STA ({CMAB_VARIANT})")
        per_sta_rows.extend(process_cmab_per_sta())
        per_sta_other = pd.concat(per_sta_rows, ignore_index=True) if per_sta_rows else pd.DataFrame()

        print("[INFO] Processing UORA per-STA")
        per_sta_uora = process_uora_per_sta()
        print(f"[OK] per-STA UORA rows: {len(per_sta_uora)}, other rows: {len(per_sta_other)}")

        # ---------------- UORA OCW selection (per (pMean, RA_RU), p99 of Avg_delay) --
        def select_best_ocw_per_sta(per_sta_df, delay_col=PER_STA_COL):
          if per_sta_df.empty:
              return pd.DataFrame()
          grouped = (per_sta_df.groupby(["pMean", "RA_RU", "OCW"])[delay_col]
                     .quantile(0.99).reset_index())
          idx = grouped.groupby(["pMean", "RA_RU"])[delay_col].idxmin()
          return grouped.loc[idx][["pMean", "RA_RU", "OCW"]].reset_index(drop=True)

        per_sta_uora_ra = per_sta_uora[per_sta_uora["RA_RU"] > 0]
        per_sta_uora_sa = per_sta_uora[per_sta_uora["RA_RU"] == 0]
        best_keys = select_best_ocw_per_sta(per_sta_uora_ra)
        one_ocw = sorted(per_sta_uora_sa["OCW"].unique())[0] if not per_sta_uora_sa.empty else None

        print("\n[INFO] UORA OCW picked per (pMean, RA_RU) by per-STA p99 of Avg_delay_ms:")
        if not best_keys.empty:
          print(best_keys.pivot(index="RA_RU", columns="pMean", values="OCW").to_string())
        print()

        # ---------------- Apply selection ----------------
        if not best_keys.empty:
          per_sta_uora_ra_best = per_sta_uora_ra.merge(best_keys, on=["pMean", "RA_RU", "OCW"], how="inner")
        else:
          per_sta_uora_ra_best = pd.DataFrame()
        if one_ocw is not None:
          per_sta_uora_sa_best = per_sta_uora_sa[per_sta_uora_sa["OCW"] == one_ocw].copy()
        else:
          per_sta_uora_sa_best = pd.DataFrame()
        per_sta_uora_best = pd.concat([per_sta_uora_ra_best, per_sta_uora_sa_best], ignore_index=True)

        # ---------------- Labels + combine ----------------
        def _uora_label(raru):
          if raru == 0: return "SA OFDMA"
          if raru == 1: return "1 RA RU"
          return f"{int(raru)} RA RUs"

        if not per_sta_uora_best.empty:
          per_sta_uora_best["Method"] = "UORA"
          per_sta_uora_best["Label"]  = per_sta_uora_best["RA_RU"].apply(_uora_label)

        per_sta_std = per_sta_other.copy()
        if not per_sta_std.empty:
          per_sta_std["Label"] = per_sta_std["Method"].replace({"CMAB": CMAB_LABEL})

        per_sta_combined = pd.concat([per_sta_std, per_sta_uora_best], ignore_index=True)
        per_sta_combined.to_csv(OUTPUT_CSV, index=False)
        print(f"[OK] per-STA combined CSV: {OUTPUT_CSV}")

        # ---------------- Throughput load + aggregate ----------------
        def aggregate_tp(per_run_df, group_cols):
          g = per_run_df.groupby(group_cols)["Total_Throughput_Mbps"]
          out = g.agg(mean="mean", std="std", n="count").reset_index()
          out["sem"] = out["std"] / np.sqrt(out["n"].clip(lower=1))
          return out

        tp_rows = []
        for method in BASE_DIRS:
          for run in RUNS:
              for pmean in PMEAN_VALUES:
                  df = read_tp(tp_path(method, run, pmean))
                  if df is None: continue
                  tp_rows.append({"Method": method, "pMean": pmean, "Run": run,
                                  "Total_Throughput_Mbps": df["Throughput_Mbps"].sum()})
        for run in RUNS:
          for pmean in PMEAN_VALUES:
              df = read_tp(cmab_tp_path(run, pmean))
              if df is None: continue
              tp_rows.append({"Method": "CMAB", "pMean": pmean, "Run": run,
                              "Total_Throughput_Mbps": df["Throughput_Mbps"].sum()})

        uora_tp_rows = []
        for run in RUNS:
          for pmean in PMEAN_VALUES:
              for raru in nRaRus:
                  for ocw in OCwMin:
                      df = read_tp(uora_tp_path(run, pmean, raru, ocw))
                      if df is None: continue
                      uora_tp_rows.append({"Method": "UORA", "pMean": pmean, "Run": run,
                                           "RA_RU": raru, "OCW": ocw,
                                           "Total_Throughput_Mbps": df["Throughput_Mbps"].sum()})

        tp_std = pd.DataFrame(tp_rows)
        tp_uora = pd.DataFrame(uora_tp_rows)
        agg_std = aggregate_tp(tp_std, ["Method", "pMean"]) if not tp_std.empty else pd.DataFrame()

        if not tp_uora.empty:
          uora_ra_tp = tp_uora[tp_uora["RA_RU"] > 0]
          uora_sa_tp = tp_uora[tp_uora["RA_RU"] == 0]
          uora_ra_tp_best = (uora_ra_tp.merge(best_keys, on=["pMean", "RA_RU", "OCW"], how="inner")
                             if not best_keys.empty else pd.DataFrame())
          uora_sa_tp_best = (uora_sa_tp[uora_sa_tp["OCW"] == one_ocw].copy()
                             if one_ocw is not None else pd.DataFrame())
          uora_tp_best = pd.concat([uora_ra_tp_best, uora_sa_tp_best], ignore_index=True)
          agg_uora = aggregate_tp(uora_tp_best, ["pMean", "RA_RU"])
        else:
          agg_uora = pd.DataFrame()

        # ---------------- Styling ----------------
        HUE_ORDER = ["EDCA", "A2P", "A2PV2", CMAB_LABEL, "SA OFDMA",
                   "1 RA RU", "5 RA RUs", "9 RA RUs", "13 RA RUs", "18 RA RUs"]
        plt.rcParams.update({"font.size": 14, "axes.labelsize": 14, "xtick.labelsize": 12,
                           "ytick.labelsize": 12, "legend.fontsize": 12})

        # ---------------- Plot 1: per-STA mean delay boxplot ----------------
        COMPRESS_FACTOR = 0.075
        BOUND = 100
        def transform(y):
          return y if y <= BOUND else BOUND + (y - BOUND) * COMPRESS_FACTOR

        # Ticks: linear up to BOUND, then compressed decades to 500.
        # Positions are transformed; labels are the real ms values.
        def ticks():
          base = [0, 20, 40, 60, 80, 100, 200, 300, 400, 500]
          return [transform(y) for y in base], base

        per_sta_bp = per_sta_combined.copy()
        per_sta_bp["y"] = per_sta_bp[PER_STA_COL].apply(transform)

        plt.figure(figsize=(9.4, 6.8))
        sns.boxplot(data=per_sta_bp, x="pMean", y="y",
                  hue="Label", hue_order=HUE_ORDER, order=PMEAN_VALUES,
                  showfliers=True, whis=3.0, width=.9)
        ax = plt.gca()

        tick_pos, tick_labels = ticks()
        ax.set_yticks(tick_pos)
        ax.set_yticklabels([str(v) for v in tick_labels])
        ax.set_ylim(bottom=0, top=transform(500) + 2)        # show all data up to 500 ms
        ax.axhline(BOUND, color="grey", linewidth=0.8, linestyle=":")  # compression boundary

        plt.xlabel("Type-2 generation mean interval (s)")
        plt.ylabel("UL Average Delay (ms)")
        ax.grid(True, axis="x", linestyle="--", linewidth=0.5)
        ax.grid(True, axis="y", linestyle=":",  linewidth=0.8, alpha=0.7)
        plt.legend(prop={'size': 12}, title=None)
        plt.tight_layout()
        plt.savefig("fig/iiot/pmean/pmean_iiot_boxplot_delay.png", dpi=300)
        plt.show(); plt.close()
        print("[OK] Plot 1 (per-STA delay boxplot vs pMean) done.")

        # ---------------- Plot 2: throughput vs pMean ----------------
        def yerr(df): return df[ERROR_KIND]
        standard_markers = {"EDCA": ("o", "EDCA"), "A2P": ("s", "A2P"),
                          "A2PV2": ("D", "A2PV2"), "CMAB": ("*", CMAB_LABEL)}

        plt.figure(figsize=(8.6, 5.2))
        for method, (marker, label) in standard_markers.items():
          if agg_std.empty: break
          df_m = agg_std[agg_std["Method"] == method].sort_values("pMean")
          if df_m.empty: continue
          plt.errorbar(df_m["pMean"], df_m["mean"], yerr=yerr(df_m),
                       marker=marker, linewidth=2,
                       markersize=8 if method == "CMAB" else 7, capsize=3, label=label)

        if not agg_uora.empty:
          sa = agg_uora[agg_uora["RA_RU"] == 0].sort_values("pMean")
          if not sa.empty:
              plt.errorbar(sa["pMean"], sa["mean"], yerr=yerr(sa),
                           marker="^", linewidth=2, markersize=7, capsize=3, label="SA OFDMA")
          for raru in nRaRus:
              if raru == 0: continue
              df_u = agg_uora[agg_uora["RA_RU"] == raru].sort_values("pMean")
              if df_u.empty: continue
              plt.errorbar(df_u["pMean"], df_u["mean"], yerr=yerr(df_u),
                           linestyle="--", marker="o", markersize=5, linewidth=2, capsize=2,
                           label=(f"{raru} RA RU" if raru == 1 else f"{raru} RA RUs"))

        plt.xlabel("Type-2 generation mean interval (s)")
        plt.ylabel("Throughput (Mbps)")
        plt.grid(True, linestyle="--", linewidth=0.5)
        plt.xticks(PMEAN_VALUES)
        plt.legend(title=None, prop={"size": 12})
        plt.tight_layout()
        plt.savefig("fig/iiot/pmean/pmean_iiot_throughput.png", dpi=300)
        plt.show(); plt.close()
        print("[OK] Plot 2 (throughput vs pMean) done.")
        _done("iiot_pmean_delay_tput")
    except Exception as _err:
        _done("iiot_pmean_delay_tput", _err)

# ---- iiot_pmean_loss: Traffic-intensity sweep: packet loss ----
if _run("iiot_pmean_loss"):
    try:
        from pathlib import Path
        import pandas as pd
        import matplotlib.pyplot as plt
        import seaborn as sns

        # ---------------- Configuration ----------------
        RUNS = range(1, 11)
        NSTA = 90
        PMEAN_VALUES = [0.00625, 0.0125, 0.025 , 0.05]

        nRaRus = [0, 1, 5, 9, 13, 18]
        OCwMin = [1, 3, 7, 15, 31, 63]

        BASE_DIRS = {
          "EDCA":  Path("iiot_data/iiot_data_pmean/edca"),
          "A2P":   Path("iiot_data/iiot_data_pmean/a2p"),
          "A2PV2": Path("iiot_data/iiot_data_pmean/a2pv2"),
        }
        CMAB_DIR     = Path("iiot_data/iiot_data_pmean/cmab")
        CMAB_VARIANT = "EXP3M_Binary_g0.3"
        CMAB_LABEL   = "EXP3M"

        DELAY_COL    = "delay_ms"
        PER_STA_COL  = "Avg_delay_ms"
        DATA_FILE    = "type2_packets.out"
        PER_STA_FILE = "per_sta_stats.out"
        DEADLINE_MS  = 20
        ERRORBAR     = "sd"

        def ptag(pmean):
          return "" if abs(pmean - 0.1) < 1e-9 else f"_pMean-{pmean}"

        def read_csv(path):
          if not path.exists(): return None
          df = pd.read_csv(path, delimiter="\t")
          return None if df.dropna(how="all").empty else df

        def t2_path(method, run, pmean):
          return BASE_DIRS[method] / f"{run}_run-{NSTA}_sta{ptag(pmean)}" / DATA_FILE
        def uora_path(run, pmean, raru, ocw):
          return (Path("iiot_data/iiot_data_pmean/uora") / f"ocwMin_{ocw}"
                  / f"{run}_run-{NSTA}_sta-{raru}_rarus{ptag(pmean)}" / DATA_FILE)
        def uora_path_per_sta(run, pmean, raru, ocw):
          return (Path("iiot_data/iiot_data_pmean/uora") / f"ocwMin_{ocw}"
                  / f"{run}_run-{NSTA}_sta-{raru}_rarus{ptag(pmean)}" / PER_STA_FILE)
        def cmab_path(run, pmean):
          return CMAB_DIR / CMAB_VARIANT / f"{run}_run-{NSTA}_sta{ptag(pmean)}" / DATA_FILE

        # ---- per-packet loaders ----
        def process_method(method):
          rows = []
          for run in RUNS:
              for pmean in PMEAN_VALUES:
                  df = read_csv(t2_path(method, run, pmean))
                  if df is None or DELAY_COL not in df.columns: continue
                  df = df[[DELAY_COL]].copy(); df["pMean"] = pmean; df["Method"] = method; df["Run"] = run
                  rows.append(df)
          return rows

        def process_uora_packets():
          rows = []
          for run in RUNS:
              for pmean in PMEAN_VALUES:
                  for raru in nRaRus:
                      for ocw in OCwMin:
                          df = read_csv(uora_path(run, pmean, raru, ocw))
                          if df is None or DELAY_COL not in df.columns: continue
                          df = df[[DELAY_COL]].copy()
                          df["pMean"] = pmean; df["Method"] = "UORA"; df["RA_RU"] = raru
                          df["OCW"] = ocw; df["Run"] = run
                          rows.append(df)
          return rows

        def process_cmab():
          rows = []
          for run in RUNS:
              for pmean in PMEAN_VALUES:
                  df = read_csv(cmab_path(run, pmean))
                  if df is None or DELAY_COL not in df.columns: continue
                  df = df[[DELAY_COL]].copy(); df["pMean"] = pmean; df["Method"] = "CMAB"; df["Run"] = run
                  rows.append(df)
          return rows

        def _load_per_sta(path, extra_cols):
          df = read_csv(path)
          if df is None or PER_STA_COL not in df.columns: return None
          if "Class" in df.columns:    df = df[df["Class"] == 2]
          if "RX_bytes" in df.columns: df = df[df["RX_bytes"] > 0]
          if df.empty: return None
          out = df[[PER_STA_COL]].copy()
          for k, v in extra_cols.items(): out[k] = v
          return out

        def process_uora_per_sta():
          rows = []
          for run in RUNS:
              for pmean in PMEAN_VALUES:
                  for raru in nRaRus:
                      for ocw in OCwMin:
                          d = _load_per_sta(uora_path_per_sta(run, pmean, raru, ocw),
                                            {"pMean": pmean, "Run": run, "RA_RU": raru, "OCW": ocw, "Method": "UORA"})
                          if d is not None: rows.append(d)
          return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()

        # ---- Load ----
        all_rows = []
        for method in BASE_DIRS:
          print(f"[INFO] {method} (per-packet)"); all_rows.extend(process_method(method))
        print("[INFO] UORA per-packet"); all_rows.extend(process_uora_packets())
        print(f"[INFO] CMAB per-packet ({CMAB_VARIANT})"); all_rows.extend(process_cmab())
        if not all_rows: raise RuntimeError("No per-packet data collected.")
        dplt_full = pd.concat(all_rows, ignore_index=True)

        print("[INFO] UORA per-STA (for OCW selection)")
        per_sta_uora = process_uora_per_sta()

        # ---- UORA OCW selection per (pMean, RA_RU) ----
        def select_best_ocw_per_sta(per_sta_df, delay_col=PER_STA_COL):
          if per_sta_df.empty: return pd.DataFrame()
          grouped = per_sta_df.groupby(["pMean","RA_RU","OCW"])[delay_col].quantile(0.99).reset_index()
          idx = grouped.groupby(["pMean","RA_RU"])[delay_col].idxmin()
          return grouped.loc[idx][["pMean","RA_RU","OCW"]].reset_index(drop=True)

        best_keys = select_best_ocw_per_sta(per_sta_uora[per_sta_uora["RA_RU"] > 0])
        uora_sa_pkt = dplt_full[(dplt_full["Method"] == "UORA") & (dplt_full["RA_RU"] == 0)]
        one_ocw = sorted(uora_sa_pkt["OCW"].unique())[0] if not uora_sa_pkt.empty else None

        # ---- Combine for PLR ----
        uora_full = dplt_full[dplt_full["Method"] == "UORA"]
        uora_ra_full = uora_full[uora_full["RA_RU"] > 0]
        uora_sa_full = uora_full[uora_full["RA_RU"] == 0]
        uora_ra_full_best = (uora_ra_full.merge(best_keys, on=["pMean","RA_RU","OCW"], how="inner")
                           if not best_keys.empty else pd.DataFrame())
        uora_sa_full_best = (uora_sa_full[uora_sa_full["OCW"] == one_ocw].copy()
                           if one_ocw is not None else pd.DataFrame())
        uora_best_full = pd.concat([uora_ra_full_best, uora_sa_full_best], ignore_index=True)

        def _uora_label(raru):
          if raru == 0: return "SA OFDMA"
          if raru == 1: return "1 RA RU"
          return f"{int(raru)} RA RUs"

        std_df_full = dplt_full[dplt_full["Method"].isin(list(BASE_DIRS) + ["CMAB"])].copy()
        std_df_full["Label"] = std_df_full["Method"].replace({"CMAB": CMAB_LABEL})
        if not uora_best_full.empty:
          uora_best_full["Label"] = uora_best_full["RA_RU"].apply(_uora_label)
        combined_df_full = pd.concat([std_df_full, uora_best_full], ignore_index=True)

        # ---- PLR per run ----
        plr_per_run = (combined_df_full
                     .groupby(["Label", "pMean", "Run"])
                     .apply(lambda g: 100 * (g[DELAY_COL] > DEADLINE_MS).mean())
                     .reset_index(name="plr_pct"))

        HUE_ORDER = ["EDCA", "A2P", "A2PV2", CMAB_LABEL, "SA OFDMA",
                   "1 RA RU", "5 RA RUs", "9 RA RUs", "13 RA RUs", "18 RA RUs"]
        plr_per_run["Label"] = pd.Categorical(plr_per_run["Label"], categories=HUE_ORDER, ordered=True)
        plr_per_run = plr_per_run.sort_values(["Label", "pMean", "Run"])

        # ---- Plot ----
        plt.rcParams.update({"font.size": 14, "axes.labelsize": 14, "xtick.labelsize": 12,
                           "ytick.labelsize": 12, "legend.fontsize": 12})
        plt.figure(figsize=(8.6, 5.2))
        ax = sns.lineplot(data=plr_per_run, x="pMean", y="plr_pct",
                        hue="Label", hue_order=HUE_ORDER,
                        style="Label", markers=True, dashes=False, linewidth=2,
                        errorbar=ERRORBAR, err_style="bars",
                        err_kws={"capsize": 3, "capthick": 1, "elinewidth": 1})
        for line in ax.lines: line.set_markersize(7)
        plt.xlabel("Type-2 generation mean interval (s)")
        plt.ylabel(f"Packet loss ratio (% packets > {DEADLINE_MS} ms)")
        plt.xticks(PMEAN_VALUES)
        plt.grid(True, linestyle="--", linewidth=0.5)
        plt.legend(prop={'size': 11}, title=None)
        plt.tight_layout()
        plt.savefig("fig/iiot/pmean/pmean_iiot_plr.png", dpi=300)
        plt.show(); plt.close()
        print("[OK] PLR vs pMean plot done.")
        _done("iiot_pmean_loss")
    except Exception as _err:
        _done("iiot_pmean_loss", _err)

# ---- iiot_pmean_type1: Traffic-intensity sweep: type-1 delay and throughput ----
if _run("iiot_pmean_type1"):
    try:
        from pathlib import Path
        import pandas as pd
        import numpy as np
        import matplotlib.pyplot as plt
        import seaborn as sns

        # ---------------- Configuration ----------------
        RUNS = range(1, 11)
        NSTA = 90
        PMEAN_VALUES = [0.00625, 0.0125, 0.025 , 0.05]
        nRaRus = [0, 1, 5, 9, 13, 18]
        OCwMin = [1, 3, 7, 15, 31, 63]

        BASE_DIRS = {"EDCA": Path("iiot_data/iiot_data_pmean/edca"), "A2P": Path("iiot_data/iiot_data_pmean/a2p"),
                   "A2PV2": Path("iiot_data/iiot_data_pmean/a2pv2")}
        CMAB_DIR, CMAB_VARIANT, CMAB_LABEL = Path("iiot_data/iiot_data_pmean/cmab"), "EXP3M_Binary_g0.3", "EXP3M"

        PER_STA_COL, PER_STA_FILE, TP_FILE = "Avg_delay_ms", "per_sta_stats.out", "throughput.out"
        ERROR_KIND = "std"

        def ptag(p): return "" if abs(p - 0.1) < 1e-9 else f"_pMean-{p}"
        def read_tsv(path):
          if not path.exists(): return None
          df = pd.read_csv(path, delimiter="\t")
          return None if df.dropna(how="all").empty else df

        def ps_path(method, run, p):  return BASE_DIRS[method] / f"{run}_run-{NSTA}_sta{ptag(p)}" / PER_STA_FILE
        def tp_path(method, run, p):  return BASE_DIRS[method] / f"{run}_run-{NSTA}_sta{ptag(p)}" / TP_FILE
        def u_ps(run, p, raru, ocw):  return Path("iiot_data/iiot_data_pmean/uora")/f"ocwMin_{ocw}"/f"{run}_run-{NSTA}_sta-{raru}_rarus{ptag(p)}"/PER_STA_FILE
        def u_tp(run, p, raru, ocw):  return Path("iiot_data/iiot_data_pmean/uora")/f"ocwMin_{ocw}"/f"{run}_run-{NSTA}_sta-{raru}_rarus{ptag(p)}"/TP_FILE
        def c_ps(run, p):             return CMAB_DIR/CMAB_VARIANT/f"{run}_run-{NSTA}_sta{ptag(p)}"/PER_STA_FILE
        def c_tp(run, p):             return CMAB_DIR/CMAB_VARIANT/f"{run}_run-{NSTA}_sta{ptag(p)}"/TP_FILE

        # ---- type-1 per-STA delay rows + type-1 throughput (byte-share) per cell ----
        def cell_rows(ps_p, tp_p, extra):
          """Return (delay_rows_df, tp_value) for one cell, type-1 only."""
          ps = read_tsv(ps_p)
          if ps is None or PER_STA_COL not in ps.columns or "Class" not in ps.columns:
              return None, None
          t1 = ps[ps["Class"] == 1]
          if "RX_bytes" in ps.columns:
              t1 = t1[t1["RX_bytes"] > 0]
          if t1.empty:
              return None, None
          # delay rows
          drow = t1[[PER_STA_COL]].copy()
          for k, v in extra.items(): drow[k] = v
          # throughput share
          tp = read_tsv(tp_p); tpval = None
          if tp is not None and "Throughput_Mbps" in tp.columns and "RX_bytes" in ps.columns:
              tot = ps["RX_bytes"].sum()
              if tot > 0:
                  tpval = float(tp["Throughput_Mbps"].sum()) * (t1["RX_bytes"].sum() / tot)
          return drow, tpval

        # ---- type-2 per-STA p99 -> UORA OCW selection (same operating point) --------
        def t2_p99_ocw():
          rows = []
          for run in RUNS:
              for p in PMEAN_VALUES:
                  for raru in nRaRus:
                      for ocw in OCwMin:
                          ps = read_tsv(u_ps(run, p, raru, ocw))
                          if ps is None or PER_STA_COL not in ps.columns: continue
                          t2 = ps[(ps["Class"] == 2) & (ps.get("RX_bytes", 1) > 0)]
                          if t2.empty: continue
                          d = t2[[PER_STA_COL]].copy()
                          d["pMean"], d["RA_RU"], d["OCW"] = p, raru, ocw
                          rows.append(d)
          if not rows: return pd.DataFrame()
          df = pd.concat(rows, ignore_index=True)
          g = df[df["RA_RU"] > 0].groupby(["pMean","RA_RU","OCW"])[PER_STA_COL].quantile(0.99).reset_index()
          idx = g.groupby(["pMean","RA_RU"])[PER_STA_COL].idxmin()
          return g.loc[idx][["pMean","RA_RU","OCW"]].reset_index(drop=True)

        best_keys = t2_p99_ocw()

        # ---- collect type-1 delay + throughput ----
        delay_rows, tp_rows = [], []
        for method in BASE_DIRS:
          for run in RUNS:
              for p in PMEAN_VALUES:
                  d, tpv = cell_rows(ps_path(method, run, p), tp_path(method, run, p),
                                     {"pMean": p, "Run": run, "Label": method})
                  if d is not None: delay_rows.append(d)
                  if tpv is not None: tp_rows.append({"Label": method, "pMean": p, "Run": run, "tp": tpv})
        for run in RUNS:
          for p in PMEAN_VALUES:
              d, tpv = cell_rows(c_ps(run, p), c_tp(run, p), {"pMean": p, "Run": run, "Label": CMAB_LABEL})
              if d is not None: delay_rows.append(d)
              if tpv is not None: tp_rows.append({"Label": CMAB_LABEL, "pMean": p, "Run": run, "tp": tpv})

        def u_label(raru): return "SA OFDMA" if raru == 0 else ("1 RA RU" if raru == 1 else f"{raru} RA RUs")
        one_ocw = sorted(OCwMin)[0]
        for run in RUNS:
          for p in PMEAN_VALUES:
              for raru in nRaRus:
                  if raru > 0:
                      sel = best_keys[(best_keys.pMean == p) & (best_keys.RA_RU == raru)]
                      if sel.empty: continue
                      ocws = [int(sel.OCW.iloc[0])]
                  else:
                      ocws = [one_ocw]
                  for ocw in ocws:
                      d, tpv = cell_rows(u_ps(run, p, raru, ocw), u_tp(run, p, raru, ocw),
                                         {"pMean": p, "Run": run, "Label": u_label(raru)})
                      if d is not None: delay_rows.append(d)
                      if tpv is not None: tp_rows.append({"Label": u_label(raru), "pMean": p, "Run": run, "tp": tpv})

        delay_df = pd.concat(delay_rows, ignore_index=True)
        delay_df = delay_df[delay_df[PER_STA_COL] <= 1000]
        tp_df = pd.DataFrame(tp_rows)
        agg_tp = tp_df.groupby(["Label","pMean"])["tp"].agg(mean="mean", std="std", n="count").reset_index()
        agg_tp["sem"] = agg_tp["std"] / np.sqrt(agg_tp["n"].clip(lower=1))

        HUE_ORDER = ["EDCA","A2P","A2PV2",CMAB_LABEL,"SA OFDMA","1 RA RU","5 RA RUs","9 RA RUs","13 RA RUs","18 RA RUs"]
        plt.rcParams.update({"font.size":14,"axes.labelsize":14,"xtick.labelsize":12,"ytick.labelsize":12,"legend.fontsize":12})

        # ---------------- Plot A: type-1 per-STA avg delay ----------------
        plt.figure(figsize=(9.4, 6.8))
        sns.boxplot(data=delay_df, x="pMean", y=PER_STA_COL, hue="Label",
                  hue_order=HUE_ORDER, order=PMEAN_VALUES, showfliers=True, whis=3.0, width=.9)
        ax = plt.gca()
        plt.xlabel("Type-2 generation mean interval (s)")
        plt.ylabel("Type-1 UL Average Delay (ms)")
        ax.grid(True, axis="x", linestyle="--", linewidth=0.5)
        ax.grid(True, axis="y", linestyle=":", linewidth=0.8, alpha=0.7)
        plt.legend(prop={'size':12}, title=None)
        plt.tight_layout()
        #plt.savefig("fig/iiot/pmean/pmean_iiot_type1_delay.png", dpi=300)
        plt.show(); plt.close()
        print("[OK] type-1 delay plot done.")

        # ---------------- Plot B: type-1 throughput ----------------
        markers = {"EDCA":"o","A2P":"s","A2PV2":"D",CMAB_LABEL:"*","SA OFDMA":"^"}
        plt.figure(figsize=(8.6, 5.2))
        for label in HUE_ORDER:
          df_l = agg_tp[agg_tp["Label"] == label].sort_values("pMean")
          if df_l.empty: continue
          if label in markers:
              plt.errorbar(df_l["pMean"], df_l["mean"], yerr=df_l[ERROR_KIND],
                           marker=markers[label], linewidth=2,
                           markersize=8 if label == CMAB_LABEL else 7, capsize=3, label=label)
          else:
              plt.errorbar(df_l["pMean"], df_l["mean"], yerr=df_l[ERROR_KIND],
                           linestyle="--", marker="o", markersize=5, linewidth=2, capsize=2, label=label)
        plt.xlabel("Type-2 generation mean interval (s)")
        plt.ylabel("Type-1 Throughput (Mbps)")
        plt.xticks(PMEAN_VALUES)
        plt.grid(True, linestyle="--", linewidth=0.5)
        plt.legend(title=None, prop={"size":12})
        plt.tight_layout()
        #plt.savefig("fig/iiot/pmean/pmean_iiot_type1_throughput.png", dpi=300)
        plt.show(); plt.close()
        print("[OK] type-1 throughput plot done.")
        _done("iiot_pmean_type1")
    except Exception as _err:
        _done("iiot_pmean_type1", _err)

# ---- iiot_pmean_grid: Traffic-intensity sweep: summary grid ----
if _run("iiot_pmean_grid"):
    try:
        from pathlib import Path
        import pandas as pd, numpy as np
        import matplotlib.pyplot as plt

        # ---------------- Configuration ----------------
        RUNS = range(1, 11)
        NSTA_VALUES  = [1, 30, 60, 90]
        PMEAN_VALUES = [0.00625, 0.0125, 0.025, 0.05]
        DEADLINE_MS  = 20

        nRaRus = [0, 1, 5, 9, 13, 18]
        OCwMin = [1, 3, 7, 15, 31, 63]
        BASE_DIRS = {"EDCA": Path("iiot_data/iiot_data_pmean/edca"), "A2P": Path("iiot_data/iiot_data_pmean/a2p"), "A2PV2": Path("iiot_data/iiot_data_pmean/a2pv2")}
        CMAB_DIR, CMAB_VARIANT, CMAB_LABEL = Path("iiot_data/iiot_data_pmean/cmab"), "EXP3M_Binary_g0.3", "EXP3M"
        DELAY_COL, PER_STA_COL = "delay_ms", "Avg_delay_ms"
        DATA_FILE, PER_STA_FILE, TP_FILE = "type2_packets.out", "per_sta_stats.out", "throughput.out"

        def ptag(p): return "" if abs(p - 0.1) < 1e-9 else f"_pMean-{p}"
        def rd(path):
            if not path.exists(): return None
            df = pd.read_csv(path, delimiter="\t")
            return None if df.dropna(how="all").empty else df

        def d_pkt(method, run, n, p):  return BASE_DIRS[method]/f"{run}_run-{n}_sta{ptag(p)}"/DATA_FILE
        def d_tp(method, run, n, p):   return BASE_DIRS[method]/f"{run}_run-{n}_sta{ptag(p)}"/TP_FILE
        def u_pkt(run, n, p, r, o):    return Path("iiot_data/iiot_data_pmean/uora")/f"ocwMin_{o}"/f"{run}_run-{n}_sta-{r}_rarus{ptag(p)}"/DATA_FILE
        def u_tp(run, n, p, r, o):     return Path("iiot_data/iiot_data_pmean/uora")/f"ocwMin_{o}"/f"{run}_run-{n}_sta-{r}_rarus{ptag(p)}"/TP_FILE
        def u_ps(run, n, p, r, o):     return Path("iiot_data/iiot_data_pmean/uora")/f"ocwMin_{o}"/f"{run}_run-{n}_sta-{r}_rarus{ptag(p)}"/PER_STA_FILE
        def c_pkt(run, n, p):          return CMAB_DIR/CMAB_VARIANT/f"{run}_run-{n}_sta{ptag(p)}"/DATA_FILE
        def c_tp(run, n, p):           return CMAB_DIR/CMAB_VARIANT/f"{run}_run-{n}_sta{ptag(p)}"/TP_FILE

        def cell_metrics(delays, tps):
            """delays: list of arrays (per run); tps: list of floats. -> (p99, plr, mean_tp)."""
            allp = np.concatenate(delays) if delays else np.array([])
            p99 = np.percentile(allp, 99) if allp.size else np.nan
            plr = 100 * (allp > DEADLINE_MS).mean() if allp.size else np.nan
            tp  = np.mean(tps) if tps else np.nan
            return p99, plr, tp

        # ---- UORA OCW selection per (nSta, pMean, RA_RU) by type-2 p99 of Avg_delay -
        sel_rows = []
        for run in RUNS:
          for n in NSTA_VALUES:
            for p in PMEAN_VALUES:
              for r in nRaRus:
                for o in OCwMin:
                  ps = rd(u_ps(run, n, p, r, o))
                  if ps is None or PER_STA_COL not in ps.columns: continue
                  t2 = ps[(ps["Class"] == 2) & (ps.get("RX_bytes", 1) > 0)]
                  if t2.empty: continue
                  d = t2[[PER_STA_COL]].copy(); d["nSta"], d["pMean"], d["RA_RU"], d["OCW"] = n, p, r, o
                  sel_rows.append(d)
        sel = pd.concat(sel_rows, ignore_index=True) if sel_rows else pd.DataFrame()
        if not sel.empty:
            g = sel[sel.RA_RU > 0].groupby(["nSta","pMean","RA_RU","OCW"])[PER_STA_COL].quantile(0.99).reset_index()
            idx = g.groupby(["nSta","pMean","RA_RU"])[PER_STA_COL].idxmin()
            best = g.loc[idx][["nSta","pMean","RA_RU","OCW"]]
            best = {(r.nSta, r.pMean, r.RA_RU): int(r.OCW) for r in best.itertuples()}
        else:
            best = {}
        one_ocw = sorted(OCwMin)[0]

        def u_label(r): return "SA OFDMA" if r == 0 else ("1 RA RU" if r == 1 else f"{r} RA RUs")

        # ---- collect metrics per (Label, nSta, pMean) ----
        recs = []
        def add(label, n, p, delays, tps):
            p99, plr, tp = cell_metrics(delays, tps)
            recs.append({"Label": label, "nSta": n, "pMean": p, "p99": p99, "plr": plr, "tp": tp})

        for method in BASE_DIRS:
            for n in NSTA_VALUES:
                for p in PMEAN_VALUES:
                    dl, tp = [], []
                    for run in RUNS:
                        pk = rd(d_pkt(method, run, n, p))
                        if pk is not None and DELAY_COL in pk.columns: dl.append(pk[DELAY_COL].values)
                        t = rd(d_tp(method, run, n, p))
                        if t is not None and "Throughput_Mbps" in t.columns: tp.append(t["Throughput_Mbps"].sum())
                    add(method, n, p, dl, tp)

        for n in NSTA_VALUES:
            for p in PMEAN_VALUES:
                dl, tp = [], []
                for run in RUNS:
                    pk = rd(c_pkt(run, n, p))
                    if pk is not None and DELAY_COL in pk.columns: dl.append(pk[DELAY_COL].values)
                    t = rd(c_tp(run, n, p))
                    if t is not None and "Throughput_Mbps" in t.columns: tp.append(t["Throughput_Mbps"].sum())
                add(CMAB_LABEL, n, p, dl, tp)

        for r in nRaRus:
            for n in NSTA_VALUES:
                for p in PMEAN_VALUES:
                    o = best.get((n, p, r), one_ocw) if r > 0 else one_ocw
                    dl, tp = [], []
                    for run in RUNS:
                        pk = rd(u_pkt(run, n, p, r, o))
                        if pk is not None and DELAY_COL in pk.columns: dl.append(pk[DELAY_COL].values)
                        t = rd(u_tp(run, n, p, r, o))
                        if t is not None and "Throughput_Mbps" in t.columns: tp.append(t["Throughput_Mbps"].sum())
                    add(u_label(r), n, p, dl, tp)

        df = pd.DataFrame(recs)

        # ---------------- Faceted grid: rows=metric, cols=pMean ----------------
        HUE_ORDER = ["EDCA","A2P","A2PV2",CMAB_LABEL,"SA OFDMA","1 RA RU","5 RA RUs","9 RA RUs","13 RA RUs","18 RA RUs"]
        cmap = plt.cm.tab10(np.linspace(0, 1, len(HUE_ORDER)))
        colors = {lab: cmap[i] for i, lab in enumerate(HUE_ORDER)}
        metrics = [("p99", "Type-2 p99 delay (ms)"), ("tp", "Throughput (Mbps)"), ("plr", f"PLR (% > {DEADLINE_MS} ms)")]

        plt.rcParams.update({"font.size": 11})
        nrow, ncol = len(metrics), len(PMEAN_VALUES)
        fig, axes = plt.subplots(nrow, ncol, figsize=(2.7*ncol, 2.3*nrow), sharex="col", sharey="row")

        for ri, (mkey, mlabel) in enumerate(metrics):
            for ci, p in enumerate(PMEAN_VALUES):
                ax = axes[ri, ci]
                sub = df[df["pMean"] == p]
                for lab in HUE_ORDER:
                    s = sub[sub["Label"] == lab].sort_values("nSta")
                    if s.empty or s[mkey].isna().all(): continue
                    ax.plot(s["nSta"], s[mkey], marker="o", ms=4, lw=1.6, color=colors[lab], label=lab)
                if ri == 0: ax.set_title(f"pMean={p}", fontsize=10)
                if ci == 0: ax.set_ylabel(mlabel, fontsize=10)
                if ri == nrow-1: ax.set_xlabel("nSta")
                ax.set_xticks(NSTA_VALUES)
                ax.grid(True, ls="--", lw=0.4, alpha=0.6)

        handles, labels = axes[0, 0].get_legend_handles_labels()
        fig.legend(handles, labels, loc="upper center", ncol=5, fontsize=9,
                   bbox_to_anchor=(0.5, 1.04), frameon=False)
        fig.tight_layout(rect=[0, 0, 1, 0.97])
        fig.savefig("fig/iiot/pmean/sweep_grid.png", dpi=300, bbox_inches="tight")
        plt.show(); plt.close()
        print("[OK] faceted sweep grid done.")
        _done("iiot_pmean_grid")
    except Exception as _err:
        _done("iiot_pmean_grid", _err)

# ---- iiot_pmean_type1_grid: Traffic-intensity sweep: type-1 throughput grid ----
if _run("iiot_pmean_type1_grid"):
    try:
        from pathlib import Path
        import pandas as pd, numpy as np
        import matplotlib.pyplot as plt

        # ---------------- Configuration ----------------
        RUNS = range(1, 11)
        NSTA_VALUES  = [1, 30, 60, 90]
        PMEAN_VALUES = [0.00625, 0.0125, 0.025, 0.05]

        nRaRus = [0, 1, 5, 9, 13, 18]
        OCwMin = [1, 3, 7, 15, 31, 63]
        BASE_DIRS = {"EDCA": Path("iiot_data/iiot_data_pmean/edca"), "A2P": Path("iiot_data/iiot_data_pmean/a2p"), "A2PV2": Path("iiot_data/iiot_data_pmean/a2pv2")}
        CMAB_DIR, CMAB_VARIANT, CMAB_LABEL = Path("iiot_data/iiot_data_pmean/cmab"), "EXP3M_Binary_g0.3", "EXP3M"
        PER_STA_COL, PER_STA_FILE, TP_FILE = "Avg_delay_ms", "per_sta_stats.out", "throughput.out"

        def ptag(p): return "" if abs(p - 0.1) < 1e-9 else f"_pMean-{p}"
        def rd(path):
            if not path.exists(): return None
            df = pd.read_csv(path, delimiter="\t")
            return None if df.dropna(how="all").empty else df

        def d_ps(m, run, n, p): return BASE_DIRS[m]/f"{run}_run-{n}_sta{ptag(p)}"/PER_STA_FILE
        def d_tp(m, run, n, p): return BASE_DIRS[m]/f"{run}_run-{n}_sta{ptag(p)}"/TP_FILE
        def u_ps(run, n, p, r, o): return Path("iiot_data/iiot_data_pmean/uora")/f"ocwMin_{o}"/f"{run}_run-{n}_sta-{r}_rarus{ptag(p)}"/PER_STA_FILE
        def u_tp(run, n, p, r, o): return Path("iiot_data/iiot_data_pmean/uora")/f"ocwMin_{o}"/f"{run}_run-{n}_sta-{r}_rarus{ptag(p)}"/TP_FILE
        def c_ps(run, n, p): return CMAB_DIR/CMAB_VARIANT/f"{run}_run-{n}_sta{ptag(p)}"/PER_STA_FILE
        def c_tp(run, n, p): return CMAB_DIR/CMAB_VARIANT/f"{run}_run-{n}_sta{ptag(p)}"/TP_FILE

        def type1_tp(ps_path, tp_path):
            """aggregate throughput * type-1 byte share. None if unavailable."""
            ps, tp = rd(ps_path), rd(tp_path)
            if ps is None or tp is None: return None
            if "Class" not in ps.columns or "RX_bytes" not in ps.columns or "Throughput_Mbps" not in tp.columns:
                return None
            tot = ps["RX_bytes"].sum()
            if tot <= 0: return None
            t1 = ps[ps["Class"] == 1]["RX_bytes"].sum()
            return float(tp["Throughput_Mbps"].sum()) * (t1 / tot)

        # ---- UORA OCW per (nSta, pMean, RA_RU) by type-2 p99 (same operating point) -
        sel_rows = []
        for run in RUNS:
          for n in NSTA_VALUES:
            for p in PMEAN_VALUES:
              for r in nRaRus:
                for o in OCwMin:
                  ps = rd(u_ps(run, n, p, r, o))
                  if ps is None or PER_STA_COL not in ps.columns: continue
                  t2 = ps[(ps["Class"] == 2) & (ps.get("RX_bytes", 1) > 0)]
                  if t2.empty: continue
                  d = t2[[PER_STA_COL]].copy(); d["nSta"], d["pMean"], d["RA_RU"], d["OCW"] = n, p, r, o
                  sel_rows.append(d)
        sel = pd.concat(sel_rows, ignore_index=True) if sel_rows else pd.DataFrame()
        if not sel.empty:
            g = sel[sel.RA_RU > 0].groupby(["nSta","pMean","RA_RU","OCW"])[PER_STA_COL].quantile(0.99).reset_index()
            idx = g.groupby(["nSta","pMean","RA_RU"])[PER_STA_COL].idxmin()
            best = {(r.nSta, r.pMean, r.RA_RU): int(r.OCW) for r in g.loc[idx].itertuples()}
        else:
            best = {}
        one_ocw = sorted(OCwMin)[0]
        def u_label(r): return "SA OFDMA" if r == 0 else ("1 RA RU" if r == 1 else f"{r} RA RUs")

        # ---- collect type-1 throughput per (Label, nSta, pMean) ----
        recs = []
        def add(label, n, p, tps):
            recs.append({"Label": label, "nSta": n, "pMean": p,
                         "tp": np.mean(tps) if tps else np.nan,
                         "sd": np.std(tps) if tps else np.nan})

        for m in BASE_DIRS:
            for n in NSTA_VALUES:
                for p in PMEAN_VALUES:
                    tps = [v for run in RUNS if (v := type1_tp(d_ps(m,run,n,p), d_tp(m,run,n,p))) is not None]
                    add(m, n, p, tps)
        for n in NSTA_VALUES:
            for p in PMEAN_VALUES:
                tps = [v for run in RUNS if (v := type1_tp(c_ps(run,n,p), c_tp(run,n,p))) is not None]
                add(CMAB_LABEL, n, p, tps)
        for r in nRaRus:
            for n in NSTA_VALUES:
                for p in PMEAN_VALUES:
                    o = best.get((n, p, r), one_ocw) if r > 0 else one_ocw
                    tps = [v for run in RUNS if (v := type1_tp(u_ps(run,n,p,r,o), u_tp(run,n,p,r,o))) is not None]
                    add(u_label(r), n, p, tps)

        df = pd.DataFrame(recs)

        # ---------------- 1-row faceted grid: cols = pMean ----------------
        HUE_ORDER = ["EDCA","A2P","A2PV2",CMAB_LABEL,"SA OFDMA","1 RA RU","5 RA RUs","9 RA RUs","13 RA RUs","18 RA RUs"]
        cmap = plt.cm.tab10(np.linspace(0, 1, len(HUE_ORDER)))
        colors = {lab: cmap[i] for i, lab in enumerate(HUE_ORDER)}

        plt.rcParams.update({"font.size": 11})
        ncol = len(PMEAN_VALUES)
        fig, axes = plt.subplots(1, ncol, figsize=(2.9*ncol, 2.8), sharey=True)
        for ci, p in enumerate(PMEAN_VALUES):
            ax = axes[ci]
            sub = df[df["pMean"] == p]
            for lab in HUE_ORDER:
                s = sub[sub["Label"] == lab].sort_values("nSta")
                if s.empty or s["tp"].isna().all(): continue
                ax.plot(s["nSta"], s["tp"], marker="o", ms=4, lw=1.6, color=colors[lab], label=lab)
            ax.set_title(f"pMean={p}", fontsize=10)
            ax.set_xlabel("nSta")
            if ci == 0: ax.set_ylabel("Type-1 Throughput (Mbps)", fontsize=10)
            ax.set_xticks(NSTA_VALUES)
            ax.grid(True, ls="--", lw=0.4, alpha=0.6)

        handles, labels = axes[0].get_legend_handles_labels()
        fig.legend(handles, labels, loc="upper center", ncol=5, fontsize=9,
                   bbox_to_anchor=(0.5, 1.12), frameon=False)
        fig.tight_layout(rect=[0, 0, 1, 0.92])
        fig.savefig("fig/iiot/pmean/type1_throughput_grid.png", dpi=300, bbox_inches="tight")
        plt.show(); plt.close()
        print("[OK] type-1 throughput grid done.")
        _done("iiot_pmean_type1_grid")
    except Exception as _err:
        _done("iiot_pmean_type1_grid", _err)

# ---- iiot_type1_box_bars: Type-1 stations: box plots and bars ----
if _run("iiot_type1_box_bars"):
    try:
        from pathlib import Path
        import pandas as pd
        import numpy as np
        import matplotlib.pyplot as plt
        import seaborn as sns


        # ---------------- Configuration ----------------
        RUNS = range(1, 11)
        NSTA_VALUES  = [1, 30, 60, 90]
        PMEAN_VALUES = [0.00625, 0.0125, 0.025, 0.05, 0.15, 0.2]   # smaller = heavier load

        nRaRus = [0, 1, 5, 9, 13, 18]
        OCwMin = [1, 3, 7, 15, 31, 63]

        BASE_DIRS = {
            "EDCA":  Path("iiot_data/iiot_data_pmean/edca"),
            "A2P":   Path("iiot_data/iiot_data_pmean/a2p"),
            "A2PV2": Path("iiot_data/iiot_data_pmean/a2pv2"),
        }
        CMAB_DIR     = Path("iiot_data/iiot_data_pmean/cmab")
        CMAB_VARIANT = "EXP3M_Binary_g0.3"
        CMAB_LABEL   = "EXP3M"

        OUTPUT_CSV     = "iiot_pmean_type1_throughput.csv"
        OUTPUT_CSV_DLY = "iiot_pmean_type1_delay.csv"
        PER_STA_COL  = "Avg_delay_ms"
        PER_STA_FILE = "per_sta_stats.out"
        TP_FILE      = "throughput.out"
        ERROR_KIND   = "std"


        # ---------------- Helpers ----------------
        def ptag(pmean):
            return "" if abs(pmean - 0.1) < 1e-9 else f"_pMean-{pmean}"

        def read_csv(path: Path):
            if not path.exists():
                return None
            df = pd.read_csv(path, delimiter="\t")
            if df.dropna(how="all").empty:
                return None
            return df

        def per_sta_path(method, run, nsta, pmean):
            return BASE_DIRS[method] / f"{run}_run-{nsta}_sta{ptag(pmean)}" / PER_STA_FILE
        def uora_per_sta_path(run, nsta, pmean, raru, ocw):
            return (Path("iiot_data/iiot_data_pmean/uora") / f"ocwMin_{ocw}"
                    / f"{run}_run-{nsta}_sta-{raru}_rarus{ptag(pmean)}" / PER_STA_FILE)
        def cmab_per_sta_path(run, nsta, pmean):
            return CMAB_DIR / CMAB_VARIANT / f"{run}_run-{nsta}_sta{ptag(pmean)}" / PER_STA_FILE
        def tp_path(method, run, nsta, pmean):
            return BASE_DIRS[method] / f"{run}_run-{nsta}_sta{ptag(pmean)}" / TP_FILE
        def uora_tp_path(run, nsta, pmean, raru, ocw):
            return (Path("iiot_data/iiot_data_pmean/uora") / f"ocwMin_{ocw}"
                    / f"{run}_run-{nsta}_sta-{raru}_rarus{ptag(pmean)}" / TP_FILE)
        def cmab_tp_path(run, nsta, pmean):
            return CMAB_DIR / CMAB_VARIANT / f"{run}_run-{nsta}_sta{ptag(pmean)}" / TP_FILE

        def read_tp(path: Path):
            if not path.exists():
                return None
            try:
                df = pd.read_csv(path, delimiter="\t")
            except Exception:
                return None
            if "Throughput_Mbps" not in df.columns or df["Throughput_Mbps"].empty:
                return None
            return df

        # type-1 TP = aggregate_TP * (type-1 byte fraction)
        def type1_throughput(ps_path, tp_pth):
            ps = read_csv(ps_path); tp = read_tp(tp_pth)
            if ps is None or tp is None: return None
            if "RX_bytes" not in ps.columns or "Class" not in ps.columns: return None
            total = ps["RX_bytes"].sum()
            if total <= 0: return None
            t1 = ps[ps["Class"] == 1]["RX_bytes"].sum()
            return float(tp["Throughput_Mbps"].sum()) * (t1 / total)

        # ---- per-STA loader for a given class (Class==1 for type-1 delay) ----
        def _load_per_sta_class(path, extra_cols, cls):
            df = read_csv(path)
            if df is None or PER_STA_COL not in df.columns or "Class" not in df.columns:
                return None
            df = df[df["Class"] == cls]
            if "RX_bytes" in df.columns:
                df = df[df["RX_bytes"] > 0]          # drop silent STAs
            if df.empty:
                return None
            out = df[[PER_STA_COL]].copy()
            for k, v in extra_cols.items():
                out[k] = v
            return out

        # ---------------- UORA OCW selection (per (nSta, pMean, RA_RU), type-2 p99) --
        def process_uora_per_sta_t2():
            rows = []
            for run in RUNS:
                for nsta in NSTA_VALUES:
                    for pmean in PMEAN_VALUES:
                        for raru in nRaRus:
                            for ocw in OCwMin:
                                d = _load_per_sta_class(
                                    uora_per_sta_path(run, nsta, pmean, raru, ocw),
                                    {"nSta": nsta, "pMean": pmean, "Run": run, "RA_RU": raru, "OCW": ocw}, 2)
                                if d is not None:
                                    rows.append(d)
            return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()

        def select_best_ocw_per_sta(per_sta_df, delay_col=PER_STA_COL):
            if per_sta_df.empty:
                return pd.DataFrame()
            grouped = (per_sta_df.groupby(["nSta", "pMean", "RA_RU", "OCW"])[delay_col]
                       .quantile(0.99).reset_index())
            idx = grouped.groupby(["nSta", "pMean", "RA_RU"])[delay_col].idxmin()
            return grouped.loc[idx][["nSta", "pMean", "RA_RU", "OCW"]].reset_index(drop=True)

        print("[INFO] UORA per-STA (type-2, for OCW selection)")
        per_sta_uora_t2 = process_uora_per_sta_t2()
        best_keys = select_best_ocw_per_sta(per_sta_uora_t2[per_sta_uora_t2["RA_RU"] > 0]) \
                    if not per_sta_uora_t2.empty else pd.DataFrame()
        one_ocw = (sorted(per_sta_uora_t2[per_sta_uora_t2["RA_RU"] == 0]["OCW"].unique())[0]
                   if (not per_sta_uora_t2.empty and not per_sta_uora_t2[per_sta_uora_t2.RA_RU == 0].empty)
                   else None)
        sel = {(r.nSta, r.pMean, r.RA_RU): int(r.OCW) for r in best_keys.itertuples()} if not best_keys.empty else {}

        def _uora_label(raru):
            if raru == 0: return "SA OFDMA"
            if raru == 1: return "1 RA RU"
            return f"{int(raru)} RA RUs"

        # ============================================================================
        #  TYPE-1 THROUGHPUT  (per-run; plotted as grouped bars)
        # ============================================================================
        def process_method_type1(method):
            return [{"Label": method, "nSta": n, "pMean": p, "Run": r, "type1_tp": v}
                    for r in RUNS for n in NSTA_VALUES for p in PMEAN_VALUES
                    if (v := type1_throughput(per_sta_path(method, r, n, p), tp_path(method, r, n, p))) is not None]

        def process_cmab_type1():
            return [{"Label": CMAB_LABEL, "nSta": n, "pMean": p, "Run": r, "type1_tp": v}
                    for r in RUNS for n in NSTA_VALUES for p in PMEAN_VALUES
                    if (v := type1_throughput(cmab_per_sta_path(r, n, p), cmab_tp_path(r, n, p))) is not None]

        def process_uora_type1():
            rows = []
            for r in RUNS:
                for n in NSTA_VALUES:
                    for p in PMEAN_VALUES:
                        for raru in nRaRus:
                            ocw = sel.get((n, p, raru)) if raru > 0 else one_ocw
                            if ocw is None: continue
                            v = type1_throughput(uora_per_sta_path(r, n, p, raru, ocw),
                                                 uora_tp_path(r, n, p, raru, ocw))
                            if v is not None:
                                rows.append({"Label": _uora_label(raru), "nSta": n, "pMean": p, "Run": r, "type1_tp": v})
            return rows

        tp_rows = []
        for method in BASE_DIRS:
            tp_rows.extend(process_method_type1(method))
        tp_rows.extend(process_cmab_type1())
        tp_rows.extend(process_uora_type1())
        tp_df = pd.DataFrame(tp_rows)
        tp_df.to_csv(OUTPUT_CSV, index=False)
        print(f"[OK] type-1 throughput CSV: {OUTPUT_CSV} (rows={len(tp_df)})")

        # ============================================================================
        #  TYPE-1 PER-STA DELAY  (boxplot)
        # ============================================================================
        def process_method_t1_delay(method):
            rows = []
            for r in RUNS:
                for n in NSTA_VALUES:
                    for p in PMEAN_VALUES:
                        d = _load_per_sta_class(per_sta_path(method, r, n, p),
                                                {"nSta": n, "pMean": p, "Run": r, "Label": method}, 1)
                        if d is not None: rows.append(d)
            return rows

        def process_cmab_t1_delay():
            rows = []
            for r in RUNS:
                for n in NSTA_VALUES:
                    for p in PMEAN_VALUES:
                        d = _load_per_sta_class(cmab_per_sta_path(r, n, p),
                                                {"nSta": n, "pMean": p, "Run": r, "Label": CMAB_LABEL}, 1)
                        if d is not None: rows.append(d)
            return rows

        def process_uora_t1_delay():
            rows = []
            for r in RUNS:
                for n in NSTA_VALUES:
                    for p in PMEAN_VALUES:
                        for raru in nRaRus:
                            ocw = sel.get((n, p, raru)) if raru > 0 else one_ocw
                            if ocw is None: continue
                            d = _load_per_sta_class(uora_per_sta_path(r, n, p, raru, ocw),
                                                    {"nSta": n, "pMean": p, "Run": r, "Label": _uora_label(raru)}, 1)
                            if d is not None: rows.append(d)
            return rows

        dly_rows = []
        for method in BASE_DIRS:
            dly_rows.extend(process_method_t1_delay(method))
        dly_rows.extend(process_cmab_t1_delay())
        dly_rows.extend(process_uora_t1_delay())
        dly_df = pd.concat(dly_rows, ignore_index=True) if dly_rows else pd.DataFrame()
        dly_df.to_csv(OUTPUT_CSV_DLY, index=False)
        print(f"[OK] type-1 per-STA delay CSV: {OUTPUT_CSV_DLY} (rows={len(dly_df)})")

        # ---------------- Plot styling ----------------
        HUE_ORDER = ["EDCA", "A2P", "A2PV2", CMAB_LABEL, "SA OFDMA",
                     "1 RA RU", "5 RA RUs", "9 RA RUs", "13 RA RUs", "18 RA RUs"]
        cmap = plt.cm.tab10(np.linspace(0, 1, len(HUE_ORDER)))
        COLORS = {lab: cmap[i] for i, lab in enumerate(HUE_ORDER)}
        plt.rcParams.update({"font.size": 14, "axes.labelsize": 14, "xtick.labelsize": 12,
                             "ytick.labelsize": 12, "legend.fontsize": 12})

        # compressed y-axis (linear up to BOUND, then compressed) for the delay boxplot
        COMPRESS_FACTOR = 0.075
        BOUND = 20
        def transform(y):
            return y if y <= BOUND else BOUND + (y - BOUND) * COMPRESS_FACTOR
        def ticks():
            base = [0, 5, 10, 15, 20, 100, 200, 300, 400, 500]
            return [transform(y) for y in base], base

        # ---------------- Plot A: type-1 per-STA delay boxplot (per pMean) ----------
        for pmean in PMEAN_VALUES:
            bp = dly_df[dly_df["pMean"] == pmean].copy() if not dly_df.empty else pd.DataFrame()
            if bp.empty:
                continue
            bp["y"] = bp[PER_STA_COL].apply(transform)
            plt.figure(figsize=(9.4, 6.0))
            sns.boxplot(data=bp, x="nSta", y="y", hue="Label",
                        hue_order=HUE_ORDER, order=NSTA_VALUES,
                        showfliers=True, whis=3.0, width=.9)
            ax = plt.gca()
            tp_pos, tp_lab = ticks()
            ax.set_yticks(tp_pos); ax.set_yticklabels([str(v) for v in tp_lab])
            ax.set_ylim(bottom=0, top=transform(500) + 2)
            ax.axhline(BOUND, color="grey", linewidth=0.8, linestyle=":")
            plt.xlabel("Number of Stochastic STAs")
            plt.ylabel("Type-1 UL Average Delay (ms)")
            plt.title(f"pMean = {pmean}")
            ax.grid(True, axis="x", linestyle="--", linewidth=0.5)
            ax.grid(True, axis="y", linestyle=":", linewidth=0.8, alpha=0.7)
            plt.legend(prop={'size': 11}, title=None, ncol=2)
            plt.tight_layout()
            plt.savefig(f"fig/iiot/pmean/type1_delay_pMean-{pmean}.png", dpi=300)
            plt.show(); plt.close()
            print(f"[OK] type-1 delay boxplot for pMean={pmean} done.")

        # ---------------- Plot B: type-1 throughput BAR chart (grouped by nSta) ------
        for pmean in PMEAN_VALUES:
            sub = tp_df[tp_df["pMean"] == pmean] if not tp_df.empty else pd.DataFrame()
            if sub.empty:
                continue
            order_present = [l for l in HUE_ORDER if l in sub["Label"].unique()]
            plt.figure(figsize=(11.0, 5.6))
            ax = sns.barplot(
                data=sub, x="nSta", y="type1_tp",
                hue="Label", hue_order=order_present, order=NSTA_VALUES,
                palette=COLORS, errorbar="sd", capsize=0.25, err_kws={"linewidth": 1.0},
            )
            plt.xlabel("Number of Stochastic STAs")
            plt.ylabel("Type-1 Throughput (Mbps)")
            plt.title(f"pMean = {pmean}")
            ax.grid(True, axis="y", linestyle="--", linewidth=0.5, alpha=0.7)
            ax.set_axisbelow(True)
            plt.legend(title=None, prop={"size": 10}, ncol=5,
                       loc="upper center", bbox_to_anchor=(0.5, 1.16), frameon=False)
            plt.tight_layout()
            plt.savefig(f"fig/iiot/pmean/type1_throughput_bar_pMean-{pmean}.png", dpi=300)
            plt.show(); plt.close()
            print(f"[OK] type-1 throughput BAR for pMean={pmean} done.")
        _done("iiot_type1_box_bars")
    except Exception as _err:
        _done("iiot_type1_box_bars", _err)

# ---- iiot_type2_box_bars: Type-2 stations: box plots and bars ----
if _run("iiot_type2_box_bars"):
    try:
        from pathlib import Path
        import pandas as pd
        import numpy as np
        import matplotlib.pyplot as plt
        import seaborn as sns


        # ---------------- Configuration ----------------
        RUNS = range(1, 11)
        NSTA_VALUES  = [1, 30, 60, 90]
        PMEAN_VALUES = [0.00625, 0.0125, 0.025, 0.05, 0.15, 0.2]   # smaller = heavier load

        nRaRus = [0, 1, 5, 9, 13, 18]
        OCwMin = [1, 3, 7, 15, 31, 63]

        BASE_DIRS = {
            "EDCA":  Path("iiot_data/iiot_data_pmean/edca"),
            "A2P":   Path("iiot_data/iiot_data_pmean/a2p"),
            "A2PV2": Path("iiot_data/iiot_data_pmean/a2pv2"),
        }
        CMAB_DIR     = Path("iiot_data/iiot_data_pmean/cmab")
        CMAB_VARIANT = "EXP3M_Binary_g0.3"
        CMAB_LABEL   = "EXP3M"

        OUTPUT_CSV = "iiot_pmean_type2_per_sta.csv"
        PER_STA_COL  = "Avg_delay_ms"
        PER_STA_FILE = "per_sta_stats.out"
        TP_FILE      = "throughput.out"
        ERROR_KIND   = "std"   # "std" or "sem"


        # ---------------- Helpers ----------------
        def ptag(pmean):
            return "" if abs(pmean - 0.1) < 1e-9 else f"_pMean-{pmean}"

        def read_csv(path: Path):
            if not path.exists():
                return None
            df = pd.read_csv(path, delimiter="\t")
            if df.dropna(how="all").empty:
                return None
            return df

        def per_sta_path(method, run, nsta, pmean):
            return BASE_DIRS[method] / f"{run}_run-{nsta}_sta{ptag(pmean)}" / PER_STA_FILE
        def uora_per_sta_path(run, nsta, pmean, raru, ocw):
            return (Path("iiot_data/iiot_data_pmean/uora") / f"ocwMin_{ocw}"
                    / f"{run}_run-{nsta}_sta-{raru}_rarus{ptag(pmean)}" / PER_STA_FILE)
        def cmab_per_sta_path(run, nsta, pmean):
            return CMAB_DIR / CMAB_VARIANT / f"{run}_run-{nsta}_sta{ptag(pmean)}" / PER_STA_FILE
        def tp_path(method, run, nsta, pmean):
            return BASE_DIRS[method] / f"{run}_run-{nsta}_sta{ptag(pmean)}" / TP_FILE
        def uora_tp_path(run, nsta, pmean, raru, ocw):
            return (Path("iiot_data/iiot_data_pmean/uora") / f"ocwMin_{ocw}"
                    / f"{run}_run-{nsta}_sta-{raru}_rarus{ptag(pmean)}" / TP_FILE)
        def cmab_tp_path(run, nsta, pmean):
            return CMAB_DIR / CMAB_VARIANT / f"{run}_run-{nsta}_sta{ptag(pmean)}" / TP_FILE


        # ---------------- Per-STA type-2 delay loaders ----------------
        def _load_per_sta(path, extra_cols):
            df = read_csv(path)
            if df is None or PER_STA_COL not in df.columns:
                return None
            if "Class" in df.columns:
                df = df[df["Class"] == 2]
            if "RX_bytes" in df.columns:
                df = df[df["RX_bytes"] > 0]
            if df.empty:
                return None
            out = df[[PER_STA_COL]].copy()
            for k, v in extra_cols.items():
                out[k] = v
            return out

        def process_method_per_sta(method):
            rows = []
            for run in RUNS:
                for nsta in NSTA_VALUES:
                    for pmean in PMEAN_VALUES:
                        d = _load_per_sta(per_sta_path(method, run, nsta, pmean),
                                          {"nSta": nsta, "pMean": pmean, "Run": run, "Method": method})
                        if d is not None:
                            rows.append(d)
            return rows

        def process_uora_per_sta():
            rows = []
            for run in RUNS:
                for nsta in NSTA_VALUES:
                    for pmean in PMEAN_VALUES:
                        for raru in nRaRus:
                            for ocw in OCwMin:
                                d = _load_per_sta(
                                    uora_per_sta_path(run, nsta, pmean, raru, ocw),
                                    {"nSta": nsta, "pMean": pmean, "Run": run,
                                     "RA_RU": raru, "OCW": ocw, "Method": "UORA"})
                                if d is not None:
                                    rows.append(d)
            return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()

        def process_cmab_per_sta():
            rows = []
            for run in RUNS:
                for nsta in NSTA_VALUES:
                    for pmean in PMEAN_VALUES:
                        d = _load_per_sta(cmab_per_sta_path(run, nsta, pmean),
                                          {"nSta": nsta, "pMean": pmean, "Run": run, "Method": "CMAB"})
                        if d is not None:
                            rows.append(d)
            return rows


        # ---------------- Throughput reader ----------------
        def read_tp(path: Path):
            if not path.exists():
                return None
            try:
                df = pd.read_csv(path, delimiter="\t")
            except Exception:
                return None
            if "Throughput_Mbps" not in df.columns or df["Throughput_Mbps"].empty:
                return None
            return df


        # ---------------- Type-2 throughput per cell (byte-share, exact) ------------
        def type2_throughput(ps_pth, tp_pth):
            ps = read_csv(ps_pth)
            tp = read_tp(tp_pth)
            if ps is None or tp is None:
                return None
            if "RX_bytes" not in ps.columns or "Class" not in ps.columns:
                return None
            total = ps["RX_bytes"].sum()
            if total <= 0:
                return None
            t2 = ps[ps["Class"] == 2]["RX_bytes"].sum()
            return float(tp["Throughput_Mbps"].sum()) * (t2 / total)


        # ---------------- Load per-STA delay ----------------
        per_sta_rows = []
        for method in BASE_DIRS:
            print(f"[INFO] Processing {method} per-STA")
            per_sta_rows.extend(process_method_per_sta(method))
        print(f"[INFO] Processing CMAB per-STA ({CMAB_VARIANT})")
        per_sta_rows.extend(process_cmab_per_sta())
        per_sta_other = pd.concat(per_sta_rows, ignore_index=True) if per_sta_rows else pd.DataFrame()

        print("[INFO] Processing UORA per-STA")
        per_sta_uora = process_uora_per_sta()
        print(f"[OK] per-STA UORA rows: {len(per_sta_uora)}, other rows: {len(per_sta_other)}")


        # ---------------- UORA OCW selection (per (nSta, pMean, RA_RU), p99) ---------
        def select_best_ocw_per_sta(per_sta_df, delay_col=PER_STA_COL):
            if per_sta_df.empty:
                return pd.DataFrame()
            grouped = (per_sta_df.groupby(["nSta", "pMean", "RA_RU", "OCW"])[delay_col]
                       .quantile(0.99).reset_index())
            idx = grouped.groupby(["nSta", "pMean", "RA_RU"])[delay_col].idxmin()
            return grouped.loc[idx][["nSta", "pMean", "RA_RU", "OCW"]].reset_index(drop=True)

        per_sta_uora_ra = per_sta_uora[per_sta_uora["RA_RU"] > 0]
        per_sta_uora_sa = per_sta_uora[per_sta_uora["RA_RU"] == 0]
        best_keys = select_best_ocw_per_sta(per_sta_uora_ra)
        one_ocw = sorted(per_sta_uora_sa["OCW"].unique())[0] if not per_sta_uora_sa.empty else None


        # ---------------- Apply selection to per-STA delay ----------------
        if not best_keys.empty:
            per_sta_uora_ra_best = per_sta_uora_ra.merge(best_keys, on=["nSta", "pMean", "RA_RU", "OCW"], how="inner")
        else:
            per_sta_uora_ra_best = pd.DataFrame()
        if one_ocw is not None:
            per_sta_uora_sa_best = per_sta_uora_sa[per_sta_uora_sa["OCW"] == one_ocw].copy()
        else:
            per_sta_uora_sa_best = pd.DataFrame()
        per_sta_uora_best = pd.concat([per_sta_uora_ra_best, per_sta_uora_sa_best], ignore_index=True)


        # ---------------- Labels + combine ----------------
        def _uora_label(raru):
            if raru == 0:
                return "SA OFDMA"
            if raru == 1:
                return "1 RA RU"
            return f"{int(raru)} RA RUs"

        if not per_sta_uora_best.empty:
            per_sta_uora_best["Method"] = "UORA"
            per_sta_uora_best["Label"]  = per_sta_uora_best["RA_RU"].apply(_uora_label)

        per_sta_std = per_sta_other.copy()
        if not per_sta_std.empty:
            per_sta_std["Label"] = per_sta_std["Method"].replace({"CMAB": CMAB_LABEL})

        per_sta_combined = pd.concat([per_sta_std, per_sta_uora_best], ignore_index=True)
        per_sta_combined.to_csv(OUTPUT_CSV, index=False)
        print(f"[OK] per-STA combined CSV: {OUTPUT_CSV}")


        # ---------------- Load type-2 throughput (UORA = delay-selected cells) ------
        tp_rows = []
        for method in BASE_DIRS:
            for run in RUNS:
                for nsta in NSTA_VALUES:
                    for pmean in PMEAN_VALUES:
                        v = type2_throughput(per_sta_path(method, run, nsta, pmean),
                                             tp_path(method, run, nsta, pmean))
                        if v is None:
                            continue
                        tp_rows.append({"Method": method, "nSta": nsta, "pMean": pmean, "Run": run, "TP": v})
        for run in RUNS:
            for nsta in NSTA_VALUES:
                for pmean in PMEAN_VALUES:
                    v = type2_throughput(cmab_per_sta_path(run, nsta, pmean),
                                         cmab_tp_path(run, nsta, pmean))
                    if v is None:
                        continue
                    tp_rows.append({"Method": "CMAB", "nSta": nsta, "pMean": pmean, "Run": run, "TP": v})

        uora_tp_rows = []
        for run in RUNS:
            for nsta in NSTA_VALUES:
                for pmean in PMEAN_VALUES:
                    for raru in nRaRus:
                        for ocw in OCwMin:
                            v = type2_throughput(uora_per_sta_path(run, nsta, pmean, raru, ocw),
                                                 uora_tp_path(run, nsta, pmean, raru, ocw))
                            if v is None:
                                continue
                            uora_tp_rows.append({"Method": "UORA", "nSta": nsta, "pMean": pmean, "Run": run,
                                                 "RA_RU": raru, "OCW": ocw, "TP": v})

        tp_std = pd.DataFrame(tp_rows)
        tp_uora = pd.DataFrame(uora_tp_rows)

        # filter UORA to the delay-selected OCW (raru>0) + one_ocw (SA OFDMA)
        if not tp_uora.empty:
            uora_ra_tp = tp_uora[tp_uora["RA_RU"] > 0]
            uora_sa_tp = tp_uora[tp_uora["RA_RU"] == 0]
            uora_ra_tp_best = (uora_ra_tp.merge(best_keys, on=["nSta", "pMean", "RA_RU", "OCW"], how="inner")
                               if not best_keys.empty else pd.DataFrame())
            uora_sa_tp_best = (uora_sa_tp[uora_sa_tp["OCW"] == one_ocw].copy()
                               if one_ocw is not None else pd.DataFrame())
            uora_tp_best = pd.concat([uora_ra_tp_best, uora_sa_tp_best], ignore_index=True)
        else:
            uora_tp_best = pd.DataFrame()

        # ---- combined per-run TP frame for the bar chart ----
        tp_std_lbl = tp_std.copy()
        if not tp_std_lbl.empty:
            tp_std_lbl["Label"] = tp_std_lbl["Method"].replace({"CMAB": CMAB_LABEL})
        if not uora_tp_best.empty:
            uora_tp_best = uora_tp_best.copy()
            uora_tp_best["Label"] = uora_tp_best["RA_RU"].apply(_uora_label)
            uora_lbl = uora_tp_best[["Label", "nSta", "pMean", "TP"]]
        else:
            uora_lbl = pd.DataFrame()
        tp_combined = pd.concat(
            [tp_std_lbl[["Label", "nSta", "pMean", "TP"]] if not tp_std_lbl.empty else pd.DataFrame(), uora_lbl],
            ignore_index=True)


        # ---------------- Plot styling ----------------
        HUE_ORDER = [
            "EDCA", "A2P", "A2PV2", CMAB_LABEL,
            "SA OFDMA",
            "1 RA RU", "5 RA RUs", "9 RA RUs", "13 RA RUs", "18 RA RUs",
        ]
        plt.rcParams.update({
            "font.size": 14, "axes.labelsize": 14,
            "xtick.labelsize": 12, "ytick.labelsize": 12, "legend.fontsize": 12,
        })

        # y-axis compression for the delay boxplot (linear up to BOUND, compressed above)
        COMPRESS_FACTOR = 0.075
        BOUND = 20
        def transform(y):
            return y if y <= BOUND else BOUND + (y - BOUND) * COMPRESS_FACTOR
        def ticks():
            base = [0, 5, 10, 15, 20, 100, 200, 300, 400, 500]
            return [transform(y) for y in base], base


        # ================= Loop: one delay + one throughput plot per pMean =========
        for pmean in PMEAN_VALUES:

            # ---- Plot A: type-2 per-STA mean delay boxplot (x = nSta) ----
            bp = per_sta_combined[per_sta_combined["pMean"] == pmean].copy()
            if not bp.empty:
                bp["y"] = bp[PER_STA_COL].apply(transform)
                plt.figure(figsize=(9.4, 6.0))
                sns.boxplot(data=bp, x="nSta", y="y",
                            hue="Label", hue_order=HUE_ORDER, order=NSTA_VALUES,
                            showfliers=True, whis=3.0, width=.9)
                ax = plt.gca()
                tp_pos, tp_lab = ticks()
                ax.set_yticks(tp_pos); ax.set_yticklabels([str(v) for v in tp_lab])
                ax.set_ylim(bottom=0, top=transform(500) + 2)
                ax.axhline(BOUND, color="grey", linewidth=0.8, linestyle=":")
                plt.xlabel("Number of Stochastic STAs")
                plt.ylabel("Type-2 UL Average Delay (ms)")
                plt.title(f"pMean = {pmean}")
                ax.grid(True, axis="x", linestyle="--", linewidth=0.5)
                ax.grid(True, axis="y", linestyle=":",  linewidth=0.8, alpha=0.7)
                plt.legend(prop={'size': 11}, title=None, ncol=2)
                plt.tight_layout()
                plt.savefig(f"fig/iiot/pmean/type2_delay_pMean-{pmean}.png", dpi=300)
                plt.show(); plt.close()
                print(f"[OK] type-2 delay plot for pMean={pmean} done.")

            # ---- Plot B: type-2 throughput BAR chart (grouped by nSta, hue=scheme) ----
            sub = tp_combined[tp_combined["pMean"] == pmean] if not tp_combined.empty else pd.DataFrame()
            if not sub.empty:
                order_present = [l for l in HUE_ORDER if l in sub["Label"].unique()]
                plt.figure(figsize=(11.0, 5.6))
                ax = sns.barplot(
                    data=sub, x="nSta", y="TP",
                    hue="Label", hue_order=order_present, order=NSTA_VALUES,
                    errorbar="sd", capsize=0.25, err_kws={"linewidth": 1.0},
                )
                plt.xlabel("Number of Stochastic STAs")
                plt.ylabel("Type-2 Throughput (Mbps)")
                plt.title(f"pMean = {pmean}")
                ax.grid(True, axis="y", linestyle="--", linewidth=0.5, alpha=0.7)
                ax.set_axisbelow(True)
                plt.legend(title=None, prop={"size": 10}, ncol=5,
                           loc="upper center", bbox_to_anchor=(0.5, 1.16), frameon=False)
                plt.tight_layout()
                plt.savefig(f"fig/iiot/pmean/type2_throughput_bar_pMean-{pmean}.png", dpi=300)
                plt.show(); plt.close()
                print(f"[OK] type-2 throughput BAR for pMean={pmean} done.")
        _done("iiot_type2_box_bars")
    except Exception as _err:
        _done("iiot_type2_box_bars", _err)

# ---- iiot_type1_lines: Type-1 stations: line plots ----
if _run("iiot_type1_lines"):
    try:
        from pathlib import Path
        import pandas as pd
        import numpy as np
        import matplotlib.pyplot as plt
        import seaborn as sns
        from matplotlib.ticker import ScalarFormatter, NullFormatter


        # ---------------- Configuration ----------------
        RUNS = range(1, 11)
        NSTA_VALUES  = [1, 30, 60, 90]                          # = number of type-2 STAs (type-1 is fixed at 18)
        PMEAN_VALUES = [0.0125, 0.025, 0.05, 0.1, 0.15, 0.2]    # smaller = heavier type-2 load

        nRaRus = [0, 1, 5, 9, 13, 18]
        OCwMin = [1, 3, 7, 15, 31, 63]

        BASE_DIRS = {
            "EDCA":  Path("iiot_data/iiot_data_pmean/edca"),
            "A2P":   Path("iiot_data/iiot_data_pmean/a2p"),
            "A2PV2": Path("iiot_data/iiot_data_pmean/a2pv2"),
        }
        CMAB_DIR     = Path("iiot_data/iiot_data_pmean/cmab")
        CMAB_VARIANT = "EXP3M_Binary_g0.3"
        CMAB_LABEL   = "EXP3M"

        # ---- which device class to plot -------------------------------------------
        CLASS_ID   = 1     # 1 = type-1 CBR background, 2 = type-2 stochastic time-critical
        # UORA has ONE OCW setting per run; it is chosen to minimise the TIME-CRITICAL
        # type-2 p99 delay (the deployed operating point), and every class -- including
        # type-1 -- is then reported at that same OCW. Keep = 2 for consistent figures.
        SELECT_CLASS = 2

        CLASS_NAME = {1: "Type-1", 2: "Type-2"}[CLASS_ID]

        PER_STA_COL  = "Avg_delay_ms"
        PER_STA_FILE = "per_sta_stats.out"
        TP_FILE      = "throughput.out"
        OUTPUT_CSV   = f"iiot_pmean_{CLASS_NAME.lower().replace('-', '')}_per_sta.csv"

        # Error bars = uncertainty of the per-configuration MEAN across seeds.
        # "sem" (sd/sqrt(#runs)) keeps the bars positive & readable on the log delay
        # axis, where at heavy load per-STA sd can exceed the mean.
        ERROR_KIND    = "sem"   # "sem" or "std"
        PLOT_DELIVERY = False   # False -> packet LOSS %, True -> delivery ratio %


        # ---------------- Path helpers ----------------
        def ptag(pmean):
            return "" if abs(pmean - 0.1) < 1e-9 else f"_pMean-{pmean}"

        def read_csv(path: Path):
            if not path.exists():
                return None
            df = pd.read_csv(path, delimiter="\t")
            if df.dropna(how="all").empty:
                return None
            return df

        def per_sta_path(method, run, nsta, pmean):
            return BASE_DIRS[method] / f"{run}_run-{nsta}_sta{ptag(pmean)}" / PER_STA_FILE
        def uora_per_sta_path(run, nsta, pmean, raru, ocw):
            return (Path("iiot_data/iiot_data_pmean/uora") / f"ocwMin_{ocw}"
                    / f"{run}_run-{nsta}_sta-{raru}_rarus{ptag(pmean)}" / PER_STA_FILE)
        def cmab_per_sta_path(run, nsta, pmean):
            return CMAB_DIR / CMAB_VARIANT / f"{run}_run-{nsta}_sta{ptag(pmean)}" / PER_STA_FILE
        def tp_path(method, run, nsta, pmean):
            return BASE_DIRS[method] / f"{run}_run-{nsta}_sta{ptag(pmean)}" / TP_FILE
        def uora_tp_path(run, nsta, pmean, raru, ocw):
            return (Path("iiot_data/iiot_data_pmean/uora") / f"ocwMin_{ocw}"
                    / f"{run}_run-{nsta}_sta-{raru}_rarus{ptag(pmean)}" / TP_FILE)
        def cmab_tp_path(run, nsta, pmean):
            return CMAB_DIR / CMAB_VARIANT / f"{run}_run-{nsta}_sta{ptag(pmean)}" / TP_FILE


        # ---------------- Per-STA delay loaders ----------------
        def _load_delay(path, extra_cols, class_id):
            """Per-STA mean delay for ONE class (used for standard/CMAB methods)."""
            df = read_csv(path)
            if df is None or PER_STA_COL not in df.columns or "Class" not in df.columns:
                return None
            df = df[df["Class"] == class_id]
            if "RX_bytes" in df.columns:
                df = df[df["RX_bytes"] > 0]
            if df.empty:
                return None
            out = df[[PER_STA_COL]].copy()
            for k, v in extra_cols.items():
                out[k] = v
            return out

        def _load_delay_two(path, extra_cols):
            """Per-STA delay for BOTH the plotted class and the OCW-selection class, in
    a single file read (used for the large UORA sweep)."""
            df = read_csv(path)
            if df is None or PER_STA_COL not in df.columns or "Class" not in df.columns:
                return None
            df = df[df["Class"].isin({CLASS_ID, SELECT_CLASS})]
            if "RX_bytes" in df.columns:
                df = df[df["RX_bytes"] > 0]
            if df.empty:
                return None
            out = df[[PER_STA_COL, "Class"]].copy()
            for k, v in extra_cols.items():
                out[k] = v
            return out


        # ---------------- Throughput / loss readers ----------------
        def read_tp(path: Path):
            if not path.exists():
                return None
            try:
                df = pd.read_csv(path, delimiter="\t")
            except Exception:
                return None
            if "Throughput_Mbps" not in df.columns or df["Throughput_Mbps"].empty:
                return None
            return df

        def cls_throughput(ps_pth, tp_pth, class_id):
            """Per-cell throughput of one class via exact byte-share of the aggregate."""
            ps = read_csv(ps_pth)
            tp = read_tp(tp_pth)
            if ps is None or tp is None:
                return None
            if "RX_bytes" not in ps.columns or "Class" not in ps.columns:
                return None
            total = ps["RX_bytes"].sum()
            if total <= 0:
                return None
            cls = ps[ps["Class"] == class_id]["RX_bytes"].sum()
            return float(tp["Throughput_Mbps"].sum()) * (cls / total)

        def cls_loss(ps_pth, class_id):
            """Deadline-free per-cell packet loss (or delivery ratio) of one class,
    pooled over that class's STAs: 1 - sumRX/sumTX."""
            ps = read_csv(ps_pth)
            if ps is None or not {"Class", "TX_pkts", "RX_pkts"}.issubset(ps.columns):
                return None
            c = ps[ps["Class"] == class_id]
            tx = c["TX_pkts"].sum()
            if tx <= 0:
                return None
            ratio = c["RX_pkts"].sum() / tx
            return 100.0 * (ratio if PLOT_DELIVERY else (1.0 - ratio))


        # ---------------- Load per-STA delay (standard + CMAB) ----------------
        per_sta_rows = []
        for method in BASE_DIRS:
            print(f"[INFO] Processing {method} per-STA ({CLASS_NAME})")
            for run in RUNS:
                for nsta in NSTA_VALUES:
                    for pmean in PMEAN_VALUES:
                        d = _load_delay(per_sta_path(method, run, nsta, pmean),
                                        {"nSta": nsta, "pMean": pmean, "Run": run, "Method": method}, CLASS_ID)
                        if d is not None:
                            per_sta_rows.append(d)
        print(f"[INFO] Processing CMAB per-STA ({CMAB_VARIANT})")
        for run in RUNS:
            for nsta in NSTA_VALUES:
                for pmean in PMEAN_VALUES:
                    d = _load_delay(cmab_per_sta_path(run, nsta, pmean),
                                    {"nSta": nsta, "pMean": pmean, "Run": run, "Method": "CMAB"}, CLASS_ID)
                    if d is not None:
                        per_sta_rows.append(d)
        per_sta_other = pd.concat(per_sta_rows, ignore_index=True) if per_sta_rows else pd.DataFrame()


        # ---------------- Load UORA per-STA delay (plot class + selection class) ----
        print("[INFO] Processing UORA per-STA")
        urows = []
        for run in RUNS:
            for nsta in NSTA_VALUES:
                for pmean in PMEAN_VALUES:
                    for raru in nRaRus:
                        for ocw in OCwMin:
                            d = _load_delay_two(uora_per_sta_path(run, nsta, pmean, raru, ocw),
                                                {"nSta": nsta, "pMean": pmean, "Run": run,
                                                 "RA_RU": raru, "OCW": ocw, "Method": "UORA"})
                            if d is not None:
                                urows.append(d)
        per_sta_uora_all = pd.concat(urows, ignore_index=True) if urows else pd.DataFrame()
        per_sta_uora_sel = per_sta_uora_all[per_sta_uora_all["Class"] == SELECT_CLASS]  # picks OCW
        per_sta_uora     = per_sta_uora_all[per_sta_uora_all["Class"] == CLASS_ID]      # plotted
        print(f"[OK] UORA rows (plot class): {len(per_sta_uora)}, other rows: {len(per_sta_other)}")


        # ---------------- UORA OCW selection (on SELECT_CLASS p99 delay) ------------
        def select_best_ocw(df, delay_col=PER_STA_COL):
            if df.empty:
                return pd.DataFrame()
            grouped = (df.groupby(["nSta", "pMean", "RA_RU", "OCW"])[delay_col]
                         .quantile(0.99).reset_index())
            idx = grouped.groupby(["nSta", "pMean", "RA_RU"])[delay_col].idxmin()
            return grouped.loc[idx][["nSta", "pMean", "RA_RU", "OCW"]].reset_index(drop=True)

        best_keys = select_best_ocw(per_sta_uora_sel[per_sta_uora_sel["RA_RU"] > 0])
        sa_sel = per_sta_uora_sel[per_sta_uora_sel["RA_RU"] == 0]
        one_ocw = sorted(sa_sel["OCW"].unique())[0] if not sa_sel.empty else None


        # ---------------- Apply selection to the plotted-class UORA delay -----------
        ra = per_sta_uora[per_sta_uora["RA_RU"] > 0]
        sa = per_sta_uora[per_sta_uora["RA_RU"] == 0]
        ra_best = ra.merge(best_keys, on=["nSta", "pMean", "RA_RU", "OCW"], how="inner") if not best_keys.empty else pd.DataFrame()
        sa_best = sa[sa["OCW"] == one_ocw].copy() if one_ocw is not None else pd.DataFrame()
        per_sta_uora_best = pd.concat([ra_best, sa_best], ignore_index=True)


        # ---------------- Labels + combine ----------------
        def _uora_label(raru):
            if raru == 0:
                return "SA OFDMA"
            if raru == 1:
                return "1 RA RU"
            return f"{int(raru)} RA RUs"

        if not per_sta_uora_best.empty:
            per_sta_uora_best["Label"] = per_sta_uora_best["RA_RU"].apply(_uora_label)

        per_sta_std = per_sta_other.copy()
        if not per_sta_std.empty:
            per_sta_std["Label"] = per_sta_std["Method"].replace({"CMAB": CMAB_LABEL})

        per_sta_combined = pd.concat([per_sta_std, per_sta_uora_best], ignore_index=True)
        per_sta_combined.to_csv(OUTPUT_CSV, index=False)
        print(f"[OK] per-STA combined CSV: {OUTPUT_CSV}")


        # ---------------- Load throughput + loss for the plotted class -------------
        tp_rows, loss_rows = [], []
        for method in BASE_DIRS:
            for run in RUNS:
                for nsta in NSTA_VALUES:
                    for pmean in PMEAN_VALUES:
                        pp = per_sta_path(method, run, nsta, pmean)
                        v = cls_throughput(pp, tp_path(method, run, nsta, pmean), CLASS_ID)
                        if v is not None:
                            tp_rows.append({"Method": method, "nSta": nsta, "pMean": pmean, "Run": run, "TP": v})
                        l = cls_loss(pp, CLASS_ID)
                        if l is not None:
                            loss_rows.append({"Method": method, "nSta": nsta, "pMean": pmean, "Run": run, "Loss": l})
        for run in RUNS:
            for nsta in NSTA_VALUES:
                for pmean in PMEAN_VALUES:
                    pp = cmab_per_sta_path(run, nsta, pmean)
                    v = cls_throughput(pp, cmab_tp_path(run, nsta, pmean), CLASS_ID)
                    if v is not None:
                        tp_rows.append({"Method": "CMAB", "nSta": nsta, "pMean": pmean, "Run": run, "TP": v})
                    l = cls_loss(pp, CLASS_ID)
                    if l is not None:
                        loss_rows.append({"Method": "CMAB", "nSta": nsta, "pMean": pmean, "Run": run, "Loss": l})

        uora_tp_rows, uora_loss_rows = [], []
        for run in RUNS:
            for nsta in NSTA_VALUES:
                for pmean in PMEAN_VALUES:
                    for raru in nRaRus:
                        for ocw in OCwMin:
                            pp = uora_per_sta_path(run, nsta, pmean, raru, ocw)
                            v = cls_throughput(pp, uora_tp_path(run, nsta, pmean, raru, ocw), CLASS_ID)
                            if v is not None:
                                uora_tp_rows.append({"Method": "UORA", "nSta": nsta, "pMean": pmean, "Run": run,
                                                     "RA_RU": raru, "OCW": ocw, "TP": v})
                            l = cls_loss(pp, CLASS_ID)
                            if l is not None:
                                uora_loss_rows.append({"Method": "UORA", "nSta": nsta, "pMean": pmean, "Run": run,
                                                       "RA_RU": raru, "OCW": ocw, "Loss": l})

        tp_std, tp_uora     = pd.DataFrame(tp_rows),   pd.DataFrame(uora_tp_rows)
        loss_std, loss_uora = pd.DataFrame(loss_rows), pd.DataFrame(uora_loss_rows)


        def _uora_select(df):
            if df.empty:
                return pd.DataFrame()
            ra = df[df["RA_RU"] > 0]
            sa = df[df["RA_RU"] == 0]
            ra_b = (ra.merge(best_keys, on=["nSta", "pMean", "RA_RU", "OCW"], how="inner")
                    if not best_keys.empty else pd.DataFrame())
            sa_b = (sa[sa["OCW"] == one_ocw].copy() if one_ocw is not None else pd.DataFrame())
            return pd.concat([ra_b, sa_b], ignore_index=True)

        def _combine(std_df, uora_best, valcol):
            s = std_df.copy()
            if not s.empty:
                s["Label"] = s["Method"].replace({"CMAB": CMAB_LABEL})
                s = s[["Label", "nSta", "pMean", "Run", valcol]]
            if not uora_best.empty:
                u = uora_best.copy()
                u["Label"] = u["RA_RU"].apply(_uora_label)
                u = u[["Label", "nSta", "pMean", "Run", valcol]]
            else:
                u = pd.DataFrame()
            return pd.concat([s if not s.empty else pd.DataFrame(), u], ignore_index=True)

        tp_combined   = _combine(tp_std,   _uora_select(tp_uora),   "TP")
        loss_combined = _combine(loss_std, _uora_select(loss_uora), "Loss")


        # ---------------- Plot styling ----------------
        HUE_ORDER = [
            "EDCA", "A2P", "A2PV2", CMAB_LABEL,
            "SA OFDMA",
            "1 RA RU", "5 RA RUs", "9 RA RUs", "13 RA RUs", "18 RA RUs",
        ]
        plt.rcParams.update({
            "font.size": 14, "axes.labelsize": 14,
            "xtick.labelsize": 12, "ytick.labelsize": 12, "legend.fontsize": 12,
        })

        ERRBAR = "se" if ERROR_KIND == "sem" else "sd"

        PMEAN_CATS = [str(p) for p in sorted(PMEAN_VALUES)]
        for _df in (per_sta_combined, tp_combined, loss_combined):
            if not _df.empty:
                _df["pMean_s"] = pd.Categorical(_df["pMean"].astype(str),
                                                categories=PMEAN_CATS, ordered=True)

        XLABEL = "Type-2 (cross-traffic) inter-arrival mean (s)   —   smaller = heavier load"
        LOSS_YLABEL = (f"{CLASS_NAME} UL Delivery Ratio (%)" if PLOT_DELIVERY
                       else f"{CLASS_NAME} UL Packet Loss (%)")

        def _title(nsta):
            return f"{nsta} Type-2 STA" + ("s" if nsta != 1 else "") + " (18 Type-1)"


        def _per_run(data, ycol):
            """Collapse per-STA samples to one value per run, so error bars reflect
    seed-to-seed variability. No-op for already-per-run frames (TP, loss)."""
            keys = [k for k in ("Label", "pMean_s", "nSta", "Run") if k in data.columns]
            return data.groupby(keys, observed=True)[ycol].mean().reset_index()

        def _lineplot(data, ycol, ax):
            d = _per_run(data, ycol)
            present = [l for l in HUE_ORDER if l in d["Label"].unique()]
            sns.lineplot(
                data=d, x="pMean_s", y=ycol, hue="Label", hue_order=present,
                estimator="mean", errorbar=ERRBAR,
                marker="o", markersize=6, linewidth=1.9,
                err_style="bars", err_kws={"capsize": 3, "capthick": 1.0, "elinewidth": 1.0},
                ax=ax,
            )
            return present


        # ============ Loop: delay + throughput + loss line plots per nSta ==========
        for nsta in NSTA_VALUES:

            # ---- Plot A: per-STA mean delay vs pMean (log-y) ----
            # NOTE: delay is averaged over RECEIVED packets only, so where loss is high
            # (see Plot C) the mean is a survivorship-biased subset -- read it together
            # with the loss plot, not in isolation.
            dl = per_sta_combined[per_sta_combined["nSta"] == nsta].copy()
            if not dl.empty:
                fig, ax = plt.subplots(figsize=(8.6, 6.0))
                _lineplot(dl, PER_STA_COL, ax)
                ax.set_yscale("log")
                ax.yaxis.set_major_formatter(ScalarFormatter())   # 1, 10, 100 instead of 10^n
                ax.yaxis.set_minor_formatter(NullFormatter())
                ax.set_xlabel(XLABEL)
                ax.set_ylabel(f"{CLASS_NAME} UL Average Delay (ms)")
                ax.set_title(_title(nsta))
                ax.grid(True, which="both", axis="y", linestyle=":", linewidth=0.8, alpha=0.7)
                ax.grid(True, axis="x", linestyle="--", linewidth=0.5, alpha=0.6)
                ax.legend(prop={"size": 11}, title=None, ncol=2)
                plt.tight_layout()
                plt.savefig(f"fig/iiot/pmean/line_{CLASS_NAME.lower()}_delay_nSta-{nsta}.png", dpi=300)
                plt.show(); plt.close()
                print(f"[OK] {CLASS_NAME} delay line plot for nSta={nsta} done.")

            # ---- Plot B: throughput vs pMean (linear-y) ----
            tp = tp_combined[tp_combined["nSta"] == nsta].copy()
            if not tp.empty:
                fig, ax = plt.subplots(figsize=(8.6, 6.0))
                _lineplot(tp, "TP", ax)
                ax.set_ylim(bottom=0)
                ax.set_xlabel(XLABEL)
                ax.set_ylabel(f"{CLASS_NAME} Throughput (Mbps)")
                ax.set_title(_title(nsta))
                ax.grid(True, axis="y", linestyle="--", linewidth=0.5, alpha=0.7)
                ax.set_axisbelow(True)
                ax.legend(prop={"size": 11}, title=None, ncol=2)
                plt.tight_layout()
                plt.savefig(f"fig/iiot/pmean/line_{CLASS_NAME.lower()}_throughput_nSta-{nsta}.png", dpi=300)
                plt.show(); plt.close()
                print(f"[OK] {CLASS_NAME} throughput line plot for nSta={nsta} done.")

            # ---- Plot C: packet loss (or delivery ratio) vs pMean (linear-y) ----
            ls = loss_combined[loss_combined["nSta"] == nsta].copy()
            if not ls.empty:
                fig, ax = plt.subplots(figsize=(8.6, 6.0))
                _lineplot(ls, "Loss", ax)
                ax.set_ylim(bottom=0, top=(100 if PLOT_DELIVERY else None))
                ax.set_xlabel(XLABEL)
                ax.set_ylabel(LOSS_YLABEL)
                ax.set_title(_title(nsta))
                ax.grid(True, axis="y", linestyle="--", linewidth=0.5, alpha=0.7)
                ax.set_axisbelow(True)
                ax.legend(prop={"size": 11}, title=None, ncol=2)
                plt.tight_layout()
                plt.savefig(f"fig/iiot/pmean/line_{CLASS_NAME.lower()}_loss_nSta-{nsta}.png", dpi=300)
                plt.show(); plt.close()
                print(f"[OK] {CLASS_NAME} loss line plot for nSta={nsta} done.")
        _done("iiot_type1_lines")
    except Exception as _err:
        _done("iiot_type1_lines", _err)

# ---- iiot_type2_lines: Type-2 stations: line plots ----
if _run("iiot_type2_lines"):
    try:
        from pathlib import Path
        import pandas as pd
        import numpy as np
        import matplotlib.pyplot as plt
        import seaborn as sns
        from matplotlib.ticker import ScalarFormatter, NullFormatter


        # ---------------- Configuration ----------------
        RUNS = range(1, 11)
        NSTA_VALUES  = [1, 30, 60, 90]
        PMEAN_VALUES = [0.0125, 0.025, 0.05, 0.1, 0.15, 0.2]   # smaller = heavier load

        nRaRus = [0, 1, 5, 9, 13, 18]
        OCwMin = [1, 3, 7, 15, 31, 63]

        BASE_DIRS = {
            "EDCA":  Path("iiot_data/iiot_data_pmean/edca"),
            "A2P":   Path("iiot_data/iiot_data_pmean/a2p"),
            "A2PV2": Path("iiot_data/iiot_data_pmean/a2pv2"),
        }
        CMAB_DIR     = Path("iiot_data/iiot_data_pmean/cmab")
        CMAB_VARIANT = "EXP3M_Binary_g0.3"
        CMAB_LABEL   = "EXP3M"

        OUTPUT_CSV = "iiot_pmean_type2_per_sta.csv"
        PER_STA_COL  = "Avg_delay_ms"
        PER_STA_FILE = "per_sta_stats.out"
        TP_FILE      = "throughput.out"
        # Error bars = uncertainty of the per-configuration MEAN across seeds.
        # "sem" (sd/sqrt(#runs)) is the right choice here: at heavy load some schemes
        # (e.g. A2P) have a per-STA sd larger than the mean, so raw "std" bars are
        # unplottable on a log axis (lower cap goes <= 0). SEM stays positive & sane.
        ERROR_KIND   = "sem"   # "sem" or "std"
        PLOT_DELIVERY = False  # False -> plot packet LOSS %, True -> delivery ratio %


        # ---------------- Helpers ----------------
        def ptag(pmean):
            return "" if abs(pmean - 0.1) < 1e-9 else f"_pMean-{pmean}"

        def read_csv(path: Path):
            if not path.exists():
                return None
            df = pd.read_csv(path, delimiter="\t")
            if df.dropna(how="all").empty:
                return None
            return df

        def per_sta_path(method, run, nsta, pmean):
            return BASE_DIRS[method] / f"{run}_run-{nsta}_sta{ptag(pmean)}" / PER_STA_FILE
        def uora_per_sta_path(run, nsta, pmean, raru, ocw):
            return (Path("iiot_data/iiot_data_pmean/uora") / f"ocwMin_{ocw}"
                    / f"{run}_run-{nsta}_sta-{raru}_rarus{ptag(pmean)}" / PER_STA_FILE)
        def cmab_per_sta_path(run, nsta, pmean):
            return CMAB_DIR / CMAB_VARIANT / f"{run}_run-{nsta}_sta{ptag(pmean)}" / PER_STA_FILE
        def tp_path(method, run, nsta, pmean):
            return BASE_DIRS[method] / f"{run}_run-{nsta}_sta{ptag(pmean)}" / TP_FILE
        def uora_tp_path(run, nsta, pmean, raru, ocw):
            return (Path("iiot_data/iiot_data_pmean/uora") / f"ocwMin_{ocw}"
                    / f"{run}_run-{nsta}_sta-{raru}_rarus{ptag(pmean)}" / TP_FILE)
        def cmab_tp_path(run, nsta, pmean):
            return CMAB_DIR / CMAB_VARIANT / f"{run}_run-{nsta}_sta{ptag(pmean)}" / TP_FILE


        # ---------------- Per-STA type-2 delay loaders ----------------
        def _load_per_sta(path, extra_cols):
            df = read_csv(path)
            if df is None or PER_STA_COL not in df.columns:
                return None
            if "Class" in df.columns:
                df = df[df["Class"] == 2]
            if "RX_bytes" in df.columns:
                df = df[df["RX_bytes"] > 0]
            if df.empty:
                return None
            out = df[[PER_STA_COL]].copy()
            for k, v in extra_cols.items():
                out[k] = v
            return out

        def process_method_per_sta(method):
            rows = []
            for run in RUNS:
                for nsta in NSTA_VALUES:
                    for pmean in PMEAN_VALUES:
                        d = _load_per_sta(per_sta_path(method, run, nsta, pmean),
                                          {"nSta": nsta, "pMean": pmean, "Run": run, "Method": method})
                        if d is not None:
                            rows.append(d)
            return rows

        def process_uora_per_sta():
            rows = []
            for run in RUNS:
                for nsta in NSTA_VALUES:
                    for pmean in PMEAN_VALUES:
                        for raru in nRaRus:
                            for ocw in OCwMin:
                                d = _load_per_sta(
                                    uora_per_sta_path(run, nsta, pmean, raru, ocw),
                                    {"nSta": nsta, "pMean": pmean, "Run": run,
                                     "RA_RU": raru, "OCW": ocw, "Method": "UORA"})
                                if d is not None:
                                    rows.append(d)
            return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()

        def process_cmab_per_sta():
            rows = []
            for run in RUNS:
                for nsta in NSTA_VALUES:
                    for pmean in PMEAN_VALUES:
                        d = _load_per_sta(cmab_per_sta_path(run, nsta, pmean),
                                          {"nSta": nsta, "pMean": pmean, "Run": run, "Method": "CMAB"})
                        if d is not None:
                            rows.append(d)
            return rows


        # ---------------- Throughput reader ----------------
        def read_tp(path: Path):
            if not path.exists():
                return None
            try:
                df = pd.read_csv(path, delimiter="\t")
            except Exception:
                return None
            if "Throughput_Mbps" not in df.columns or df["Throughput_Mbps"].empty:
                return None
            return df


        # ---------------- Type-2 throughput per cell (byte-share, exact) ------------
        def type2_throughput(ps_pth, tp_pth):
            ps = read_csv(ps_pth)
            tp = read_tp(tp_pth)
            if ps is None or tp is None:
                return None
            if "RX_bytes" not in ps.columns or "Class" not in ps.columns:
                return None
            total = ps["RX_bytes"].sum()
            if total <= 0:
                return None
            t2 = ps[ps["Class"] == 2]["RX_bytes"].sum()
            return float(tp["Throughput_Mbps"].sum()) * (t2 / total)


        # ---------------- Type-2 packet loss per cell (deadline-free) ---------------
        # Uses the TX_pkts / RX_pkts columns written by the scenario: TX_pkts is what
        # each STA generated inside the logging window, RX_pkts is how many the AP
        # received. Loss is pooled over the type-2 STAs of the run: 1 - sumRX/sumTX.
        def type2_loss(ps_pth):
            ps = read_csv(ps_pth)
            if ps is None or not {"Class", "TX_pkts", "RX_pkts"}.issubset(ps.columns):
                return None
            t2 = ps[ps["Class"] == 2]
            tx = t2["TX_pkts"].sum()
            if tx <= 0:
                return None
            ratio = t2["RX_pkts"].sum() / tx            # delivery ratio in [0,1]
            return 100.0 * (ratio if PLOT_DELIVERY else (1.0 - ratio))


        # ---------------- Load per-STA delay ----------------
        per_sta_rows = []
        for method in BASE_DIRS:
            print(f"[INFO] Processing {method} per-STA")
            per_sta_rows.extend(process_method_per_sta(method))
        print(f"[INFO] Processing CMAB per-STA ({CMAB_VARIANT})")
        per_sta_rows.extend(process_cmab_per_sta())
        per_sta_other = pd.concat(per_sta_rows, ignore_index=True) if per_sta_rows else pd.DataFrame()

        print("[INFO] Processing UORA per-STA")
        per_sta_uora = process_uora_per_sta()
        print(f"[OK] per-STA UORA rows: {len(per_sta_uora)}, other rows: {len(per_sta_other)}")


        # ---------------- UORA OCW selection (per (nSta, pMean, RA_RU), p99) ---------
        def select_best_ocw_per_sta(per_sta_df, delay_col=PER_STA_COL):
            if per_sta_df.empty:
                return pd.DataFrame()
            grouped = (per_sta_df.groupby(["nSta", "pMean", "RA_RU", "OCW"])[delay_col]
                       .quantile(0.99).reset_index())
            idx = grouped.groupby(["nSta", "pMean", "RA_RU"])[delay_col].idxmin()
            return grouped.loc[idx][["nSta", "pMean", "RA_RU", "OCW"]].reset_index(drop=True)

        per_sta_uora_ra = per_sta_uora[per_sta_uora["RA_RU"] > 0]
        per_sta_uora_sa = per_sta_uora[per_sta_uora["RA_RU"] == 0]
        best_keys = select_best_ocw_per_sta(per_sta_uora_ra)
        one_ocw = sorted(per_sta_uora_sa["OCW"].unique())[0] if not per_sta_uora_sa.empty else None


        # ---------------- Apply selection to per-STA delay ----------------
        if not best_keys.empty:
            per_sta_uora_ra_best = per_sta_uora_ra.merge(best_keys, on=["nSta", "pMean", "RA_RU", "OCW"], how="inner")
        else:
            per_sta_uora_ra_best = pd.DataFrame()
        if one_ocw is not None:
            per_sta_uora_sa_best = per_sta_uora_sa[per_sta_uora_sa["OCW"] == one_ocw].copy()
        else:
            per_sta_uora_sa_best = pd.DataFrame()
        per_sta_uora_best = pd.concat([per_sta_uora_ra_best, per_sta_uora_sa_best], ignore_index=True)


        # ---------------- Labels + combine ----------------
        def _uora_label(raru):
            if raru == 0:
                return "SA OFDMA"
            if raru == 1:
                return "1 RA RU"
            return f"{int(raru)} RA RUs"

        if not per_sta_uora_best.empty:
            per_sta_uora_best["Method"] = "UORA"
            per_sta_uora_best["Label"]  = per_sta_uora_best["RA_RU"].apply(_uora_label)

        per_sta_std = per_sta_other.copy()
        if not per_sta_std.empty:
            per_sta_std["Label"] = per_sta_std["Method"].replace({"CMAB": CMAB_LABEL})

        per_sta_combined = pd.concat([per_sta_std, per_sta_uora_best], ignore_index=True)
        per_sta_combined.to_csv(OUTPUT_CSV, index=False)
        print(f"[OK] per-STA combined CSV: {OUTPUT_CSV}")


        # ---------------- Load type-2 throughput + loss (UORA = delay-selected) -----
        # One value per (Method, nSta, pMean, Run) cell for each metric.
        tp_rows, loss_rows = [], []
        for method in BASE_DIRS:
            for run in RUNS:
                for nsta in NSTA_VALUES:
                    for pmean in PMEAN_VALUES:
                        pp = per_sta_path(method, run, nsta, pmean)
                        v = type2_throughput(pp, tp_path(method, run, nsta, pmean))
                        if v is not None:
                            tp_rows.append({"Method": method, "nSta": nsta, "pMean": pmean, "Run": run, "TP": v})
                        l = type2_loss(pp)
                        if l is not None:
                            loss_rows.append({"Method": method, "nSta": nsta, "pMean": pmean, "Run": run, "Loss": l})
        for run in RUNS:
            for nsta in NSTA_VALUES:
                for pmean in PMEAN_VALUES:
                    pp = cmab_per_sta_path(run, nsta, pmean)
                    v = type2_throughput(pp, cmab_tp_path(run, nsta, pmean))
                    if v is not None:
                        tp_rows.append({"Method": "CMAB", "nSta": nsta, "pMean": pmean, "Run": run, "TP": v})
                    l = type2_loss(pp)
                    if l is not None:
                        loss_rows.append({"Method": "CMAB", "nSta": nsta, "pMean": pmean, "Run": run, "Loss": l})

        uora_tp_rows, uora_loss_rows = [], []
        for run in RUNS:
            for nsta in NSTA_VALUES:
                for pmean in PMEAN_VALUES:
                    for raru in nRaRus:
                        for ocw in OCwMin:
                            pp = uora_per_sta_path(run, nsta, pmean, raru, ocw)
                            v = type2_throughput(pp, uora_tp_path(run, nsta, pmean, raru, ocw))
                            if v is not None:
                                uora_tp_rows.append({"Method": "UORA", "nSta": nsta, "pMean": pmean, "Run": run,
                                                     "RA_RU": raru, "OCW": ocw, "TP": v})
                            l = type2_loss(pp)
                            if l is not None:
                                uora_loss_rows.append({"Method": "UORA", "nSta": nsta, "pMean": pmean, "Run": run,
                                                       "RA_RU": raru, "OCW": ocw, "Loss": l})

        tp_std   = pd.DataFrame(tp_rows)
        tp_uora  = pd.DataFrame(uora_tp_rows)
        loss_std  = pd.DataFrame(loss_rows)
        loss_uora = pd.DataFrame(uora_loss_rows)


        def _uora_select(df):
            """Keep only the delay-selected OCW (raru>0) and one_ocw (SA OFDMA) cells."""
            if df.empty:
                return pd.DataFrame()
            ra = df[df["RA_RU"] > 0]
            sa = df[df["RA_RU"] == 0]
            ra_b = (ra.merge(best_keys, on=["nSta", "pMean", "RA_RU", "OCW"], how="inner")
                    if not best_keys.empty else pd.DataFrame())
            sa_b = (sa[sa["OCW"] == one_ocw].copy() if one_ocw is not None else pd.DataFrame())
            return pd.concat([ra_b, sa_b], ignore_index=True)

        uora_tp_best   = _uora_select(tp_uora)
        uora_loss_best = _uora_select(loss_uora)


        def _combine(std_df, uora_best, valcol):
            """Label + stack the standard/CMAB frame with the OCW-selected UORA frame."""
            s = std_df.copy()
            if not s.empty:
                s["Label"] = s["Method"].replace({"CMAB": CMAB_LABEL})
                s = s[["Label", "nSta", "pMean", "Run", valcol]]
            if not uora_best.empty:
                u = uora_best.copy()
                u["Label"] = u["RA_RU"].apply(_uora_label)
                u = u[["Label", "nSta", "pMean", "Run", valcol]]
            else:
                u = pd.DataFrame()
            return pd.concat([s if not s.empty else pd.DataFrame(), u], ignore_index=True)

        tp_combined   = _combine(tp_std,   uora_tp_best,   "TP")
        loss_combined = _combine(loss_std, uora_loss_best, "Loss")


        # ---------------- Plot styling ----------------
        HUE_ORDER = [
            "EDCA", "A2P", "A2PV2", CMAB_LABEL,
            "SA OFDMA",
            "1 RA RU", "5 RA RUs", "9 RA RUs", "13 RA RUs", "18 RA RUs",
        ]
        plt.rcParams.update({
            "font.size": 14, "axes.labelsize": 14,
            "xtick.labelsize": 12, "ytick.labelsize": 12, "legend.fontsize": 12,
        })

        ERRBAR = "se" if ERROR_KIND == "sem" else "sd"

        # pMean as an ordered category -> evenly spaced x positions
        PMEAN_ORDER   = sorted(PMEAN_VALUES)
        PMEAN_CATS    = [str(p) for p in PMEAN_ORDER]
        for _df in (per_sta_combined, tp_combined, loss_combined):
            if not _df.empty:
                _df["pMean_s"] = pd.Categorical(_df["pMean"].astype(str),
                                                categories=PMEAN_CATS, ordered=True)

        XLABEL = "Type-2 inter-arrival exponential mean (s)   —   smaller = heavier load"
        LOSS_YLABEL = "Type-2 UL Delivery Ratio (%)" if PLOT_DELIVERY else "Type-2 UL Packet Loss (%)"


        def _per_run(data, ycol):
            """Collapse the per-STA samples to ONE value per run, so the error bars
    reflect seed-to-seed variability (N = #runs) rather than the heavy-tailed
    per-STA spread. For already per-run frames (TP, loss) this is a no-op."""
            keys = [k for k in ("Label", "pMean_s", "nSta", "Run") if k in data.columns]
            return data.groupby(keys, observed=True)[ycol].mean().reset_index()


        def _lineplot(data, ycol, ax):
            d = _per_run(data, ycol)
            present = [l for l in HUE_ORDER if l in d["Label"].unique()]
            sns.lineplot(
                data=d, x="pMean_s", y=ycol, hue="Label", hue_order=present,
                estimator="mean", errorbar=ERRBAR,
                marker="o", markersize=6, linewidth=1.9,
                err_style="bars", err_kws={"capsize": 3, "capthick": 1.0, "elinewidth": 1.0},
                ax=ax,
            )
            return present


        # ============ Loop: delay + throughput + loss line plots per nSta ==========
        for nsta in NSTA_VALUES:

            # ---- Plot A: type-2 per-STA mean delay vs pMean (log-y) ----
            dl = per_sta_combined[per_sta_combined["nSta"] == nsta].copy()
            if not dl.empty:
                fig, ax = plt.subplots(figsize=(8.6, 6.0))
                _lineplot(dl, PER_STA_COL, ax)
                ax.set_yscale("log")
                ax.yaxis.set_major_formatter(ScalarFormatter())   # 1, 10, 100 instead of 10^n
                ax.yaxis.set_minor_formatter(NullFormatter())      # minor ticks stay unlabeled
                ax.set_xlabel(XLABEL)
                ax.set_ylabel("Type-2 UL Average Delay (ms)")
                ax.set_title(f"{nsta} Stochastic STA" + ("s" if nsta != 1 else ""))
                ax.grid(True, which="both", axis="y", linestyle=":", linewidth=0.8, alpha=0.7)
                ax.grid(True, axis="x", linestyle="--", linewidth=0.5, alpha=0.6)
                ax.legend(prop={"size": 11}, title=None, ncol=2)
                plt.tight_layout()
                plt.savefig(f"fig/iiot/pmean/line_type2_delay_nSta-{nsta}.png", dpi=300)
                plt.show(); plt.close()
                print(f"[OK] type-2 delay line plot for nSta={nsta} done.")

            # ---- Plot B: type-2 throughput vs pMean (linear-y) ----
            tp = tp_combined[tp_combined["nSta"] == nsta].copy()
            if not tp.empty:
                fig, ax = plt.subplots(figsize=(8.6, 6.0))
                _lineplot(tp, "TP", ax)
                ax.set_ylim(bottom=0)
                ax.set_xlabel(XLABEL)
                ax.set_ylabel("Type-2 Throughput (Mbps)")
                ax.set_title(f"{nsta} Stochastic STA" + ("s" if nsta != 1 else ""))
                ax.grid(True, axis="y", linestyle="--", linewidth=0.5, alpha=0.7)
                ax.set_axisbelow(True)
                ax.legend(prop={"size": 11}, title=None, ncol=2)
                plt.tight_layout()
                plt.savefig(f"fig/iiot/pmean/line_type2_throughput_nSta-{nsta}.png", dpi=300)
                plt.show(); plt.close()
                print(f"[OK] type-2 throughput line plot for nSta={nsta} done.")

            # ---- Plot C: type-2 packet loss (or delivery ratio) vs pMean (linear-y) ----
            ls = loss_combined[loss_combined["nSta"] == nsta].copy()
            if not ls.empty:
                fig, ax = plt.subplots(figsize=(8.6, 6.0))
                _lineplot(ls, "Loss", ax)
                ax.set_ylim(0, 100 if PLOT_DELIVERY else None)
                if not PLOT_DELIVERY:
                    ax.set_ylim(bottom=0)
                ax.set_xlabel(XLABEL)
                ax.set_ylabel(LOSS_YLABEL)
                ax.set_title(f"{nsta} Stochastic STA" + ("s" if nsta != 1 else ""))
                ax.grid(True, axis="y", linestyle="--", linewidth=0.5, alpha=0.7)
                ax.set_axisbelow(True)
                ax.legend(prop={"size": 11}, title=None, ncol=2)
                plt.tight_layout()
                plt.savefig(f"fig/iiot/pmean/line_type2_loss_nSta-{nsta}.png", dpi=300)
                plt.show(); plt.close()
                print(f"[OK] type-2 loss line plot for nSta={nsta} done.")
        _done("iiot_type2_lines")
    except Exception as _err:
        _done("iiot_type2_lines", _err)

# ---- iiot_box_per_sta: Per-station mean delay, side by side ----
if _run("iiot_box_per_sta"):
    try:
        from pathlib import Path
        import pandas as pd, numpy as np
        import matplotlib.pyplot as plt
        import seaborn as sns

        plt.rcParams.update({
            "font.size": 8, "axes.labelsize": 8, "axes.titlesize": 9,
            "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 6.5,
            "pdf.fonttype": 42, "ps.fonttype": 42,
        })
        TEXTWIDTH_IN = 7.16                    # figure* width

        RUNS, NSTA_VALUES, PMEANS = range(1, 11), [1, 30, 50, 60, 70, 90], [0.025, 0.05]
        DEADLINE_MS = 20
        BOX_EXCLUDE = {("EDCA", 0.025, 70), ("EDCA", 0.025, 80), ("EDCA", 0.025, 90)}
        BOX_DROP  = []
        COMPRESS_PMEANS = {0.025}              # only this panel gets the broken/compressed y-axis
        BOUND, COMPRESS = 20, 0.15            # linear <= 20 ms, compressed above (break = deadline)
        TICKS_COMPRESS = [0, 2.5, 5, 7.5, 10, 12.5, 15, 17.5, 20, 35, 45]
        TICKS_LINEAR   = [0, 2.5, 5, 7.5, 10, 12.5, 15, 17.5]     # 50 ms panel: plain linear
        WHIS, WIDTH = 3.5, 0.9
        FILTER_MS = None

        BASE_DIRS = {"EDCA": Path("iiot_data/iiot_data_pmean/edca"), "A2P": Path("iiot_data/iiot_data_pmean/a2p"),
                     "A2PV2": Path("iiot_data/iiot_data_pmean/a2pv2")}
        CMAB_DIR, CMAB_VARIANT, CMAB_LABEL = Path("iiot_data/iiot_data_pmean/cmab"), "CUCB_FairnessWeighted_c2.5", "CUCB"
        UORA_ROOT = Path("iiot_data/iiot_data_pmean/uora")
        nRaRus, OCwMin, PS = [0, 1, 5, 9, 13, 18], [1, 3, 7, 15, 31, 63], "per_sta_stats.out"

        def ptag(p): return "" if abs(p - 0.1) < 1e-9 else f"_pMean-{p}"
        def std_dir(m,run,n,p):    return BASE_DIRS[m]/f"{run}_run-{n}_sta{ptag(p)}"
        def cmab_dir(run,n,p):     return CMAB_DIR/CMAB_VARIANT/f"{run}_run-{n}_sta{ptag(p)}"
        def uora_dir(run,n,p,r,o): return UORA_ROOT/f"ocwMin_{o}"/f"{run}_run-{n}_sta-{r}_rarus{ptag(p)}"
        def ulabel(r): return "SA OFDMA" if r == 0 else ("1 RA RU" if r == 1 else f"{int(r)} RA RUs")

        def t2_delay(run_dir):
            q = run_dir/PS
            if not q.exists(): return np.array([])
            s = pd.read_csv(q, sep="\t")
            if "Class" not in s.columns: return np.array([])
            return s[s["Class"] == 2]["Avg_delay_ms"].dropna().values

        # ---- UORA: best OCW per (pMean,nSta,RA_RU) by median per-STA delay ----
        best_ocw = {}
        for p in PMEANS:
            for n in NSTA_VALUES:
                for r in nRaRus:
                    cand = []
                    for o in OCwMin:
                        v = np.concatenate([t2_delay(uora_dir(run, n, p, r, o)) for run in RUNS] or [np.array([])])
                        if len(v): cand.append((float(np.median(v)), o))
                    if cand: best_ocw[(p, n, r)] = min(cand)[1]

        ORDER = ["EDCA", "A2P", "A2PV2", "CUCB", "SA OFDMA", "1 RA RU", "5 RA RUs", "9 RA RUs", "13 RA RUs", "18 RA RUs"]
        cmap = plt.cm.tab10(np.linspace(0, 1, 10))
        STYLE = {l: cmap[i] for i, l in enumerate(ORDER)}

        def tform_compress(y):
            y = np.asarray(y, float)
            return np.where(y <= BOUND, y, BOUND + (y - BOUND) * COMPRESS)

        def panel_data(p):
            recs = []
            for n in NSTA_VALUES:
                for m in list(BASE_DIRS) + [CMAB_LABEL]:
                    if (m, p, n) in BOX_EXCLUDE: continue
                    for run in RUNS:
                        rd = cmab_dir(run, n, p) if m == CMAB_LABEL else std_dir(m, run, n, p)
                        for v in t2_delay(rd): recs.append((n, m, v))
                for r in nRaRus:
                    lab = ulabel(r)
                    if lab in BOX_DROP: continue
                    o = best_ocw.get((p, n, r), OCwMin[0])
                    for run in RUNS:
                        for v in t2_delay(uora_dir(run, n, p, r, o)): recs.append((n, lab, v))
            dd = pd.DataFrame(recs, columns=["nSta", "Method", "delay"])
            if FILTER_MS is not None: dd = dd[dd["delay"] < FILTER_MS]
            return dd

        def draw_panel(ax, p, tag):
            dd = panel_data(p)
            if dd.empty: ax.text(0.5, 0.5, f"no data (pMean={p})", ha="center", va="center", transform=ax.transAxes); return
            compress = p in COMPRESS_PMEANS
            yt = tform_compress if compress else (lambda y: np.asarray(y, float))
            ticks = TICKS_COMPRESS if compress else TICKS_LINEAR
            dd = dd.assign(y=yt(dd["delay"].values))
            hue_order = [l for l in ORDER if l not in BOX_DROP and l in set(dd["Method"])]
            palette = {l: STYLE[l] for l in hue_order}
            sns.boxplot(data=dd, x="nSta", y="y", hue="Method", hue_order=hue_order, palette=palette,
                        whis=WHIS, width=WIDTH, showfliers=True, ax=ax, linewidth=0.5,
                        flierprops=dict(marker=".", markersize=1.5, markeredgecolor="none", alpha=0.4))
            ax.set_yticks(yt(ticks)); ax.set_yticklabels([str(t) for t in ticks])
            ax.set_ylim(0, yt(ticks[-1]))
            ax.axhline(yt(DEADLINE_MS), ls="--", color="k", lw=0.9, alpha=0.7)
            ax.set_xlabel(f"({tag})", labelpad=2)          # panel label, no title on top
            ax.grid(True, axis="y", ls="--", lw=0.4); ax.grid(True, axis="x", ls="--", lw=0.4)
            if ax.get_legend() is not None: ax.get_legend().remove()

        Path("fig/iiot").mkdir(parents=True, exist_ok=True)
        fig, axes = plt.subplots(1, len(PMEANS), figsize=(TEXTWIDTH_IN, 2.5))
        axes = np.atleast_1d(axes)
        for ax, p, tag in zip(axes, PMEANS, ["a", "b", "c", "d"]):
            draw_panel(ax, p, tag)
        axes[0].set_ylabel("Type-2 avg UL delay (ms)")
        for ax in axes[1:]: ax.set_ylabel("")

        handles = [plt.Rectangle((0, 0), 1, 1, color=STYLE[l]) for l in ORDER]
        fig.legend(handles, ORDER, loc="upper center", ncol=5,
                   bbox_to_anchor=(0.5, 1.10), frameon=False)

        fig.tight_layout()
        fig.supxlabel("Number of type-2 STAs", y=-0.02, fontsize=8)   # raised -> closer to (a)/(b)
        fig.savefig("fig/iiot/iiot_box_sidebyside.pdf", bbox_inches="tight")
        plt.show()
        _done("iiot_box_per_sta")
    except Exception as _err:
        _done("iiot_box_per_sta", _err)

# ---- iiot_box_loss_grid: Per-packet delay and loss grid ----
if _run("iiot_box_loss_grid"):
    try:
        from pathlib import Path
        import pandas as pd, numpy as np
        import matplotlib.pyplot as plt

        plt.rcParams.update({
            "font.size": 8, "axes.labelsize": 8, "xtick.labelsize": 7,
            "ytick.labelsize": 7, "legend.fontsize": 6.5,
            "lines.linewidth": 1.0, "lines.markersize": 3.0,
            "pdf.fonttype": 42, "ps.fonttype": 42,
        })
        TEXTWIDTH_IN = 7.16

        RUNS, NSTA_VALUES, PMEANS = range(1, 11), [1, 30, 50, 60, 70, 90], [0.025, 0.05]
        DEADLINE_MS = 20
        EXCLUDE = {("EDCA", 0.025, 70), ("EDCA", 0.025, 80), ("EDCA", 0.025, 90)}   # box (delay) only
        LOSS_ERR = "sem"          # "sem" (uncertainty in mean) or "std" (run-to-run spread)

        # ---- delay transforms (top row) ----
        S1_25, S2_25 = 10/80, 5/200
        S_50         = 0.25
        def yt_25(y):
            y = np.asarray(y, float)
            return np.where(y <= 20, y,
                   np.where(y <= 100, 20 + (y-20)*S1_25, 20 + 80*S1_25 + (y-100)*S2_25))
        def yt_50(y):
            y = np.asarray(y, float)
            return np.where(y <= 20, y, 20 + (y-20)*S_50)
        YCFG = {
            0.025: dict(yt=yt_25, major=[0,5,10,15,20,40,60,80,100,200,300], minor=[2.5,7.5,12.5,17.5], top=300),
            0.05:  dict(yt=yt_50, major=[0,5,10,15,20,30,40,50],             minor=[2.5,7.5,12.5,17.5], top=50),
        }

        BASE_DIRS = {"EDCA": Path("iiot_data/iiot_data_pmean/edca"), "A2P": Path("iiot_data/iiot_data_pmean/a2p"),
                     "A2S": Path("iiot_data/iiot_data_pmean/a2pv2")}
        CMAB_DIR, CMAB_VARIANT, CMAB_LABEL = Path("iiot_data/iiot_data_pmean/cmab"), "CUCB_FairnessWeighted_c2.5", "CUCB"
        UORA_ROOT = Path("iiot_data/iiot_data_pmean/uora")
        nRaRus, OCwMin, PS, T2 = [0, 1, 5, 9, 13, 18], [1, 3, 7, 15, 31, 63], "per_sta_stats.out", "type2_packets.out"

        def ptag(p): return "" if abs(p - 0.1) < 1e-9 else f"_pMean-{p}"
        def std_dir(m,run,n,p):    return BASE_DIRS[m]/f"{run}_run-{n}_sta{ptag(p)}"
        def cmab_dir(run,n,p):     return CMAB_DIR/CMAB_VARIANT/f"{run}_run-{n}_sta{ptag(p)}"
        def uora_dir(run,n,p,r,o): return UORA_ROOT/f"ocwMin_{o}"/f"{run}_run-{n}_sta-{r}_rarus{ptag(p)}"
        def ulabel(r): return "SA OFDMA" if r == 0 else ("1 RA RU" if r == 1 else f"{int(r)} RA RUs")

        def pkt_delays(run_dir):
            q = run_dir/T2
            if not q.exists(): return np.array([])
            return pd.read_csv(q, sep="\t")["delay_ms"].dropna().values
        def gen_count(run_dir):
            q = run_dir/PS
            if not q.exists(): return 0
            s = pd.read_csv(q, sep="\t")
            if "Class" not in s.columns: return 0
            return int(s[s["Class"] == 2]["TX_pkts"].sum())
        def persta(run_dir):
            q = run_dir/PS
            if not q.exists(): return np.array([])
            s = pd.read_csv(q, sep="\t")
            if "Class" not in s.columns: return np.array([])
            return s[s["Class"] == 2]["Avg_delay_ms"].dropna().values

        ORDER = ["EDCA", "A2P", "A2S", "CUCB", "SA OFDMA", "1 RA RU", "5 RA RUs", "9 RA RUs", "13 RA RUs", "18 RA RUs"]
        cmap, MARK = plt.cm.tab10(np.linspace(0, 1, 10)), "osv^D<>ph*"
        STYLE = {l: dict(color=cmap[i], marker=MARK[i % 10]) for i, l in enumerate(ORDER)}

        best_ocw = {}
        for p in PMEANS:
            for n in NSTA_VALUES:
                for r in nRaRus:
                    cand = []
                    for o in OCwMin:
                        v = np.concatenate([persta(uora_dir(run, n, p, r, o)) for run in RUNS] or [np.array([])])
                        if len(v): cand.append((float(np.median(v)), o))
                    if cand: best_ocw[(p, n, r)] = min(cand)[1]

        def run_dirs(label, n, p):
            if label == CMAB_LABEL: return [cmab_dir(run, n, p) for run in RUNS]
            if label in BASE_DIRS:  return [std_dir(label, run, n, p) for run in RUNS]
            r = {ulabel(x): x for x in nRaRus}[label]; o = best_ocw.get((p, n, r), OCwMin[0])
            return [uora_dir(run, n, p, r, o) for run in RUNS]

        # ---- box stats (pooled per-packet) + loss mean/error (per-run) ----
        STATS, LOSS, LOSSE = {}, {}, {}
        for p in PMEANS:
            for n in NSTA_VALUES:
                for label in ORDER:
                    pooled_list, loss_runs = [], []
                    for d in run_dirs(label, n, p):
                        g = gen_count(d); dl = pkt_delays(d)
                        if len(dl): pooled_list.append(dl)
                        if g > 0:
                            ontime = int((dl <= DEADLINE_MS).sum()) if len(dl) else 0
                            loss_runs.append(1 - ontime / g)               # per-run loss
                    if loss_runs:
                        LOSS[(label, p, n)]  = float(np.mean(loss_runs))
                        sd = float(np.std(loss_runs))
                        LOSSE[(label, p, n)] = sd / np.sqrt(len(loss_runs)) if LOSS_ERR == "sem" else sd
                    if (label, p, n) in EXCLUDE or not pooled_list: continue
                    pooled = np.concatenate(pooled_list)
                    q1, med, q3 = np.percentile(pooled, [25, 50, 75])
                    p1, p99 = np.percentile(pooled, [1, 99])
                    STATS[(label, p, n)] = dict(med=med, q1=q1, q3=q3, whislo=p1, whishi=p99)

        xpos = np.arange(len(NSTA_VALUES))
        present = [l for l in ORDER if any((l, p, n) in STATS or (l, p, n) in LOSS for p in PMEANS for n in NSTA_VALUES)]
        w = 0.8 / len(present)

        # ---- loss transforms (bottom row) ----
        LB    = 0.2
        TOP_C = 0.9
        S_LC  = 0.1 / (TOP_C - LB)                                    # compressed zone display height = 0.1
        def yl_25(y):
            y = np.asarray(y, float)
            return np.where(y <= LB, y, LB + (y - LB) * S_LC)
        def yl_50(y): return np.asarray(y, float)

        LOSS_MAJ_25 = [0, 0.05, 0.1, 0.15] + list(np.round(np.arange(0.2, TOP_C + 1e-9, 0.2), 2))   # 0..0.15, 0.2,0.4,0.6,0.8
        LOSS_MIN_25 = list(np.round(np.arange(0.1, TOP_C + 1e-9, 0.2), 2))                            # 0.1,0.3,0.5,0.7,0.9
        LOSSCFG = {
            0.025: dict(yt=yl_25, major=LOSS_MAJ_25, minor=LOSS_MIN_25, top=TOP_C),
            0.05:  dict(yt=yl_50, major=[0, 0.05, 0.1, 0.15, 0.2], minor=[], top=0.2),
        }

        def draw_box(ax, p):
            yt = YCFG[p]["yt"]
            for i, label in enumerate(present):
                bx, pos = [], []
                for k, n in enumerate(NSTA_VALUES):
                    s = STATS.get((label, p, n))
                    if not s: continue
                    bx.append({key: float(yt(s[key])) for key in ("med","q1","q3","whislo","whishi")} | {"fliers": []})
                    pos.append(xpos[k] + (i - (len(present) - 1) / 2) * w)
                if not bx: continue
                r = ax.bxp(bx, positions=pos, widths=w * 0.9, showfliers=False, patch_artist=True, manage_ticks=False)
                for box in r["boxes"]:   box.set_facecolor(STYLE[label]["color"]); box.set_linewidth(0.3)
                for e in r["medians"]:   e.set_color("k"); e.set_linewidth(0.5)
                for e in r["whiskers"]+r["caps"]: e.set_linewidth(0.3)
            cfg = YCFG[p]
            ax.set_yticks(yt(cfg["major"])); ax.set_yticklabels([str(t) for t in cfg["major"]]); ax.set_ylim(0, float(yt(cfg["top"])))
            if cfg["minor"]:
                ax.set_yticks(yt(cfg["minor"]), minor=True); ax.grid(True, which="minor", axis="y", ls=":", lw=0.3, alpha=0.4)
            ax.set_xticks(xpos); ax.set_xticklabels([])
            ax.grid(True, which="major", ls="--", lw=0.4, alpha=0.6)

        def draw_loss(ax, p):
            cfg = LOSSCFG[p]; yt = cfg["yt"]
            for label in present:
                y  = np.array([LOSS.get((label, p, n), np.nan)  for n in NSTA_VALUES])
                ye = np.array([LOSSE.get((label, p, n), 0.0)    for n in NSTA_VALUES])
                if np.all(np.isnan(y)): continue
                ymid = yt(y)
                lower = ymid - yt(np.clip(y - ye, 0, None))
                upper = yt(y + ye) - ymid
                yerr  = np.clip(np.nan_to_num(np.vstack([lower, upper]), nan=0.0), 0, None)  # no negatives/NaN
                ax.errorbar(xpos, ymid, yerr=yerr, label=label, color=STYLE[label]["color"],
                            marker=STYLE[label]["marker"], capsize=2, elinewidth=0.6)
            ax.set_yticks(yt(np.array(cfg["major"]))); ax.set_yticklabels([f"{t:g}" for t in cfg["major"]])
            if cfg.get("minor"):
                ax.set_yticks(yt(np.array(cfg["minor"])), minor=True)
                ax.grid(True, which="minor", axis="y", ls=":", lw=0.3, alpha=0.4)
            top_disp = float(yt(cfg["top"]))
            ax.set_ylim(-0.04 * top_disp, top_disp)
            #ax.set_ylim(0, float(yt(cfg["top"])))
            ax.set_xticks(xpos); ax.set_xticklabels(NSTA_VALUES)
            ax.grid(True, which="major", ls="--", lw=0.4, alpha=0.6)

        fig, axes = plt.subplots(2, 2, figsize=(TEXTWIDTH_IN, 4.0),
                                 gridspec_kw={"height_ratios": [1.25, 1]})
        SUBCAPS = {
            0.025: ("(a) Mean inter-arrival time of 25 ms.", "(c) Mean inter-arrival time of 25 ms."),
            0.05:  ("(b) Mean inter-arrival time of 50 ms.", "(d) Mean inter-arrival time of 50 ms."),
        }

        for c, p in enumerate(PMEANS):
            draw_box(axes[0][c], p);  axes[0][c].set_xlabel(SUBCAPS[p][0], labelpad=2, fontsize=7)
            draw_loss(axes[1][c], p); axes[1][c].set_xlabel(SUBCAPS[p][1], labelpad=2, fontsize=7)
    
        axes[0][0].set_ylabel("Type-2 UL delay (ms)")
        axes[1][0].set_ylabel("Type-2 deadline-miss ratio")

        hb = [plt.Rectangle((0, 0), 1, 1, color=STYLE[l]["color"]) for l in present]
        fig.legend(hb, present, loc="upper center", ncol=5, bbox_to_anchor=(0.5, 1.07), frameon=False)
        fig.tight_layout(); fig.supxlabel("Number of type-2 STAs", y=-0.02, fontsize=8)
        Path("fig/iiot").mkdir(parents=True, exist_ok=True)
        fig.savefig("fig/iiot/iiot_box_loss_grid.pdf", bbox_inches="tight"); plt.show()
        _done("iiot_box_loss_grid")
    except Exception as _err:
        _done("iiot_box_loss_grid", _err)

# ---- iiot_t1_throughput: Type-1 throughput ----
if _run("iiot_t1_throughput"):
    try:
        from pathlib import Path
        import pandas as pd, numpy as np
        import matplotlib.pyplot as plt

        TP = "throughput.out"

        def t1_tp_run(run_dir):                      # type-1 throughput for one run (Mbps)
            ps, tp = run_dir/PS, run_dir/TP
            if not ps.exists() or not tp.exists(): return np.nan
            s = pd.read_csv(ps, sep="\t")
            if "Class" not in s.columns: return np.nan
            ln = tp.read_text().splitlines()
            if len(ln) < 2: return np.nan
            tot = float(s["RX_bytes"].sum())
            if tot <= 0: return np.nan
            return float(ln[1].split()[3]) * float(s[s["Class"] == 1]["RX_bytes"].sum()) / tot

        # ---- UORA: best OCW per (pMean,nSta,RA_RU) by MAX type-1 throughput ----
        best_ocw_tp = {}
        for p in PMEANS:
            for n in NSTA_VALUES:
                for r in nRaRus:
                    cand = []
                    for o in OCwMin:
                        vals = [v for run in RUNS if np.isfinite(v := t1_tp_run(uora_dir(run, n, p, r, o)))]
                        if vals: cand.append((float(np.mean(vals)), o))
                    if cand: best_ocw_tp[(p, n, r)] = max(cand)[1]     # argmax throughput

        def tp_dirs(label, n, p):
            if label == CMAB_LABEL: return [cmab_dir(run, n, p) for run in RUNS]
            if label in BASE_DIRS:  return [std_dir(label, run, n, p) for run in RUNS]
            r = {ulabel(x): x for x in nRaRus}[label]; o = best_ocw_tp.get((p, n, r), OCwMin[0])
            return [uora_dir(run, n, p, r, o) for run in RUNS]

        # ---- type-1 throughput per (label, pMean, nSta): mean +/- sem ----
        T1, T1E = {}, {}
        for p in PMEANS:
            for n in NSTA_VALUES:
                for label in ORDER:
                    vals = [v for d in tp_dirs(label, n, p) if np.isfinite(v := t1_tp_run(d))]
                    if not vals: continue
                    T1[(label, p, n)]  = float(np.mean(vals))
                    T1E[(label, p, n)] = float(np.std(vals) / np.sqrt(len(vals)))

        present_tp = [l for l in ORDER if any((l, p, n) in T1 for p in PMEANS for n in NSTA_VALUES)]
        wb = 0.8 / len(present_tp)

        fig, axes = plt.subplots(1, len(PMEANS), figsize=(TEXTWIDTH_IN, 2.2), sharey=True)
        axes = np.atleast_1d(axes)
        for ax, p, tag in zip(axes, PMEANS, ["(a) Mean inter-arrival time of 25 ms.", "(b) Mean inter-arrival time of 50 ms."]):
            for i, label in enumerate(present_tp):
                y  = [T1.get((label, p, n), np.nan) for n in NSTA_VALUES]
                ye = [T1E.get((label, p, n), np.nan) for n in NSTA_VALUES]
                ax.bar(xpos + (i - (len(present_tp) - 1) / 2) * wb, y, wb, yerr=ye,
                       color=STYLE[label]["color"], error_kw=dict(elinewidth=0.4, capsize=1.0))
            ax.set_xticks(xpos); ax.set_xticklabels(NSTA_VALUES)
            ax.set_xlabel(f"{tag}", labelpad=2, fontsize=7)
            ax.grid(True, axis="y", ls="--", lw=0.4, alpha=0.6)
        axes[0].set_ylabel("Type-1 throughput (Mbps)")

        hb = [plt.Rectangle((0, 0), 1, 1, color=STYLE[l]["color"]) for l in present_tp]
        fig.legend(hb, present_tp, loc="upper center", ncol=5, bbox_to_anchor=(0.5, 1.10), frameon=False)
        fig.tight_layout(); fig.supxlabel("Number of type-2 STAs", y=-0.02, fontsize=8)
        Path("fig/iiot").mkdir(parents=True, exist_ok=True)
        fig.savefig("fig/iiot/iiot_t1_throughput.pdf", bbox_inches="tight"); plt.show()
        _done("iiot_t1_throughput")
    except Exception as _err:
        _done("iiot_t1_throughput", _err)

# ============================================================================
# Extended-reality scenario
# ============================================================================

# ---- xr_results: Pose delay, deadline misses and video throughput ----
if _run("xr_results"):
    try:
        from pathlib import Path
        import pandas as pd, numpy as np
        import matplotlib.pyplot as plt

        plt.rcParams.update({
            "font.size": 8, "axes.labelsize": 8, "axes.titlesize": 8,
            "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 6.5,
            "lines.linewidth": 1.0, "lines.markersize": 3.0,
            "axes.linewidth": 0.6, "grid.linewidth": 0.4, "pdf.fonttype": 42, "ps.fonttype": 42,
        })
        TEXTWIDTH_IN, COLWIDTH_IN = 7.16, 3.5

        # ---------------- config ----------------
        # All OFDMA schemes are read from the DlFirstAcrossAcs sweep: with the flag off,
        # an access won on AC_VO with an empty voice queue builds a DL-MU for AC_VO only,
        # finds nothing, and discards the TXOP while video sits queued. EDCA has no
        # multi-user scheduler, so it is unaffected and comes from the baseline root.
        DLFIRST_ROOT = Path("xr_data_ari_dlfirst")
        EDCA_ROOT    = Path("xr_data")
        RUNS         = range(1, 11)
        NSTA_VALUES  = [1, 2, 3, 4, 5, 6, 7, 8]

        # Headset counts shown in the single-column throughput bar chart. 1 anchors the
        # unloaded reference; 5 is the feasibility boundary; 6-8 are the overload region.
        # 2-4 are omitted -- they sit on the flat part of the curve and only cost width.
        BAR_NSTA = [1, 5, 6, 7, 8]

        # Selected Access Request Interval per scheme (us), from the 10-seed sweep over
        # {16..1024}. Video frame loss saturates from ARI 64 up and cannot discriminate,
        # so each value is chosen on UL pose deadline loss and pose tail at the binding
        # operating point. A2PV2 takes 512 rather than the 256 its nSta<=5 numbers
        # marginally favour: it buys nSta=6 frame loss 0.865->0.830 for +0.25 ms of pose
        # tail, and unlike 1024 it keeps pose P99.9 inside the 10 ms deadline.
        ARI = {"A2P": 128, "A2S": 512, "UORA": 256, "CMAB": 256}

        # Deadlines the sim scored against (job_script_xr BASE_ARGS): pose 10, video 50,
        # audio 30 ms. These bounds come from the Wi-Fi Alliance tail-latency figures, so
        # the delay diagnostic uses each flow's P99.9 column, not P99 -- P99 is not the
        # statistic the bound was derived from and understates the tail. Mean delay is
        # not reported: it hides deadline violations on a skewed, deadline-bound quantity.
        POSE_DEADLINE_MS, VIDEO_FRAME_MS, AUDIO_DEADLINE_MS = 10.0, 50.0, 30.0
        DMR_BUDGET  = 0.05                     # deadline miss ratio a flow must stay under
        ERROR_KIND  = "sem"                    # "sem" or "std"; used by the line() plots only

        # XR CMAB winner: CUCB + fairness-weighted reward. c is immaterial -- the four
        # values in the grid {0.5, sqrt2, 2.0, 2.5} give byte-identical output, because
        # the exploration term is never the binding one.
        CMAB_VARIANT, CMAB_LABEL = "CUCB_FairnessWeighted_c1.41421", "CUCB-FW"
        nRaRus, OCwMin = [0, 1, 2, 3, 4], [1, 3, 7, 15, 31, 63]
        TP, PS, VH = "throughput.out", "per_sta_stats.out", "video_frame_ontime_hist.out"

        # ---------------- loaders ----------------
        def read_tp(run_dir):
            q = run_dir/TP
            if not q.exists(): return None
            df = pd.read_csv(q, sep="\t")
            return df.iloc[0] if len(df) else None

        def read_ps(run_dir):
            q = run_dir/PS
            if not q.exists(): return None
            df = pd.read_csv(q, sep="\t")
            return df if len(df) else None

        # ---- the primary metric -------------------------------------------------------
        # Packet deadline miss ratio: 1 - (packets delivered within the deadline) /
        # (packets generated). Counts a packet as failed whether it was dropped or merely
        # late, and its denominator is generated packets, so it is survivorship-proof.
        # Identical definition for all three flows; only the deadline differs.
        def pooled_dmr(s, gen, ontime):
            """Packet deadline miss ratio for a flow whose per-packet on-time count is in
    per_sta_stats.out (audio, pose)."""
            if gen not in s or ontime not in s: return np.nan
            g = float(s[gen].sum())
            return max(0.0, 1.0 - float(s[ontime].sum())/g) if g > 0 else np.nan

        def vid_pkt_dmr(run_dir, per_frame=96):
            """Packet deadline miss ratio for DL video. per_sta_stats.out only carries the
    frame-level count, so the packet-level one is recovered from the per-frame
    histogram: sum(Ontime_pkts * N_frames) is the number of video packets that
    arrived within the bound. No frame-integrity rule is applied -- that belongs
    to the separate decodability-threshold figure. Returns NaN for runs produced
    before the per-frame logging was added."""
            hp, sp = run_dir/VH, run_dir/PS
            if not hp.exists() or not sp.exists(): return np.nan
            h = pd.read_csv(hp, sep="\t"); s = pd.read_csv(sp, sep="\t")
            ontime = float((h["Ontime_pkts"] * h["N_frames"]).sum())
            gen    = float(s["Vid_frames_gen"].sum()) * per_frame
            return max(0.0, 1.0 - ontime/gen) if gen > 0 else np.nan

        # ---- secondary diagnostics ----------------------------------------------------
        def pooled_plr(s, gen, rx):
            """Packet loss ratio: counts only packets that never arrived. Subtracted from
    the deadline miss ratio it gives the share of failures that were lateness."""
            if gen not in s or rx not in s: return np.nan
            g = float(s[gen].sum())
            return max(0.0, 1.0 - float(s[rx].sum())/g) if g > 0 else np.nan

        def pkt_deliv(s, rx, frames_gen, per_frame=96):
            """DL video packet delivery: rx / (frames_gen * pkts_per_frame). Used to pick
    the UORA operating point."""
            g = float(s[frames_gen].sum()) * per_frame
            return float(s[rx].sum())/g if g > 0 else np.nan

        def frame_dmr(s):
            """Frame-level miss ratio under the strict all-96-packets rule. Kept for the
    decodability-threshold figure; not plotted here."""
            return pooled_dmr(s, "Vid_frames_gen", "Vid_frames_ontime")

        def edca_dir(run, n):     return EDCA_ROOT/"edca"/f"{run}_run-{n}_sta"
        def a2p_dir(run, n):      return DLFIRST_ROOT/"a2p"  /f"ari_{ARI['A2P']}"  /f"{run}_run-{n}_sta"
        def a2pv2_dir(run, n):    return DLFIRST_ROOT/"a2pv2"/f"ari_{ARI['A2S']}"/f"{run}_run-{n}_sta"
        def cmab_dir(run, n):     return DLFIRST_ROOT/"cmab" /f"ari_{ARI['CMAB']}" /CMAB_VARIANT/f"{run}_run-{n}_sta"
        def uora_dir(run, n, r, o):
            return DLFIRST_ROOT/"uora"/f"ari_{ARI['UORA']}"/f"ocwMin_{o}"/f"{run}_run-{n}_sta-{r}_rarus"
        def ulabel(r): return "SA OFDMA" if r == 0 else ("1 RA RU" if r == 1 else f"{int(r)} RA RUs")

        BASE_FN = {"EDCA": edca_dir, "A2P": a2p_dir, "A2S": a2pv2_dir, CMAB_LABEL: cmab_dir}
        ORDER = ["EDCA","A2P","A2S",CMAB_LABEL,"SA OFDMA","1 RA RU","2 RA RUs","3 RA RUs","4 RA RUs"]
        cmap, MARK = plt.cm.tab10(np.linspace(0,1,10)), "osv^D<>ph*"
        STYLE = {l: dict(color=cmap[i], marker=MARK[i%10]) for i,l in enumerate(ORDER)}

        # ---------------- UORA: best OCW per (nSta, RA_RU) ----------------
        # Two criteria, mean rank: DL video packet delivery (maximise) and UL pose
        # deadline miss ratio (minimise), ties broken on pose. Selecting on pose alone
        # picks configurations that trade away video; selecting on the tail alone picks a
        # 60%-pose-miss cell at nSta=5. One OCwMin per (nSta, RA-RU) is used for every
        # metric, so all panels show the same configuration under one label.
        def mean_over_runs(dir_fn, fn):
            vals = []
            for run in RUNS:
                ps = read_ps(dir_fn(run))
                if ps is not None:
                    v = fn(ps)
                    if np.isfinite(v): vals.append(v)
            return np.mean(vals) if vals else np.nan

        best_ocw = {}
        for n in NSTA_VALUES:
            for r in nRaRus:
                cand = []
                for o in OCwMin:
                    f = lambda run, r=r, o=o, n=n: uora_dir(run, n, r, o)
                    dv = mean_over_runs(f, lambda s: pkt_deliv(s, "Vid_rx", "Vid_frames_gen"))
                    pl = mean_over_runs(f, lambda s: pooled_dmr(s, "Pose_gen", "Pose_ontime"))
                    if np.isfinite(dv) and np.isfinite(pl): cand.append((o, dv, pl))
                if not cand: continue
                c = pd.DataFrame(cand, columns=["ocw","deliv","pose"])
                c["rank"] = (c.deliv.rank(ascending=False) + c.pose.rank(ascending=True)) / 2
                best_ocw[(n, r)] = int(c.sort_values(["rank","pose"]).iloc[0].ocw)

        def run_dirs(label, n):
            if label in BASE_FN: return [BASE_FN[label](run, n) for run in RUNS]
            r = {ulabel(x): x for x in nRaRus}[label]
            o = best_ocw.get((n, r), OCwMin[0])
            return [uora_dir(run, n, r, o) for run in RUNS]

        # ---------------- aggregate ----------------
        def stats(a):
            """mean, SEM, and sample std (ddof=1) over runs. The bar chart uses std
    explicitly regardless of ERROR_KIND; line() below uses ERROR_KIND."""
            a = np.asarray(a, float); a = a[np.isfinite(a)]
            if a.size == 0: return np.nan, np.nan, np.nan
            mean = a.mean()
            std  = a.std(ddof=1) if a.size > 1 else 0.0
            sem  = std / np.sqrt(a.size)
            return mean, sem, std

        rows = []
        for label in ORDER:
            for n in NSTA_VALUES:
                tp_v = []                            # DL video throughput (Mbps), per run
                d_v999, d_a999, d_p999 = [], [], []  # worst-STA P99.9 delays (received pkts)
                m_vid, m_aud, m_pose = [], [], []    # packet deadline miss ratio  <-- primary
                e_vid, e_aud, e_pose = [], [], []    # packet loss ratio (drops only)
                f_vid = []                           # frame-level miss ratio (strict rule)
                for d in run_dirs(label, n):
                    t = read_tp(d)
                    if t is not None:
                        tp_v.append(t["DL_Video_Mbps"])
                    m_vid.append(vid_pkt_dmr(d))     # NaN unless the run emitted the histogram
                    s = read_ps(d)
                    if s is not None:
                        # Worst station, not the mean of per-STA percentiles: a per-STA
                        # mean understates the tail by ~22% at nSta=6. max is an
                        # extreme-value statistic, so the spread over seeds is still shown.
                        d_v999.append(s["Vid_p999_ms"].max())
                        d_a999.append(s["Aud_p999_ms"].max())
                        d_p999.append(s["Pose_p999_ms"].max())
                        m_aud.append(pooled_dmr(s,  "Aud_gen",  "Aud_ontime"))
                        m_pose.append(pooled_dmr(s, "Pose_gen", "Pose_ontime"))
                        e_vid.append(1.0 - pkt_deliv(s, "Vid_rx", "Vid_frames_gen"))
                        e_aud.append(pooled_plr(s,  "Aud_gen",  "Aud_rx"))
                        e_pose.append(pooled_plr(s, "Pose_gen", "Pose_rx"))
                        f_vid.append(frame_dmr(s))
                rec = {"label": label, "nSta": n}
                for k, arr in [("tp_vid",tp_v),
                               ("d_vid_p999",d_v999),("d_aud_p999",d_a999),("d_pose_p999",d_p999),
                               ("vid_dmr",m_vid),("aud_dmr",m_aud),("pose_dmr",m_pose),
                               ("vid_plr",e_vid),("aud_plr",e_aud),("pose_plr",e_pose),
                               ("vid_frame_dmr",f_vid)]:
                    mean, sem, std = stats(arr)
                    rec[k], rec[k+"_sem"], rec[k+"_std"] = mean, sem, std
                    rec[k+"_e"] = sem if ERROR_KIND == "sem" else std
                rows.append(rec)
        df = pd.DataFrame(rows)
        present = [l for l in ORDER if df[(df.label==l)]["tp_vid"].notna().any() or df[(df.label==l)]["pose_dmr"].notna().any()]
        print("schemes found:", present)
        print("UORA OCwMin selected per (nSta, RA-RU):", {k: v for k, v in sorted(best_ocw.items())})
        if df["vid_dmr"].isna().all():
            print("NOTE: no run emitted", VH, "-- the DL video deadline-miss panel will be empty.")

        # ---------------- plotting helpers ----------------
        def asym_err(mean, err):
            """Symmetric std/SEM -> [lower, upper] with the lower whisker clipped at zero:
    throughput, delay and ratios are all non-negative, so mean - std must not be
    drawn below the axis."""
            mean = np.asarray(mean, dtype=float)
            err  = np.asarray(err, dtype=float)
            lower = np.minimum(err, np.maximum(mean, 0.0))
            return np.vstack([lower, err])

        def line(ax, metric, ylab, title, deadline=None, ylim=None, dodge=0.0):
            for i, l in enumerate(present):
                d = df[df.label == l].sort_values("nSta")
                if d[metric].isna().all(): continue
                dx = (i - (len(present) - 1) / 2) * dodge
                ax.errorbar(d["nSta"] + dx, d[metric],
                            yerr=asym_err(d[metric], d[metric + "_e"]), label=l,
                            color=STYLE[l]["color"], marker=STYLE[l]["marker"],
                            capsize=2, elinewidth=0.6)
            if deadline is not None: ax.axhline(deadline, ls="--", color="k", lw=0.8, alpha=0.7)
            if ylim is not None: ax.set_ylim(*ylim)
            ax.set_xticks(NSTA_VALUES)
            if ylab: ax.set_ylabel(ylab)          # left-hand panel of each row only
            if title: ax.set_title(title)
            ax.grid(True, alpha=0.4)

        def bar(ax, metric, std_col, ylab, title, nsta_values=None):
            nsta_values = nsta_values if nsta_values is not None else NSTA_VALUES
            x = np.arange(len(nsta_values))
            n = len(present)
            width = 0.9 / max(n, 1)
            for i, l in enumerate(present):
                d = df[df.label == l].set_index("nSta").reindex(nsta_values)
                offset = (i - (n - 1) / 2) * width
                ax.bar(x + offset, d[metric], width=width,
                       yerr=asym_err(d[metric], d[std_col]),
                       label=l, color=STYLE[l]["color"], linewidth=0,
                       error_kw=dict(elinewidth=0.4, capsize=0))
            ax.set_xticks(x); ax.set_xticklabels(nsta_values)
            ax.set_xlabel("Number of headsets"); ax.set_ylabel(ylab); ax.set_title(title)
            ax.grid(True, axis="y", alpha=0.4)
            ax.margins(x=0.02)

        def split_yscale(ax, split=50.0, top=200.0, frac=0.70,
                         ticks_lo=(0, 10, 20, 30, 40, 50), ticks_hi=(100, 150, 200), fmt="{:g}"):
            """Piecewise-linear y axis: [0, split] gets `frac` of the panel height and
    [split, top] the remainder. Both segments are linear -- only their scales
    differ -- so this is neither a log nor a broken axis. The dotted line marks
    the change of scale."""
            def fwd(y):
                y = np.asarray(y, dtype=float)
                return np.where(y <= split, y / split * frac,
                                frac + (y - split) / (top - split) * (1.0 - frac))
            def inv(t):
                t = np.asarray(t, dtype=float)
                return np.where(t <= frac, t / frac * split,
                                split + (t - frac) / (1.0 - frac) * (top - split))
            ax.set_yscale("function", functions=(fwd, inv))
            ax.set_yticks(list(ticks_lo) + list(ticks_hi))
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: fmt.format(v)))
            ax.set_ylim(0, top)
            ax.axhline(split, color="0.5", lw=0.5, ls=":", alpha=0.8)

        def panel_labels(axes, loc=(0.035, 0.96), start="a", **kw):
            """(a), (b), (c), ... inside each panel in reading order, so the caption can
    refer to panels individually. Axes-fraction coordinates, so the piecewise
    ordinates do not affect placement."""
            style = dict(fontsize=8, va="top", ha="left")
            style.update(kw)
            for i, a in enumerate(np.asarray(axes).ravel()):
                a.text(loc[0], loc[1], f"({chr(ord(start) + i)})", transform=a.transAxes, **style)

        def panel_labels_below(axes, start="a", pad=2.0):
            """(a), (b), ... beneath each panel, in reading order."""
            for i, a in enumerate(np.asarray(axes).ravel()):
                a.set_xlabel(f"({chr(ord(start) + i)})", labelpad=pad)

        Path("fig/xr").mkdir(parents=True, exist_ok=True)

        # ===== Figure 1: DL video throughput, single column, error = std over runs =====
        fig, ax = plt.subplots(figsize=(COLWIDTH_IN, 2.5))
        bar(ax, "tp_vid", "tp_vid_std", "DL video throughput (Mbps)", "", nsta_values=BAR_NSTA)
        h, l = ax.get_legend_handles_labels()
        fig.legend(h, l, loc="upper center", ncol=5, bbox_to_anchor=(0.54, 1.1), frameon=False,
                   handlelength=1.1, columnspacing=0.8, handletextpad=0.4)
        fig.tight_layout()
        fig.savefig("fig/xr/xr_video_throughput_bar.png", dpi=300, bbox_inches="tight")
        fig.savefig("fig/xr/xr_video_throughput_bar.pdf", bbox_inches="tight")
        plt.show()

        # ===== Figure 2: P99.9 delay (top) + packet deadline miss ratio (bottom) =====
        # One y label per row (on the left-hand panel, which centres it on the row) and
        # one x label under the middle panel of the bottom row. Panels within a row share
        # a quantity but not a scale -- each has its own limits, declared in the caption.
        fig, ax = plt.subplots(2, 3, figsize=(TEXTWIDTH_IN, 4.2), sharex=True)

        # Top row: worst-STA P99.9 delay. Video and pose use a piecewise ordinate so the
        # region around the deadline is resolved while the far tail stays on the panel.
        line(ax[0][0], "d_vid_p999",  "P99.9 delay (ms)", "DL video",
             deadline=VIDEO_FRAME_MS, dodge=0.07)
        split_yscale(ax[0][0], split=50.0, top=200.0, frac=0.72)
        line(ax[0][1], "d_aud_p999",  "", "DL audio", deadline=AUDIO_DEADLINE_MS, dodge=0.07)
        line(ax[0][2], "d_pose_p999", "", "UL pose",  deadline=POSE_DEADLINE_MS, dodge=0.07)
        split_yscale(ax[0][2], split=50.0, top=500.0, frac=0.80,
                     ticks_lo=(0, 10, 20, 30, 40, 50), ticks_hi=(300, 500))

        # Bottom row: packet deadline miss ratio, same definition for all three flows but
        # an individual ordinate each. The limits are set so the budget region is
        # readable rather than so every point fits: curves that exceed the limit leave
        # the panel, which only happens where the flow has already failed the budget.
        line(ax[1][0], "vid_dmr",  "Packet deadline-miss ratio", "",
             deadline=DMR_BUDGET, ylim=(-0.02, 1.02), dodge=0.07)
        split_yscale(ax[1][0], split=0.2, top=1.0, frac=0.72, fmt="{:.2f}")
        ax[1][0].set_yticks([ 0.0, 0.05, 0.10, 0.15, 0.20, 1.0])
        ax[1][0].set_yticks([-0.02, 1.2], minor=True)
        #ax[1][0].yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}"))
        ax[1][0].grid(True, which="minor", axis="y", alpha=0.2, lw=0.3)
        #ticks_lo=(0, 0.05, 0.10, 0.15, 0.20,), ticks_hi=(0.2, 1.02)


        line(ax[1][1], "aud_dmr",  "", "", ylim=(-0.01, 0.010), dodge=0.07)
        ax[1][1].set_yticks([-0.1, 0, 0.1])
        ax[1][1].set_yticks([-0.05, 0.05], minor=True)
        ax[1][1].yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}"))
        ax[1][1].grid(True, which="minor", axis="y", alpha=0.2, lw=0.3)

        line(ax[1][2], "pose_dmr", "", "",
             deadline=DMR_BUDGET, ylim=(-0.02, 0.50), dodge=0.07)
        #ax[1][2].set_yticks([0, 0.02, 0.04, 0.06, 0.08, 0.10])
        #ax[1][2].yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}"))

        panel_labels_below(ax)
        fig.supxlabel("Number of headsets", fontsize=8, y=0.1)

        h, l = ax[0][0].get_legend_handles_labels()
        fig.legend(h, l, loc="upper center", ncol=9, bbox_to_anchor=(0.5, 1.06), frameon=False,
                   handlelength=1.3, columnspacing=1.0, handletextpad=0.4)
        fig.tight_layout(w_pad=0.4, h_pad=0.9, rect=(0, 0.055, 1, 1))
        fig.savefig("fig/xr/xr_p999_and_dmr.png", dpi=300, bbox_inches="tight")
        fig.savefig("fig/xr/xr_p999_and_dmr.pdf", bbox_inches="tight")
        plt.show()
        _done("xr_results")
    except Exception as _err:
        _done("xr_results", _err)

# ---- xr_cmab_tuning: CMAB hyper-parameter sweep ----
if _run("xr_cmab_tuning"):
    try:
        # %% imports
        import re
        from pathlib import Path
        import matplotlib.pyplot as plt
        import numpy as np
        import pandas as pd

        plt.rcParams.update({
          "font.size": 14, "axes.labelsize": 14, "xtick.labelsize": 12,
          "ytick.labelsize": 12, "legend.fontsize": 12,
        })

        # %% config
        # XR CMAB hyperparameter sweep. Unlike IIoT there is no pMean; the only load
        # axis is the headset count (nSta). Each run dir holds throughput.out and
        # per_sta_stats.out (no type2_packets.out). Selection is on deadline compliance:
        # DL video is frame-level (a frame is on-time only if all its packets arrive
        # within VIDEO_BOUND_MS), pose/audio are per-packet.
        ROOT            = Path("xr_data/cmab")
        VIDEO_BOUND_MS  = 50   # DL video per-frame bound (Wi-Fi Alliance VR-gaming p99.9)
        POSE_DEADLINE   = 10   # UL pose per-packet bound
        AUDIO_DEADLINE  = 30   # DL audio per-packet bound
        # Load region the winner is scored over. nSta<=4 is uncongested (all variants
        # ~0 loss) and nSta>=14 is ~3x over capacity (all variants collapse); the HP
        # choice only discriminates in between, so score over the contested mid-load band.
        SCORE_NSTA      = [6, 8, 10, 12]
        SAVE_FIGS       = False
        FIG_DIR         = Path("./fig/xr/cmab_hp_sweep_figs")

        ALGOS    = ["CUCB", "EpsilonGreedy", "EXP3M", "ThompsonSampling"]
        HP_GLYPH = {"CUCB": "c", "EpsilonGreedy": "ε", "EXP3M": "γ"}
        ALGO_DEFAULT = {"CUCB": 1.41421, "EpsilonGreedy": 0.1, "EXP3M": 0.1}

        METRIC_LABELS = {
          "vid_frame_loss": "DL video frame deadline loss",
          "pose_loss":      "UL pose deadline loss",
          "aud_loss":       "DL audio deadline loss",
          "vid_tput":       "DL video throughput (Mbps)",
          "vid_p99_ms":     "DL video P99 delay (ms)",
          "pose_p99_ms":    "UL pose P99 delay (ms)",
        }
        # lower-is-better metrics (losses and delays); the rest are higher-is-better
        LOSS_METRICS  = {"vid_frame_loss", "pose_loss", "aud_loss"}
        DELAY_METRICS = {"vid_p99_ms", "pose_p99_ms"}
        # primary/secondary objective for picking the winner (both lower-is-better)
        PRIMARY, SECONDARY = "vid_frame_loss", "pose_loss"

        RE_ALGO_DIR = re.compile(
          r"^(?P<algo>CUCB|EpsilonGreedy|EXP3M|ThompsonSampling)"
          r"_(?P<reward>Binary|FairnessWeighted)"
          r"(?:_(?P<hp>[ceg])(?P<val>[\d.]+))?$")
        RE_RUN_DIR = re.compile(r"^(?P<run>\d+)_run-(?P<nSta>\d+)_sta$")

        # %% parsers / loaders
        def parse_dirs(algo_dir, run_dir):
          m1, m2 = RE_ALGO_DIR.match(algo_dir.name), RE_RUN_DIR.match(run_dir.name)
          if not (m1 and m2):
              return None
          return {
              "algorithm": m1["algo"], "rewardType": m1["reward"],
              "hp_value":  float(m1["val"]) if m1["hp"] else np.nan,
              "run": int(m2["run"]), "nSta": int(m2["nSta"]),
          }

        def _survivor_loss(gen, ontime):
          """Deadline loss over *generated* packets (drops + late), survivorship-proof."""
          g = float(np.nansum(gen))
          return max(0.0, 1.0 - float(np.nansum(ontime)) / g) if g > 0 else np.nan

        def load_run(run_dir):
          m = {k: np.nan for k in METRIC_LABELS}

          # aggregate DL video throughput (Mbps) from throughput.out
          if (p := run_dir / "throughput.out").is_file():
              try:
                  f = pd.read_csv(p, sep="\t")
                  m["vid_tput"] = float(f["DL_Video_Mbps"].iloc[0])
              except Exception:
                  pass

          # per-STA QoS from per_sta_stats.out
          if (p := run_dir / "per_sta_stats.out").is_file():
              try:
                  s = pd.read_csv(p, sep="\t")
                  # deadline compliance from counts (aggregated over STAs, not averaged
                  # per-STA fractions) so a starved STA is not over/under-weighted
                  m["vid_frame_loss"] = _survivor_loss(s["Vid_frames_gen"], s["Vid_frames_ontime"])
                  m["pose_loss"]      = _survivor_loss(s["Pose_gen"],       s["Pose_ontime"])
                  m["aud_loss"]       = _survivor_loss(s["Aud_gen"],        s["Aud_ontime"])
                  # tail delays: mean across STAs of the per-STA percentile (no raw
                  # packet dump is written, so this is a per-STA-p99 average, not a
                  # global p99 -- adequate for ranking variants, not for absolute claims)
                  m["vid_p99_ms"]  = float(s["Vid_p99_ms"].mean())
                  m["pose_p99_ms"] = float(s["Pose_p99_ms"].mean())
              except Exception:
                  pass

          return m

        # %% walk the tree
        rows = []
        for algo_dir in sorted(ROOT.iterdir()):
          if not algo_dir.is_dir():
              continue
          for run_dir in sorted(algo_dir.iterdir()):
              if not run_dir.is_dir():
                  continue
              meta = parse_dirs(algo_dir, run_dir)
              if meta is None:
                  continue
              meta.update(load_run(run_dir))
              rows.append(meta)

        df = pd.DataFrame(rows)
        df = df[df["algorithm"].isin(ALGOS)].reset_index(drop=True)
        print(f"loaded {len(df)} runs; nSta: {sorted(df['nSta'].unique())}; "
              f"variants: {df.groupby(['algorithm','rewardType','hp_value']).ngroups}")

        # %% aggregation helper
        def agg_mean_sem(sub, group_cols, metric):
          g   = sub.groupby(group_cols)[metric]
          out = g.agg(["mean", "std", "count"]).reset_index()
          out["sem"] = out["std"] / np.sqrt(out["count"].clip(lower=1))
          return out

        # %% variant label + winner selection
        def hp_label(row):
          algo = row["algorithm"]
          if algo == "ThompsonSampling" or pd.isna(row["hp_value"]):
              return f"{algo}/{row['rewardType']}"
          return f"{algo}({HP_GLYPH[algo]}={row['hp_value']:g})/{row['rewardType']}"

        def select_best(df, primary=PRIMARY, secondary=SECONDARY, nsta=SCORE_NSTA):
          """Rank every (algorithm, rewardType, hp) variant by mean deadline loss over
  the contested load band. Score = per-variant mean over runs and over nsta of
  the primary metric; ties broken by the secondary metric."""
          band = df[df["nSta"].isin(nsta)]
          keys = ["algorithm", "rewardType", "hp_value"]
          score = (band.groupby(keys, dropna=False)[[primary, secondary]]
                        .mean().reset_index()
                        .sort_values([primary, secondary]).reset_index(drop=True))
          score["variant"] = score.apply(hp_label, axis=1)
          return score

        ranked = select_best(df)
        print(f"\n=== CMAB variant ranking over nSta={SCORE_NSTA} "
              f"(by {PRIMARY}, tie {SECONDARY}; lower is better) ===")
        with pd.option_context("display.max_rows", None, "display.width", 120):
          print(ranked[["variant", PRIMARY, SECONDARY]].to_string(
                index=False, float_format=lambda x: f"{x:.4f}"))
        best = ranked.iloc[0]
        print(f"\nBEST XR CMAB variant: {best['variant']}  "
              f"({PRIMARY}={best[PRIMARY]:.4f}, {SECONDARY}={best[SECONDARY]:.4f})")
        # also the winner per reward family (Binary vs FairnessWeighted can reverse)
        for rew in sorted(df["rewardType"].unique()):
          r = ranked[ranked["rewardType"] == rew].iloc[0]
          print(f"  best {rew:>16}: {r['variant']}  "
                f"({PRIMARY}={r[PRIMARY]:.4f}, {SECONDARY}={r[SECONDARY]:.4f})")

        # %% plot -- one grid per metric (reward rows x algo cols), curves = HP values
        rewards = sorted(df["rewardType"].dropna().unique())
        cmap    = plt.get_cmap("viridis")
        for metric, ylabel in METRIC_LABELS.items():
          fig, axes = plt.subplots(
              len(rewards), len(ALGOS),
              figsize=(4 * len(ALGOS), 3.2 * len(rewards)),
              sharex=True, sharey="row", squeeze=False)
          for r, reward in enumerate(rewards):
              for c, algo in enumerate(ALGOS):
                  ax  = axes[r][c]
                  sub = df[(df["algorithm"] == algo) & (df["rewardType"] == reward)]
                  if sub.empty or sub[metric].dropna().empty:
                      ax.text(0.5, 0.5, "no data", ha="center", va="center",
                              transform=ax.transAxes)
                      if r == 0: ax.set_title(algo)
                      continue
                  hp_vals = sorted(sub["hp_value"].dropna().unique())
                  if hp_vals:
                      default = ALGO_DEFAULT.get(algo)
                      for i, hp in enumerate(hp_vals):
                          g = agg_mean_sem(sub[sub["hp_value"] == hp], ["nSta"], metric).sort_values("nSta")
                          if g.empty: continue
                          is_default = default is not None and np.isclose(hp, default)
                          ax.errorbar(g["nSta"], g["mean"], yerr=g["sem"], marker="o", capsize=2,
                                      color=cmap(i / max(1, len(hp_vals) - 1)),
                                      lw=2.2 if is_default else 1.2,
                                      label=f"{HP_GLYPH[algo]}={hp:g}" + ("  (default)" if is_default else ""))
                  else:  # ThompsonSampling: no hyperparameter
                      g = agg_mean_sem(sub, ["nSta"], metric).sort_values("nSta")
                      if not g.empty:
                          ax.errorbar(g["nSta"], g["mean"], yerr=g["sem"], marker="o",
                                      capsize=2, color="tab:red", lw=2.2, label=algo)
                  if metric == "vid_p99_ms":  ax.axhline(VIDEO_BOUND_MS, ls="--", color="k", lw=1, alpha=0.6)
                  if metric == "pose_p99_ms": ax.axhline(POSE_DEADLINE,  ls="--", color="k", lw=1, alpha=0.6)
                  if metric in LOSS_METRICS:  ax.set_ylim(-0.02, 1.05)
                  if r == 0: ax.set_title(algo)
                  if c == 0: ax.set_ylabel(f"{reward}\n{ylabel}")
                  ax.grid(True, alpha=0.3); ax.legend(loc="best", fontsize=9)
          fig.suptitle(f"{ylabel} vs. headsets")
          fig.supxlabel("Number of XR headsets", y=0.02)
          if SAVE_FIGS:
              FIG_DIR.mkdir(parents=True, exist_ok=True)
              fig.savefig(FIG_DIR / f"{metric}.png", dpi=300, bbox_inches="tight")
          plt.show()
        _done("xr_cmab_tuning")
    except Exception as _err:
        _done("xr_cmab_tuning", _err)

# ---- xr_ari_cmab: Access request interval selection, CMAB ----
if _run("xr_ari_cmab"):
    try:
        # %% imports
        import re
        from pathlib import Path
        import numpy as np, pandas as pd
        import matplotlib.pyplot as plt
        from matplotlib.colors import LinearSegmentedColormap
        from scipy import stats as st

        plt.rcParams.update({
            "font.size": 8, "axes.labelsize": 8, "axes.titlesize": 8,
            "xtick.labelsize": 6.5, "ytick.labelsize": 6.5, "legend.fontsize": 6,
            "lines.linewidth": 1.6, "lines.markersize": 3.5,
            "axes.linewidth": 0.6, "grid.linewidth": 0.4,
            "pdf.fonttype": 42, "ps.fonttype": 42,
        })
        TEXTWIDTH_IN = 7.16

        # %% config
        # CMAB ARI sweep: xr_data_ari/cmab/ari_<us>/<algo>_<reward>[_<hp>]/<run>_run-<n>_sta
        ROOT = Path("xr_data_ari_dlfirst/cmab")
        VIDEO_BOUND, POSE_BOUND = 50.0, 10.0
        VIDEO_PER_HEADSET_MBPS  = 100       # offered DL video load per headset
        VIDEO_PKTS_PER_FRAME    = 96        # a frame is on-time only if all 96 arrive in time
        LOSS_BUDGET = 0.05                  # deadline-loss budget for the feasibility check
        ALPHA       = 0.05                  # significance level for the ARI comparisons
        LOSS_FLOOR  = 1e-6                  # log axes drop exact zeros; clip the loss series
        SHOW_FIGS   = True                 # True = inline too (8 metrics x 8 nSta = 64 figures)
        CHOSEN      = ("CUCB", "FairnessWeighted", 2.5)   # winner from the HP sweep

        ALGOS   = ["CUCB", "EXP3M", "EpsilonGreedy", "ThompsonSampling"]   # panel columns
        REWARDS = ["FairnessWeighted", "Binary"]                           # panel rows
        # one hue per algorithm; validated with the dataviz validator (all checks pass)
        ALGO_COLOR = {"CUCB": "#2a78d6", "EXP3M": "#eb6834",
                      "EpsilonGreedy": "#1baf7a", "ThompsonSampling": "#4a3aa7"}
        ALGO_SHORT = {"CUCB": "CUCB", "EXP3M": "EXP3M",
                      "EpsilonGreedy": "$\\epsilon$-greedy", "ThompsonSampling": "Thompson"}
        HP_GLYPH   = {"CUCB": "c", "EXP3M": "$\\gamma$",
                      "EpsilonGreedy": "$\\epsilon$", "ThompsonSampling": None}

        RE_ARI = re.compile(r"^ari_(?P<ari>\d+)$")
        RE_VAR = re.compile(r"^(?P<algo>CUCB|EpsilonGreedy|EXP3M|ThompsonSampling)"
                            r"_(?P<rew>Binary|FairnessWeighted)(?:_(?P<hp>[ceg])(?P<val>[\d.]+))?$")
        RE_RUN = re.compile(r"^(?P<run>\d+)_run-(?P<nSta>\d+)_sta$")

        def surv(gen, ontime):
            """Deadline loss over *generated* packets (drops + late), survivorship-proof."""
            g = float(np.nansum(gen))
            return max(0.0, 1.0 - float(np.nansum(ontime))/g) if g > 0 else np.nan

        def variant_label(algo, hp):
            if algo == "ThompsonSampling" or pd.isna(hp): return algo
            return f"{algo}({HP_GLYPH[algo]}={hp:g})"

        DECOMP_KEYS = ["pose_delivered","pose_drop_loss","pose_late_loss",
                       "aud_drop_loss","aud_late_loss","vid_pkt_delivered"]

        # %% load
        rows = []
        for ad in sorted(ROOT.iterdir()):
            ma = RE_ARI.match(ad.name)
            if not (ad.is_dir() and ma): continue
            for vd in sorted(ad.iterdir()):
                mv = RE_VAR.match(vd.name)
                if not (vd.is_dir() and mv): continue
                for rd in sorted(vd.iterdir()):
                    mr = RE_RUN.match(rd.name)
                    if not (rd.is_dir() and mr): continue
                    r = dict(ari=int(ma["ari"]), algorithm=mv["algo"], rewardType=mv["rew"],
                             hp=float(mv["val"]) if mv["hp"] else np.nan,
                             run=int(mr["run"]), nSta=int(mr["nSta"]))
                    try:
                        r["vid_tput"] = float(pd.read_csv(rd/"throughput.out", sep="\t")["DL_Video_Mbps"].iloc[0])
                    except Exception:
                        r["vid_tput"] = np.nan
                    try:
                        s = pd.read_csv(rd/"per_sta_stats.out", sep="\t")
                        r["vid_frame_loss"] = surv(s["Vid_frames_gen"], s["Vid_frames_ontime"])
                        r["pose_loss"]      = surv(s["Pose_gen"], s["Pose_ontime"])
                        r["aud_loss"]       = surv(s["Aud_gen"], s["Aud_ontime"])
                        r["vid_p999_ms"]    = float(s["Vid_p999_ms"].mean())
                        r["pose_p999_ms"]   = float(s["Pose_p999_ms"].mean())

                        # --- deadline loss decomposed: never-arrived vs arrived-late ---
                        # Two schemes with equal total loss can fail completely differently:
                        # a starving scheduler drops packets (and its delay percentiles then
                        # only describe the subset it chose to serve), while a loaded one
                        # delivers everything a little late. Total loss alone hides this.
                        pg, prx, pon = (float(s["Pose_gen"].sum()), float(s["Pose_rx"].sum()),
                                        float(s["Pose_ontime"].sum()))
                        r["pose_delivered"] = prx/pg       if pg > 0 else np.nan  # arrived at all
                        r["pose_drop_loss"] = 1.0 - prx/pg if pg > 0 else np.nan  # never arrived
                        r["pose_late_loss"] = (prx-pon)/pg if pg > 0 else np.nan  # arrived, too late
                        ag, arx, aon = (float(s["Aud_gen"].sum()), float(s["Aud_rx"].sum()),
                                        float(s["Aud_ontime"].sum()))
                        r["aud_drop_loss"] = 1.0 - arx/ag  if ag > 0 else np.nan
                        r["aud_late_loss"] = (arx-aon)/ag  if ag > 0 else np.nan
                        # video is frame-level and per_sta_stats has no "frames received"
                        # column, so use packet delivery: a frame needs all 96 packets.
                        vfg, vrx = float(s["Vid_frames_gen"].sum()), float(s["Vid_rx"].sum())
                        r["vid_pkt_delivered"] = vrx/(vfg*VIDEO_PKTS_PER_FRAME) if vfg > 0 else np.nan
                    except Exception:
                        for k in ["vid_frame_loss","pose_loss","aud_loss",
                                  "vid_p999_ms","pose_p999_ms"] + DECOMP_KEYS:
                            r[k] = np.nan
                    rows.append(r)

        df       = pd.DataFrame(rows)
        NSTA_ALL = sorted(df.nSta.unique())
        ARI_ALL  = sorted(df.ari.unique())
        print(f"loaded {len(df)} runs; ari={ARI_ALL}; nSta={NSTA_ALL}; "
              f"variants={df.groupby(['algorithm','rewardType','hp'], dropna=False).ngroups}")

        def ramp(hex_hue, n):
            """Light->dark ramp of one hue: the hyperparameter is a sequential quantity."""
            cm = LinearSegmentedColormap.from_list("r", ["#cfd8e3", hex_hue, "#12233a"])
            return [cm(x) for x in (np.linspace(0.25, 0.92, n) if n > 1 else [0.6])]

        outdir = Path("fig/xr/ari_cmab"); outdir.mkdir(parents=True, exist_ok=True)

        METRICS = [("vid_tput",          "DL video throughput (Mbps)",    None,        "linear"),
                   ("vid_frame_loss",    "DL video frame deadline loss",  None,        "linear"),
                   ("vid_pkt_delivered", "DL video packet delivery rate", None,        "linear"),
                   ("pose_loss",         "UL pose deadline loss (total)", None,        "log"),
                   ("pose_drop_loss",    "UL pose loss: never delivered", None,        "log"),
                   ("pose_late_loss",    "UL pose loss: delivered late",  None,        "log"),
                   ("vid_p999_ms",       "DL video P99.9 delay (ms)",     VIDEO_BOUND, "log"),
                   ("pose_p999_ms",      "UL pose P99.9 delay (ms)",      POSE_BOUND,  "log")]
        LOSS_METRICS = {"pose_loss", "pose_drop_loss", "pose_late_loss"}

        # Fixed y-limits per metric over the WHOLE dataset, so the eight figures of a
        # given metric are directly comparable to one another.
        YLIM = {}
        for metric, _, bound, yscale in METRICS:
            g = (df.groupby(["nSta","ari","algorithm","rewardType","hp"], dropna=False)[metric]
                   .mean()).replace([np.inf,-np.inf], np.nan).dropna()
            if metric in LOSS_METRICS: g = g.clip(lower=LOSS_FLOOR)
            if g.empty: YLIM[metric] = None; continue
            if yscale == "log":
                lo, hi = max(g[g > 0].min()*0.7, LOSS_FLOOR*0.7), g.max()*1.4
                if bound is not None: lo, hi = min(lo, bound*0.7), max(hi, bound*1.4)
            else:
                lo, hi = 0, g.max()*1.08
            YLIM[metric] = (lo, hi)

        # %% figures: 8 metrics x each headset count (2 reward rows x 4 algorithm cols)
        for n in NSTA_ALL:
            dn = df[df.nSta == n]
            for metric, ylab, bound, yscale in METRICS:
                fig, axes = plt.subplots(len(REWARDS), len(ALGOS),
                                         figsize=(TEXTWIDTH_IN, 3.9), sharex=True, sharey=True)
                for i, rw in enumerate(REWARDS):
                    for j, a in enumerate(ALGOS):
                        ax  = axes[i][j]
                        ax.axvspan(96, 1400, color="#000000", alpha=0.045, lw=0, zorder=0)
                        sub = dn[(dn.algorithm == a) & (dn.rewardType == rw)]
                        hps = sorted(sub.hp.dropna().unique())
                        cols = ramp(ALGO_COLOR[a], max(len(hps), 1))
                        if hps:
                            for k, hp in enumerate(hps):
                                g = sub[np.isclose(sub.hp, hp)].groupby("ari")[metric].mean().sort_index()
                                if g.empty or g.isna().all(): continue
                                if metric in LOSS_METRICS: g = g.clip(lower=LOSS_FLOOR)
                                ax.plot(g.index, g.values, color=cols[k], marker="o",
                                        markeredgecolor="white", markeredgewidth=0.4, zorder=3,
                                        label=f"{HP_GLYPH[a]}={hp:g}")
                        else:                       # Thompson sampling: no hyperparameter
                            g = sub.groupby("ari")[metric].mean().sort_index()
                            if not g.empty:
                                if metric in LOSS_METRICS: g = g.clip(lower=LOSS_FLOOR)
                                ax.plot(g.index, g.values, color=cols[0], marker="o",
                                        markeredgecolor="white", markeredgewidth=0.4,
                                        zorder=3, label="—")
                        if bound is not None:
                            ax.axhline(bound, ls=":", color="#52514e", lw=0.9, zorder=2)
                        ax.set_xscale("log", base=2); ax.set_yscale(yscale)
                        ax.set_xticks([16, 64, 256, 1024]); ax.set_xticklabels([16, 64, 256, 1024])
                        if YLIM[metric] is not None: ax.set_ylim(*YLIM[metric])
                        ax.grid(True, alpha=0.3, lw=0.4); ax.set_axisbelow(True)
                        if i == 0: ax.set_title(ALGO_SHORT[a], fontsize=7)
                        if j == 0:
                            ax.set_ylabel(("Fairness-weighted" if rw == "FairnessWeighted" else "Binary")
                                          + f"\n{ylab}", fontsize=7)
                        ax.legend(loc="best", frameon=False, handlelength=1.2,
                                  borderpad=0.2, labelspacing=0.25)
                for ax in axes[-1]: ax.set_xlabel("ARI ($\\mu$s)")
                note = "  (values clipped at %g for the log axis)" % LOSS_FLOOR if metric in LOSS_METRICS else ""
                fig.suptitle(f"{ylab} — CMAB, {n} headset{'s' if n != 1 else ''}{note}",
                             fontsize=8.5, y=1.03)
                fig.tight_layout()
                fig.savefig(outdir/f"xr_ari_dlfirst_cmab_{metric}_nsta{n}.pdf", bbox_inches="tight")
                if SHOW_FIGS: plt.show()
                else: plt.close(fig)
        print(f"wrote {len(NSTA_ALL)*len(METRICS)} per-headset figures to {outdir}")

        # %% capacity figure: DL video throughput vs headsets, ARI as the ramp
        ch_mask = ((df.algorithm == CHOSEN[0]) & (df.rewardType == CHOSEN[1])
                   & (np.isclose(df.hp, CHOSEN[2]) if not pd.isna(CHOSEN[2]) else df.hp.isna()))
        chosen  = df[ch_mask]
        fig, ax = plt.subplots(figsize=(3.5, 2.5))
        cols = ramp(ALGO_COLOR[CHOSEN[0]], len(ARI_ALL))
        for k, a in enumerate(ARI_ALL):
            g = chosen[chosen.ari == a].groupby("nSta")["vid_tput"].agg(["mean", "std"])
            if g.empty: continue
            ax.errorbar(g.index, g["mean"],
                        yerr=np.vstack([np.minimum(g["std"].values, g["mean"].values),
                                        g["std"].values]),      # lower whisker clipped at 0
                        color=cols[k], marker="o", capsize=1.5, elinewidth=0.5,
                        markeredgecolor="white", markeredgewidth=0.4, zorder=3, label=f"ARI={a}")
        ax.plot(NSTA_ALL, [VIDEO_PER_HEADSET_MBPS*x for x in NSTA_ALL],
                ls=":", color="#52514e", lw=0.9, zorder=2, label="offered")
        ax.set_xticks(NSTA_ALL); ax.grid(True, alpha=0.3, lw=0.4); ax.set_axisbelow(True)
        ax.set_xlabel("Number of headsets"); ax.set_ylabel("DL video throughput (Mbps)", fontsize=7.5)
        ax.legend(loc="best", frameon=False, handlelength=1.2, borderpad=0.2,
                  labelspacing=0.25, fontsize=5.5)
        fig.suptitle(f"DL video throughput — CMAB {variant_label(CHOSEN[0], CHOSEN[2])}/{CHOSEN[1]}",
                     fontsize=8.5, y=1.02)
        fig.tight_layout()
        fig.savefig(outdir/"xr_ari_dlfirst_cmab_tput_vs_nsta.pdf", bbox_inches="tight")
        plt.show()

        # %% ===================== ARI selection =========================================
        # Raw metrics only -- no composite score: summing/maxing frame loss with pose loss
        # lets one saturated metric decide the ranking and hides any tradeoff.
        var = (df.groupby(["nSta","ari","algorithm","rewardType","hp"], dropna=False)
                 [["vid_frame_loss","pose_loss","pose_drop_loss","pose_late_loss",
                   "pose_delivered","vid_tput","pose_p999_ms"]].mean().reset_index())
        var["variant"] = var.apply(lambda r: f"{variant_label(r.algorithm, r.hp)}/{r.rewardType}", axis=1)

        # --- 1. feasibility: how many of the 26 variants meet BOTH budgets? ------------
        print(f"\n=== 1) variants meeting BOTH budgets (frame<= {LOSS_BUDGET} and pose<= {LOSS_BUDGET}) ===")
        feas = (var.assign(ok=(var.vid_frame_loss <= LOSS_BUDGET) & (var.pose_loss <= LOSS_BUDGET))
                   .groupby(["nSta","ari"])["ok"].sum().reset_index())
        print(feas.pivot(index="nSta", columns="ari", values="ok").to_string())
        print("  (out of 26 variants; 0 = that load is unservable at that ARI)")

        # --- 2. is the loss starvation or lateness? -----------------------------------
        # ~1.0 => the scheme is dropping packets it never even attempted, so its delay
        # percentiles describe only the traffic it chose to carry. ~0.0 => it delivers
        # everything and some arrives late. Same total loss, opposite meaning.
        var["drop_share"] = var["pose_drop_loss"] / var["pose_loss"].replace(0, np.nan)
        print("\n=== 2) share of UL pose loss that is DROPS (~1.0 starvation, ~0.0 lateness) ===")
        print(var[var.nSta >= 5].pivot_table(index="variant", columns="nSta",
                                             values="drop_share", aggfunc="mean")
                .to_string(float_format=lambda x: f"{x:.3f}"))
        print("\n=== 2b) % of generated UL pose delivered ON TIME (= 100 - deadline loss) ===")
        var["pct_ontime"] = 100*(1 - var["pose_loss"])
        print(var[var.ari >= 128].pivot_table(index="variant", columns="nSta",
                                              values="pct_ontime", aggfunc="mean")
                .to_string(float_format=lambda x: f"{x:.2f}"))

        # --- 3. raw values for the chosen variant -------------------------------------
        print(f"\n=== 3) chosen variant {variant_label(CHOSEN[0], CHOSEN[2])}/{CHOSEN[1]}: raw per (nSta, ari) ===")
        chv = chosen.groupby(["nSta","ari"])[["vid_frame_loss","pose_loss","pose_drop_loss",
                                              "pose_late_loss","pose_delivered","aud_loss",
                                              "vid_tput","vid_p999_ms","pose_p999_ms"]].mean().reset_index()
        print(chv.to_string(index=False, float_format=lambda x: f"{x:.5f}"))

        # --- 4. per-nSta nominal best ARI ----------------------------------------------
        print("\n=== 4) nominal best ARI per headset count (chosen variant) ===")
        for n in NSTA_ALL:
            s  = chv[chv.nSta == n].sort_values(["vid_frame_loss","pose_loss"]).iloc[0]
            bp = chv[chv.nSta == n].sort_values(["pose_loss","vid_frame_loss"]).iloc[0]
            print(f"  nSta={n}: best-video ARI={int(s.ari):5d} (frame {s.vid_frame_loss:.5f}, "
                  f"pose {s.pose_loss:.5f}) | best-pose ARI={int(bp.ari):5d} "
                  f"(pose {bp.pose_loss:.5f}, frame {bp.vid_frame_loss:.5f})")

        # --- 5. is that "winner" real? pairwise tests across the passing ARI values ----
        # Without this, sort().first() always yields a winner whether or not one exists.
        PASSING = [a for a in ARI_ALL if a >= 128]
        print(f"\n=== 5) significance of ARI differences among {PASSING} (chosen variant, frame loss) ===")
        for n in NSTA_ALL:
            print(f"\n nSta={n}")
            samples = {}
            for a in PASSING:
                v = chosen[(chosen.nSta == n) & (chosen.ari == a)]["vid_frame_loss"].dropna().values
                if len(v):
                    samples[a] = v
                    print(f"   ARI={a:5d}  mean={v.mean():.5f}  sd={v.std(ddof=1):.5f}  "
                          f"sem={v.std(ddof=1)/np.sqrt(len(v)):.5f}  n={len(v)}")
            sig = []
            for i, x in enumerate(PASSING):
                for y in PASSING[i+1:]:
                    if x not in samples or y not in samples: continue
                    vx, vy = samples[x], samples[y]
                    if len(vx) < 2 or len(vy) < 2: continue
                    p = st.ttest_ind(vx, vy, equal_var=False).pvalue
                    if p < ALPHA: sig.append((x, y, p))
                    print(f"   {x} vs {y}: diff={vx.mean()-vy.mean():+.5f}  p={p:.3f}  "
                          f"{'SIG' if p < ALPHA else 'n.s.'}")
            print("   -> " + ("no ARI is significantly better; the nominal winner is a rank artifact"
                              if not sig else f"{len(sig)} significant pair(s)"))

        # --- 6. the claim that actually survives: the ARI>=128 threshold, all variants --
        print("\n=== 6) ARI<=64 vs ARI>=128 per variant (mean frame loss, nSta 2..5) ===")
        sub = var[var.nSta.isin([2,3,4,5])]
        lo  = sub[sub.ari <= 64].groupby("variant")["vid_frame_loss"].mean()
        hi  = sub[sub.ari >= 128].groupby("variant")["vid_frame_loss"].mean()
        cmp = pd.DataFrame({"ARI<=64": lo, "ARI>=128": hi})
        cmp["ratio"] = cmp["ARI<=64"] / cmp["ARI>=128"].replace(0, np.nan)
        print(cmp.sort_values("ratio").to_string(float_format=lambda x: f"{x:.4f}"))

        # --- 7. cost of fixing one ARI for everything ----------------------------------
        FIXED_ARI = 256
        print(f"\n=== 7) penalty of forcing ARI={FIXED_ARI} vs per-cell best (all variants, nSta<=5) ===")
        s5 = var[var.nSta <= 5]
        bestcell = s5.sort_values(["vid_frame_loss","pose_loss"]).groupby(["variant","nSta"]).first()
        gap = (s5[s5.ari == FIXED_ARI].set_index(["variant","nSta"])["vid_frame_loss"]
               - bestcell["vid_frame_loss"])
        print(f"  max penalty={gap.max():.5f}   mean penalty={gap.mean():.5f}   "
              f"over {len(gap)} (variant, nSta) cells")
        _done("xr_ari_cmab")
    except Exception as _err:
        _done("xr_ari_cmab", _err)

# ---- xr_ari_uora: Access request interval selection, UORA ----
if _run("xr_ari_uora"):
    try:
        # %% imports
        import re
        from pathlib import Path
        import numpy as np, pandas as pd
        import matplotlib.pyplot as plt
        from matplotlib.colors import LinearSegmentedColormap
        from scipy import stats as st

        plt.rcParams.update({
            "font.size": 8, "axes.labelsize": 8, "axes.titlesize": 8,
            "xtick.labelsize": 6.5, "ytick.labelsize": 6.5, "legend.fontsize": 6,
            "lines.linewidth": 1.6, "lines.markersize": 3.5,
            "axes.linewidth": 0.6, "grid.linewidth": 0.4,
            "pdf.fonttype": 42, "ps.fonttype": 42,
        })
        TEXTWIDTH_IN = 7.16

        # %% config
        # UORA ARI sweep: xr_data_ari/uora/ari_<us>/ocwMin_<o>/<run>_run-<n>_sta-<r>_rarus
        ROOT = Path("xr_data_ari_dlfirst/uora")
        VIDEO_BOUND, POSE_BOUND = 50.0, 10.0
        VIDEO_PER_HEADSET_MBPS  = 100       # offered DL video load per headset
        VIDEO_PKTS_PER_FRAME    = 96        # a frame is on-time only if all 96 arrive in time
        LOSS_BUDGET = 0.05                  # deadline-loss budget for the feasibility check
        ALPHA       = 0.05                  # significance level for the ARI comparisons
        LOSS_FLOOR  = 1e-6                  # log axes drop exact zeros; clip the loss series
        SHOW_FIGS   = True                 # True = inline too (8 metrics x 8 nSta = 64 figures)

        NRARUS = [0, 1, 2, 3, 4]            # panels  (0 = SA-OFDMA, no random access)
        OCWMIN = [1, 3, 7, 15, 31, 63]      # light->dark ramp within each panel
        # one hue per nRaRus panel; validated with the dataviz validator (all checks pass)
        RARU_COLOR = {0: "#2a78d6", 1: "#eb6834", 2: "#1baf7a", 3: "#4a3aa7", 4: "#eda100"}
        def raru_label(r):
            return "SA OFDMA (0 RA RU)" if r == 0 else (f"{r} RA RU" if r == 1 else f"{r} RA RUs")

        RE_ARI = re.compile(r"^ari_(?P<ari>\d+)$")
        RE_OCW = re.compile(r"^ocwMin_(?P<ocw>\d+)$")
        RE_RUN = re.compile(r"^(?P<run>\d+)_run-(?P<nSta>\d+)_sta-(?P<raru>\d+)_rarus$")

        def surv(gen, ontime):
            """Deadline loss over *generated* packets (drops + late), survivorship-proof."""
            g = float(np.nansum(gen))
            return max(0.0, 1.0 - float(np.nansum(ontime))/g) if g > 0 else np.nan

        DECOMP_KEYS = ["pose_delivered","pose_drop_loss","pose_late_loss",
                       "aud_drop_loss","aud_late_loss","vid_pkt_delivered"]

        # %% load
        rows = []
        for ad in sorted(ROOT.iterdir()):
            ma = RE_ARI.match(ad.name)
            if not (ad.is_dir() and ma): continue
            for od in sorted(ad.iterdir()):
                mo = RE_OCW.match(od.name)
                if not (od.is_dir() and mo): continue
                for rd in sorted(od.iterdir()):
                    mr = RE_RUN.match(rd.name)
                    if not (rd.is_dir() and mr): continue
                    r = dict(ari=int(ma["ari"]), OCwMin=int(mo["ocw"]), nRaRus=int(mr["raru"]),
                             run=int(mr["run"]), nSta=int(mr["nSta"]))
                    try:
                        r["vid_tput"] = float(pd.read_csv(rd/"throughput.out", sep="\t")["DL_Video_Mbps"].iloc[0])
                    except Exception:
                        r["vid_tput"] = np.nan
                    try:
                        s = pd.read_csv(rd/"per_sta_stats.out", sep="\t")
                        r["vid_frame_loss"] = surv(s["Vid_frames_gen"], s["Vid_frames_ontime"])
                        r["pose_loss"]      = surv(s["Pose_gen"], s["Pose_ontime"])
                        r["aud_loss"]       = surv(s["Aud_gen"], s["Aud_ontime"])
                        r["vid_p999_ms"]    = float(s["Vid_p999_ms"].mean())
                        r["pose_p999_ms"]   = float(s["Pose_p999_ms"].mean())

                        # --- deadline loss decomposed: never-arrived vs arrived-late ---
                        # Two schemes with equal total loss can fail completely differently:
                        # a starving scheduler drops packets (and its delay percentiles then
                        # only describe the subset it chose to serve), while a loaded one
                        # delivers everything a little late. Total loss alone hides this.
                        pg, prx, pon = (float(s["Pose_gen"].sum()), float(s["Pose_rx"].sum()),
                                        float(s["Pose_ontime"].sum()))
                        r["pose_delivered"] = prx/pg       if pg > 0 else np.nan  # arrived at all
                        r["pose_drop_loss"] = 1.0 - prx/pg if pg > 0 else np.nan  # never arrived
                        r["pose_late_loss"] = (prx-pon)/pg if pg > 0 else np.nan  # arrived, too late
                        ag, arx, aon = (float(s["Aud_gen"].sum()), float(s["Aud_rx"].sum()),
                                        float(s["Aud_ontime"].sum()))
                        r["aud_drop_loss"] = 1.0 - arx/ag  if ag > 0 else np.nan
                        r["aud_late_loss"] = (arx-aon)/ag  if ag > 0 else np.nan
                        # video is frame-level and per_sta_stats has no "frames received"
                        # column, so use packet delivery: a frame needs all 96 packets.
                        vfg, vrx = float(s["Vid_frames_gen"].sum()), float(s["Vid_rx"].sum())
                        r["vid_pkt_delivered"] = vrx/(vfg*VIDEO_PKTS_PER_FRAME) if vfg > 0 else np.nan
                    except Exception:
                        for k in ["vid_frame_loss","pose_loss","aud_loss",
                                  "vid_p999_ms","pose_p999_ms"] + DECOMP_KEYS:
                            r[k] = np.nan
                    rows.append(r)

        df       = pd.DataFrame(rows)
        NSTA_ALL = sorted(df.nSta.unique())
        ARI_ALL  = sorted(df.ari.unique())
        print(f"loaded {len(df)} runs; ari={ARI_ALL}; nSta={NSTA_ALL}; "
              f"nRaRus={sorted(df.nRaRus.unique())}; OCwMin={sorted(df.OCwMin.unique())}")

        def ramp(hex_hue, n):
            """Light->dark ramp of one hue: OCwMin (and ARI, below) are sequential."""
            cm = LinearSegmentedColormap.from_list("r", ["#cfd8e3", hex_hue, "#12233a"])
            return [cm(x) for x in (np.linspace(0.25, 0.92, n) if n > 1 else [0.6])]

        outdir = Path("fig/xr/ari_uora"); outdir.mkdir(parents=True, exist_ok=True)

        METRICS = [("vid_tput",          "DL video throughput (Mbps)",    None,        "linear"),
                   ("vid_frame_loss",    "DL video frame deadline loss",  None,        "linear"),
                   ("vid_pkt_delivered", "DL video packet delivery rate", None,        "linear"),
                   ("pose_loss",         "UL pose deadline loss (total)", None,        "log"),
                   ("pose_drop_loss",    "UL pose loss: never delivered", None,        "log"),
                   ("pose_late_loss",    "UL pose loss: delivered late",  None,        "log"),
                   ("vid_p999_ms",       "DL video P99.9 delay (ms)",     VIDEO_BOUND, "log"),
                   ("pose_p999_ms",      "UL pose P99.9 delay (ms)",      POSE_BOUND,  "log")]
        LOSS_METRICS = {"pose_loss", "pose_drop_loss", "pose_late_loss"}

        # Fixed y-limits per metric over the WHOLE dataset, so the eight figures of a
        # given metric are directly comparable to one another.
        YLIM = {}
        for metric, _, bound, yscale in METRICS:
            g = (df.groupby(["nSta","ari","nRaRus","OCwMin"])[metric].mean()).replace(
                    [np.inf,-np.inf], np.nan).dropna()
            if metric in LOSS_METRICS: g = g.clip(lower=LOSS_FLOOR)
            if g.empty: YLIM[metric] = None; continue
            if yscale == "log":
                lo, hi = max(g[g > 0].min()*0.7, LOSS_FLOOR*0.7), g.max()*1.4
                if bound is not None: lo, hi = min(lo, bound*0.7), max(hi, bound*1.4)
            else:
                lo, hi = 0, g.max()*1.08
            YLIM[metric] = (lo, hi)

        # %% figures: 8 metrics x each headset count  (one 1x5 nRaRus grid per figure)
        for n in NSTA_ALL:
            dn = df[df.nSta == n]
            for metric, ylab, bound, yscale in METRICS:
                fig, axes = plt.subplots(1, len(NRARUS), figsize=(TEXTWIDTH_IN, 2.5),
                                         sharex=True, sharey=True)
                for j, r in enumerate(NRARUS):
                    ax   = axes[j]
                    ax.axvspan(96, 1400, color="#000000", alpha=0.045, lw=0, zorder=0)
                    sub  = dn[dn.nRaRus == r]
                    cols = ramp(RARU_COLOR[r], len(OCWMIN))
                    for k, o in enumerate(OCWMIN):
                        g = sub[sub.OCwMin == o].groupby("ari")[metric].mean().sort_index()
                        if g.empty or g.isna().all(): continue
                        if metric in LOSS_METRICS: g = g.clip(lower=LOSS_FLOOR)
                        ax.plot(g.index, g.values, color=cols[k], marker="o",
                                markeredgecolor="white", markeredgewidth=0.4, zorder=3,
                                label=f"OCW$_{{min}}$={o}")
                    if bound is not None:
                        ax.axhline(bound, ls=":", color="#52514e", lw=0.9, zorder=2)
                    ax.set_xscale("log", base=2); ax.set_yscale(yscale)
                    ax.set_xticks([16, 64, 256, 1024]); ax.set_xticklabels([16, 64, 256, 1024])
                    if YLIM[metric] is not None: ax.set_ylim(*YLIM[metric])
                    ax.grid(True, alpha=0.3, lw=0.4); ax.set_axisbelow(True)
                    ax.set_title(raru_label(r), fontsize=7)
                    ax.set_xlabel("ARI ($\\mu$s)")
                    if j == 0: ax.set_ylabel(ylab, fontsize=7.5)
                    ax.legend(loc="best", frameon=False, handlelength=1.2,
                              borderpad=0.2, labelspacing=0.25)
                note = "  (values clipped at %g for the log axis)" % LOSS_FLOOR if metric in LOSS_METRICS else ""
                fig.suptitle(f"{ylab} — UORA, {n} headset{'s' if n != 1 else ''}{note}",
                             fontsize=8.5, y=1.04)
                fig.tight_layout()
                fig.savefig(outdir/f"xr_ari_dlfirst_uora_{metric}_nsta{n}.pdf", bbox_inches="tight")
                if SHOW_FIGS: plt.show()
                else: plt.close(fig)
        print(f"wrote {len(NSTA_ALL)*len(METRICS)} per-headset figures to {outdir}")

        # %% capacity figure: DL video throughput vs headsets, ARI as the ramp
        fig, axes = plt.subplots(1, len(NRARUS), figsize=(TEXTWIDTH_IN, 2.5),
                                 sharex=True, sharey=True)
        for j, r in enumerate(NRARUS):
            ax   = axes[j]
            sub  = df[df.nRaRus == r]
            cols = ramp(RARU_COLOR[r], len(ARI_ALL))
            for k, a in enumerate(ARI_ALL):
                g = sub[sub.ari == a].groupby("nSta")["vid_tput"].agg(["mean", "std"])
                if g.empty: continue
                ax.errorbar(g.index, g["mean"],
                            yerr=np.vstack([np.minimum(g["std"].values, g["mean"].values),
                                            g["std"].values]),   # lower whisker clipped at 0
                            color=cols[k], marker="o", capsize=1.5, elinewidth=0.5,
                            markeredgecolor="white", markeredgewidth=0.4, zorder=3,
                            label=f"ARI={a}")
            ax.plot(NSTA_ALL, [VIDEO_PER_HEADSET_MBPS*x for x in NSTA_ALL],
                    ls=":", color="#52514e", lw=0.9, zorder=2,
                    label="offered" if j == 0 else None)
            ax.set_xticks(NSTA_ALL); ax.grid(True, alpha=0.3, lw=0.4); ax.set_axisbelow(True)
            ax.set_title(raru_label(r), fontsize=7)
            ax.set_xlabel("Number of headsets")
            if j == 0: ax.set_ylabel("DL video throughput (Mbps)", fontsize=7.5)
            ax.legend(loc="best", frameon=False, handlelength=1.2,
                      borderpad=0.2, labelspacing=0.25, fontsize=5.5)
        fig.suptitle("DL video throughput vs headsets — UORA, per nRaRus (ramp = ARI)",
                     fontsize=8.5, y=1.04)
        fig.tight_layout()
        fig.savefig(outdir/"xr_ari_dlfirst_uora_tput_vs_nsta.pdf", bbox_inches="tight")
        plt.show()

        # %% ===================== ARI selection =========================================
        # UORA needs an operating point (nRaRus, OCwMin) chosen before ARI can be compared,
        # so every step below reports which config it selected. Raw metrics only -- no
        # composite score: summing/maxing frame loss with pose loss lets one saturated
        # metric decide the ranking and hides the video/pose tradeoff.
        cfg = (df.groupby(["nSta","ari","nRaRus","OCwMin"])
                 [["vid_frame_loss","pose_loss","pose_drop_loss","pose_late_loss",
                   "pose_delivered","vid_tput","pose_p999_ms"]].mean().reset_index())

        # --- 1. feasibility: can UORA meet BOTH deadline budgets at all? ---------------
        print(f"\n=== 1) configs meeting BOTH budgets (frame<= {LOSS_BUDGET} and pose<= {LOSS_BUDGET}) ===")
        feas = (cfg.assign(ok=(cfg.vid_frame_loss <= LOSS_BUDGET) & (cfg.pose_loss <= LOSS_BUDGET))
                   .groupby(["nSta","ari"])["ok"].sum().reset_index())
        print(feas.pivot(index="nSta", columns="ari", values="ok").to_string())
        print("  (out of 30 nRaRus x OCwMin configs; 0 = unservable at any config)")

        # --- 2. is the loss starvation or lateness? -----------------------------------
        # ~1.0 => the config is dropping packets it never even attempted, so its delay
        # percentiles describe only the traffic it chose to carry. ~0.0 => it delivers
        # everything and some arrives late. Same total loss, opposite meaning.
        cfg["drop_share"] = cfg["pose_drop_loss"] / cfg["pose_loss"].replace(0, np.nan)
        print("\n=== 2) share of UL pose loss that is DROPS (~1.0 starvation, ~0.0 lateness) ===")
        print(cfg[cfg.nSta >= 5].pivot_table(index="nRaRus", columns="nSta",
                                             values="drop_share", aggfunc="mean")
                .to_string(float_format=lambda x: f"{x:.3f}"))
        print("\n=== 2b) % of generated UL pose delivered ON TIME, ARI>=128 (rows=nRaRus) ===")
        cfg["pct_ontime"] = 100*(1 - cfg["pose_loss"])
        print(cfg[cfg.ari >= 128].pivot_table(index="nRaRus", columns="nSta",
                                              values="pct_ontime", aggfunc="mean")
                .to_string(float_format=lambda x: f"{x:.2f}"))

        # --- 3. raw metrics at the video-optimal and pose-optimal operating points -----
        vbest = cfg.sort_values(["vid_frame_loss","pose_loss"]).groupby(["nSta","ari"]).first().reset_index()
        pbest = cfg.sort_values(["pose_loss","vid_frame_loss"]).groupby(["nSta","ari"]).first().reset_index()
        print("\n=== 3a) video-optimal operating point: raw values per (nSta, ari) ===")
        print(vbest[["nSta","ari","nRaRus","OCwMin","vid_frame_loss","pose_loss",
                     "pose_drop_loss","pose_late_loss","vid_tput"]]
                .to_string(index=False, float_format=lambda x: f"{x:.5f}"))
        print("\n=== 3b) pose-optimal operating point: raw values per (nSta, ari) ===")
        print(pbest[["nSta","ari","nRaRus","OCwMin","pose_loss","pose_drop_loss",
                     "pose_late_loss","vid_frame_loss","vid_tput"]]
                .to_string(index=False, float_format=lambda x: f"{x:.5f}"))

        # --- 4. per-nSta nominal best ARI ----------------------------------------------
        print("\n=== 4) nominal best ARI per headset count (video-optimal point) ===")
        for n in NSTA_ALL:
            t = vbest[vbest.nSta == n].sort_values(["vid_frame_loss","pose_loss"]).iloc[0]
            print(f"  nSta={n}: ARI={int(t.ari):5d}  frame={t.vid_frame_loss:.5f} "
                  f"pose={t.pose_loss:.5f} tput={t.vid_tput:.1f} "
                  f"cfg={int(t.nRaRus)}RU/ocw{int(t.OCwMin)}")

        # --- 5. is that "winner" real? pairwise tests across the passing ARI values ----
        # Without this, sort().first() always yields a winner whether or not one exists.
        PASSING = [a for a in ARI_ALL if a >= 128]
        print(f"\n=== 5) significance of ARI differences among {PASSING} (video-optimal point) ===")
        for n in NSTA_ALL:
            print(f"\n nSta={n}")
            samples = {}
            for a in PASSING:
                row = vbest[(vbest.nSta == n) & (vbest.ari == a)]
                if row.empty: continue
                r0 = row.iloc[0]
                v = df[(df.nSta == n) & (df.ari == a) & (df.nRaRus == r0.nRaRus)
                       & (df.OCwMin == r0.OCwMin)]["vid_frame_loss"].dropna().values
                if len(v):
                    samples[a] = v
                    print(f"   ARI={a:5d}  mean={v.mean():.5f}  sd={v.std(ddof=1):.5f}  "
                          f"sem={v.std(ddof=1)/np.sqrt(len(v)):.5f}  n={len(v)}")
            sig = []
            for i, x in enumerate(PASSING):
                for y in PASSING[i+1:]:
                    if x not in samples or y not in samples: continue
                    vx, vy = samples[x], samples[y]
                    if len(vx) < 2 or len(vy) < 2: continue
                    p = st.ttest_ind(vx, vy, equal_var=False).pvalue
                    if p < ALPHA: sig.append((x, y, p))
                    print(f"   {x} vs {y}: diff={vx.mean()-vy.mean():+.5f}  p={p:.3f}  "
                          f"{'SIG' if p < ALPHA else 'n.s.'}")
            print("   -> " + ("no ARI is significantly better; the nominal winner is a rank artifact"
                              if not sig else f"{len(sig)} significant pair(s)"))

        # --- 6. the claim that actually survives: the ARI>=128 threshold ---------------
        print("\n=== 6) ARI<=64 vs ARI>=128 (video-optimal point), per headset count ===")
        lo  = vbest[vbest.ari <= 64].groupby("nSta")["vid_frame_loss"].mean()
        hi  = vbest[vbest.ari >= 128].groupby("nSta")["vid_frame_loss"].mean()
        out = pd.DataFrame({"ARI<=64": lo, "ARI>=128": hi})
        out["ratio"] = out["ARI<=64"] / out["ARI>=128"].replace(0, np.nan)
        print(out.to_string(float_format=lambda x: f"{x:.5f}"))

        # --- 7. best OCwMin per (ari, nRaRus), per headset count -----------------------
        print("\n=== 7) best OCwMin by pose deadline loss, per headset count ===")
        best = (df.groupby(["nSta","ari","nRaRus","OCwMin"])["pose_loss"].mean()
                  .reset_index().sort_values("pose_loss")
                  .groupby(["nSta","ari","nRaRus"]).first().reset_index())
        for n in NSTA_ALL:
            print(f"\n-- nSta={n} : chosen OCwMin (rows=nRaRus, cols=ari) --")
            print(best[best.nSta == n].pivot(index="nRaRus", columns="ari", values="OCwMin").to_string())
        _done("xr_ari_uora")
    except Exception as _err:
        _done("xr_ari_uora", _err)

# ---- xr_ari_a2p: Access request interval selection, A2P and A2PV2 ----
if _run("xr_ari_a2p"):
    try:
        # %% imports
        import re
        from pathlib import Path
        import numpy as np, pandas as pd
        import matplotlib.pyplot as plt
        from matplotlib.colors import LinearSegmentedColormap

        plt.rcParams.update({
            "font.size": 8, "axes.labelsize": 8, "axes.titlesize": 8,
            "xtick.labelsize": 6.5, "ytick.labelsize": 6.5, "legend.fontsize": 6,
            "lines.linewidth": 1.6, "lines.markersize": 3.5,
            "axes.linewidth": 0.6, "grid.linewidth": 0.4,
            "pdf.fonttype": 42, "ps.fonttype": 42,
        })
        TEXTWIDTH_IN = 7.16

        # %% config
        # A2P / A2PV2 ARI sweep: xr_data_ari/<scheme>/ari_<us>/<run>_run-<n>_sta
        ROOT    = Path("xr_data_ari_dlfirst")
        SCHEMES = ["a2p", "a2pv2"]
        SCHEME_LABEL = {"a2p": "A2P", "a2pv2": "A2PV2"}
        # one hue per scheme; from the dataviz-validated categorical palette
        SCHEME_COLOR = {"a2p": "#2a78d6", "a2pv2": "#eb6834"}
        VIDEO_BOUND, POSE_BOUND = 50.0, 10.0
        VIDEO_PER_HEADSET_MBPS  = 100
        VIDEO_PKTS_PER_FRAME    = 96
        LOSS_BUDGET = 0.05
        LOSS_FLOOR  = 1e-6        # log axes drop exact zeros; clip the loss series

        RE_ARI = re.compile(r"^ari_(?P<ari>\d+)$")
        RE_RUN = re.compile(r"^(?P<run>\d+)_run-(?P<nSta>\d+)_sta$")

        def surv(gen, ontime):
            """Deadline loss over *generated* packets (drops + late), survivorship-proof."""
            g = float(np.nansum(gen))
            return max(0.0, 1.0 - float(np.nansum(ontime))/g) if g > 0 else np.nan

        # %% load
        rows = []
        for sch in SCHEMES:
            base = ROOT/sch
            if not base.is_dir(): continue
            for ad in sorted(base.iterdir()):
                ma = RE_ARI.match(ad.name)
                if not (ad.is_dir() and ma): continue
                for rd in sorted(ad.iterdir()):
                    mr = RE_RUN.match(rd.name)
                    if not (rd.is_dir() and mr): continue
                    r = dict(scheme=sch, ari=int(ma["ari"]),
                             run=int(mr["run"]), nSta=int(mr["nSta"]))
                    try:
                        r["vid_tput"] = float(pd.read_csv(rd/"throughput.out", sep="\t")["DL_Video_Mbps"].iloc[0])
                    except Exception:
                        r["vid_tput"] = np.nan
                    try:
                        s = pd.read_csv(rd/"per_sta_stats.out", sep="\t")
                        r["vid_frame_loss"] = surv(s["Vid_frames_gen"], s["Vid_frames_ontime"])
                        r["pose_loss"]      = surv(s["Pose_gen"], s["Pose_ontime"])
                        r["aud_loss"]       = surv(s["Aud_gen"], s["Aud_ontime"])
                        r["vid_p999_ms"]    = float(s["Vid_p999_ms"].mean())
                        r["pose_p999_ms"]   = float(s["Pose_p999_ms"].mean())
                        # deadline loss decomposed: never-arrived vs arrived-late. The same
                        # total loss can mean starvation or lateness -- opposite meanings,
                        # and delay percentiles only describe the traffic actually carried.
                        pg, prx, pon = (float(s["Pose_gen"].sum()), float(s["Pose_rx"].sum()),
                                        float(s["Pose_ontime"].sum()))
                        r["pose_delivered"] = prx/pg       if pg > 0 else np.nan
                        r["pose_drop_loss"] = 1.0 - prx/pg if pg > 0 else np.nan
                        r["pose_late_loss"] = (prx-pon)/pg if pg > 0 else np.nan
                        vfg, vrx = float(s["Vid_frames_gen"].sum()), float(s["Vid_rx"].sum())
                        r["vid_pkt_delivered"] = vrx/(vfg*VIDEO_PKTS_PER_FRAME) if vfg > 0 else np.nan
                    except Exception:
                        for k in ["vid_frame_loss","pose_loss","aud_loss","vid_p999_ms","pose_p999_ms",
                                  "pose_delivered","pose_drop_loss","pose_late_loss","vid_pkt_delivered"]:
                            r[k] = np.nan
                    rows.append(r)

        df       = pd.DataFrame(rows)
        NSTA_ALL = sorted(df.nSta.unique())
        ARI_ALL  = sorted(df.ari.unique())
        PASSING  = [a for a in ARI_ALL if a >= 128]
        pd.set_option("display.width", 200)
        print(f"loaded {len(df)} runs; schemes={sorted(df.scheme.unique())}; "
              f"ari={ARI_ALL}; nSta={NSTA_ALL}")

        def ramp(hex_hue, n):
            """Light->dark ramp of one hue: nSta is a sequential quantity."""
            cm = LinearSegmentedColormap.from_list("r", ["#cfd8e3", hex_hue, "#12233a"])
            return [cm(x) for x in (np.linspace(0.25, 0.92, n) if n > 1 else [0.6])]

        outdir = Path("fig/xr/ari_a2p"); outdir.mkdir(parents=True, exist_ok=True)

        METRICS = [("vid_tput",          "DL video throughput (Mbps)",    None,        "linear"),
                   ("vid_frame_loss",    "DL video frame deadline loss",  None,        "linear"),
                   ("vid_pkt_delivered", "DL video packet delivery rate", None,        "linear"),
                   ("pose_loss",         "UL pose deadline loss (total)", None,        "log"),
                   ("pose_drop_loss",    "UL pose loss: never delivered", None,        "log"),
                   ("pose_late_loss",    "UL pose loss: delivered late",  None,        "log"),
                   ("vid_p999_ms",       "DL video P99.9 delay (ms)",     VIDEO_BOUND, "log"),
                   ("pose_p999_ms",      "UL pose P99.9 delay (ms)",      POSE_BOUND,  "log")]
        LOSS_METRICS = {"pose_loss","pose_drop_loss","pose_late_loss"}

        # %% figures: one per metric, 1x2 panels (scheme), nSta as the ramp
        for metric, ylab, bound, yscale in METRICS:
            fig, axes = plt.subplots(1, len(SCHEMES), figsize=(TEXTWIDTH_IN*0.62, 2.6),
                                     sharex=True, sharey=True)
            for j, sch in enumerate(SCHEMES):
                ax   = axes[j]
                ax.axvspan(96, 1400, color="#000000", alpha=0.045, lw=0, zorder=0)
                sub  = df[df.scheme == sch]
                cols = ramp(SCHEME_COLOR[sch], len(NSTA_ALL))
                for k, n in enumerate(NSTA_ALL):
                    g = sub[sub.nSta == n].groupby("ari")[metric].mean().sort_index()
                    if g.empty or g.isna().all(): continue
                    if metric in LOSS_METRICS: g = g.clip(lower=LOSS_FLOOR)
                    ax.plot(g.index, g.values, color=cols[k], marker="o",
                            markeredgecolor="white", markeredgewidth=0.4, zorder=3,
                            label=f"{n} sta")
                if bound is not None:
                    ax.axhline(bound, ls=":", color="#52514e", lw=0.9, zorder=2)
                ax.set_xscale("log", base=2); ax.set_yscale(yscale)
                ax.set_xticks([16, 64, 256, 1024]); ax.set_xticklabels([16, 64, 256, 1024])
                if metric in ("vid_frame_loss", "vid_pkt_delivered"): ax.set_ylim(-0.02, 1.02)
                ax.minorticks_off(); ax.grid(True, alpha=0.3, lw=0.4); ax.set_axisbelow(True)
                ax.set_title(SCHEME_LABEL[sch], fontsize=7.5)
                ax.set_xlabel("ARI ($\\mu$s)")
                if j == 0: ax.set_ylabel(ylab, fontsize=7.5)
                ax.legend(loc="best", frameon=False, ncol=2, handlelength=1.2,
                          borderpad=0.2, labelspacing=0.25)
            note = "  (clipped at %g for the log axis)" % LOSS_FLOOR if metric in LOSS_METRICS else ""
            fig.suptitle(f"{ylab} vs ARI — ramp = headsets{note}", fontsize=8.5, y=1.03)
            fig.tight_layout()
            fig.savefig(outdir/f"xr_ari_dlfirst_a2p_{metric}.pdf", bbox_inches="tight")
            plt.show()

        # %% ===================== ARI selection ========================================
        agg = df.groupby(["scheme","nSta","ari"])[
                ["vid_frame_loss","pose_loss","pose_drop_loss","pose_late_loss",
                 "vid_tput","pose_p999_ms"]].mean().reset_index()

        print(f"\n=== 1) meets BOTH budgets (frame<={LOSS_BUDGET}, pose<={LOSS_BUDGET})? ===")
        for sch in SCHEMES:
            a = agg[agg.scheme == sch].assign(
                    ok=lambda d: (d.vid_frame_loss <= LOSS_BUDGET) & (d.pose_loss <= LOSS_BUDGET))
            print(f"\n-- {SCHEME_LABEL[sch]} --")
            print(a.pivot(index="nSta", columns="ari", values="ok")
                   .replace({True: "ok", False: "-"}).to_string())

        for metric, name in [("pose_loss", "UL pose deadline loss"),
                             ("vid_frame_loss", "DL video frame deadline loss")]:
            print(f"\n=== 2) {name}: rows=nSta cols=ari ===")
            for sch in SCHEMES:
                print(f"\n-- {SCHEME_LABEL[sch]} --")
                print(agg[agg.scheme == sch].pivot(index="nSta", columns="ari", values=metric)
                        .to_string(float_format=lambda x: f"{x:.5f}"))

        print("\n=== 3) lowest-loss ARI per headset count (within ARI>=128) ===")
        for metric, name in [("pose_loss", "pose"), ("vid_frame_loss", "video")]:
            for sch in SCHEMES:
                p = agg[agg.scheme == sch].pivot(index="nSta", columns="ari", values=metric)[PASSING]
                t7, t8 = {}, {}
                for n in p.index:
                    w = p.loc[n].idxmin()
                    t8[w] = t8.get(w, 0) + 1
                    if n <= 7: t7[w] = t7.get(w, 0) + 1
                print(f"  {SCHEME_LABEL[sch]:6s} {name:6s}: nSta1-7 {t7}   nSta1-8 {t8}")

        print("\n=== 4) share of UL pose loss that is DROPS (~1 starvation, ~0 lateness) ===")
        agg["drop_share"] = agg["pose_drop_loss"] / agg["pose_loss"].replace(0, np.nan)
        print(agg[agg.ari >= 128].pivot_table(index="scheme", columns="nSta",
                values="drop_share", aggfunc="mean").to_string(float_format=lambda x: f"{x:.3f}"))

        print("\n=== 5) ARI<=64 vs ARI>=128 (mean video frame loss) ===")
        lo  = agg[agg.ari <= 64].groupby(["scheme","nSta"])["vid_frame_loss"].mean()
        hi  = agg[agg.ari >= 128].groupby(["scheme","nSta"])["vid_frame_loss"].mean()
        cmp = pd.DataFrame({"ARI<=64": lo, "ARI>=128": hi})
        cmp["ratio"] = cmp["ARI<=64"] / cmp["ARI>=128"].replace(0, np.nan)
        print(cmp.to_string(float_format=lambda x: f"{x:.5f}"))
        _done("xr_ari_a2p")
    except Exception as _err:
        _done("xr_ari_a2p", _err)


if _FAILED:
    print("\nFailed sections: " + ", ".join(_FAILED))
    sys.exit(1)
