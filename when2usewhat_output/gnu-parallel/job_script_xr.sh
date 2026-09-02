#!/usr/bin/env bash

set -euo pipefail

MODE="${1:?MODE not set}"
HEADER="${2:?HEADER missing}"
ROW="${3:?ROW missing}"

read $(echo "$HEADER" | tr ',' ' ') < <(echo "$ROW" | tr ',' ' ')

export NS_LOG=""

: "${run:?Missing run}"
: "${nSta:?Missing nSta}"   # total number of XR stations

if [ "$MODE" = "uora" ]; then
    : "${nRaRus:?Missing nRaRus}"
    : "${OCwMin:?Missing OCwMin}"
    logDir=/data/antwerpen/208/vsc20879/xr_data/${MODE}/ocwMin_${OCwMin}/${run}_run-${nSta}_sta-${nRaRus}_rarus
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
    logDir=/data/antwerpen/208/vsc20879/xr_data/${MODE}/${algorithm}_${rewardType}${hpTag}/${run}_run-${nSta}_sta
else
    logDir=/data/antwerpen/208/vsc20879/xr_data/${MODE}/${run}_run-${nSta}_sta
fi


# Per-headset-count RU (low-load efficiency): at 160 MHz a 996-tone RU is 80 MHz
# and there are 2 of them, so <=2 headsets each get 80 MHz instead of a 40 MHz
# 484-tone. From 3 headsets up we keep the settled 484-tone (4 RUs, one per
# headset up to 4, round-robin beyond), so the high-load capacity behavior is
# unchanged. (ru-2x996-tone / full 160 MHz for a single headset is not wired in
# the sim, so 1 headset uses one 996-tone = 80 MHz.)
if [ "$nSta" -le 2 ]; then
    RU_ALLOC=ru-996-tone
else
    RU_ALLOC=ru-484-tone
fi

BASE_ARGS="
    --simulationTime=30
    --RngRun=${run}
    --logDir=${logDir}
    --nStations=${nSta}
    --nMpdus=256
    --nMsdus=8
    --channelWidth=160
    --ruAllocationType=${RU_ALLOC}
    --startLogTime=2.0
    --edcaPrime=true
    --videoFrameBound=33
    --audioDeadline=30
    --poseDeadline=10
    "

# Spectrum + UL-OFDMA are non-default; dlAckType, UseCentral26TonesRus,
# DelayAccessReqUponAccess are already defaults and left implicit.
BASE_OFDMA="
    --phyModel=Spectrum
    --enableUlOfdma=true
    "

BASE_A2P="
    ${BASE_OFDMA}
    --Scheduler=ns3::VlceMultiUserScheduler
    "

run_simulation() {
  local extra_args="$1"

  $VSC_DATA/ns3-when2usewhat/ns3 run --no-build \
                    "scratch/xr_when2usewhat/xr_when2usewhat \
                    ${BASE_ARGS} \
                    ${extra_args}"
}

edca() {
  run_simulation "
    --dlAckType=NO-OFDMA
    --useMuEdca=false
  "
}

a2p() {
    run_simulation "
        ${BASE_A2P}
        --muSchedAccessReqInterval=128
        --ns3::VlceMultiUserScheduler::BsrpPrioritizeEmpty=true
        --ns3::VlceMultiUserScheduler::PrioritizeByAc=true
        --ns3::VlceMultiUserScheduler::DownlinkAware=true
        --ns3::QosFrameExchangeManager::TrackBufferDrain=true
    "
}

a2pv2() {
    run_simulation "
         ${BASE_A2P}
         --enableBsrp=false
         --muSchedAccessReqInterval=256
         --ns3::VlceMultiUserScheduler::FilterByBsr=false
         --ns3::VlceMultiUserScheduler::PrioritizeByAc=false
         --ns3::VlceMultiUserScheduler::DownlinkAware=true
    "
}

uora() {
    run_simulation "
        ${BASE_OFDMA}
        --muSchedAccessReqInterval=16 \
        --Scheduler=ns3::UoraMultiUserScheduler \
        --OCwMin=${OCwMin} \
        --nRaRus=${nRaRus} \
        --ns3::UoraMultiUserScheduler::BsrpPrioritizeEmpty=true \
        --ns3::UoraMultiUserScheduler::PrioritizeByAc=true \
        --ns3::UoraMultiUserScheduler::DownlinkAware=true \
        --ns3::QosFrameExchangeManager::TrackBufferDrain=true
    "
    # DownlinkAware is safe for UORA here because BASE_ARGS enables --edcaPrime:
    # STAs arm MU-EDCA during warm-up (EDCA off before XR), which removes the
    # asynchronous UL that otherwise races a DL-first TX (SendNormalAck while the
    # PHY is in TX -> "Invalid WifiPhy state"). Verified crash-free across a
    # seeds x OCwMin scan at the sensitive nRaRus=18, nSta=6 point.
}

cmab() {
    run_simulation "
        ${BASE_OFDMA}
        --muSchedAccessReqInterval=16 \
        --Scheduler=ns3::CmabMultiUserScheduler \
        --cmabAlgorithm=${algorithm} \
        --cmabRewardType=${rewardType} \
        --cmabUcbConstant=${ucbConstant} \
        --cmabEpsilon=${epsilon} \
        --cmabExp3Gamma=${exp3Gamma} \
        --ns3::CmabMultiUserScheduler::DownlinkAware=true
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
