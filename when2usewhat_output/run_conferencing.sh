#!/bin/bash

set -euo pipefail

export NS_LOG=""

# --------Common Parameters -------
#
run_simulation() {
    local mode="$1"
    local extra_args="$2"
    local raru="${RA_RU_COUNT:-0}"
    local ocw="${OCW_MIN:-63}"
    local cmab_alg="${CMAB_ALG:-CUCB}"
    local cmab_reward="${CMAB_REWARD:-Binary}"


    for run in $(seq 1 1); do
        for nSta in $(seq 100 100); do
            it=16
            tt=8
            if [ "$mode" = "uora" ]; then
                logDir="$PWD/local_${mode}_${ocw}/${run}-${nSta}-${raru}"
            elif [ "$mode" = "cmab" ]; then
                logDir="$PWD/local_${mode}/${cmab_alg}_${cmab_reward}/${run}-${nSta}"
            else
                logDir="$PWD/local_${mode}/${run}-${nSta}"
            fi
            ./../ns3 run --no-build --gdb \
                "scratch/conference_when2usewhat/conference_when2usewhat \
                --simulationTime=8 \
                --nStationsToJoin=${tt} \
                --totalNStations=${nSta} \
                --initNStations=${it} \
                --RngRun=${run} \
                --logDir=$logDir \
                --enablePcap=true \
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
        --simType=UORA
        --useMuEdca=true
        --muSchedAccessReqInterval=64
        --DelayAccessReqUponAccess=true
        --scheduler=ns3::UoraMultiUserScheduler
        --nRaRus=${raru}
        --OCwMin=${ocw}
    "
}

cmab() {
    : "${CMAB_ALG:=CUCB}"
    : "${CMAB_REWARD:=Binary}"
    : "${CMAB_UCB_C:=1.41421}"
    : "${CMAB_EPSILON:=0.1}"
    : "${CMAB_EXP3_GAMMA:=0.1}"
    export CMAB_ALG CMAB_REWARD
    run_simulation "cmab" "
        ${BASE_OFDMA}
        --simType=UORA \
        --useMuEdca=true \
        --muSchedAccessReqInterval=64 \
        --DelayAccessReqUponAccess=true \
        --muEdcaTimer=8192 \
        --scheduler=ns3::CmabMultiUserScheduler \
        --nRaRus=0 \
        --cmabAlgorithm=${CMAB_ALG} \
        --cmabRewardType=${CMAB_REWARD} \
        --cmabUcbConstant=${CMAB_UCB_C} \
        --cmabEpsilon=${CMAB_EPSILON} \
        --cmabExp3Gamma=${CMAB_EXP3_GAMMA}
    "
}

# ------- Main logic -------
#
usage() {
    echo "Usage: $0 {edca|a2p|a2pv2|uora|cmab}"
    echo "  cmab mode honours CMAB_ALG / CMAB_REWARD / CMAB_UCB_C / CMAB_EPSILON / CMAB_EXP3_GAMMA env vars."
    exit 1
}

if [[ $# -ne 1 ]]; then
    usage
fi

case "$1" in
    edca|a2p|a2pv2|uora|cmab)
        "$1"
        ;;
    *)
        usage
        ;;
esac
