#!/bin/bash
#--nRaRus=${nRaRus} --pMean=${pMean} --OCwMin=${OCwMin}

module purge
ml calcua/supported
ml GCC/13.3.0

read $(echo "$1" | tr ',' ' ') < <(echo $2 | tr ',' ' ')

$VSC_DATA/ns3-veloce/ns3 run --no-build "scratch/wifi-ax-when2usewhat/wifi-ax-when2usewhat \
  --simulationTime=30 --typeTwoNStations=${nSta} --RngRun=${run} \
  --accessCategory=AC_VO --phyModel=Yans --channelWidth=20 --mcs=8 \
  --enableUlOfdma=true --enableBsrp=true --useRts=false \
  --logDir=/data/antwerpen/208/vsc20879/edca_output_2/${run}_run-${nSta}_sta \
  --ulPayloadSize=1700 --interval=0.00208 --maxDistance=40 --OCwMin=3 \
  --useMuEdca=false --muSchedAccessReqInterval=16 --txPowerStart=40.0412 \
  --txPowerEnd=40.0412 --UseCentral26TonesRus=true --TxOPLimits=2080 \
  --startLogTime=5 --DelayAccessReqUponAccess=true  #--nRaRus=0 --pMean=5 \
  --enableAggregation=true --ruAllocationType=ru-26-tone --activateNaiks=false \
  --LongerEdcaDisable=true --Scheduler=ns3::RrMultiUserScheduler --muEdcaTimer=8192"
