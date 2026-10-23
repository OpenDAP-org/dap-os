#!/bin/sh
# Create the local development SSH key and the tree that puts it in qemu images (never in device images).
# Used by dap-image.sh; a derivative built on this checkout runs it once before building its qemu profile.
set -eu
here="$(cd "$(dirname "$0")" && pwd)"
key="$here/dev-ssh/id_ed25519"
if [ ! -f "$key" ]; then
  mkdir -p "$here/dev-ssh"
  ssh-keygen -q -t ed25519 -N "" -C "blackbird-os development" -f "$key"
fi
mkdir -p "$here/dev-ssh/tree/root/.ssh"
cp "$key.pub" "$here/dev-ssh/tree/root/.ssh/authorized_keys"
chmod 700 "$here/dev-ssh/tree/root/.ssh"; chmod 600 "$here/dev-ssh/tree/root/.ssh/authorized_keys"
