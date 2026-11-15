// Research-only pure priority helper; not wired into mainnet payment selection.
// Activation of a new selection rule requires separate consensus review.
#ifndef PEPEPOW_TIER_REWARD_PRIORITY_RESEARCH_H
#define PEPEPOW_TIER_REWARD_PRIORITY_RESEARCH_H

#include <stdint.h>

namespace TierRewardResearch {

// Input is PEPEW (whole coins), not satoshis/atoms.
inline int TierWeight(int64_t collateral_pepew)
{
    switch (collateral_pepew) {
    case 10000000:  return 2;
    case 25000000:  return 5;
    case 50000000:  return 10;
    case 100000000: return 20;
    default:        return 0;
    }
}

// Integer arithmetic: 10M : 25M : 50M : 100M = 2 : 5 : 10 : 20.
// Larger priority means longer weighted wait, hence higher selection priority.
// Deterministic tie-breaking must be specified before consensus integration.
inline int64_t WeightedWaitPriority(int n_block_height,
                                   int n_last_paid_block,
                                   int64_t collateral_pepew)
{
    const int weight = TierWeight(collateral_pepew);
    if (weight == 0 || n_block_height < 0 || n_last_paid_block < 0
        || n_last_paid_block > n_block_height) {
        return 0;
    }
    return (static_cast<int64_t>(n_block_height) -
            static_cast<int64_t>(n_last_paid_block)) * weight;
}

} // namespace TierRewardResearch

#endif // PEPEPOW_TIER_REWARD_PRIORITY_RESEARCH_H
