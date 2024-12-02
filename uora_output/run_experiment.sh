#!/bin/bash

set -e

export NS_LOG=""
#MultiUserScheduler:HeFrameExchangeManager"
#:HeFrameExchangeManager"
#VlceMultiUserScheduler:WifiDefaultAckManager:QosFrameExchangeManager
#export 'NS_LOG=*=level_all|prefix_func|prefix_time' # AGGR-MU-BAR NO-OFDMA
#only edca := phyModel=Yans, dlAckType=NO-OFDMA, useMuEdca=false
#only ofdma with no muedca(ofmda+edca) := phyModel=Spectrum, dlAckType=AGGR-MU-BAR,
#                          useMuEdca=false, scheduler =VlceMultiUserScheduler|VlceMultiUserScheduler, used the standard without
#                          disabling muedca
#ofdma only === disable edca after sending initial packet with edca
# change the file name accordindly
#
#
#
    for run in $(seq 9 9); do
        for pMean in $(seq 5 5); do
            for nSta in $(seq 20 20); do
                tt=20
                it=0
                ./../ns3 run --gdb --no-build "scratch/wifi-ax-uora/wifi-ax-uora --simulationTime=8 \
                    --totalNStations=${nSta}  \
                    --accessCategory=AC_VO --phyModel=Spectrum --channelWidth=40 --mcs=8 --RngRun=${run} \
                    --initNStations=${it} \
                    --dlAckType=AGGR-MU-BAR --enableUlOfdma=true --enableBsrp=true --useRts=false \
                    --nStationsToJoin=${tt} --simType=OFDMA+EDCA \
                    --logDir=$PWD/UORA/${run}-${nSta}-${pMean} --ulPayloadSize=740 \
                    --dlPayloadSize=500 --interval=0.005 --maxDistance=40 --useMuEdca=true \
                    --muSchedAccessReqInterval=512 --txPowerStart=40.0412 --txPowerEnd=40.0412 \
                    --UseCentral26TonesRus=true --StartSendInterval=0.001 --startLogTime=0 \
                    --DelayAccessReqUponAccess=true --strictWindow=true --nMpdus=0 --nMsdus=10 \
                    --enableAggregation=true --ruAllocationType=ru-26-tone \
                    --scheduler=ns3::RrMultiUserScheduler --scenario=1 --poissonMean=${pMean} \
                    --nRaRus=3" #> log_output.txt 2>&1 #--TxOPLimits=3200"  > interval_output_$mcs-$nSta.txt 2>&1
                done
        done
    done
