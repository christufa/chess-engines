#!/bin/sh
# Build the pinned Lc0 release from source for CPU (the Eigen BLAS backend) and install it.
# Used by docker/Dockerfile and by CI (tests against the real engine). Lc0 publishes no
# Linux binaries, hence the build. Usage: build.sh <install dir>
#
# Needs a C++ compiler, meson, ninja, python3 and zlib headers (Debian: g++ meson
# ninja-build python3 zlib1g-dev). Meson fetches Eigen and Abseil from Lc0's pinned wraps,
# which check their own checksums. The binary needs only libstdc++ and zlib at run time,
# both in the python:slim base.
#
# Built for x86-64-v3 (AVX2, FMA): the AKS VMs and GitHub's runners all have it, and Eigen
# vectorises with it.
# Bumping: change VERSION, SHA256, COMMON (the libs/lczero-common submodule commit at that
# tag) and COMMON_SHA256 together, and engines/engines.yaml's lc0 version.
set -eu
VERSION=v0.32.1
SHA256=78b17e8e8d29da30492c86fdac69c519816f4a9d9c3b787dc41a6f9e8d20fde3
COMMON=b326b154221a6eb91977bdccf11d6f89e8547875
COMMON_SHA256=d12ec2257c0412a8962c0c439170ce98c6001ab6be6a6444a849d0115bfb330a

dest=${1:?usage: build.sh <install dir>}
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
curl -fsSL --retry 3 -o "$tmp/lc0.tar.gz" \
  "https://github.com/LeelaChessZero/lc0/archive/refs/tags/$VERSION.tar.gz"
curl -fsSL --retry 3 -o "$tmp/common.tar.gz" \
  "https://github.com/LeelaChessZero/lczero-common/archive/$COMMON.tar.gz"
echo "$SHA256  $tmp/lc0.tar.gz" | sha256sum -c -
echo "$COMMON_SHA256  $tmp/common.tar.gz" | sha256sum -c -

mkdir "$tmp/src"
tar -xzf "$tmp/lc0.tar.gz" -C "$tmp/src" --strip-components=1
mkdir -p "$tmp/src/libs/lczero-common"
tar -xzf "$tmp/common.tar.gz" -C "$tmp/src/libs/lczero-common" --strip-components=1

# Only the CPU backend: no GPU toolkits, no OpenBLAS or DNNL (Eigen is header-only, so
# the binary needs nothing extra at run time), no tests.
cd "$tmp/src"
meson setup build --buildtype=release -Dnative_arch=false -Dgtest=false \
  -Dblas=true -Dopenblas=false -Dmkl=false -Ddnnl=false -Donednn=false -Daccelerate=false \
  -Dispc=false -Dcudnn=false -Dplain_cuda=false -Dopencl=false -Donnx=false -Dxla=false \
  -Dtensorflow=false -Dpython_bindings=false -Drescorer=false \
  -Dcpp_args=-march=x86-64-v3 -Dc_args=-march=x86-64-v3
ninja -C build lc0

mkdir -p "$dest"
install -m 0755 build/lc0 "$dest/lc0"
# GPL-3: ship the licence with the binary (the source is the release tag above).
install -m 0644 COPYING "$dest/COPYING"
echo "$VERSION https://github.com/LeelaChessZero/lc0/tree/$VERSION" > "$dest/SOURCE"
