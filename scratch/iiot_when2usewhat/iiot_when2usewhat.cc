/* -*-  Mode: C++; c-file-style: "gnu"; indent-tabs-mode:nil; -*- */
/*
 * Copyright (c) 2026
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 2 as
 * published by the Free Software Foundation;
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
 *
 * Author: Douglas Agbeve <douglas.agbeve@uantwerpen.be>
 */

#include <cerrno>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <sstream>
#include <string>
#include <ns3/wifi-module.h>
#include <unistd.h>
#include <vector>
#include "ns3/command-line.h"
#include "ns3/config.h"
#include "ns3/string.h"
#include "ns3/mobility-helper.h"
#include "ns3/constant-position-mobility-model.h"
#include "ns3/multi-model-spectrum-channel.h"
#include "ns3/internet-stack-helper.h"
#include "ns3/ipv4-address-helper.h"
#include "ns3/application-container.h"
#include "ns3/packet-sink-helper.h"
#include "ns3/udp-client-server-helper.h"
#include "ns3/ipv4-global-routing-helper.h"
#include "ns3/progress-bar.h"
#include "ns3/seq-ts-header.h"
#include "ns3/packet-sink.h"
#include "ns3/packet-tag.h"
#include "ns3/ap-server-helper.h"
#include "ns3/flow-monitor-helper.h"

#include "ns3/arp-cache.h"

using namespace ns3;

struct stats_t
{
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

  uint8_t classId {0};   // 1 = type-1 CBR background, 2 = type-2 time-critical
};

std::map<Mac48Address, stats_t> g_statsMap; //!< map for statistics for each station
std::map<Ipv4Address, Mac48Address> g_Ip2Mac; //!< map for mapping IPv4 to MAC address
std::map<Mac48Address, stats_t> g_statsMapAp;  //!< map for starts for only AP

static uint8_t
TosForAc (const std::string &ac)
{
  if (ac == "AC_VO") return 0xc0;
  if (ac == "AC_VI") return 0xa0;
  if (ac == "AC_BE") return 0x00;
  if (ac == "AC_BK") return 0x20;
  NS_ABORT_MSG ("Invalid AC name: " << ac
                << " (expected AC_VO | AC_VI | AC_BE | AC_BK)");
  return 0;
}

void SinrTrace (Mac48Address addr, double sinr)
{
  g_statsMap[addr].sinr += sinr;
  g_statsMap[addr].totalBeacons++;
}

void RxTraceWithAddressParam (double logTime, Ptr<const Packet> p, const Address &src, const Address &dst)
{
  Ptr<Packet> pkt = p->Copy ();

  SeqTsHeader seqTs;
  PacketTag tag;
  pkt->RemovePacketTag(tag);
  pkt->RemoveHeader(seqTs);
  Time startLogTime = Seconds(logTime);

  if (Simulator::Now().GetSeconds () >= startLogTime.GetSeconds()) {

    Mac48Address srcMac = g_Ip2Mac.at (InetSocketAddress::ConvertFrom (src).GetIpv4 ());
    auto &s = g_statsMap[srcMac];
    s.rxBytes += p->GetSize ();
    s.pktDelays.push_back ((Simulator::Now() - seqTs.GetTs ()).GetSeconds ());
    s.pktTag.push_back (tag.GetValue());
    s.genTime.push_back (seqTs.GetTs().GetSeconds());
    s.rxTime.push_back (Simulator::Now().GetSeconds());
    s.src.push_back (srcMac);
  }
}



int main(int argc, char *argv[])
{
  //LogComponentEnable("QosFrameExchangeManager", LOG_LEVEL_DEBUG);
  //LogComponentEnable("WifiPhyStateHelper", LOG_LEVEL_DEBUG);
  //LogComponentEnable("WifiMac", LOG_LEVEL_DEBUG);
  //LogComponentEnable("ApWifiMac", LOG_LEVEL_DEBUG);
  //LogComponentEnable("PhyEntity", LOG_LEVEL_DEBUG);

  //LogComponentEnable("WifiDefaultAckManager", LOG_LEVEL_DEBUG);
  //LogComponentEnable("WifiRemoteStationManager", LOG_LEVEL_DEBUG);
  //LogComponentEnable("HeFrameExchangeManager", LOG_LEVEL_DEBUG);
  //LogComponentEnable("HtFrameExchangeManager", LOG_LEVEL_DEBUG);
  //LogComponentEnable("BlockAckManager", LOG_LEVEL_DEBUG);
  //LogComponentEnable("OriginatorBlockAckAgreement", LOG_LEVEL_DEBUG);
  //LogComponentEnable("RecipientBlockAckAgreement", LOG_LEVEL_DEBUG);
  //LogComponentEnable("ChannelAccessManager", LOG_LEVEL_DEBUG);
  //LogComponentEnable("QosTxop", LOG_LEVEL_ALL);
  //LogComponentEnable("MpduAggregator", LOG_LEVEL_DEBUG);
  //LogComponentEnable("QosFrameExchangeManager", LOG_LEVEL_DEBUG);
  //LogComponentEnable("WifiMacQueue", LOG_LEVEL_ALL);
  //LogComponentEnable("VlceMultiUserScheduler", LOG_LEVEL_ALL);

  double simulationTime {10};//seconds
  std::string logDir {"output"};
  double minDistance {1.0}; //meters
  double maxDistance {40}; //meters
  std::size_t typeOneNStations {18};
  std::size_t typeTwoNStations {1};
  double apHeight {3}; //meters
  double staHeight {1}; //meters
  double startLogTime = {1.030};
  std::string simType {"OFDMA"};
  bool enablePcap {false}; 



  std::string frequency {"5"}; //whether 2.4, 5 or 6 GHz
  uint32_t channelWidth {40}; //for 2.4 <= 40 MHz, for 5 <= 160 MHz
  uint32_t guardInterval {800}; //in ns
  int mcs {8}; // 0..11
  std::string phyModel {"Spectrum"}; //Spectrum or Yans
  bool enableShadowing = false;
  double txPowerStart = {40.0412}; //16.0206
  double txPowerEnd = {40.0412};
  uint32_t nMsdus = 1;
  uint32_t nRaRus {0};

  std::string cmabAlgorithm {"CUCB"};       // CUCB | ThompsonSampling | EpsilonGreedy | EXP3M
  std::string cmabRewardType {"Binary"};    // Binary | FairnessWeighted
  double cmabUcbConstant {std::sqrt(2.0)};
  double cmabEpsilon {0.1};
  double cmabExp3Gamma {0.1};


  std::string dlAckSeqType {"AGGR-MU-BAR"};
  bool enableUlOfdma {true};
  bool enableBsrp {true};
  double accessReqInterval = {0}; //microseconds
  bool useRts {false};
  bool useExtendedBlockAck {true};
  bool useMuEdca {false};
  uint32_t nMpdus = 1;
  bool UseCentral26TonesRus = {true};
  bool DelayAccessReqUponAccess = {true};
  double txOpLimits = {2080};  //AC_VO default value in microseconds 2080
  std::string ruAllocationType {"ru-undefined"};
  HeRu::RuType ruAllocType {HeRu::RU_UNDEFINED};
  uint32_t OCwMin {7};
  uint32_t OCwMax {127};
  std::string scheduler {"ns3::RrMultiUserScheduler"};
  double  muEdcaTimer {8192 * 5};
  double maxTimeInList {8192 * 5}; //amount credit a stations can have when using
                        //RrMultiUserScheduler, and how long to disable edca for
                        //in VlceMultiUserScheduler in MicroSeconds


  uint32_t ulPayloadSize = 700; // must fit in the max TX duration when transmitting at MCS 0 over an RU of 26 tones
  std::string trafficType {"CBR"}; //CBR or not
  double interval {0.00208}; //seconds
  bool randomStart {false};
  std::string accessCategory {"AC_VO"};
  bool enableAggregation {false};
  double pMean {0.1};

  std::string type1Ac {"AC_BE"};
  std::string type2Ac {"AC_VO"};

  CommandLine cmd (__FILE__);

  //Experiment set-up
  cmd.AddValue ("simulationTime", "Simulation time in seconds", simulationTime);
  cmd.AddValue ("logDir", "Directory for the output stats files", logDir);
  cmd.AddValue ("minDistance", "Minimum distance in meters between the station and the access point", minDistance);
  cmd.AddValue ("maxDistance", "Maximum distance in meters between the station and the access point", maxDistance);
  cmd.AddValue ("typeOneNStations", "number of non-AP HE stations that generate CBR traffic", typeOneNStations);
  cmd.AddValue ("typeTwoNStations", "number of non-AP HE stations that generate sporadic traffic", typeTwoNStations);
  cmd.AddValue ("apHeight", "Height of AP [m]", apHeight);
  cmd.AddValue ("staHeight", "Height of STA [m]", staHeight);
  cmd.AddValue ("startLogTime","Time to begin logging [seconds]", startLogTime);
  cmd.AddValue ("simType","the type of sim to run e.g OFDMA+MUEDCA (least timer value) | OFDMA+EDCA(non-standard no disabling of edca (comment out the code in he-frame-exchange for disabling)) | OFDMA_only", simType);
  cmd.AddValue ("enablePcap","Enable/Disable generating PCAP files of the simulation", enablePcap);




  //PHY params
  cmd.AddValue ("frequency", "Whether working in the 2.4, 5 or 6 GHz band (other values gets rejected)", frequency);
  cmd.AddValue ("channelWidth", "Channel width used for transmissions (20, 40, 80, 80+80, 160 MHz)", channelWidth);
  cmd.AddValue ("guardInterval", "The value of the guard interval (800, 1600, 3200 ns)", guardInterval);
  cmd.AddValue ("mcs", "if set, limit testing to a specific MCS (0-11)", mcs);
  cmd.AddValue ("phyModel", "PHY model to use when OFDMA is disabled (Yans or Spectrum). If OFDMA is enabled then Spectrum is automatically selected", phyModel);
  cmd.AddValue ("enableShadowing", "Enable/disable gaussian shadowing", enableShadowing);
  cmd.AddValue ("txPowerStart", "Minimum available transmissions level (dBm)", txPowerStart);
  cmd.AddValue ("txPowerEnd", "Maximum available transmissions level (dBm)", txPowerEnd);
  cmd.AddValue ("UseCentral26TonesRus","Enable/Disable the use of Cenral 26 tone RUs", UseCentral26TonesRus);
  cmd.AddValue ("ruAllocationType","The type of RUs allocated to STAs, if undefined - dynamically selected based on the number of STAs (ru-26-tone, ru-52-tone)", ruAllocationType);
  cmd.AddValue ("nRaRus","Number of RUs to reserve for Random Access", nRaRus);


  //MAC params
  cmd.AddValue ("useRts", "Enable/disable RTS/CTS", useRts);
  cmd.AddValue ("useExtendedBlockAck", "Enable/disable use of extended BACK", useExtendedBlockAck);
  cmd.AddValue ("dlAckType", "Ack sequence type for DL OFDMA (NO-OFDMA, ACK-SU-FORMAT, MU-BAR, AGGR-MU-BAR)", dlAckSeqType);
  cmd.AddValue ("enableUlOfdma", "Enable UL OFDMA (useful if DL OFDMA is enabled and TCP is used)", enableUlOfdma);
  cmd.AddValue ("enableBsrp", "Enable BSRP (useful if DL and UL OFDMA are enabled and TCP is used)", enableBsrp);
  cmd.AddValue ("muSchedAccessReqInterval", "Duration of the interval between two requests for channel access made by the MU scheduler (MicroSeconds)", accessReqInterval);
  cmd.AddValue ("useMuEdca", "Enable/disable Specific EDCA parameters set", useMuEdca);
  cmd.AddValue ("nMsdus", "Number of aggregated MSDUs (=< 11398/740 for VHT/HE/EHT PPDUs)", nMsdus);
  cmd.AddValue ("nMpdus", "Number of aggregated MPDUs (=< 6500631/740 for HE PPDUs)", nMpdus);
  cmd.AddValue ("DelayAccessReqUponAccess", "Enable/Disable delay of access req only upon access grant", DelayAccessReqUponAccess);
  cmd.AddValue ("TxOPLimits", "TX Opportunity limits in microseconds", txOpLimits);
  cmd.AddValue ("OCwMin", "Min OFDMA CW", OCwMin);
  cmd.AddValue ("OCwMax", "Max OFDMA CW", OCwMax);
  cmd.AddValue ("scheduler", "Type of resource scheduler to use  e.g ns3::RrMultiUserScheduler | ns3::VlceMultiUserScheduler", scheduler);

  cmd.AddValue ("muEdcaTimer", "How long to disable EDCA for and for VlceMultiUserScheduler, how long to stay in polling list without transmission (in Seconds)", muEdcaTimer);  // todo : multi user scedualer for A2P?
  cmd.AddValue ("maxTimeInList", "VLCE poll-list eviction timeout (microseconds). Default 8192*5 us = 41 ms.", maxTimeInList);
  cmd.AddValue ("cmabAlgorithm", "CMAB algorithm (CUCB | ThompsonSampling | EpsilonGreedy | EXP3M)", cmabAlgorithm);
  cmd.AddValue ("cmabRewardType", "Per-arm reward shape (Binary | FairnessWeighted)", cmabRewardType);
  cmd.AddValue ("cmabUcbConstant", "CUCB exploration constant c in score = mean + c*sqrt(2 ln t / n_i)", cmabUcbConstant);
  cmd.AddValue ("cmabEpsilon", "EpsilonGreedy random-exploration probability in [0,1]", cmabEpsilon);
  cmd.AddValue ("cmabExp3Gamma", "EXP3.M mixing parameter gamma in (0,1]", cmabExp3Gamma);



  //Traffic params
  cmd.AddValue ("ulPayloadSize", "the application payload size in bytes for ul traffic", ulPayloadSize);
  cmd.AddValue ("interval", "Average inter-packet interval [s]", interval);
  cmd.AddValue ("accessCategory", "Access category for traffic: AC_BE, AC_BK, AC_VO, AC_VI", accessCategory);
  cmd.AddValue ("enableAggregation", "Enable/disable mpdu/msdu aggregation", enableAggregation);
  cmd.AddValue ("pMean", "Exponential Mean for how often stations generate packets in Seconds", pMean);
  cmd.AddValue ("type1Ac", "Access category for type-1 CBR background sensors (AC_BE | AC_BK | AC_VI | AC_VO)", type1Ac);
  cmd.AddValue ("type2Ac", "Access category for type-2 sporadic time-critical sensors (AC_BE | AC_BK | AC_VI | AC_VO)", type2Ac);



  cmd.Parse (argc, argv);


  /*
   * make and change into the lodDir
   */
  std::string mkdir {"mkdir -p " + logDir};
  if ( system(mkdir.c_str()) == -1 )
  {
    NS_FATAL_ERROR("Error in creating log directory" << strerror(errno));
  }
  if ( chdir(logDir.c_str()) == -1 )
  {
    perror ("chdir");
    NS_FATAL_ERROR ("Error changing into directory " << strerror (errno));
  }

  /*
   * rts/cts
   * Uniform RTS policy across all schedulers (no per-simType asymmetry):
   *   useRts=true  -> RTS for unicast packets >= 700 B (also includes aggregated MPDUs).
   *   useRts=false -> RTS effectively disabled.
   * MU-RTS protection of MU-TX bursts is always off.
   * */
  Config::SetDefault ("ns3::WifiRemoteStationManager::RtsCtsThreshold",
                      StringValue (useRts ? "700" : "4294967295"));
  Config::SetDefault ("ns3::WifiDefaultProtectionManager::EnableMuRts", BooleanValue (false));

  /*
   * Downlink ACK type
   * */
  if (dlAckSeqType == "ACK-SU-FORMAT")
    {
      Config::SetDefault ("ns3::WifiDefaultAckManager::DlMuAckSequenceType",
                          EnumValue (WifiAcknowledgment::DL_MU_BAR_BA_SEQUENCE));
    }
  else if (dlAckSeqType == "MU-BAR")
    {
      Config::SetDefault ("ns3::WifiDefaultAckManager::DlMuAckSequenceType",
                          EnumValue (WifiAcknowledgment::DL_MU_TF_MU_BAR));
    }
  else if (dlAckSeqType == "AGGR-MU-BAR")
    {
      Config::SetDefault ("ns3::WifiDefaultAckManager::DlMuAckSequenceType",
                          EnumValue (WifiAcknowledgment::DL_MU_AGGREGATE_TF));
    }
  else if (dlAckSeqType != "NO-OFDMA")
    {
      NS_ABORT_MSG ("Invalid DL ack sequence type (must be NO-OFDMA, ACK-SU-FORMAT, MU-BAR or AGGR-MU-BAR)");
    }

  /*
   * PHY model
   */
  if (phyModel != "Yans" && phyModel != "Spectrum")
    {
      NS_ABORT_MSG ("Invalid PHY model (must be Yans or Spectrum)");
    }

  /*
   * Type of resource unit tones
   */
  if (ruAllocationType == "ru-26-tone" )
    ruAllocType = HeRu::RU_26_TONE;
  else if (ruAllocationType == "ru-52-tone")
    ruAllocType = HeRu::RU_52_TONE;

  /*
   * Create totalNStations of STA and 1 AP
   */
  NodeContainer wifiStaNodes;
  wifiStaNodes.Create(typeOneNStations + typeTwoNStations);
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

  Ptr<ConstantPositionMobilityModel> apMobility = CreateObject<ConstantPositionMobilityModel> ();
  apMobility->SetPosition ({0, 0, apHeight});
  wifiApNode.Get (0)->AggregateObject (apMobility);

  /*
   * To use specific UORA Parameter sets
   */
  if(nRaRus)
  {
    Config::SetDefault ("ns3::HeConfiguration::OCwMin",UintegerValue(OCwMin));
    Config::SetDefault("ns3::HeConfiguration::OCwMax", UintegerValue(OCwMax));
  }
    //prevent stations from explicitly sending BAR request
    Config::SetDefault("ns3::QosTxop::UseExplicitBarAfterMissedBlockAck", BooleanValue(false));
    Config::SetDefault("ns3::WifiDefaultAckManager::UseExplicitBar", BooleanValue(false));
    Config::SetDefault("ns3::WifiMacQueue::MaxDelay", TimeValue (MilliSeconds(500)) );

  /*
   * To use specific MU-EDCA parameters for various AC
   */
  if (useMuEdca)
    {
      //STA AIFSN
      Config::SetDefault ("ns3::HeConfiguration::MuBkAifsn", UintegerValue (0));
      Config::SetDefault ("ns3::HeConfiguration::MuBeAifsn", UintegerValue (0));
      Config::SetDefault ("ns3::HeConfiguration::MuViAifsn", UintegerValue (0));
      Config::SetDefault ("ns3::HeConfiguration::MuVoAifsn", UintegerValue (0));

      //STA CW min
      Config::SetDefault ("ns3::HeConfiguration::MuBkCwMin", UintegerValue (32767));
      Config::SetDefault ("ns3::HeConfiguration::MuBeCwMin", UintegerValue (32767));
      Config::SetDefault ("ns3::HeConfiguration::MuViCwMin", UintegerValue (32767));
      Config::SetDefault ("ns3::HeConfiguration::MuVoCwMin", UintegerValue (32767));

      //STA CW max
      Config::SetDefault ("ns3::HeConfiguration::MuBkCwMax", UintegerValue (32767));
      Config::SetDefault ("ns3::HeConfiguration::MuBeCwMax", UintegerValue (32767));
      Config::SetDefault ("ns3::HeConfiguration::MuViCwMax", UintegerValue (32767));
      Config::SetDefault ("ns3::HeConfiguration::MuVoCwMax", UintegerValue (32767));

      // Stagger between MuTxStartTime (AP MU-TX begin) and HtMuTxStartTime
      // (EDCA disable) for A2P/A2PV2. AP starts polling first; HT EDCA stays
      // enabled for a short overlap window so STAs can bootstrap into the
      // VLCE poll list via EDCA *while* the AP is already cycling triggers.
      double muTxStartSec = startLogTime - 2;
      if (simType =="A2P" || simType =="A2PV2") {
          muEdcaTimer = maxTimeInList;
          Config::SetDefault("ns3::HtFrameExchangeManager::HtMuTxStartTime",
                             TimeValue(Seconds(startLogTime)));
          muTxStartSec = startLogTime;

          Config::SetDefault("ns3::QosFrameExchangeManager::TrackBufferDrain",
                             BooleanValue(simType == "A2P"));
        }
      else if (simType =="UORA" || simType == "CMAB") {
          //STA timer (validity of set)
          /* Disable EDCA for the duration of the entire simulation:
           *    Calculate the ceiling multiple of
           *    8192 from simulation time
           */
          int simTime = Seconds(simulationTime).GetMicroSeconds();
          muEdcaTimer = (simTime % 8192 == 0) ? simTime : ( std::round( simTime / 8192.0) * 8192);

          Config::SetDefault("ns3::QosTxop::LongerEDCADisable", BooleanValue(true));

          Config::SetDefault("ns3::QosFrameExchangeManager::TrackBufferDrain",
                             BooleanValue(simType == "UORA"));

          if (simType =="UORA" && nRaRus) {
            Config::SetDefault ("ns3::HeConfiguration::OCwMin",UintegerValue(OCwMin));
            Config::SetDefault("ns3::HeConfiguration::OCwMax", UintegerValue(OCwMax));
            Config::SetDefault("ns3::HeFrameExchangeManager::SendQosNullAfterBasicTf", BooleanValue(true));
          }
      }
      else {
          NS_FATAL_ERROR ("A valid simulation type is needed to continue" << strerror (errno));
      }

        Config::SetDefault ("ns3::HeConfiguration::BkMuEdcaTimer", TimeValue (MicroSeconds(muEdcaTimer)));
        Config::SetDefault ("ns3::HeConfiguration::BeMuEdcaTimer", TimeValue (MicroSeconds(muEdcaTimer)));
        Config::SetDefault ("ns3::HeConfiguration::ViMuEdcaTimer", TimeValue (MicroSeconds(muEdcaTimer)));
        Config::SetDefault ("ns3::HeConfiguration::VoMuEdcaTimer", TimeValue (MicroSeconds(muEdcaTimer)));

        Config::SetDefault("ns3::HtFrameExchangeManager::DisableEDCA", BooleanValue(true));

        //Config::SetDefault("ns3::HtFrameExchangeManager::HtMuTxStartTime", TimeValue(Seconds(startLogTime)));
        Config::SetDefault("ns3::HeFrameExchangeManager::MuTxStartTime", TimeValue(Seconds(muTxStartSec)));
    }


  /*
   * SIFS and Slot time
   */
  Config::SetDefault("ns3::WifiPhy::Sifs", TimeValue(MicroSeconds(16)));
  Config::SetDefault("ns3::WifiPhy::Slot", TimeValue(MicroSeconds(9)));

  /*
   * Retry limit
   */
  Config::SetDefault ("ns3::WifiRemoteStationManager::MaxSsrc", UintegerValue (32));
  Config::SetDefault ("ns3::WifiRemoteStationManager::MaxSlrc", UintegerValue (32));

  /*
   * Intrinsic Queue Size reporting
   */
  Config::SetDefault("ns3::QosFrameExchangeManager::SetQueueSize", BooleanValue(true));

  if (enableAggregation)
  {
    Config::SetDefault ("ns3::WifiRemoteStationManager::FragmentationThreshold", StringValue ("990000"));
    //Config::SetDefault ("ns3::WifiMac::VO_MaxAmpduSize", UintegerValue (0)); //6500631
    //Config::SetDefault("ns3::WifiMac::VO_MaxAmsduSize", UintegerValue (11398)); //11398
    //Config::SetDefault ("ns3::WifiMac::BE_MaxAmpduSize", UintegerValue (0)); //6500631
    //Config::SetDefault("ns3::WifiMac::BE_MaxAmsduSize", UintegerValue (11398)); //11398
  }

  /*
   * Set up Network devices
   */
  NetDeviceContainer apNetDevice, staNetDevices;
  WifiMacHelper wifimac;
  WifiHelper wifi;
  std::string channelStr ("{0, " + std::to_string (channelWidth) + ", ");

  wifi.SetStandard(WIFI_STANDARD_80211ax);

  if (frequency == "2.4")
    {
      channelStr += "BAND_2_4GHZ, 0}";
    }
  else if (frequency == "5")
    {
      channelStr += "BAND_5GHZ, 0}";
    }
  else if (frequency == "6")
    {
      channelStr += "BAND_6GHZ, 0}";
    }
  else
    {
      NS_FATAL_ERROR ("Wrong frequency value!");
    }
    std::ostringstream oss;
  oss << "HeMcs" << mcs;
  wifi.SetRemoteStationManager("ns3::ConstantRateWifiManager","DataMode", StringValue(oss.str()), "ControlMode", StringValue(oss.str()));

  /*Set guard interval and MPDU buffer size
   */
  wifi.ConfigHeOptions ("GuardInterval", TimeValue (NanoSeconds (guardInterval)),
                      "MpduBufferSize", UintegerValue (useExtendedBlockAck ? 256 : 64));
  /*
   * Setup PHY and MAC layers
   */

  Ssid ssid = Ssid("ns3-80211ax");

  Ptr<ConstantSpeedPropagationDelayModel> delayModel = CreateObject<ConstantSpeedPropagationDelayModel> ();
  Ptr<IeeeIndoorPropagationLossModel> propModel = CreateObject<IeeeIndoorPropagationLossModel> ();
  if (enableShadowing)
    {
      propModel->SetAttribute ("EnableShadowing", BooleanValue (true));
    }


  if (phyModel == "Spectrum")
    {
      /*
      * SingleModelSpectrumChannel cannot be used with 802.11ax because two
      * spectrum models are required: one with 78.125 kHz bands for HE PPDUs
      * and one with 312.5 kHz bands for, e.g., non-HT PPDUs (for more details,
      * see issue #408 (CLOSED))
      */
      Ptr<MultiModelSpectrumChannel> spectrumChannel = CreateObject<MultiModelSpectrumChannel> ();
      spectrumChannel->AddPropagationLossModel (propModel);
      spectrumChannel->SetPropagationDelayModel (delayModel);
      SpectrumWifiPhyHelper phy;
      phy.SetPcapDataLinkType (WifiPhyHelper::DLT_IEEE802_11_RADIO);
      phy.SetChannel (spectrumChannel);
      phy.Set ("ChannelSettings", StringValue (channelStr));
      phy.Set("TxPowerStart", DoubleValue(txPowerStart ));
      phy.Set("TxPowerEnd", DoubleValue(txPowerEnd ));

      wifimac.SetType ("ns3::StaWifiMac", "Ssid", SsidValue (ssid),
                       "VO_BlockAckThreshold", UintegerValue(0));

      staNetDevices = wifi.Install (phy, wifimac, wifiStaNodes);

      if (dlAckSeqType != "NO-OFDMA")
        {
          wifimac.SetMultiUserSchedulerNoAttr (scheduler);
          wifimac.SetMultiUserSchedulerAttribute("EnableUlOfdma", BooleanValue (enableUlOfdma));
          wifimac.SetMultiUserSchedulerAttribute("EnableBsrp", BooleanValue (enableBsrp));
          wifimac.SetMultiUserSchedulerAttribute("AccessReqInterval", TimeValue (MicroSeconds(accessReqInterval)));
          wifimac.SetMultiUserSchedulerAttribute("DelayAccessReqUponAccess", BooleanValue (DelayAccessReqUponAccess));
          wifimac.SetMultiUserSchedulerAttribute("UseCentral26TonesRus", BooleanValue (UseCentral26TonesRus));
          wifimac.SetMultiUserSchedulerAttribute("NStations", UintegerValue (typeOneNStations + typeTwoNStations));
          wifimac.SetMultiUserSchedulerAttribute("AccessReqAc",EnumValue(AcIndex::AC_VO));
          wifimac.SetMultiUserSchedulerAttribute("RuAllocationType", EnumValue(ruAllocType));
          wifimac.SetMultiUserSchedulerAttribute("UlPsduSize", UintegerValue(ulPayloadSize));

          if (scheduler == "ns3::VlceMultiUserScheduler" ) {
            wifimac.SetMultiUserSchedulerAttribute("MaxTimeInList", TimeValue( MicroSeconds(maxTimeInList) ));
          }
          if (scheduler == "ns3::UoraMultiUserScheduler" ) {
            wifimac.SetMultiUserSchedulerAttribute("NumRandomAccessRus", UintegerValue(nRaRus));
          }
          if (scheduler == "ns3::CmabMultiUserScheduler") {
            NS_ABORT_MSG_IF (cmabAlgorithm != "CUCB" &&
                             cmabAlgorithm != "ThompsonSampling" &&
                             cmabAlgorithm != "EpsilonGreedy" &&
                             cmabAlgorithm != "EXP3M",
                             "Invalid --cmabAlgorithm: " << cmabAlgorithm
                             << " (expected CUCB | ThompsonSampling | EpsilonGreedy | EXP3M)");
            NS_ABORT_MSG_IF (cmabRewardType != "Binary" &&
                             cmabRewardType != "FairnessWeighted",
                             "Invalid --cmabRewardType: " << cmabRewardType
                             << " (expected Binary | FairnessWeighted)");
            wifimac.SetMultiUserSchedulerAttribute("Algorithm",   StringValue(cmabAlgorithm));
            wifimac.SetMultiUserSchedulerAttribute("RewardType",  StringValue(cmabRewardType));
            wifimac.SetMultiUserSchedulerAttribute("UcbConstant", DoubleValue(cmabUcbConstant));
            wifimac.SetMultiUserSchedulerAttribute("Epsilon",     DoubleValue(cmabEpsilon));
            wifimac.SetMultiUserSchedulerAttribute("Exp3Gamma",   DoubleValue(cmabExp3Gamma));
          }

          //this is for uora alone
          //wifimac.SetMultiUserSchedulerAttribute("NumRandomAccessRus", UintegerValue(nRaRus));

        }
        wifimac.SetType ("ns3::ApWifiMac",
                  "EnableBeaconJitter", BooleanValue (false),
                  "Ssid", SsidValue (ssid),
                  "BsrLifetime", TimeValue(MilliSeconds(200000)),
                  "VO_BlockAckThreshold", UintegerValue(0));

      apNetDevice = wifi.Install (phy, wifimac, wifiApNode);
      if (enablePcap) {
        phy.EnablePcap("wifi-ax-ofdma-ap", apNetDevice); // AP-side only
        //phy.EnablePcap("wifi-ax-ofdma-sta", staNetDevices);
      }
    }
  else
    {
      Ptr<YansWifiChannel> channel = CreateObject<YansWifiChannel> ();
      channel->SetPropagationLossModel (propModel);
      channel->SetPropagationDelayModel (delayModel);

      YansWifiPhyHelper YansPhy;
      YansPhy.SetPcapDataLinkType (WifiPhyHelper::DLT_IEEE802_11_RADIO);
      YansPhy.SetChannel (channel); //channel.Create ()
      wifimac.SetType ("ns3::StaWifiMac", "Ssid", SsidValue (ssid));

      YansPhy.Set ("ChannelSettings", StringValue (channelStr));
      YansPhy.Set("TxPowerStart", DoubleValue(txPowerStart ));
      YansPhy.Set("TxPowerEnd", DoubleValue(txPowerEnd ));
      staNetDevices = wifi.Install (YansPhy, wifimac, wifiStaNodes);

      wifimac.SetType ("ns3::ApWifiMac",
                       "EnableBeaconJitter", BooleanValue (false),
                       "Ssid", SsidValue (ssid),
                       "VO_BlockAckThreshold", UintegerValue(0));
      apNetDevice = wifi.Install (YansPhy, wifimac, wifiApNode);
      if (enablePcap) {
        YansPhy.EnablePcap("wifi-ax-edca-ap", apNetDevice); // enable pcap tracing
        YansPhy.EnablePcap("wifi-ax-edca-sta", staNetDevices);
      }
    }


  /*
   * Internet Stack on
   */
  InternetStackHelper internetStack;
  internetStack.Install(wifiApNode);
  internetStack.Install(wifiStaNodes);

  Ipv4AddressHelper address;
  address.SetBase("192.168.1.0", "255.255.255.0");
  Ipv4InterfaceContainer staNodeInterfaces = address.Assign (staNetDevices);
  Ipv4InterfaceContainer apNodeInterface = address.Assign (apNetDevice);

  ArpCache::PopulateArpCache ();


  /*
   * Setup server on AP and client on STAs applications
   */
  uint16_t port = 9;
  ApplicationContainer apServerApps;

  InetSocketAddress voAddress(apNodeInterface.GetAddress(0), port);
  voAddress.SetTos(0xc0); // AC_VO
  PacketSinkHelper sinkHelper("ns3::UdpSocketFactory", voAddress);
  apServerApps = sinkHelper.Install(wifiApNode);

  apServerApps.Start(Seconds(0));
  apServerApps.Stop(Seconds(simulationTime + startLogTime));

  double staStartTime = startLogTime - 2.0;

  const uint8_t type1Tos = TosForAc (type1Ac);
  const uint8_t type2Tos = TosForAc (type2Ac);

  for (size_t i = 0; i < typeOneNStations + typeTwoNStations; ++i)
  {
    staStartTime += 0.00108;
    const bool isType1 = (i < typeOneNStations);

    InetSocketAddress voAddr(apNodeInterface.GetAddress(0), port);
    
    voAddr.SetTos(isType1 ? type1Tos : type2Tos);

    UdpClientHelper announcer(voAddr);
    announcer.SetAttribute("MaxPackets", UintegerValue(1));
    announcer.SetAttribute("PacketSize", UintegerValue(500));
    announcer.SetAttribute("EnableRandom", BooleanValue(false));
    announcer.SetAttribute("Interval", TimeValue(Seconds(1)));

    auto announceApp = announcer.Install(wifiStaNodes.Get(i));
    announceApp.Start(Seconds(1 + i * 0.001));
    announceApp.Stop(Seconds(startLogTime - 2.0));

    // Main uplink traffic -- ToS picks per-class AC.
    InetSocketAddress trafficAddr(apNodeInterface.GetAddress(0), port);
    trafficAddr.SetTos(isType1 ? type1Tos : type2Tos);
    UdpClientHelper trafficGen(trafficAddr);
    trafficGen.SetAttribute("MaxPackets", UintegerValue(0));
    trafficGen.SetAttribute("PacketSize", UintegerValue(ulPayloadSize));

    if (trafficType == "CBR" && isType1)
    {
      trafficGen.SetAttribute("EnableRandom", BooleanValue(false));
      trafficGen.SetAttribute("Interval", TimeValue(Seconds(interval)));
    }
    else
    {
      trafficGen.SetAttribute("EnableRandom", BooleanValue(true));
      std::ostringstream distr;
      distr << "ns3::ExponentialRandomVariable[Mean=" << pMean << "|Bound=0]";
      trafficGen.SetAttribute("IntervalRandomVariable", StringValue(distr.str()));
    }

    auto trafficApp = trafficGen.Install(wifiStaNodes.Get(i));

    if (randomStart)
    {
      Ptr<UniformRandomVariable> rv = CreateObject<UniformRandomVariable>();
      rv->SetAttribute("Max", DoubleValue(1.5));
      // Optional jittered start
      // trafficApp.StartWithJitter(Seconds(1.0), rv);
    }
    else
    {
      trafficApp.Start(Seconds(staStartTime));
    }

    trafficApp.Stop(Seconds(simulationTime + startLogTime));
  }


  Simulator::Schedule (Seconds (0), &Ipv4GlobalRoutingHelper::PopulateRoutingTables);

  for (uint32_t i = 0; i < staNetDevices.GetN (); i++)
  {
    Ptr<WifiNetDevice> dev = DynamicCast<WifiNetDevice> ( staNetDevices.Get(i) );
    Ptr<WifiMac> wifi_mac = dev->GetMac();
    if (enableAggregation) {
      // Apply aggregation to all four ACs so type-1 (AC_BE by default) and
      // type-2 (AC_VO by default) both benefit; remaining ACs left enabled
      // for completeness.
      for (const char* ac : {"BK", "BE", "VI", "VO"}) {
        wifi_mac->SetAttribute(std::string(ac) + "_MaxAmpduSize", UintegerValue (nMpdus * ulPayloadSize ));
        wifi_mac->SetAttribute(std::string(ac) + "_MaxAmsduSize", UintegerValue (nMsdus * ulPayloadSize ));
      }
    }
    wifi_mac->GetQosTxop(AC_VO)->SetTxopLimit(MicroSeconds(txOpLimits));
    auto mac = Mac48Address::ConvertFrom (staNetDevices.Get (i)->GetAddress ());
    auto ip = staNodeInterfaces.Get (i).first->GetAddress (1, 0).GetAddress ();
    g_Ip2Mac[ip] = mac;
    g_statsMap[mac].classId = (i < typeOneNStations) ? 1 : 2;

    staNetDevices.Get(i)->GetObject<WifiNetDevice>()->GetPhy()->GetPhyEntity(WIFI_MOD_CLASS_OFDM)->TraceConnectWithoutContext("SinrTrace", MakeBoundCallback (&SinrTrace, Mac48Address::ConvertFrom (staNetDevices.Get (i)->GetAddress ())));
    staNetDevices.Get(i)->GetObject<WifiNetDevice>()->GetPhy()->GetPhyEntity(WIFI_MOD_CLASS_HE)->TraceConnectWithoutContext("SinrTrace", MakeBoundCallback (&SinrTrace, Mac48Address::ConvertFrom (staNetDevices.Get (i)->GetAddress ())));
  }

  for (uint32_t i = 0; i < apNetDevice.GetN (); i++)
  {
    Ptr<WifiNetDevice> dev = DynamicCast<WifiNetDevice> ( apNetDevice.Get(i) );
    Ptr<WifiMac> wifi_mac = dev->GetMac();
    if (enableAggregation) {
      for (const char* ac : {"BK", "BE", "VI", "VO"}) {
        wifi_mac->SetAttribute(std::string(ac) + "_MaxAmpduSize", UintegerValue (nMpdus * ulPayloadSize ));
        wifi_mac->SetAttribute(std::string(ac) + "_MaxAmsduSize", UintegerValue (nMsdus * ulPayloadSize ));
      }
    }
    wifi_mac->GetQosTxop(AC_VO)->SetTxopLimit(MicroSeconds(txOpLimits));
  }

  Config::ConnectWithoutContext("/NodeList/*/ApplicationList/*/$ns3::PacketSink/RxWithAddresses", MakeBoundCallback(&RxTraceWithAddressParam, startLogTime));



  ProgressBar pg (Seconds(simulationTime + startLogTime ));
  Simulator::Stop (Seconds (simulationTime + startLogTime ));
  Simulator::Run ();


  // Compute throughput from g_statsMap, which is already gated by startLogTime
  // (see RxTraceWithAddressParam). This avoids counting the 2 s pre-log warmup
  // bytes that the PacketSink also receives. Denominator is the logging window
  // = simulationTime seconds (i.e., [startLogTime, startLogTime+simulationTime]).
  uint64_t rxBytesLogWindow = 0;
  for (const auto &kv : g_statsMap)
  {
    rxBytesLogWindow += kv.second.rxBytes;
  }

  Simulator::Destroy();

  double throughput = (rxBytesLogWindow * 8.0) / (simulationTime * 1e6); //Mbit/s

  std::ofstream totalStatsOutStream;
  totalStatsOutStream.open ("throughput.out", std::ios::out);
  totalStatsOutStream << "MCS\tBandwidth_MHz\tGuard_interval_ns\tThroughput_Mbps" << std::endl;
  totalStatsOutStream << mcs << "\t" << channelWidth << "\t" << guardInterval << "\t" << throughput << std::endl;
  totalStatsOutStream.close ();

  std::ofstream perStaOutStream;
  perStaOutStream.open ("per_sta_stats.out", std::ios::out);
  perStaOutStream << "MAC-addr\tSINR_dB\tRX_bytes\tAvg_delay_ms\tClass" << std::endl;
  for (auto &staStats : g_statsMap)
    {
      auto &s = staStats.second;
      if (s.totalBeacons > 0) s.sinr /= s.totalBeacons;
      double sumDelay = 0.;
      for (auto &delay : s.pktDelays)
        {
          sumDelay += delay * 1000.; //in ms
        }
      double avgMs = s.pktDelays.empty () ? 0.0 : sumDelay / s.pktDelays.size ();
      perStaOutStream << staStats.first << "\t" << s.sinr << "\t" << s.rxBytes
        << "\t" << avgMs << "\t" << static_cast<int>(s.classId) << std::endl;
    }
  perStaOutStream.close ();

  std::ofstream t2Pkt;
  t2Pkt.open ("type2_packets.out", std::ios::out);
  t2Pkt << "MAC-addr\tgen_s\trx_s\tdelay_ms" << std::endl;
  for (const auto &kv : g_statsMap)
    {
      if (kv.second.classId != 2) continue;
      const auto &s = kv.second;
      for (size_t i = 0; i < s.pktDelays.size (); ++i)
        {
          t2Pkt << kv.first << "\t"
                << s.genTime[i] << "\t"
                << s.rxTime[i] << "\t"
                << s.pktDelays[i] * 1000.0 << std::endl;
        }
    }
  t2Pkt.close ();


  return 0;
}
