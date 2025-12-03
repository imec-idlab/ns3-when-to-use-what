#!/bin/bash
sbatch --nodes=1 --partition=zen3 wrapper.slurm params/a2p_validation.csv job_a2p.sh
