#ifndef VIDEO_CAMERA_APP_H
#define VIDEO_CAMERA_APP_H

#include "ns3/application.h"
#include "ns3/socket.h"
#include "ns3/event-id.h"
#include "ns3/random-variable-stream.h"
#include "ns3/inet-socket-address.h"

namespace ns3 {

class VideoCameraApp : public Application {
public:
    static TypeId GetTypeId(void);
    VideoCameraApp();
    virtual ~VideoCameraApp();

private:
    virtual void StartApplication(void);
    virtual void StopApplication(void);

    void ScheduleNextFrame(void);
    void GenerateAndSendFrame(void);
    void SendFragments(uint32_t totalSize);

    Ptr<Socket> m_socket;
    Address m_peer;

    // Configurable attributes
    double m_fps;            // frames per second
    uint32_t m_gop;          // I-frame every N frames
    uint32_t m_iMean;        // mean I-frame size (bytes)
    uint32_t m_iStd;         // I-frame std dev
    uint32_t m_pMean;        // mean P-frame size
    uint32_t m_pStd;         // P-frame std dev
    uint32_t m_mtu;          // max UDP payload
    Time m_intraBurstGap;    // gap between fragments in a frame

    // State
    uint32_t m_frameIndex;
    uint32_t m_seqNo;        // per-fragment sequence number (carried in SeqTsHeader)
    EventId  m_nextFrameEvent;
    Ptr<NormalRandomVariable> m_iSize;
    Ptr<NormalRandomVariable> m_pSize;
};

} // namespace ns3
#endif
