
/*
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
#include "ap-server-helper.h"
#include "ns3/ap-server.h"
#include "ns3/uinteger.h"
#include "ns3/string.h"

namespace ns3 {

ApServerHelper::ApServerHelper ()
{
  m_factory.SetTypeId (ApServer::GetTypeId ());
}

ApServerHelper::ApServerHelper (uint16_t port)
{
  m_factory.SetTypeId (ApServer::GetTypeId ());
  SetAttribute ("Port", UintegerValue (port));
}


void
ApServerHelper::SetAttribute (std::string name, const AttributeValue &value)
{
  m_factory.Set (name, value);
}

ApplicationContainer
ApServerHelper::Install (NodeContainer c)
{
  ApplicationContainer apps;
  for (NodeContainer::Iterator i = c.Begin (); i != c.End (); ++i)
    {
      Ptr<Node> node = *i;
      m_server = m_factory.Create<ApServer> ();
      node->AddApplication (m_server);
      apps.Add (m_server);
    }
  return apps;
}

Ptr<ApServer>
ApServerHelper::GetServer (void)
{
  return m_server;
}




StaClientHelper::StaClientHelper ()
{
  m_factory.SetTypeId (StaClient::GetTypeId ());
}

StaClientHelper::StaClientHelper (Address address, uint16_t port)
{
  m_factory.SetTypeId (StaClient::GetTypeId ());
  SetAttribute ("RemoteAddress", AddressValue (address));
  SetAttribute ("RemotePort", UintegerValue (port));
}

StaClientHelper::StaClientHelper (Address address)
{
  m_factory.SetTypeId (StaClient::GetTypeId ());
  SetAttribute ("RemoteAddress", AddressValue (address));
}

void
StaClientHelper::SetAttribute (std::string name, const AttributeValue &value)
{
  m_factory.Set (name, value);
}

ApplicationContainer
StaClientHelper::Install (NodeContainer c)
{
  ApplicationContainer apps;
  for (NodeContainer::Iterator i = c.Begin (); i != c.End (); ++i)
    {
      Ptr<Node> node = *i;
      Ptr<StaClient> client = m_factory.Create<StaClient> ();
      node->AddApplication (client);
      apps.Add (client);
    }
  return apps;
}


} //namespace ns3
