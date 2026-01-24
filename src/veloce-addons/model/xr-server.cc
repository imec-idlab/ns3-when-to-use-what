#include "xr-server.h"
#include "ns3/log.h"
#include "ns3/udp-socket-factory.h"
#include "ns3/seq-ts-header.h"
#include "packet-tag.h"
#include "ns3/simulator.h"
#include "ns3/double.h"
#include "ns3/boolean.h"

namespace ns3 {
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
                .AddAttribute("RemotePort",
                              "The destination port of the outbound packets",
                              UintegerValue(0),
                              MakeUintegerAccessor(&XrServerUdpApp::m_port),
                              MakeUintegerChecker<uint16_t>())
                .AddAttribute("LocalPort",
                              "Local UDP port to bind",
                              UintegerValue(0),
                              MakeUintegerAccessor(&XrServerUdpApp::m_localPort),
                        MakeUintegerChecker<uint16_t>())
                .AddAttribute ("Tos",
                       "Value of type of service",
                       UintegerValue (0),
                       MakeUintegerAccessor (&XrServerUdpApp::m_tos),
                       MakeUintegerChecker<uint8_t> ())
                        .AddAttribute("Interval",
                              "Inter-batch period",
                              TimeValue(Seconds(0.01111)),
                              MakeTimeAccessor(&XrServerUdpApp::m_interval),
                              MakeTimeChecker())
                 .AddAttribute ("SinkFlag",
                                "To indicate if instance is a sink or server (True for sink and AP otherwise)",
                                BooleanValue (false),
                        MakeBooleanAccessor (&XrServerUdpApp::m_sinkFlag),
                                MakeBooleanChecker ())
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
                              MakeUintegerChecker<uint32_t>())

                .AddTraceSource("Rx",
                                "Packet received",
                                MakeTraceSourceAccessor(&XrServerUdpApp::m_rxTrace),
                                "ns3::Packet::TwoAddressTracedCallback");

        return tid;
    }

    XrServerUdpApp::XrServerUdpApp()
        : m_socket(nullptr),
          m_port(0),
          m_localPort(0),
          m_tos(0),
          m_interval(Seconds(0)),
          m_packetsPerBatch(0),
          m_packetSize(0),
          m_maxPackets(0),
          m_sent(0),
          m_totalTx(0),
          m_totalRx(0),
          m_received(0),
          m_sinkFlag(false) {
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
    uint64_t
    XrServerUdpApp::GetTotalRx() const
    {
        NS_LOG_FUNCTION(this);
        return m_totalRx;
    }

    void
    XrServerUdpApp::DoDispose() {
        Application::DoDispose();
    }

    void
    XrServerUdpApp::StartApplication(void)
    {
        if (!m_socket) {
            m_socket = Socket::CreateSocket(GetNode(), UdpSocketFactory::GetTypeId());
            if (m_sinkFlag) {
                // RX-only
                InetSocketAddress local =
                    InetSocketAddress(Ipv4Address::GetAny(), m_localPort);
                m_socket->Bind(local);
                m_socket->SetRecvCallback(
                    MakeCallback(&XrServerUdpApp::HandleRead, this));
            }
            else {
                // TX-only
                InetSocketAddress remote =
                    InetSocketAddress(InetSocketAddress::ConvertFrom(m_peer).GetIpv4(),
                                      m_port);
                m_socket->Connect(remote);
                m_socket->SetIpTos(m_tos);
                ScheduleNextCycle();
            }
            m_socket->SetAllowBroadcast(true);
        }
    }


    void
    XrServerUdpApp::StopApplication() {
        NS_LOG_FUNCTION(this);

        if (m_sinkFlag == false) {
            Simulator::Cancel(m_cycleEvent);
            for (auto &ev: m_sendEvents) {
                Simulator::Cancel(ev);
            }
            m_sendEvents.clear();
        }

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

    void
    XrServerUdpApp::HandleRead(Ptr<Socket> socket) {
        Address from;
        Address local;
        Ptr<Packet> packet;

        while ((packet = socket->RecvFrom(from))) {
            socket->GetSockName(local);

            if (packet->GetSize() == 0)
                continue;

            m_totalRx += packet->GetSize();
            m_received++;

            Ptr<Packet> pCopy = packet->Copy();
            SeqTsHeader seqTs;
            bool hasSeqTs = packet->RemoveHeader(seqTs);

            if (hasSeqTs) {
                Time txTime = seqTs.GetTs();
                Time rxTime = Simulator::Now();
                Time latency = rxTime - txTime;
            }
            m_rxTrace(pCopy, from, local);
        }
    }
} // namespace ns3
