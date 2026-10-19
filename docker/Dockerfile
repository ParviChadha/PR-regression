# Shared toolchain base (generic, no target specifics). Image name: prh-base
# Ubuntu 24.04 LTS arm64, pinned by digest (index digest; resolved to arm64 on pull).
FROM ubuntu:24.04@sha256:68ee22004a9109b44973313b02ff7b1de250f1de0f5ecb628d73f579aaff33ac

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git unzip xz-utils python3 \
      build-essential gcc-14 g++-14 rsync \
      cmake ninja-build make ccache gcovr lcov \
      clang-18 clangd-18 clang-tidy-18 clang-tools-18 \
    && update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-14 100 \
    && update-alternatives --install /usr/bin/g++ g++ /usr/bin/g++-14 100 \
    && update-alternatives --install /usr/bin/gcov gcov /usr/bin/gcov-14 100 \
    && update-alternatives --install /usr/bin/clangd clangd /usr/bin/clangd-18 100 \
    && update-alternatives --install /usr/bin/clang-tidy clang-tidy /usr/bin/clang-tidy-18 100 \
    && update-alternatives --install /usr/bin/clang clang /usr/bin/clang-18 100 \
    && update-alternatives --install /usr/bin/clang++ clang++ /usr/bin/clang++-18 100 \
    && rm -rf /var/lib/apt/lists/*

ENV CC=gcc CXX=g++ CMAKE_GENERATOR=Ninja CCACHE_DIR=/ccache \
    CMAKE_C_COMPILER_LAUNCHER=ccache CMAKE_CXX_COMPILER_LAUNCHER=ccache
# Tools may run as root inside the container; the source tree is mounted read-only.
# Mounted source trees are owned by another uid inside the container; allow git to read them.
RUN git config --system --add safe.directory '*'
WORKDIR /build
