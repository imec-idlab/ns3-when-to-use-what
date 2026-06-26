/*
 * Copyright (c) 2026 IDLab (UAntwerpen & Imec)
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 2 as
 * published by the Free Software Foundation;
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * Author: Douglas Agbeve <douglas.agbeve@uantwerpen.be>
 */

#include "cmab-multi-user-scheduler.h"

#include "he-configuration.h"
#include "he-frame-exchange-manager.h"
#include "he-phy.h"

#include "ns3/log.h"
#include "ns3/wifi-acknowledgment.h"
#include "ns3/wifi-mac-queue.h"
#include "ns3/wifi-protection.h"
#include "ns3/wifi-psdu.h"
#include "ns3/double.h"
#include "ns3/enum.h"

#include <algorithm>
#include <cmath>
#include <numeric>
#include <random>

namespace ns3
{

NS_LOG_COMPONENT_DEFINE("CmabMultiUserScheduler");

NS_OBJECT_ENSURE_REGISTERED(CmabMultiUserScheduler);

TypeId
CmabMultiUserScheduler::GetTypeId()
{
    static TypeId tid =
        TypeId("ns3::CmabMultiUserScheduler")
            .SetParent<MultiUserScheduler>()
            .SetGroupName("Wifi")
            .AddConstructor<CmabMultiUserScheduler>()
            .AddAttribute("NStations",
                          "The maximum number of stations that can be granted an RU in a DL MU "
                          "OFDMA transmission",
                          UintegerValue(4),
                          MakeUintegerAccessor(&CmabMultiUserScheduler::m_nStations),
                          MakeUintegerChecker<uint8_t>(1, 255))
            .AddAttribute("EnableTxopSharing",
                          "If enabled, allow A-MPDUs of different TIDs in a DL MU PPDU.",
                          BooleanValue(true),
                          MakeBooleanAccessor(&CmabMultiUserScheduler::m_enableTxopSharing),
                          MakeBooleanChecker())
            .AddAttribute("ForceDlOfdma",
                          "If enabled, return DL_MU_TX even if no DL MU PPDU could be built.",
                          BooleanValue(false),
                          MakeBooleanAccessor(&CmabMultiUserScheduler::m_forceDlOfdma),
                          MakeBooleanChecker())
            .AddAttribute("EnableUlOfdma",
                          "If enabled, return UL_MU_TX if DL_MU_TX was returned the previous time.",
                          BooleanValue(true),
                          MakeBooleanAccessor(&CmabMultiUserScheduler::m_enableUlOfdma),
                          MakeBooleanChecker())
            .AddAttribute("EnableBsrp",
                          "If enabled, send a BSRP Trigger Frame before an UL MU transmission.",
                          BooleanValue(true),
                          MakeBooleanAccessor(&CmabMultiUserScheduler::m_enableBsrp),
                          MakeBooleanChecker())
            .AddAttribute("UlPsduSize",
                          "The default size in bytes of the solicited PSDU (to be sent in a TB PPDU)",
                          UintegerValue(500),
                          MakeUintegerAccessor(&CmabMultiUserScheduler::m_ulPsduSize),
                          MakeUintegerChecker<uint32_t>())
            .AddAttribute("UseCentral26TonesRus",
                          "If enabled, central 26-tone RUs are allocated, too, when the "
                          "selected RU type is at least 52 tones.",
                          BooleanValue(false),
                          MakeBooleanAccessor(&CmabMultiUserScheduler::m_useCentral26TonesRus),
                          MakeBooleanChecker())
            .AddAttribute("MaxCredits",
                          "Maximum amount of credits a station can have (legacy RR knob, unused by CMAB).",
                          TimeValue(Seconds(1)),
                          MakeTimeAccessor(&CmabMultiUserScheduler::m_maxCredits),
                          MakeTimeChecker())
            .AddAttribute("RuAllocationType",
                          "The type of RUs allocated to STAs; if undefined, dynamically selected based on the number of STAs.",
                          EnumValue(HeRu::RU_UNDEFINED),
                          MakeEnumAccessor(&CmabMultiUserScheduler::m_ruAllocationType),
                          MakeEnumChecker(HeRu::RU_26_TONE,    "Ru-26-Tone",
                                          HeRu::RU_52_TONE,    "Ru-52-Tone",
                                          HeRu::RU_106_TONE,   "Ru-106-Tone",
                                          HeRu::RU_242_TONE,   "Ru-242-Tone",
                                          HeRu::RU_484_TONE,   "Ru-484-Tone",
                                          HeRu::RU_996_TONE,   "Ru-996-Tone",
                                          HeRu::RU_2x996_TONE, "Ru-2x996-Tone",
                                          HeRu::RU_UNDEFINED,  "Ru-Undefined"))
            .AddAttribute("Algorithm",
                          "CMAB algorithm used to pick the K stations to solicit in each Basic TF.",
                          EnumValue(CMAB_CUCB),
                          MakeEnumAccessor(&CmabMultiUserScheduler::m_algorithm),
                          MakeEnumChecker(CMAB_CUCB,             "CUCB",
                                          CMAB_ThompsonSampling, "ThompsonSampling",
                                          CMAB_EpsilonGreedy,    "EpsilonGreedy",
                                          CMAB_EXP3M,            "EXP3M"))
            .AddAttribute("RewardType",
                          "Per-arm reward: Binary (1 if STA sent any bytes) or "
                          "FairnessWeighted (normalised bytes / (1 + pulls/N)).",
                          EnumValue(REWARD_FairnessWeighted),
                          MakeEnumAccessor(&CmabMultiUserScheduler::m_rewardType),
                          MakeEnumChecker(REWARD_Binary,           "Binary",
                                          REWARD_FairnessWeighted, "FairnessWeighted"))
            .AddAttribute("UcbConstant",
                          "Exploration constant c for CUCB (score = mean + c * sqrt(2 ln t / n_i)).",
                          DoubleValue(std::sqrt(2.0)),
                          MakeDoubleAccessor(&CmabMultiUserScheduler::m_ucbConstant),
                          MakeDoubleChecker<double>(0.0))
            .AddAttribute("Epsilon",
                          "Random-exploration probability for EpsilonGreedy in [0,1].",
                          DoubleValue(0.1),
                          MakeDoubleAccessor(&CmabMultiUserScheduler::m_epsilon),
                          MakeDoubleChecker<double>(0.0, 1.0))
            .AddAttribute("Exp3Gamma",
                          "Mixing parameter gamma for EXP3.M in (0,1]; smaller = more exploitation.",
                          DoubleValue(0.1),
                          MakeDoubleAccessor(&CmabMultiUserScheduler::m_exp3Gamma),
                          MakeDoubleChecker<double>(1e-6, 1.0))
            .AddAttribute("AcAwareReward",
                          "If enabled, the per-arm bandit reward is scaled by the access "
                          "category of the station's buffered data (VO=1.0, VI=0.75, BE=0.5, "
                          "BK=0.25), so the bandit learns to prefer serving higher-priority "
                          "(e.g. time-critical VO) traffic. Default off keeps the AC-agnostic "
                          "reward.",
                          BooleanValue(false),
                          MakeBooleanAccessor(&CmabMultiUserScheduler::m_acAwareReward),
                          MakeBooleanChecker());
    return tid;
}

CmabMultiUserScheduler::CmabMultiUserScheduler()
{
    NS_LOG_FUNCTION(this);
}

CmabMultiUserScheduler::~CmabMultiUserScheduler()
{
    NS_LOG_FUNCTION_NOARGS();
}

void
CmabMultiUserScheduler::DoInitialize()
{
    NS_LOG_FUNCTION(this);
    NS_ASSERT(m_apMac);
    m_apMac->TraceConnectWithoutContext(
        "AssociatedSta",
        MakeCallback(&CmabMultiUserScheduler::NotifyStationAssociated, this));
    m_apMac->TraceConnectWithoutContext(
        "DeAssociatedSta",
        MakeCallback(&CmabMultiUserScheduler::NotifyStationDeassociated, this));
    for (const auto& ac : wifiAcList)
    {
        m_staListDl.insert({ac.first, {}});
    }
    m_rngU = CreateObject<UniformRandomVariable>();
    m_rngN = CreateObject<NormalRandomVariable>();
    m_rngG = CreateObject<GammaRandomVariable>();
    MultiUserScheduler::DoInitialize();
}

void
CmabMultiUserScheduler::DoDispose()
{
    NS_LOG_FUNCTION(this);
    // Final arm-state summary -- enable with NS_LOG=CmabMultiUserScheduler=info to inspect.
    for (const auto& [aid, arm] : m_arms)
    {
        NS_LOG_INFO("ArmSummary aid=" << aid
                                       << " pulls=" << arm.pulls
                                       << " meanReward=" << arm.Mean()
                                       << " alpha=" << arm.alpha
                                       << " beta=" << arm.beta
                                       << " weight=" << arm.weight);
    }
    m_staListDl.clear();
    m_staListUl.clear();
    m_candidates.clear();
    m_arms.clear();
    m_lastBasicTfAids.clear();
    m_preBasicTfBytes.clear();
    m_txParams.Clear();
    m_apMac->TraceDisconnectWithoutContext(
        "AssociatedSta",
        MakeCallback(&CmabMultiUserScheduler::NotifyStationAssociated, this));
    m_apMac->TraceDisconnectWithoutContext(
        "DeAssociatedSta",
        MakeCallback(&CmabMultiUserScheduler::NotifyStationDeassociated, this));
    MultiUserScheduler::DoDispose();
}


MultiUserScheduler::TxFormat
CmabMultiUserScheduler::SelectTxFormat()
{
    NS_LOG_FUNCTION(this);


    Ptr<const WifiMpdu> mpdu = m_edca->PeekNextMpdu(m_linkId);

    if (mpdu && !m_apMac->GetHeSupported(mpdu->GetHeader().GetAddr1()))
    {
        return SU_TX;
    }

    auto ResetUlState = [&]() {
        m_ulIdleState = m_enableBsrp ? UlIdleState::SEND_BSRP : UlIdleState::SEND_BASIC;
    };

    if ((mpdu && m_ulIdleState != UlIdleState::SEND_BSRP) || !m_enableUlOfdma)
    {
        ResetUlState();
        return TrySendingDlMuPpdu();
    }

    if (m_enableBsrp)
    {
        TxFormat txFormat;

        if (m_ulIdleState == UlIdleState::SEND_BSRP)
        {
            txFormat = TrySendingBsrpTf();
            if (txFormat != DL_MU_TX)
            {
                m_ulIdleState = UlIdleState::SEND_BASIC;
                return txFormat;
            }
        }
        else if (m_ulIdleState == UlIdleState::SEND_BASIC)
        {
            txFormat = TrySendingBasicTf();
            if (txFormat != DL_MU_TX)
            {
                m_ulIdleState = UlIdleState::SEND_DLMU;
                return txFormat;
            }
        }
    }
    else
    {
        if (m_ulIdleState == UlIdleState::SEND_BASIC)
        {
            TxFormat txFormat = TrySendingBasicTf();
            if (txFormat != DL_MU_TX)
            {
                m_ulIdleState = UlIdleState::SEND_DLMU;
                return txFormat;
            }
        }
    }

    ResetUlState();
    return TrySendingDlMuPpdu();
}

// ---------------------------------------------------------------------------
// GetTxVectorForUlMu — accepts an optional CMAB-selected AID ordering
// ---------------------------------------------------------------------------

template <class Func>
WifiTxVector
CmabMultiUserScheduler::GetTxVectorForUlMu(Func canbeSolicited,
                                           bool isBasicTrigger,
                                           const std::vector<uint16_t>& cmabSelectedAids)
{
    NS_LOG_FUNCTION(this);

    auto count = std::min<std::size_t>(m_nStations, m_staListUl.size());
    std::size_t nCentral26TonesRus;
    if (m_ruAllocationType == HeRu::RU_UNDEFINED)
    {
        HeRu::GetEqualSizedRusForStations(m_allowedWidth, count, nCentral26TonesRus);
        NS_ASSERT(count >= 1);
    }
    else
    {
        count = std::min(HeRu::GetRusOfType(m_allowedWidth, m_ruAllocationType).size(), count);
        nCentral26TonesRus = HeRu::GetCentral26TonesRus(m_allowedWidth, m_ruAllocationType).size();
    }

    if (!m_useCentral26TonesRus)
    {
        nCentral26TonesRus = 0;
    }

    Ptr<HeConfiguration> heConfiguration = m_apMac->GetHeConfiguration();
    NS_ASSERT(heConfiguration);

    WifiTxVector txVector;
    txVector.SetPreambleType(WIFI_PREAMBLE_HE_TB);
    txVector.SetChannelWidth(m_allowedWidth);
    txVector.SetGuardInterval(heConfiguration->GetGuardInterval().GetNanoSeconds());
    txVector.SetBssColor(heConfiguration->GetBssColor());

    m_candidates.clear();
    const std::size_t maxCandidates = std::min<std::size_t>(m_nStations, count + nCentral26TonesRus);

    // Helper to add one MasterInfo entry to txVector if it passes the filters.
    auto tryAdd = [&](std::list<MasterInfo>::iterator staIt) -> bool {
        if (!canbeSolicited(*staIt))
        {
            return false;
        }
        if (txVector.GetPreambleType() == WIFI_PREAMBLE_EHT_TB &&
            !m_apMac->GetEhtSupported(staIt->address))
        {
            return false;
        }

        // BA agreement check (UL OFDMA needs block ack).
        uint8_t tid = 0;
        while (tid < 8)
        {
            if (m_apMac->GetBaAgreementEstablishedAsRecipient(staIt->address, tid))
            {
                break;
            }
            ++tid;
        }
        if (tid == 8)
        {
            return false;
        }

        if (txVector.GetHeMuUserInfoMap().empty())
        {
            if (m_apMac->GetEhtSupported() && m_apMac->GetEhtSupported(staIt->address))
            {
                txVector.SetPreambleType(WIFI_PREAMBLE_EHT_TB);
                txVector.SetEhtPpduType(0);
            }
        }

        WifiMacHeader hdr(WIFI_MAC_QOSDATA);
        hdr.SetAddr1(GetWifiRemoteStationManager(m_linkId)
                         ->GetAffiliatedStaAddress(staIt->address)
                         .value_or(staIt->address));
        hdr.SetAddr2(m_apMac->GetFrameExchangeManager(m_linkId)->GetAddress());
        WifiTxVector suTxVector =
            GetWifiRemoteStationManager(m_linkId)->GetDataTxVector(hdr, m_allowedWidth);
        txVector.SetHeMuUserInfo(staIt->aid,
                                 {HeRu::RuSpec(),
                                  suTxVector.GetMode().GetMcsValue(),
                                  suTxVector.GetNss()});
        m_candidates.emplace_back(staIt, nullptr);
        return true;
    };

    if (cmabSelectedAids.empty())
    {
        // Fall-back: round-robin iteration over m_staListUl.
        for (auto staIt = m_staListUl.begin();
             staIt != m_staListUl.end() && txVector.GetHeMuUserInfoMap().size() < maxCandidates;
             ++staIt)
        {
            tryAdd(staIt);
        }
    }
    else
    {
        // CMAB ordering: iterate the selected AIDs in priority order.
        for (uint16_t aid : cmabSelectedAids)
        {
            if (txVector.GetHeMuUserInfoMap().size() >= maxCandidates)
            {
                break;
            }
            auto staIt = std::find_if(m_staListUl.begin(),
                                      m_staListUl.end(),
                                      [aid](const MasterInfo& mi) { return mi.aid == aid; });
            if (staIt == m_staListUl.end())
            {
                continue;
            }
            tryAdd(staIt);
        }
    }

    if (txVector.GetHeMuUserInfoMap().empty())
    {
        NS_LOG_DEBUG("No suitable station");
        return txVector;
    }

    FinalizeTxVector(txVector, isBasicTrigger);
    return txVector;
}

// ---------------------------------------------------------------------------
// BSRP TF — CMAB picks which K STAs to poll for buffer status reports.
// ---------------------------------------------------------------------------

MultiUserScheduler::TxFormat
CmabMultiUserScheduler::TrySendingBsrpTf()
{
    NS_LOG_FUNCTION(this);

    if (m_staListUl.empty())
    {
        return TxFormat::SU_TX;
    }

    auto [ruCount, ruCentral26] = ComputeRuLayout();
    const std::size_t numArms = std::min<std::size_t>(m_nStations, ruCount + ruCentral26);
    std::vector<uint16_t> cmabAids = SelectArmsByCmab(numArms);

    WifiTxVector txVector = GetTxVectorForUlMu([this](const MasterInfo& info) {
        const auto& staList = m_apMac->GetStaList(m_linkId);
        return staList.find(info.aid) != staList.cend();
    }, false, cmabAids);

    if (txVector.GetHeMuUserInfoMap().empty())
    {
        return TxFormat::DL_MU_TX;
    }

    m_trigger = CtrlTriggerHeader(TriggerFrameType::BSRP_TRIGGER, txVector);
    txVector.SetGuardInterval(m_trigger.GetGuardInterval());

    auto item = GetTriggerFrame(m_trigger, m_linkId);
    m_triggerMacHdr = item->GetHeader();

    m_txParams.Clear();
    m_txParams.m_txVector =
        m_apMac->GetWifiRemoteStationManager(m_linkId)->GetRtsTxVector(m_triggerMacHdr.GetAddr1());

    if (!GetHeFem(m_linkId)->TryAddMpdu(item, m_txParams, m_availableTime))
    {
        return NO_TX;
    }

    Time qosNullTxDuration = Seconds(0);
    for (const auto& userInfo : m_trigger)
    {
        Time duration = WifiPhy::CalculateTxDuration(GetMaxSizeOfQosNullAmpdu(m_trigger),
                                                     txVector,
                                                     m_apMac->GetWifiPhy(m_linkId)->GetPhyBand(),
                                                     userInfo.GetAid12());
        qosNullTxDuration = Max(qosNullTxDuration, duration);
    }

    if (m_availableTime != Time::Min())
    {
        NS_ASSERT(m_txParams.m_protection &&
                  m_txParams.m_protection->protectionTime != Time::Min());
        NS_ASSERT(m_txParams.m_acknowledgment &&
                  (m_txParams.m_acknowledgment->acknowledgmentTime != Time::Min()
                   || m_txParams.m_acknowledgment->acknowledgmentTime.IsZero()));
        NS_ASSERT(m_txParams.m_txDuration != Time::Min());

        if (m_txParams.m_protection->protectionTime + m_txParams.m_txDuration
                + m_apMac->GetWifiPhy(m_linkId)->GetSifs() + qosNullTxDuration >
            m_availableTime)
        {
            return NO_TX;
        }
    }

    uint16_t ulLength;
    std::tie(ulLength, qosNullTxDuration) = HePhy::ConvertHeTbPpduDurationToLSigLength(
        qosNullTxDuration,
        m_trigger.GetHeTbTxVector(m_trigger.begin()->GetAid12()),
        m_apMac->GetWifiPhy(m_linkId)->GetPhyBand());
    m_trigger.SetUlLength(ulLength);


    return UL_MU_TX;
}


MultiUserScheduler::TxFormat
CmabMultiUserScheduler::TrySendingBasicTf()
{
    NS_LOG_FUNCTION(this);

    if (m_staListUl.empty())
    {
        return TxFormat::SU_TX;
    }
    NS_ABORT_MSG_IF(m_ulPsduSize == 0, "The UlPsduSize attribute must be set to a non-null value");

    WifiTxVector txVector = GetTxVectorForUlMu([this](const MasterInfo& info) {
        const auto& staList = m_apMac->GetStaList(m_linkId);
        return staList.find(info.aid) != staList.cend() &&
               m_apMac->GetMaxBufferStatus(info.address) > 0;
    }, true);

    if (txVector.GetHeMuUserInfoMap().empty())
    {
        return TxFormat::DL_MU_TX;
    }

    uint32_t maxBufferSize = 0;
    for (const auto& candidate : txVector.GetHeMuUserInfoMap())
    {
        if (!candidate.first)
        {
            maxBufferSize = ((m_ulPsduSize + 511) / 512) * 512;
            continue;
        }
        auto address = m_apMac->GetMldOrLinkAddressByAid(candidate.first);
        NS_ASSERT_MSG(address, "AID " << candidate.first << " not found");

        uint8_t queueSize = m_apMac->GetMaxBufferStatus(*address);
        if (queueSize == 255)
        {
            // unknown
        }
        else if (queueSize == 254)
        {
            maxBufferSize = 0xffffffff;
        }
        else
        {
            maxBufferSize = std::max(maxBufferSize, static_cast<uint32_t>(queueSize * 256));
        }
    }

    if (maxBufferSize == 0)
    {
        return DL_MU_TX;
    }

    m_trigger = CtrlTriggerHeader(TriggerFrameType::BASIC_TRIGGER, txVector);
    txVector.SetGuardInterval(m_trigger.GetGuardInterval());

    auto item = GetTriggerFrame(m_trigger, m_linkId);
    m_triggerMacHdr = item->GetHeader();

    Time maxDuration = GetPpduMaxTime(txVector.GetPreambleType());

    m_txParams.Clear();
    m_txParams.m_txVector =
        m_apMac->GetWifiRemoteStationManager(m_linkId)->GetRtsTxVector(m_triggerMacHdr.GetAddr1());

    if (!GetHeFem(m_linkId)->TryAddMpdu(item, m_txParams, m_availableTime))
    {
        return NO_TX;
    }

    if (m_availableTime != Time::Min())
    {
        NS_ASSERT(m_txParams.m_protection &&
                  m_txParams.m_protection->protectionTime != Time::Min());
        NS_ASSERT(m_txParams.m_acknowledgment &&
                  (m_txParams.m_acknowledgment->acknowledgmentTime != Time::Min()
                   || m_txParams.m_acknowledgment->acknowledgmentTime.IsZero()));
        NS_ASSERT(m_txParams.m_txDuration != Time::Min());

        maxDuration = Min(maxDuration,
                          m_availableTime - m_txParams.m_protection->protectionTime -
                              m_txParams.m_txDuration - m_apMac->GetWifiPhy(m_linkId)->GetSifs() -
                              m_txParams.m_acknowledgment->acknowledgmentTime);
        if (maxDuration.IsNegative())
        {
            return NO_TX;
        }
    }

    Time bufferTxTime = Seconds(0);
    for (const auto& userInfo : m_trigger)
    {
        Time duration = WifiPhy::CalculateTxDuration(maxBufferSize,
                                                     txVector,
                                                     m_apMac->GetWifiPhy(m_linkId)->GetPhyBand(),
                                                     userInfo.GetAid12());
        bufferTxTime = Max(bufferTxTime, duration);
    }

    if (bufferTxTime < maxDuration)
    {
        maxDuration = bufferTxTime;
    }
    else
    {
        Time minDuration = Seconds(0);
        for (const auto& userInfo : m_trigger)
        {
            Time duration =
                WifiPhy::CalculateTxDuration(m_ulPsduSize,
                                             txVector,
                                             m_apMac->GetWifiPhy(m_linkId)->GetPhyBand(),
                                             userInfo.GetAid12());
            minDuration = (minDuration.IsZero() ? duration : Min(minDuration, duration));
        }
        if (maxDuration < minDuration)
        {
            return NO_TX;
        }
    }

    uint16_t ulLength;
    std::tie(ulLength, maxDuration) = HePhy::ConvertHeTbPpduDurationToLSigLength(
        maxDuration, txVector, m_apMac->GetWifiPhy(m_linkId)->GetPhyBand());
    m_trigger.SetUlLength(ulLength);

    for (auto& userInfo : m_trigger)
    {
        userInfo.SetBasicTriggerDepUserInfo(0, 0, m_edca->GetAccessCategory());
    }

    for (const auto& candidate : m_candidates)
    {
        m_staListUl.splice(m_staListUl.end(), m_staListUl, candidate.first);
    }

    return UL_MU_TX;
}


MultiUserScheduler::TxFormat
CmabMultiUserScheduler::TrySendingDlMuPpdu()
{
    NS_LOG_FUNCTION(this);

    AcIndex primaryAc = m_edca->GetAccessCategory();

    if (m_staListDl[primaryAc].empty())
    {
        return TxFormat::SU_TX;
    }

    std::size_t count =
        std::min(static_cast<std::size_t>(m_nStations), m_staListDl[primaryAc].size());
    std::size_t nCentral26TonesRus;
    HeRu::RuType ruType;
    if (m_ruAllocationType == HeRu::RU_UNDEFINED)
    {
        ruType = HeRu::GetEqualSizedRusForStations(m_allowedWidth, count, nCentral26TonesRus);
    }
    else
    {
        ruType = m_ruAllocationType;
        count = std::min(HeRu::GetRusOfType(m_allowedWidth, m_ruAllocationType).size(), count);
        nCentral26TonesRus = HeRu::GetCentral26TonesRus(m_allowedWidth, m_ruAllocationType).size();
    }
    NS_ASSERT(count >= 1);

    if (!m_useCentral26TonesRus)
    {
        nCentral26TonesRus = 0;
    }

    uint8_t currTid = wifiAcList.at(primaryAc).GetHighTid();
    Ptr<WifiMpdu> mpdu = m_edca->PeekNextMpdu(m_linkId);
    if (mpdu && mpdu->GetHeader().IsQosData())
    {
        currTid = mpdu->GetHeader().GetQosTid();
    }

    std::vector<uint8_t> tids;
    if (m_enableTxopSharing)
    {
        for (auto acIt = wifiAcList.find(primaryAc); acIt != wifiAcList.end(); acIt++)
        {
            uint8_t firstTid = (acIt->first == primaryAc ? currTid : acIt->second.GetHighTid());
            tids.push_back(firstTid);
            tids.push_back(acIt->second.GetOtherTid(firstTid));
        }
    }
    else
    {
        tids.push_back(currTid);
    }

    Ptr<HeConfiguration> heConfiguration = m_apMac->GetHeConfiguration();
    NS_ASSERT(heConfiguration);

    m_txParams.Clear();
    m_txParams.m_txVector.SetPreambleType(WIFI_PREAMBLE_HE_MU);
    m_txParams.m_txVector.SetChannelWidth(m_allowedWidth);
    m_txParams.m_txVector.SetGuardInterval(heConfiguration->GetGuardInterval().GetNanoSeconds());
    m_txParams.m_txVector.SetBssColor(heConfiguration->GetBssColor());

    Time actualAvailableTime = (m_initialFrame ? Time::Min() : m_availableTime);

    auto staIt = m_staListDl[primaryAc].begin();
    m_candidates.clear();

    while (staIt != m_staListDl[primaryAc].end() &&
           m_candidates.size() <
               std::min(static_cast<std::size_t>(m_nStations), count + nCentral26TonesRus))
    {
        if (m_txParams.m_txVector.GetPreambleType() == WIFI_PREAMBLE_EHT_MU &&
            !m_apMac->GetEhtSupported(staIt->address))
        {
            staIt++;
            continue;
        }

        HeRu::RuType currRuType = (m_candidates.size() < count ? ruType : HeRu::RU_26_TONE);

        for (uint8_t tid : tids)
        {
            AcIndex ac = QosUtilsMapTidToAc(tid);
            NS_ASSERT(ac >= primaryAc);
            if (m_apMac->GetBaAgreementEstablishedAsOriginator(staIt->address, tid))
            {
                mpdu = m_apMac->GetQosTxop(ac)->PeekNextMpdu(m_linkId, tid, staIt->address);
                if (mpdu)
                {
                    mpdu = GetHeFem(m_linkId)->CreateAliasIfNeeded(mpdu);
                    WifiTxVector suTxVector =
                        GetWifiRemoteStationManager(m_linkId)->GetDataTxVector(mpdu->GetHeader(),
                                                                               m_allowedWidth);
                    WifiTxVector txVectorCopy = m_txParams.m_txVector;

                    m_txParams.m_txVector.SetHeMuUserInfo(staIt->aid,
                                                          {{currRuType, 1, true},
                                                           suTxVector.GetMode().GetMcsValue(),
                                                           suTxVector.GetNss()});

                    if (!GetHeFem(m_linkId)->TryAddMpdu(mpdu, m_txParams, actualAvailableTime))
                    {
                        m_txParams.m_txVector = txVectorCopy;
                    }
                    else
                    {
                        m_candidates.emplace_back(staIt, mpdu);
                        break;
                    }
                }
            }
        }

        if (m_candidates.size() == 1)
        {
            if (m_apMac->GetEhtSupported() && m_apMac->GetEhtSupported(staIt->address))
            {
                m_txParams.m_txVector.SetPreambleType(WIFI_PREAMBLE_EHT_MU);
                m_txParams.m_txVector.SetEhtPpduType(0);
            }
        }
        staIt++;
    }

    if (m_candidates.empty())
    {
        return m_forceDlOfdma ? NO_TX : SU_TX;
    }
    return TxFormat::DL_MU_TX;
}


void
CmabMultiUserScheduler::FinalizeTxVector(WifiTxVector& txVector, bool /*isBasicTrigger*/)
{
    NS_LOG_FUNCTION(this);
    NS_ASSERT(txVector.GetHeMuUserInfoMap().size() == m_candidates.size());

    std::size_t nRusAssigned = m_candidates.size();
    std::size_t nCentral26TonesRus;
    HeRu::RuType ruType;
    if (m_ruAllocationType == HeRu::RU_UNDEFINED)
    {
        ruType = HeRu::GetEqualSizedRusForStations(m_allowedWidth, nRusAssigned, nCentral26TonesRus);
    }
    else
    {
        ruType = m_ruAllocationType;
        nRusAssigned = std::min(HeRu::GetRusOfType(m_allowedWidth, m_ruAllocationType).size(), nRusAssigned);
        nCentral26TonesRus = HeRu::GetCentral26TonesRus(m_allowedWidth, m_ruAllocationType).size();
    }

    if (!m_useCentral26TonesRus || m_candidates.size() == nRusAssigned)
    {
        nCentral26TonesRus = 0;
    }
    else
    {
        nCentral26TonesRus = std::min(m_candidates.size() - nRusAssigned, nCentral26TonesRus);
    }

    WifiTxVector::HeMuUserInfoMap heMuUserInfoMap;
    std::swap(heMuUserInfoMap, txVector.GetHeMuUserInfoMap());

    auto candidateIt = m_candidates.begin();
    auto ruSet = HeRu::GetRusOfType(m_allowedWidth, ruType);
    auto ruSetIt = ruSet.begin();
    auto central26TonesRus = HeRu::GetCentral26TonesRus(m_allowedWidth, ruType);
    auto central26TonesRusIt = central26TonesRus.begin();

    for (std::size_t i = 0; i < nRusAssigned + nCentral26TonesRus; i++)
    {
        NS_ASSERT(candidateIt != m_candidates.end());
        auto mapIt = heMuUserInfoMap.find(candidateIt->first->aid);
        NS_ASSERT(mapIt != heMuUserInfoMap.end());

        HeMuUserInfo info = {(i < nRusAssigned ? *ruSetIt++ : *central26TonesRusIt++),
                             mapIt->second.mcs, mapIt->second.nss};
        info.ru.SetRandomAccessFlag(false);
        txVector.SetHeMuUserInfo(mapIt->first, info);
        candidateIt++;
    }

    m_candidates.erase(candidateIt, m_candidates.end());
}


void
CmabMultiUserScheduler::UpdateCredits(std::list<MasterInfo>& /*staList*/,
                                      Time /*txDuration*/,
                                      const WifiTxVector& /*txVector*/)
{
    // CMAB doesn't use credit-based fairness; the bandit reward shapes fairness.
}


MultiUserScheduler::DlMuInfo
CmabMultiUserScheduler::ComputeDlMuInfo()
{
    NS_LOG_FUNCTION(this);
    if (m_candidates.empty())
    {
        return DlMuInfo();
    }

    DlMuInfo dlMuInfo;
    std::swap(dlMuInfo.txParams.m_txVector, m_txParams.m_txVector);
    FinalizeTxVector(dlMuInfo.txParams.m_txVector, false);

    m_txParams.Clear();
    Ptr<WifiMpdu> mpdu;
    Time actualAvailableTime = (m_initialFrame ? Time::Min() : m_availableTime);

    for (const auto& candidate : m_candidates)
    {
        mpdu = candidate.second;
        NS_ASSERT(mpdu);
        bool ret [[maybe_unused]] =
            GetHeFem(m_linkId)->TryAddMpdu(mpdu, dlMuInfo.txParams, actualAvailableTime);
        NS_ASSERT_MSG(ret, "MPDU does not meet constraints when transmitted over a larger RU");
    }

    for (const auto& candidate : m_candidates)
    {
        mpdu = candidate.second;
        NS_ASSERT(mpdu);
        uint8_t tid = mpdu->GetHeader().GetQosTid();
        NS_ASSERT(mpdu->IsQueued());
        Ptr<WifiMpdu> item = mpdu;
        if (!mpdu->GetHeader().IsRetry())
        {
            item = GetHeFem(m_linkId)->GetMsduAggregator()->GetNextAmsdu(mpdu,
                                                                          dlMuInfo.txParams,
                                                                          m_availableTime);
            if (!item)
            {
                item = mpdu;
            }
            m_apMac->GetQosTxop(QosUtilsMapTidToAc(tid))->AssignSequenceNumber(item);
        }

        std::vector<Ptr<WifiMpdu>> mpduList =
            GetHeFem(m_linkId)->GetMpduAggregator()->GetNextAmpdu(item,
                                                                   dlMuInfo.txParams,
                                                                   m_availableTime);
        if (mpduList.size() > 1)
        {
            dlMuInfo.psduMap[candidate.first->aid] = Create<WifiPsdu>(std::move(mpduList));
        }
        else
        {
            dlMuInfo.psduMap[candidate.first->aid] = Create<WifiPsdu>(item, true);
        }
    }

    return dlMuInfo;
}

MultiUserScheduler::UlMuInfo
CmabMultiUserScheduler::ComputeUlMuInfo()
{
    return UlMuInfo{m_trigger, m_triggerMacHdr, std::move(m_txParams)};
}


void
CmabMultiUserScheduler::NotifyStationAssociated(uint16_t aid, Mac48Address address)
{
    NS_LOG_FUNCTION(this << aid << address);

    if (!m_apMac->GetHeSupported(address))
    {
        return;
    }
    auto mldOrLinkAddress = m_apMac->GetMldOrLinkAddressByAid(aid);
    NS_ASSERT_MSG(mldOrLinkAddress, "AID " << aid << " not found");

    for (auto& staList : m_staListDl)
    {
        const auto staIt = std::find_if(staList.second.cbegin(),
                                        staList.second.cend(),
                                        [aid](auto&& info) { return info.aid == aid; });
        if (staIt == staList.second.cend())
        {
            staList.second.push_back(MasterInfo{aid, *mldOrLinkAddress, 0.0});
        }
    }

    const auto staIt = std::find_if(m_staListUl.cbegin(), m_staListUl.cend(),
                                    [aid](auto&& info) { return info.aid == aid; });
    if (staIt == m_staListUl.cend())
    {
        m_staListUl.push_back(MasterInfo{aid, *mldOrLinkAddress, 0.0});
    }

    // Initialise bandit state for this arm.
    m_arms.emplace(aid, ArmState{});
}

void
CmabMultiUserScheduler::NotifyStationDeassociated(uint16_t aid, Mac48Address address)
{
    NS_LOG_FUNCTION(this << aid << address);

    if (!m_apMac->GetHeSupported(address))
    {
        return;
    }
    auto mldOrLinkAddress = m_apMac->GetMldOrLinkAddressByAid(aid);
    NS_ASSERT_MSG(mldOrLinkAddress, "AID " << aid << " not found");

    if (m_apMac->IsAssociated(*mldOrLinkAddress))
    {
        return;
    }

    for (auto& staList : m_staListDl)
    {
        staList.second.remove_if([&aid](const MasterInfo& info) { return info.aid == aid; });
    }
    m_staListUl.remove_if([&aid](const MasterInfo& info) { return info.aid == aid; });
    m_arms.erase(aid);
}


void
CmabMultiUserScheduler::NotifyBsrpResponse(Mac48Address senderAddr, uint8_t reportedQueueSize)
{
    NS_LOG_FUNCTION(this << senderAddr << +reportedQueueSize);

    // Resolve AID for this sender.
    auto staIt = std::find_if(m_staListUl.begin(), m_staListUl.end(),
                              [&senderAddr](const MasterInfo& mi) {
                                  return mi.address == senderAddr;
                              });
    if (staIt == m_staListUl.end())
    {
        return;
    }
    uint16_t aid = staIt->aid;

    auto armIt = m_arms.find(aid);
    if (armIt == m_arms.end())
    {
        return;
    }
    auto& arm = armIt->second;

    // Decode the BSR octet from the QoS Control field:
    //   255 = unknown (treat as no info), 254 = unlimited, else value * 256 bytes.
    uint32_t bytesReported = 0;
    if (reportedQueueSize == 254)
    {
        bytesReported = m_maxBytesPerTxop;
    }
    else if (reportedQueueSize != 255)
    {
        bytesReported = static_cast<uint32_t>(reportedQueueSize) * 256;
    }

    const std::size_t N = std::max<std::size_t>(1, m_staListUl.size());
    double reward = 0.0;
    if (m_rewardType == REWARD_Binary)
    {
        reward = (bytesReported > 0) ? 1.0 : 0.0;
    }
    else // FairnessWeighted
    {
        double normBytes = std::min(1.0,
                                    static_cast<double>(bytesReported) /
                                        static_cast<double>(m_maxBytesPerTxop));
        double pulls = static_cast<double>(arm.pulls);
        double fairness = 1.0 / (1.0 + pulls / static_cast<double>(N));
        reward = normBytes * fairness;
    }

    // Scale by the access category of the STA's buffered data (no-op unless
    // AcAwareReward is set), so the bandit learns to prefer higher-AC traffic.
    reward *= AcRewardWeight(senderAddr);

    arm.pulls++;
    arm.rewardSum += reward;
    arm.alpha += reward;
    arm.beta += (1.0 - reward);

    if (m_algorithm == CMAB_EXP3M)
    {
        // Use the p_i stashed at SelectArmsByCmab time (importance-weighted
        // estimator requires *selection-time* probability, not post-hoc).
        // Fallback to uniform 1/N if no record exists (first round corner case).
        double p;
        auto pIt = m_lastSelectionP.find(aid);
        if (pIt != m_lastSelectionP.end())
        {
            p = pIt->second;
        }
        else
        {
            std::size_t n = std::max<std::size_t>(1, m_staListUl.size());
            p = 1.0 / static_cast<double>(n);
        }
        double estR = reward / std::max(p, 1e-6);
        double K = static_cast<double>(std::max<std::size_t>(1, m_nStations));
        arm.weight *= std::exp(m_exp3Gamma * estR / K);
        arm.weight = std::min(arm.weight, 1e6);
    }
    // m_timeStep is now incremented once per SelectArmsByCmab call (round),
    // not per reward observation -- see CUCB convention.
}

void
CmabMultiUserScheduler::NotifyBsrpNoResponse(Mac48Address senderAddr)
{
    NotifyBsrpResponse(senderAddr, 0);
}


std::pair<std::size_t, std::size_t>
CmabMultiUserScheduler::ComputeRuLayout() const
{
    std::size_t count = std::min<std::size_t>(m_nStations, m_staListUl.size());
    std::size_t nCentral26TonesRus = 0;
    if (m_ruAllocationType == HeRu::RU_UNDEFINED)
    {
        HeRu::GetEqualSizedRusForStations(m_allowedWidth, count, nCentral26TonesRus);
    }
    else
    {
        count = std::min(HeRu::GetRusOfType(m_allowedWidth, m_ruAllocationType).size(), count);
        nCentral26TonesRus = HeRu::GetCentral26TonesRus(m_allowedWidth, m_ruAllocationType).size();
    }
    if (!m_useCentral26TonesRus)
    {
        nCentral26TonesRus = 0;
    }
    return {count, nCentral26TonesRus};
}

int
CmabMultiUserScheduler::StaHighestAcWithData(Mac48Address address) const
{
    // TID -> AC priority rank (standard UP->AC): VO(6,7)=3, VI(4,5)=2, BE(0,3)=1, BK(1,2)=0.
    static const int tidToRank[8] = {1, 0, 0, 1, 2, 2, 3, 3};
    int best = -1;
    for (uint8_t tid = 0; tid < 8; ++tid)
    {
        uint8_t bs = m_apMac->GetBufferStatus(tid, address);
        if (bs != 255 && bs > 0)
        {
            best = std::max(best, tidToRank[tid]);
        }
    }
    return best;
}

double
CmabMultiUserScheduler::AcRewardWeight(Mac48Address address) const
{
    if (!m_acAwareReward)
    {
        return 1.0;
    }
    // rank -> weight: BK=0.25, BE=0.5, VI=0.75, VO=1.0; unknown AC -> neutral 1.0.
    static const double acWeight[4] = {0.25, 0.5, 0.75, 1.0};
    int rank = StaHighestAcWithData(address);
    return (rank >= 0 && rank < 4) ? acWeight[rank] : 1.0;
}

double
CmabMultiUserScheduler::UcbScore(const ArmState& arm) const
{
    if (arm.pulls == 0 || m_timeStep == 0)
    {
        return std::numeric_limits<double>::infinity();
    }
    return arm.Mean() +
           m_ucbConstant * std::sqrt(2.0 * std::log(static_cast<double>(m_timeStep)) /
                                     static_cast<double>(arm.pulls));
}

std::vector<uint16_t>
CmabMultiUserScheduler::SelectArmsByCmab(std::size_t k)
{
    NS_LOG_FUNCTION(this << k);
    std::vector<uint16_t> selection;
    if (m_staListUl.empty() || k == 0)
    {
        return selection;
    }

    const std::size_t poolSize = m_staListUl.size();
    k = std::min(k, poolSize);

    // CUCB convention: t = number of rounds played, not total arm pulls.
    // Increment once per selection, not per reward.
    ++m_timeStep;

    switch (m_algorithm)
    {
    case CMAB_CUCB:
    {
        std::vector<std::pair<double, uint16_t>> scored;
        scored.reserve(poolSize);
        for (const auto& mi : m_staListUl)
        {
            scored.emplace_back(UcbScore(m_arms.at(mi.aid)), mi.aid);
        }
        std::partial_sort(scored.begin(), scored.begin() + k, scored.end(),
                          [](const auto& a, const auto& b) { return a.first > b.first; });
        for (std::size_t i = 0; i < k; ++i)
        {
            selection.push_back(scored[i].second);
        }
        break;
    }
    case CMAB_ThompsonSampling:
    {
        // True Beta(α, β) sampling via two Gamma draws:
        //   X = G1 / (G1 + G2),  G1 ~ Gamma(α, 1),  G2 ~ Gamma(β, 1)
        // Used for BOTH reward types: rewards are in [0,1] so Beta is a valid
        // posterior; α += reward, β += (1 - reward) handles continuous values
        // the same way as binary.
        std::vector<std::pair<double, uint16_t>> sampled;
        sampled.reserve(poolSize);
        for (const auto& mi : m_staListUl)
        {
            const auto& arm = m_arms.at(mi.aid);
            const double g1 = m_rngG->GetValue(arm.alpha, 1.0);
            const double g2 = m_rngG->GetValue(arm.beta, 1.0);
            const double s = g1 / std::max(g1 + g2, 1e-300);
            sampled.emplace_back(s, mi.aid);
        }
        std::partial_sort(sampled.begin(), sampled.begin() + k, sampled.end(),
                          [](const auto& a, const auto& b) { return a.first > b.first; });
        for (std::size_t i = 0; i < k; ++i)
        {
            selection.push_back(sampled[i].second);
        }
        break;
    }
    case CMAB_EpsilonGreedy:
    {
        if (m_rngU->GetValue(0.0, 1.0) < m_epsilon)
        {
            // Explore: reservoir-sample k AIDs without replacement (Algorithm R).
            // Single pass over m_staListUl using ns-3's RNG -- no std::default_random_engine.
            selection.reserve(k);
            std::size_t i = 0;
            for (const auto& mi : m_staListUl)
            {
                if (i < k)
                {
                    selection.push_back(mi.aid);
                }
                else
                {
                    std::size_t j = m_rngU->GetInteger(0, static_cast<uint32_t>(i));
                    if (j < k)
                    {
                        selection[j] = mi.aid;
                    }
                }
                ++i;
            }
        }
        else
        {
            // Exploit: top-k by empirical mean (unplayed arms get +inf so each
            // is tried at least once during the initial exploration phase).
            std::vector<std::pair<double, uint16_t>> scored;
            scored.reserve(poolSize);
            for (const auto& mi : m_staListUl)
            {
                const auto& arm = m_arms.at(mi.aid);
                double s = (arm.pulls == 0) ? std::numeric_limits<double>::infinity() : arm.Mean();
                scored.emplace_back(s, mi.aid);
            }
            std::partial_sort(scored.begin(), scored.begin() + k, scored.end(),
                              [](const auto& a, const auto& b) { return a.first > b.first; });
            for (std::size_t i = 0; i < k; ++i)
            {
                selection.push_back(scored[i].second);
            }
        }
        break;
    }
    case CMAB_EXP3M:
    {
        // EXP3.M: p_i = (1-γ) w_i / Σw + γ/N; pick k via weighted sampling
        // without replacement (Efraimidis-Spirakis A-Res). We stash each p_i
        // in m_lastSelectionP so the reward update can use the *selection-time*
        // probability rather than reconstructing it from now-stale weights.
        double sumW = 0.0;
        for (const auto& mi : m_staListUl)
        {
            sumW += m_arms.at(mi.aid).weight;
        }
        m_lastSelectionP.clear();
        std::vector<std::pair<double, uint16_t>> keys;
        keys.reserve(poolSize);
        for (const auto& mi : m_staListUl)
        {
            double w = m_arms.at(mi.aid).weight;
            double p = (1.0 - m_exp3Gamma) * (w / std::max(sumW, 1e-12)) +
                       m_exp3Gamma / static_cast<double>(poolSize);
            m_lastSelectionP[mi.aid] = p;
            double u = m_rngU->GetValue(1e-12, 1.0);
            double key = std::pow(u, 1.0 / std::max(p, 1e-12));
            keys.emplace_back(key, mi.aid);
        }
        std::partial_sort(keys.begin(), keys.begin() + k, keys.end(),
                          [](const auto& a, const auto& b) { return a.first > b.first; });
        for (std::size_t i = 0; i < k; ++i)
        {
            selection.push_back(keys[i].second);
        }
        break;
    }
    }

    NS_LOG_DEBUG("CMAB selected " << selection.size() << " arms out of " << poolSize);
    return selection;
}

void
CmabMultiUserScheduler::UpdateBanditRewards()
{
    NS_LOG_FUNCTION(this << m_lastBasicTfAids.size());
    const std::size_t N = std::max<std::size_t>(1, m_staListUl.size());

    for (uint16_t aid : m_lastBasicTfAids)
    {
        auto armIt = m_arms.find(aid);
        if (armIt == m_arms.end())
        {
            continue;
        }
        auto address = m_apMac->GetMldOrLinkAddressByAid(aid);
        if (!address)
        {
            continue;
        }
        // Reward = freshly-reported BSR for this polled STA. A non-zero value
        // means polling this arm was useful (the STA had data to send).
        uint8_t qs = m_apMac->GetMaxBufferStatus(*address);
        uint32_t bytesReported = (qs == 255 || qs == 254)
                                     ? 0 : static_cast<uint32_t>(qs) * 256;

        double reward = 0.0;
        if (m_rewardType == REWARD_Binary)
        {
            reward = (bytesReported > 0) ? 1.0 : 0.0;
        }
        else // FairnessWeighted
        {
            double normBytes = std::min(1.0,
                                        static_cast<double>(bytesReported) /
                                            static_cast<double>(m_maxBytesPerTxop));
            double pulls = static_cast<double>(armIt->second.pulls);
            double fairness = 1.0 / (1.0 + pulls / static_cast<double>(N));
            reward = normBytes * fairness;
        }

        // Scale by the access category of the STA's buffered data (no-op unless
        // AcAwareReward is set), so the bandit learns to prefer higher-AC traffic.
        reward *= AcRewardWeight(*address);

        auto& arm = armIt->second;
        arm.pulls++;
        arm.rewardSum += reward;
        // Beta posterior update (binary view; harmless if reward in [0,1]).
        arm.alpha += reward;
        arm.beta += (1.0 - reward);
        // EXP3.M weight update: ŵ_i *= exp(γ * r̃_i / K), with r̃ = r / p_i.
        if (m_algorithm == CMAB_EXP3M)
        {
            // Reconstruct p_i used at selection time (approximation; current weights).
            double sumW = 0.0;
            for (const auto& [a, st] : m_arms) sumW += st.weight;
            double p = (1.0 - m_exp3Gamma) * (arm.weight / std::max(sumW, 1e-12)) +
                       m_exp3Gamma / static_cast<double>(std::max<std::size_t>(1, m_arms.size()));
            double estR = reward / std::max(p, 1e-6);
            arm.weight *= std::exp(m_exp3Gamma * estR /
                                   static_cast<double>(std::max<std::size_t>(1, m_lastBasicTfAids.size())));
            // Cap weight to avoid overflow.
            arm.weight = std::min(arm.weight, 1e6);
        }
        m_timeStep++;
    }

    m_lastBasicTfAids.clear();
    m_preBasicTfBytes.clear();
}

} // namespace ns3
