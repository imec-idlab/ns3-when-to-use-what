#!/bin/bash

module purge
ml calcua/supported
ml GCC/9.3.0
ml atools/slurm

# specification (required!)
#SBATCH --ntasks=1 --cpus-per-task=1 --mem-per-cpu=2g

# requested running time (required!)
#SBATCH --time=50:00

#
# send mail notification (optional)
#   FAIL   when job is aborted
#   BEGIN  when job begins
#   END    when job ends
#   ... and more, see the manual page of sbatch.
#SBATCH --mail-type=ALL
#SBATCH --mail-user=douglas.agbeve@uantwerpen.be

source <(aenv --data edca.csv)

./../../ns3 run --no-build "wifi-ax-veloce --simulationTime=20 --nStations=$nStations  \
                    --accessCategory=AC_VO --phyModel=Spectrum --channelWidth=20 --mcs=$mcs \
                    --dlAckType=AGGR-MU-BAR --enableUlOfdma=true --enableBsrp=true --useRts=false \
		    --logDir=$PWD/OFDMA_only_DL/$run-withEDCA-$nStations-mcs$mcs --ulPayloadSize=740 \
                    --dlPayloadSize=500 --interval=0.005 --maxDistance=40 --useMuEdca=true \
                    --muSchedAccessReqInterval=0.1ms --txPowerStart=32.0412 --txPowerEnd=32.0412 \
		    --UseCentral26TonesRus=true --StartSendInterval=0.001 --startLogTime=0.3" > /dev/null
