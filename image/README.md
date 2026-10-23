# Image

The Blackbird OS image definition, built with [mkosi](https://github.com/systemd/mkosi) inside the Debian build VM by toolkit-image's `odap-image build <profile>`.

- `mkosi.conf`: what every output shares (Debian trixie, kernel from trixie-backports).
- `mkosi.profiles/<profile>/`: per-output settings. `qemu` (virtual T1), `oci` (container) and `sysroot` (headers and libraries for cross-builds on the host, never shipped) are implemented; `t1` (device) is not yet.
- The `qemu` profile is the image for every virtual device ([virtual-devices](https://github.com/opendap-project/virtual-devices)). It carries no model: the build passes in the virtual board's support package (virtual-devices `export/bsp`), which reads the running model's description from the virtual board. It also carries:
  - the shell's session: `odap-shell.service`, run as the `odap` user through PAM and logind;
  - the display stack;
  - `systemd-sysext`, for development extensions;
  - the power-key policy;
  - the quiet product boot, with the "debug" boot entry as its only debug boot mode (OS-035).

  The `t1` profile will share these until system packages provide them.
- `mkosi.sandbox/`, `mkosi.extra/`: APT sources and pinning for trixie-backports, used at build time and kept in the image.
- `mkosi.env` and `mkosi.postinst.chroot`: the system's identity in every output ([ADR 0011](../docs/adr/0011-blackbird-os.md)). `mkosi.env` holds the `OS_*` values (name, ID, version, URLs); the script writes `/usr/lib/os-release` from them (`ID=blackbird`, `ID_LIKE=debian`, no codename), with Debian's file diverted so package upgrades keep it, plus `/etc/issue` and the login message in `/etc/motd` (with Debian's licence and warranty notice). A derivative sets its own values without changing these files ([guide](../docs/derivatives.md)).

Build with toolkit-image `odap-image build`; run with virtual-devices `odap-vdev start`.
