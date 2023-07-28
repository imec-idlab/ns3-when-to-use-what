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
 * Author: Andrey Belogaev <andrei.belogaev@uantwerpen.be>
           Douglas Agbeve <douglas.agbeve@uantwerpen.be>
 */

#include <cerrno>
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

using namespace ns3;

struct stats_t
{
  double sinr;
  uint64_t totalBeacons;
  uint64_t rxBytes;
  std::vector<double> pktDelays,genTime, rxTime;
  std::vector<uint64_t> pktTag;
  std::vector<Mac48Address> src;
};

std::map<Mac48Address, stats_t> g_statsMap; //!< map for statistics for each station
std::map<Ipv4Address, Mac48Address> g_Ip2Mac; //!< map for mapping IPv4 to MAC address

void SinrTrace (Mac48Address addr, double sinr)
{
  g_statsMap[addr].sinr += sinr;
  g_statsMap[addr].totalBeacons++;
}


void RxTrace ( Ptr<const Packet> p, const Address &src, const Address &dst)
{
  Ptr<Packet> pkt = p->Copy ();
  SeqTsHeader seqTs;
  PacketTag tag;
  pkt->RemovePacketTag(tag);
  pkt->RemoveHeader(seqTs);

  g_statsMap[g_Ip2Mac.at (InetSocketAddress::ConvertFrom (dst).GetIpv4 ())].rxBytes += p->GetSize ();
  g_statsMap[g_Ip2Mac.at (InetSocketAddress::ConvertFrom (dst).GetIpv4 ())].pktDelays.push_back ((Simulator::Now() - seqTs.GetTs ()).GetSeconds ());
  g_statsMap[g_Ip2Mac.at (InetSocketAddress::ConvertFrom (dst).GetIpv4 ())].pktTag.push_back (tag.GetValue());
  g_statsMap[g_Ip2Mac.at (InetSocketAddress::ConvertFrom (dst).GetIpv4 ())].genTime.push_back(seqTs.GetTs().GetSeconds() );
  g_statsMap[g_Ip2Mac.at (InetSocketAddress::ConvertFrom (dst).GetIpv4 ())].rxTime.push_back(Simulator::Now().GetSeconds());
  g_statsMap[g_Ip2Mac.at (InetSocketAddress::ConvertFrom (dst).GetIpv4 ())].src.push_back( g_Ip2Mac.at (InetSocketAddress::ConvertFrom (src).GetIpv4 ()));
}

int  main(int argc, char *argv[])
{
  double simulationTime {10};//seconds
  std::string logDir {"output"};
  double minDistance {1.0}; //meters
  double maxDistance {4.0}; //meters
  std::size_t nStations {1};
  double apHeight {3}; //meters
  double staHeight {1}; //meters

  std::string frequency {"5"}; //whether 2.4, 5 or 6 GHz
  uint32_t channelWidth {40}; //for 2.4 <= 40 MHz, for 5 <= 160 MHz
  uint32_t guardInterval {800}; //in ns
  int mcs {11}; // 0..11
  std::string phyModel {"Yans"};
  bool enableShadowing = false;
  double txPowerStart = {16.0206};
  double txPowerEnd = {16.0206};

  std::string dlAckSeqType {"NO-OFDMA"};
  bool enableUlOfdma {false};
  bool enableBsrp {false};
  Time accessReqInterval {0.000005};
  bool useRts {true};
  bool useExtendedBlockAck {false};
  bool useMuEdca {true};

  uint32_t ulPayloadSize = 93; // must fit in the max TX duration when transmitting at MCS 0 over an RU of 26 tones
  uint32_t dlPayloadSize = 500;
  std::string trafficType {"CBR"};
  double interval {0.005}; //seconds
  std::string accessCategory {"AC_VO"};

  CommandLine cmd (__FILE__);
  //Experiment set-up
  cmd.AddValue ("simulationTime", "Simulation time in seconds", simulationTime);
  cmd.AddValue ("logDir", "Directory for the output stats files", logDir);
  cmd.AddValue ("minDistance", "Minimum distance in meters between the station and the access point", minDistance);
  cmd.AddValue ("maxDistance", "Maximum distance in meters between the station and the access point", maxDistance);
  cmd.AddValue ("nStations", "Number of non-AP HE stations", nStations);
  cmd.AddValue ("apHeight", "Height of AP [m]", apHeight);
  cmd.AddValue ("staHeight", "Height of STA [m]", staHeight);

  //PHY params
  cmd.AddValue ("frequency", "Whether working in the 2.4, 5 or 6 GHz band (other values gets rejected)", frequency);
  cmd.AddValue ("channelWidth", "Channel width used for transmissions (20, 40, 80, 80+80, 160 MHz)", channelWidth);
  cmd.AddValue ("guardInterval", "The value of the guard interval (800, 1600, 3200 ns)", guardInterval);
  cmd.AddValue ("mcs", "if set, limit testing to a specific MCS (0-11)", mcs);
  cmd.AddValue ("phyModel", "PHY model to use when OFDMA is disabled (Yans or Spectrum). If OFDMA is enabled then Spectrum is automatically selected", phyModel);
  cmd.AddValue ("enableShadowing", "Enable/disable gaussian shadowing", enableShadowing);
  cmd.AddValue ("txPowerStart", "Minimum available transmissions level (dBm)", txPowerStart);
  cmd.AddValue ("txPowerEnd", "Maximum available transmissions level (dBm)", txPowerEnd);

  //MAC params
  cmd.AddValue ("useRts", "Enable/disable RTS/CTS", useRts);
  cmd.AddValue ("useExtendedBlockAck", "Enable/disable use of extended BACK", useExtendedBlockAck);
  cmd.AddValue ("dlAckType", "Ack sequence type for DL OFDMA (NO-OFDMA, ACK-SU-FORMAT, MU-BAR, AGGR-MU-BAR)", dlAckSeqType);
  cmd.AddValue ("enableUlOfdma", "Enable UL OFDMA (useful if DL OFDMA is enabled and TCP is used)", enableUlOfdma);
  cmd.AddValue ("enableBsrp", "Enable BSRP (useful if DL and UL OFDMA are enabled and TCP is used)", enableBsrp);
  cmd.AddValue ("muSchedAccessReqInterval", "Duration of the interval between two requests for channel access made by the MU scheduler", accessReqInterval);
  cmd.AddValue ("useMuEdca", "Enable/disable Specific EDCA parameters set", useMuEdca);

  //Traffic params
  cmd.AddValue ("ulPayloadSize", "the application payload size in bytes for ul traffic", ulPayloadSize);
  cmd.AddValue ("dlPayloadSize", "the application payload size in bytes for dl traffic", dlPayloadSize);
  cmd.AddValue ("interval", "Average inter-packet interval [s]", interval);
  cmd.AddValue ("accessCategory", "Access category for traffic: AC_BE, AC_BK, AC_VO, AC_VI", accessCategory);

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
      Config::SetDefault ("ns3::WifiRemoteStationManager::RtsCtsThreshold", StringValue ("2200"));
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
  if (dlAckSeqType != "NO-OFDMA")
    {
      // SpectrumWifiPhy is required for OFDMA
      phyModel = "Spectrum";
    }

  // create nStations of STA and 1 AP
  NodeContainer wifiStaNodes;
  wifiStaNodes.Create(nStations);
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

      //STA timer (validity of set)
      Config::SetDefault ("ns3::HeConfiguration::BkMuEdcaTimer", TimeValue (MicroSeconds (8192)));
      Config::SetDefault ("ns3::HeConfiguration::BeMuEdcaTimer", TimeValue (MicroSeconds (8192)));
      Config::SetDefault ("ns3::HeConfiguration::ViMuEdcaTimer", TimeValue (MicroSeconds (8192)));
      Config::SetDefault ("ns3::HeConfiguration::VoMuEdcaTimer", TimeValue (MicroSeconds (8192)));
  }

  //sifs and slot time
  Config::SetDefault("ns3::WifiPhy::Sifs", TimeValue(MicroSeconds(16)));
  Config::SetDefault("ns3::WifiPhy::Slot", TimeValue(MicroSeconds(9)));

  //Retry limit
  Config::SetDefault ("ns3::WifiRemoteStationManager::MaxSsrc", UintegerValue (32));
  Config::SetDefault ("ns3::WifiRemoteStationManager::MaxSlrc", UintegerValue (32));

  Config::SetDefault("ns3::QosFrameExchangeManager::SetQueueSize", BooleanValue(true));

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

      wifimac.SetType ("ns3::StaWifiMac",
                  "Ssid", SsidValue (ssid));
      phy.Set ("ChannelSettings", StringValue (channelStr));
      phy.Set("TxPowerStart", DoubleValue(txPowerStart ));
      phy.Set("TxPowerEnd", DoubleValue(txPowerEnd ));
      staNetDevices = wifi.Install (phy, wifimac, wifiStaNodes);

      if (dlAckSeqType != "NO-OFDMA")
        {
          wifimac.SetMultiUserScheduler ("ns3::RrMultiUserScheduler",
                                      "EnableUlOfdma", BooleanValue (enableUlOfdma),
                                      "EnableBsrp", BooleanValue (enableBsrp),
                                      "AccessReqInterval", TimeValue (accessReqInterval),
                                      "DelayAccessReqUponAccess", BooleanValue (true),
                                      "UseCentral26TonesRus", BooleanValue (false),
                                      "NStations", UintegerValue (74));
        }
      wifimac.SetType ("ns3::ApWifiMac",
                  "EnableBeaconJitter", BooleanValue (false),
                  "Ssid", SsidValue (ssid));
      apNetDevice = wifi.Install (phy, wifimac, wifiApNode);

      phy.EnablePcap("wifi-ax-ofdma-ap", apNetDevice); // enable pcap tracing
      phy.EnablePcap("wifi-ax-ofdma-sta", staNetDevices);
    }
  else
    {
      Ptr<YansWifiChannel> channel = CreateObject<YansWifiChannel> ();
      channel->SetPropagationLossModel (propModel);
      channel->SetPropagationDelayModel (delayModel);

      YansWifiPhyHelper YansPhy;
      YansPhy.SetPcapDataLinkType (WifiPhyHelper::DLT_IEEE802_11_RADIO);
      YansPhy.SetChannel (channel); //channel.Create ()

      wifimac.SetType ("ns3::StaWifiMac",
                  "Ssid", SsidValue (ssid));
      YansPhy.Set ("ChannelSettings", StringValue (channelStr));
      YansPhy.Set("TxPowerStart", DoubleValue(txPowerStart ));
      YansPhy.Set("TxPowerEnd", DoubleValue(txPowerEnd ));
      staNetDevices = wifi.Install (YansPhy, wifimac, wifiStaNodes);

      wifimac.SetType ("ns3::ApWifiMac",
                  "EnableBeaconJitter", BooleanValue (false),
                  "Ssid", SsidValue (ssid));
      apNetDevice = wifi.Install (YansPhy, wifimac, wifiApNode);
      YansPhy.EnablePcap("wifi-ax-edca-ap", apNetDevice); // enable pcap tracing
      YansPhy.EnablePcap("wifi-ax-edca-sta", staNetDevices);
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

  /*
   * jitter for random start time
   * */

  Ptr<UniformRandomVariable> uv = CreateObject<UniformRandomVariable>();
  uv->SetAttribute("Max", DoubleValue(0.005));

  uint16_t port = {9};

  // AP server
  InetSocketAddress broadcastAddress = InetSocketAddress(Ipv4Address::GetBroadcast(), port);
  InetSocketAddress apLocalAddress = InetSocketAddress (apNodeInterface.Get (0).first->GetAddress (1, 0).GetAddress (), port);
  broadcastAddress.SetTos(0xc0);
  apLocalAddress.SetTos(0xc0);
  ApServerHelper apServer(port);
  apServer.SetAttribute("PacketSize", UintegerValue (dlPayloadSize));
  apServer.SetAttribute("RemoteAddress", AddressValue (broadcastAddress));
  apServer.SetAttribute("NStations", UintegerValue(nStations));
  apServer.SetAttribute("LocalAddress", AddressValue(apLocalAddress) );
  apServer.SetAttribute ("Interval", TimeValue (Seconds (interval)));

  ApplicationContainer apServerApp = apServer.Install (wifiApNode);

  apServerApp.Start(Seconds (0));
  apServerApp.Stop (Seconds (simulationTime + 1));

  // Sta Server
  for (size_t i = 0; i < nStations; i++) {
    ApServerHelper staServer(port);
    InetSocketAddress staLocalAddress = InetSocketAddress (staNodeInterfaces.Get (i).first->GetAddress (1, 0).GetAddress () );
    staLocalAddress.SetTos(0xc0);
    staServer.SetAttribute("LocalAddress", AddressValue(staLocalAddress));
    staServer.SetAttribute("StaApFlag", BooleanValue(true));
    ApplicationContainer staServerApp = staServer.Install(wifiStaNodes.Get(i));
    staServerApp.Start(Seconds(0));
    staServerApp.Stop(Seconds(simulationTime + 1 ));
  }

    //Udp Sta
  StaClientHelper staUdpClient (apLocalAddress);
  staUdpClient.SetAttribute ("MaxPackets", UintegerValue (4294967295u));
  if (trafficType == "CBR") /*CBR traffic*/
  {
    staUdpClient.SetAttribute ("EnableRandom", BooleanValue (false));
    staUdpClient.SetAttribute ("Interval", TimeValue (Seconds (interval)));
  }
  else //Poisson traffic
  {
    staUdpClient.SetAttribute ("EnableRandom", BooleanValue (true));
    std::ostringstream intervalDistr;
    intervalDistr << "ns3::ExponentialRandomVariable[Mean=" << interval << "|Bound=0]";
    staUdpClient.SetAttribute ("IntervalRandomVariable", StringValue (intervalDistr.str()));
  }
  staUdpClient.SetAttribute ("PacketSize", UintegerValue (ulPayloadSize));
  ApplicationContainer staUdpclientApp = staUdpClient.Install (wifiStaNodes);
  staUdpclientApp.StartWithJitter (Seconds (0.0031), uv);
  staUdpclientApp.Stop (Seconds (simulationTime + 1));

  Simulator::Schedule (Seconds (0), &Ipv4GlobalRoutingHelper::PopulateRoutingTables);

  for (uint32_t i = 0; i < staNetDevices.GetN (); i++)
    {
      auto mac = Mac48Address::ConvertFrom (staNetDevices.Get (i)->GetAddress ());
      auto ip = staNodeInterfaces.Get (i).first->GetAddress (1, 0).GetAddress ();
      g_Ip2Mac[ip] = mac;

      staNetDevices.Get(i)->GetObject<WifiNetDevice>()->GetPhy()->GetPhyEntity(WIFI_MOD_CLASS_OFDM)->TraceConnectWithoutContext("SinrTrace", MakeBoundCallback (&SinrTrace, Mac48Address::ConvertFrom (staNetDevices.Get (i)->GetAddress ())));
      staNetDevices.Get(i)->GetObject<WifiNetDevice>()->GetPhy()->GetPhyEntity(WIFI_MOD_CLASS_HE)->TraceConnectWithoutContext("SinrTrace", MakeBoundCallback (&SinrTrace, Mac48Address::ConvertFrom (staNetDevices.Get (i)->GetAddress ())));
    }
  for (uint32_t i = 0; i < apNetDevice.GetN (); i++)
    {
      auto mac = Mac48Address::ConvertFrom (apNetDevice.Get (i)->GetAddress ());
      auto ip = apNodeInterface.Get (i).first->GetAddress (1, 0).GetAddress ();
      g_Ip2Mac[ip] = mac;

      apNetDevice.Get(i)->GetObject<WifiNetDevice>()->GetPhy()->GetPhyEntity(WIFI_MOD_CLASS_OFDM)->TraceConnectWithoutContext("SinrTrace", MakeBoundCallback (&SinrTrace, Mac48Address::ConvertFrom (apNetDevice.Get (i)->GetAddress ())));
      apNetDevice.Get(i)->GetObject<WifiNetDevice>()->GetPhy()->GetPhyEntity(WIFI_MOD_CLASS_HE)->TraceConnectWithoutContext("SinrTrace", MakeBoundCallback (&SinrTrace, Mac48Address::ConvertFrom (apNetDevice.Get (i)->GetAddress ())));
    }

/*
   for (uint32_t i = 0; i < apServerApp.GetN (); i++)
    {
     // DynamicCast<ApServer> (apServerApp.Get (i))->TraceConnectWithoutContext ("RxWithAddresses", MakeBoundCallback (&RxTrace ));
    }
    for (uint32_t i = 0; i < staServerApp.GetN (); i++)
    {
      DynamicCast<ApServer> (staServerApp.Get (i))->TraceConnectWithoutContext ("RxWithAddresses", MakeBoundCallback (&RxTrace ));
    }
*/

    Config::ConnectWithoutContext("/NodeList/*/ApplicationList/*/$ns3::ApServer/RxWithAddresses", MakeCallback(&RxTrace));

  ProgressBar pg (Seconds(simulationTime + 1 ));
  Simulator::Stop (Seconds (simulationTime + 1 ));
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


  double throughput = (rxBytes * 8) / (simulationTime * 1000000.0); //Mbit/s

  std::ofstream totalStatsOutStream;
  totalStatsOutStream.open ("throughput.out", std::ios::out);
  totalStatsOutStream << "MCS\tBandwidth_MHz\tGuard_interval_ns\tThroughput_Mbps" << std::endl;
  totalStatsOutStream << mcs << "\t" << channelWidth << "\t" << guardInterval << "\t" << throughput << std::endl;
  totalStatsOutStream.close ();

  std::ofstream perStaOutStream;
  perStaOutStream.open ("per_sta_stats.out", std::ios::out);
  perStaOutStream << "MAC-addr\tSINR_dB\tRX_bytes\tAvg_delay_ms" << std::endl;
  for (auto &staStats : g_statsMap)
    {
      staStats.second.sinr /= staStats.second.totalBeacons;
      double sumDelay = 0.;
      for (auto &delay : staStats.second.pktDelays)
        {
          sumDelay += delay * 1000.; //in ms
        }
      perStaOutStream << staStats.first << "\t" << staStats.second.sinr << "\t" << staStats.second.rxBytes
        << "\t" << sumDelay / staStats.second.pktDelays.size () << std::endl;
    }
  perStaOutStream.close ();

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


  Simulator::Destroy ();

  return 0;
}
