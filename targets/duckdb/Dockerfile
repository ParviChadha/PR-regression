# Target layer for duckdb: nothing beyond the shared toolchain (prh-base has GCC 14, CMake, Ninja, ccache, rsync, python3, git).
# The base image sets CMAKE_GENERATOR=Ninja and ccache as compiler launcher. duckdb needs no test data and no vendored git repos.
FROM prh-base
