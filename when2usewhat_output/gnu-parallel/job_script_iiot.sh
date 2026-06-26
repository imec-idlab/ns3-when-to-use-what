#!/usr/bin/env bash

set -euo pipefail

MODE="${1:?MODE not set}"
HEADER="${2:?HEADER missing}"
ROW="${3:?ROW missing}"

read $(echo "$HEADER" | tr ',' ' ') < <(echo "$ROW" | tr ',' ' ')

export NS_LOG=""

: "${run:?Missing run}"
: "${typeTwoNStations:?Missing typeTwoNStations}"

nSta=${typeTwoNStations}

# Exponential mean (s) of the stochastic stations' packet generation. Default to
# 0.1 when the CSV has no pMean column. Tag the output path only for non-default
# values, so the nSta-sweep paths (pMean=0.1) stay stable.
pMean="${pMean:-0.1}"
if [ "${pMean}" = "0.1" ]; then pTag=""; else pTag="_pMean-${pMean}"; fi

if [ "$MODE" = "uora" ]; then
    : "${nRaRus:?Missing nRaRus}"
    : "${OCwMin:?Missing OCwMin}"
    logDir=/data/antwerpen/208/vsc20879/iiot_data/${MODE}/ocwMin_${OCwMin}/${run}_run-${nSta}_sta-${nRaRus}_rarus${pTag}
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
    logDir=/data/antwerpen/208/vsc20879/iiot_data/${MODE}/${algorithm}_${rewardType}${hpTag}/${run}_run-${nSta}_sta${pTag}
else
    logDir=/data/antwerpen/208/vsc20879/iiot_data/${MODE}/${run}_run-${nSta}_sta${pTag}
fi



BASE_ARGS="
    --simulationTime=30
    --RngRun=${run}
    --logDir=${logDir}
    --nMpdus=0
    --nMsdus=10
    --ruAllocationType=ru-26-tone
    --startLogTime=5
    --pMean=${pMean}
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
    --maxTimeInList=204800
    "

run_simulation() {
  local extra_args="$1"

  $VSC_DATA/ns3-when2usewhat/ns3 run --no-build \
                    "scratch/iiot_when2usewhat/iiot_when2usewhat \
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
    --enableAggregation=true
  "
}


a2p() {
    run_simulation "
        ${BASE_A2P}
        --muSchedAccessReqInterval=128
        --simType=A2P
        --ns3::VlceMultiUserScheduler::BsrpPrioritizeEmpty=true
        --ns3::VlceMultiUserScheduler::PrioritizeByAc=true
    "
}

a2pv2() {
    run_simulation "
         ${BASE_A2P}
         --enableBsrp=false
         --muSchedAccessReqInterval=256
         --simType=A2PV2
         --ns3::VlceMultiUserScheduler::FilterByBsr=false
         --ns3::VlceMultiUserScheduler::PrioritizeByAc=false
    "
}

uora() {
    run_simulation "
        ${BASE_OFDMA}
        --simType=UORA \
        --useMuEdca=true \
        --muSchedAccessReqInterval=16 \
        --DelayAccessReqUponAccess=true \
        --muEdcaTimer=8192 \
        --scheduler=ns3::UoraMultiUserScheduler \
        --OCwMin=${OCwMin} \
        --nRaRus=${nRaRus} \
        --ns3::UoraMultiUserScheduler::BsrpPrioritizeEmpty=true \
        --ns3::UoraMultiUserScheduler::PrioritizeByAc=true
    "
}

cmab() {
    run_simulation "
        ${BASE_OFDMA}
        --simType=CMAB \
        --useMuEdca=true \
        --muSchedAccessReqInterval=16 \
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
