#!/bin/bash
# A2Pv2 experiment: parameters from your A2Pv2 set

set -e

module purge
ml GCC/13.3.0

read $(echo "$1" | tr ',' ' ') < <(echo $2 | tr ',' ' ')

NS3_BIN="$VSC_DATA/ns-3/ns3-when2usewhat/ns3"
OUT_BASE="$VSC_DATA/ns-3/ns3-when2usewhat/when2usewhat_output/data"

typeTwoNStations=${nSta}
typeOneNStations=8

logDir="${OUT_BASE}/a2pv2_run/run-${run}_nSta-${nSta}"
mkdir -p "$logDir"

"$NS3_BIN" run --no-build "scratch/wifi-ax-when2usewhat/wifi-ax-when2usewhat \
  --simulationTime=8 \
  --typeTwoNStations=${typeTwoNStations} \
  --typeOneNStations=${typeOneNStations} \
  --accessCategory=AC_VO \
  \
  --phyModel=Spectrum \
  --channelWidth=40 \
  --mcs=8 \
  --RngRun=${run} \
  --dlAckType=AGGR-MU-BAR \
  \
  --enableUlOfdma=true \
  --enableBsrp=false \
  --useRts=false \
  --useA2Pv2=1 \
  \
  --logDir=${logDir} \
  \
  --ulPayloadSize=1700 \
  --interval=0.00208 \
  --maxDistance=40 \
  \
  --useMuEdca=true \
  --muSchedAccessReqInterval=128 \
  \
  --txPowerStart=40.0412 \
  --txPowerEnd=40.0412 \
  --UseCentral26TonesRus=true \
  --startLogTime=3 \
  \
  --DelayAccessReqUponAccess=true \
  --nMpdus=0 \
  --nMsdus=10 \
  --enableAggregation=false \
  --OCwMin=3 \
  \
  --ruAllocationType=ru-26-tone \
  --Scheduler=ns3::RrMultiUserScheduler \
  \
  --LongerEdcaDisable=false \
  --muEdcaTimer=8192 \
  --nRaRus=3"
