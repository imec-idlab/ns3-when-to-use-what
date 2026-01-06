#include "xr-server.h"
#include "ns3/log.h"
#include "ns3/udp-socket-factory.h"
#include "ns3/seq-ts-header.h"
#include "packet-tag.h"
#include "ns3/simulator.h"
#include "ns3/double.h"

namespace ns3 {
    /*NS_LOG_COMPONENT_DEFINE("XrServerUdpApp");
    NS_OBJECT_ENSURE_REGISTERED(XrServerUdpApp);

    TypeId XrServerUdpApp::GetTypeId(void) {
        static TypeId tid = TypeId("ns3::XrServerUdpApp")
                .SetParent<Application>()
                .SetGroupName("Applications")
                .AddConstructor<XrServerUdpApp>();
        return tid;
    }

    XrServerUdpApp::XrServerUdpApp()
        : m_sent(0),
          m_packetsPerBatch(0),
          m_packetSize(0) {
        m_rng = CreateObject<UniformRandomVariable>();
    }

    XrServerUdpApp::~XrServerUdpApp() {
        m_socket = nullptr;
    }

    void XrServerUdpApp::Setup(Address peer, Time interval, uint32_t packetsPerBatch, uint32_t packetSize) {
        m_peer = peer;
        m_interval = interval;
        m_packetsPerBatch = packetsPerBatch;
        m_packetSize = packetSize;
    }

    void XrServerUdpApp::StartApplication(void) {
        if (!m_socket) {
            m_socket = Socket::CreateSocket(GetNode(), UdpSocketFactory::GetTypeId());
            m_socket->Connect(m_peer);
        }

        m_rng = CreateObject<UniformRandomVariable>();
        m_socket->SetAllowBroadcast(true);
        ScheduleNextCycle();
    }

    void XrServerUdpApp::StopApplication(void) {
        Simulator::Cancel(m_cycleEvent);
        for (auto &ev: m_sendEvents) {
            Simulator::Cancel(ev);
        }
        m_sendEvents.clear();
    }

    void XrServerUdpApp::ScheduleNextCycle(void) {
        for (uint32_t i = 0; i < m_packetsPerBatch; ++i) {
            ScheduleSendInCycle(m_packetSize);
        }

        m_cycleEvent = Simulator::Schedule(m_interval, &XrServerUdpApp::ScheduleNextCycle, this);
    }

    void XrServerUdpApp::ScheduleSendInCycle(uint32_t sizeBytes) {
        double offsetS = m_rng->GetValue(0.0, 0.002);

        EventId ev = Simulator::Schedule(Seconds(offsetS), &XrServerUdpApp::SendPacket, this, sizeBytes);
        m_sendEvents.push_back(ev);
    }

    void XrServerUdpApp::SendPacket(uint32_t sizeBytes) {
        Ptr<Packet> p = Create<Packet>(sizeBytes - 12);

        SeqTsHeader seqTs;
        seqTs.SetSeq(m_sent++);
        p->AddHeader(seqTs);

        PacketTag tag;
        tag.SetValue(std::floor(Simulator::Now().GetSeconds() / m_interval.GetSeconds()));
        p->AddPacketTag(tag);

        m_socket->Send(p);
    }*/

    NS_LOG_COMPONENT_DEFINE("XrServerUdpApp");
    NS_OBJECT_ENSURE_REGISTERED(XrServerUdpApp);

    TypeId
    XrServerUdpApp::GetTypeId(void) {
        static TypeId tid =
                TypeId("ns3::XrServerUdpApp")
                .SetParent<Application>()
                .SetGroupName("Applications")
                .AddConstructor<XrServerUdpApp>()

                .AddAttribute("RemoteAddress",
                              "Destination address",
                              AddressValue(),
                              MakeAddressAccessor(&XrServerUdpApp::m_peer),
                              MakeAddressChecker())

                .AddAttribute("Interval",
                              "Inter-batch period",
                              TimeValue(Seconds(0.01111)),
                              MakeTimeAccessor(&XrServerUdpApp::m_interval),
                              MakeTimeChecker())

                .AddAttribute("PacketsPerBatch",
                              "Number of packets sent every Interval",
                              UintegerValue(96),
                              MakeUintegerAccessor(&XrServerUdpApp::m_packetsPerBatch),
                              MakeUintegerChecker<uint32_t>())

                .AddAttribute("PacketSize",
                              "Total packet size in bytes inc SeqTsHeader",
                              UintegerValue(1448),
                              MakeUintegerAccessor(&XrServerUdpApp::m_packetSize),
                              MakeUintegerChecker<uint32_t>(12, 65507))

                .AddAttribute("MaxPackets",
                              "Maximum number of packets to send (0 means unlimited).",
                              UintegerValue(0),
                              MakeUintegerAccessor(&XrServerUdpApp::m_maxPackets),
                              MakeUintegerChecker<uint32_t>());

        return tid;
    }

    XrServerUdpApp::XrServerUdpApp()
        : m_socket(nullptr),
          m_interval(Seconds(0)),
          m_packetsPerBatch(0),
          m_packetSize(0),
          m_maxPackets(0),
          m_sent(0),
          m_totalTx(0) {
    }

    XrServerUdpApp::~XrServerUdpApp() {
        m_socket = nullptr;
    }

    void
    XrServerUdpApp::Setup(Address addr, Time interval, uint32_t packetsPerBatch, uint32_t packetSize) {
        m_peer = addr;
        m_interval = interval;
        m_packetsPerBatch = packetsPerBatch;
        m_packetSize = packetSize;
    }

    uint64_t
    XrServerUdpApp::GetTotalTx() const {
        return m_totalTx;
    }

    void
    XrServerUdpApp::DoDispose() {
        Application::DoDispose();
    }

    void XrServerUdpApp::StartApplication(void) {
        if (!m_socket) {
            m_socket = Socket::CreateSocket(GetNode(), UdpSocketFactory::GetTypeId());
            m_socket->Connect(m_peer);
        }

        m_socket->SetAllowBroadcast(true);
        ScheduleNextCycle();
    }

    void
    XrServerUdpApp::StopApplication() {
        NS_LOG_FUNCTION(this);

        Simulator::Cancel(m_cycleEvent);
        for (auto &ev: m_sendEvents) {
            Simulator::Cancel(ev);
        }
        m_sendEvents.clear();

        if (m_socket) {
            m_socket->Close();
            m_socket = nullptr;
        }
    }

    void
    XrServerUdpApp::ScheduleNextCycle() {
        if (m_maxPackets != 0 && m_sent >= m_maxPackets) {
            return;
        }

        for (uint32_t i = 0; i < m_packetsPerBatch; ++i) {
            if (m_maxPackets != 0 && m_sent + i >= m_maxPackets) {
                break;
            }
            ScheduleSendInCycle(i);
        }

        m_cycleEvent = Simulator::Schedule(m_interval, &XrServerUdpApp::ScheduleNextCycle, this);
    }

    void
    XrServerUdpApp::ScheduleSendInCycle(uint32_t seqInBatch) {
        // todo : we want to send video and audio in batches
        Time offset = NanoSeconds(seqInBatch);
        EventId ev = Simulator::Schedule(offset, &XrServerUdpApp::SendPacket, this, seqInBatch);
        m_sendEvents.push_back(ev);
    }

    void
    XrServerUdpApp::SendPacket(uint32_t /*seqInBatch*/) {
        if (m_maxPackets != 0 && m_sent >= m_maxPackets) {
            return;
        }

        SeqTsHeader seqTs;
        seqTs.SetSeq(m_sent);

        const uint32_t headerSize = 12;
        const uint32_t payloadSize = m_packetSize - headerSize;

        Ptr<Packet> p = Create<Packet>(payloadSize);
        p->AddHeader(seqTs);

        int ret = m_socket->Send(p);
        if (ret >= 0) {
            ++m_sent;
            m_totalTx += p->GetSize();
            /*
            #ifdef NS3_LOG_ENABLE
                        NS_LOG_INFO("XR DL TX total=" << m_packetSize
                            << " uid=" << p->GetUid ()
                            << " seq=" << (m_sent - 1)
                            << " to=" << m_peerAddressString
                            << " t=" << Simulator::Now ().As (Time::S));
            #endif
                    }
            #ifdef NS3_LOG_ENABLE
                    else {
                        NS_LOG_INFO("XR DL send error to=" << m_peerAddressString);
                    }
            #endif*/
        }
    }
} // namespace ns3
