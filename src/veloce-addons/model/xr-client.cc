#include "xr-client.h"
#include "ns3/log.h"
#include "ns3/udp-socket-factory.h"
#include "ns3/seq-ts-header.h"
#include "packet-tag.h"

#include "ns3/pointer.h"
#include "ns3/string.h"
#include "ns3/boolean.h"


namespace ns3 {
    NS_LOG_COMPONENT_DEFINE("XrPacketGenerationUdpApp");

    NS_OBJECT_ENSURE_REGISTERED(XrPacketGenerationUdpApp);

    TypeId
    XrPacketGenerationUdpApp::GetTypeId(void) {
        static TypeId tid =
                TypeId("ns3::XrPacketGenerationUdpApp")
                .SetParent<Application>()
                .SetGroupName("Applications")
                .AddConstructor<XrPacketGenerationUdpApp>()

                .AddAttribute("MaxPackets",
                              "The maximum number of packets the application will send",
                              UintegerValue(0),
                              MakeUintegerAccessor(&XrPacketGenerationUdpApp::m_count),
                              MakeUintegerChecker<uint32_t>())
                .AddAttribute("Interval",
                              "Cycle (frame) period for XR uplink traffic", TimeValue(Seconds(1.0)),
                              MakeTimeAccessor(&XrPacketGenerationUdpApp::m_interval),
                              MakeTimeChecker())
                .AddAttribute("StartSendInterval",
                              "Interval within which packets are randomly sent", TimeValue(Seconds(1.0)),
                              MakeTimeAccessor(&XrPacketGenerationUdpApp::m_startSendIntval),
                              MakeTimeChecker())
                .AddAttribute("RemoteAddress",
                              "The destination Address of the outbound packets",
                              AddressValue(),
                              MakeAddressAccessor(&XrPacketGenerationUdpApp::m_peer),
                              MakeAddressChecker())
                .AddAttribute("RemotePort",
                      "The destination port of the outbound packets",
                      UintegerValue(0),
                      MakeUintegerAccessor(&XrPacketGenerationUdpApp::m_port),
                      MakeUintegerChecker<uint16_t>())
                /*.AddAttribute ("PacketSize",
                               "Size of packets generated. The minimum packet size is 12 \
                               bytes which is the size of the header carrying the sequence \
                               number and the time stamp.",
                               UintegerValue (1024),
                               MakeUintegerAccessor (&XrPacketGenerationUdpApp::m_size),
                               MakeUintegerChecker<uint32_t> (12,65507))*/
                .AddAttribute("EnableRandom",
                              "For random traffic instead of CBR",
                              BooleanValue(true),
                              MakeBooleanAccessor(&XrPacketGenerationUdpApp::m_enableRandom),
                              MakeBooleanChecker())
                .AddAttribute("InitPacketSentDelay",
                              "Time to start sending initial packets", TimeValue(Seconds(0.0)),
                              MakeTimeAccessor(&XrPacketGenerationUdpApp::m_initPacketSentDelay),
                              MakeTimeChecker())
                .AddAttribute ("Tos",
                       "Value of type of service",
                       UintegerValue (0),
                       MakeUintegerAccessor (&XrPacketGenerationUdpApp::m_tos),
                       MakeUintegerChecker<uint8_t> ())


                // todo : do we need this?

                .AddAttribute("InitSession",
                              "Flag for initial STA sessions",
                              BooleanValue(false),
                              MakeBooleanAccessor(&XrPacketGenerationUdpApp::m_initFlag),
                              MakeBooleanChecker())
                .AddAttribute("ToJoinSession",
                              "Flag to join the session",
                              BooleanValue(false),
                              MakeBooleanAccessor(&XrPacketGenerationUdpApp::m_toJoinFlag),
                              MakeBooleanChecker())
                .AddAttribute("TimeToJoin",
                              "Time to for random stations to join", TimeValue(Seconds(1.0)),
                              MakeTimeAccessor(&XrPacketGenerationUdpApp::m_timeToJoin),
                              MakeTimeChecker())
                .AddAttribute("InitStaJoinTime",
                              "Time to for initial stations to join after establishing connection",
                              TimeValue(Seconds(1.0)),
                              MakeTimeAccessor(&XrPacketGenerationUdpApp::m_initStaJoinTime),
                              MakeTimeChecker())

                .AddAttribute("IdleStations",
                              "Flag to indicate idle stations",
                              BooleanValue(false),
                              MakeBooleanAccessor(&XrPacketGenerationUdpApp::m_idleFlag),
                              MakeBooleanChecker())
                .AddAttribute("OnOffFlag",
                              "Whether to enable on and off behavior or ONLY on",
                              BooleanValue(false),
                              MakeBooleanAccessor(&XrPacketGenerationUdpApp::m_onOffFlag),
                              MakeBooleanChecker())
                .AddAttribute("IntervalRandomVariable",
                              "For random interval distribution instead of constant",
                              StringValue("ns3::ConstantRandomVariable[Constant=1.0]"),
                              MakePointerAccessor(&XrPacketGenerationUdpApp::m_intervalRandomVariable),
                              MakePointerChecker<RandomVariableStream>());
        return tid;
    }

    void
    XrPacketGenerationUdpApp::DoDispose(void) {
        Application::DoDispose();
    }


    XrPacketGenerationUdpApp::XrPacketGenerationUdpApp()
        : m_socket(nullptr),
          m_rng(nullptr),
          m_interval(Seconds(1.0)),
          m_tos(0),
          m_cycleEvent(),
          m_count(0),
          m_intervalRandomVariable(nullptr),
          m_startSendIntval(Seconds(0.0)),
          m_timeToJoin(Seconds(0.0)),
          m_initStaJoinTime(Seconds(0.0)),
          m_initPacketSentDelay(Seconds(0.0)),
          m_offTime(Seconds(0.0)),
          m_enableRandom(false),
          m_initFlag(false),
          m_toJoinFlag(false),
          m_idleFlag(false),
          m_onOffFlag(false),
          m_sent(0),
          m_totalTx(0),
          m_port(0),
          m_sendEvent(),
          m_tagValue(0) {
    }

    XrPacketGenerationUdpApp::~XrPacketGenerationUdpApp() { m_socket = nullptr; }

    void XrPacketGenerationUdpApp::Setup(Address addr, Time interval) {
        m_peer = addr;
        m_interval = interval;
    }

    void
    XrPacketGenerationUdpApp::StartApplication(void) {
        NS_LOG_FUNCTION(this);
        if (m_socket == nullptr) {
            m_socket = Socket::CreateSocket(GetNode(), UdpSocketFactory::GetTypeId());
            if (InetSocketAddress::IsMatchingType(m_peer)) {
                Ipv4Address addr = InetSocketAddress::ConvertFrom(m_peer).GetIpv4();
                m_socket->Connect(InetSocketAddress(addr, m_port));
            } else {
                m_socket->Connect(m_peer);
            }
            m_socket->SetIpTos(m_tos);
        }
        m_socket->SetRecvCallback(MakeNullCallback<void, Ptr<Socket> >());
        m_socket->SetAllowBroadcast(true);

        if (m_rng == nullptr) {
            m_rng = CreateObject<UniformRandomVariable>();
        }

        Time startDelay = Seconds(0);

        if (m_initPacketSentDelay.GetSeconds() > 0.0) {
            startDelay = m_initPacketSentDelay;
        } else {
            double d = m_rng->GetValue(0.0, m_startSendIntval.GetSeconds());
            startDelay = Seconds(d);
        }

        m_sendEvent = Simulator::Schedule(startDelay,
                                          &XrPacketGenerationUdpApp::ScheduleNextCycle,
                                          this);
    }


    void
    XrPacketGenerationUdpApp::StopApplication() {
        Simulator::Cancel(m_sendEvent);
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

    void XrPacketGenerationUdpApp::ScheduleNextCycle() {
        if (m_count != 0 && m_sent >= m_count) {
            return;
        }
        // Schedule 4 sends uniformly within [0, m_interval)
        // 3 x 106B, 1 x 212B
        ScheduleSendInCycle(106);
        ScheduleSendInCycle(106);
        ScheduleSendInCycle(106);
        ScheduleSendInCycle(212);

        // Schedule next cycle after exactly 11.11 ms
        m_cycleEvent = Simulator::Schedule(m_interval, &XrPacketGenerationUdpApp::ScheduleNextCycle, this);
    }

    void XrPacketGenerationUdpApp::ScheduleSendInCycle(uint32_t sizeBytes) {
        Time offset = Seconds(0);

        if (m_enableRandom) {
            double t = m_rng->GetValue(0.0, m_interval.GetSeconds());
            offset = Seconds(t);
        }

        EventId ev = Simulator::Schedule(offset,
                                         &XrPacketGenerationUdpApp::SendPacket,
                                         this,
                                         sizeBytes);
        m_sendEvents.push_back(ev);
    }


    void
    XrPacketGenerationUdpApp::SendPacket(uint32_t sizeBytes) {
        if (m_count != 0 && m_sent >= m_count) {
            return;
        }

        SeqTsHeader seqTs;
        seqTs.SetSeq(m_sent);

        const uint32_t headerSize = 12;
        //uint32_t hdrSize = seqTs.GetSerializedSize ();
        uint32_t payloadSize = 0;

        if (sizeBytes > headerSize) {
            payloadSize = sizeBytes - headerSize;
        }

        Ptr<Packet> p = Create<Packet>(payloadSize);
        p->AddHeader(seqTs);

        int sentBytes = m_socket->Send(p);
        if (sentBytes >= 0) {
            ++m_sent;
            m_totalTx += p->GetSize();

#ifdef NS3_LOG_ENABLE
            NS_LOG_INFO("XR UL TX total=" << sizeBytes
                << " uid=" << p->GetUid ()
                << " seq=" << (m_sent - 1)
                << " t=" << Simulator::Now ().As (Time::S));
#endif
        }
#ifdef NS3_LOG_ENABLE
        else {
            NS_LOG_INFO("XR UL send error");
        }
#endif
    }
} // namespace ns3
