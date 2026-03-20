#!/usr/bin/env bash
set -euo pipefail
MODE="${1:?MODE not set}"
HEADER="${2:?HEADER missing}"
ROW="${3:?ROW missing}"
read $(echo "$HEADER" | tr ',' ' ') < <(echo "$ROW" | tr ',' ' ')
initNStations=8
: "${run:?Missing run}"
: "${nStationsToJoin:?Missing nStationsToJoin}"
nStations=$((initNStations + nStationsToJoin))
OCwMin="${OCwMin:-7}"
nRaRus="${nRaRus:-0}"
logDir=$VSC_DATA/ns3/ns3-when2usewhat/when2usewhat_output/xr_when2usewhat_out/${MODE}/run_${run}_sta_${nStations}
BASE_ARGS="
  --simulationTime=10
  --startLogTime=1.030
  --logDir=${logDir}
  --nStations=${nStations}
  --frequency=5
  --channelWidth=40
  --guardInterval=800
  --mcs=8
  --enableShadowing=false
  --txPower=40.0412
  --useExtendedBlockAck=false
  --enableUlOfdma=true
  --enableBsrp=true
  --useMuEdca=false
  --nMsdus=1
  --nMpdus=1
  --DelayAccessReqUponAccess=false
  --TxOPLimits=2080
  --OCwMin=${OCwMin}
  --OCwMax=127
  --muEdcaTimer=8192
  --enableAggregation=false
"
run_simulation() {
  local extra_args="$1"
  $VSC_DATA/ns3/ns3-when2usewhat/ns3 run --no-build \
    "scratch/xr_when2usewhat/xr_when2usewhat \
     ${BASE_ARGS} \
     ${extra_args}"
}
edca() {
  run_simulation "
    --nRaRus=0
    --dlAckType=NO-OFDMA
    --useMuEdca=false
    --Scheduler=ns3::RrMultiUserScheduler
    --phyModel=Yans
  "
}
ofdma() {
  run_simulation "
    --nRaRus=0
    --phyModel=Spectrum
    --dlAckType=AGGR-MU-BAR
    --useMuEdca=true
    --Scheduler=ns3::RrMultiUserScheduler
    --muSchedAccessReqInterval=0
    --ruAllocationType=ru-26-tone
  "
}
a2p() {
  run_simulation "
    --nRaRus=0
    --phyModel=Spectrum
    --dlAckType=AGGR-MU-BAR
    --useMuEdca=true
    --Scheduler=ns3::VlceMultiUserScheduler
    --muSchedAccessReqInterval=0
    --ruAllocationType=ru-26-tone
  "
}
a2pv2() {
  run_simulation "
    --nRaRus=0
    --phyModel=Spectrum
    --dlAckType=AGGR-MU-BAR
    --useMuEdca=true
    --useA2Pv2=true
    --muSchedAccessReqInterval=0
    --ruAllocationType=ru-26-tone
  "
}
uora() {
  run_simulation "
    --nRaRus=${nRaRus}
    --phyModel=Spectrum
    --dlAckType=AGGR-MU-BAR
    --useMuEdca=true
    --Scheduler=ns3::UoraMultiUserScheduler
    --muSchedAccessReqInterval=0
    --ruAllocationType=ru-26-tone
  "
}
case "${MODE}" in
    edca|ofdma|a2p|a2pv2|uora)
        "${MODE}"
        ;;
    *)
        echo "Unknown mode: ${MODE}"
        exit 1
        ;;
esac
