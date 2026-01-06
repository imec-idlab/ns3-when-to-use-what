#!/bin/bash

logDir="results_xr_a2pv2"
nStations=10
mcs=11
channelWidth=80
run=1

mkdir -p ${logDir}

./../ns3 run scratch/xr_when2usewhat/xr_when2usewhat --no-build -- \
  --simulationTime=10 \
  --nStations=10 \
  --logDir=results_xr_a2pv2 \
  --frequency=6 \
  --channelWidth=80 \
  --mcs=11 \
  --phyModel=Spectrum \
  --txPower=23.0 \
  --dlAckType=AGGR-MU-BAR \
  --Scheduler=ns3::VlceMultiUserSchedulerNoBsrp \
  --useA2Pv2=true \
  --enableUlOfdma=true \
  --enableBsrp=false \
  --useMuEdca=true \
  --muEdcaTimer=40960 \
  --LongerEdcaDisable=true \
  --TxOPLimits=2080 \
  --nRaRus=0 \
  --ruAllocationType=ru-26-tone \
  --UseCentral26TonesRus=true \
  --DelayAccessReqUponAccess=true \
  --startLogTime=1.03 \
  --OCwMin=7 \
  --OCwMax=127 \
  --nMsdus=1 \
  --nMpdus=1 \
  --useExtendedBlockAck=true
