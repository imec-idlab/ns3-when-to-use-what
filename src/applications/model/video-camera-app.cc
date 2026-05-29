#include "video-camera-app.h"
#include "ns3/udp-socket-factory.h"
#include "ns3/packet.h"
#include "ns3/seq-ts-header.h"
#include "ns3/simulator.h"
#include "ns3/log.h"
#include "ns3/uinteger.h"
#include "ns3/double.h"
#include "ns3/address-utils.h"

#include <algorithm>

namespace ns3 {

NS_LOG_COMPONENT_DEFINE("VideoCameraApp");
NS_OBJECT_ENSURE_REGISTERED(VideoCameraApp);

TypeId VideoCameraApp::GetTypeId(void) {
    static TypeId tid = TypeId("ns3::VideoCameraApp")
        .SetParent<Application>()
        .AddConstructor<VideoCameraApp>()
        .AddAttribute("RemoteAddress", "Destination address",
                      AddressValue(),
                      MakeAddressAccessor(&VideoCameraApp::m_peer),
                      MakeAddressChecker())
        .AddAttribute("Fps", "Frames per second",
                      DoubleValue(30.0),
                      MakeDoubleAccessor(&VideoCameraApp::m_fps),
                      MakeDoubleChecker<double>(1.0, 120.0))
        .AddAttribute("Gop", "GOP length (I-frame period in frames)",
                      UintegerValue(30),
                      MakeUintegerAccessor(&VideoCameraApp::m_gop),
                      MakeUintegerChecker<uint32_t>(1))
        .AddAttribute("IFrameMeanBytes", "Mean I-frame size",
                      UintegerValue(50000),
                      MakeUintegerAccessor(&VideoCameraApp::m_iMean),
                      MakeUintegerChecker<uint32_t>())
        .AddAttribute("IFrameStdBytes", "I-frame std deviation",
                      UintegerValue(8000),
                      MakeUintegerAccessor(&VideoCameraApp::m_iStd),
                      MakeUintegerChecker<uint32_t>())
        .AddAttribute("PFrameMeanBytes", "Mean P-frame size",
                      UintegerValue(2048),
                      MakeUintegerAccessor(&VideoCameraApp::m_pMean),
                      MakeUintegerChecker<uint32_t>())
        .AddAttribute("PFrameStdBytes", "P-frame std deviation",
                      UintegerValue(1024),
                      MakeUintegerAccessor(&VideoCameraApp::m_pStd),
                      MakeUintegerChecker<uint32_t>())
        .AddAttribute("Mtu", "Max UDP payload bytes",
                      UintegerValue(1400),
                      MakeUintegerAccessor(&VideoCameraApp::m_mtu),
                      MakeUintegerChecker<uint32_t>(100, 1500))
        .AddAttribute("IntraBurstGap",
                      "Time between consecutive fragments of one frame",
                      TimeValue(MicroSeconds(50)),
                      MakeTimeAccessor(&VideoCameraApp::m_intraBurstGap),
                      MakeTimeChecker())
        .AddAttribute("PostFirstFrameTime",
                      "Absolute simulation time at which the SECOND frame is "
                      "scheduled (overrides 1/Fps for the second frame only). "
                      "If 0, normal cadence applies from frame 1 onward.",
                      TimeValue(Seconds(0)),
                      MakeTimeAccessor(&VideoCameraApp::m_postFirstFrameTime),
                      MakeTimeChecker());
    return tid;
}

VideoCameraApp::VideoCameraApp() : m_socket(0), m_frameIndex(0), m_seqNo(0) {}
VideoCameraApp::~VideoCameraApp() {}

void VideoCameraApp::StartApplication(void) {
    if (!m_socket) {
        m_socket = Socket::CreateSocket(GetNode(),
                                        UdpSocketFactory::GetTypeId());
        m_socket->Bind();
        m_socket->Connect(m_peer);
    }
    m_iSize = CreateObject<NormalRandomVariable>();
    m_iSize->SetAttribute("Mean", DoubleValue(m_iMean));
    m_iSize->SetAttribute("Variance", DoubleValue((double)m_iStd * m_iStd));
    m_pSize = CreateObject<NormalRandomVariable>();
    m_pSize->SetAttribute("Mean", DoubleValue(m_pMean));
    m_pSize->SetAttribute("Variance", DoubleValue((double)m_pStd * m_pStd));

    m_frameIndex = 0;
    m_seqNo = 0;
    ScheduleNextFrame();
}

void VideoCameraApp::StopApplication(void) {
    if (m_nextFrameEvent.IsRunning()) Simulator::Cancel(m_nextFrameEvent);
    if (m_socket) { m_socket->Close(); m_socket = 0; }
}

void VideoCameraApp::ScheduleNextFrame(void) {
    Time interval = Seconds(1.0 / m_fps);
    // After the very first frame fires, optionally push the SECOND frame's
    // scheduled time forward to m_postFirstFrameTime (absolute) so it doesn't
    // collide with the AP's MU-TX stabilization window. m_frameIndex is
    // incremented in GenerateAndSendFrame BEFORE calling ScheduleNextFrame,
    // so == 1 here means "we just sent frame 0, scheduling frame 1".
    if (m_frameIndex == 1 && !m_postFirstFrameTime.IsZero() &&
        Simulator::Now() < m_postFirstFrameTime)
    {
        interval = m_postFirstFrameTime - Simulator::Now();
    }
    m_nextFrameEvent = Simulator::Schedule(
        interval, &VideoCameraApp::GenerateAndSendFrame, this);
}

void VideoCameraApp::GenerateAndSendFrame(void) {
    bool isI = (m_frameIndex % m_gop) == 0;
    double raw = isI ? m_iSize->GetValue() : m_pSize->GetValue();
    double clamped = std::clamp(raw, 500.0, isI ? 200000.0 : 30000.0);
    uint32_t size = static_cast<uint32_t>(clamped);

    NS_LOG_INFO("Frame " << m_frameIndex
                << (isI ? " I " : " P ")
                << size << " bytes");

    Time frameTs = Simulator::Now();
    SendFragments(size, frameTs);
    m_frameIndex++;
    ScheduleNextFrame();
}

void VideoCameraApp::SendFragments(uint32_t totalSize, Time frameTs) {
    const uint32_t hdrSize = SeqTsHeader().GetSerializedSize();
    NS_ASSERT_MSG(m_mtu > hdrSize, "MTU must exceed SeqTsHeader size");
    const uint32_t maxPayload = m_mtu - hdrSize;

    uint32_t remaining = totalSize;
    Time t = Seconds(0);
    while (remaining > 0) {
        uint32_t chunk = std::min(remaining, maxPayload);
        Simulator::Schedule(t, [this, chunk, frameTs]() {
            Ptr<Packet> p = Create<Packet>(chunk);
            SeqTsHeader hdr;
            hdr.SetSeq(m_seqNo++);
            hdr.SetTs(frameTs.GetNanoSeconds());
            p->AddHeader(hdr);
            m_socket->Send(p);
        });
        remaining -= chunk;
        t += m_intraBurstGap;
    }
}

} // namespace ns3
