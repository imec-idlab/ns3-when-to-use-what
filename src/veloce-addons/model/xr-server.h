#ifndef XR_SERVER_H
#define XR_SERVER_H

#include "ns3/application.h"
#include "ns3/socket.h"
#include "ns3/event-id.h"
#include "ns3/ptr.h"
#include "ns3/packet.h"
#include "ns3/random-variable-stream.h"
#include <vector>

namespace ns3 {

    /*class XrServerUdpApp : public Application
    {
    public:
        static TypeId GetTypeId (void);
        XrServerUdpApp ();
        virtual ~XrServerUdpApp ();

        void Setup (Address peer, Time interval, uint32_t packetsPerBatch, uint32_t packetSize);

    private:
        void StartApplication() override;
        void StopApplication() override;

        void ScheduleNextCycle();
        void ScheduleSendInCycle (uint32_t sizeBytes);
        void SendPacket (uint32_t sizeBytes);

        Ptr<Socket>                 m_socket;
        Ptr<UniformRandomVariable>  m_rng;
        Address                     m_peer;
        Time                        m_interval;
        uint32_t                    m_sent;
        uint32_t                    m_packetsPerBatch;
        uint32_t                    m_packetSize;
        EventId                     m_cycleEvent;
        std::vector<EventId>        m_sendEvents;
    };*/

    class XrServerUdpApp : public Application
    {
    public:
        static TypeId GetTypeId (void);

        XrServerUdpApp ();
        ~XrServerUdpApp () override;

        void Setup (Address ip, Time interval, uint32_t packetsPerBatch, uint32_t packetSize);

        uint64_t GetTotalTx () const;

    protected:
        void DoDispose () override;

    private:
        void StartApplication () override;
        void StopApplication () override;

        void ScheduleNextCycle ();
        void ScheduleSendInCycle (uint32_t seqInBatch);
        void SendPacket (uint32_t seqInBatch);

    private:
        Ptr<Socket> m_socket;
        Address     m_peer;

        Time        m_interval;         //!< time between batches
        uint32_t    m_packetsPerBatch;  //!< packets per batch
        uint32_t    m_packetSize;       //!< total packet bytes INCLUDING SeqTsHeader (12 bytes)
        uint32_t    m_maxPackets;       //!< 0 means unlimited

        uint32_t    m_sent;
        uint64_t    m_totalTx;

        EventId              m_cycleEvent;
        std::vector<EventId> m_sendEvents;

#ifdef NS3_LOG_ENABLE
        std::string m_peerAddressString;
#endif
    };

} // namespace ns3

#endif /* XR_SERVER_H */