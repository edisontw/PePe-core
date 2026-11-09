#!/bin/bash
set -euo pipefail
# /source is a clean git archive; /output is writable by the caller.
mkdir -p /tmp/pepe-source /tmp/pepe-build /output
cp -a /source/. /tmp/pepe-source/
cd /tmp/pepe-source
./autogen.sh
cd /tmp/pepe-build
/tmp/pepe-source/configure --with-gui=qt5 --without-miniupnpc --disable-tests --disable-bench --disable-zmq CPPFLAGS=-I/opt/db4/include LDFLAGS=-L/opt/db4/lib CXXFLAGS='-O2 -g0'
make -C src -j4 qt/PEPEPOW_qt PEPEPOWd PEPEPOW-cli CXXFLAGS='-O2 -g0 -include deque -include condition_variable'
exec /source/contrib/linux-portable/package.sh /tmp/pepe-source /tmp/pepe-build /output
