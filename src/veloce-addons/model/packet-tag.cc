/*
 * Copyright (c) 2006,2007 INRIA
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
#include "ns3/object-base.h"
#include "ns3/simulator.h"

#include "packet-tag.h"
#include <cstdint>


namespace ns3 {

NS_LOG_COMPONENT_DEFINE ("PacketTag");

NS_OBJECT_ENSURE_REGISTERED (PacketTag);

TypeId
PacketTag::GetTypeId(void)
{
    static TypeId tid = TypeId("ns3::MyTag")
                            .SetParent<Tag>()
                            .AddConstructor<PacketTag>()
                            .AddAttribute("SimpleValue",
                                          "A simple value",
                                          UintegerValue (0),
                                          MakeUintegerAccessor(&PacketTag::m_tagSimpleValue),
                                          MakeUintegerChecker<uint64_t>());

    return tid;
}


PacketTag::PacketTag ()
  : m_tagSimpleValue(0)
{
  m_tagSimpleValue = 0;
}

PacketTag::~PacketTag ()
{
  NS_LOG_FUNCTION (this);
}

TypeId
PacketTag::GetInstanceTypeId() const
{
    return GetTypeId();
}

uint32_t
PacketTag::GetSerializedSize() const
{
    return sizeof(uint64_t);
}

void
PacketTag::Serialize(TagBuffer i) const
{
  i.WriteU64(m_tagSimpleValue);
}

void
PacketTag::Deserialize(TagBuffer i)
{
    m_tagSimpleValue = i.ReadU64();
}

void
PacketTag::Print(std::ostream& os) const
{
    os << m_tagSimpleValue;
}

void
PacketTag::SetValue(uint64_t value)
{
    m_tagSimpleValue= value;
}

uint64_t
PacketTag::GetValue() const
{
    return m_tagSimpleValue;
}

TypeId
OnOffTag::GetTypeId(void)
{
    static TypeId tid = TypeId("ns3::MyOnOffTag")
                            .SetParent<Tag>()
                            .AddConstructor<PacketTag>()
                            .AddAttribute("SimpleValue",
                                          "A simple value",
                                          UintegerValue (0),
                                          MakeUintegerAccessor(&OnOffTag::m_tagSimpleValue),
                                          MakeUintegerChecker<uint64_t>());

    return tid;
}


OnOffTag::OnOffTag ()
  : m_tagSimpleValue(0)
{
  m_tagSimpleValue = 0;
}

OnOffTag::~OnOffTag ()
{
  NS_LOG_FUNCTION (this);
}

TypeId
OnOffTag::GetInstanceTypeId() const
{
    return GetTypeId();
}

uint32_t
OnOffTag::GetSerializedSize() const
{
    return sizeof(uint64_t);
}

void
OnOffTag::Serialize(TagBuffer i) const
{
  i.WriteU64(m_tagSimpleValue);
}

void
OnOffTag::Deserialize(TagBuffer i)
{
    m_tagSimpleValue = i.ReadU64();
}

void
OnOffTag::Print(std::ostream& os) const
{
    os << m_tagSimpleValue;
}

void
OnOffTag::SetValue(uint64_t value)
{
    m_tagSimpleValue= value;
}

uint64_t
OnOffTag::GetValue() const
{
    return m_tagSimpleValue;
}


} // ns3 namespace
