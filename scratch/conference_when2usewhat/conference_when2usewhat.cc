/* -*-  Mode: C++; c-file-style: "gnu"; indent-tabs-mode:nil; -*- */
/*
 * Copyright (c) 2022
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

#include <algorithm>
#include <cerrno>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <sstream>
#include <string>
#include <ns3/wifi-module.h>
#include <unistd.h>
#include <vector>
#include <unordered_map>

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

  //wakeup_time
  uint64_t rxBytesWakeUp;
  std::vector<double> pktDelaysWakeUp, genTimeWakeUp, rxTimeWakeUp;
  std::vector<uint64_t> pktTagWakeUp;
  std::vector<Mac48Address> srcWakeUp;
};

std::map<Mac48Address, stats_t> g_statsMap; //!< map for statistics for each station
std::map<Ipv4Address, Mac48Address> g_Ip2Mac; //!< map for mapping IPv4 to MAC address
std::map<Mac48Address, stats_t> g_statsMapAp;  //!< map for starts for only AP
void SinrTrace (Mac48Address addr, double sinr)
{
  g_statsMap[addr].sinr += sinr;
  g_statsMap[addr].totalBeacons++;
}


void RxTraceWithAddress ( double startLogTime, Ptr<const Packet> p, const Address &src, const Address &dst)
{
  Ptr<Packet> pkt = p->Copy ();

  SeqTsHeader seqTs;
  PacketTag tag;
  pkt->RemovePacketTag(tag);
  pkt->RemoveHeader(seqTs);
  startLogTime *= 1e+9;

  if (Simulator::Now().GetNanoSeconds () >= startLogTime) {

    g_statsMap[g_Ip2Mac.at (InetSocketAddress::ConvertFrom (dst).GetIpv4 ())].rxBytes += p->GetSize ();
    g_statsMap[g_Ip2Mac.at (InetSocketAddress::ConvertFrom (dst).GetIpv4 ())].pktDelays.push_back ((Simulator::Now() - seqTs.GetTs ()).GetSeconds ());
    g_statsMap[g_Ip2Mac.at (InetSocketAddress::ConvertFrom (dst).GetIpv4 ())].pktTag.push_back (tag.GetValue());
    g_statsMap[g_Ip2Mac.at (InetSocketAddress::ConvertFrom (dst).GetIpv4 ())].genTime.push_back(seqTs.GetTs().GetSeconds() );
    g_statsMap[g_Ip2Mac.at (InetSocketAddress::ConvertFrom (dst).GetIpv4 ())].rxTime.push_back(Simulator::Now().GetSeconds());
    g_statsMap[g_Ip2Mac.at (InetSocketAddress::ConvertFrom (dst).GetIpv4 ())].src.push_back( g_Ip2Mac.at (InetSocketAddress::ConvertFrom (src).GetIpv4 ()));
  }
}

void RxTrace ( double startLogTime, Ptr< const Packet> p, const Address &src, const Address &dst, bool k)
{
  Ptr<Packet> pkt = p->Copy ();

  SeqTsHeader seqTs;
  PacketTag tag;
  pkt->RemovePacketTag(tag);
  pkt->RemoveHeader(seqTs);
  startLogTime *= 1e+9;


  if (Simulator::Now().GetNanoSeconds () >= startLogTime)
  {
    g_statsMap[g_Ip2Mac.at (InetSocketAddress::ConvertFrom (dst).GetIpv4 ())].rxBytesLate += p->GetSize ();
    g_statsMap[g_Ip2Mac.at (InetSocketAddress::ConvertFrom (dst).GetIpv4 ())].pktDelaysLate.push_back ((Simulator::Now() - seqTs.GetTs ()).GetSeconds ());
    g_statsMap[g_Ip2Mac.at (InetSocketAddress::ConvertFrom (dst).GetIpv4 ())].pktTagLate.push_back (tag.GetValue());
    g_statsMap[g_Ip2Mac.at (InetSocketAddress::ConvertFrom (dst).GetIpv4 ())].genTimeLate.push_back(seqTs.GetTs().GetSeconds() );
    g_statsMap[g_Ip2Mac.at (InetSocketAddress::ConvertFrom (dst).GetIpv4 ())].rxTimeLate.push_back(Simulator::Now().GetSeconds());
    g_statsMap[g_Ip2Mac.at (InetSocketAddress::ConvertFrom (dst).GetIpv4 ())].srcLate.push_back( g_Ip2Mac.at (InetSocketAddress::ConvertFrom (src).GetIpv4 ()));
  }
}


void RxTraceWakeUp ( double startLogTime, Ptr< const Packet> p, const Address &src, const Address &dst, size_t k)
{
  Ptr<Packet> pkt = p->Copy ();

  SeqTsHeader seqTs;
  OnOffTag tag;
  pkt->RemovePacketTag(tag);
  pkt->RemoveHeader(seqTs);
  startLogTime *= 1e+9;


  if (Simulator::Now().GetNanoSeconds () >= startLogTime)
  {
    g_statsMapAp[g_Ip2Mac.at (InetSocketAddress::ConvertFrom (dst).GetIpv4 ())].rxBytesLate += p->GetSize ();
    g_statsMapAp[g_Ip2Mac.at (InetSocketAddress::ConvertFrom (dst).GetIpv4 ())].pktDelaysWakeUp.push_back ((Simulator::Now() - seqTs.GetTs ()).GetSeconds ());
    g_statsMapAp[g_Ip2Mac.at (InetSocketAddress::ConvertFrom (dst).GetIpv4 ())].pktTagWakeUp.push_back (tag.GetValue());
    g_statsMapAp[g_Ip2Mac.at (InetSocketAddress::ConvertFrom (dst).GetIpv4 ())].genTimeWakeUp.push_back(seqTs.GetTs().GetSeconds() );
    g_statsMapAp[g_Ip2Mac.at (InetSocketAddress::ConvertFrom (dst).GetIpv4 ())].rxTimeWakeUp.push_back(Simulator::Now().GetSeconds());
    g_statsMapAp[g_Ip2Mac.at (InetSocketAddress::ConvertFrom (dst).GetIpv4 ())].srcWakeUp.push_back( g_Ip2Mac.at (InetSocketAddress::ConvertFrom (src).GetIpv4 ()));
  }
}


int  main(int argc, char *argv[])
{

  //LogComponentEnable("HeFrameExchangeManager", LOG_LEVEL_ALL);
  //LogComponentEnable("QosFrameExchangeManager", LOG_LEVEL_ALL);
  //LogComponentEnable("QosTxop", LOG_LEVEL_ALL);
  //LogComponentEnable("UoraMultiUserScheduler", LOG_LEVEL_ALL);
  double simulationTime {10};//seconds
  std::string logDir {"output"};
  double minDistance {1.0}; //meters
  double maxDistance {40}; //meters
  std::size_t totalNStations {100};
  std::size_t initNStations = {8};
  std::size_t nStationsToJoin = {0};
  double apHeight {3}; //meters
  double staHeight {1}; //meters
  double startLogTime = {1.030};
  double timeToJoin {5}; //seconds
  double initStaJoinTime {2}; //seconds
  std::size_t scenario {1};
  bool onOffFlag {true};
  std::string simType {"OFDMA"};
  bool enablePcap {false}; 


  std::string frequency {"5"}; //whether 2.4, 5 or 6 GHz
  uint32_t channelWidth {40}; //for 2.4 <= 40 MHz, for 5 <= 160 MHz
  uint32_t guardInterval {800}; //in ns
  int mcs {8}; // 0..11
  std::string phyModel {"Yans"};
  bool enableShadowing = false;
  double txPowerStart = {40.0412};
  double txPowerEnd = {40.0412};
  uint32_t nMsdus = 1;
  uint32_t nRaRus {0};
  std::string scheduler {"ns3::RrMultiUserScheduler"};


  std::string dlAckSeqType {"NO-OFDMA"};
  bool enableUlOfdma {true};
  bool enableBsrp {true};
  double accessReqInterval = {0}; //microseconds
  bool useRts {false};
  bool useExtendedBlockAck {false};
  bool useMuEdca {false};
  uint32_t nMpdus = 1;
  bool UseCentral26TonesRus = {false};
  bool DelayAccessReqUponAccess = {false};
  double txOpLimits = {2080};  //AC_VO default value in microseconds
  std::string ruAllocationType {"ru-undefined"};
  HeRu::RuType ruAllocType {HeRu::RU_UNDEFINED};
  uint32_t OCwMin {7};
  uint32_t OCwMax {127};
  double  muEdcaTimer {8192};
  double maxTimeInList {8192 * 5}; //amount credit a stations can have when using
                        //RrMultiUserScheduler, and how long to disable edca for
                        //in VlceMultiUserScheduler in MicroSeconds 


  uint32_t ulPayloadSize = 740; // must fit in the max TX duration when transmitting at MCS 0 over an RU of 26 tones
  uint32_t dlPayloadSize = 500;
  std::string trafficType {"CBR"};
  double interval {0.005}; //seconds
  std::string accessCategory {"AC_VO"};
  bool enableAggregation {false};
  double StartSendInterval {0.001}; //seconds
  bool strictWindow {true};
  double poissonMean {5};

  Mac48Address apMacAddress;


  CommandLine cmd (__FILE__);
  //Experiment set-up
  cmd.AddValue ("simulationTime", "Simulation time in seconds", simulationTime);
  cmd.AddValue ("logDir", "Directory for the output stats files", logDir);
  cmd.AddValue ("minDistance", "Minimum distance in meters between the station and the access point", minDistance);
  cmd.AddValue ("maxDistance", "Maximum distance in meters between the station and the access point", maxDistance);
  cmd.AddValue ("totalNStations", "Total number of non-AP HE stations", totalNStations);
  cmd.AddValue ("initNStations", "Initial number of non-AP HE stations to start transmitting", initNStations);
  cmd.AddValue ("nStationsToJoin", "Number of non-AP HE stations to join later", nStationsToJoin);
  cmd.AddValue ("apHeight", "Height of AP [m]", apHeight);
  cmd.AddValue ("staHeight", "Height of STA [m]", staHeight);
  cmd.AddValue ("startLogTime","Time to begin logging [seconds]",startLogTime);
  cmd.AddValue ("timeToJoin","Time for random stations to join [seconds]", timeToJoin);
  cmd.AddValue ("initStaJoinTime","Time at which Initial STAs transmit after established connection with AP [seconds]", initStaJoinTime);
  cmd.AddValue ("scenario","Scenario to simulate; 0 - only up to 8 active stations.  1 - idle stations joining along the way", scenario);
  cmd.AddValue ("onOffFlag","Enable on and off behavior of joining STAs or ONLY on and no off", onOffFlag);
  cmd.AddValue ("scheduler","The OFDMA scheduler to use e.g ns3::RrMultiUserScheduler | ns3::VlceMultiUserScheduler", scheduler);
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
  cmd.AddValue ("muEdcaTimer", "How long to disable EDCA for and for VlceMultiUserScheduler, how long to stay in polling list without transmission (in Seconds)", muEdcaTimer);


  //Traffic params
  cmd.AddValue ("ulPayloadSize", "the application payload size in bytes for ul traffic", ulPayloadSize);
  cmd.AddValue ("dlPayloadSize", "the application payload size in bytes for dl traffic", dlPayloadSize);
  cmd.AddValue ("interval", "Average inter-packet interval [s]", interval);
  cmd.AddValue ("accessCategory", "Access category for traffic: AC_BE, AC_BK, AC_VO, AC_VI", accessCategory);
  cmd.AddValue ("enableAggregation", "Enable/disable mpdu/msdu aggregation", enableAggregation);
  cmd.AddValue ("StartSendInterval", "Time interval within which stations randomly send initial packet [Seconds]", StartSendInterval);
  cmd.AddValue ("strictWindow", "To enable/disable strict AP sending time, independent of packet arrival", strictWindow);
  cmd.AddValue ("poissonMean", "The mean of the values returned by Poisson Distro", poissonMean);



  cmd.Parse (argc, argv);

  /*
   * make and change into the lodDir
   * */
  std::string mkdir {"mkdir -p " + logDir};
  if ( system(mkdir.c_str()) == -1 ) {
    NS_FATAL_ERROR("Error in creating log directory" << strerror(errno));
  }
  if ( chdir(logDir.c_str()) == -1 ) {
     perror ("chdir");
    NS_FATAL_ERROR ("Error changing into directory " << strerror (errno));
  }

  if (useRts)
    {
      Config::SetDefault ("ns3::WifiRemoteStationManager::RtsCtsThreshold", StringValue ("0"));
      Config::SetDefault("ns3::WifiDefaultProtectionManager::EnableMuRts", BooleanValue(true));
    }
  else
    {
      //use rts/cts for edca to see if this solves the retransmission issue in
      //some cases.
      Config::SetDefault ("ns3::WifiRemoteStationManager::RtsCtsThreshold", StringValue ("700"));
      Config::SetDefault("ns3::WifiDefaultProtectionManager::EnableMuRts", BooleanValue(false));
    }

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

  if (phyModel != "Yans" && phyModel != "Spectrum")
    {
      NS_ABORT_MSG ("Invalid PHY model (must be Yans or Spectrum)");
    }

  if (ruAllocationType == "ru-26-tone" )
    ruAllocType = HeRu::RU_26_TONE;
  else if (ruAllocationType == "ru-52-tone")
    ruAllocType = HeRu::RU_52_TONE;

  // create totalNStations of STA and 1 AP
  NodeContainer wifiStaNodes;
  wifiStaNodes.Create(totalNStations);
  NodeContainer wifiApNode;
  wifiApNode.Create(1);

  //Constant mobility and randomly distributed nodes around AP
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
   * To use specific MU-EDCA parameters for various AC
   * */
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

        if (simType =="A2P" || simType =="A2PV2") {
          muEdcaTimer = 8192 * 5;
          maxTimeInList = muEdcaTimer;
          Config::SetDefault("ns3::HtFrameExchangeManager::HtMuTxStartTime", TimeValue(Seconds(1.5)));
        }
        /*else if (simType == "OFDMA") {
          muEdcaTimer = 2088960;

        }*/
        else if (simType =="UORA" || simType == "OFDMA") {
          //STA timer (validity of set)
          /* Disable EDCA for the duration of the entire simulation:
           *    Calculate the ceiling multiple of
           *    8192 from simulation time
           */
          int simTime = Seconds(simulationTime).GetMicroSeconds();
          muEdcaTimer = (simTime % 8192 == 0) ? simTime : ( std::round( simTime / 8192.0) * 8192);
          
          Config::SetDefault("ns3::QosTxop::LongerEDCADisable", BooleanValue(true));

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
        Config::SetDefault("ns3::HeFrameExchangeManager::MuTxStartTime", TimeValue(Seconds(1.5)));
        
        
  }

  //sifs and slot time
  Config::SetDefault("ns3::WifiPhy::Sifs", TimeValue(MicroSeconds(16)));
  Config::SetDefault("ns3::WifiPhy::Slot", TimeValue(MicroSeconds(9)));

  //Retry limit
  Config::SetDefault ("ns3::WifiRemoteStationManager::MaxSsrc", UintegerValue (32));
  Config::SetDefault ("ns3::WifiRemoteStationManager::MaxSlrc", UintegerValue (32));

  Config::SetDefault("ns3::QosFrameExchangeManager::SetQueueSize", BooleanValue(true));

  if (enableAggregation)
    Config::SetDefault ("ns3::WifiRemoteStationManager::FragmentationThreshold", StringValue ("990000"));

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

  // Set guard interval and MPDU buffer size
  wifi.ConfigHeOptions ("GuardInterval", TimeValue (NanoSeconds (guardInterval)),
                      "MpduBufferSize", UintegerValue (useExtendedBlockAck ? 256 : 64));

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
          wifimac.SetMultiUserSchedulerAttribute("NStations", UintegerValue (totalNStations));
          wifimac.SetMultiUserSchedulerAttribute("AccessReqAc",EnumValue(AcIndex::AC_VO));
          wifimac.SetMultiUserSchedulerAttribute("RuAllocationType", EnumValue(ruAllocType));
          wifimac.SetMultiUserSchedulerAttribute("UlPsduSize", UintegerValue(ulPayloadSize));

          if (scheduler == "ns3::VlceMultiUserScheduler" ) {
            wifimac.SetMultiUserSchedulerAttribute("MaxTimeInList", TimeValue( MicroSeconds(maxTimeInList) ));
          }
          if (scheduler == "ns3::UoraMultiUserScheduler" ) {
            wifimac.SetMultiUserSchedulerAttribute("NumRandomAccessRus", UintegerValue(nRaRus));
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
        phy.EnablePcap("wifi-ax-ofdma-ap", apNetDevice); // enable pcap tracing
        phy.EnablePcap("wifi-ax-ofdma-sta", staNetDevices);
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

  /* Internet Stack on*/
  InternetStackHelper internetStack;
  internetStack.Install(wifiApNode);
  internetStack.Install(wifiStaNodes);

  Ipv4AddressHelper address;
  address.SetBase("192.168.1.0", "255.255.255.0");
  Ipv4InterfaceContainer staNodeInterfaces;
  Ipv4InterfaceContainer apNodeInterface;

  staNodeInterfaces = address.Assign (staNetDevices);
  apNodeInterface = address.Assign (apNetDevice);

  ArpCache::PopulateArpCache ();

  /*
   * jitter for random start time
   * */

  //Ptr<UniformRandomVariable> rv = CreateObject<UniformRandomVariable>();
  //rv->SetAttribute("Max", DoubleValue(interval));

  uint16_t port = {9};

  // AP server
  InetSocketAddress broadcastAddress = InetSocketAddress(Ipv4Address::GetBroadcast(), port);
  InetSocketAddress apLocalAddress = InetSocketAddress (apNodeInterface.Get (0).first->GetAddress (1, 0).GetAddress (), port);
  broadcastAddress.SetTos(0xc0);
  apLocalAddress.SetTos(0xc0);
  ApServerHelper apServer(port);
  apServer.SetAttribute("PacketSize", UintegerValue (dlPayloadSize));
  apServer.SetAttribute("RemoteAddress", AddressValue (broadcastAddress));
  apServer.SetAttribute("LocalAddress", AddressValue(apLocalAddress) );
  apServer.SetAttribute ("Interval", TimeValue (Seconds (interval)));
  apServer.SetAttribute("StrictWindow", BooleanValue(strictWindow));

  VeloceAppContainer apServerApp = apServer.Install (wifiApNode);

  apServerApp.Start(Seconds (0));
  apServerApp.Stop (Seconds (simulationTime + startLogTime));

  // Sta Server
  for (size_t i = 0; i < totalNStations; i++) {
    ApServerHelper staServer(port);
    InetSocketAddress staLocalAddress = InetSocketAddress (staNodeInterfaces.Get (i).first->GetAddress (1, 0).GetAddress () );
    staLocalAddress.SetTos(0xc0);
    staServer.SetAttribute("LocalAddress", AddressValue(staLocalAddress));
    staServer.SetAttribute("StaApFlag", BooleanValue(true));
    VeloceAppContainer staServerApp = staServer.Install(wifiStaNodes.Get(i));
    staServerApp.Start(Seconds(0));
    staServerApp.Stop(Seconds(simulationTime + startLogTime ));
  }

  if (scenario) {

    std::set<std::size_t> totalNStationsSet;
    std::set<std::size_t> initNStationsSet;
    std::set<std::size_t> nStationsToJoinSet;
    Ptr<UniformRandomVariable> rv = CreateObject<UniformRandomVariable>();
    rv->SetAttribute("Max", DoubleValue(totalNStations -1));

    while (initNStationsSet.size() < initNStations) {
      initNStationsSet.insert(rv->GetInteger());
    }
    while (nStationsToJoinSet.size() < nStationsToJoin) {
      size_t lrv = rv->GetInteger();
      auto p = std::find(initNStationsSet.begin(), initNStationsSet.end(), lrv);
        if (p != initNStationsSet.end())
          continue;
        else
          nStationsToJoinSet.insert(lrv);
    }
    for (size_t i = 0; i < totalNStations; i++) {
      auto  p = std::find(initNStationsSet.begin(), initNStationsSet.end(), i );
      auto q = std::find(nStationsToJoinSet.begin(), nStationsToJoinSet.end(), i);
      if ( p != initNStationsSet.end() || q != nStationsToJoinSet.end())
        continue;
      else
       totalNStationsSet.insert(i);
    }

    double staStartTime = 1;
    //Initial Session Stations
    for (auto i : initNStationsSet)
    {
      staStartTime += 0.00208;
      StaClientHelper staUdpClient (apLocalAddress);
      staUdpClient.SetAttribute ("MaxPackets", UintegerValue (4294967295u));
      staUdpClient.SetAttribute ("InitSession", BooleanValue (true));
      staUdpClient.SetAttribute ("Interval", TimeValue (Seconds (interval)));
      staUdpClient.SetAttribute ("StartSendInterval", TimeValue (Seconds(StartSendInterval)));
      staUdpClient.SetAttribute ("PacketSize", UintegerValue (ulPayloadSize));
      staUdpClient.SetAttribute("InitStaJoinTime", TimeValue(Seconds(initStaJoinTime)));
      staUdpClient.SetAttribute("InitPacketSentDelay", TimeValue(Seconds(staStartTime)));

      VeloceAppContainer staUdpclientApp = staUdpClient.Install (wifiStaNodes.Get(i));
      staUdpclientApp.Start (Seconds (0));
      staUdpclientApp.Stop (Seconds (simulationTime + startLogTime));
    }

    //poison clients
    for (auto i : nStationsToJoinSet )
    {
      staStartTime += 0.00208;
      StaClientHelper staUdpClient (apLocalAddress);
      staUdpClient.SetAttribute ("MaxPackets", UintegerValue (4294967295u));
      staUdpClient.SetAttribute ("ToJoinSession", BooleanValue (true));
      staUdpClient.SetAttribute ("Interval", TimeValue (Seconds (interval)));
      staUdpClient.SetAttribute ("EnableRandom", BooleanValue (true));
      staUdpClient.SetAttribute ("PacketSize", UintegerValue (ulPayloadSize));
      staUdpClient.SetAttribute("TimeToJoin", TimeValue(Seconds(timeToJoin - staStartTime)));
      staUdpClient.SetAttribute("OnOffFlag", BooleanValue(onOffFlag));

      std::ostringstream intervalDistr;
      double mean = (((simulationTime + startLogTime) - timeToJoin) - (startLogTime + timeToJoin) / 2);
      double bound = ((simulationTime + startLogTime) - timeToJoin );
      //double mean = poissonMean;
      intervalDistr << "ns3::ExponentialRandomVariable[Mean=" << mean  << "|Bound="<< bound <<"]";
      staUdpClient.SetAttribute ("IntervalRandomVariable", StringValue (intervalDistr.str()));
      staUdpClient.SetAttribute("InitPacketSentDelay", TimeValue(Seconds(staStartTime)));

      VeloceAppContainer staUdpclientApp = staUdpClient.Install (wifiStaNodes.Get(i));
      staUdpclientApp.Start (Seconds (0) );
      staUdpclientApp.Stop (Seconds (simulationTime + startLogTime));
    }

  // idle clients
    for (auto i : totalNStationsSet)
    {
      staStartTime += 0.00208;
      StaClientHelper staUdpClient (apLocalAddress);
      staUdpClient.SetAttribute ("MaxPackets", UintegerValue (4294967295u));
      staUdpClient.SetAttribute ("IdleStations", BooleanValue (true));
      staUdpClient.SetAttribute ("Interval", TimeValue (Seconds (interval)));
      staUdpClient.SetAttribute ("StartSendInterval", TimeValue (Seconds(StartSendInterval)));
      staUdpClient.SetAttribute ("PacketSize", UintegerValue (ulPayloadSize));

      staUdpClient.SetAttribute("InitPacketSentDelay", TimeValue(Seconds(staStartTime)));

      VeloceAppContainer staUdpclientApp = staUdpClient.Install (wifiStaNodes.Get(i));
      staUdpclientApp.Start (Seconds (0) );
      staUdpclientApp.Stop (Seconds (simulationTime + startLogTime));
    }
  }
  else {
    for (size_t i = 0; i < totalNStations; i++) 
    {
      StaClientHelper staUdpClient (apLocalAddress);
      staUdpClient.SetAttribute ("MaxPackets", UintegerValue (4294967295u));
      staUdpClient.SetAttribute ("InitSession", BooleanValue (false));
      staUdpClient.SetAttribute ("Interval", TimeValue (Seconds (interval)));
      staUdpClient.SetAttribute ("StartSendInterval", TimeValue (Seconds(StartSendInterval)));
      staUdpClient.SetAttribute ("PacketSize", UintegerValue (ulPayloadSize));
      VeloceAppContainer staUdpclientApp = staUdpClient.Install (wifiStaNodes.Get(i));
      staUdpclientApp.Start (Seconds (0) );
      staUdpclientApp.Stop (Seconds (simulationTime + startLogTime));
    }
  }

  Simulator::Schedule (Seconds (0), &Ipv4GlobalRoutingHelper::PopulateRoutingTables);

  for (uint32_t i = 0; i < staNetDevices.GetN (); i++)
    {
      Ptr<WifiNetDevice> dev = DynamicCast<WifiNetDevice> ( staNetDevices.Get(i) );
      Ptr<WifiMac> wifi_mac = dev->GetMac();
      if (enableAggregation) {
        wifi_mac->SetAttribute("VO_MaxAmpduSize", UintegerValue (nMpdus * ulPayloadSize ));
        wifi_mac->SetAttribute("VO_MaxAmsduSize", UintegerValue (nMsdus * ulPayloadSize ));
      }
      wifi_mac->GetQosTxop(AC_VO)->SetTxopLimit(MicroSeconds(txOpLimits));
      auto mac = Mac48Address::ConvertFrom (staNetDevices.Get (i)->GetAddress ());
      auto ip = staNodeInterfaces.Get (i).first->GetAddress (1, 0).GetAddress ();
      g_Ip2Mac[ip] = mac;

      staNetDevices.Get(i)->GetObject<WifiNetDevice>()->GetPhy()->GetPhyEntity(WIFI_MOD_CLASS_OFDM)->TraceConnectWithoutContext("SinrTrace", MakeBoundCallback (&SinrTrace, Mac48Address::ConvertFrom (staNetDevices.Get (i)->GetAddress ())));
      staNetDevices.Get(i)->GetObject<WifiNetDevice>()->GetPhy()->GetPhyEntity(WIFI_MOD_CLASS_HE)->TraceConnectWithoutContext("SinrTrace", MakeBoundCallback (&SinrTrace, Mac48Address::ConvertFrom (staNetDevices.Get (i)->GetAddress ())));
    }
  for (uint32_t i = 0; i < apNetDevice.GetN (); i++)
    {
      Ptr<WifiNetDevice> dev = DynamicCast<WifiNetDevice> ( apNetDevice.Get(i) );
      Ptr<WifiMac> wifi_mac = dev->GetMac();
      if (enableAggregation) {
        wifi_mac->SetAttribute("VO_MaxAmpduSize", UintegerValue (nMpdus * dlPayloadSize ));
        wifi_mac->SetAttribute("VO_MaxAmsduSize", UintegerValue (nMsdus * dlPayloadSize ));
      }
      wifi_mac->GetQosTxop(AC_VO)->SetTxopLimit(MicroSeconds(txOpLimits));
      auto mac = Mac48Address::ConvertFrom (apNetDevice.Get (i)->GetAddress ());
      auto ip = apNodeInterface.Get (i).first->GetAddress (1, 0).GetAddress ();
      g_Ip2Mac[ip] = mac;
      apMacAddress = mac;

      apNetDevice.Get(i)->GetObject<WifiNetDevice>()->GetPhy()->GetPhyEntity(WIFI_MOD_CLASS_OFDM)->TraceConnectWithoutContext("SinrTrace", MakeBoundCallback (&SinrTrace, Mac48Address::ConvertFrom (apNetDevice.Get (i)->GetAddress ())));
      apNetDevice.Get(i)->GetObject<WifiNetDevice>()->GetPhy()->GetPhyEntity(WIFI_MOD_CLASS_HE)->TraceConnectWithoutContext("SinrTrace", MakeBoundCallback (&SinrTrace, Mac48Address::ConvertFrom (apNetDevice.Get (i)->GetAddress ())));
    }


   for (uint32_t i = 0; i < apServerApp.GetN (); i++)
    {
      DynamicCast<ApServer> (apServerApp.Get (i))->TraceConnectWithoutContext ("Rx", MakeBoundCallback (&RxTrace,startLogTime ));
    }
/*    for (uint32_t i = 0; i < staServerApp.GetN (); i++)
    {
      DynamicCast<ApServer> (staServerApp.Get (i))->TraceConnectWithoutContext ("RxWithAddresses", MakeBoundCallback (&RxTrace ));
    }
*/

  Config::ConnectWithoutContext("/NodeList/*/ApplicationList/*/$ns3::ApServer/RxWithAddresses", MakeBoundCallback(&RxTraceWithAddress, startLogTime));

  Config::ConnectWithoutContext("/NodeList/*/ApplicationList/*/$ns3::ApServer/RxWithAddressesWakeUp", MakeBoundCallback(&RxTraceWakeUp, startLogTime));


  ProgressBar pg (Seconds(simulationTime + startLogTime ));
  Simulator::Stop (Seconds (simulationTime + startLogTime ));
  Simulator::Run ();

  // Statistics
  uint64_t rxBytes = 0;

  for (uint32_t i = 0; i < apServerApp.GetN (); i++)
    {
      rxBytes += DynamicCast<ApServer> (apServerApp.Get (i))->GetTotalRx ();
    }
  for (uint32_t i = 0; i < wifiStaNodes.GetN(); i++)
    {
      rxBytes +=   DynamicCast<ApServer> (wifiStaNodes.Get(i)-> GetApplication(0) )->GetTotalRx ();

      //rxBytes += DynamicCast<ApServer> (staServerApp.Get (i))->GetTotalRx ();
    }
  Simulator::Destroy ();


  double throughput = (rxBytes * 8) / (simulationTime * 1000000.0); //Mbit/s

  std::ofstream totalStatsOutStream;
  totalStatsOutStream.open ("throughput.out", std::ios::out);
  totalStatsOutStream << "MCS\tBandwidth_MHz\tGuard_interval_ns\tThroughput_Mbps" << std::endl;
  totalStatsOutStream << mcs << "\t" << channelWidth << "\t" << guardInterval << "\t" << throughput << std::endl;
  totalStatsOutStream.close ();

  std::ofstream perStaOutStream;
  perStaOutStream.open ("per_sta_stats.out", std::ios::out);
  perStaOutStream << "MAC-addr\tSINR_dB\tRX_bytes\tAvg_delay_ms\tPacket_loss_ratio" << std::endl;
  for (auto &staStats : g_statsMap)
    {
      staStats.second.sinr /= staStats.second.totalBeacons;
      double sumDelay = 0.;
      double latePkts = staStats.second.pktDelaysLate.size() ;
      double totalPkts = staStats.second.pktDelaysLate.size() + staStats.second.pktDelays.size() ;
      double pktLossRatio = latePkts / totalPkts;
      for (auto &delay : staStats.second.pktDelays)
        {
          sumDelay += delay * 1000.; //in ms
        }
      perStaOutStream << staStats.first << "\t" << staStats.second.sinr << "\t" << staStats.second.rxBytes
        << "\t" << sumDelay / staStats.second.pktDelays.size () << "\t" << pktLossRatio << std::endl;
    }
  perStaOutStream.close ();


  std::ofstream out("all_packets_e2e.out", std::ios::out);

  out << "Packet_Tag\tSTA_MAC\tAP_Gen_ms\tSTA_Rx_ms\tE2E_Delay_ms\n";

  // Composite key: (tag + MAC string)
  using Key = std::pair<uint32_t, std::string>;

  // Custom hash for unordered_map
  struct KeyHash {
    std::size_t operator()(const Key& k) const {
      return std::hash<uint32_t>()(k.first) ^
        (std::hash<std::string>()(k.second) << 1);
    }
  };

  std::unordered_map<Key, double, KeyHash> apGenMap;

  for (auto &entry : g_statsMap)
  {
    if (entry.first == apMacAddress)
    {
      for (size_t i = 0; i < entry.second.pktTag.size(); i++)
      {
        uint32_t tag = entry.second.pktTag[i];

        std::ostringstream src_mac;
        src_mac << entry.second.src[i];  // station that sent it

        double genMs = entry.second.genTime[i] * 1000;

        apGenMap[{tag, src_mac.str()}] = genMs;
      }
      break;
    }
  }

  for (auto &entry : g_statsMap)
  {
    if (entry.first == apMacAddress)
      continue;

    std::ostringstream sta_mac;
    sta_mac << entry.first;

    for (size_t i = 0; i < entry.second.pktTag.size(); i++)
    {
      uint32_t tag = entry.second.pktTag[i];
      double rxMs = entry.second.rxTime[i] * 1000;

      Key key = {tag, sta_mac.str()};

      if (apGenMap.find(key) != apGenMap.end())
      {
        double apGenMs = apGenMap[key];
        double e2e = rxMs - apGenMs;

        out << tag << "\t"
          << sta_mac.str() << "\t"
          << apGenMs << "\t"
          << rxMs << "\t"
          << e2e << "\n";
      }
    }
  }

  out.close();

  /*
  std::ofstream pktDistOutStream;

  for (auto &staStats : g_statsMap) {
    std::ostringstream mac_str;
    mac_str << staStats.first;
    pktDistOutStream.open (mac_str.str(), std::ios::out);
    pktDistOutStream << "Packet_Tag\tReceived_from\tGeneration_time\tReception_time\tDelay_ms" << std::endl;
    for (size_t i = 0;  i < staStats.second.pktDelays.size(); i++) {
      pktDistOutStream << staStats.second.pktTag[i] <<"\t"<< staStats.second.src[i] <<"\t"<<staStats.second.genTime[i] * 1000 <<"\t"<<staStats.second.rxTime[i]* 1000<< "\t"<< staStats.second.pktDelays[i] * 1000 << std::endl;
    }
    pktDistOutStream.close();
  }
  * No need to log individual delayed packets, we calculated it earlier*
  for (auto &staStats : g_statsMap) {
    std::ostringstream mac_str;
    mac_str << staStats.first;
    pktDistOutStream.open ("delayed_packet_" + mac_str.str(), std::ios::out);
    pktDistOutStream << "Packet_Tag\tReceived_from\tGeneration_time\tReception_time\tDelay_ms" << std::endl;
    for (size_t i = 0;  i < staStats.second.pktDelaysLate.size(); i++) {
      pktDistOutStream << staStats.second.pktTagLate[i] <<"\t"<< staStats.second.srcLate[i] <<"\t"<<staStats.second.genTimeLate[i] * 1000 <<"\t"<<staStats.second.rxTimeLate[i]* 1000<< "\t"<< staStats.second.pktDelaysLate[i] * 1000 << std::endl;
    }
    pktDistOutStream.close();
  } */
  
  std::ofstream pktDistOutStream;
  for (auto &staStats : g_statsMapAp) {
    //std::ostringstream mac_str;
    //mac_str << staStats.first ;
    pktDistOutStream.open ("wakeup_packet_stats" ,std::ios::out);
    pktDistOutStream << "Packet_Tag\tReceived_from\tGeneration_time\tReception_time\tDelay_ms" << std::endl;
    for (size_t i = 0;  i < staStats.second.pktDelaysWakeUp.size(); i++) {
      pktDistOutStream << staStats.second.pktTagWakeUp[i] <<"\t"<< staStats.second.srcWakeUp[i] <<"\t"<<staStats.second.genTimeWakeUp[i] * 1000 <<"\t"<<staStats.second.rxTimeWakeUp[i]* 1000<< "\t"<< staStats.second.pktDelaysWakeUp[i] * 1000 << std::endl;
    }
    pktDistOutStream.close();
  }


  return 0;
}
