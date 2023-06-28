#!/bin/bash

set -e

#export 'NS_LOG=*=level_all|prefix_func|prefix_time'

    for run in $(seq 1 1); do
        for mcs in $(seq 11 11); do
            for nSta in $(seq 8 8); do
                ./../../ns3 run --no-build "wifi-ax-edca --simulationTime=2 --nStations=$nSta  --accessCategory=AC_VO --phyModel=Yans --channelWidth=20 --mcs=$mcs \
                    --dlAckType=NO-OFDMA --enableUlOfdma=false --enableBsrp=false --useRts=false --logDir=$PWD/results/$run-withEdca-$nSta-mcs$mcs \
                     --ulPayloadSize=740 --dlPayloadSize=500 --interval=0.005 --maxDistance=40 --txPowerStart=32.0412 --txPowerEnd=32.0412"  #> limits_output_MAC_$mcs-$nSta.txt 2>&1
                done
        done
    done
