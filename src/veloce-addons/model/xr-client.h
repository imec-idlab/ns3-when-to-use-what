#ifndef XR_CLIENT_H
#define XR_CLIENT_H

#include "ns3/application.h"
#include "ns3/socket.h"
#include "ns3/event-id.h"
#include "ns3/ptr.h"
#include "ns3/random-variable-stream.h"

namespace ns3 {
    class XrPacketGenerationUdpApp : public Application {
    public:
        /**
        * \brief Get the type ID.
        * \return the object TypeId
        */
        static TypeId GetTypeId(void);

        XrPacketGenerationUdpApp();
        ~XrPacketGenerationUdpApp() override;

        void Setup(Address addr, Time interval);

    protected:
        void DoDispose(void) override;

    private:
        void StartApplication() override;

        void StopApplication() override;

        /**
        * \brief Schedule 4 packets uniformly within [0, m_interval), 3 x 106B, 1 x 212B
        */
        void ScheduleNextCycle();

        void ScheduleSendInCycle(uint32_t sizeBytes);

        void SendPacket(uint32_t sizeBytes);

        Ptr<Socket> m_socket;
        Ptr<UniformRandomVariable> m_rng;
        Time m_interval;
        uint8_t m_tos;

        EventId m_cycleEvent;
        std::vector<EventId> m_sendEvents;


        uint32_t m_count; //!< Maximum number of packets the application will send
        //uint32_t m_size; //!< Size of the sent packet (including the SeqTsHeader)
        Ptr<ExponentialRandomVariable> m_intervalRandomVariable; //!< Random variable for inter-packet interval
        Time m_startSendIntval; //!< Interval within which initial packets are randomly sent
        Time m_timeToJoin; //<! Time for random stations to join the badwagon
        Time m_initStaJoinTime; //<! Time to send actual data after establishing connection
        Time m_initPacketSentDelay; //<! Time to send the initial packets
        Time m_offTime; //<! Time for STA to go off

        bool m_enableRandom; //!< Enable random distribution
        bool m_initFlag; //!< Flag for initial sessions
        bool m_toJoinFlag; //!< Flag for STAs that would join
        bool m_idleFlag; //<! Flag for Idle STAs
        bool m_onOffFlag; //<! Flag for STAs to stay on throughout or have an on
        //and off behavior

        uint32_t m_sent; //!< Counter for sent packets
        uint64_t m_totalTx; //!< Total bytes sent
        Address m_peer; //!< Remote peer address
        uint16_t    m_port;
        EventId m_sendEvent; //!< Event to send the next packet
#ifdef NS3_LOG_ENABLE
        std::string m_peerAddressString; //!< Remote peer address string
#endif // NS3_LOG_ENABLE
        uint64_t m_tagValue; //!< packet tags
    };
} // namespace ns3
#endif
