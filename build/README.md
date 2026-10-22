# Build and run

Everything runs locally (no CI).

| Script | What it does |
|---|---|
| `dap-image.sh [profile]` | Builds a DAP OS image with mkosi inside the Debian build VM (`lima/dapos-build.yaml`, created on first use). Default profile: `qemu`. |
| `dap-qemu.sh start\|stop\|ssh\|console` | Runs the **virtual T1** on the host with QEMU (HVF on macOS, KVM on Linux): 4 GB RAM, 32 GB disk, 320 × 480 portrait display, multitouch, the four buttons, audio output. SSH on `127.0.0.1:2222`, remote desktop over VNC on `127.0.0.1:5900`. |
| `dap-qmp.py screenshot\|press\|tap\|raw` | Headless automation through QEMU's QMP socket: capture the display, press `action` / `vol-up` / `vol-down` / `power`, touch at a pixel. |

Button mapping in the virtual T1: Action → `KEY_PLAYPAUSE`, Volume + → `KEY_VOLUMEUP`, Volume − → `KEY_VOLUMEDOWN`, Power → `KEY_POWER` (Linux input events).

For UI work with GPU acceleration, the same image can be opened in UTM.

Local, never committed: `dev-ssh/` (development SSH key for virtual instances only) and `run/` (QEMU state).
