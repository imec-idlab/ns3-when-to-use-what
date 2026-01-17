#!/usr/bin/env bash

set -euo pipefail

MODE="${1:?MODE not set}"
HEADER="${2:?HEADER missing}"
ROW="${3:?ROW missing}"

read $(echo "$HEADER" | tr ',' ' ') < <(echo "$ROW" | tr ',' ' ')

export NS_LOG=""

: "${run:?Missing run}"
: "${nStationsToJoin:?Missing nStationsToJoin}"

nSta=$((8 + nStationsToJoin))

BASE_ARGS="
    --simulationTime=30
    --RngRun=${run}
    --logDir=/data/antwerpen/208/vsc20879/${MODE}/${run}_run-${nSta}_sta
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
    --muSchedAccessReqInterval=128
    --scheduler=ns3::VlceMultiUserScheduler
    "

run_simulation() {
  local extra_args="$1"

  $VSC_DATA/ns3-when2usewhat/ns3 run --no-build \
                    "scratch/conference_when2usewhat/conference_when2usewhat \
                    --nStationsToJoin=${nStationsToJoin} \
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
    run_simulation "a2p" "
        ${BASE_A2P}
        --simType=A2P
    "
}

a2pv2() {
    run_simulation "a2pv2" "
         ${BASE_A2P}
         --enableBsrp=false
         --simType=A2PV2
    "
}

uora() {
    run_simulation "uora" "
        ${BASE_OFDMA}
        --simType=EDCA \
        --useMuEdca=true \
        --muSchedAccessReqInterval=34 \
        --DelayAccessReqUponAccess=true \
        --LongerEdcaDisable=true \
        --muEdcaTimer=8192 \
        --scheduler=ns3::UoraMultiUserScheduler
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
