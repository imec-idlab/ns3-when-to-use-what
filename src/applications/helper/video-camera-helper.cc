#include "video-camera-helper.h"

#include "ns3/names.h"
#include "ns3/video-camera-app.h"

namespace ns3
{

VideoCameraHelper::VideoCameraHelper(Address remoteAddress)
{
    m_factory.SetTypeId(VideoCameraApp::GetTypeId());
    m_factory.Set("RemoteAddress", AddressValue(remoteAddress));
}

void
VideoCameraHelper::SetAttribute(std::string name, const AttributeValue& value)
{
    m_factory.Set(name, value);
}

ApplicationContainer
VideoCameraHelper::Install(Ptr<Node> node) const
{
    return ApplicationContainer(InstallPriv(node));
}

ApplicationContainer
VideoCameraHelper::Install(std::string nodeName) const
{
    Ptr<Node> node = Names::Find<Node>(nodeName);
    return ApplicationContainer(InstallPriv(node));
}

ApplicationContainer
VideoCameraHelper::Install(NodeContainer c) const
{
    ApplicationContainer apps;
    for (NodeContainer::Iterator i = c.Begin(); i != c.End(); ++i)
    {
        apps.Add(InstallPriv(*i));
    }
    return apps;
}

Ptr<Application>
VideoCameraHelper::InstallPriv(Ptr<Node> node) const
{
    Ptr<Application> app = m_factory.Create<Application>();
    node->AddApplication(app);
    return app;
}

} // namespace ns3
