#!/usr/bin/env bash
#
# Run one parameter sweep on a single machine with GNU Parallel (no Slurm).
#
#   ./run_local.sh <scenario> <mode> [extra GNU Parallel options]
#
#   scenario   conf | iiot | xr
#   mode       edca | a2p | a2pv2 | uora | cmab
#              (xr also accepts the suffixes _ari and _dlfirst, e.g. uora_ari)
#
# Examples
#   ./run_local.sh iiot a2p                 # all cores
#   ./run_local.sh conf cmab -j 8           # 8 simulations at a time
#   ./run_local.sh xr uora_ari --dry-run    # print the commands only
#
# Environment variables (all optional)
#   NS3_DIR    root of the ns-3 tree          (default: two levels above this script)
#   DATA_ROOT  where the results are written  (default: ../conf_data, ../iiot_data, or ../xr_data)
#   PARAMS     parameter CSV to sweep         (default: chosen from scenario and mode)
#
# Every row of the parameter CSV is one simulation. Finished rows are recorded
# in <PARAMS>.<mode>.log, so rerunning the same command resumes the sweep and
# repeats only the rows that failed or did not run.

set -euo pipefail

usage() {
    sed -n '3,14p' "$0" | sed 's/^# \{0,1\}//'
    exit 1
}

[[ $# -ge 2 ]] || usage
SCENARIO="$1"
MODE="$2"
shift 2

command -v parallel >/dev/null || { echo "Error: GNU Parallel not found in PATH" >&2; exit 1; }

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$(dirname "$HERE")"
export NS3_DIR="${NS3_DIR:-$(dirname "$OUT")}"

case "$SCENARIO" in
    conf)
        JOB="$HERE/job_script.sh"
        DEFAULT_PARAMS="$HERE/params/${MODE}_input.csv"
        DEFAULT_ROOT="$OUT/conf_data"
        KEY=nStationsToJoin
        ;;
    iiot)
        JOB="$HERE/job_script_iiot.sh"
        DEFAULT_PARAMS="$HERE/params/${MODE}_iiot_input.csv"
        DEFAULT_ROOT="$OUT/iiot_data"
        KEY=typeTwoNStations
        ;;
    xr)
        JOB="$HERE/job_script_xr.sh"
        # <mode>_dlfirst sweeps the same parameters as <mode>; <mode>_ari has its own file.
        DEFAULT_PARAMS="$HERE/params/${MODE%_dlfirst}_xr_input.csv"
        DEFAULT_ROOT="$OUT/xr_data"
        KEY=nSta
        ;;
    *)
        echo "Error: unknown scenario \"$SCENARIO\"" >&2
        usage
        ;;
esac

export DATA_ROOT="${DATA_ROOT:-$DEFAULT_ROOT}"
PARAMS="${PARAMS:-$DEFAULT_PARAMS}"
LOG="${PARAMS%.csv}.${MODE}.log"

[[ -r "$PARAMS" ]]      || { echo "Error: parameter file \"$PARAMS\" is not readable" >&2; exit 1; }
[[ -x "$JOB" ]]         || { echo "Error: job script \"$JOB\" is not executable" >&2; exit 1; }
[[ -x "$NS3_DIR/ns3" ]] || { echo "Error: no ns3 launcher in \"$NS3_DIR\" (set NS3_DIR)" >&2; exit 1; }

HEADER="$(head -1 "$PARAMS")"
NROWS=$(( $(wc -l < "$PARAMS") - 1 ))

# Each job script expects a scenario-specific column for the number of stations.
case ",$HEADER," in
    *",$KEY,"*) ;;
    *) echo "Error: \"$PARAMS\" has no \"$KEY\" column (header: $HEADER)." >&2
       echo "       It is not a parameter file of the $SCENARIO scenario; set PARAMS=<file.csv>." >&2
       exit 1 ;;
esac

echo "# Scenario:   $SCENARIO ($MODE)"
echo "# Parameters: $PARAMS ($NROWS runs)"
echo "# Results:    $DATA_ROOT"
echo "# Job log:    $LOG"

# The job scripts run ns-3 with --no-build, so build once up front.
case " $* " in
    *" --dry-run "*) ;;
    *) (cd "$NS3_DIR" && ./ns3 build) ;;
esac

# The first CSV line is the header; each following line is passed to the job
# script as one argument, after the mode and the header.
parallel -a "$PARAMS" --header '.*\n' \
    --joblog "$LOG" --resume-failed --ungroup --tag \
    "$@" \
    "$JOB" "$MODE" "$HEADER"
