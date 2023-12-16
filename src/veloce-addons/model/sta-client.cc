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
  m_onOffEvent = EventId ();
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

  if (m_toJoinFlag)
  {
    m_sendEvent = Simulator::Schedule ((m_timeToJoin), &StaClient::DelayedSession, this, "on" );

  }
  else if (m_initFlag)
  {
    Ptr<UniformRandomVariable> rand = CreateObject <UniformRandomVariable> ();
    double delay = rand->GetValue (0, m_startSendIntval.GetSeconds ());
    std::cout << "Initial TX after delay = " << delay << "s" << std::endl;
    m_sendEvent = Simulator::Schedule (Seconds (delay), &StaClient::Send, this, "FirstPacket");
  }
  else{
    //
  }
}

void
StaClient::StopApplication (void)
{
  NS_LOG_FUNCTION (this);
  Simulator::Cancel (m_sendEvent);
}

void StaClient::DelayedSession (std::string onOrOff)
{
  if (onOrOff == "on"){
    double delay = m_intervalRandomVariable->GetValue();
    std::cout << "Poison On After = " << delay << "s" << std::endl;
    m_sendEvent = Simulator::Schedule (Seconds (delay), &StaClient::Send, this, "FirstPacket");
  }
  else if (onOrOff == "off") {
    double delay = m_intervalRandomVariable->GetValue();
    std::cout << "Poison Off After = " << delay << "s" << std::endl;
    m_sendEvent = Simulator::Schedule (Seconds (delay), &StaClient::Send, this, "LastPacket");
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
  Ptr<Packet> p = Create<Packet> (m_size-(8+4));

  if (PacketKind == "FirstPacket") {
    p = Create<Packet> (64-(8+4));
    p->AddHeader (seqTs);
    initTag.SetValue(1);
    p->AddPacketTag(initTag);
    //if (m_enableRandom)
    //  DelayedSession("off");
  }
  else if (PacketKind == "LastPacket") {
    p = Create<Packet> (64-(8+4));
    p->AddHeader (seqTs);
    initTag.SetValue(2);
    p->AddPacketTag(initTag);
    //if (m_enableRandom)
     // DelayedSession("on");
  }
  else {
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

  if (m_sent < m_count && PacketKind != "LastPacket")
    {
      m_sendEvent = Simulator::Schedule (m_interval, &StaClient::Send, this, "");
    }
}


uint64_t
StaClient::GetTotalTx () const
{
  return m_totalTx;
}

} // namespace ns3
