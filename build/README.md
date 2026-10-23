# Build and run

Everything runs locally (no CI).

| Script | What it does |
|---|---|
| `dap-image.sh [profile]` | Builds a Blackbird OS image with mkosi inside the Debian build VM (`lima/blackbird-os-build.yaml`, created on first use). Default profile: `qemu`. |
| `dap-sysroot.sh [--no-build\|--path]` | Builds the `sysroot` profile (the image's packages plus their `-dev` packages) and installs it on the host, in a case-sensitive APFS sparse image under `~/.cache/opendap/`, for cross-builds (`system/scripts/cross.sh`). |
| `dap-qemu.sh start\|stop\|ssh\|console` | Runs the **virtual T1** on the host with QEMU (HVF on macOS, KVM on Linux): 4 GB RAM, 32 GB disk, 320 × 480 portrait display, multitouch, the four buttons, audio output. SSH on `127.0.0.1:2222`, remote desktop over VNC on `127.0.0.1:5900`. |
| `dap-qmp.py screenshot\|press\|tap\|raw` | Headless automation through QEMU's QMP socket: capture the display, press `action` / `vol-up` / `vol-down` / `power`, touch at a pixel. |

Button mapping in the virtual T1: Action → `KEY_PLAYPAUSE`, Volume + → `KEY_VOLUMEUP`, Volume − → `KEY_VOLUMEDOWN`, Power → `KEY_POWER` (Linux input events). The image's device description (`/usr/share/opendap/device/description.toml`) gives each code its role; a short press of Power goes to the shell, and a long press powers off.

The build VM builds images and the sysroot only; software is built on the host and reaches a running instance as a development system extension (`system/scripts/deploy.sh`), without rebuilding the image. Process: [development workflow](https://github.com/opendap-project/toolkit-host/blob/main/docs/specs/development-workflow.md).

Touch from the host (`dap-qmp.py tap`) is not a valid contact in QEMU 11.1.2. Tests inject touches in the guest with `dap-qemu.sh ssh dap-inject tap X Y`.

For UI work with GPU acceleration, the same image can be opened in UTM.

Local, never committed: `dev-ssh/` (development SSH key for virtual instances only) and `run/` (QEMU state).
