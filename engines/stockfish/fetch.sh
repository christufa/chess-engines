#!/bin/sh
# Download the pinned Stockfish release and verify its checksum. Used by docker/Dockerfile
# and by CI (tests against the real engine). Usage: fetch.sh <install dir>
#
# The x86-64 "universal" build picks the best code path for the CPU at run time
# (AVX2 on the AKS spot VMs, AVX-512 where available), so one binary runs everywhere.
# Bumping: change VERSION, ASSET and SHA256 together (the release page lists the digest),
# and engines/engines.yaml's version.
set -eu
VERSION=sf_19
ASSET=stockfish-linux-x86-64-universal.tar.gz
SHA256=9defc0d4e55d49c65a6d042f3e571a39fcea499ade6dbe741b53b8c65e03611f

dest=${1:?usage: fetch.sh <install dir>}
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
curl -fsSL --retry 3 -o "$tmp/sf.tar.gz" \
  "https://github.com/official-stockfish/Stockfish/releases/download/$VERSION/$ASSET"
echo "$SHA256  $tmp/sf.tar.gz" | sha256sum -c -
mkdir -p "$dest"
tar -xzf "$tmp/sf.tar.gz" -C "$tmp"
install -m 0755 "$tmp/stockfish/stockfish-linux-x86-64-universal" "$dest/stockfish"
# GPL-3: ship the licence with the binary (the source is the release tag above).
install -m 0644 "$tmp/stockfish/Copying.txt" "$dest/COPYING"
echo "$VERSION https://github.com/official-stockfish/Stockfish/tree/$VERSION" > "$dest/SOURCE"
