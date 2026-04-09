#!/usr/bin/env bash

set -euo pipefail

MODE="${1:?MODE not set}"
HEADER="${2:?HEADER missing}"
ROW="${3:?ROW missing}"

read $(echo "$HEADER" | tr ',' ' ') < <(echo "$ROW" | tr ',' ' ')

export NS_LOG=""

: "${run:?Missing run}"
: "${typeTwoNStations:?Missing typeTwoNStations}"


if [ "$MODE" = "uora" ]; then
    : "${nRaRus:?Missing OCwMin}"
    : "${OCwMin:?Missing OCwMin}"
    logDir=/scratch/antwerpen/208/vsc20879/iiot/${MODE}/ocwMin_${OCwMin}/${run}_run-${typeTwoNStations}_sta-${nRaRus}_rarus
else
    logDir=/scratch/antwerpen/208/vsc20879/iiot/${MODE}/${run}_run-${typeTwoNStations}_sta
fi



BASE_ARGS="
    --simulationTime=30
    --RngRun=${run}
    --logDir=${logDir}
    --enableAggregation=true
    --nMpdus=0
    --nMsdus=10
    --ruAllocationType=ru-26-tone
    --startLogTime=5
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

run_simulation() {
  local extra_args="$1"

  $VSC_DATA/ns3-when2usewhat/ns3 run --no-build \
                    "scratch/conference_when2usewhat/conference_when2usewhat \
                    --typeTwoNStations=${typeTwoNStations} \
                    ${BASE_ARGS} \
                    ${extra_args}"
}

edca() {
  run_simulation "
    --phyModel=Yans
    --simType=EDCA
    --dlAckType=NO-OFDMA
    --useMuEdca=false
  "
}


ofdma() {
    run_simulation "
        ${BASE_OFDMA}
        --simType=OFDMA
        --useMuEdca=true
        --muSchedAccessReqInterval=128
        --scheduler=ns3::RrMultiUserScheduler
    "
}

a2p() {
    run_simulation "
        ${BASE_A2P}
        --muSchedAccessReqInterval=128
        --simType=A2P
    "
}

a2pv2() {
    run_simulation "
         ${BASE_A2P}
         --enableBsrp=false
         --muSchedAccessReqInterval=512
         --simType=A2PV2
    "
}

uora() {
    run_simulation "
        ${BASE_OFDMA}
        --simType=UORA \
        --useMuEdca=true \
        --muSchedAccessReqInterval=64 \
        --DelayAccessReqUponAccess=true \
        --muEdcaTimer=8192 \
        --scheduler=ns3::UoraMultiUserScheduler \
        --OCwMin=${OCwMin} \
        --nRaRus=${nRaRus}
    "
}

# -
#
usage() {
    echo "Usage: {edca|ofdma|a2p|a2pv2|uora} | Unknown mode: ${MODE}"
    exit 1
}


case "${MODE}" in
    edca|ofdma|a2p|a2pv2|uora)
        "${MODE}"
        ;;
    *)
        usage
        ;;
esac
