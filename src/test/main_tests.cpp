// Copyright (c) 2014-2015 The Bitcoin Core developers
// Distributed under the MIT software license, see the accompanying
// Copyright (c) 2014-2024 The Dash Core developers
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#include "chainparams.h"
#include "validation.h"
#include "net.h"

#include "test/test_PEPEPOW.h"

#include <boost/signals2/signal.hpp>
#include <boost/test/unit_test.hpp>

BOOST_FIXTURE_TEST_SUITE(main_tests, TestingSetup)

static void TestBlockSubsidyHalvings(const Consensus::Params& consensusParams)
{
    // tested in PEPEPOW_tests.cpp
    //int maxHalvings = 64;
    //CAmount nInitialSubsidy = 50 * COIN;

    //CAmount nPreviousSubsidy = nInitialSubsidy * 2; // for height == 0
    //BOOST_CHECK_EQUAL(nPreviousSubsidy, nInitialSubsidy * 2);
    //for (int nHalvings = 0; nHalvings < maxHalvings; nHalvings++) {
    //    int nHeight = nHalvings * consensusParams.nSubsidyHalvingInterval;
    //    CAmount nSubsidy = GetBlockSubsidy(0, nHeight, consensusParams);
    //    BOOST_CHECK(nSubsidy <= nInitialSubsidy);
    //    BOOST_CHECK_EQUAL(nSubsidy, nPreviousSubsidy / 2);
    //    nPreviousSubsidy = nSubsidy;
    //}
    //BOOST_CHECK_EQUAL(GetBlockSubsidy(0, maxHalvings * consensusParams.nSubsidyHalvingInterval, consensusParams), 0);
}

static void TestBlockSubsidyHalvings(int nSubsidyHalvingInterval)
{
    // tested in PEPEPOW_tests.cpp
    //Consensus::Params consensusParams;
    //consensusParams.nSubsidyHalvingInterval = nSubsidyHalvingInterval;
    //TestBlockSubsidyHalvings(consensusParams);
}

BOOST_AUTO_TEST_CASE(block_subsidy_test)
{
    // tested in PEPEPOW_tests.cpp
    //TestBlockSubsidyHalvings(Params(CBaseChainParams::MAIN).GetConsensus()); // As in main
    //TestBlockSubsidyHalvings(150); // As in regtest
    //TestBlockSubsidyHalvings(1000); // Just another interval
}

BOOST_AUTO_TEST_CASE(subsidy_limit_test)
{
    // tested in PEPEPOW_tests.cpp
    //const Consensus::Params& consensusParams = Params(CBaseChainParams::MAIN).GetConsensus();
    //CAmount nSum = 0;
    //for (int nHeight = 0; nHeight < 14000000; nHeight += 1000) {
    //    /* @TODO fix subsidity, add nBits */
    //    CAmount nSubsidy = GetBlockSubsidy(0, nHeight, consensusParams);
    //    BOOST_CHECK(nSubsidy <= 25 * COIN);
    //    nSum += nSubsidy * 1000;
    //    BOOST_CHECK(MoneyRange(nSum));
    //}
    //BOOST_CHECK_EQUAL(nSum, 1350824726649000ULL);
}

bool ReturnFalse() { return false; }
bool ReturnTrue() { return true; }

BOOST_AUTO_TEST_CASE(test_combiner_all)
{
    boost::signals2::signal<bool (), CombinerAll> Test;
    BOOST_CHECK(Test());
    Test.connect(&ReturnFalse);
    BOOST_CHECK(!Test());
    Test.connect(&ReturnTrue);
    BOOST_CHECK(!Test());
    Test.disconnect(&ReturnFalse);
    BOOST_CHECK(Test());
    Test.disconnect(&ReturnTrue);
    BOOST_CHECK(Test());
}
BOOST_AUTO_TEST_SUITE_END()

namespace {
struct BlockIndexCandidateSetup
{
    CBlockIndex indexes[2];
    CBlockIndex& candidate;
    CBlockIndex& tip;

    BlockIndexCandidateSetup() : candidate(indexes[0]), tip(indexes[1])
    {
        candidate.pprev = &tip;
        candidate.nStatus = tip.nStatus = BLOCK_VALID_TRANSACTIONS;
        candidate.nChainTx = tip.nChainTx = 1;
        candidate.nChainWork = tip.nChainWork = arith_uint256(100);
    }
};
}

BOOST_FIXTURE_TEST_SUITE(blockindex_candidate_tests, BlockIndexCandidateSetup)

BOOST_AUTO_TEST_CASE(active_tip)
{
    BOOST_CHECK(IsBlockIndexCandidateForTip(&tip, &tip));
}

BOOST_AUTO_TEST_CASE(worse_historical_block)
{
    candidate.nChainWork = arith_uint256(99);
    BOOST_CHECK(!IsBlockIndexCandidateForTip(&candidate, &tip));
}

BOOST_AUTO_TEST_CASE(equal_work_tie_breaks)
{
    // Disk-loaded entries have sequence 0: the lower pointer sorts better.
    BOOST_CHECK(IsBlockIndexCandidateForTip(&candidate, &tip));
    BOOST_CHECK(!IsBlockIndexCandidateForTip(&tip, &candidate));
    candidate.nSequenceId = 2;
    tip.nSequenceId = 1;
    BOOST_CHECK(!IsBlockIndexCandidateForTip(&candidate, &tip));
    candidate.nSequenceId = 0;
    BOOST_CHECK(IsBlockIndexCandidateForTip(&candidate, &tip));
}

BOOST_AUTO_TEST_CASE(better_work_side_chain)
{
    candidate.nChainWork = arith_uint256(101);
    BOOST_CHECK(IsBlockIndexCandidateForTip(&candidate, &tip));
}

BOOST_AUTO_TEST_CASE(invalid_or_insufficiently_valid_block)
{
    candidate.nChainWork = arith_uint256(101);
    candidate.nStatus |= BLOCK_FAILED_VALID;
    BOOST_CHECK(!IsBlockIndexCandidateForTip(&candidate, &tip));
    candidate.nStatus = BLOCK_VALID_TRANSACTIONS | BLOCK_FAILED_CHILD;
    BOOST_CHECK(!IsBlockIndexCandidateForTip(&candidate, &tip));
    candidate.nStatus = BLOCK_VALID_TREE;
    BOOST_CHECK(!IsBlockIndexCandidateForTip(&candidate, &tip));
}

BOOST_AUTO_TEST_CASE(missing_chain_transaction_state)
{
    candidate.nChainWork = arith_uint256(101);
    candidate.nChainTx = 0;
    BOOST_CHECK(!IsBlockIndexCandidateForTip(&candidate, &tip));
}

BOOST_AUTO_TEST_CASE(missing_active_tip)
{
    candidate.nChainWork = arith_uint256(99);
    BOOST_CHECK(IsBlockIndexCandidateForTip(&candidate, NULL));
    candidate.nChainTx = 0;
    BOOST_CHECK(!IsBlockIndexCandidateForTip(&candidate, NULL));
}

BOOST_AUTO_TEST_CASE(genesis_transaction_state_exception)
{
    candidate.pprev = NULL;
    candidate.nChainTx = 0;
    BOOST_CHECK(IsBlockIndexCandidateForTip(&candidate, NULL));
}

BOOST_AUTO_TEST_CASE(pruned_data_does_not_change_eligibility)
{
    BOOST_CHECK(!(candidate.nStatus & BLOCK_HAVE_DATA));
    BOOST_CHECK(IsBlockIndexCandidateForTip(&candidate, &tip));
}

BOOST_AUTO_TEST_SUITE_END()
