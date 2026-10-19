# Target layer for nlohmann/json: base toolchain + vendored test data.
# Build with scripts/image.sh nlohmann-json (passes the build args from target.toml).
FROM prh-base
ARG TEST_DATA_URL
ARG TEST_DATA_SHA256
ARG TEST_DATA_DIR
ARG VENDORED_GIT
RUN set -eux; \
    curl -fsSL -o /tmp/td.tgz "$TEST_DATA_URL"; \
    echo "$TEST_DATA_SHA256  /tmp/td.tgz" | sha256sum -c -; \
    mkdir -p "$TEST_DATA_DIR"; \
    tar -xzf /tmp/td.tgz -C "$TEST_DATA_DIR" --strip-components=1; \
    rm /tmp/td.tgz

# Mirror git deps that tests would otherwise clone from the network; verify the pinned commit.
RUN set -eux; \
    for e in $VENDORED_GIT; do \
      url="${e%%@*}"; rest="${e#*@}"; tag="${rest%%@*}"; sha="${rest#*@}"; \
      dir="/opt/vendor/$(echo "${url#https://}" | tr '/:' '__')"; \
      git clone --mirror "$url" "$dir"; \
      test "$(git -C "$dir" rev-parse "$tag^{commit}")" = "$sha"; \
      git config --system "url.file://$dir.insteadOf" "$url"; \
    done
