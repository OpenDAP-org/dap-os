# Build

Everything runs locally (no CI).

| Script | What it does |
|---|---|
| `dap-image.sh [profile]` | Builds a Blackbird OS image with mkosi inside the Debian build VM (`lima/blackbird-os-build.yaml`, created on first use). Default profile: `qemu`. |
| `dap-sysroot.sh [--no-build\|--path]` | Builds the `sysroot` profile (the image's packages plus their `-dev` packages) and installs it on the host, in a case-sensitive APFS sparse image under `~/.cache/opendap/`, for cross-builds (`system/scripts/cross.sh`). |
| `dev-key.sh` | Creates the development SSH key that `qemu` images accept for root (`dev-ssh/`, never in device images). |
| `security-check.py` | Checks an image's package manifest against known advisories. |

**Outputs other repositories use:**

- `image/mkosi.output/blackbird-os-qemu.raw`, the `qemu` image;
- `build/dev-ssh/id_ed25519`, its development key.

[virtual-devices](https://github.com/opendap-project/virtual-devices) runs that image as any virtual model. Its board support package (`export/bsp/`) is installed into the image by the `qemu` profile.

The build VM builds images and the sysroot only. Software is built on the host and reaches a running instance as a development system extension (`system/scripts/deploy.sh`), without rebuilding the image. Process: [development workflow](https://github.com/opendap-project/toolkit-host/blob/main/docs/specs/development-workflow.md).

Local, never committed: `dev-ssh/`.
