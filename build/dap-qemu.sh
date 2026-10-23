#!/bin/sh
# Run the virtual T1 (Blackbird OS qemu image) on the host with QEMU, headless.
# Usage: build/dap-qemu.sh start|stop|ssh [command…]|console
#   start    boot in the background. Virtual T1 hardware: 4 GB RAM, 32 GB disk, 320x480 portrait display (virtio-gpu),
#            touch screen (virtio-multitouch), the four buttons (virtio-keyboard), audio out (virtio-sound).
#            SSH:  127.0.0.1:${DAP_SSH_PORT:-2222}      remote desktop: VNC on 127.0.0.1:${DAP_VNC_DISPLAY:-0} (port 5900+N)
#            QMP:  build/run/qmp.sock (driven by build/dap-qmp.py: screenshot, press, tap)
#            Console log: build/run/console.log
set -eu
here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/.." && pwd)"
run="$here/run"; port="${DAP_SSH_PORT:-2222}"; vnc="${DAP_VNC_DISPLAY:-0}"
image="$repo/image/mkosi.output/blackbird-os-qemu.raw"
disk="$run/disk.qcow2"   # 32 GB like the T1, backed by the built image
key="$here/dev-ssh/id_ed25519"
fw_code="$(brew --prefix qemu 2>/dev/null)/share/qemu/edk2-aarch64-code.fd"
case "$(uname -s)" in Darwin) accel=hvf; audio=coreaudio;; *) accel=kvm; audio=pa;; esac

case "${1:-start}" in
  start)
    mkdir -p "$run"
    # Fresh 32 GB disk on top of the latest image (the image itself stays untouched).
    if [ ! -f "$disk" ] || [ "$image" -nt "$disk" ]; then
      rm -f "$disk"; qemu-img create -q -f qcow2 -F raw -b "$image" "$disk" 32G
    fi
    [ -f "$run/vars.fd" ] || dd if=/dev/zero of="$run/vars.fd" bs=1m count=64 2>/dev/null
    # Not -daemonize: on macOS it forks after CoreAudio initializes and crashes.
    nohup qemu-system-aarch64 -machine virt -accel "$accel" -cpu host -smp 4 -m 4096 \
      -drive if=pflash,format=raw,readonly=on,file="$fw_code" \
      -drive if=pflash,format=raw,file="$run/vars.fd" \
      -drive if=virtio,format=qcow2,file="$disk" \
      -netdev user,id=net0,hostfwd=tcp:127.0.0.1:"$port"-:22 -device virtio-net-pci,netdev=net0 \
      -device virtio-gpu-pci \
      -device virtio-multitouch-pci -device virtio-keyboard-pci \
      -audiodev "$audio",id=snd0 -device virtio-sound-pci,audiodev=snd0,streams=1 \
      -display vnc=127.0.0.1:"$vnc" -qmp unix:"$run/qmp.sock",server=on,wait=off \
      -serial file:"$run/console.log" \
      >"$run/qemu.log" 2>&1 &
    echo $! > "$run/qemu.pid"; sleep 1
    kill -0 "$(cat "$run/qemu.pid")" 2>/dev/null || { cat "$run/qemu.log" >&2; exit 1; }
    echo "started (pid $(cat "$run/qemu.pid")); console: $run/console.log; ssh: $0 ssh";;
  stop)
    [ -f "$run/qemu.pid" ] && kill "$(cat "$run/qemu.pid")" 2>/dev/null && rm -f "$run/qemu.pid"; echo stopped;;
  ssh)
    shift
    exec ssh -i "$key" -p "$port" -o ConnectTimeout=5 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR root@127.0.0.1 -- "$@";;  # `--`: nothing after the host is read as an ssh option
  console)
    exec tail -f "$run/console.log";;
  *) echo "usage: $0 start|stop|ssh [command…]|console" >&2; exit 2;;
esac
