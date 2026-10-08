// Diagnostic-only Windows LevelDB block-index filesystem I/O counters.
// This interface reports cumulative process counters; callers take deltas.
// No database format or file I/O behavior is modified.
#ifndef LEVELDB_UTIL_WIN_IO_STATS_H_
#define LEVELDB_UTIL_WIN_IO_STATS_H_

#include <stdint.h>

namespace leveldb {

struct WinIOStats {
    bool enabled;
    uint64_t random_calls;
    uint64_t random_request_bytes;
    uint64_t random_read_bytes;
    uint64_t random_read_us;
    uint64_t random_failures;
    uint64_t sequential_calls;
    uint64_t sequential_request_bytes;
    uint64_t sequential_read_bytes;
    uint64_t sequential_read_us;
    uint64_t sequential_failures;
    uint64_t random_open_attempts;
    uint64_t random_open_successes;
    uint64_t random_open_us;
    uint64_t sst_open_attempts;
    uint64_t sst_open_successes;
    uint64_t sst_open_us;
};

// Windows only. Instrumentation is disabled unless the process environment
// contains PEPEPOW_LEVELDB_IO_PROFILE=1 before LevelDB is first used.
void GetWinIOStats(WinIOStats* result);

} // namespace leveldb

#endif // LEVELDB_UTIL_WIN_IO_STATS_H_
