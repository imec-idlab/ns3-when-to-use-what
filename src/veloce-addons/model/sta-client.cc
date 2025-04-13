/* -*- Mode:C++; c-file-style:"gnu"; indent-tabs-mode:nil; -*- */
/*
 * Copyright (c) 2023
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
 * Author: Douglas AGbeve <douglas.agbeve@uantwerpen.be>
 */
#include "ns3/log.h"
#include "ns3/ipv4-address.h"
#include "ns3/nstime.h"
#include "ns3/inet-socket-address.h"
#include "ns3/inet6-socket-address.h"
#include "ns3/socket.h"
#include "ns3/simulator.h"
#include "ns3/socket-factory.h"
#include "ns3/packet.h"
#include "ns3/uinteger.h"
#include "sta-client.h"
#include "ns3/seq-ts-header.h"

#include "ns3/application-container.h"
#include "ns3/names.h"

#include "ns3/pointer.h"
#include "ns3/string.h"
#include "ns3/boolean.h"
#include "ns3/double.h"
#include "ns3/packet-tag.h"

namespace ns3 {

NS_LOG_COMPONENT_DEFINE ("StaClient");

NS_OBJECT_ENSURE_REGISTERED (StaClient);

TypeId
StaClient::GetTypeId (void)
{
  static TypeId tid = TypeId ("ns3::StaClient")
    .SetParent<Application> ()
    .SetGroupName("Applications")
    .AddConstructor<StaClient> ()
    .AddAttribute ("MaxPackets",
                   "The maximum number of packets the application will send",
                   UintegerValue (100),
                   MakeUintegerAccessor (&StaClient::m_count),
                   MakeUintegerChecker<uint32_t> ())
    .AddAttribute ("Interval",
                   "The time to wait between packets", TimeValue (Seconds (1.0)),
                   MakeTimeAccessor (&StaClient::m_interval),
                   MakeTimeChecker ())
    .AddAttribute ("StartSendInterval",
                   "Interval within which packets are randomly sent", TimeValue (Seconds (1.0)),
                   MakeTimeAccessor (&StaClient::m_startSendIntval),
                   MakeTimeChecker ())
    .AddAttribute ("RemoteAddress",
                   "The destination Address of the outbound packets",
                   AddressValue (),
                   MakeAddressAccessor (&StaClient::m_peerAddress),
                   MakeAddressChecker ())
    .AddAttribute ("RemotePort", "The destination port of the outbound packets",
                   UintegerValue (100),
                   MakeUintegerAccessor (&StaClient::m_peerPort),
                   MakeUintegerChecker<uint16_t> ())
    .AddAttribute ("PacketSize",
                   "Size of packets generated. The minimum packet size is 12 \
                   bytes which is the size of the header carrying the sequence \
                   number and the time stamp.",
                   UintegerValue (1024),
                   MakeUintegerAccessor (&StaClient::m_size),
                   MakeUintegerChecker<uint32_t> (12,65507))
    .AddAttribute ("EnableRandom",
                   "For random traffic instead of CBR",
                   BooleanValue (false),
                   MakeBooleanAccessor (&StaClient::m_enableRandom),
                   MakeBooleanChecker ())
    .AddAttribute ("InitSession",
                   "Flag for initial STA sessions",
                   BooleanValue (false),
                   MakeBooleanAccessor (&StaClient::m_initFlag),
                   MakeBooleanChecker ())
    .AddAttribute ("ToJoinSession",
                   "Flag to join the session",
                   BooleanValue (false),
                   MakeBooleanAccessor (&StaClient::m_toJoinFlag),
                   MakeBooleanChecker ())
    .AddAttribute ("TimeToJoin",
                   "Time to for random stations to join", TimeValue (Seconds (1.0)),
                   MakeTimeAccessor (&StaClient::m_timeToJoin),
                   MakeTimeChecker ())
    .AddAttribute ("InitStaJoinTime",
                   "Time to for initial stations to join after establishing connection", TimeValue (Seconds (1.0)),
                   MakeTimeAccessor (&StaClient::m_initStaJoinTime),
                   MakeTimeChecker ())
    .AddAttribute ("InitPacketSentDelay",
                   "Time to start sending initial packets", TimeValue (Seconds (0.0)),
                   MakeTimeAccessor (&StaClient::m_initPacketSentDelay),
                   MakeTimeChecker ())
    .AddAttribute ("IdleStations",
                   "Flag to indicate idle stations",
                   BooleanValue (false),
                   MakeBooleanAccessor (&StaClient::m_idleFlag),
                   MakeBooleanChecker ())
    .AddAttribute ("OnOffFlag",
                   "Whether to enable on and off behavior or ONLY on",
                   BooleanValue (false),
                   MakeBooleanAccessor (&StaClient::m_onOffFlag),
                   MakeBooleanChecker ())
    .AddAttribute ("IntervalRandomVariable",
                   "For random interval distribution instead of constant",
                   StringValue ("ns3::ConstantRandomVariable[Constant=1.0]"),
                   MakePointerAccessor (&StaClient::m_intervalRandomVariable),
                   MakePointerChecker<RandomVariableStream> ())
  ;
  return tid;
}

StaClient::StaClient ()
{
  NS_LOG_FUNCTION (this);
  m_sent = 0;
  m_totalTx = 0;
  m_socket = 0;
  m_sendEvent = EventId ();
  m_tagValue = 0;
}

StaClient::~StaClient ()
{
  NS_LOG_FUNCTION (this);
}

void
StaClient::SetRemote (Address ip, uint16_t port)
{
  NS_LOG_FUNCTION (this << ip << port);
  m_peerAddress = ip;
  m_peerPort = port;
}

void
StaClient::SetRemote (Address addr)
{
  NS_LOG_FUNCTION (this << addr);
  m_peerAddress = addr;
}

void
StaClient::DoDispose (void)
{
  NS_LOG_FUNCTION (this);
  Application::DoDispose ();
}

void
StaClient::StartApplication (void)
{
  NS_LOG_FUNCTION (this);

  if (m_socket == nullptr)
    {
      TypeId tid = TypeId::LookupByName ("ns3::UdpSocketFactory");
      m_socket = Socket::CreateSocket (GetNode (), tid);
      if (Ipv4Address::IsMatchingType(m_peerAddress) == true)
        {
          if (m_socket->Bind () == -1)
            {
              NS_FATAL_ERROR ("Failed to bind socket");
            }
          m_socket->Connect (InetSocketAddress (Ipv4Address::ConvertFrom(m_peerAddress), m_peerPort));
        }
      else if (Ipv6Address::IsMatchingType(m_peerAddress) == true)
        {
          if (m_socket->Bind6 () == -1)
            {
              NS_FATAL_ERROR ("Failed to bind socket");
            }
          m_socket->Connect (Inet6SocketAddress (Ipv6Address::ConvertFrom(m_peerAddress), m_peerPort));
        }
      else if (InetSocketAddress::IsMatchingType (m_peerAddress) == true)
        {
          if (m_socket->Bind () == -1)
            {
              NS_FATAL_ERROR ("Failed to bind socket");
            }
          m_socket->Connect (m_peerAddress);
        }
      else if (Inet6SocketAddress::IsMatchingType (m_peerAddress) == true)
        {
          if (m_socket->Bind6 () == -1)
            {
              NS_FATAL_ERROR ("Failed to bind socket");
            }
          m_socket->Connect (m_peerAddress);
        }
      else
        {
          NS_ASSERT_MSG (false, "Incompatible address type: " << m_peerAddress);
        }
    }
#ifdef NS3_LOG_ENABLE
  std::stringstream peerAddressStringStream;
  if (Ipv4Address::IsMatchingType (m_peerAddress))
    {
      peerAddressStringStream << Ipv4Address::ConvertFrom (m_peerAddress);
    }
  else if (Ipv6Address::IsMatchingType (m_peerAddress))
    {
      peerAddressStringStream << Ipv6Address::ConvertFrom (m_peerAddress);
    }
  else if (InetSocketAddress::IsMatchingType (m_peerAddress))
    {
      peerAddressStringStream << InetSocketAddress::ConvertFrom (m_peerAddress).GetIpv4 ();
    }
  else if (Inet6SocketAddress::IsMatchingType (m_peerAddress))
    {
      peerAddressStringStream << Inet6SocketAddress::ConvertFrom (m_peerAddress).GetIpv6 ();
    }
  m_peerAddressString = peerAddressStringStream.str();
#endif // NS3_LOG_ENABLE

  m_socket->SetRecvCallback (MakeNullCallback<void, Ptr<Socket> > ());
  m_socket->SetAllowBroadcast (true);

  if (m_initPacketSentDelay.GetSeconds())
  {
    m_sendEvent = Simulator::Schedule(Seconds( m_initPacketSentDelay.GetSeconds() ), &StaClient::Send, this, "FirstPacket");
  } 
  else
  {
    Ptr<UniformRandomVariable> rand = CreateObject <UniformRandomVariable> ();
    double delay = rand->GetValue (0, m_startSendIntval.GetSeconds ());
    //delay += (m_initStaJoinTime.GetSeconds() - Simulator::Now().GetSeconds());
    std::cout << "Initial TX after delay = " << delay << "s" << std::endl;
    m_sendEvent = Simulator::Schedule (Seconds (delay), &StaClient::Send, this, "FirstPacket");

  }
}

void
StaClient::StopApplication (void)
{
  NS_LOG_FUNCTION (this);
  Simulator::Cancel (m_sendEvent);
}

void StaClient::DelayedSession (std::string onOrOff, std::string joinPolling)
{
  double delay {0};
  //double mean {};
  //double bound = m_intervalRandomVariable->GetBound();

  if (onOrOff == "on"){
    delay = m_intervalRandomVariable->GetValue();
    std::cout << "Poison On After = " << delay << "s" <<std::endl;
    DelayedToRightWindow(delay, joinPolling);
  }
  else if (onOrOff == "off") {
    //check if there is enough time to come on
    if (Simulator::Now().GetSeconds() < m_intervalRandomVariable->GetBound()){
      //mean = (bound - Simulator::Now().GetSeconds()) / 2;
      delay = m_intervalRandomVariable->GetValue();
      std::cout << "Poison Off For = " << delay << "s" << std::endl;
      DelayedToRightWindow(delay, joinPolling);
    }
    else{
      //keep it on till the end
       m_sendEvent = Simulator::Schedule (m_interval, &StaClient::Send, this, "");
       m_onOffFlag = false;
    }
  }

  if (m_onOffFlag){
    //mean = (bound - (Simulator::Now().GetSeconds() + delay )) / 2;
    double of_delay = m_intervalRandomVariable->GetValue( );
    m_offTime = Simulator::Now() + Seconds(delay) + Seconds(of_delay);
  }
}

void StaClient::DelayedToRightWindow(double delay, std::string joinPolling){

  //get which 5ms window
  double  actual_delay = Simulator::Now().GetSeconds() + Seconds(delay).GetSeconds();
  double mt5 = std::floor(actual_delay / m_interval.GetSeconds() ) * m_interval.GetSeconds();

  //if not in the 1ms of the 5ms window selected, force to the 1ms of the next
  //5ms window
  if ( (actual_delay - mt5) <= 0.001 ) {
    if (joinPolling == "JoinPolling")
      m_sendEvent = Simulator::Schedule (Seconds (delay), &StaClient::Send, this, joinPolling);
    else
      m_sendEvent = Simulator::Schedule (Seconds (delay), &StaClient::Send, this, "");
  }
  else {
    Ptr<UniformRandomVariable> rand = CreateObject <UniformRandomVariable> ();
    double del = rand->GetValue (mt5 + m_interval.GetSeconds() + MicroSeconds(1).GetSeconds(),
        mt5 + m_interval.GetSeconds() + Seconds(0.001).GetSeconds());
    delay = del - Simulator::Now().GetSeconds();
    if (joinPolling == "JoinPolling")
      m_sendEvent = Simulator::Schedule (Seconds (delay), &StaClient::Send, this, joinPolling);
    else
      m_sendEvent = Simulator::Schedule ( Seconds( delay), &StaClient::Send, this, "");
    }
}

void
StaClient::Send (std::string PacketKind)
{
  NS_LOG_FUNCTION (this);
  if (PacketKind == "LastPacket")
    Simulator::Cancel (m_sendEvent);
  NS_ASSERT (m_sendEvent.IsExpired ());
  SeqTsHeader seqTs;
  PacketTag tag;
  OnOffTag initTag;
  seqTs.SetSeq (m_sent);
  Ptr<Packet> p = Create<Packet> ();
  if (PacketKind == "FirstPacket")
  {
    p = Create<Packet> (64-(8+4));
    p->AddHeader (seqTs);
    initTag.SetValue(1);
    p->AddPacketTag(initTag);
  }
  else if (PacketKind == "JoinPolling")
  {
    p = Create<Packet> (m_size-(8+4));
    p->AddHeader (seqTs);
    initTag.SetValue(2);
    p->AddPacketTag(initTag);
  }
  else {
    p = Create<Packet> (m_size-(8+4));
    p->AddHeader (seqTs);
    tag.SetValue( std::floor( seqTs.GetTs().GetSeconds() / m_interval.GetSeconds() ));
    p->AddPacketTag(tag);
  }

  if ((m_socket->Send (p)) >= 0)
    {
      ++m_sent;
      m_totalTx += p->GetSize ();
#ifdef NS3_LOG_ENABLE
    NS_LOG_INFO ("TraceDelay TX " << m_size << " bytes to "
                                    << m_peerAddressString << " Uid: "
                                    << p->GetUid () << " Time: "
                                    << (Simulator::Now ()).As (Time::S));
#endif // NS3_LOG_ENABLE
    }
#ifdef NS3_LOG_ENABLE
  else
    {
      NS_LOG_INFO ("Error while sending " << m_size << " bytes to "
                                          << m_peerAddressString);
    }
#endif // NS3_LOG_ENABLE
  if (m_initFlag && PacketKind == "FirstPacket") 
  {
    Ptr<UniformRandomVariable> rand = CreateObject <UniformRandomVariable> ();
    double delay = rand->GetValue (0, m_startSendIntval.GetSeconds ());
    delay += (m_initStaJoinTime.GetSeconds() - Simulator::Now().GetSeconds());
    std::cout << "Initial TX after delay = " << delay << "s" << std::endl;
    m_sendEvent = Simulator::Schedule (Seconds (delay), &StaClient::Send, this, "JoinPolling");
  }
  else if (m_toJoinFlag && PacketKind == "FirstPacket"){
    m_sendEvent = Simulator::Schedule ((m_timeToJoin), &StaClient::DelayedSession, this, "on", "JoinPolling" );
  }
  else if (m_idleFlag && PacketKind == "FirstPacket"){
     //do nothing
    }
  else if (m_sent < m_count)
    {
      if (m_toJoinFlag && m_onOffFlag && (Simulator::Now().GetSeconds() >= m_offTime.GetSeconds() )){
        DelayedSession("off", "JoinPolling");
      }
      else
        m_sendEvent = Simulator::Schedule (m_interval, &StaClient::Send, this, "");
    }
}


uint64_t
StaClient::GetTotalTx () const
{
  return m_totalTx;
}

} // namespace ns3
