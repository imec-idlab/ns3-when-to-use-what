# Polling Schemes for OFDMA Uplink Scheduling in Wi-Fi (ns-3)

This repository contains the ns-3 implementation, the simulation scenarios, and
the plotting scripts for the paper

> D. D. Agbeve, F. Van Herck, A. Belogaev, and J. Famaey, "Evaluating Polling
> Schemes for OFDMA Uplink Scheduling in Time-Sensitive Wi-Fi Networks,"
> submitted to **, 2026.

The paper compares six ways for an IEEE 802.11ax access point to learn which
stations have uplink data and to schedule them, under three time-sensitive
workloads (video conferencing, industrial IoT, and extended reality).

| Scheme in the paper | Mode name in the scripts | Scheduler class |
|---|---|---|
| EDCA (no uplink OFDMA) | `edca` | none |
| SA-OFDMA (scheduled access only) | `uora` with `nRaRus=0` | `ns3::UoraMultiUserScheduler` |
| UORA (uplink OFDMA random access) | `uora` with `nRaRus>0` | `ns3::UoraMultiUserScheduler` |
| A2P | `a2p` | `ns3::VlceMultiUserScheduler` |
| A2S | `a2pv2` | `ns3::VlceMultiUserScheduler` with `--enableBsrp=false` |
| CMAB (CUCB, epsilon-greedy, and others) | `cmab` | `ns3::CmabMultiUserScheduler` |

The code is based on [ns-3.38](https://www.nsnam.org/releases/ns-3-38/). The
original ns-3 README is kept in [`README-ns3.md`](README-ns3.md) and applies
to everything not described here.

## Repository layout

| Path | Content |
|---|---|
| `scratch/conference_when2usewhat/` | Video-conferencing scenario |
| `scratch/iiot_when2usewhat/` | Industrial IoT scenario |
| `scratch/xr_when2usewhat/` | Extended-reality scenario |
| `src/wifi/model/he/` | Multi-user schedulers (`cmab-`, `uora-`, `vlce-`, `rr-multi-user-scheduler`) and the UORA parameter set |
| `src/veloce-addons/` | Traffic applications (`ap-server`, `sta-client`, `xr-server`, `xr-client`) and packet tags |
| `when2usewhat_output/run_*.sh` | Scripts that run a single configuration locally |
| `when2usewhat_output/gnu-parallel/` | GNU Parallel launcher (`run_local.sh`), job scripts, and Slurm wrapper for the full parameter sweeps, with the parameter files in `params/` |
| `when2usewhat_output/plot_figures.py` | Script that generates the figures of the paper |
| `when2usewhat_output/plotter.ipynb` | Notebook version of the plotting script |
| `README-ns3.md` | Original ns-3 README (build options, documentation, upstream project) |

## Requirements

- Linux, a C++17 compiler (GCC 9 or later, or Clang 10 or later), CMake 3.10 or
  later, and Python 3.
- For the figures: `numpy`, `pandas`, `scipy`, `matplotlib`, and `seaborn`.
- For the sweeps: GNU Parallel. A Slurm cluster is optional.

## Build

```shell
./ns3 configure -d optimized --disable-gtk --disable-tests --disable-examples --cxx-standard=17
./ns3 build
```

Use `-d debug` instead of `-d optimized` to enable `NS_LOG` output and
assertions. [`README-ns3.md`](README-ns3.md) describes the remaining ns-3
build options.

## Running a single simulation

Each scenario is an ns-3 program with command-line options. `--PrintHelp`
lists them all, for example

```shell
./ns3 run "scratch/iiot_when2usewhat/iiot_when2usewhat --PrintHelp"
```

The following command runs the industrial IoT scenario with A2P and 20
sporadic stations.

```shell
./ns3 run --no-build "scratch/iiot_when2usewhat/iiot_when2usewhat \
    --simType=A2P \
    --scheduler=ns3::VlceMultiUserScheduler \
    --typeTwoNStations=20 \
    --simulationTime=30 --startLogTime=5 --RngRun=1 \
    --phyModel=Spectrum --dlAckType=AGGR-MU-BAR \
    --enableUlOfdma=true --useMuEdca=true \
    --UseCentral26TonesRus=true --ruAllocationType=ru-26-tone \
    --DelayAccessReqUponAccess=true \
    --muSchedAccessReqInterval=128 --maxTimeInList=204800 \
    --nMpdus=0 --nMsdus=10 --pMean=0.1 \
    --ns3::VlceMultiUserScheduler::BsrpPrioritizeEmpty=true \
    --ns3::VlceMultiUserScheduler::PrioritizeByAc=true \
    --logDir=$PWD/results/iiot/a2p/1_run-20_sta"
```

The scripts `run_conferencing.sh`, `run_iiot.sh`, and `run_xr.sh` in
`when2usewhat_output/` wrap such commands for every scheme. The exact
arguments used for each scheme in the paper are in
`when2usewhat_output/gnu-parallel/job_script_conf.sh` (conferencing),
`job_script_iiot.sh`, and `job_script_xr.sh`.

Options shared by the three scenarios include

| Option | Meaning |
|---|---|
| `--simType` | Scheme label (`EDCA`, `A2P`, `A2PV2`, `UORA`, `CMAB`, ...) |
| `--scheduler` (`--Scheduler` in the XR scenario) | Multi-user scheduler class |
| `--muSchedAccessReqInterval` | Access request interval of the scheduler |
| `--nRaRus`, `--OCwMin`, `--OCwMax` | UORA random-access resource units and OFDMA contention window |
| `--cmabAlgorithm` | `CUCB`, `ThompsonSampling`, `EpsilonGreedy`, or `EXP3M` |
| `--cmabRewardType` | `Binary` or `FairnessWeighted` |
| `--RngRun` | Seed index of the run |
| `--startLogTime` | Start of the measurement window in seconds |
| `--logDir` | Output directory of the run |

Each run writes its statistics to `--logDir`, including `per_sta_stats.out`,
`throughput.out`, and `all_packets_e2e.out`.

## Reproducing the parameter sweeps

Every line of a file in `when2usewhat_output/gnu-parallel/params/` is one
simulation run (seed, number of stations, and scheme parameters). The launcher
`run_local.sh` runs such a file on a single machine with GNU Parallel.

```shell
cd when2usewhat_output/gnu-parallel
./run_local.sh <scenario> <mode> [extra GNU Parallel options]
```

`<scenario>` is `conf`, `iiot`, or `xr`, and `<mode>` is `edca`, `a2p`,
`a2pv2`, `uora`, or `cmab`. For example

```shell
./run_local.sh iiot a2p               # all cores
./run_local.sh xr cmab -j 8           # 8 simulations at a time
./run_local.sh iiot uora --dry-run    # print the commands only
```

The launcher builds ns-3 once, starts one simulation per row, and records the
finished rows in a job log next to the parameter file. Running the same
command again resumes the sweep and repeats only the rows that failed or did
not run. Three environment variables override the defaults.

| Variable | Meaning | Default |
|---|---|---|
| `PARAMS` | Parameter file to sweep | `params/<mode>_conf_input.csv`, `params/<mode>_iiot_input.csv`, or `params/<mode>_xr_input.csv` |
| `DATA_ROOT` | Directory of the results | `when2usewhat_output/conf_data`, `iiot_data`, or `xr_data` |
| `NS3_DIR` | Root of the ns-3 tree | This repository |

The scheme arguments of each scenario are in `job_script_conf.sh` (conferencing),
`job_script_iiot.sh`, and `job_script_xr.sh`. The parameter files are
generated by the scripts in `params/`.


## Generating the figures

`when2usewhat_output/plot_figures.py` reads the per-run result directories
(`conf_data/`, `iiot_data/`, `xr_data/`, and `xr_data_ari_dlfirst/`),
aggregates them over the seeds, and writes the figures to
`when2usewhat_output/fig/`.

```shell
cd when2usewhat_output
python3 plot_figures.py paper          # only the figures used in the paper
python3 plot_figures.py                # every section
python3 plot_figures.py conf           # one scenario: conf, iiot, or xr
python3 plot_figures.py xr_results iiot_t1_throughput
python3 plot_figures.py --list         # list the sections
```

Each section of the script is one self-contained plotting block. The sections
that produce the figures of the paper are

| Section | Figure |
|---|---|
| `conf_results_row` | Conferencing delay, wake-up delay, and loss |
| `conf_video_delay` | Conferencing uplink video delay |
| `conf_cmab_tuning_voice` | Conferencing CMAB hyper-parameter sweep |
| `iiot_box_loss_grid` | Industrial IoT per-packet delay and loss |
| `iiot_t1_throughput` | Industrial IoT type-1 throughput |
| `xr_results` | Extended-reality pose delay, deadline misses, and video throughput |

The remaining sections cover the parameter selection (CMAB hyper-parameters
and access request interval) and additional views of the same results.

By default the script looks for the result directories next to itself and
saves the figures without opening a window. `--data-dir <path>` selects
another location, and `--show` also displays the figures. A section that fails,
for example because its results are missing, is reported at the end and does
not stop the others.

`plotter.ipynb` is the notebook from which the script was derived.
`xr_ari_uora_plots.py` and `xr_ari_cmab_plots.py` are standalone versions of
the access request interval sections of the extended-reality scenario.

## Citation

```bibtex
@article{agbeve2026polling,
  author  = {Agbeve, Douglas Dziedzorm and Van Herck, Ferhat and Belogaev, Andrey and Famaey, Jeroen},
  title   = {Evaluating Polling Schemes for {OFDMA} Uplink Scheduling in Time-Sensitive {Wi-Fi} Networks},
  journal = {IEEE },
  year    = {2026},
  note    = {Submitted for publication}
}
```

## License

This software is licensed under the GNU General Public License v2.0, as is
ns-3. See `LICENSE`.

## Acknowledgment

This research was supported by the FWO WaveVR project (G034322N).
