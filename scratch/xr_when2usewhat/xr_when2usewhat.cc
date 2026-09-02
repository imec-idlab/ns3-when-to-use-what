#include "ns3/application.h"
#include "ns3/inet-socket-address.h"
#include "ns3/log.h"

#include <cerrno>
#include <cstdint>
#include <algorithm>
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

    // per-direction / per-AC accounting (delays in seconds)
    uint64_t vidBytes{0}, audBytes{0}, poseBytes{0};   // DL video (AC_VI), DL audio (AC_VO), UL pose (AC_VO)
    std::vector<double> vidDelays, audDelays, poseDelays;
    std::vector<uint32_t> vidSeq;                       // per received video packet, its app seq (for frame grouping)
};

// XR traffic flows: DL video is AC_VI; DL audio and UL pose are AC_VO.
enum XrFlow { FLOW_VIDEO_DL = 0, FLOW_AUDIO_DL = 1, FLOW_POSE_UL = 2 };

std::map<Mac48Address, stats_t> g_statsMap; //!< map for statistics for each station
std::map<Ipv4Address, Mac48Address> g_Ip2Mac; //!< map for mapping IPv4 to MAC address
std::map<Mac48Address, stats_t> g_statsMapAp; //!< map for starts for only AP
void SinrTrace(Mac48Address addr, double sinr) {
    g_statsMap[addr].sinr += sinr;
    g_statsMap[addr].totalBeacons++;
}


// Bound per sink with its STA MAC and flow. For the downlink flows the sink runs
// on the STA, so the bound staMac is the receiver; for the uplink pose flow the
// single AP sink receives from every STA, so the STA is resolved from the source.
void RxFlowTrace(Mac48Address staMac, uint8_t flow, double logTime,
                 Ptr<const Packet> p, const Address &src, const Address &dst) {
    if (Simulator::Now().GetSeconds() < logTime) return;

    Ptr<Packet> pkt = p->Copy();
    SeqTsHeader seqTs;
    ns3::PacketTag tag;
    pkt->RemovePacketTag(tag);
    pkt->RemoveHeader(seqTs);

    double delay = (Simulator::Now() - seqTs.GetTs()).GetSeconds();
    uint32_t sz = p->GetSize();

    Mac48Address key = staMac;
    if (flow == FLOW_POSE_UL) {
        key = g_Ip2Mac.at(InetSocketAddress::ConvertFrom(src).GetIpv4());
    }
    stats_t &st = g_statsMap[key];

    if (flow == FLOW_VIDEO_DL)      { st.vidBytes  += sz; st.vidDelays.push_back(delay); st.vidSeq.push_back(seqTs.GetSeq()); }
    else if (flow == FLOW_AUDIO_DL) { st.audBytes  += sz; st.audDelays.push_back(delay); }
    else                            { st.poseBytes += sz; st.poseDelays.push_back(delay); }
}

int main(int argc, char *argv[]) {
    std::string logDir{"output"};
    double startLogTime = {1.030};
    double simulationTime = 10.0;
    uint32_t nStations = 10;
    uint32_t channelWidth = 80; // 20, 40, 80, 160, 320 MHz
    uint32_t nss = 1;           // spatial streams (MIMO); XR DL video needs >1 for multi-headset capacity
    int mcs = 11; // 4096-QAM for Wi-Fi 7
    std::string Scheduler = "ns3::RrMultiUserScheduler";
    uint32_t nRaRus = 0; // 0 = EDCA, >0 = UORA
    bool useA2Pv2 = false;

    // CMAB scheduler params (applied when Scheduler == ns3::CmabMultiUserScheduler)
    std::string cmabAlgorithm {"CUCB"};       // CUCB | ThompsonSampling | EpsilonGreedy | EXP3M
    std::string cmabRewardType {"Binary"};    // Binary | FairnessWeighted
    double cmabUcbConstant {std::sqrt(2.0)};
    double cmabEpsilon {0.1};
    double cmabExp3Gamma {0.1};
    double txPower = 40.0; // From Table II
    std::string frequency = "5"; // From Section C

    double minDistance{1.0}; //meters
    double maxDistance{4.0}; //meters
    double apHeight{3}; //meters
    double staHeight{1}; //meters

    uint32_t guardInterval{800}; //in ns
    std::string phyModel{"Yans"}; //Spectrum or Yans
    bool enableShadowing = false;
    uint32_t nMsdus = 8;   // A-MSDU count per AC (8*1448=11584 -> clamped to HE max 11398)
    HeRu::RuType ruAllocType{HeRu::RU_UNDEFINED};
    bool enableAggregation{true};
    uint32_t ulPayloadSize = 1500;


    std::string dlAckSeqType{"AGGR-MU-BAR"};
    bool enableUlOfdma{false};
    bool enableBsrp{true};   // match conference: A2P uses BSRP; UORA/CMAB trigger on it
    double accessReqInterval = {0}; //microseconds
    bool useExtendedBlockAck{true};
    bool useMuEdca{true};
    uint32_t nMpdus = 256; // A-MPDU count per AC (256*1448=370KB; PPDU duration binds first)
    bool UseCentral26TonesRus = {false};
    bool DelayAccessReqUponAccess = {true};
    std::string ruAllocationType{"ru-undefined"};
    uint32_t OCwMin{7};
    uint32_t OCwMax{127}; // Should this be lager? 1023?
    bool LongerEdcaDisable{true};
    bool edcaPrime{true};        // warm-up: STAs send tiny UL packets so the AP triggers
    double edcaPrimeStart{0.15}; // them and their MU-EDCA timer arms (EDCA off) before XR
    double edcaPrimeInterval{0.001};
    // Wi-Fi XR QoS targets. Video is frame-level: a frame (all its packets) must
    // arrive within videoFrameBound (Carrascosa/Bellalta VR-over-Wi-Fi: 33 ms,
    // NFR >= 99%). Pose/audio are per-packet (802.11 RTA low-latency class).
    double poseDeadline{10.0};    // UL pose per-packet latency target (ms)
    double videoFrameBound{33.0}; // DL video per-frame delivery bound (ms)
    double audioDeadline{30.0};   // DL audio per-packet latency target (ms)
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
    cmd.AddValue("nss", "Number of spatial streams (MIMO) at AP and STAs", nss);
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
    cmd.AddValue("OCwMin", "Min OFDMA CW", OCwMin);
    cmd.AddValue("OCwMax", "Max OFDMA CW", OCwMax);
    cmd.AddValue("Scheduler", "Type resource scheduler to use", Scheduler);
    cmd.AddValue("startLogTime", "Time to begin logging [seconds]", startLogTime);

    // CMAB scheduler hyperparameters (match conference scenario)
    cmd.AddValue("cmabAlgorithm", "CMAB algorithm (CUCB | ThompsonSampling | EpsilonGreedy | EXP3M)", cmabAlgorithm);
    cmd.AddValue("cmabRewardType", "Per-arm reward shape (Binary | FairnessWeighted)", cmabRewardType);
    cmd.AddValue("cmabUcbConstant", "CUCB exploration constant c in score = mean + c*sqrt(2 ln t / n_i)", cmabUcbConstant);
    cmd.AddValue("cmabEpsilon", "EpsilonGreedy random-exploration probability in [0,1]", cmabEpsilon);
    cmd.AddValue("cmabExp3Gamma", "EXP3.M mixing parameter gamma in (0,1]", cmabExp3Gamma);
    cmd.AddValue("ulPayloadSize", "Arbitrary UL PSDU size (bytes) the scheduler allocates when a STA's BSR is unknown", ulPayloadSize);

    cmd.AddValue("useA2Pv2",
                 "If true, use A2Pv2 (VlceMultiUserSchedulerNoBsrp: no BSRP, direct BasicTF).",
                 useA2Pv2); // New, use A2Pv2

    cmd.AddValue("LongerEdcaDisable", "if True, disable EDCA for the duration of simulation", LongerEdcaDisable);
    cmd.AddValue("edcaPrime", "warm-up: STAs send tiny UL packets before XR so their MU-EDCA arms (EDCA off)", edcaPrime);
    cmd.AddValue("edcaPrimeStart", "time (s) to start the UL priming flow (after association)", edcaPrimeStart);
    cmd.AddValue("edcaPrimeInterval", "inter-packet interval (s) of the UL priming flow", edcaPrimeInterval);
    cmd.AddValue("poseDeadline", "UL pose per-packet latency target in ms", poseDeadline);
    cmd.AddValue("videoFrameBound", "DL video per-frame delivery bound in ms (frame on-time if all its packets arrive within this)", videoFrameBound);
    cmd.AddValue("audioDeadline", "DL audio per-packet latency target in ms", audioDeadline);
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
    else if (ruAllocationType == "ru-106-tone")
        ruAllocType = HeRu::RU_106_TONE;
    else if (ruAllocationType == "ru-242-tone")
        ruAllocType = HeRu::RU_242_TONE;
    else if (ruAllocationType == "ru-484-tone")
        ruAllocType = HeRu::RU_484_TONE;
    else if (ruAllocationType == "ru-996-tone")
        ruAllocType = HeRu::RU_996_TONE;


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

        // Per-scheme MU-EDCA timer + warm-up, matching the conference scenario.
        // (XR selects the scheme via the Scheduler string + useA2Pv2 + nRaRus.)
        if (Scheduler.find("Vlce") != std::string::npos) {
            // A2P / A2Pv2 (VlceMultiUserScheduler[NoBsrp]): longer poll-list tenure,
            // HT EDCA stays up briefly so STAs bootstrap into the poll list.
            muEdcaTimer = 8192 * 5;
            maxTimeInList = muEdcaTimer;
            Config::SetDefault("ns3::HtFrameExchangeManager::HtMuTxStartTime", TimeValue(Seconds(1.5)));
        } else {
            // UORA / CMAB / RR: disable EDCA for the whole simulation.
            int simTime = Seconds(simulationTime).GetMicroSeconds();
            muEdcaTimer = (simTime % 8192 == 0) ? simTime : (std::round(simTime / 8192.0) * 8192);
            Config::SetDefault("ns3::QosTxop::LongerEDCADisable", BooleanValue(true));
            if (Scheduler.find("Uora") != std::string::npos && nRaRus) {
                Config::SetDefault("ns3::HeFrameExchangeManager::SendQosNullAfterBasicTf", BooleanValue(true));
            }
        }

        //STA timer (validity of set)
        Config::SetDefault("ns3::HeConfiguration::BkMuEdcaTimer", TimeValue(MicroSeconds(muEdcaTimer)));
        Config::SetDefault("ns3::HeConfiguration::BeMuEdcaTimer", TimeValue(MicroSeconds(muEdcaTimer)));
        Config::SetDefault("ns3::HeConfiguration::ViMuEdcaTimer", TimeValue(MicroSeconds(muEdcaTimer)));
        Config::SetDefault("ns3::HeConfiguration::VoMuEdcaTimer", TimeValue(MicroSeconds(muEdcaTimer)));

        Config::SetDefault("ns3::HtFrameExchangeManager::DisableEDCA", BooleanValue(true));

        // Warm-up: AP begins MU transmissions at 1.5 s (matches conference). The
        // first traffic flows via EDCA, then MU-OFDMA takes over.
        Config::SetDefault("ns3::HeFrameExchangeManager::MuTxStartTime", TimeValue(Seconds(1.5)));
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
        // Aggregation limits are driven by nMsdus/nMpdus (counts of the 1448 B XR
        // MSDU) and applied uniformly to every AC, clamped to the 802.11ax maxima
        // (A-MSDU 11398 B, A-MPDU 6500631 B). A-MPDU is enabled for AC_VO (audio +
        // UL pose) as well, not only AC_VI.
        const uint32_t xrMsdu = 1448;
        const uint32_t amsduLimit = std::min<uint32_t>(nMsdus * xrMsdu, 11398);
        const uint32_t ampduLimit = std::min<uint32_t>(nMpdus * xrMsdu, 6500631);
        for (const std::string& ac : {std::string("VI"), std::string("VO"), std::string("BE")}) {
            Config::SetDefault("ns3::WifiMac::" + ac + "_MaxAmpduSize", UintegerValue(ampduLimit));
            Config::SetDefault("ns3::WifiMac::" + ac + "_MaxAmsduSize", UintegerValue(amsduLimit));
        }
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
        phy.Set("Antennas", UintegerValue(nss));
        phy.Set("MaxSupportedTxSpatialStreams", UintegerValue(nss));
        phy.Set("MaxSupportedRxSpatialStreams", UintegerValue(nss));

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
            wifimac.SetMultiUserSchedulerAttribute("UlPsduSize", UintegerValue(ulPayloadSize)); // fallback UL alloc when BSR unknown

            // Scheduler-specific attributes
            if (Scheduler == "ns3::VlceMultiUserScheduler") {
                wifimac.SetMultiUserSchedulerAttribute("MaxTimeInList", TimeValue(MicroSeconds(maxTimeInList)));
            }

            if (Scheduler == "ns3::UoraMultiUserScheduler") {
                wifimac.SetMultiUserSchedulerAttribute("NumRandomAccessRus", UintegerValue(nRaRus));
            }

            if (Scheduler == "ns3::CmabMultiUserScheduler") {
                NS_ABORT_MSG_IF(cmabAlgorithm != "CUCB" &&
                                cmabAlgorithm != "ThompsonSampling" &&
                                cmabAlgorithm != "EpsilonGreedy" &&
                                cmabAlgorithm != "EXP3M",
                                "Invalid --cmabAlgorithm: " << cmabAlgorithm
                                << " (expected CUCB | ThompsonSampling | EpsilonGreedy | EXP3M)");
                NS_ABORT_MSG_IF(cmabRewardType != "Binary" &&
                                cmabRewardType != "FairnessWeighted",
                                "Invalid --cmabRewardType: " << cmabRewardType
                                << " (expected Binary | FairnessWeighted)");
                wifimac.SetMultiUserSchedulerAttribute("Algorithm",   StringValue(cmabAlgorithm));
                wifimac.SetMultiUserSchedulerAttribute("RewardType",  StringValue(cmabRewardType));
                wifimac.SetMultiUserSchedulerAttribute("UcbConstant", DoubleValue(cmabUcbConstant));
                wifimac.SetMultiUserSchedulerAttribute("Epsilon",     DoubleValue(cmabEpsilon));
                wifimac.SetMultiUserSchedulerAttribute("Exp3Gamma",   DoubleValue(cmabExp3Gamma));
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
    uint16_t ulPrimePort = 12;
    const uint32_t VIDEO_PKTS_PER_FRAME = 96;   // DL video packets per frame (for frame-level QoS)

    uint8_t tosVo = 0xc0; // Voice
    uint8_t tosVi = 0xb8; // Video

    XrAppContainer xrServerApps;
    XrAppContainer xrClientApps;
    XrAppContainer primeApps;   // warm-up UL priming (own start/stop window; not logged)
    std::map<Mac48Address, Ptr<XrPacketGenerationUdpApp>> poseSender; // per-STA UL pose generator (for generated count)
    std::map<Mac48Address, Ptr<XrServerUdpApp>> videoSender, audioSender; // per-STA DL generators (for generated count)

    // AP-side sink for the priming flow (deliberately NOT connected to RxFlowTrace,
    // so priming traffic is never counted in the XR metrics).
    if (edcaPrime)
    {
        XrServerHelper primeSinkHelper;
        primeSinkHelper.SetAttribute("SinkFlag", BooleanValue(true));
        primeSinkHelper.SetAttribute("LocalPort", UintegerValue(ulPrimePort));
        primeApps.Add(primeSinkHelper.Install(wifiApNode.Get(0)));
    }

    // Helpers
    XrServerHelper videoHelper;
    XrServerHelper audioHelper;
    XrClientHelper trackingHelper(apNodeInterface.GetAddress(0), ulTrackingPort);


    XrServerHelper trackingSinkHelper;
    trackingSinkHelper.SetAttribute("SinkFlag", BooleanValue(true));
    trackingSinkHelper.SetAttribute("LocalPort", UintegerValue(ulTrackingPort));


    XrAppContainer trackingSink = trackingSinkHelper.Install(wifiApNode.Get(0));
    trackingSink.Get(0)->TraceConnectWithoutContext(
        "Rx", MakeBoundCallback(&RxFlowTrace, apMac, (uint8_t)FLOW_POSE_UL, startLogTime));
    xrServerApps.Add(trackingSink);

    for (uint32_t i = 0; i < nStations; ++i) {
        double staggeredStart = startLogTime + (i * 0.00108);
        Mac48Address staMac = Mac48Address::ConvertFrom(staNetDevices.Get(i)->GetAddress());

        // DOWNLINK
        InetSocketAddress videoAddr(staNodeInterfaces.GetAddress(i), dlVideoPort);
        videoHelper.SetAttribute("Tos", UintegerValue(tosVi));
        videoHelper.SetAttribute("RemoteAddress", AddressValue(videoAddr));
        videoHelper.SetAttribute("RemotePort", UintegerValue(dlVideoPort));
        videoHelper.SetAttribute("Interval", TimeValue(Seconds(0.01111)));
        videoHelper.SetAttribute("PacketsPerBatch", UintegerValue(VIDEO_PKTS_PER_FRAME));
        videoHelper.SetAttribute("PacketSize", UintegerValue(1448));

        XrAppContainer vApp = videoHelper.Install(wifiApNode.Get(0));
        vApp.Start(Seconds(staggeredStart));
        videoSender[staMac] = DynamicCast<XrServerUdpApp>(vApp.Get(0));
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
        audioSender[staMac] = DynamicCast<XrServerUdpApp>(aApp.Get(0));
        xrServerApps.Add(aApp);

        // DL VIDEO SINK (AC_VI)
        XrServerHelper videoSinkHelper;
        videoSinkHelper.SetAttribute("SinkFlag", BooleanValue(true));
        videoSinkHelper.SetAttribute("LocalPort", UintegerValue(dlVideoPort));
        XrAppContainer vSink = videoSinkHelper.Install(wifiStaNodes.Get(i));
        vSink.Get(0)->TraceConnectWithoutContext(
            "Rx", MakeBoundCallback(&RxFlowTrace, staMac, (uint8_t)FLOW_VIDEO_DL, startLogTime));
        xrServerApps.Add(vSink);

        // DL AUDIO SINK (AC_VO)
        XrServerHelper audioSinkHelper;
        audioSinkHelper.SetAttribute("SinkFlag", BooleanValue(true));
        audioSinkHelper.SetAttribute("LocalPort", UintegerValue(dlAudioPort));
        XrAppContainer aSink = audioSinkHelper.Install(wifiStaNodes.Get(i));
        aSink.Get(0)->TraceConnectWithoutContext(
            "Rx", MakeBoundCallback(&RxFlowTrace, staMac, (uint8_t)FLOW_AUDIO_DL, startLogTime));
        xrServerApps.Add(aSink);

        // UPLINK
        InetSocketAddress trackingAddr(apNodeInterface.GetAddress(0), ulTrackingPort);
        trackingHelper.SetAttribute("Tos", UintegerValue(tosVo));
        trackingHelper.SetAttribute("RemoteAddress", AddressValue(trackingAddr));
        trackingHelper.SetAttribute("RemotePort", UintegerValue(ulTrackingPort));
        trackingHelper.SetAttribute("InitPacketSentDelay", TimeValue(Seconds(staggeredStart)));
        trackingHelper.SetAttribute("Interval", TimeValue(Seconds(0.01111)));

        XrAppContainer poseApp = trackingHelper.Install(wifiStaNodes.Get(i));
        poseSender[staMac] = DynamicCast<XrPacketGenerationUdpApp>(poseApp.Get(0));
        xrClientApps.Add(poseApp);

        // WARM-UP EDCA PRIMING: tiny AC_VO UL packets so the AP triggers this STA
        // during the (DL-empty) warm-up, arming its MU-EDCA timer before XR starts.
        if (edcaPrime)
        {
            XrServerHelper primeHelper;
            primeHelper.SetAttribute("Tos", UintegerValue(tosVo));
            primeHelper.SetAttribute("RemoteAddress", AddressValue(InetSocketAddress(apNodeInterface.GetAddress(0), ulPrimePort)));
            primeHelper.SetAttribute("RemotePort", UintegerValue(ulPrimePort));
            primeHelper.SetAttribute("Interval", TimeValue(Seconds(edcaPrimeInterval)));
            primeHelper.SetAttribute("PacketsPerBatch", UintegerValue(1));
            primeHelper.SetAttribute("PacketSize", UintegerValue(60));
            primeApps.Add(primeHelper.Install(wifiStaNodes.Get(i)));
        }
    }

    xrServerApps.Start(Seconds(startLogTime));
    xrServerApps.Stop(Seconds(simulationTime + startLogTime));

    xrClientApps.Start(Seconds(startLogTime));
    xrClientApps.Stop(Seconds(simulationTime + startLogTime));

    // Priming runs only during warm-up: from just after association until XR starts.
    if (edcaPrime)
    {
        primeApps.Start(Seconds(edcaPrimeStart));
        primeApps.Stop(Seconds(startLogTime));
    }

    Simulator::Schedule(Seconds(0), &Ipv4GlobalRoutingHelper::PopulateRoutingTables);
    // TXOP limits left at the ns-3 standard EDCA defaults (AC_VO=2080 us,
    // AC_VI=4096 us; IEEE 802.11-2020 Table 9-155).

    ProgressBar pg(Seconds(simulationTime + startLogTime));
    Simulator::Stop(Seconds(simulationTime + startLogTime));
    Simulator::Run();

    double effectiveSimTime = simulationTime; // logging window (excludes warm-up)

    // Per-flow aggregate bytes across all stations.
    uint64_t vidBytes = 0, audBytes = 0, poseBytes = 0;
    for (auto &kv : g_statsMap) {
        vidBytes  += kv.second.vidBytes;
        audBytes  += kv.second.audBytes;
        poseBytes += kv.second.poseBytes;
    }
    auto mbps = [&](uint64_t bytes) { return (bytes * 8.0) / (effectiveSimTime * 1e6); };

    std::ofstream totalStatsOutStream;
    totalStatsOutStream.open("throughput.out", std::ios::out);
    totalStatsOutStream << "MCS\tBandwidth_MHz\tGuard_interval_ns\t"
                        << "DL_Video_Mbps\tDL_Audio_Mbps\tUL_Pose_Mbps\tTotal_Mbps" << std::endl;
    totalStatsOutStream << mcs << "\t" << channelWidth << "\t" << guardInterval << "\t"
                        << mbps(vidBytes) << "\t" << mbps(audBytes) << "\t" << mbps(poseBytes) << "\t"
                        << mbps(vidBytes + audBytes + poseBytes) << std::endl;
    totalStatsOutStream.close();

    // mean + p75/p95/p99/p99.9 of a delay vector, in ms (empty -> 0). Percentiles
    // over DELIVERED packets; pair with the gen/rx counts below to see drops too.
    auto delayStats = [](std::vector<double> v, double &mean,
                         double &p75, double &p95, double &p99, double &p999) {
        if (v.empty()) { mean = p75 = p95 = p99 = p999 = 0.; return; }
        double s = 0.; for (double x : v) s += x * 1000.; mean = s / v.size();
        std::sort(v.begin(), v.end());
        auto pct = [&](double q) { return v[std::min(v.size() - 1, (size_t)(q * v.size()))] * 1000.; };
        p75 = pct(0.75); p95 = pct(0.95); p99 = pct(0.99); p999 = pct(0.999);
    };

    // Per-flow QoS (survivorship-proof: generated = the sender's exact TX count).
    // Audio/pose are per-packet; video is per-FRAME (Wi-Fi VR KPI): a frame is
    // on-time only if ALL its packets arrive within the frame bound.
    auto genOf = [](auto &m, const Mac48Address &k) -> uint32_t {
        auto it = m.find(k); return (it != m.end() && it->second) ? it->second->GetSent() : 0;
    };
    auto pktCompliance = [](const std::vector<double> &delays, uint32_t gen, double dlS,
                            uint32_t &rx, uint32_t &ontime, double &loss) {
        rx = delays.size(); ontime = 0;
        for (double d : delays) { if (d <= dlS) ++ontime; }
        loss = (gen > 0) ? (1.0 - static_cast<double>(ontime) / gen) : 0.0;
        if (loss < 0.0) loss = 0.0;
    };
    // Video frame-level: group received packets by frame (seq / pktsPerFrame); a
    // frame is on-time iff all pktsPerFrame packets arrived and the last within bound.
    auto frameCompliance = [](const std::vector<uint32_t> &seq, const std::vector<double> &delays,
                              uint32_t genPkts, uint32_t pktsPerFrame, double boundS,
                              uint32_t &genFrames, uint32_t &ontimeFrames, double &frameLoss) {
        genFrames = genPkts / pktsPerFrame;
        std::map<uint32_t, std::pair<uint32_t,double>> fr; // frame -> (count, maxDelay)
        for (size_t i = 0; i < seq.size(); ++i) {
            auto &e = fr[seq[i] / pktsPerFrame];
            e.first += 1; e.second = std::max(e.second, delays[i]);
        }
        ontimeFrames = 0;
        for (auto &kv : fr)
            if (kv.second.first >= pktsPerFrame && kv.second.second <= boundS) ++ontimeFrames;
        frameLoss = (genFrames > 0) ? (1.0 - static_cast<double>(ontimeFrames) / genFrames) : 0.0;
        if (frameLoss < 0.0) frameLoss = 0.0;
    };
    double aDlS = audioDeadline / 1000.0, pDlS = poseDeadline / 1000.0, vFrS = videoFrameBound / 1000.0;

    std::ofstream perStaOutStream;
    perStaOutStream.open("per_sta_stats.out", std::ios::out);
    perStaOutStream << "MAC-addr\tAvg_SINR_dB\t"
                    << "Vid_RXbytes\tVid_rx\tVid_mean_ms\tVid_p75_ms\tVid_p95_ms\tVid_p99_ms\tVid_p999_ms\tVid_frames_gen\tVid_frames_ontime\tVid_frame_loss\t"
                    << "Aud_RXbytes\tAud_mean_ms\tAud_p75_ms\tAud_p95_ms\tAud_p99_ms\tAud_p999_ms\tAud_gen\tAud_rx\tAud_ontime\tAud_deadline_loss\t"
                    << "Pose_RXbytes\tPose_mean_ms\tPose_p75_ms\tPose_p95_ms\tPose_p99_ms\tPose_p999_ms\tPose_gen\tPose_rx\tPose_ontime\tPose_deadline_loss"
                    << std::endl;

    for (auto &staStats : g_statsMap) {
        const Mac48Address &k = staStats.first;
        stats_t &s = staStats.second;
        double avgSinr = (s.totalBeacons > 0) ? (s.sinr / s.totalBeacons) : 0;
        double vMean, vP75, vP95, vP99, vP999, aMean, aP75, aP95, aP99, aP999, pMean, pP75, pP95, pP99, pP999;
        delayStats(s.vidDelays,  vMean, vP75, vP95, vP99, vP999);
        delayStats(s.audDelays,  aMean, aP75, aP95, aP99, aP999);
        delayStats(s.poseDelays, pMean, pP75, pP95, pP99, pP999);

        uint32_t vGen = genOf(videoSender, k), aGen = genOf(audioSender, k), pGen = genOf(poseSender, k);
        uint32_t vFrGen, vFrOn, aRx, aOn, pRx, pOn; double vFrLoss, aLoss, pLoss;
        frameCompliance(s.vidSeq, s.vidDelays, vGen, VIDEO_PKTS_PER_FRAME, vFrS, vFrGen, vFrOn, vFrLoss);
        pktCompliance(s.audDelays,  aGen, aDlS, aRx, aOn, aLoss);
        pktCompliance(s.poseDelays, pGen, pDlS, pRx, pOn, pLoss);

        perStaOutStream << k << "\t" << avgSinr << "\t"
            << s.vidBytes  << "\t" << s.vidDelays.size() << "\t" << vMean << "\t" << vP75 << "\t" << vP95 << "\t" << vP99 << "\t" << vP999 << "\t" << vFrGen << "\t" << vFrOn << "\t" << vFrLoss << "\t"
            << s.audBytes  << "\t" << aMean << "\t" << aP75 << "\t" << aP95 << "\t" << aP99 << "\t" << aP999 << "\t" << aGen << "\t" << aRx << "\t" << aOn << "\t" << aLoss << "\t"
            << s.poseBytes << "\t" << pMean << "\t" << pP75 << "\t" << pP95 << "\t" << pP99 << "\t" << pP999 << "\t" << pGen << "\t" << pRx << "\t" << pOn << "\t" << pLoss
            << std::endl;
    }
    perStaOutStream.close();
    Simulator::Destroy();
    return 0;
}
