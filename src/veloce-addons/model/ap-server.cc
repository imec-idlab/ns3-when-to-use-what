/* -*- Mode:C++; c-file-style:"gnu"; indent-tabs-mode:nil; -*- */
/*
 *  Copyright (c) 2007,2008,2009 INRIA, UDCAST
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
 * Author: Douglas D. Agbeve <douglas.agbeve@uantwerpen.be>
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
#include "ns3/ipv4-packet-info-tag.h"
#include "ns3/ipv6-packet-info-tag.h"

#include "ns3/seq-ts-header.h"
#include "ap-server.h"
#include "ns3/packet-tag.h"
#include "ns3/boolean.h"
#include <algorithm>
#include <cstdint>
#include <utility>
#include <vector>
namespace ns3 {

NS_LOG_COMPONENT_DEFINE ("ApServer");

NS_OBJECT_ENSURE_REGISTERED (ApServer);


TypeId
ApServer::GetTypeId (void)
{
  static TypeId tid = TypeId ("ns3::ApServer")
    .SetParent<Application> ()
    .SetGroupName("Applications")
    .AddConstructor<ApServer> ()
    .AddAttribute ("RemoteAddress",
                   "The destination Address of the outbound packets",
                   AddressValue (),
                   MakeAddressAccessor (&ApServer::m_peerAddress),
                   MakeAddressChecker ())
    .AddAttribute ("LocalAddress",
                   "Local IP Address of the outbound packets",
                   AddressValue (),
                   MakeAddressAccessor (&ApServer::m_localAddress),
                   MakeAddressChecker ())
    .AddAttribute ("StaApFlag",
                   "To indicate if installed on STA or AP (True for STA and AP otherwise)",
                   BooleanValue (false),
                   MakeBooleanAccessor (&ApServer::m_staApFlag),
                   MakeBooleanChecker ())
    .AddAttribute ("Port",
                   "Port on which we listen for incoming packets.",
                   UintegerValue (100),
                   MakeUintegerAccessor (&ApServer::m_port),
                   MakeUintegerChecker<uint16_t> ())
    .AddAttribute ("PacketSize",
                   "Size of packets generated. The minimum packet size is 12 bytes which is the size of the header carrying the sequence number and the time stamp.",
                   UintegerValue (1024),
                   MakeUintegerAccessor (&ApServer::m_size),
                   MakeUintegerChecker<uint32_t> (12,65507))
    .AddAttribute ("PacketWindowSize",
                   "The size of the window used to compute the packet loss. This value should be a multiple of 8.",
                   UintegerValue (32),
                   MakeUintegerAccessor (&ApServer::GetPacketWindowSize,
                                         &ApServer::SetPacketWindowSize),
                   MakeUintegerChecker<uint16_t> (8,256))
    .AddAttribute ("Tos",
                   "Value of type of service",
                   UintegerValue (0),
                   MakeUintegerAccessor (&ApServer::m_tos),
                   MakeUintegerChecker<uint8_t> ())
    .AddAttribute ("NStations",
                   "Number of Stations",
                   UintegerValue (0),
                   MakeUintegerAccessor (&ApServer::m_nStations),
                   MakeUintegerChecker<std::size_t> ())
    .AddAttribute ("Interval",
                   "Time interval between successive packet sending",
                   TimeValue( MilliSeconds(5) ),
                   MakeTimeAccessor (&ApServer::m_interval),
                   MakeTimeChecker ())
    .AddTraceSource ("Rx", "A packet has been received",
                     MakeTraceSourceAccessor (&ApServer::m_rxTrace),
                     "ns3::Packet::TracedCallback")
    .AddTraceSource ("RxWithAddresses", "A packet has been received",
                     MakeTraceSourceAccessor (&ApServer::m_rxTraceWithAddresses),
                     "ns3::Packet::TwoAddressTracedCallback")
  ;
  return tid;
}

ApServer::ApServer ()
  : m_lossCounter (0)
{
  NS_LOG_FUNCTION (this);
  m_received=0;
  m_sendEvent = EventId();
  m_sent = 0;
  m_tagValue = 0;
  m_totalRx = 0;
  m_sentTags = {};
}

ApServer::~ApServer ()
{
  NS_LOG_FUNCTION (this);
}

uint16_t
ApServer::GetPacketWindowSize () const
{
  NS_LOG_FUNCTION (this);
  return m_lossCounter.GetBitMapSize ();
}

void
ApServer::SetPacketWindowSize (uint16_t size)
{
  NS_LOG_FUNCTION (this << size);
  m_lossCounter.SetBitMapSize (size);
}

uint32_t
ApServer::GetLost (void) const
{
  NS_LOG_FUNCTION (this);
  return m_lossCounter.GetLost ();
}

uint64_t
ApServer::GetReceived (void) const
{
  NS_LOG_FUNCTION (this);
  return m_received;
}

uint64_t
ApServer::GetTotalRx() const
{
    NS_LOG_FUNCTION(this);
    return m_totalRx;
}

void
ApServer::DoDispose (void)
{
  NS_LOG_FUNCTION (this);
  Application::DoDispose ();
}

void
ApServer::StartApplication (void)
{
  NS_LOG_FUNCTION (this);


  if (m_socket == nullptr)
    {
      TypeId tid = TypeId::LookupByName ("ns3::UdpSocketFactory");
      m_socket = Socket::CreateSocket (GetNode (), tid);
      InetSocketAddress local = InetSocketAddress (Ipv4Address::GetAny (),
                                                   m_port);
      local.SetTos (m_tos);
      if (m_socket->Bind (local) == -1)
        {
          NS_FATAL_ERROR ("Failed to bind socket");
        }
    }

  m_socket->SetRecvCallback (MakeCallback (&ApServer::HandleRead, this));
  m_socket->SetAllowBroadcast(true);

  if (!m_staApFlag)
    m_sendEvent = Simulator::Schedule (m_interval, &ApServer::five_ms_winB, this);

  if (m_socket6 == nullptr)
    {
      TypeId tid = TypeId::LookupByName ("ns3::UdpSocketFactory");
      m_socket6 = Socket::CreateSocket (GetNode (), tid);
      Inet6SocketAddress local = Inet6SocketAddress (Ipv6Address::GetAny (),
                                                   m_port);
      if (m_socket6->Bind (local) == -1)
        {
          NS_FATAL_ERROR ("Failed to bind socket");
        }
    }

  m_socket6->SetRecvCallback (MakeCallback (&ApServer::HandleRead, this));
  m_socket6->SetAllowBroadcast(true);

}


void
ApServer::StopApplication ()
{
  NS_LOG_FUNCTION (this);

  if (m_socket != nullptr)
    {
      m_socket->SetRecvCallback (MakeNullCallback<void, Ptr<Socket> > ());
    }
}


void
ApServer::HandleRead (Ptr<Socket> socket)
{
  NS_LOG_FUNCTION (this << socket);
  Ptr<Packet> packet;
  Address from;
  Address localAddress;
  while ((packet = socket->RecvFrom (from)))
    {
      socket->GetSockName (localAddress);
      if (packet->GetSize () > 0)
        {
          bool latePacket = false;
          uint32_t receivedSize = packet->GetSize ();
          m_totalRx += receivedSize;
          Ptr<Packet> packet_copy = packet->Copy();
          PacketTag tag;
          packet->RemovePacketTag(tag);
          SeqTsHeader seqTs;
          packet->RemoveHeader (seqTs);
          uint32_t currentSequenceNumber = seqTs.GetSeq ();
          m_tagValue = tag.GetValue();

          m_lossCounter.NotifyReceived (currentSequenceNumber);
          m_received++;

          // check for delayed packet
          if (!m_sentTags.empty() && std::find(m_sentTags.begin(), m_sentTags.end(),
                  m_tagValue ) !=  m_sentTags.end() )
          {
            std::cout<<Simulator::Now().GetMilliSeconds()  <<": received tag value: delayed: "<< m_tagValue<< std::endl;
            latePacket = true;
          }
          else if( ( (Simulator::Now() - seqTs.GetTs ()).GetMilliSeconds() ) >= m_interval.GetMilliSeconds() ) {
            // outdated packets
            latePacket = true;
            m_sentTags.push_back(m_tagValue);
          }

          if (!m_staApFlag && !latePacket ) { //AP not late
            m_rxTraceWithAddresses (packet_copy, from, m_localAddress);
          }
          else if (!m_staApFlag && latePacket ) { //AP late
            m_rxTrace (packet_copy, from, m_localAddress, true);
            break;
          }
          else if (m_staApFlag) { //STA
            m_rxTraceWithAddresses (packet_copy, from, m_localAddress);
            break;
          }
          //check if first time seeing the tag
          if (m_tag2TagVec.find(m_tagValue) == m_tag2TagVec.end() ) {
            // first time
            std::vector<uint64_t> vec {m_tagValue};
            m_tag2TagVec.insert(std::make_pair (m_tagValue, vec ));


            //m_sendEvent = Simulator::Schedule (m_interval, &ApServer::five_ms_window, this, m_tagValue); // schedule in case of delay
            //m_tag2EventId.insert(std::make_pair(m_tagValue, m_sendEvent) );
          }
          else{
            m_tag2TagVec.at(m_tagValue).push_back(m_tagValue);
          }

          for (auto tagVal = m_tag2TagVec.cbegin(), next_tagVal = tagVal; tagVal != m_tag2TagVec.cend();
              tagVal = next_tagVal) {
            auto key = tagVal->first;
            ++next_tagVal;

            if ( tagVal->second.size() == m_nStations )
            {
              SendTo(key, 0);
              m_tag2TagVec.erase(tagVal);
              //Simulator::Cancel(m_tag2EventId.at(key));
              //m_tag2EventId.erase(key);

            }
          } //end for
        }
    }
}

void ApServer::five_ms_window ( uint64_t key ) {

  NS_LOG_FUNCTION (this);


  SendTo(key, 0);

  m_tag2TagVec.erase(key);
}

void ApServer::five_ms_winB(void) {

  NS_LOG_FUNCTION (this);

  if (!m_tag2TagVec.empty()) {

    for (auto tagVal = m_tag2TagVec.cbegin(), next_tagVal = tagVal; tagVal != m_tag2TagVec.cend();
              tagVal = next_tagVal) {
      auto key = tagVal->first;
      ++next_tagVal;

      SendTo(key, 0);
      m_tag2TagVec.erase(tagVal);
      break;
    } //end for
    m_sendEvent = Simulator::Schedule (m_interval, &ApServer::five_ms_winB, this);
    }
  else
    m_sendEvent = Simulator::Schedule (m_interval, &ApServer::five_ms_winB, this);
}

void
ApServer::SendTo (uint64_t tagId, int64_t seqTsV)
{
  NS_LOG_FUNCTION(this);

  SeqTsHeader seqTs;
  if (seqTsV) {
    seqTs.SetTs( seqTsV );
  }
  PacketTag tag;
  tag.SetValue( tagId );

  Ptr<Packet> p = Create<Packet> (m_size-(8+4));
  p->AddHeader (seqTs);
  p->AddPacketTag(tag);

  if ( (m_socket->SendTo(p, 0, m_peerAddress)) >= 0 )
  {
    ++m_sent;
    m_sentTags.push_back(tagId);
  }
  else
  {
    NS_LOG_INFO ("Error while sending " << m_size);
  }
}

} // Namespace ns3
