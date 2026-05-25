#ifndef VIDEO_CAMERA_HELPER_H
#define VIDEO_CAMERA_HELPER_H

#include "ns3/address.h"
#include "ns3/application-container.h"
#include "ns3/attribute.h"
#include "ns3/node-container.h"
#include "ns3/object-factory.h"
#include "ns3/video-camera-app.h"

#include <string>

namespace ns3
{

/**
 * \ingroup applications
 * \brief Helper to install ns3::VideoCameraApp on a set of nodes.
 */
class VideoCameraHelper
{
  public:
    /**
     * \param remoteAddress destination address (UDP) the camera streams to
     */
    VideoCameraHelper(Address remoteAddress);

    /**
     * \param name attribute name on ns3::VideoCameraApp
     * \param value attribute value
     */
    void SetAttribute(std::string name, const AttributeValue& value);

    ApplicationContainer Install(Ptr<Node> node) const;
    ApplicationContainer Install(std::string nodeName) const;
    ApplicationContainer Install(NodeContainer c) const;

  private:
    Ptr<Application> InstallPriv(Ptr<Node> node) const;

    ObjectFactory m_factory;
};

} // namespace ns3

#endif /* VIDEO_CAMERA_HELPER_H */
