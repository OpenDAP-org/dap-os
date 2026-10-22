#!/bin/sh
# Build a OpenDAP OS image inside the Debian build VM.
# Usage: build/dap-image.sh [profile]   (default: qemu)
set -eu
profile="${1:-qemu}"
here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/.." && pwd)"

if [ "$profile" = qemu ]; then
  # Local development key for SSH into virtual instances. Never used for device images.
  key="$here/dev-ssh/id_ed25519"
  if [ ! -f "$key" ]; then
    mkdir -p "$here/dev-ssh"
    ssh-keygen -q -t ed25519 -N "" -C "opendap-os development" -f "$key"
  fi
  mkdir -p "$here/dev-ssh/tree/root/.ssh"
  cp "$key.pub" "$here/dev-ssh/tree/root/.ssh/authorized_keys"
  chmod 700 "$here/dev-ssh/tree/root/.ssh"; chmod 600 "$here/dev-ssh/tree/root/.ssh/authorized_keys"
fi

# Create the build VM on first use; start it if it exists but is stopped.
if ! limactl list -q 2>/dev/null | grep -qx opendap-os-build; then
  limactl start --name=opendap-os-build --tty=false "$here/lima/opendap-os-build.yaml"
elif [ "$(limactl list --format '{{.Status}}' opendap-os-build)" != Running ]; then
  limactl start --tty=false opendap-os-build
fi
limactl shell opendap-os-build -- sudo mkosi -C "$repo/image" --profile="$profile" -f build
ls -lh "$repo/image/mkosi.output/"
