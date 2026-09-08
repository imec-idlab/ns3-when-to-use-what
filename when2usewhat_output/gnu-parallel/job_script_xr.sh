#!/usr/bin/env bash

set -euo pipefail

MODE="${1:?MODE not set}"
HEADER="${2:?HEADER missing}"
ROW="${3:?ROW missing}"

read $(echo "$HEADER" | tr ',' ' ') < <(echo "$ROW" | tr ',' ' ')

export NS_LOG=""

: "${run:?Missing run}"
: "${nSta:?Missing nSta}"   # total number of XR stations

# ARI (Access Request Interval) sweep: MODE=<scheme>_ari (e.g. a2p_ari) reuses
# the <scheme> function below but reads --muSchedAccessReqInterval from the CSV
# column "ari" instead of the scheme's fixed default, and writes to a SEPARATE
# data root (xr_data_ari/) so it never collides with the baseline xr_data/
# sweep, which already fixed ARI per scheme. EDCA has no OFDMA scheduler and is
# therefore not swept over ari.
BASE_MODE="${MODE%_ari}"
if [[ "$MODE" == *_ari ]]; then
    : "${ari:?Missing ari}"
    DATA_ROOT=/data/antwerpen/208/vsc20879/xr_data_ari
    ARI_SEG="ari_${ari}/"
else
    DATA_ROOT=/data/antwerpen/208/vsc20879/xr_data
    ARI_SEG=""
fi

if [ "$BASE_MODE" = "uora" ]; then
    : "${nRaRus:?Missing nRaRus}"
    : "${OCwMin:?Missing OCwMin}"
    logDir=${DATA_ROOT}/${BASE_MODE}/${ARI_SEG}ocwMin_${OCwMin}/${run}_run-${nSta}_sta-${nRaRus}_rarus
elif [ "$BASE_MODE" = "cmab" ]; then
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
    logDir=${DATA_ROOT}/${BASE_MODE}/${ARI_SEG}${algorithm}_${rewardType}${hpTag}/${run}_run-${nSta}_sta
else
    logDir=${DATA_ROOT}/${BASE_MODE}/${ARI_SEG}${run}_run-${nSta}_sta
fi


# DL-only per-headset-count RU (low-load efficiency). The UPLINK always keeps
# 484-tone (4 RUs), so UORA random-access RUs and the UL pose flow are never
# starved. The DOWNLINK uses a 996-tone RU (80 MHz, 2 RUs) for <=2 headsets so
# few headsets get more of the band on DL, and 484-tone (4 RUs) from 3 headsets
# up (settled high-load config, unchanged). (ru-2x996-tone / full 160 MHz for a
# single headset is not wired in the sim, so 1 headset uses one 996-tone = 80 MHz.)
if [ "$nSta" -le 2 ]; then
    DL_RU_ALLOC=ru-996-tone
else
    DL_RU_ALLOC=ru-484-tone
fi

BASE_ARGS="
    --simulationTime=30
    --RngRun=${run}
    --logDir=${logDir}
    --nStations=${nSta}
    --nMpdus=256
    --nMsdus=8
    --channelWidth=160
    --ruAllocationType=ru-484-tone
    --dlRuAllocationType=${DL_RU_ALLOC}
    --startLogTime=4.0
    --edcaPrime=true
    --videoFrameBound=50
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
        --muSchedAccessReqInterval=${ari:-128}
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
         --muSchedAccessReqInterval=${ari:-256}
         --ns3::VlceMultiUserScheduler::FilterByBsr=false
         --ns3::VlceMultiUserScheduler::PrioritizeByAc=false
         --ns3::VlceMultiUserScheduler::DownlinkAware=true
    "
}

uora() {
    run_simulation "
        ${BASE_OFDMA}
        --muSchedAccessReqInterval=${ari:-16} \
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
        --muSchedAccessReqInterval=${ari:-16} \
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
    echo "Usage: {edca|a2p|a2pv2|uora|cmab}[_ari] | Unknown mode: ${MODE}"
    exit 1
}


case "${BASE_MODE}" in
    edca|a2p|a2pv2|uora|cmab)
        "${BASE_MODE}"
        ;;
    *)
        usage
        ;;
esac
