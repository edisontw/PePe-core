// Build without the Core toolchain:
// g++ -std=c++11 -Wall -Wextra -Werror -pedantic \
//   contrib/devtools/tier_reward_priority_research_smoke.cpp -o /tmp/tier_reward_smoke
// /tmp/tier_reward_smoke
#include "../../src/tier_reward_priority_research.h"
#include <cassert>
#include <climits>
#include <iostream>

int main()
{
    using namespace TierRewardResearch;

    assert(TierWeight(10000000) == 2);
    assert(TierWeight(25000000) == 5);
    assert(TierWeight(50000000) == 10);
    assert(TierWeight(100000000) == 20);
    assert(TierWeight(1) == 0);

    // Equivalent weighted wait: 10*2 == 4*5 == 2*10 == 1*20.
    assert(WeightedWaitPriority(200, 190, 10000000) == 20);
    assert(WeightedWaitPriority(200, 196, 25000000) == 20);
    assert(WeightedWaitPriority(200, 198, 50000000) == 20);
    assert(WeightedWaitPriority(200, 199, 100000000) == 20);

    // Guard invalid heights/collateral, and keep 64-bit multiplication.
    assert(WeightedWaitPriority(200, 201, 100000000) == 0);
    assert(WeightedWaitPriority(-1, 0, 100000000) == 0);
    assert(WeightedWaitPriority(200, 0, 123) == 0);
    assert(WeightedWaitPriority(INT_MAX, 0, 100000000) == 20LL * INT_MAX);

    std::cout << "PASS: TierRewardResearch weighted wait priority smoke test\n";
}
