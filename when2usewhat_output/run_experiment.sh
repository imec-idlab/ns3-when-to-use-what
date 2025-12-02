#!/bin/bash

set -e

export NS_LOG=""

#export 'NS_LOG=*=level_all|prefix_func|prefix_time' # AGGR-MU-BAR NO-OFDMA
#only edca := phyModel=Yans, dlAckType=NO-OFDMA, useMuEdca=false

# change the file name accordindly
#
# you can remove the gdb if you dont want to debug and have not built it with a
# debug function
#
    for run in $(seq 9 9); do
        for nSta in $(seq 20 20); do
            it=8
            ./../ns3 run --no-build "scratch/wifi-ax-when2usewhat/wifi-ax-when2usewhat --simulationTime=8 \
                --typeTwoNStations=${nSta}  --typeOneNStations=${it} --accessCategory=AC_VO --phyModel=Spectrum \
                --channelWidth=40 --mcs=8 --RngRun=${run} --dlAckType=AGGR-MU-BAR --enableUlOfdma=true \
                --enableBsrp=true --useRts=false --logDir=$PWD/data/${run}_run-${nSta}_sta --ulPayloadSize=1700 \
                --interval=0.00208 --maxDistance=40 --useMuEdca=true --muSchedAccessReqInterval=128 \
                --txPowerStart=40.0412 --txPowerEnd=40.0412 --UseCentral26TonesRus=true  --startLogTime=3 \
                --DelayAccessReqUponAccess=true  --nMpdus=0 --nMsdus=10 --enableAggregation=false --OCwMin=3 \
                --ruAllocationType=ru-26-tone --Scheduler=ns3::RrMultiUserScheduler --LongerEdcaDisable=true \
                --muEdcaTimer=8192 --nRaRus=3" #> log_output.txt 2>&1
        done
    done
