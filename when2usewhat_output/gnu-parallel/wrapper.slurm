#!/bin/bash

#SBATCH -A ap_idlab_thesis
#SBATCH --nodes=1 --exclusive
#SBATCH --time=10:50:00

#SBATCH --mail-type=FAIL
#SBATCH --mail-user=douglas.agbeve@uantwerpen.be

module --force purge
module load calcua/all parallel


if [[ $# -lt 1 || $# -gt 2 ]] ; then
  echo "# Usage: $0 <input.csv> [job_script.sh]"
  exit -1
elif [[ ! -r $1 ]] ; then
  echo "# Error: input \"$1\" is not a readable file"
  exit -1
fi

CSV="$1"
NAME="${CSV%.csv}"
LOG="${NAME}.log"

if [[ $# -eq 2 ]]; then
  RUN="$2"
else
  RUN="job_script.sh"
fi

if [[ ! -x ${RUN} ]] ; then
  echo "# Error: run file \"${RUN}\" must be an executable"
  exit -1
fi

echo "# Input file: ${CSV}"
echo "# Run script: ${RUN}"
echo "# Log file: ${LOG}"

HEADER=$(head -1 "${CSV}")
parallel -P $((${SLURM_NNODES}*${SLURM_CPUS_ON_NODE})) -a ${CSV} --resume-failed --ungroup --tag --joblog ${LOG} --header '.*\n' srun --exclusive -N1 -n1 -c1 ${RUN} "${MODE}" "${HEADER}"

exitcode=$?

if [[ $exitcode == 0 ]] ; then
  echo "# Result: all $(($(wc -l ${CSV} | awk '{print $1}') - 1)) job steps ran successfully"
else
  missing=$(parallel --dry-run -a ${CSV} --resume-failed --joblog ${LOG} --header '.*\n' srun --exclusive -N1 -n1 -c1 ${RUN} "${MODE}" "${HEADER}" | wc -l)
  echo "# Result: some jobs failed, still need to run $missing job steps"
  exit $exitcode
fi
