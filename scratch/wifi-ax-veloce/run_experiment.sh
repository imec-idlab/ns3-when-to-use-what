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
        for mcs in $(seq 5 5); do
            for nSta in $(seq 3 3); do
                echo "${mcs} ${nSta}:"
                ./../../ns3 run --gdb --no-build "wifi-ax-veloce --simulationTime=2 --nStations=$nSta  \
                    --accessCategory=AC_VO --phyModel=Yans --channelWidth=20 --mcs=$mcs --RngRun=$run \
                    --dlAckType=NO-OFDMA --enableUlOfdma=true --enableBsrp=true --useRts=false \
                    --logDir=$PWD/results_edca_only/$run-withEDCA-$nSta-mcs$mcs --ulPayloadSize=740 \
                    --dlPayloadSize=500 --interval=0.005 --maxDistance=40 --useMuEdca=true \
                    --muSchedAccessReqInterval=0.1ms --txPowerStart=32.0412 --txPowerEnd=32.0412 \
                    --UseCentral26TonesRus=true --StartSendInterval=0.001 --startLogTime=0.3 \
                    --downlinkOnly=false" # > limits_output_MAC_$mcs-$nSta.txt 2>&1
                done
        done
    done
