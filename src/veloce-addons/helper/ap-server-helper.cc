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
    ApServerHelper::ApServerHelper() {
        m_factory.SetTypeId(ApServer::GetTypeId());
    }

    ApServerHelper::ApServerHelper(uint16_t port) {
        m_factory.SetTypeId(ApServer::GetTypeId());
        SetAttribute("Port", UintegerValue(port));
    }


    void
    ApServerHelper::SetAttribute(std::string name, const AttributeValue &value) {
        m_factory.Set(name, value);
    }

    VeloceAppContainer
    ApServerHelper::Install(NodeContainer c) {
        VeloceAppContainer apps;
        for (NodeContainer::Iterator i = c.Begin(); i != c.End(); ++i) {
            Ptr<Node> node = *i;
            m_server = m_factory.Create<ApServer>();
            node->AddApplication(m_server);
            apps.Add(m_server);
        }
        return apps;
    }

    Ptr<ApServer>
    ApServerHelper::GetServer(void) {
        return m_server;
    }


    StaClientHelper::StaClientHelper() {
        m_factory.SetTypeId(StaClient::GetTypeId());
    }

    StaClientHelper::StaClientHelper(Address address, uint16_t port) {
        m_factory.SetTypeId(StaClient::GetTypeId());
        SetAttribute("RemoteAddress", AddressValue(address));
        SetAttribute("RemotePort", UintegerValue(port));
    }

    StaClientHelper::StaClientHelper(Address address) {
        m_factory.SetTypeId(StaClient::GetTypeId());
        SetAttribute("RemoteAddress", AddressValue(address));
    }

    void
    StaClientHelper::SetAttribute(std::string name, const AttributeValue &value) {
        m_factory.Set(name, value);
    }

    VeloceAppContainer
    StaClientHelper::Install(NodeContainer c) {
        VeloceAppContainer apps;
        for (NodeContainer::Iterator i = c.Begin(); i != c.End(); ++i) {
            Ptr<Node> node = *i;
            Ptr<StaClient> client = m_factory.Create<StaClient>();
            node->AddApplication(client);
            apps.Add(client);
        }
        return apps;
    }


    // xr client helper class
    XrClientHelper::XrClientHelper() {
        m_factory.SetTypeId(XrPacketGenerationUdpApp::GetTypeId());
    }

    XrClientHelper::XrClientHelper(Address ip, uint16_t port) {
        m_factory.SetTypeId(XrPacketGenerationUdpApp::GetTypeId());
        SetAttribute("RemoteAddress", AddressValue(ip));
        SetAttribute("RemotePort", UintegerValue(port));
    }

    XrClientHelper::XrClientHelper(Address addr) {
        m_factory.SetTypeId(XrPacketGenerationUdpApp::GetTypeId());
        SetAttribute("RemoteAddress", AddressValue(addr));
    }

    void
    XrClientHelper::SetAttribute(std::string name, const AttributeValue &value) {
        m_factory.Set(name, value);
    }

    XrAppContainer
    XrClientHelper::Install(NodeContainer c) const {
        XrAppContainer apps;
        for (NodeContainer::Iterator i = c.Begin(); i != c.End(); ++i) {
            Ptr<Node> node = *i;
            Ptr<XrPacketGenerationUdpApp> client = m_factory.Create<XrPacketGenerationUdpApp>();
            node->AddApplication(client);
            apps.Add(client);
        }
        return apps;
    }


    // xr server helper class
    XrServerHelper::XrServerHelper() {
        m_factory.SetTypeId(XrServerUdpApp::GetTypeId());
    }

    XrServerHelper::XrServerHelper(Address ip, uint16_t port) {
        m_factory.SetTypeId(XrServerUdpApp::GetTypeId());
        SetAttribute("RemoteAddress", AddressValue(ip));
        SetAttribute("RemotePort", UintegerValue(port));
    }

    XrServerHelper::XrServerHelper(Address addr) {
        m_factory.SetTypeId(XrServerUdpApp::GetTypeId());
        SetAttribute("RemoteAddress", AddressValue(addr));
    }

    void
    XrServerHelper::SetAttribute(std::string name, const AttributeValue &value) {
        m_factory.Set(name, value);
    }

    XrAppContainer
    XrServerHelper::Install(NodeContainer c) const {
        XrAppContainer apps;
        for (NodeContainer::Iterator i = c.Begin(); i != c.End(); ++i) {
            Ptr<Node> node = *i;
            Ptr<XrServerUdpApp> server = m_factory.Create<XrServerUdpApp>();
            node->AddApplication(server);
            apps.Add(server);
        }
        return apps;
    }
} //namespace ns3
