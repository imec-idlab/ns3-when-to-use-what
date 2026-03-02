#!/bin/bash

set -euo pipefail

export NS_LOG=""

# --------Common Parameters -------
#
run_simulation() {
    local mode="$1"
    local extra_args="$2"
    local raru="${3:-3}"
    local ocw="${3:-3}"


    for run in $(seq 9 9); do
        for nSta in $(seq 20 20); do
            it=8
            tt=8
            if [ "$mode" = "uora" ]; then
                logDir="$PWD/${mode}_${ocw}/${run}-${nSta}-${raru}"
            else
                logDir="$PWD/${mode}/${run}-${nSta}"
            fi
            ./../ns3 run --no-build --gdb \
                "scratch/conference_when2usewhat/conference_when2usewhat \
                --simulationTime=8 \
                --nStationsToJoin=${tt} \
                --totalNStations=${nSta} \
                --initNStations=${it} \
                --RngRun=${run} \
                --logDir=$logDir \
                --enablePcap=false \
                --startLogTime=3 \
                --enableAggregation=true --nMpdus=0 --nMsdus=10 \
                --ruAllocationType=ru-26-tone \
                ${extra_args}"
        done
    done
}

# ------ Various Modes ------
#
BASE_EDCA="
    --phyModel=Yans
    --simType=EDCA
    --dlAckType=NO-OFDMA
    "

BASE_OFDMA="
    --phyModel=Spectrum
    --dlAckType=AGGR-MU-BAR
    --enableUlOfdma=true
    --UseCentral26TonesRus=true
    --DelayAccessReqUponAccess=true
    "

BASE_A2P="
    ${BASE_OFDMA}
    --useMuEdca=true
    --scheduler=ns3::VlceMultiUserScheduler
    "

edca() {
    run_simulation "edca" "${BASE_EDCA}"
}

ofdma() {
    run_simulation "ofdma" "
        ${BASE_OFDMA}
        --simType=OFDMA
        --useMuEdca=true
        --muSchedAccessReqInterval=128
        --scheduler=ns3::RrMultiUserScheduler
    "
}

a2p() {
    run_simulation "a2p" "
        ${BASE_A2P}
        --muSchedAccessReqInterval=128
        --simType=A2P
    "
}

a2pv2() {
    run_simulation "a2pv2" "
         ${BASE_A2P}
         --enableBsrp=false
         --muSchedAccessReqInterval=512
         --simType=A2PV2
    "
}

uora() {
    run_simulation "uora" "
        ${BASE_OFDMA}
        --simType=UORA \
        --useMuEdca=true \
        --muSchedAccessReqInterval=1024 \
        --DelayAccessReqUponAccess=true \
        --muEdcaTimer=8192 \
        --scheduler=ns3::UoraMultiUserScheduler \
        --nRaRus=3 \
        --OCwMin=3
    "
}

# ------- Main logic -------
#
usage() {
    echo "Usage: $0 {edca|ofdma|a2p|a2pv2|uora}"
    exit 1
}

if [[ $# -ne 1 ]]; then
    usage
fi

case "$1" in
    edca|ofdma|a2p|a2pv2|uora)
        "$1"
        ;;
    *)
        usage
        ;;
esac
