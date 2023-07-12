#!/bin/bash

ml atools/slurm

sbatch --array $(arange --data edca.csv) Edca.slurm
