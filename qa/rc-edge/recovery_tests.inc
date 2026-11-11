// Included only in the instrumented test binary, never production sources.
#include "masternodeman.h"
#include "masternode-sync.h"
#include "streams.h"
#include "utiltime.h"

extern int edgeOrphanInsertions;
extern int edgeRecoveryReprocesses;

namespace {
using EdgeRequests = std::map<uint256, std::pair<int64_t, std::set<CNetAddr> > >;
using EdgeReplies = std::map<uint256, std::vector<CMasternodeBroadcast> >;
struct EdgeMaps { EdgeRequests requests; EdgeReplies replies; };

// Exercise the real public serialization format rather than exposing private maps.
static void EdgeLoad(CMasternodeMan& manager, const EdgeMaps& data)
{
    CDataStream stream(SER_DISK, CLIENT_VERSION);
    std::map<COutPoint, CMasternode> nodes;
    std::map<CNetAddr, int64_t> asked, weAsked;
    std::map<COutPoint, std::map<CNetAddr, int64_t> > entries;
    int64_t watchdog = 0, dsq = 0;
    std::map<uint256, std::pair<int64_t, CMasternodeBroadcast> > seen;
    std::map<uint256, CMasternodePing> pings;
    stream << std::string("CMasternodeMan-Version-7") << nodes << asked << weAsked << entries
           << data.requests << data.replies << watchdog << dsq << seen << pings;
    stream >> manager;
}
static EdgeMaps EdgeSnapshot(CMasternodeMan& manager)
{
    CDataStream stream(SER_DISK, CLIENT_VERSION);
    stream << manager;
    std::string version;
    std::map<COutPoint, CMasternode> nodes;
    std::map<CNetAddr, int64_t> asked, weAsked;
    std::map<COutPoint, std::map<CNetAddr, int64_t> > entries;
    EdgeMaps data;
    stream >> version >> nodes >> asked >> weAsked >> entries >> data.requests >> data.replies;
    return data;
}
struct EdgeRecoverySetup : TestChain100Setup {
    EdgeRecoverySetup() {
        masternodeSync.Reset();
        masternodeSync.SwitchToNextAsset(*connman);
        masternodeSync.SwitchToNextAsset(*connman);
        masternodeSync.SwitchToNextAsset(*connman);
        BOOST_REQUIRE(masternodeSync.IsMasternodeListSynced());
    }
    ~EdgeRecoverySetup() { masternodeSync.Reset(); }
};
static CMasternodeBroadcast EdgeSignedReply(bool stale)
{
    CKey collateral, masternode;
    collateral.MakeNewKey(true);
    masternode.MakeNewKey(true);
    const COutPoint outpoint(uint256S("01"), 0);
    CMasternodeBroadcast reply(CService(), outpoint, collateral.GetPubKey(),
                               masternode.GetPubKey(), PROTOCOL_VERSION);
    reply.lastPing.vin = CTxIn(outpoint);
    {
        LOCK(cs_main);
        reply.lastPing.blockHash = chainActive[chainActive.Height() - (stale ? 25 : 1)]->GetBlockHash();
    }
    BOOST_REQUIRE(reply.lastPing.Sign(masternode, masternode.GetPubKey()));
    BOOST_REQUIRE(reply.Sign(collateral));
    return reply;
}
}

BOOST_FIXTURE_TEST_CASE(rc_recovery_request_reply_invariants, EdgeRecoverySetup)
{
    const uint256 hash = uint256S("1234");
    const int64_t now = GetTime();
    const CMasternodeBroadcast valid = EdgeSignedReply(false);
    const CMasternodeBroadcast stale = EdgeSignedReply(true);
    auto run = [&](const EdgeMaps& input) {
        CMasternodeMan manager;
        EdgeLoad(manager, input);
        edgeOrphanInsertions = edgeRecoveryReprocesses = 0;
        manager.CheckAndRemove(*connman);
        return EdgeSnapshot(manager);
    };
    EdgeMaps in, out;
    in.requests[hash].first = now + 60;
    in.replies[hash] = std::vector<CMasternodeBroadcast>(6, valid);
    out = run(in);
    BOOST_CHECK_EQUAL(out.requests.size(), 1U);
    BOOST_CHECK_EQUAL(out.replies.size(), 1U);
    BOOST_CHECK_EQUAL(edgeRecoveryReprocesses, 0);
    BOOST_TEST_MESSAGE("future request: retained without reprocessing");

    in.requests[hash].first = now - 1;
    in.replies[hash] = std::vector<CMasternodeBroadcast>(5, valid);
    out = run(in);
    BOOST_CHECK_EQUAL(out.requests.size(), 1U);
    BOOST_CHECK(out.replies.empty());
    BOOST_CHECK_EQUAL(edgeRecoveryReprocesses, 0);
    BOOST_TEST_MESSAGE("expired request with five replies: no quorum");

    in.replies[hash] = std::vector<CMasternodeBroadcast>(6, stale);
    out = run(in);
    BOOST_CHECK(out.replies.empty());
    BOOST_CHECK_EQUAL(edgeRecoveryReprocesses, 0);
    BOOST_TEST_MESSAGE("six signed stale pings: no reprocessing");

    in.replies[hash] = std::vector<CMasternodeBroadcast>(6, valid);
    out = run(in);
    BOOST_CHECK(out.replies.empty());
    BOOST_CHECK_EQUAL(edgeRecoveryReprocesses, 1);
    BOOST_TEST_MESSAGE("six signed fresh replies: reached recovery reprocessing");

    in.requests.clear();
    out = run(in);
    BOOST_CHECK(out.requests.empty());
    BOOST_CHECK(out.replies.empty());
    BOOST_CHECK_EQUAL(edgeOrphanInsertions, 0);
    BOOST_CHECK_EQUAL(edgeRecoveryReprocesses, 0);
    BOOST_TEST_MESSAGE("orphan replies: no inserted request or reprocessing");

    in.requests[hash].first = now - 10801;
    in.replies[hash] = std::vector<CMasternodeBroadcast>(1, valid);
    out = run(in);
    BOOST_CHECK(out.requests.empty());
    BOOST_CHECK(out.replies.empty());
    BOOST_CHECK_EQUAL(edgeRecoveryReprocesses, 0);
    BOOST_TEST_MESSAGE("retry-expired request: cleanup");
}
