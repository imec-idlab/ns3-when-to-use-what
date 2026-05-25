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

if [ "$MODE" = "uora" ]; then
    : "${nRaRus:?Missing nRaRus}"
    : "${OCwMin:?Missing OCwMin}"
    logDir=/scratch/antwerpen/208/vsc20879/${MODE}/ocwMin_${OCwMin}/${run}_run-${nSta}_sta-${nRaRus}_rarus
elif [ "$MODE" = "cmab" ]; then
    : "${algorithm:?Missing algorithm (CUCB|ThompsonSampling|EpsilonGreedy|EXP3M)}"
    : "${rewardType:?Missing rewardType (Binary|FairnessWeighted)}"
    : "${ucbConstant:=1.41421}"   # sqrt(2), used only by CUCB
    : "${epsilon:=0.1}"           # used only by EpsilonGreedy
    : "${exp3Gamma:=0.1}"         # used only by EXP3M
    # Append a hyperparameter tag only for algorithms that actually use one,
    # so ThompsonSampling / default-HP runs get clean paths.
    case "${algorithm}" in
        CUCB)          hpTag="_c${ucbConstant}" ;;
        EpsilonGreedy) hpTag="_e${epsilon}"     ;;
        EXP3M)         hpTag="_g${exp3Gamma}"   ;;
        *)             hpTag=""                 ;;
    esac
    logDir=/scratch/antwerpen/208/vsc20879/${MODE}/${algorithm}_${rewardType}${hpTag}/${run}_run-${nSta}_sta
else
    logDir=/scratch/antwerpen/208/vsc20879/${MODE}/${run}_run-${nSta}_sta
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

cmab() {
    run_simulation "
        ${BASE_OFDMA}
        --simType=UORA \
        --useMuEdca=true \
        --muSchedAccessReqInterval=64 \
        --DelayAccessReqUponAccess=true \
        --muEdcaTimer=8192 \
        --scheduler=ns3::CmabMultiUserScheduler \
        --nRaRus=0 \
        --cmabAlgorithm=${algorithm} \
        --cmabRewardType=${rewardType} \
        --cmabUcbConstant=${ucbConstant} \
        --cmabEpsilon=${epsilon} \
        --cmabExp3Gamma=${exp3Gamma}
    "
}

# -
#
usage() {
    echo "Usage: {edca|a2p|a2pv2|uora|cmab} | Unknown mode: ${MODE}"
    exit 1
}


case "${MODE}" in
    edca|a2p|a2pv2|uora|cmab)
        "${MODE}"
        ;;
    *)
        usage
        ;;
esac
