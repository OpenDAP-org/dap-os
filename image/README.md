# Image

The Blackbird OS image definition, built with [mkosi](https://github.com/systemd/mkosi) inside the Debian build VM (`../build/lima/`).

- `mkosi.conf`: what every output shares (Debian trixie, kernel from trixie-backports).
- `mkosi.profiles/<profile>/`: per-output settings. `qemu` (virtual T1), `oci` (container) and `sysroot` (headers and libraries for cross-builds on the host, never shipped) are implemented; `t1` (device) is not yet.
- The `qemu` profile carries the shell's session (`dap-shell.service` as the `dap` user through PAM and logind, the display stack, `systemd-sysext` for development extensions, the virtual T1's device description, the power-key policy). The `t1` profile will share it until system packages provide it.
- `mkosi.sandbox/`, `mkosi.extra/`: APT sources and pinning for trixie-backports, used at build time and kept in the image.
- `mkosi.env` and `mkosi.postinst.chroot`: the system's identity in every output ([ADR 0011](../docs/adr/0011-blackbird-os.md)). `mkosi.env` holds the `OS_*` values (name, ID, version, URLs); the script writes `/usr/lib/os-release` from them (`ID=blackbird`, `ID_LIKE=debian`, no codename), with Debian's file diverted so package upgrades keep it, plus `/etc/issue` and the login message in `/etc/motd` (with Debian's licence and warranty notice). A derivative sets its own values without changing these files ([guide](../docs/derivatives.md)).

Build and run with `../build/dap-image.sh` and `../build/dap-qemu.sh`.
