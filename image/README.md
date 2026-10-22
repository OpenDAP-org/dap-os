# Image

The OpenDAP OS image definition, built with [mkosi](https://github.com/systemd/mkosi) inside the Debian build VM (`../build/lima/`).

- `mkosi.conf`: what every output shares (Debian trixie, kernel from trixie-backports).
- `mkosi.profiles/<profile>/`: per-output settings. `qemu` (virtual T1) and `oci` (container) are implemented; `t1` (device) is not yet.
- `mkosi.sandbox/`, `mkosi.extra/`: APT sources and pinning for trixie-backports, used at build time and kept in the image.

Build and run with `../build/dap-image.sh` and `../build/dap-qemu.sh`.
