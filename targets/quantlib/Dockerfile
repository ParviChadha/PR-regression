# Target layer for QuantLib: the shared toolchain plus Boost headers (QuantLib uses header-only parts of Boost;
# no compiled Boost libraries are needed with the test suite off). Image name: prh-quantlib
FROM prh-base
RUN apt-get update && apt-get install -y --no-install-recommends libboost-dev \
    && rm -rf /var/lib/apt/lists/*
