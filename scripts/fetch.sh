#!/usr/bin/env bash
# Clone (full history, HTTPS) and check out the pinned SHA, or the SHA given as 2nd arg.
# Usage: scripts/fetch.sh <target> [sha]
. "$(dirname "$0")/lib/common.sh"; use_target "${1:-}"
SHA="${2:-$(cfg pinned_sha)}"
[ -d "$REPO/.git" ] || git clone "$(cfg upstream_url)" "$REPO"
git -C "$REPO" cat-file -e "$SHA^{commit}" 2>/dev/null || git -C "$REPO" fetch origin
git -C "$REPO" checkout --detach "$SHA"
git -C "$REPO" rev-parse HEAD
