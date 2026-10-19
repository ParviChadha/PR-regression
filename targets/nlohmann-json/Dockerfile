# Target layer for nlohmann/json: base toolchain + vendored test data.
# Build with scripts/image.sh nlohmann-json (passes the build args from target.toml).
FROM prh-base
ARG TEST_DATA_URL
ARG TEST_DATA_SHA256
ARG TEST_DATA_DIR
RUN set -eux; \
    curl -fsSL -o /tmp/td.tgz "$TEST_DATA_URL"; \
    echo "$TEST_DATA_SHA256  /tmp/td.tgz" | sha256sum -c -; \
    mkdir -p "$TEST_DATA_DIR"; \
    tar -xzf /tmp/td.tgz -C "$TEST_DATA_DIR" --strip-components=1; \
    rm /tmp/td.tgz
