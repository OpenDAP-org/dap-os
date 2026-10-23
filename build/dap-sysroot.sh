#!/bin/sh
# Build the cross-compilation sysroot and install it on the host.
# Usage: build/dap-sysroot.sh            build (in the build VM) and install
#        build/dap-sysroot.sh --no-build install the last built sysroot
#        build/dap-sysroot.sh --path     print the sysroot path
#
# The sysroot is the image's own Debian packages plus their -dev packages (profile `sysroot`).
# macOS volumes are case-insensitive, and Linux headers are not (ipt_ecn.h and ipt_ECN.h), so the
# sysroot lives in a case-sensitive APFS sparse image, mounted at $OPENDAP_SYSROOT.
set -eu
here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/.." && pwd)"
cache="${XDG_CACHE_HOME:-$HOME/.cache}/opendap"
mnt="${OPENDAP_SYSROOT:-$cache/sysroot}"
img="$cache/sysroot.sparseimage"

if [ "${1:-}" = --path ]; then echo "$mnt/trixie-arm64"; exit 0; fi

[ "${1:-}" = --no-build ] || "$here/dap-image.sh" sysroot

mkdir -p "$cache" "$mnt"
if [ "$(uname)" = Darwin ]; then
  [ -f "$img" ] || hdiutil create -quiet -size 8g -type SPARSE -fs "Case-sensitive APFS" -volname opendap-sysroot "$img"
  mount | grep -q " on $mnt " || hdiutil attach -quiet -nobrowse -mountpoint "$mnt" "$img"
  mdutil -i off "$mnt" >/dev/null 2>&1 || true
fi

dest="$mnt/trixie-arm64"
rm -rf "$dest.new"
mkdir -p "$dest.new"
# Device nodes and ownership are not needed to link; extract as the current user.
out="$repo/image/mkosi.output"
tar -xf "$out/blackbird-os-sysroot.tar.zst" -C "$dest.new" --exclude './dev/*'
rm -rf "$dest"
mv "$dest.new" "$dest"
cp "$out/blackbird-os-sysroot.manifest" "$dest.manifest"
rm -f "$out/blackbird-os-sysroot" "$out/blackbird-os-sysroot.tar.zst" "$out/blackbird-os-sysroot.manifest"
echo "$dest"
