# Image

The Blackbird OS image definition, built with [mkosi](https://github.com/systemd/mkosi) inside the Debian build VM (`../build/lima/`).

- `mkosi.conf`: what every output shares (Debian trixie, kernel from trixie-backports).
- `mkosi.profiles/<profile>/`: per-output settings. `qemu` (virtual T1) and `oci` (container) are implemented; `t1` (device) is not yet.
- `mkosi.sandbox/`, `mkosi.extra/`: APT sources and pinning for trixie-backports, used at build time and kept in the image.
- `mkosi.postinst.chroot`: the system's identity in every output ([ADR 0011](../docs/adr/0011-blackbird-os.md)): `/usr/lib/os-release` says Blackbird OS (`ID=blackbird`, `ID_LIKE=debian`, no codename), with Debian's file diverted so package upgrades keep it, plus the console banner in `/etc/issue` and the login message in `/etc/motd` (with Debian's licence and warranty notice).

Build and run with `../build/dap-image.sh` and `../build/dap-qemu.sh`.
