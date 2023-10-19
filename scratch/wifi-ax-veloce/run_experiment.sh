#!/bin/bash

set -e

#export 'NS_LOG=*=level_all|prefix_func|prefix_time' # AGGR-MU-BAR NO-OFDMA
#only edca := phyModel=Yans, dlAckType=NO-OFDMA, *useEdca=true*
#only ofdma with muedca := phyModel=Spectrum, dlAckType=AGGR-MU-BAR,
#                          useEdca=true,
# change the file name accordindly
#
#
    for run in $(seq 1 1); do
        for mcs in $(seq 4 4); do
            for nSta in $(seq 10 10); do
                echo "${mcs} ${nSta}:"
                ./../../ns3 run --no-build "scratch/wifi-ax-veloce/wifi-ax-veloce --simulationTime=2 --nStations=$nSta  \
                    --accessCategory=AC_VO --phyModel=Spectrum --channelWidth=20 --mcs=$mcs --RngRun=$run \
                    --dlAckType=AGGR-MU-BAR --enableUlOfdma=true --enableBsrp=true --useRts=false \
                    --logDir=$PWD/result_ofdma_strict/${run}runs-${nSta}Stations-mcs$mcs --ulPayloadSize=740 \
                    --dlPayloadSize=500 --interval=0.005 --maxDistance=40 --useMuEdca=true \
                    --muSchedAccessReqInterval=0.0001 --txPowerStart=32.0412 --txPowerEnd=32.0412 \
                    --UseCentral26TonesRus=false --StartSendInterval=0.001 --startLogTime=0.0 \
                    --DelayAccessReqUponAccess=false --strictWindow=true --nMsdus=10 --nMpdus=10 \
                    --enableAggregation=true --TxOPLimits=4160" # > interval_output_$mcs-$nSta.txt 2>&1
                done
        done
    done
