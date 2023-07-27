#!/bin/bash

set -e

#export 'NS_LOG=*=level_all|prefix_func|prefix_time' # AGGR-MU-BAR NO-OFDMA
#only edca := phyModel=Yans, dlAckType=NO-OFDMA, useEdca=true
#only ofdma with muedca := phyModel=Spectrum, dlAckType=AGGR-MU-BAR,
#                          useEdca=false,
# change the file name accordindly if possible
#
# 
    for run in $(seq 1 1); do
        for mcs in $(seq 0 11); do
            for nSta in $(seq 1 8); do
                ./../../ns3 run --no-build "wifi-ax-veloce --simulationTime=5 --nStations=$nSta  \
                    --accessCategory=AC_VO --phyModel=Yans --channelWidth=20 --mcs=$mcs \
                    --dlAckType=NO-OFDMA --enableUlOfdma=true --enableBsrp=true --useRts=false \
                    --logDir=$PWD/results/$run-withEdca-$nSta-mcs$mcs --ulPayloadSize=740 \
                    --dlPayloadSize=500 --interval=0.005 --maxDistance=40 --useEdca=false \
                    --muSchedAccessReqInterval=1ms --txPowerStart=32.0412 --txPowerEnd=32.0412"  #> limits_output_MAC_$mcs-$nSta.txt 2>&1
                done
        done
    done
