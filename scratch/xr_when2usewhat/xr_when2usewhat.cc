#include "ns3/application.h"
#include "ns3/inet-socket-address.h"
#include "ns3/log.h"

#include <cerrno>
#include <cstdint>
#include <cstring>
#include <sstream>
#include <string>
#include <ns3/wifi-module.h>
#include <unistd.h>
#include <vector>
#include "ns3/mobility-helper.h"
#include "ns3/constant-position-mobility-model.h"
#include "ns3/multi-model-spectrum-channel.h"
#include "ns3/packet-sink-helper.h"
#include "ns3/progress-bar.h"
#include "ns3/packet-sink.h"
#include "ns3/packet-tag.h"

#include <fstream>
#include "ns3/wifi-module.h"
#include "ns3/internet-module.h"

#include "ns3/xr-client.h"
#include "ns3/xr-server.h"
#include "ns3/seq-ts-header.h"

#include "ns3/veloce-app-container.h"
#include "ns3/ap-server-helper.h"

using namespace ns3;


struct stats_t {
    double sinr;
    uint64_t totalBeacons;
    uint64_t rxBytes;
    std::vector<double> pktDelays, genTime, rxTime;
    std::vector<uint64_t> pktTag;
    std::vector<Mac48Address> src;

    //late packet parameters
    uint64_t rxBytesLate;
    std::vector<double> pktDelaysLate, genTimeLate, rxTimeLate;
    std::vector<uint64_t> pktTagLate;
    std::vector<Mac48Address> srcLate;
};

std::map<Mac48Address, stats_t> g_statsMap; //!< map for statistics for each station
std::map<Ipv4Address, Mac48Address> g_Ip2Mac; //!< map for mapping IPv4 to MAC address
std::map<Mac48Address, stats_t> g_statsMapAp; //!< map for starts for only AP
void SinrTrace(Mac48Address addr, double sinr) {
    g_statsMap[addr].sinr += sinr;
    g_statsMap[addr].totalBeacons++;
}

void RxTraceWithAddressParam(double logTime, Ptr<const Packet> p, const Address &src, const Address &dst) {
    Ptr<Packet> pkt = p->Copy();

    SeqTsHeader seqTs;
    ns3::PacketTag tag;
    pkt->RemovePacketTag(tag);
    pkt->RemoveHeader(seqTs);
    Time startLogTime = Seconds(logTime);

    if (Simulator::Now().GetSeconds() >= startLogTime.GetSeconds()) {
        g_statsMap[g_Ip2Mac.at(InetSocketAddress::ConvertFrom(src).GetIpv4())].rxBytes += p->GetSize();
        g_statsMap[g_Ip2Mac.at(InetSocketAddress::ConvertFrom(src).GetIpv4())].pktDelays.push_back(
            (Simulator::Now() - seqTs.GetTs()).GetSeconds());
        g_statsMap[g_Ip2Mac.at(InetSocketAddress::ConvertFrom(src).GetIpv4())].pktTag.push_back(tag.GetValue());
        g_statsMap[g_Ip2Mac.at(InetSocketAddress::ConvertFrom(src).GetIpv4())].genTime.push_back(
            seqTs.GetTs().GetSeconds());
        g_statsMap[g_Ip2Mac.at(InetSocketAddress::ConvertFrom(src).GetIpv4())].rxTime.push_back(
            Simulator::Now().GetSeconds());
        g_statsMap[g_Ip2Mac.at(InetSocketAddress::ConvertFrom(src).GetIpv4())].src.push_back(
            g_Ip2Mac.at(InetSocketAddress::ConvertFrom(src).GetIpv4()));
    }
}

int main(int argc, char *argv[]) {
    std::string logDir{"output"};
    double startLogTime = {1.030};
    double simulationTime = 10.0;
    uint32_t nStations = 10;
    uint32_t channelWidth = 80; // 20, 40, 80, 160, 320 MHz
    int mcs = 11; // 4096-QAM for Wi-Fi 7
    std::string Scheduler = "ns3::RrMultiUserScheduler";
    uint32_t nRaRus = 0; // 0 = EDCA, >0 = UORA
    bool useA2Pv2 = false;
    double txPower = 23.0; // From Table II
    std::string frequency = "5"; // From Section C

    double minDistance{1.0}; //meters
    double maxDistance{4.0}; //meters
    double apHeight{3}; //meters
    double staHeight{1}; //meters

    uint32_t guardInterval{800}; //in ns
    std::string phyModel{"Yans"}; //Spectrum or Yans
    bool enableShadowing = false;
    uint32_t nMsdus = 1;
    HeRu::RuType ruAllocType{HeRu::RU_UNDEFINED};
    bool enableAggregation{true}; // todo : should this be true or false?


    std::string dlAckSeqType{"AGGR-MU-BAR"};
    bool enableUlOfdma{false};
    bool enableBsrp{false};
    double accessReqInterval = {0}; //microseconds
    bool useExtendedBlockAck{true};
    bool useMuEdca{true};
    uint32_t nMpdus = 1;
    bool UseCentral26TonesRus = {true};
    bool DelayAccessReqUponAccess = {true};
    double txOpLimits = {2080}; //AC_VO default value in microseconds 2080
    std::string ruAllocationType{"ru-undefined"};
    uint32_t OCwMin{7};
    uint32_t OCwMax{127}; // Should this be lager? 1023?
    bool LongerEdcaDisable{true};
    // double muEdcaTimer{8192 * 5};
    //double maxCredit{1000000}; //amount credit a stations can have when using // todo : check this
    //RrMultiUserScheduler, and how long to disable edca for
    //in VlceMultiUserScheduler in MicroSeconds

    double  muEdcaTimer {8192};
    double maxTimeInList {8192 * 5}; //amount credit a stations can have when using
    //RrMultiUserScheduler, and how long to disable edca for
    //in VlceMultiUserScheduler in MicroSeconds


    CommandLine cmd(__FILE__);
    cmd.AddValue("simulationTime", "Simulation time in seconds", simulationTime);
    cmd.AddValue("logDir", "Directory for the output stats files", logDir);
    cmd.AddValue("nStations", "Total VR stations", nStations);
    cmd.AddValue("nRaRus", "Number of RUs for Random Access (UORA)", nRaRus);
    cmd.AddValue("useA2Pv2", "Use A2P Scheduler", useA2Pv2);

    cmd.AddValue("minDistance", "Minimum distance in meters between the station and the access point", minDistance);
    cmd.AddValue("maxDistance", "Maximum distance in meters between the station and the access point", maxDistance);
    cmd.AddValue("apHeight", "Height of AP [m]", apHeight);
    cmd.AddValue("staHeight", "Height of STA [m]", staHeight);

    //PHY params
    cmd.AddValue("frequency", "Whether working in the 2.4, 5 or 6 GHz band (other values gets rejected)", frequency);
    cmd.AddValue("channelWidth", "Channel width used for transmissions (20, 40, 80, 80+80, 160 MHz)", channelWidth);
    cmd.AddValue("guardInterval", "The value of the guard interval (800, 1600, 3200 ns)", guardInterval);
    cmd.AddValue("mcs", "if set, limit testing to a specific MCS (0-11)", mcs);
    cmd.AddValue("enableShadowing", "Enable/disable gaussian shadowing", enableShadowing);
    cmd.AddValue("UseCentral26TonesRus", "Enable/Disable the use of Cenral 26 tone RUs", UseCentral26TonesRus);
    cmd.AddValue("ruAllocationType",
                 "The type of RUs allocated to STAs, if undefined - dynamically selected based on the number of STAs (ru-26-tone, ru-52-tone)",
                 ruAllocationType);
    cmd.AddValue("nRaRus", "Number of RUs to reserve for Random Access", nRaRus);
    cmd.AddValue(
        "phyModel",
        "PHY model to use when OFDMA is disabled (Yans or Spectrum). If OFDMA is enabled then Spectrum is automatically selected",
        phyModel);
    cmd.AddValue("txPower", "Transmission power in dBm", txPower);

    //MAC params
    cmd.AddValue("useExtendedBlockAck", "Enable/disable use of extended BACK", useExtendedBlockAck);
    cmd.AddValue("dlAckType", "Ack sequence type for DL OFDMA (NO-OFDMA, ACK-SU-FORMAT, MU-BAR, AGGR-MU-BAR)",
                 dlAckSeqType);
    cmd.AddValue("enableUlOfdma", "Enable UL OFDMA (useful if DL OFDMA is enabled and TCP is used)", enableUlOfdma);
    cmd.AddValue("enableBsrp", "Enable BSRP (useful if DL and UL OFDMA are enabled and TCP is used)", enableBsrp);
    cmd.AddValue("muSchedAccessReqInterval",
                 "Duration of the interval between two requests for channel access made by the MU scheduler (MicroSeconds)",
                 accessReqInterval);
    cmd.AddValue("useMuEdca", "Enable/disable Specific EDCA parameters set", useMuEdca);
    cmd.AddValue("nMsdus", "Number of aggregated MSDUs (=< 11398/740 for VHT/HE/EHT PPDUs)", nMsdus);
    cmd.AddValue("nMpdus", "Number of aggregated MPDUs (=< 6500631/740 for HE PPDUs)", nMpdus);
    cmd.AddValue("DelayAccessReqUponAccess", "Enable/Disable delay of access req only upon access grant",
                 DelayAccessReqUponAccess);
    cmd.AddValue("TxOPLimits", "TX Opportunity limits in microseconds", txOpLimits);
    cmd.AddValue("OCwMin", "Min OFDMA CW", OCwMin);
    cmd.AddValue("OCwMax", "Max OFDMA CW", OCwMax);
    cmd.AddValue("Scheduler", "Type resource scheduler to use", Scheduler);
    cmd.AddValue("startLogTime", "Time to begin logging [seconds]", startLogTime);

    cmd.AddValue("useA2Pv2",
                 "If true, use A2Pv2 (VlceMultiUserSchedulerNoBsrp: no BSRP, direct BasicTF).",
                 useA2Pv2); // New, use A2Pv2

    cmd.AddValue("LongerEdcaDisable", "if True, disable EDCA for the duration of simulation", LongerEdcaDisable);
    cmd.AddValue("muEdcaTimer",
                 "How long to disable EDCA for and for VlceMultiUserScheduler, how long to stay in polling list without transmission (in Seconds)",
                 muEdcaTimer);
    cmd.AddValue("enableAggregation", "Enable/disable mpdu/msdu aggregation", enableAggregation);


    cmd.Parse(argc, argv);


    if (useA2Pv2) Scheduler = "ns3::VlceMultiUserSchedulerNoBsrp";
    /*
    * make and change into the lodDir
    */
    std::string mkdir{"mkdir -p " + logDir};
    if (system(mkdir.c_str()) == -1) {
        NS_FATAL_ERROR("Error in creating log directory" << strerror(errno));
    }
    if (chdir(logDir.c_str()) == -1) {
        perror("chdir");
        NS_FATAL_ERROR("Error changing into directory " << strerror (errno));
    }


    /*
     * Downlink ACK type
     * */
    if (dlAckSeqType == "ACK-SU-FORMAT") {
        Config::SetDefault("ns3::WifiDefaultAckManager::DlMuAckSequenceType",
                           EnumValue(WifiAcknowledgment::DL_MU_BAR_BA_SEQUENCE));
    } else if (dlAckSeqType == "MU-BAR") {
        Config::SetDefault("ns3::WifiDefaultAckManager::DlMuAckSequenceType",
                           EnumValue(WifiAcknowledgment::DL_MU_TF_MU_BAR));
    } else if (dlAckSeqType == "AGGR-MU-BAR") {
        Config::SetDefault("ns3::WifiDefaultAckManager::DlMuAckSequenceType",
                           EnumValue(WifiAcknowledgment::DL_MU_AGGREGATE_TF));
    } else if (dlAckSeqType != "NO-OFDMA") {
        NS_ABORT_MSG("Invalid DL ack sequence type (must be NO-OFDMA, ACK-SU-FORMAT, MU-BAR or AGGR-MU-BAR)");
    }

    /*
     * PHY model
     */
    if (phyModel != "Yans" && phyModel != "Spectrum") {
        NS_ABORT_MSG("Invalid PHY model (must be Yans or Spectrum)");
    }


    /*
     * Type of resource unit tones
     */
    if (ruAllocationType == "ru-26-tone")
        ruAllocType = HeRu::RU_26_TONE;
    else if (ruAllocationType == "ru-52-tone")
        ruAllocType = HeRu::RU_52_TONE;


    /*
    * Create totalNStations of STA and 1 AP
    */

    NodeContainer wifiStaNodes;
    wifiStaNodes.Create(nStations);
    NodeContainer wifiApNode;
    wifiApNode.Create(1);

    /*
    * Mobility and Positioning: Constant mobility and randomly distributed nodes around AP
    */
    MobilityHelper staMobility;
    Ptr<UniformDiscPositionAllocator> positionAlloc = CreateObject<UniformDiscPositionAllocator>();
    positionAlloc->SetRho(maxDistance);
    positionAlloc->SetMinDist(minDistance);
    positionAlloc->SetX(0);
    positionAlloc->SetY(0);
    positionAlloc->SetZ(staHeight);
    staMobility.SetPositionAllocator(positionAlloc);
    staMobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    staMobility.Install(wifiStaNodes);

    Ptr<ConstantPositionMobilityModel> apMobility = CreateObject<ConstantPositionMobilityModel>();
    apMobility->SetPosition({0, 0, apHeight});
    wifiApNode.Get(0)->AggregateObject(apMobility);

    /*
    * To use specific UORA Parameter sets
    */
    if (nRaRus) {
        Config::SetDefault("ns3::HeConfiguration::OCwMin", UintegerValue(OCwMin));
        Config::SetDefault("ns3::HeConfiguration::OCwMax", UintegerValue(OCwMax));
    }
    //prevent stations from explicitly sending BAR request
    Config::SetDefault("ns3::QosTxop::UseExplicitBarAfterMissedBlockAck", BooleanValue(false));
    Config::SetDefault("ns3::WifiDefaultAckManager::UseExplicitBar", BooleanValue(false));
    Config::SetDefault("ns3::WifiMacQueue::MaxDelay", TimeValue(MilliSeconds(500)));

    /*
     * To use specific MU-EDCA parameters for various AC
     */
    if (useMuEdca) {
        //STA AIFSN
        Config::SetDefault("ns3::HeConfiguration::MuBkAifsn", UintegerValue(0));
        Config::SetDefault("ns3::HeConfiguration::MuBeAifsn", UintegerValue(0));
        Config::SetDefault("ns3::HeConfiguration::MuViAifsn", UintegerValue(0));
        Config::SetDefault("ns3::HeConfiguration::MuVoAifsn", UintegerValue(0));

        //STA CW min
        Config::SetDefault("ns3::HeConfiguration::MuBkCwMin", UintegerValue(32767));
        Config::SetDefault("ns3::HeConfiguration::MuBeCwMin", UintegerValue(32767));
        Config::SetDefault("ns3::HeConfiguration::MuViCwMin", UintegerValue(32767));
        Config::SetDefault("ns3::HeConfiguration::MuVoCwMin", UintegerValue(32767));

        //STA CW max
        Config::SetDefault("ns3::HeConfiguration::MuBkCwMax", UintegerValue(32767));
        Config::SetDefault("ns3::HeConfiguration::MuBeCwMax", UintegerValue(32767));
        Config::SetDefault("ns3::HeConfiguration::MuViCwMax", UintegerValue(32767));
        Config::SetDefault("ns3::HeConfiguration::MuVoCwMax", UintegerValue(32767));

        if (LongerEdcaDisable) {
            /* Disable EDCA for the duration of the entire simulation:
             *    Calculate the ceiling multiple of
             *    8192 from simulation time
             *    This is needed for UORA only simulation
             */
            int simTime = Seconds(simulationTime).GetMicroSeconds();
            muEdcaTimer = (simTime % 8192 == 0) ? simTime : (std::round(simTime / 8192.0) * 8192);
            Config::SetDefault("ns3::QosTxop::LongerEDCADisable", BooleanValue(true));
        }

        //STA timer (validity of set)
        Config::SetDefault("ns3::HeConfiguration::BkMuEdcaTimer", TimeValue(MicroSeconds(muEdcaTimer)));
        Config::SetDefault("ns3::HeConfiguration::BeMuEdcaTimer", TimeValue(MicroSeconds(muEdcaTimer)));
        Config::SetDefault("ns3::HeConfiguration::ViMuEdcaTimer", TimeValue(MicroSeconds(muEdcaTimer)));
        Config::SetDefault("ns3::HeConfiguration::VoMuEdcaTimer", TimeValue(MicroSeconds(muEdcaTimer)));

        Config::SetDefault("ns3::HtFrameExchangeManager::DisableEDCA", BooleanValue(true));

        Config::SetDefault("ns3::HeFrameExchangeManager::MuTxStartTime", TimeValue(Seconds(startLogTime)));
    } else {
        Config::SetDefault("ns3::HeFrameExchangeManager::MuTxStartTime",
                           TimeValue(Seconds(simulationTime + startLogTime)));
    }

    /*
   * SIFS and Slot time
   */
    Config::SetDefault("ns3::WifiPhy::Sifs", TimeValue(MicroSeconds(16)));
    Config::SetDefault("ns3::WifiPhy::Slot", TimeValue(MicroSeconds(9)));

    /*
     * Retry limit
     */
    Config::SetDefault("ns3::WifiRemoteStationManager::MaxSsrc", UintegerValue(8));
    // lower this amount because of xr deley req
    Config::SetDefault("ns3::WifiRemoteStationManager::MaxSlrc", UintegerValue(8));

    /*
     * Intrinsic Queue Size reporting
     */
    Config::SetDefault("ns3::QosFrameExchangeManager::SetQueueSize", BooleanValue(true));

    if (enableAggregation) {
        Config::SetDefault("ns3::WifiRemoteStationManager::FragmentationThreshold", StringValue("990000"));
        Config::SetDefault("ns3::WifiMac::VO_MaxAmpduSize", UintegerValue(0)); //6500631
        Config::SetDefault("ns3::WifiMac::VO_MaxAmsduSize", UintegerValue(11398)); //11398
        Config::SetDefault("ns3::WifiMac::BE_MaxAmpduSize", UintegerValue(0)); //6500631
        Config::SetDefault("ns3::WifiMac::BE_MaxAmsduSize", UintegerValue(11398)); //11398
    }

    /*
    * Set up Network devices
    */
    NetDeviceContainer apNetDevice, staNetDevices;
    WifiMacHelper wifimac;
    WifiHelper wifi;
    std::string channelStr("{0, " + std::to_string(channelWidth) + ", ");
    wifi.SetStandard(WIFI_STANDARD_80211ax);

    channelStr += "BAND_5GHZ, 0}";

    std::ostringstream oss;
    oss << "HeMcs" << mcs;
    wifi.SetRemoteStationManager("ns3::ConstantRateWifiManager",
                                 "DataMode", StringValue(oss.str()),
                                 "ControlMode", StringValue(oss.str()));

    /*Set guard interval and MPDU buffer size
     */
    wifi.ConfigHeOptions("GuardInterval", TimeValue(NanoSeconds(guardInterval)),
                         "MpduBufferSize", UintegerValue(useExtendedBlockAck ? 256 : 64));

    /*
     * Setup PHY and MAC layers
     */

    Ssid ssid = Ssid("ns3-80211be");

    Ptr<ConstantSpeedPropagationDelayModel> delayModel = CreateObject<ConstantSpeedPropagationDelayModel>();
    Ptr<IeeeIndoorPropagationLossModel> propModel = CreateObject<IeeeIndoorPropagationLossModel>();
    if (enableShadowing) {
        propModel->SetAttribute("EnableShadowing", BooleanValue(true));
    }


    if (phyModel == "Spectrum") {
        /*
        * SingleModelSpectrumChannel cannot be used with 802.11ax because two
        * spectrum models are required: one with 78.125 kHz bands for HE PPDUs
        * and one with 312.5 kHz bands for, e.g., non-HT PPDUs (for more details,
        * see issue #408 (CLOSED))
        */
        Ptr<MultiModelSpectrumChannel> spectrumChannel = CreateObject<MultiModelSpectrumChannel>();
        spectrumChannel->AddPropagationLossModel(propModel);
        spectrumChannel->SetPropagationDelayModel(delayModel);
        SpectrumWifiPhyHelper phy;
        phy.SetPcapDataLinkType(WifiPhyHelper::DLT_IEEE802_11_RADIO);
        phy.SetChannel(spectrumChannel);
        phy.Set("ChannelSettings", StringValue(channelStr));
        phy.Set("TxPowerStart", DoubleValue(txPower));
        phy.Set("TxPowerEnd", DoubleValue(txPower));
        phy.Set("RxNoiseFigure", DoubleValue(7));

        wifimac.SetType("ns3::StaWifiMac", "Ssid", SsidValue(ssid),
                        "VO_BlockAckThreshold", UintegerValue(0));

        staNetDevices = wifi.Install(phy, wifimac, wifiStaNodes);

        //if (Scheduler == "ns3::VlceMultiUserScheduler")
        //    maxCredit = muEdcaTimer;

        if (dlAckSeqType != "NO-OFDMA")
        {
            wifimac.SetMultiUserSchedulerNoAttr(Scheduler);

            // Common attributes
            wifimac.SetMultiUserSchedulerAttribute("EnableUlOfdma", BooleanValue(enableUlOfdma));
            wifimac.SetMultiUserSchedulerAttribute("EnableBsrp", BooleanValue(enableBsrp));
            wifimac.SetMultiUserSchedulerAttribute("AccessReqInterval", TimeValue(MicroSeconds(accessReqInterval)));
            wifimac.SetMultiUserSchedulerAttribute("DelayAccessReqUponAccess", BooleanValue(DelayAccessReqUponAccess));
            wifimac.SetMultiUserSchedulerAttribute("UseCentral26TonesRus", BooleanValue(UseCentral26TonesRus));
            wifimac.SetMultiUserSchedulerAttribute("NStations", UintegerValue(nStations));
            wifimac.SetMultiUserSchedulerAttribute("AccessReqAc", EnumValue(AcIndex::AC_VO));
            wifimac.SetMultiUserSchedulerAttribute("RuAllocationType", EnumValue(ruAllocType));
            wifimac.SetMultiUserSchedulerAttribute("UlPsduSize", UintegerValue(1500)); // todo : what does this par do?

            // Scheduler-specific attributes
            if (Scheduler == "ns3::RrMultiUserScheduler") {
                wifimac.SetMultiUserSchedulerAttribute("MaxCredits",
                    TimeValue(MicroSeconds(maxTimeInList)));
            }

            if (Scheduler == "ns3::VlceMultiUserScheduler") {
                wifimac.SetMultiUserSchedulerAttribute("MaxTimeInList",
                    TimeValue(MicroSeconds(maxTimeInList)));
            }

            if (Scheduler == "ns3::UoraMultiUserScheduler") {
                wifimac.SetMultiUserSchedulerAttribute("NumRandomAccessRus",
                    UintegerValue(nRaRus));
            }
        }
        wifimac.SetType("ns3::ApWifiMac",
                        "EnableBeaconJitter", BooleanValue(false),
                        "Ssid", SsidValue(ssid),
                        "VO_BlockAckThreshold", UintegerValue(0),
                        "BeaconGeneration", BooleanValue(true),
                        "BsrLifetime", TimeValue(MilliSeconds(200000)),
                        "BeaconInterval", TimeValue(MicroSeconds(102400)));

        apNetDevice = wifi.Install(phy, wifimac, wifiApNode);
        //phy.EnablePcap("xr-ap", apNetDevice.Get(0), true);
        //phy.EnablePcap("xr-sta", staNetDevices, true);
    } else {
        Ptr<YansWifiChannel> channel = CreateObject<YansWifiChannel>();
        channel->SetPropagationLossModel(propModel);
        channel->SetPropagationDelayModel(delayModel);

        YansWifiPhyHelper YansPhy;
        YansPhy.SetPcapDataLinkType(WifiPhyHelper::DLT_IEEE802_11_RADIO);
        YansPhy.SetChannel(channel); //channel.Create ()
        wifimac.SetType("ns3::StaWifiMac", "Ssid", SsidValue(ssid));

        YansPhy.Set("ChannelSettings", StringValue(channelStr));
        YansPhy.Set("TxPowerStart", DoubleValue(txPower));
        YansPhy.Set("TxPowerEnd", DoubleValue(txPower));
        staNetDevices = wifi.Install(YansPhy, wifimac, wifiStaNodes);

        wifimac.SetType("ns3::ApWifiMac",
                        "EnableBeaconJitter", BooleanValue(false),
                        "Ssid", SsidValue(ssid),
                        "VO_BlockAckThreshold", UintegerValue(0),
                        "BE_BlockAckThreshold", UintegerValue(0));
        apNetDevice = wifi.Install(YansPhy, wifimac, wifiApNode);
        //YansPhy.EnablePcap("xr-ap", apNetDevice.Get(0), true);
        //YansPhy.EnablePcap("xr-sta", staNetDevices, true);
    }

    /*
       * Internet Stack on
       */
    InternetStackHelper internetStack;
    internetStack.Install(wifiApNode);
    internetStack.Install(wifiStaNodes);

    Ipv4AddressHelper address;
    address.SetBase("192.168.1.0", "255.255.255.0");
    Ipv4InterfaceContainer staNodeInterfaces = address.Assign(staNetDevices);
    Ipv4InterfaceContainer apNodeInterface = address.Assign(apNetDevice);

    for (uint32_t i = 0; i < nStations; ++i) {
        Mac48Address mac = Mac48Address::ConvertFrom(staNetDevices.Get(i)->GetAddress());
        Ipv4Address ip = staNodeInterfaces.Get(i).first->GetAddress(1, 0).GetAddress();
        g_Ip2Mac[ip] = mac;


        Ptr<WifiNetDevice> dev = DynamicCast<WifiNetDevice>(staNetDevices.Get(i));
        Ptr<WifiPhy> phy = dev->GetPhy();
        phy->GetPhyEntity(WIFI_MOD_CLASS_HE)->TraceConnectWithoutContext("SinrTrace",
            MakeBoundCallback(&SinrTrace, mac));
        phy->GetPhyEntity(WIFI_MOD_CLASS_OFDM)->TraceConnectWithoutContext("SinrTrace",
            MakeBoundCallback(&SinrTrace, mac));
    }

    Mac48Address apMac = Mac48Address::ConvertFrom(apNetDevice.Get(0)->GetAddress());
    Ipv4Address apIp = apNodeInterface.Get(0).first->GetAddress(1, 0).GetAddress();
    g_Ip2Mac[apIp] = apMac;

    ArpCache::PopulateArpCache();

    uint16_t dlVideoPort = 9;
    uint16_t dlAudioPort = 10;
    uint16_t ulTrackingPort = 11;

    uint8_t tosVo = 0xc0; // Voice
    uint8_t tosVi = 0xb8; // Video

    XrAppContainer xrServerApps;
    XrAppContainer xrClientApps;

    // Helpers
    XrServerHelper videoHelper;
    XrServerHelper audioHelper;
    XrClientHelper trackingHelper(apNodeInterface.GetAddress(0), ulTrackingPort);


    XrServerHelper trackingSinkHelper;
    trackingSinkHelper.SetAttribute("SinkFlag", BooleanValue(true));
    trackingSinkHelper.SetAttribute("LocalPort", UintegerValue(ulTrackingPort));


    xrServerApps.Add(
        trackingSinkHelper.Install(wifiApNode.Get(0))
    );

    for (uint32_t i = 0; i < nStations; ++i) {
        double staggeredStart = startLogTime + (i * 0.00108);

        // DOWNLINK
        InetSocketAddress videoAddr(staNodeInterfaces.GetAddress(i), dlVideoPort);
        videoHelper.SetAttribute("Tos", UintegerValue(tosVi));
        videoHelper.SetAttribute("RemoteAddress", AddressValue(videoAddr));
        videoHelper.SetAttribute("RemotePort", UintegerValue(dlVideoPort));
        videoHelper.SetAttribute("Interval", TimeValue(Seconds(0.01111)));
        videoHelper.SetAttribute("PacketsPerBatch", UintegerValue(96));
        videoHelper.SetAttribute("PacketSize", UintegerValue(1448));

        XrAppContainer vApp = videoHelper.Install(wifiApNode.Get(0));
        vApp.Start(Seconds(staggeredStart));
        xrServerApps.Add(vApp);

        InetSocketAddress audioAddr(staNodeInterfaces.GetAddress(i), dlAudioPort);
        audioHelper.SetAttribute("Tos", UintegerValue(tosVo));
        audioHelper.SetAttribute("RemoteAddress", AddressValue(audioAddr));
        audioHelper.SetAttribute("RemotePort", UintegerValue(dlAudioPort));
        audioHelper.SetAttribute("Interval", TimeValue(MilliSeconds(25)));
        audioHelper.SetAttribute("PacketsPerBatch", UintegerValue(4));
        audioHelper.SetAttribute("PacketSize", UintegerValue(1448));

        XrAppContainer aApp = audioHelper.Install(wifiApNode.Get(0));
        aApp.Start(Seconds(staggeredStart));
        xrServerApps.Add(aApp);

        // DL VIDEO SINK
        XrServerHelper videoSinkHelper;
        videoSinkHelper.SetAttribute("SinkFlag", BooleanValue(true));
        videoSinkHelper.SetAttribute("LocalPort", UintegerValue(dlVideoPort));
        xrServerApps.Add(
            videoSinkHelper.Install(wifiStaNodes.Get(i))
        );

        // DL AUDIO SINK
        XrServerHelper audioSinkHelper;
        audioSinkHelper.SetAttribute("SinkFlag", BooleanValue(true));
        audioSinkHelper.SetAttribute("LocalPort", UintegerValue(dlAudioPort));
        xrServerApps.Add(
            audioSinkHelper.Install(wifiStaNodes.Get(i))
        );

        // UPLINK
        InetSocketAddress trackingAddr(apNodeInterface.GetAddress(0), ulTrackingPort);
        trackingHelper.SetAttribute("Tos", UintegerValue(tosVo));
        trackingHelper.SetAttribute("RemoteAddress", AddressValue(trackingAddr));
        trackingHelper.SetAttribute("RemotePort", UintegerValue(ulTrackingPort));
        trackingHelper.SetAttribute("InitPacketSentDelay", TimeValue(Seconds(staggeredStart)));
        trackingHelper.SetAttribute("Interval", TimeValue(Seconds(0.01111)));

        xrClientApps.Add(trackingHelper.Install(wifiStaNodes.Get(i)));
    }

    xrServerApps.Start(Seconds(startLogTime));
    xrServerApps.Stop(Seconds(simulationTime + startLogTime));

    xrClientApps.Start(Seconds(startLogTime));
    xrClientApps.Stop(Seconds(simulationTime + startLogTime));

    Simulator::Schedule(Seconds(0), &Ipv4GlobalRoutingHelper::PopulateRoutingTables);
    for (uint32_t i = 0; i < nStations; i++) {
        Ptr<WifiNetDevice> dev = DynamicCast<WifiNetDevice>(staNetDevices.Get(i));
        dev->GetMac()->GetQosTxop(AC_VO)->SetTxopLimit(MicroSeconds(txOpLimits));
    }
    Ptr<WifiNetDevice> apDev = DynamicCast<WifiNetDevice>(apNetDevice.Get(0));
    apDev->GetMac()->GetQosTxop(AC_VO)->SetTxopLimit(MicroSeconds(txOpLimits));

    Config::ConnectWithoutContext(
      "/NodeList/*/ApplicationList/*/$ns3::XrServerUdpApp/Rx",
      MakeBoundCallback(&RxTraceWithAddressParam, startLogTime)
    );

    ProgressBar pg(Seconds(simulationTime + startLogTime));
    Simulator::Stop(Seconds(simulationTime + startLogTime));
    Simulator::Run();

    uint64_t totalRxBytes = 0;

    for (uint32_t i = 0; i < xrServerApps.GetN(); ++i) {
        Ptr<XrServerUdpApp> app =
            DynamicCast<XrServerUdpApp>(xrServerApps.Get(i));
        if (app) {
            totalRxBytes += app->GetTotalRx();
        }
    }

    double effectiveSimTime = simulationTime;
    double throughput = (totalRxBytes * 8) / (effectiveSimTime * 1000000.0); // Mbit/s

    std::ofstream totalStatsOutStream;
    totalStatsOutStream.open("throughput.out", std::ios::out);
    totalStatsOutStream << "MCS\tBandwidth_MHz\tGuard_interval_ns\tTotal_Throughput_Mbps" << std::endl;
    totalStatsOutStream << mcs << "\t" << channelWidth << "\t" << guardInterval << "\t" << throughput << std::endl;
    totalStatsOutStream.close();

    std::ofstream perStaOutStream;
    perStaOutStream.open("per_sta_stats.out", std::ios::out);
    perStaOutStream << "MAC-addr\tAvg_SINR_dB\tRX_bytes\tAvg_delay_ms" << std::endl;

    for (auto &staStats: g_statsMap) {
        double avgSinr = (staStats.second.totalBeacons > 0) ? (staStats.second.sinr / staStats.second.totalBeacons) : 0;

        double sumDelay = 0.;
        for (auto &delay: staStats.second.pktDelays) {
            sumDelay += delay * 1000.;
        }

        double avgDelay = (staStats.second.pktDelays.size() > 0) ? (sumDelay / staStats.second.pktDelays.size()) : 0;

        perStaOutStream << staStats.first << "\t" << avgSinr << "\t" << staStats.second.rxBytes
                << "\t" << avgDelay << std::endl;
    }
    perStaOutStream.close();
    Simulator::Destroy();
    return 0;
}
