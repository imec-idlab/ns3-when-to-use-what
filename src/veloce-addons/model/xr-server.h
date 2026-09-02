#ifndef XR_SERVER_H
#define XR_SERVER_H

#include "ns3/application.h"
#include "ns3/socket.h"
#include "ns3/event-id.h"
#include "ns3/ptr.h"
#include "ns3/packet.h"
#include "ns3/random-variable-stream.h"
#include <vector>
#include "ns3/traced-callback.h"

namespace ns3 {

    class XrServerUdpApp : public Application
    {
    public:
        static TypeId GetTypeId (void);

        XrServerUdpApp ();
        ~XrServerUdpApp () override;

        void Setup (Address ip, Time interval, uint32_t packetsPerBatch, uint32_t packetSize);

        uint64_t GetTotalTx () const;
        uint64_t GetTotalRx() const;

        /** \brief Number of application-layer packets generated (sent) so far. */
        uint32_t GetSent () const { return m_sent; }

    protected:
        void DoDispose () override;

    private:
        void StartApplication () override;
        void StopApplication () override;

        void ScheduleNextCycle ();
        void ScheduleSendInCycle (uint32_t seqInBatch);
        void SendPacket (uint32_t seqInBatch);
        void HandleRead (Ptr<Socket> socket);

    private:
        Ptr<Socket> m_socket;
        Address     m_peer;
        uint16_t    m_port;
        uint16_t    m_localPort;
        uint8_t m_tos;

        Time        m_interval;         //!< time between batches
        uint32_t    m_packetsPerBatch;  //!< packets per batch
        uint32_t    m_packetSize;       //!< total packet bytes INCLUDING SeqTsHeader (12 bytes)
        uint32_t    m_maxPackets;       //!< 0 means unlimited

        uint32_t    m_sent;
        uint64_t    m_totalTx;

        EventId              m_cycleEvent;
        std::vector<EventId> m_sendEvents;

        uint64_t m_totalRx;
        uint64_t m_received;
        bool m_sinkFlag;


        TracedCallback<Ptr<const Packet>, const Address &, const Address &> m_rxTrace;

#ifdef NS3_LOG_ENABLE
        std::string m_peerAddressString;
#endif
    };

} // namespace ns3

#endif /* XR_SERVER_H */