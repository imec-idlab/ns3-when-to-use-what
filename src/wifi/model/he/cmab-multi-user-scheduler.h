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

#ifndef CMAB_MULTI_USER_SCHEDULER_H
#define CMAB_MULTI_USER_SCHEDULER_H

#include "multi-user-scheduler.h"

#include "ns3/random-variable-stream.h"

#include <list>
#include <map>
#include <vector>

namespace ns3
{

/**
 * \ingroup wifi
 *
 * CmabMultiUserScheduler is an OFDMA scheduler that selects the set of stations
 * to solicit in a Basic Trigger Frame via a Combinatorial Multi-Armed Bandit
 * policy. Each STA in m_staListUl is one arm. Every Basic TF picks K arms
 * (where K is determined by the RU layout the same way UORA/RR pick it).
 * The reward for arm i is observed via the change in the STA's BSR between the
 * Basic TF transmission and the next channel access, and updates the bandit
 * state via the selected algorithm:
 *   - CUCB             (Combinatorial UCB1)
 *   - ThompsonSampling (combinatorial; Beta posterior for binary, Gaussian for continuous)
 *   - EpsilonGreedy    (with prob epsilon: random K; else top-K by empirical mean)
 *   - EXP3M            (combinatorial EXP3 with weighted sampling without replacement)
 *
 * BSRP TF and DL MU PPDU selection remain identical to the RR scheduler.
 */
class CmabMultiUserScheduler : public MultiUserScheduler
{
  public:
    /// CMAB algorithm choice. Plain enum (not enum class) for ns-3 EnumValue compatibility.
    enum Algorithm
    {
        CMAB_CUCB,
        CMAB_ThompsonSampling,
        CMAB_EpsilonGreedy,
        CMAB_EXP3M
    };

    /// Reward signal the bandit observes per arm per Basic TF.
    enum RewardType
    {
        /// 1 if the STA sent any bytes (BSR dropped); 0 otherwise.
        REWARD_Binary,
        /// (bytes_sent / max_bytes_per_txop) / (1 + n_i / N): in [0,1], penalises over-served STAs.
        REWARD_FairnessWeighted
    };

    /**
     * \brief Get the type ID.
     * \return the object TypeId
     */
    static TypeId GetTypeId();
    CmabMultiUserScheduler();
    ~CmabMultiUserScheduler() override;

    /**
     * Reward hook: called by HeFrameExchangeManager when a polled STA's QoS Null
     * (BSRP response) is decoded. \p reportedQueueSize is the raw BSR octet
     * from the QoS Control field (0--254 = buffer in 256-byte units; 254 =
     * unlimited; 255 = unknown). No-op if the sender isn't a tracked arm.
     */
    void NotifyBsrpResponse(Mac48Address senderAddr, uint8_t reportedQueueSize);

    /**
     * Reward hook: called by HeFrameExchangeManager::TbPpduTimeout for each
     * polled STA that did *not* return a QoS Null before the BSRP timeout.
     * Applies a zero reward (same arm-state update as NotifyBsrpResponse with
     * reportedQueueSize=0) so the bandit can learn to deprioritise silent arms.
     */
    void NotifyBsrpNoResponse(Mac48Address senderAddr);

  protected:
    void DoDispose() override;
    void DoInitialize() override;

  private:
    TxFormat SelectTxFormat() override;
    DlMuInfo ComputeDlMuInfo() override;
    UlMuInfo ComputeUlMuInfo() override;

    virtual TxFormat TrySendingBsrpTf();
    virtual TxFormat TrySendingBasicTf();
    virtual TxFormat TrySendingDlMuPpdu();

    template <class Func>
    WifiTxVector GetTxVectorForUlMu(Func canBeSolicited,
                                    bool isBasicTrigger,
                                    const std::vector<uint16_t>& cmabSelectedAids = {});

    void NotifyStationAssociated(uint16_t aid, Mac48Address address);
    void NotifyStationDeassociated(uint16_t aid, Mac48Address address);

    /// Information used to sort stations (mirrors RR/UORA schedulers).
    struct MasterInfo
    {
        uint16_t aid;
        Mac48Address address;
        double credits;
    };

    enum class UlIdleState
    {
        SEND_BSRP,
        SEND_BASIC,
        SEND_DLMU
    };

    void FinalizeTxVector(WifiTxVector& txVector, bool isBasicTrigger, HeRu::RuType ruAllocType);
    void UpdateCredits(std::list<MasterInfo>& staList,
                       Time txDuration,
                       const WifiTxVector& txVector);

    typedef std::pair<std::list<MasterInfo>::iterator, Ptr<WifiMpdu>> CandidateInfo;

    // ====================== CMAB =====================================

    /// Bandit state for one arm (one STA).
    struct ArmState
    {
        uint64_t pulls = 0;        ///< number of pulls so far
        double rewardSum = 0.0;    ///< cumulative reward
        double alpha = 1.0;        ///< Beta(α,β) posterior for binary Thompson Sampling
        double beta = 1.0;
        double tsMu = 0.0;         ///< Gaussian posterior mean (continuous TS)
        double tsTau = 0.0;        ///< Gaussian posterior precision (continuous TS); 0 = uninformative
        double weight = 1.0;       ///< EXP3.M weight

        double Mean() const { return pulls ? rewardSum / pulls : 0.0; }
    };

    std::vector<uint16_t> SelectArmsByCmab(std::size_t k);

    std::pair<std::size_t, std::size_t> ComputeRuLayout() const;

    /**
     * Priority rank of the highest-priority Access Category for which the given
     * STA currently has buffered UL data (VO=3 > VI=2 > BE=1 > BK=0; -1 if none),
     * read from the AP's per-TID BSR cache.
     */
    int StaHighestAcWithData(Mac48Address address) const;

    /**
     * Reward multiplier in (0,1] for the given STA based on its highest AC with
     * buffered data: VO=1.0, VI=0.75, BE=0.5, BK=0.25. Returns 1.0 when
     * AcAwareReward is disabled or the AC is unknown (neutral).
     */
    double AcRewardWeight(Mac48Address address) const;

    /// UCB1 score for the given arm (uses m_timeStep as global t).
    double UcbScore(const ArmState& arm) const;

    void UpdateBanditRewards();


    // CMAB attributes
    Algorithm m_algorithm;
    RewardType m_rewardType;
    double m_ucbConstant;      ///< exploration constant for CUCB (default sqrt(2))
    double m_epsilon;          ///< probability of random selection for EpsilonGreedy
    double m_exp3Gamma;        ///< exploration mixing parameter for EXP3.M (in (0,1])
    bool m_acAwareReward;      ///< scale arm reward by the STA's highest-AC-with-data weight
    Time m_learningStartTime;  ///< arm statistics only accumulate from this time on

    // CMAB state
    std::map<uint16_t, ArmState> m_arms;        ///< per-AID arm state
    uint64_t m_timeStep = 0;                    ///< global pull counter
    Ptr<UniformRandomVariable> m_rngU;          ///< uniform RNG (ε-greedy / EXP3.M sampling)
    Ptr<NormalRandomVariable> m_rngN;           ///< normal RNG (unused after Beta-sampling fix; kept for API compat)
    Ptr<GammaRandomVariable> m_rngG;            ///< gamma RNG for true Beta sampling in TS

    std::map<uint16_t, double> m_lastSelectionP;

    // Per-TXOP reward observation
    std::vector<uint16_t> m_lastBasicTfAids;    ///< AIDs selected in last Basic TF (in order)
    std::map<uint16_t, uint32_t> m_preBasicTfBytes; ///< per-AID buffered bytes snapshot pre-TF
    bool m_rewardPending = false;               ///< true while waiting to observe rewards
    uint64_t m_maxBytesPerTxop = 1500 * 64;     ///< approximate max bytes one STA can send per TXOP (normaliser)

    // ====================== Inherited UORA/RR-like state ============

    uint8_t m_nStations;
    bool m_enableTxopSharing;
    bool m_forceDlOfdma;
    bool m_downlinkAware;        //!< SelectTxFormat: serve DL-MU whenever DL backlog exists (DL-first)
    bool m_dlFirstAcrossAcs;     //!< build the DL-MU for the highest-priority DL AC with backlog
    bool m_dlBeforeUl;           //!< skip the UL trigger cycle when another DL AC has backlog
    AcIndex m_dlPrimaryAc{AC_BE};         //!< AC the current DL-MU candidates were drawn from
    bool m_enableUlOfdma;
    bool m_enableBsrp;
    bool m_useCentral26TonesRus;
    uint32_t m_ulPsduSize;
    std::map<AcIndex, std::list<MasterInfo>> m_staListDl;
    std::list<MasterInfo> m_staListUl;
    std::list<CandidateInfo> m_candidates;
    Time m_maxCredits;
    CtrlTriggerHeader m_trigger;
    WifiMacHeader m_triggerMacHdr;
    WifiTxParameters m_txParams;
    HeRu::RuType m_ruAllocationType;
    HeRu::RuType m_dlRuAllocationType; //!< DL-only RU type; overrides m_ruAllocationType for downlink (RU_UNDEFINED = use m_ruAllocationType)
    UlIdleState m_ulIdleState = UlIdleState::SEND_BSRP;
};

} // namespace ns3

#endif /* CMAB_MULTI_USER_SCHEDULER_H */
