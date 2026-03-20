slurm logs can be found in when2usewhat_output/bugs

slurm-3240229.out:
aborted. cond="bandwidth != 160 || nStations != 1, +1.035214670s 10 file=/data/antwerpen/211/vsc21159/ns3/ns3-when2usewhat/src/wifi/model/he/he-ru.cc, line=834

Originally, I had set ru-undefined for all the runs because I assumed it would dynamically allocate ru's. 
Then I got the error above. I think its because no ru type fits the number of stations dynamically. 
I was able to fix it by setting ruAllocationType=ru-26-tone.


slurm-3243331.out and slurm-3243650.out:
NS_ASSERT failed, cond="!m_wifiPhy->m_currentEvent", +1.144033317s 11 file=/data/antwerpen/211/vsc21159/ns3/ns3-when2usewhat/src/wifi/model/phy-entity.cc, line=536

This failed for the a2p run with 30 stations and almost all of the uora runs (which have a high station count). 
I'm assuming the PHY expects m_currentEvent to be null when in IDLE state, but there is still a stale event pointer. 
But I'm not sure.


UoraMultiUserScheduler::ComputeDlMuInfo() in uora-multi-user-scheduler.cc:
NS_ASSERT failed, cond="ret", msg="Weird that an MPDU does not meet constraints when transmitted over a larger RU", +1.057707076s 9 file=/data/antwerpen/211/vsc21159/ns3/ns3-when2usewhat/src/wifi/model/he/uora-multi-user-scheduler.cc, line=1038

I think the initial candidates are selected in TrySendingDlMuPpdu based on the input stations which calculates the ru/tone type based on the expected station count, 
but only stations with frames are added to m_candidates. Then later FinalizeTxVector computes the tone type again with m_candidates, which is only the candidates with frames, 
which could be smaller. So we have a larger ru type.

So the MPDUs were validated against the smaller ru type in TrySendingDlMuPpdu but then re-validated against the larger ru type in ComputeDlMuInfo, which fails.

Though if you set ru-26-tone, it gets fixed. You can reproduce this by running the parameters from bug_test.sh in terminal from root, which you can find in  when2usewhat_output/bugs 
Also I have added logs to the uora multi user scheduler so you can see the tones and candidates change as well as the log from running the bug_test.sh, where you can see this happening.
The logs are also in the bugs dir.
