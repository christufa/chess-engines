#!/bin/sh
# Download the pinned Maia networks (CSSLab/maia-chess v1.0) and verify their checksums.
# Used by docker/Dockerfile and by CI (tests against the real nets). Usage: fetch.sh <dir>
#
# Maia is a set of Lc0 networks trained on Lichess games by players of one rating band
# each (1100 to 1900), to predict the move a human at that level would play. They run on
# Lc0 (engines/lc0/build.sh) at one node. Bumping: change VERSION and the checksums
# together, and engines/engines.yaml's maia versions.
set -eu
VERSION=v1.0
NETS="
1100 e1cf1cd0c96b8a4fa6a275f4b9fd54ed1ffebf9fe44641b9fceded310e9619c4
1200 ead4ba953f233ae732999ebc1e2b675378148527ebcfad2f0acbc5e4c224d98e
1300 36195f87bf4761834baa0bf87472b18509a7261a9d7d6f1a8443261369a733f2
1400 d5353ea6766356dad2d28920c6692f37a5f30963767f1a3105d33b4d0af011e8
1500 35ab6f20421d59e1df3b17c5a5016947af4c6761368ef84044a9a9c7619a9a00
1600 d2c9e5948581acf4b9fc0b1e720c5dc0fe64ce80cfc4a239d3f8a42e1176c876
1700 d277eacd792d340a30abb464dc65127254e65cac57abca17facc469889b96478
1800 0031ad7c4256b1fd09fbebd28418d644d68b26cd2a45df4967ccf5c7ec9c4965
1900 e2f565f42d7cd9f122557e6dc4eb84e5bbaedceda1d404dc485d3611c7c97a12
"
LICENSE_SHA256=3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986

dest=${1:?usage: fetch.sh <dir>}
mkdir -p "$dest"
echo "$NETS" | while read -r level sha256; do
  [ -n "$level" ] || continue
  curl -fsSL --retry 3 -o "$dest/maia-$level.pb.gz" \
    "https://github.com/CSSLab/maia-chess/releases/download/$VERSION/maia-$level.pb.gz"
  echo "$sha256  $dest/maia-$level.pb.gz" | sha256sum -c -
done
# GPL-3: the networks' licence and source go with them.
curl -fsSL --retry 3 -o "$dest/COPYING" \
  "https://raw.githubusercontent.com/CSSLab/maia-chess/$VERSION/LICENSE"
echo "$LICENSE_SHA256  $dest/COPYING" | sha256sum -c -
echo "$VERSION https://github.com/CSSLab/maia-chess/releases/tag/$VERSION" > "$dest/SOURCE"
