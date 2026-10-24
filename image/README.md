# Image

The Blackbird OS image definition, built with [mkosi](https://github.com/systemd/mkosi) inside the Debian build VM by toolkit-image's `odapkit image build <profile>`.

- `mkosi.conf`: what every output shares (Debian trixie, kernel from trixie-backports), and what the image leaves out because it serves nothing on the device (OS-021):
  - documentation, manual pages and translations of system tools, through dpkg's path filters (`mkosi.sandbox/etc/dpkg/dpkg.cfg.d/01-blackbird-slim`; copyright files stay), applied again by `scripts/slim.postinst.chroot` to the essential packages that mkosi unpacks before dpkg;
  - kernel modules for hardware no OpenDAP device, HAT or peripheral can have (datacenter fabrics and adapters, cluster file systems, hypervisor guests, PC graphics cards). Every other module stays; a board support package trims further only what its board cannot use, such as other boards' devicetrees.
- `mkosi.profiles/<profile>/`: per-output settings. `qemu` (virtual T1), `oci` (container) and `sysroot` (headers and libraries for cross-builds on the host, never shipped) are implemented; `t1` (device) is not yet.
- The `qemu` profile is the image for every virtual device ([virtual-devices](https://github.com/opendap-project/virtual-devices)). It carries no model: the build includes the virtual board's support package (virtual-devices `export/bsp`: files, initrd drivers, kernel options), which reads the running model's description from the virtual board. It also carries:
  - the shell's session: `odap-shell.service`, run as the `odap` user through PAM and logind;
  - the display stack;
  - `systemd-sysext`, for development extensions;
  - the power-key policy;
  - the quiet product boot, with the "debug" boot entry as its only debug boot mode (OS-035).

  The `t1` profile will share these until system packages provide them.
- `mkosi.sandbox/`, `mkosi.extra/`: APT sources and pinning for trixie-backports, used at build time and kept in the image; the sandbox also holds the dpkg path filters, used at build time only.
- `mkosi.extra/usr/bin/odap-reboot`: restarts into a boot mode of the device: `normal`, `debug` when the image has the debug entry, and whatever a board support package adds as `/usr/lib/opendap/boot-modes.d/<mode>` (`--list` names them). The `opendap` CLI and `odap-vdev` call it instead of imitating button combinations.
- `mkosi.env` and `mkosi.postinst.chroot`: the system's identity in every output ([ADR 0011](../docs/adr/0011-blackbird-os.md)). `mkosi.env` holds the `OS_*` values (name, ID, version, URLs); the script writes `/usr/lib/os-release` from them (`ID=blackbird`, `ID_LIKE=debian`, no codename), with Debian's file diverted so package upgrades keep it, plus `/etc/issue` and the login message in `/etc/motd` (with Debian's licence and warranty notice). A derivative sets its own values without changing these files ([guide](../docs/derivatives.md)).

Build with toolkit-image `odapkit image build`; run with virtual-devices `odap-vdev start`.
