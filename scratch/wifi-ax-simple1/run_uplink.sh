#!/bin/bash

set -e

#export 'NS_LOG=*=level_all|prefix_func|prefix_time'

for run in $(seq 1 1); do
    for mcs in $(seq 11 11); do
        for nSta in $(seq 8 8); do
            ./../../ns3 run --no-build "wifi-ax-simple1 --RngRun=$run --simulationTime=3 --nStations=$nSta --downlink=false --accessCategory=AC_VO --phyModel=Spectrum --channelWidth=20 --mcs=$mcs \
                    --dlAckType=AGGR-MU-BAR --enableUlOfdma=true --enableBsrp=true --useRts=false --logDir=$PWD/results_edcaofdma/$run-uplink-withOfdma-$nSta-mcs$mcs \
                    --udp=true --payloadSize=740 --trafficType=CBR --interval=0.005 --muSchedAccessReqInterval=1ms --disableStaEdca=false --ns3::QosFrameExchangeManager::SetQueueSize=true"  #> output_RU_alloc_$mcs-$nSta.txt
        done
    done
done
