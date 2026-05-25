#!/bin/bash

usage() {
    echo "Usage: $0 {edca|ofdma|a2p|a2pv2|uora|cmab}"
    exit 1
}

if [[ $# -ne 1 ]]; then
    usage
fi

MODE="$1"

sbatch --nodes=4 --partition=zen3 --export=ALL,MODE="$MODE" wrapper.slurm params/${MODE}_input.csv
