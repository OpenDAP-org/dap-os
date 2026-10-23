# Blackbird OS lifecycle and on-device peripheral hosting: research

- **Date:** 2026-10-21
- **Status:** research, not a decision. Everything labelled **Recommendation** is a proposal for the maintainers to decide on. Nothing here changes an ADR.
- **Scope:** the full Blackbird OS lifecycle (development, image build, signing, release, flashing, OTA updates) and how Blackbird OS hosts every programmable peripheral chip on the board and on HATs.
- **Related:** [`2026-10-base-distribution.md`](2026-10-base-distribution.md), ADR 0001/0002 in [`../adr/`](../adr/), board ADR 0003 (RK3566), `toolkit/host/docs/research/2026-10-software-firmware-toolchain.md` (it overlaps sections 1, 4 and 6 of this report; this report goes deeper and is consistent with it unless stated).

## 0. Inputs

### Decided (from ADRs and requirements, not re-opened here)

- Debian 13 trixie, kernel from trixie-backports (7.2.x) (ADR 0002). No custom kernel builds (OS-002, OS-006, BRD-001).
- SoC: Rockchip RK3566 (board ADR 0003). Mainline U-Boot; the boot chain is researched separately.
- Board support comes from a device tree plus overlays applied by U-Boot.
- All custom software is Rust: services, orchestrator, and the Slint-on-Wayland UI.
- No CI. Everything runs on developer machines (macOS on Apple Silicon first, Linux too), driven by local scripts, pre-commit and Claude Code skills.
- OS-008 / BRD-004 / BRD-005 / HCS-013: Blackbird OS is the real host of every programmable chip, on the board and on HATs. Helper MCUs never sit in a data path.
- BRD-014 / BRD-015: there is an RP-series coprocessor (exact part not fixed), and Blackbird OS flashes and updates it.
- HCS-007…011, SYS-010/011: HATs carry signed capability manifests in EEPROM. Capabilities are fetched over HTTP (reverse-domain / well-known) through the package endpoint.

**Evidence convention.** A version is a live query made on 2026-10-21 against the URL given: GitHub Releases/Tags API, crates.io API, Homebrew API, Debian madison (`qa.debian.org/madison.php`), or the upstream docs. **UNVERIFIED** marks anything not checked against a primary source in this session.

---

## 1. Key findings (read this first)

1. **Use one declarative image definition with three profiles.** mkosi (upstream **v27.1**, 2026-09-28; trixie ships 25.3-7) can produce `Format=oci`, `Format=disk` (via systemd-repart, with erofs + dm-verity) and directory/tar trees from one config tree, with `Profiles=`, `Snapshot=` (snapshot.debian.org) and `SourceDateEpoch=`/`Seed=` for reproducibility ([mkosi man page v27.1](https://github.com/systemd/mkosi/blob/v27.1/mkosi/resources/man/mkosi.1.md)). mkosi has **no U-Boot bootloader mode** (`Bootloader=` covers only none/systemd-boot/uki/grub). The device profile therefore uses `Bootloader=none` plus our own post-output step that writes U-Boot and the FIT images.
2. **On macOS the builder must be a Linux VM.** Run mkosi inside an arm64 Debian trixie VM (Lima 2.2.1 with `vmType: vz`, or an OrbStack machine). The build is native arm64, so no binfmt is needed. The image itself runs best in **QEMU 11.1.2 with HVF** on the macOS host. In the Homebrew build, virtio-gpu is **2D only**: the formula has no virglrenderer dependency ([formula API](https://formulae.brew.sh/api/formula/qemu.json)), so the guest renders with llvmpipe. UTM 5.0.8 gives GL through `virtio-gpu-gl-pci` with ANGLE/Metal ([UTM docs](https://docs.getutm.app/guest-support/linux/)).
3. **A fully open flashing path exists, in Rust, without sudo on macOS.** Mainline U-Boot can build MaskROM images (`CONFIG_ROCKCHIP_MASKROM_IMAGE` → `u-boot-rockchip-usb471.bin` / `usb472.bin`, [rockchip-u-boot.dtsi v2026.10](https://github.com/u-boot/u-boot/blob/v2026.10/arch/arm/dts/rockchip-u-boot.dtsi)). Collabora's `rockusb` crate (**0.4.0**, 2026-09-09) can push them (`download-sram` / `download-ddr`) and then write a `.img` + `.bmap` (`write-bmap`, gzip/zstd) over the nusb backend. This is the base for a one-command `dap flash`.
4. **For OTA, RAUC fits our stack best.** U-Boot now ships a **RAUC bootmeth** (`bootmeth_rauc.c`, first commit 2025-06-18, [docs](https://docs.u-boot.org/en/latest/develop/bootstd/rauc.html)). It implements `BOOT_ORDER` / `BOOT_x_LEFT` A/B with try counters. RAUC (upstream **1.15.2**; trixie **1.13**) has signed verity bundles, HTTP streaming (Range requests) and *adaptive* (block-hash-index) updates. A static HTTP server through the package endpoint is enough.
5. **Debian's OpenOCD cannot bit-bang SWD from Linux GPIO.** Debian `openocd 0.12.0-2` disabled the libgpiod backend (changelog: "Disable libgpiod backend (Closes: #1070885)", [debian/changelog](https://sources.debian.org/src/openocd/0.12.0-3/debian/changelog/)). The last upstream release is still **v0.12.0 (2023-01-14)**. Upstream *master* has the pieces we need: libgpiod v2 support (Sept 2025), the **`linuxspidev` SWD adapter** (SWD over a SPI controller, 1 kΩ between MOSI and MISO, up to about 3 MHz) and RP2350 support (Apr 2025) ([openocd.texi](https://github.com/openocd-org/openocd/blob/master/doc/openocd.texi)). **Blackbird OS has to package OpenOCD from a pinned git commit.**
6. **probe-rs (0.32.0) has no Linux-GPIO or spidev probe** (driver list: blackmagic, ch347, cmsisdap, ftdi, glasgow, jlink, stlink, sifliuart, ti_icdi, wlink, xvc; the bitbang PR [#1579](https://github.com/probe-rs/probe-rs/pull/1579) was closed). So probe-rs on the device works only with USB probes, which would put a helper MCU in the debug path. **Recommendation:** use OpenOCD for SoC-driven SWD/JTAG now, and contribute a gpiod/spidev probe to probe-rs later.
7. **The Debian kernel has FPGA Manager disabled** (`# CONFIG_FPGA is not set` on the `debian/latest` branch, [debian/config](https://salsa.debian.org/kernel-team/linux/-/tree/debian/latest/debian/config)). FPGA configuration must therefore be **userspace**: openFPGALoader (upstream **v1.2.0**, 2026-10-18, has a `libgpiod` JTAG cable and an XVC server; trixie has 0.13.1), or a small Rust spidev + gpiod loader for iCE40/ECP5 slave-SPI.
8. **An RP2350 makes BRD-015 safe by design; an RP2040 does not.** The RP2350 bootrom has A/B partitions, **Try-Before-You-Buy** (the new image must call `explicit_buy()` within 16.7 s or the bootrom falls back), anti-rollback, signed images (secp256k1), USB BOOTSEL and a **UART boot** mode ([RP2350 datasheet §5.1.7, §5.1.17, §5.8](https://datasheets.raspberrypi.com/rp2350/rp2350-datasheet.pdf)). Add SoC-driven SWD and the coprocessor is always recoverable from Linux.
9. **Images and apt are in tension with OS-013.** With a read-only, verity-protected root, Debian security updates reach devices as **new signed images**, not as `apt upgrade`. The maintainers should confirm that this satisfies OS-013. Section 6 proposes a "developer mode" where apt works.
10. **No CI is a real security risk for update cadence.** Section 6.6 proposes a scripted local "security watch" that diffs the image manifest against the Debian security tracker.

---

## 2. Dev loop: running Blackbird OS on the host (OS-009)

### 2.1 Where each kind of test can run

| Environment | Versions (2026-10-21) | Kernel | systemd as PID 1 | Wayland UI | Audio | Device drivers (VOP2, Panfrost, I2S/DAC, GPIO) | Boot chain, A/B, verity | Best use |
|---|---|---|---|---|---|---|---|---|
| **Native macOS** (`cargo run`) | rustup toolchain | n/a | no | Slint runs natively (winit), with no Wayland compositor | CoreAudio | no; mock the HAL | no | Fastest loop for UI and service logic with mocked hardware |
| **OCI container** (OrbStack, Docker, Apple `container`) | OrbStack 2.2.4 ([cask](https://formulae.brew.sh/api/cask/orbstack.json)); Apple `container` 1.6.0 (2026-10-20) ([releases](https://github.com/apple/container/releases)) | the VM's kernel, **not** Debian's (Apple `container` boots its own minimal kernel per container, [technical overview](https://github.com/apple/container/blob/main/docs/technical-overview.md)) | Docker/OrbStack: possible with extra flags (**UNVERIFIED** exact flags for systemd 257 in OrbStack). Apple `container`: PID 1 is `vminitd`; a custom init image is possible ([runtime-configuration](https://github.com/apple/container/blob/main/docs/runtime-configuration.md)), but systemd as PID 1 is **UNVERIFIED** | Headless compositor (e.g. weston headless/RDP, or cage + wayvnc) plus screenshots | PipeWire null sink | no | no | Service integration tests, bus/API tests, packaging checks (`apt install` of our .debs) |
| **systemd-nspawn via `mkosi boot`** inside the Linux builder VM | systemd 257.13 (trixie) | builder VM kernel (Debian) | **yes**, full systemd | headless compositor | null sink | no | no | The closest thing to a "container of the real rootfs": units, timers, users and tmpfiles behave as on the device |
| **Lima / OrbStack machine** (Debian trixie cloud image) | Lima 2.2.1 ([releases](https://github.com/lima-vm/lima/releases)) | Debian kernel | yes | headless | null sink | no | no | **Builder VM** (mkosi, cargo-deb, aptly). Not the Blackbird OS image itself |
| **QEMU `virt` + HVF** on macOS | QEMU 11.1.2 (Homebrew) | **our image's** trixie-backports kernel | yes | `virtio-gpu` 2D + llvmpipe; compositor on DRM as on the device | `virtio-sound-pci` → `-audiodev coreaudio` ([virtio-snd doc](https://www.qemu.org/docs/master/system/devices/virtio/virtio-snd.html)) | no SoC drivers. Kernel config has `DRM_VIRTIO_GPU=m` and `SND_VIRTIO=m` | **yes**: same GPT layout, verity and RAUC. U-Boot `qemu_arm64` as firmware lets us test the U-Boot A/B logic (**UNVERIFIED** under HVF; TCG works) | Image-level tests: boot, first boot, read-only root, OTA install and rollback, compositor, audio routing |
| **UTM** (QEMU backend) | 5.0.8 | our kernel | yes | `virtio-gpu-gl-pci`: GL via virgl, Vulkan via Venus, ANGLE/Metal | CoreAudio | no | yes | UI performance with GPU acceleration |
| **RK3566 reference board** (before T1 hardware exists) | U-Boot v2026.10 defconfigs, e.g. `radxa-zero-3-rk3566`, `quartz64-a-rk3566`, `anbernic-rgxx3-rk3566` ([U-Boot rockchip doc](https://github.com/u-boot/u-boot/blob/v2026.10/doc/board/rockchip/rockchip.rst)) | our kernel + mainline DTB | yes | VOP2 + Panfrost, the real thing | real I2S/codec, but not our DAC | most SoC drivers; not our board's DAC, PMIC wiring or RP | yes, the real boot chain | **Recommendation:** buy two or three of these now. Use them to validate U-Boot, FIT, RAUC, flashing and Panfrost/Wayland before the T1 exists |
| **T1 hardware** | n/a | our kernel + T1 DTB | yes | yes | yes | yes | yes | Final Definition-of-Done verification |

What none of the virtual targets can test: the RK3566 display pipeline, Panfrost, the DAC and audio path, real GPIO/SWD/SPI to peripheral chips, power management (BRD-008/009), and thermal (BRD-010). Only a reference board or the T1 covers these.

### 2.2 One image definition, three outputs

**Recommendation: mkosi** (upstream v27.1, installed pinned in the builder VM, e.g. `pipx install git+https://github.com/systemd/mkosi@v27.1`, **UNVERIFIED** install route; trixie's 25.3 is two majors behind). It is preferred over mmdebstrap + hooks for these reasons:

- `Format=oci | disk | directory | tar | sysext | confext` all come from one config tree ([mkosi.1 Format=](https://github.com/systemd/mkosi/blob/v27.1/mkosi/resources/man/mkosi.1.md)).
- `Format=disk` uses **systemd-repart**, which supports `Format=erofs` and `Verity=data|hash|signature` partitions and puts the roothash in the build JSON ([repart.d](https://www.freedesktop.org/software/systemd/man/latest/repart.d.html)).
- `Snapshot=` with the Debian default mirror `https://snapshot.debian.org`, `SourceDateEpoch=`, `Seed=` (deterministic partition UUIDs), `ImageVersion=`, and `ManifestFormat=json,changelog` (package manifest plus a human-diffable changelog, the raw material for release notes and the SBOM).
- `mkosi boot` (nspawn) and `mkosi vm` (qemu or vmspawn) give quick boots inside the builder VM.
- Fallback: mmdebstrap 1.5.7 + systemd-repart/genimage, as in the toolkit report. It is more Debian-native and simpler, but we would rebuild profiles, verity wiring, OCI export and the VM boot ourselves.

Proposed layout in `blackbird-os/image/` (illustrative):

```text
image/
  mkosi.conf                 # Distribution=debian, Release=trixie, Architecture=arm64,
                             # Snapshot=<YYYYMMDDTHHMMSSZ>, SourceDateEpoch=, Seed=, ImageVersion= (from mkosi.version)
  mkosi.conf.d/
    10-base.conf             # package set shared by every profile (systemd, pipewire, compositor, our dap-* debs)
    20-repos.conf            # trixie, trixie-security, trixie-backports (kernel only, pinned), OpenDAP APT repo snapshot
  mkosi.profiles/
    t1/                      # Format=disk, Bootloader=none, kernel+firmware+DTB packages, repart.d (A/B), post-output: FIT + U-Boot
    qemu/                    # Format=disk, same repart.d layout; either Bootloader=uki (EFI fast path) or U-Boot qemu_arm64 (fidelity)
    oci/                     # Format=oci, no kernel/firmware/bootloader; units that need hardware masked
  mkosi.repart/              # GPT A/B layout (section 4.2), erofs + verity
  mkosi.extra/               # only what cannot be a package (prefer packaging config, see 2.5)
  mkosi.postinst.chroot      # minimal; everything else lives in .debs
  mkosi.version
  packages.lock              # pinned versions: Debian snapshot ID + OpenDAP aptly snapshot name
```

The QEMU fast path (`Bootloader=uki`, EDK2 from Homebrew's QEMU) boots in seconds but does not exercise U-Boot. The fidelity path boots U-Boot `qemu_arm64` as `-bios`, with the **same** `boot.scr`/FIT and `bootmeth_rauc` as the T1. **Recommendation:** use the fast path for daily work, and the fidelity path for every release candidate and every OTA/rollback test.

### 2.3 Connecting to and controlling a running instance

**Recommendation:** add a `dap` CLI as a Rust crate in `toolkit/cli/crates/dap`. It is a thin wrapper and every step stays a plain, documented command underneath.

| Command | What it does |
|---|---|
| `dap builder up` | Creates or starts the Lima VM "dap-builder" (Debian trixie arm64, `vmType: vz`, workspace mounted with virtiofs, mkosi/cargo/aptly installed by a provisioning script in `toolkit/host/`) |
| `dap build [t1\|qemu\|oci]` | Runs `mkosi --profile …` in the builder VM. Outputs go to `blackbird-os/image/mkosi.output/` |
| `dap vm up [--fidelity]` | Runs QEMU on the macOS host: `-accel hvf -cpu host -M virt`, virtio-blk on the image, `virtio-gpu-pci` (or `-gl`), `virtio-sound-pci` + coreaudio, `-netdev user,hostfwd=tcp::2222-:22`, `-serial unix:…` for the console, `-qmp unix:…` for control |
| `dap ssh [target]` / `dap console [target]` | SSH (keys installed by the dev profile) or the serial console (QEMU unix socket; `tio` on a real device) |
| `dap deploy <crate> [--target vm\|dev-board\|t1] [--watch]` | Cross-builds and installs as a **development sysext** (see below), then restarts the unit |
| `dap logs <unit>` | `journalctl -fu` over SSH |
| `dap debug <service>` | Starts `lldb-server` (trixie `lldb-19`) or `gdbserver` (16.3; 18.1 in backports) on the target, forwards the port over SSH, and attaches CodeLLDB/rust-lldb from the host |
| `dap flash …` | Section 5 |
| `dap chip …` | Section 7: calls the on-device chip-hosting daemon |
| `dap release …` | Section 4.7 |

Transport to real hardware:

- **USB-C gadget.** A configfs composite device of **CDC-NCM** (network) + **CDC-ACM** (serial console). The Debian kernel has `USB_CONFIGFS_NCM=y`, `USB_CONFIGFS_ACM=y`, `USB_CONFIGFS_MASS_STORAGE=y`, `USB_DWC3=m`. Prefer NCM over RNDIS. That macOS drives CDC-NCM with no extra driver is **UNVERIFIED**; test it on day one.
- **Wi-Fi + mDNS** (avahi-daemon 0.8): `t1-<serial>.local`.
- **The early serial console** (U-Boot, kernel before userspace) needs a physical UART. Routing it through the RP coprocessor to USB would make the coprocessor a debug-console bridge. That is arguably not a "data path", but it conflicts with the spirit of BRD-005. Open question Q7.

### 2.4 Live-reloading our Rust services on a read-only root

The root is erofs + dm-verity, so binaries cannot be copied into `/usr`. **Recommendation: development system extensions.**

1. The dev profile enables `systemd-sysext` and allows **unsigned** extensions in `/var/lib/extensions/` (production allows only signed ones, or none).
2. `dap deploy` builds the binary:
   - **inside the builder VM** (native arm64, trixie glibc, so the ABI is identical to the image; the workspace is shared over virtiofs); or
   - on macOS with a cross-linker (`cargo-zigbuild` or similar, **UNVERIFIED** in this session) targeting `aarch64-unknown-linux-gnu` with the trixie glibc as the floor.
3. It rsyncs a directory tree `dev-<crate>/usr/bin/<bin>` + `usr/lib/extension-release.d/extension-release.dev-<crate>` to the target's `/var/lib/extensions/`, then runs `systemd-sysext refresh` and `systemctl restart <unit>`.
4. `--watch` repeats this on change (bacon/cargo-watch). `dap deploy --reset` removes the dev extensions, so the target is back to the pristine image.

This works the same way on QEMU, a reference board and the T1, and never mutates the verified root.

### 2.5 Applying changes through code and configuration, and promoting them into the image

**Recommendation:** every change reaches the image as a **versioned package or a reviewed mkosi config change**, never as a hand-edited file:

| Kind of change | Where it lives | How it is promoted |
|---|---|---|
| Rust service, orchestrator, UI | `system` → `cargo-deb` → OpenDAP APT repo | bump the version in `blackbird-os/image/packages.lock` |
| System configuration (`/etc` drop-ins, units, udev rules, polkit, PipeWire config) | `blackbird-os` package `blackbird-os-config` (built with dpkg-deb/debhelper from `blackbird-os/overlays/`) | same; it then appears in the manifest and the SBOM |
| Debian package set | `blackbird-os/image/mkosi.conf.d/10-base.conf` | git review, then a rebuild |
| Debian versions | `Snapshot=` ID in `mkosi.conf` | "snapshot bump" commit, rebuild and test |
| Board DT and overlays | `board` repo → package `dap-t1-dtb` (built against the matching kernel's dts includes) | `packages.lock` |
| Per-device state | `/var` (data partition); never in the image | n/a |

Experiment on a live target with a dev sysext or a confext (`systemd-confext` for `/etc` overlays). Then capture the result as a package change in git. A `dap diff` helper (**proposal**) can list what differs from the pristine image (dev extensions, confexts, `/var` drift).

**Known read-only-root pain points with Debian** (all solvable, prototype them early):

- `/etc/machine-id`: systemd-firstboot or a bind mount.
- SSH host keys: `HostKey /var/lib/ssh/...`.
- `/etc/resolv.conf` → `/run`.
- `/etc/localtime` and user-chosen settings → `/var` + symlinks.
- `apt` itself, disabled in production (section 6.5).

---

## 3. Packaging our software

### 3.1 Rust to .deb

- **cargo-deb 3.8.0** (2026-09-01, [crates.io](https://crates.io/crates/cargo-deb), [README](https://github.com/kornelski/cargo-deb)). It supports:
  - `[package.metadata.deb]` assets;
  - `systemd-units` (installs and enables units);
  - `maintainer-scripts` and `conf-files`;
  - `--separate-debug-symbols` / `--dbgsym`;
  - `variants` and `--deb-revision`.
- Build in the trixie arm64 builder VM, so the package links against the target glibc. Pin the toolchain with `rust-toolchain.toml`: trixie's rustc is 1.85.1 and backports has 1.96.1, so use rustup's toolchain, not Debian's.
- **Versioning (recommendation):**
  - crates use SemVer, and the deb version is `<semver>-1`;
  - dev and snapshot builds use `<next-semver>~git<YYYYMMDD>.<shorthash>-1`. The tilde sorts before the release, so a release always supersedes its snapshots;
  - every package declares `Depends:` with lower bounds on sibling `dap-*` packages, so APT refuses inconsistent mixes.
- **Debug symbols:** publish `-dbgsym` packages to a separate APT component (`debug`), plus a release-scoped tarball of `.debug` files. A `debuginfod` server is optional later (trixie has `debuginfod` 0.192; Debian's own packages are served by debuginfod.debian.net, **UNVERIFIED** current URL).

### 3.2 The OpenDAP APT repository

**Recommendation: aptly** (upstream **1.6.3**, 2026-06-25; trixie 1.6.1, trixie-backports 1.6.2, [publish docs](https://www.aptly.info/doc/aptly/publish/)). The reasons:

- Immutable **snapshots** of our repo (`aptly snapshot create dap-2026.11.0 from repo dap`). Each image release references one snapshot by name, which mirrors Debian's snapshot ID.
- `aptly mirror` can keep a **local, filtered mirror of the Debian snapshot** we build from (only the packages we use, plus their sources). That makes builds independent of snapshot.debian.org availability and gives us the GPL source set (section 4.6).
- Signed publishing (GPG/Sequoia keys via gpg-agent and a smartcard) to a local directory, then upload to static hosting.
- reprepro (5.3.2 in trixie) is simpler but has no first-class snapshots/merges. It is a fallback.

Repo shape: `https://<apt-host>/` (hostname not decided), suites `trixie` (released), `trixie-dev` (snapshots), components `main` and `debug`, arch `arm64` (+ `all`). It is served as static files, always reached through the package endpoint (SYS-011).

Client side:

- deb822 source with `Signed-By: /usr/share/keyrings/opendap-archive-keyring.gpg`, shipped in the package `opendap-archive-keyring`.
- apt 3.0.3 in trixie depends on **`sqv` ≥ 1.3.0** (Sequoia) for signature checks ([packages.debian.org/trixie/apt](https://packages.debian.org/trixie/apt)). So use a modern key (Ed25519 or RSA ≥ 3072) and no SHA-1 anywhere.

### 3.3 How this relates to Debian mirrors and to the capability repository

| Repository | Content | Consumer | Trust anchor |
|---|---|---|---|
| Debian (via `Snapshot:` / snapshot.debian.org, or our aptly mirror) | Base OS packages | **image build** (and dev-mode devices) | `debian-archive-keyring` 2025.1 |
| OpenDAP APT | Our services, config, DTB, the OpenOCD/openFPGALoader/RAUC backports we package | **image build** (and dev-mode devices) | OpenDAP archive key |
| Capability repository (reverse-domain, well-known HTTP) | Third-party and first-party **capabilities** (section 6.4) | **devices at runtime**, via the orchestrator | Publisher keys + OpenDAP-signed manifests, and HAT EEPROM manifests |
| Update index (static) | Signed OS bundle index + RAUC bundles | **devices at runtime**, via RAUC | RAUC CA (section 4.5) |
| Firmware index | Signed chip firmware (section 7.6) | **devices at runtime**, via the chip daemon | Firmware signing key / publisher keys |

**Recommendation:** keep capabilities **out of APT**. Debian maintainer scripts run as root, assume a writable `/usr`, and have no per-publisher trust model. That conflicts with an immutable base and with third-party publishers.

### 3.4 Snapshots and pinning

- apt (since 2.7; trixie has 3.0.3) supports `Snapshot: <YYYYMMDDTHHMMSSZ>` per source in deb822, plus `--snapshot` ([sources.list(5) trixie](https://manpages.debian.org/trixie/apt/sources.list.5.en.html)). mkosi's `Snapshot=` maps to the same service.
- **Recommendation:** one `Snapshot=` ID per image release covers `trixie`, `trixie-updates` and `trixie-backports`. `trixie-security` needs a separate snapshot archive (`/archive/debian-security/`; that mkosi wires security through its Snapshot= support is **UNVERIFIED**, otherwise add it explicitly). Also pin `linux-image-arm64` to an exact backports version in `packages.lock`, and record both in the release manifest.
- snapshot.debian.org is known to be slow or rate-limited at times (**UNVERIFIED** current limits). Build from the local aptly mirror of that snapshot, and keep snapshot.debian.org as the source of truth.

---

## 4. Image build, signing and release

### 4.1 Reproducible build

- Inputs: the git commit of `blackbird-os`, the Debian snapshot ID, the OpenDAP aptly snapshot name, the mkosi version, and the U-Boot artifact hash (from the boot-chain research).
- mkosi `SourceDateEpoch=` (= commit time) and `Seed=` (fixed). Packages are installed from pinned snapshots. Output compression is set explicitly.
- Verify with a periodic **double build** (two different developer machines, or two builder VMs) and compare with `diffoscope` (Debian package, **UNVERIFIED** version) and `reprotest` 0.7.30. Without CI, make this a release checklist step (section 4.7).
- Reproducibility also matters for OTA efficiency: RAUC adaptive updates (block-hash-index) only save bandwidth if unchanged files land in unchanged blocks. Use a stable erofs build (sorted, fixed timestamps). Measure whether erofs compression hurts block reuse (**UNVERIFIED**, needs measurement).

### 4.2 Image format and partition layout

**Recommendation** (to be reconciled with the boot-chain research). Use GPT on eMMC with **symmetric A/B** for both boot and root, a read-only verity root, and a separate data partition.

| Region / partition | Size (initial guess) | Content |
|---|---|---|
| sector 64 … ~16 MiB (raw, outside GPT partitions) | ~16 MiB | `u-boot-rockchip.bin` (idbloader + `u-boot.itb`) written at sector 64, as in the U-Boot doc; redundant U-Boot env in a reserved raw area (exact offsets: boot-chain research) |
| `boot_a`, `boot_b` | 128 MiB each | vfat or ext4: `boot.scr` + signed FIT (kernel, DTB, overlays, initramfs) |
| `root_a`, `root_b` | 3 GiB each (**guess**; eMMC size open) | erofs `/usr`-merged root, read-only |
| `root_a-verity`, `root_b-verity` | ~1–2 % of root each | dm-verity hash tree (repart `Verity=hash`) |
| `factory` | 16 MiB | written once: serial, device identity, calibration, per-device certs; read-only after provisioning |
| `data` | rest | ext4 (or f2fs, **UNVERIFIED** which is better on our eMMC): `/var`, `/home`, capabilities, logs, RAUC state |

- Use the [UAPI Discoverable Partitions](https://uapi-group.org/specifications/specs/discoverable_partitions_specification/) type GUIDs (root-arm64, root-arm64-verity). The QEMU EFI path then auto-discovers the root (systemd-gpt-auto), and the same layout serves both paths.
- U-Boot's `bootmeth_rauc` needs `CONFIG_BOOTMETH_RAUC_PARTITIONS="1,2 3,4"`-style pairs of (boot, root) ([doc](https://docs.u-boot.org/en/latest/develop/bootstd/rauc.html)). The verity partitions are found by the initramfs, not by U-Boot.

#### FIT vs UKI (recommendation: FIT on the device)

- **FIT + U-Boot verified boot** ([signature.rst](https://docs.u-boot.org/en/latest/usage/fit/signature.html)):
  - native to mainline U-Boot and to `bootmeth_rauc`;
  - signed *configurations* bind kernel + DTB + overlays + initramfs together;
  - device-tree overlays can be listed in a FIT configuration, so U-Boot applies them under the signature;
  - `mkimage` signs with an RSA key, also via PKCS#11/OpenSSL engine (`-N`), so hardware tokens work (**UNVERIFIED** with our token).
- **UKI** (systemd-stub; `systemd-ukify` 257.13 in trixie):
  - needs U-Boot's UEFI loader and either systemd-boot or direct `bootefi`;
  - pros: systemd-native boot counting, systemd-sysupdate, `.dtbauto`;
  - cons: overlays applied by U-Boot (a decided constraint) fit less naturally, and UEFI secure-boot variable storage on eMMC without RPMB is weak.
  - Keep UKI as the **QEMU fast path** only (mkosi does it out of the box).

#### dm-verity trust

- The Debian kernel has `DM_VERITY_VERIFY_ROOTHASH_SIG=y`, but that checks signatures against kernel keyrings we cannot extend without rebuilding the kernel (OS-002).
- **Recommendation:** carry the roothash inside the **signed FIT**. Either embed it in the per-image initramfs (`/etc/veritytab`, or a systemd-veritysetup config in the initrd), or put it in signed bootargs if U-Boot's config can carry them (**UNVERIFIED**).
- The trust chain is then: (Rockchip BootROM →) U-Boot → signed FIT → initramfs with roothash → dm-verity root → RAUC keyring and our other trust anchors inside the verified root.

#### Locking (maintainers' decision, Q2)

- Without burning the RK3566 OTP key hash, U-Boot itself can be replaced by anyone with physical access. FIT signing then protects against corruption and malicious OTA, but not against physical tampering.
- For an open-hardware device, **verified-but-not-locked by default** (user-ownable keys) is a coherent position. A "locked" option means fusing OTP, which is irreversible; that belongs to the boot-chain research.

### 4.3 Kernel, DTB and overlays inside the image

- The kernel comes from `linux-image-arm64` (trixie-backports, currently 7.2.9-1~bpo13+1). The FIT is assembled at build time from the installed `vmlinuz` + `initrd.img` + our DTB.
- The T1 DTB is **not in mainline**. Build it in `board` from our `.dts` against the `rk3566.dtsi` of the exact kernel version (kernel source tag), package it as `dap-t1-dtb_<board-rev>+k<kver>` and pin it per kernel. Overlays (`.dtbo`) are packaged with it.
- HAT overlays raise a problem. U-Boot can read a HAT ID from the EEPROM and select a **first-party** overlay already inside the signed FIT. A **third-party** HAT overlay that ships in a capability, not in the image, cannot be covered by the image's FIT signature. Open question Q4.

### 4.4 SBOM, versions and release notes

- **SBOM (recommendation):**
  - mkosi `ManifestFormat=json` gives the authoritative installed-package list;
  - `syft` (**v1.55.0**, 2026-10-19) scans the built root directory (dpkg cataloger) to SPDX JSON and CycloneDX JSON;
  - Rust crates are embedded with `cargo auditable` (**UNVERIFIED** version) or listed with `cargo-cyclonedx` (**UNVERIFIED** version);
  - each release ships `sbom.spdx.json` + `sbom.cdx.json`.
- **Image version (recommendation): CalVer `YYYY.MM.N`** (e.g. `2026.11.0`), with channels `dev`/`beta`/`stable`.
  - Written to `/usr/lib/os-release` as `IMAGE_ID=blackbird-os-t1` and `IMAGE_VERSION=2026.11.0` (UAPI fields; mkosi sets them from `ImageId=`/`ImageVersion=`).
  - Packages keep SemVer. Monotonic CalVer suits RAUC compatibility checks and the RP2350-style anti-rollback counters.
- **Release notes:** generate from (a) the mkosi `changelog` manifest diff against the previous release (Debian package changes, including security fixes), (b) `git log` of `blackbird-os`, `system`, `board` between release tags, (c) the firmware index diff. This can be a Claude Code skill (`/blackbird-os:release-notes`, **proposal**) that drafts, with a human editing.

### 4.5 Keys and signing

| Key | Algorithm / format | Signs | Verified by | Storage (recommendation) |
|---|---|---|---|---|
| **OpenDAP root (offline)** | Ed25519 or X.509 CA | certifies the keys below | humans and release tooling | offline, two hardware tokens in separate places |
| Rockchip secure-boot key (optional, Q2) | RSA (Rockchip format) | TPL/SPL | BootROM via OTP hash | only if locking is decided; boot-chain research |
| **FIT signing key** | RSA-2048/4096 (U-Boot) | FIT configurations (kernel, DTB, overlays, initramfs) | U-Boot (pubkey in U-Boot's control DTB) | hardware token (PKCS#11) |
| **RAUC bundle signing** | X.509 + CMS ([RAUC advanced: PKI, PKCS#11](https://rauc.readthedocs.io/en/latest/advanced.html)) | OS update bundles | RAUC on the device (keyring in the verified root) | hardware token; RAUC supports PKCS#11 URLs natively |
| **APT archive key** | OpenPGP (Ed25519) | `InRelease` of the OpenDAP repo | apt via sqv | smartcard subkey; primary key offline |
| **Release artifact signature** | minisign (Ed25519) or OpenPGP; optionally cosign (v3.1.4) | `SHA256SUMS` of each GitHub Release | users, `dap flash` | same token as the APT key, or a dedicated one |
| **Capability manifest key(s)** | Ed25519 (format set by the manifest spec) | OpenDAP-endorsed capability manifests; HAT EEPROM manifests | orchestrator | per publisher; OpenDAP's on a hardware token |
| **Firmware signing key(s)** | Ed25519 for our index + chip-native keys (e.g. RP2350 **secp256k1**, `picotool seal --sign`, [picotool README](https://github.com/raspberrypi/picotool)) | chip firmware images and the firmware index | chip daemon; the RP2350 bootrom for its own images | hardware token |
| fwupd metadata key (only if fwupd is used, 7.6) | jcat (PKCS#7 or GPG) | fwupd metadata of our remote | fwupd | **UNVERIFIED** exact keyring path for a custom remote; check [fwupd-remotes.d](https://github.com/fwupd/fwupd/blob/2.1.8/docs/fwupd-remotes.d.md) |

Without CI, signing happens on a release manager's machine. **Recommendation:**

- Require hardware tokens (YubiKey/Nitrokey via PKCS#11) for the FIT, RAUC, APT and release keys, and never put private keys in git or `~/.ssh`.
- Run one scripted `dap release sign` step that touches all of them.
- Keep separate **dev keys** (committed public halves, private halves on each developer machine) for dev images. Dev images are visibly marked (`IMAGE_VERSION` suffix `-dev`) and refuse production bundles (RAUC `compatible` differs).

### 4.6 Artifact layout and GitHub Releases

GitHub Releases allow up to 1000 assets per release, each **under 2 GiB**, with no total-size or bandwidth limit ([GitHub docs](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)). Upload from a local machine with `gh release create` ([gh manual](https://cli.github.com/manual/gh_release_create)).

```text
blackbird-os v2026.11.0 (GitHub Release in opendap-project/blackbird-os, tag v2026.11.0)
  blackbird-os-t1-2026.11.0.img.zst            # full eMMC image incl. U-Boot (flash with dap flash / bmaptool)
  blackbird-os-t1-2026.11.0.img.bmap
  blackbird-os-t1-2026.11.0.raucb              # OTA bundle (verity format, streamable)
  u-boot-t1-2026.11.0-usb471.bin         # MaskROM recovery stage 1 (TPL/DDR init)
  u-boot-t1-2026.11.0-usb472.bin         # MaskROM recovery stage 2 (SPL + U-Boot, runs from RAM)
  blackbird-os-qemu-arm64-2026.11.0.img.zst    # QEMU disk image (same layout)
  blackbird-os-rootfs-arm64-2026.11.0.oci.tar  # OCI image (also pushed to ghcr.io/opendap-project/blackbird-os:2026.11.0, UNVERIFIED org path)
  manifest.json, changelog.txt           # mkosi manifests
  sbom.spdx.json, sbom.cdx.json
  SOURCES.txt                            # pointer to the source archive (below)
  SHA256SUMS, SHA256SUMS.minisig         # signed checksums
  RELEASE-NOTES.md
```

**GPL/LGPL compliance (important).** Distributing an image of Debian binaries obliges us to provide the corresponding sources. **Recommendation:** for each release, aptly-mirror the `deb-src` of exactly the installed source packages from the pinned snapshot, and publish them as a source archive (object storage; it can exceed 2 GiB, so split it or host it outside GitHub). `SOURCES.txt` links to it. The U-Boot/TF-A sources and the rkbin blob licenses belong to the boot-chain artifacts.

### 4.7 Release procedure (no CI)

Proposed `dap release` (a script in `blackbird-os/release/`, which a Claude Code skill wraps):

1. Preflight: clean git trees, tags on `system`/`board` match `packages.lock`, a hardware token is present, and `mkosi summary` is clean.
2. Build `t1`, `qemu` and `oci` profiles from the pinned inputs.
3. Second build on another machine or VM, then `diffoscope` (allowed differences documented).
4. QEMU fidelity tests: first boot, read-only root, install the previous release → OTA to this one → forced failure → rollback (section 6.3).
5. Hardware tests on a reference board and, later, the T1: flash with `dap flash`, OTA from the previous stable release, chip-hosting smoke test (section 7).
6. Sign the FIT (done during build, via token), RAUC bundle, `SHA256SUMS` and APT `InRelease`.
7. SBOM, release notes, source archive.
8. `gh release create`, publish the aptly snapshot, update the signed update index for the channel (section 6.4).
9. Tag `blackbird-os` and record the release in `docs/` (versions, snapshot IDs, key fingerprints).

---

## 5. Flashing (OS-012)

### 5.1 Paths available on the RK3566

| Path | Tools (versions) | Needs | Pros | Cons |
|---|---|---|---|---|
| **MaskROM over USB → U-Boot in RAM → write eMMC** | `rockusb` 0.4.0 (Rust, nusb, MIT/Apache-2.0) `download-sram` / `download-ddr` with U-Boot `usb471`/`usb472` images; or `rkdeveloptool` 1.32+pine64git20240226 (trixie) with a rkbin `*_spl_loader.bin` (proprietary loader) | USB-C OTG port wired to the SoC OTG controller, plus a way to force MaskROM (button) | Works on a blank or bricked device; no SD card; the BootROM is mask ROM, so the device cannot be hard-bricked | The usb471 stage embeds the DDR init TPL (rkbin blob, `ROCKCHIP_TPL`); U-Boot's `ROCKCHIP_MASKROM_IMAGE` depends on `TPL \|\| ROCKCHIP_EXTERNAL_TPL` |
| **U-Boot `rockusb` gadget** | U-Boot `rockusb 0 mmc 0`; host `rockusb write-bmap image.img` | U-Boot running (from eMMC, or from RAM via the row above) | Rust host tool, bmap-sparse (fast), **no sudo** on macOS (nusb) | That Collabora's `rockusb` drives U-Boot's rockusb gadget end to end (write LBA + bmap) is **UNVERIFIED**; test it on a reference board |
| **U-Boot `ums`** (USB mass storage) | U-Boot `ums 0 mmc 0` ([doc](https://docs.u-boot.org/en/latest/usage/cmd/ums.html)); host `bmaptool copy` 3.9.0 or `dd` | U-Boot running | The eMMC appears as a disk on any OS; Etcher-compatible | Raw-disk writes need sudo on macOS/Linux; bmaptool on macOS raw devices is **UNVERIFIED** |
| **fastboot** (U-Boot) | `fastboot` (trixie 1:34.0.5) | U-Boot running | Familiar to Android devs | Another protocol to support; no advantage over rockusb/ums |
| **SD card** | balenaEtcher v2.1.8, `bmaptool`, `dd` | an SD slot (not decided for the T1, Q5); the BootROM boot order must reach SD | Simplest for end users | Needs a slot; the BootROM prefers eMMC if bootable (**UNVERIFIED** RK3566 boot order details) |
| **Self-update from Blackbird OS** | RAUC (section 6) | a working OS | No host needed | Not for first flash or recovery |

### 5.2 Recommendation: one command, `dap flash`

`dap flash [--image blackbird-os-t1-<ver>.img.zst] [--recovery]` in `toolkit`, Rust, built on the `rockusb` crate (nusb backend, so no libusb and no sudo on macOS, and on Linux only a udev rule shipped by `host/setup.sh`):

1. Detect the device: Rockchip VID `0x2207` in MaskROM, U-Boot rockusb, or a running Blackbird OS reachable via NCM/mDNS.
2. If Blackbird OS is running, ask it to reboot into the U-Boot rockusb gadget (a signed request through the `dap` API, or `reboot bootloader` mapped to a U-Boot env flag).
3. If in MaskROM, push `usb471` + `usb472` (versions from the release) so U-Boot runs from RAM and enters `rockusb` automatically (U-Boot env/script for the MaskROM build, **proposal**).
4. Verify `SHA256SUMS` + minisig, then `write-bmap` the `.img.zst`. Read back the GPT and a sample of hashes.
5. Reboot. Wait for the device to appear over NCM, and print the version.

Fallbacks:

- `dap flash --ums` (U-Boot ums + bmaptool).
- `rkdeveloptool` for anyone who needs the vendor loader.

#### End users

- `dap flash` ships as a standalone signed binary for macOS (arm64), Linux (x86_64/arm64) and Windows (rockusb/nusb are cross-platform; Windows WinUSB driver binding is **UNVERIFIED**).
- Normal updates are OTA from the device UI (section 6).
- A browser flasher via WebUSB is a possible later convenience (**idea, UNVERIFIED** feasibility with nusb/wasm).

**Factory provisioning:** the same flow scripted for N devices on a Linux host, plus writing `factory` partition data (serial, device certificate) and a final test.

#### Board requirements for flashing (pass to `board`)

- The SoC's USB OTG port reachable on the device's USB-C connector, with the data role switchable to device.
- A recessed **MaskROM** button (forces the BootROM into USB download). The exact method on RK3566, e.g. eMMC CLK/CMD gating, is **UNVERIFIED** and needs checking against the Rockchip reference design.
- A **Recovery** key (SARADC input) that U-Boot reads to enter rockusb mode, the Rockchip convention. **UNVERIFIED** in mainline U-Boot for a custom board.

---

## 6. Updates and OTA (OS-013, OS-014)

### 6.1 Options compared

| | **RAUC** | SWUpdate | systemd-sysupdate | Mender | OSTree / bootc |
|---|---|---|---|---|---|
| Upstream version | 1.15.2 (2026-03-27) | 2026.05.1 | systemd v262.1 | client 5.1.0 | OSTree v2026.4; bootc v1.17.1 |
| In Debian trixie | 1.13-3+deb13u1 (forky 1.15.2) | 2024.12.1 (backports 2026.05.1) | in package `systemd-container` (257.13) | `mender-client` 3.4.0 (old) | `ostree` 2025.2; bootc **UNVERIFIED** (not checked) |
| A/B + rollback with U-Boot | **Native `bootmeth_rauc` in mainline U-Boot** (`BOOT_ORDER`, `BOOT_x_LEFT`, `RAUC_DEFAULT_TRIES`), or a classic boot script; Linux side via `fw_setenv` (libubootenv-tool 0.3.5) | Native U-Boot env handling + bootcount ([bootloader interface](https://sbabic.github.io/swupdate/bootloader_interface.html)) | Writes partitions or files, but boot assessment is systemd-boot/UKI-centric; with U-Boot it needs custom glue | Yes (U-Boot integration) | OSTree has a U-Boot backend (uEnv); bootc is Fedora-centric (**UNVERIFIED** on Debian) |
| Signing | X.509/CMS, PKCS#11 | RSA/CMS for `sw-description` | GPG-signed `SHA256SUMS` | Artifact signing | GPG / ed25519 commit signing |
| Delta / bandwidth | **Adaptive `block-hash-index`** with HTTP streaming (no fixed source version needed) ([advanced](https://rauc.readthedocs.io/en/latest/advanced.html)); casync also supported | Delta handler with zchunk ([delta-update](https://sbabic.github.io/swupdate/delta-update.html)) | Partition/file level; no block delta | Delta is a commercial add-on (**UNVERIFIED** current terms) | Native file-level deltas |
| Server | **Static HTTP with Range** (or hawkBit) | static or hawkBit | static HTTP | Mender server (or hosted) | static HTTP (OSTree repo) |
| Fit with read-only verity root | Strong (verity bundles; composefs artifacts since 1.14) | Good | Strong (UAPI-native) | OK | Different model (file-level deployments, not verity partitions) |
| Control API for our Rust orchestrator | D-Bus (`de.pengutronix.rauc.Installer`) | IPC socket / progress API | D-Bus (`updatectl`, systemd 257+) | D-Bus / CLI | D-Bus (rpm-ostree), CLI |

#### Recommendation: RAUC + U-Boot `bootmeth_rauc`

- Use verity-format bundles, signed with the RAUC key on a token.
- Install by HTTP streaming with adaptive updates, from a static origin through the package endpoint.
- Package RAUC 1.15.2 ourselves (a backport of the forky package into the OpenDAP repo), or start on trixie's 1.13 if it covers what we use. Verity, streaming and adaptive updates all predate 1.13 per the [RAUC changelog](https://github.com/rauc/rauc/blob/v1.15.2/CHANGES).
- **Runner-up: SWUpdate** (more flexible handlers, zchunk deltas, but more custom scripting).

### 6.2 Slot model

- `system.conf`:
  - `compatible=blackbird-os-t1` (dev images use `blackbird-os-t1-dev`);
  - `bootloader=uboot`;
  - slot classes `boot` (vfat FIT), `rootfs` (erofs) and `verity` (hash partition), each with `.0`/`.1` instances, the verity slot `parent=rootfs`.
- The data partition is never touched by RAUC. Migrations of `/var` state run as versioned systemd units on first boot of a new slot.
- **U-Boot itself is not in the A/B set.** Rockchip boots the idbloader from fixed sectors. Treat bootloader updates as a rare, separate, guarded procedure (verify, write, read back, keep MaskROM recovery documented), owned by the boot-chain research. **Q3:** does the RK3566 BootROM try backup idbloader copies? **UNVERIFIED**.

### 6.3 Rollback

1. RAUC installs into the inactive slot and sets `BOOT_ORDER="B A"` with `BOOT_B_LEFT=3`.
2. `bootmeth_rauc` decrements `BOOT_B_LEFT` on each try.
3. In userspace, a **health gate** runs: a systemd target `dap-boot-complete.target` that requires the orchestrator, the compositor and the bus to report healthy within N seconds. On success, `rauc status mark-good` resets the counter. On failure or a watchdog reset (RK3566 watchdog, enabled via systemd `RuntimeWatchdogSec=`), the counter runs out and U-Boot boots A.
4. `CONFIG_BOOTMETH_RAUC_RESET_ALL_ZERO_TRIES` prevents lock-up if both slots run out.
5. Test it in QEMU's fidelity path: kill the health gate on purpose and check that slot A comes back.

### 6.4 Combining image-based base updates with package-based capability updates

```text
           ┌──────────── base OS (image-based, A/B, RAUC) ─────────────┐
           │ Debian trixie + backports kernel + OpenDAP .debs          │
           │ read-only erofs + dm-verity; one signed bundle per release│
           └──────────────────────────────┬────────────────────────────┘
                                          │ stable, versioned API: bus schemas, SDK ABI, os-release IMAGE_VERSION
           ┌──────────────────────────────┴────────────────────────────┐
           │ capabilities (package-based, per publisher, on /data)     │
           │ fetched via reverse-domain/well-known HTTP through the    │
           │ package endpoint; signed manifests; sandboxed             │
           └───────────────────────────────────────────────────────────┘
```

#### Recommendation

- A capability is a **signed, self-contained bundle**: manifest + payload. The payload is ideally an erofs image whose dm-verity roothash is in the signed manifest, so it is mounted read-only and verified block by block. A plain tree with per-file hashes is the fallback. It is stored on `/data/capabilities/<reverse-domain>/<version>/`. The orchestrator verifies the signature with our own Rust code (e.g. `ed25519-dalek` 3.0.0 or `minisign-verify` 0.3.0), not with kernel keyrings.
- A capability declares `requires-os: >= 2026.11` and the bus/SDK API versions it needs (SYS-002). After a base update, the orchestrator re-validates the installed capabilities **before** `mark-good`. If a critical capability breaks, the health gate fails and the system rolls back.
- Capabilities never write to `/usr` or `/etc`. Native code is statically linked Rust or brings its own libraries. Whether some first-party capabilities could be `systemd-sysext` images is an open design point; the sysext userspace signature verification path without kernel keyrings is **UNVERIFIED**.
- HAT manifests in EEPROM point at capability IDs. The orchestrator resolves them through the same repository and package endpoint.

### 6.5 Where apt fits (OS-013)

- **Production devices:** apt is present for tooling (`dpkg -l`, manifests), but the root is read-only and there are no apt sources for upgrades. Debian and OpenDAP package updates arrive **inside the next image release**. OS-013 is met at build time (each image pulls the latest trixie-security and OpenDAP packages from the new snapshot). Ask the maintainers to confirm this reading (Q1).
- **Developer mode** (user-enabled, visibly flagged): the device switches to a "writable root" variant. Options: (a) a third, non-A/B "dev" root; (b) an overlayfs on `/usr` persisted on `/data`, verity off; (c) dev sysexts only (section 2.4). Then `apt install` works against the same snapshots plus live Debian. A base OTA discards these changes, with a warning.

### 6.6 Update server and security cadence

- **Origin:** static files, `https://<update-host>/blackbird-os/<sku>/<channel>/index.json` (hostname not decided). The index is signed (minisign or JWS) and lists version, `compatible`, the bundle URL + SHA-256, minimum source version (if any) and release-notes URL.
- **Bundle hosting:** RAUC streaming needs **HTTP Range** support and benefits from HTTP/2. GitHub Release downloads redirect to a CDN, and whether that serves Range reliably for streaming is **UNVERIFIED**. **Recommendation:** devices always fetch through the **package endpoint** configured in the image (SYS-011), which must serve HTTP Range. A recalled version disappears from the signed index, and the device refuses it.
- **Device-side client:** a small Rust `dap-updated` service. It polls the index, checks the signature, checks the battery/power policy, calls RAUC over D-Bus, reports progress to the UI and runs the health gate. No hawkBit is needed.
- **Security cadence without CI:** `blackbird-os/release/security-watch` (**proposal**) compares the latest release's `manifest.json` with the [Debian security tracker JSON](https://security-tracker.debian.org/tracker/data/json) (**UNVERIFIED** current URL). It prints affected packages and a suggested urgency. Run it weekly from a launchd/systemd timer on a maintainer's machine, or as a Claude Code skill. A hit triggers a point release (`2026.11.1`). Without this, the security response depends entirely on someone remembering. The maintainers should accept that risk explicitly.

---

## 7. On-device peripheral hosting (OS-008, BRD-004/005, HCS-013)

### 7.1 Principles

1. **Every programmable chip has a direct, SoC-owned path** for reset, boot-mode strap, debug (SWD or JTAG), console (UART), and where available USB. "Direct" means SoC GPIO/SPI/UART/USB pins, through passive level shifting or analog multiplexers (BRD-006 allows multiplexers), **never through another MCU's firmware**.
2. **One daemon owns these lines.** `dap-chipd` (name is a proposal) is a Rust service in `system`. It holds the GPIO lines (via the character device, e.g. the `gpiocdev` crate; trixie `libgpiod3` 2.2.1) and serialises access per chip. It exposes a bus API: `list`, `info`, `reset`, `enter-boot`, `flash` (signed firmware only, unless in developer mode), `console`, `debug-session` (starts a GDB/DAP server bound to localhost). It calls the backend tools below.
3. **Chip topology comes from data, not code:** a machine-readable **board description** (in `board`) and, for HATs, a **debug-topology section of the capability manifest** (in `hat-standard`). Both list chip, interface, pins/bus, IDs, tool and firmware source.

### 7.2 Tools to package in Blackbird OS

| Purpose | Tool | Upstream (2026-10-21) | Debian trixie | Recommendation |
|---|---|---|---|---|
| SWD/JTAG from SoC GPIO | **OpenOCD** `linuxgpiod` | release 0.12.0 (2023); master has libgpiod v2 (2025-09-27 commits) | 0.12.0-3+b2, **libgpiod backend disabled** | Package OpenOCD from a pinned master commit as `opendap-openocd` (configure `--enable-linuxgpiod --enable-linuxspidev`) |
| SWD over a SPI controller (faster) | **OpenOCD `linuxspidev`** | master (fixes up to 2026-10-01) | not in 0.12 | Wire SWD targets to a SoC SPI controller where speed matters (1 kΩ MOSI→SWDIO, MISO on SWDIO, SCK→SWCLK; "works well … up to 3 MHz" per docs) |
| RP2040/RP2350 debug + flash over SWD | OpenOCD `target/rp2040.cfg`, `rp2350.cfg`, flash driver `rp2xxx` | master (RP2350 since 2025-04) | not in 0.12 for RP2350 | same package |
| Rust-native debug (USB probes) | **probe-rs** | 0.32.0 | not packaged | Package from crates.io for USB-probe scenarios and as the IDE DAP server. Long term, contribute a gpiod/spidev SWD probe so it can replace OpenOCD on the SoC |
| RP USB BOOTSEL / UF2 / partitions / OTP | **picotool** | 2.3.1 | 2.1.1+dfsg-1 | Package 2.3.1 (RP2350 partition/TBYB features); check RP2350-A4 support |
| DFU devices | dfu-util | 0.11 | 0.11-3 | Debian package |
| FPGAs (JTAG) | **openFPGALoader** (`libgpiod` cable, `xvc-server`) | v1.2.0 (2026-10-18) | 0.13.1-1 | Package v1.2.0, built with libgpiod (check that its build supports libgpiod v2, **UNVERIFIED**) |
| FPGAs (slave SPI: iCE40, ECP5) | small Rust loader in `dap-chipd` (spidev + gpiod for CRESET/CDONE/PROGRAMN) | n/a | `SPI_SPIDEV=y` in the Debian kernel | Kernel FPGA Manager is **off** in Debian (`CONFIG_FPGA` not set), so userspace it is |
| SPI NOR flash attached to MCUs/FPGAs | **flashrom** `linux_spi`, `linux_mtd` | v1.8.0 | 1.4.0-3 (forky 1.8.0) | Debian package; target held in reset with its SPI pins tri-stated (needs a mux or series resistors, section 7.4) |
| Rockchip SoC on a HAT | `rockusb` (Rust) | 0.4.0 | n/a | Package (also used by `dap flash`) |
| Other SoCs on HATs | `sunxi-tools` (FEL), `uuu` (NXP), `rpiboot` (Raspberry Pi) | n/a | sunxi-tools 1.4.2 in trixie; uuu, rpiboot **not found** in trixie arm64 madison | Package on demand, per HAT |
| STM32 (if used) | probe-rs / OpenOCD; `stlink-tools` | n/a | 1.8.0 | as needed |
| ESP32 (if used) | `esptool` | n/a | **UNVERIFIED** | as needed |
| UART consoles | `tio` 3.9 | n/a | 3.9-1 | Debian package; `dap-chipd` multiplexes consoles to the bus and over SSH |
| HAT ID EEPROM | kernel `at24` (`EEPROM_AT24=m`) + nvmem | n/a | in kernel | Write-protect (WP) under SoC GPIO control |
| USB-attached device firmware via a framework | **fwupd** | 2.1.8 | 2.0.20 (backports 2.1.7) | See 7.6 |
| Logic/protocol debugging | sigrok-cli 0.7.2 | n/a | yes | optional, dev image only |

### 7.3 What the board must wire, per programmable chip

**Recommendation** (hand over to `board` and `hat-standard`):

| Signal | To the SoC via | Purpose |
|---|---|---|
| SWCLK / SWDIO (or TCK/TMS/TDI/TDO) | SoC GPIOs; for fast SWD, a SoC SPI controller (SCK, MOSI through 1 kΩ, MISO) | debug, flash, recovery independent of target firmware |
| nRESET / RUN | SoC GPIO, open-drain | reset, hold in reset during SPI-flash access |
| Boot strap (RP: QSPI_CSn "BOOTSEL"; STM32: BOOT0; ESP32: IO0; SoCs: maskrom/recovery) | SoC GPIO, through a resistor so the target's own use of the pin is unaffected | enter ROM bootloader (USB/UART boot) |
| UART TX/RX | a dedicated SoC UART (the RK3566 has many UART controllers, but pin-mux availability depends on the final design, **UNVERIFIED**) | console, UART boot (RP2350 UART boot uses QSPI SD2/SD3, so check whether tapping these is acceptable on the QSPI bus) |
| USB D+/D− | SoC USB host, through a hub where needed | USB BOOTSEL/DFU/UF2, runtime USB |
| Power enable | SoC GPIO-controlled load switch | power-cycle a stuck chip (also BRD-008) |
| SPI flash of the chip | SoC SPI through an analog mux or series resistors | flashrom while the chip is in reset |

Electrical notes:

- RK3566 I/O domains are 1.8 V or 3.3 V per bank. Bidirectional SWDIO needs a level translator that works with open-drain/bidirectional lines, or same-voltage domains. The choice belongs to the board research (**UNVERIFIED** part choice).
- Multiple targets on one SWD/JTAG pair are possible:
  - **SWD multidrop**: RP2040, and OpenOCD's `dap create … -dp-id -instance-id`;
  - a **JTAG chain** for FPGAs/CPLDs;
  - an **analog mux** selected by SoC GPIOs. Allowed, and it keeps the helper MCU out of the path.
- The HAT interconnect benchmark already budgets a 5-pin SWD/JTAG group (TCK/SWCLK, TMS/SWDIO, TDI, TDO/SWO, nRESET). **Recommendation:** add a **HAT_BOOT#** strap line, and treat the UART group as the per-HAT console. With more than one chip on a HAT, the HAT provides an analog mux whose select lines the SoC drives over the ID I2C bus through a simple GPIO expander. An I2C GPIO expander is not a programmable MCU, so it does not violate BRD-005. The manifest describes the topology.

### 7.4 HAT capability manifest: debug topology (proposal for `hat-standard`)

```text
chips:
  - id: mcu0
    kind: mcu
    part: RP2350A            # free text + optional JEDEC/ARM IDs
    debug: { transport: swd, bus: hat-swd, mux: { expander: 0x20, select: 1 }, multidrop: null }
    reset: hat-nreset
    boot: { strap: hat-boot, mode: rp-bootsel }
    console: hat-uart
    usb: hat-usb2
    firmware: { source: "https://vendor.example/.well-known/opendap/firmware/mcu0/index.json", signing: <key-id> }
  - id: fpga0
    kind: fpga
    part: iCE40UP5K
    config: { transport: spi-slave, bus: hat-spi, cs: 1, creset: hat-gpio3, cdone: hat-gpio4 }
```

The manifest is signed (HCS-010), and `dap-chipd` only acts on verified manifests. In developer mode, the user can also act on an unsigned local override.

### 7.5 A second SoC on a HAT

**Recommendation:** treat the HAT SoC like the T1 treats itself.

1. Wire its **USB OTG** to the T1's USB host, and its **maskrom/recovery strap**, **reset**, **power enable** and **debug UART** to the SoC, as in the table in 7.3.
2. **Boot over USB from Blackbird OS:**
   - Rockchip: `rockusb` with a usb471/usb472 pair;
   - Allwinner: `sunxi-fel`;
   - NXP: `uuu`;
   - Raspberry Pi: `rpiboot`;
   - then either flash its eMMC (via its own U-Boot `ums`/`rockusb`) or keep it **USB-booted every time** (RAM-only, so the T1 owns the companion's software entirely).
3. Runtime link: the companion runs a **USB gadget CDC-NCM** network to the T1 (NCM, not RNDIS). The T1 can serve its root over NBD/NFS (`BLK_DEV_NBD=m` in the Debian kernel).
4. The companion's image is built from the **same mkosi definition** with another profile, and versioned and signed like the T1 image. The HAT manifest references it by capability ID.

### 7.6 Firmware update framework: fwupd or our own?

- fwupd 2.1.8 has plugins that match parts of our needs: **`rp-pico`** (resets a Pico-SDK device into the bootrom via a USB reset interface, then updates through the **`uf2`** plugin), `dfu`, `ti-tps6598x` (USB-PD controllers), `emmc`, `mtd`, `gpio` ([plugin list 2.1.8](https://github.com/fwupd/fwupd/tree/2.1.8/plugins); [rp-pico README](https://fwupd.github.io/libfwupdplugin/rp-pico-README.html)). `rp-pico` is present in trixie's 2.0.20.
- fwupd supports **custom remotes** (`MetadataURI=`, `FirmwareBaseURI=`) instead of LVFS ([fwupd-remotes.d](https://github.com/fwupd/fwupd/blob/2.1.8/docs/fwupd-remotes.d.md)). Metadata is signed with jcat (**UNVERIFIED** details for trusting a custom key).
- **But** fwupd plugins are in-tree C, and there is no SWD-over-GPIO, slave-SPI-FPGA or UART-boot plugin. Those paths would mean writing and upstreaming C plugins.

#### Recommendation

- `dap-chipd` is the **single** firmware-update authority, with its own signed firmware index. It reuses the capability manifest signature scheme and per-publisher keys, so one trust model covers both.
- Where a USB device already speaks UF2/DFU/rp-pico, `dap-chipd` may delegate to fwupd's plugins through `fwupdmgr`/D-Bus with a local custom remote. Or it calls picotool/dfu-util directly, which is simpler and needs no metadata translation. Start direct; reconsider fwupd if third-party USB peripherals with LVFS firmware become common.
- LVFS publication is optional and later.

### 7.7 Updating the RP coprocessor safely (BRD-015)

**Recommendation: choose an RP2350-family part** (BRD-014 leaves it open). The RP2040 bootrom has no A/B, signed boot or TBYB, so it would need a custom second-stage bootloader to get the same safety.

Update flow, normal path (no physical intervention):

1. The firmware image is built in `board/firmware`, then `picotool seal --sign` (secp256k1). It carries a version (rollback counter in OTP if anti-rollback is used) and the **TBYB** flag.
2. `dap-chipd` writes the image to the **inactive A/B partition**. Three transports work:
   - the running firmware's update protocol over the SoC UART/SPI link;
   - USB BOOTSEL + `picotool load -p <partition>`;
   - OpenOCD SWD.
   Then it triggers a **FLASH_UPDATE** reboot.
3. The bootrom boots the new partition under a watchdog. The firmware must complete its self-test **and** a handshake with Linux (`dap-chipd` confirms the protocol version), then call `explicit_buy()` within **16.7 s**. Otherwise the bootrom reverts to the previous partition on the next boot ([RP2350 datasheet §5.1.17](https://datasheets.raspberrypi.com/rp2350/rp2350-datasheet.pdf)).

Recovery paths, in order:

- **(a) USB BOOTSEL:** the SoC holds QSPI_CSn low, pulses RUN, then `picotool load`.
- **(b) SWD from the SoC** (OpenOCD `rp2350.cfg` + `rp2xxx` flash driver). This works whatever the flash contents are.
- **(c) UART boot** (QSPI_CSn low + QSPI SD1 high, 1 Mbaud on SD2/SD3, SRAM-only boot, §5.8) as a last resort, if those pins are reachable.

Safety constraints for the board:

- The SoC must **boot and run without the RP firmware**. The PMIC power-on and the SoC reset must not depend on RP firmware, or a failed update locks out the very host that would fix it.
- If the RP drives power sequencing, its pins need safe defaults (pull resistors) while the RP is in reset or BOOTSEL.
- Do not disable SWD via OTP in production without a documented re-enable or debug-key path (RP2350 secure debug options, **UNVERIFIED** details).

### 7.8 Developer experience for chips

- `dap chip ls`, `dap chip flash mcu0 fw.elf`, `dap chip reset mcu0`, `dap chip console mcu0`.
- `dap chip debug mcu0` starts OpenOCD's GDB server (or probe-rs's DAP server) on the device. It forwards `localhost:3333` over SSH, so `probe-rs`/`arm-none-eabi-gdb`/VS Code on the Mac attach as if the probe were local.
- In QEMU and containers there are no real lines. The virtual targets test `dap-chipd` against a **fake backend**, and a USB-passthrough probe or a real reference board covers the rest. QEMU `usb-host` passthrough on macOS (Homebrew QEMU links libusb) is **UNVERIFIED** for reliability.

---

## 8. End-to-end flow

```text
 developer machine (macOS/Linux, no CI)                                         package endpoint (static HTTP)  
 ───────────────────────────────────────                                         ──────────────────────────────
 system/ (Rust)  ──cargo test──► cargo-deb ──► aptly repo "dap" ──snapshot──┐
 board/  (DTS, RP fw) ─► dap-t1-dtb.deb, rp-fw (picotool seal --sign) ──────┤
 blackbird-os/overlays ─► blackbird-os-config.deb ──────────────────────────────────────┤
 hats/*, faceplates/* ─► signed firmware + manifests ───────────────────────┼──► firmware index / capability repo
                                                                            │
 blackbird-os/image (mkosi) + Debian Snapshot= + aptly snapshot ──────────────────┘
        │  (builder VM: Lima vz, arm64 native)
        ├─► profile oci  ──► OCI image ──► docker/OrbStack/nspawn: service tests
        ├─► profile qemu ──► disk image ──► QEMU+HVF (fast: UKI; fidelity: U-Boot) ── OTA/rollback tests
        └─► profile t1   ──► disk image + FIT (signed) + U-Boot ──► dap flash ──► reference board / T1
                                   │
                           dap release: double build + diffoscope, sign (tokens), SBOM, notes, sources
                                   │
                                   ├─► GitHub Release (img.zst+bmap, raucb, usb471/472, qemu, oci, SBOM, SHA256SUMS.minisig)
                                   ├─► aptly publish (InRelease signed) ───────────────────────────► <apt-host>
                                   └─► signed update index (channel) ──────────────────────────────► <update-host>
                                                                                                         │
 device (T1, Blackbird OS)                                                                                     │ via package endpoint
 ───────────────────                                                                                     │ (HTTP Range, recalls)
 dap-updated ──poll index──► RAUC stream install (adaptive) ──► U-Boot bootmeth_rauc try ──► health gate ─┴─ mark-good / rollback
 orchestrator ──HAT EEPROM manifest verify──► capability fetch (well-known HTTP) ──► sandboxed run
 dap-chipd ──board description + HAT manifest──► OpenOCD/picotool/openFPGALoader/flashrom/rockusb ──► every chip
```

### 8.1 Repository and tool responsibilities (recommendation)

| Repo | Owns |
|---|---|
| **blackbird-os** | mkosi definition and profiles, repart layout, `packages.lock`, `blackbird-os-config` package (from `overlays/`), RAUC `system.conf` + public keyring, U-Boot boot script source, FIT assembly script, `release/` scripts (build, sign, SBOM, notes, sources, publish, security-watch), update-index format, public key fingerprints, release records in `docs/` |
| **system** | Rust services, orchestrator, UI, SDK; `dap-updated`, `dap-chipd`, capability runtime + manifest verification; cargo-deb metadata; bus/API schemas that capabilities depend on |
| **toolkit** | `dap` CLI (`crates/dap`: builder, build, vm, ssh, console, deploy, debug, flash, chip, release wrappers); `host/setup.sh` + Brewfile additions (lima, rockusb, mkosi provisioning for the builder VM, QEMU EDK2/U-Boot firmware); pre-commit hooks (mkosi config check, `cargo deny`, REUSE); udev rules for Linux hosts |
| **board** | T1 device tree + overlays (`dap-t1-dtb` package), board description (chips, wiring, debug topology), RP coprocessor firmware + its signing manifest, flashing/recovery hardware requirements (MaskROM button, recovery key, OTG, debug lines) |
| **hat-standard** | EEPROM layout, capability manifest schema including the debug-topology section, signing scheme, HAT_BOOT#/SWD/UART pin roles |
| **hats/***, **faceplates** | Chip firmware sources, signed release artifacts, EEPROM manifest content, HAT DT overlays (first-party), companion-SoC image profiles if any |
| **claude-plugins** | Claude Code skills wrapping the above (`/blackbird-os:build`, `/blackbird-os:release`, `/blackbird-os:release-notes`, `/dap:flash`, `/blackbird-os:security-watch`), **proposal** |
| **rfcs** | Cross-repo decisions coming out of this report (key hierarchy, update model, capability bundle format) |
| boot chain (separate research) | U-Boot/TF-A/rkbin builds, usb471/472 images, FIT verification config, optional OTP locking. Possibly a dedicated `boot-firmware` repo, as the toolkit report suggests |

---

## 9. Recommendations, in order

1. Adopt **mkosi v27.1** with `t1`/`qemu`/`oci` profiles and a **Lima builder VM**. Prototype on a **reference RK3566 board** now.
2. Adopt **RAUC + U-Boot `bootmeth_rauc`** with verity bundles, HTTP streaming and adaptive updates. Write the health gate early.
3. Use **erofs + dm-verity**, with the roothash carried in the signed FIT/initramfs. Use the GPT A/B layout of 4.2.
4. Build **aptly** + `cargo-deb` packaging, `Snapshot=` pinning, and a per-release source archive.
5. Build **`dap flash` on `rockusb`** with U-Boot usb471/472 images. The board needs a MaskROM button, a recovery key and USB-C OTG.
6. Set up the key hierarchy on **hardware tokens**, with separate dev keys and `compatible` strings.
7. Package **OpenOCD from git** (linuxgpiod v2 + linuxspidev), plus picotool 2.3.1 and openFPGALoader 1.2.0, in the OpenDAP repo.
8. Write **`dap-chipd`** with a data-driven board description and HAT debug-topology manifest.
9. Prefer an **RP2350-family** coprocessor, with TBYB A/B updates and SoC-driven SWD/BOOTSEL recovery. The SoC must boot without RP firmware.
10. Add a weekly **security-watch** routine as the CI substitute for Debian security updates.

## 10. Open questions for the maintainers

- **Q1.** Does "updates from the Linux distribution repositories" (OS-013) accept Debian updates delivered **inside signed images**, with apt only in developer mode?
- **Q2.** Should Blackbird OS be verified-but-unlocked (user-ownable keys, no OTP fuse), or offer an irreversible locked mode? (Boot-chain research.)
- **Q3.** U-Boot update strategy: does the RK3566 BootROM try backup idbloader copies? Is SPI NOR planned as a separate boot medium? (Boot-chain research, **UNVERIFIED**.)
- **Q4.** How are third-party HAT device-tree overlays trusted, given that U-Boot applies overlays and they are not part of the image's signed FIT?
- **Q5.** Does the T1 have an SD card slot (end-user flashing and recovery path)? What eMMC size (sets the A/B slot sizes)?
- **Q6.** Exact RP part (RP2350A/B, or a stacked-flash variant, **UNVERIFIED** availability) and which pins the SoC owns (QSPI_CSn, RUN, SWD, UART, USB).
- **Q7.** The early serial console: a dedicated USB-UART bridge chip, debug pads only, or SoC USB-ACM only after boot? Is routing it through the RP acceptable under BRD-005?
- **Q8.** Capability bundle format: erofs + verity image vs plain tree, and whether first-party capabilities may use `systemd-sysext`.
- **Q10.** Is fwupd wanted as a user-visible framework (GNOME Firmware, LVFS), or is `dap-chipd` alone enough?

## 11. Items to verify next (from this report)

- systemd as PID 1 under Apple `container` and OrbStack (exact flags).
- U-Boot `qemu_arm64` booted under HVF.
- macOS CDC-NCM support.
- Collabora `rockusb` against U-Boot's rockusb gadget (write-bmap).
- The RK3566 MaskROM entry method and the BootROM boot order.
- How mkosi handles trixie-security with `Snapshot=`.
- erofs block-reuse with RAUC adaptive updates.
- Whether the openFPGALoader 1.2.0 build supports libgpiod v2.
- Achievable SWD clock with OpenOCD linuxgpiod vs linuxspidev on the RK3566.
- fwupd custom-remote key trust.
- Whether GitHub Releases' CDN serves Range requests reliably for RAUC streaming.
- The Debian security tracker JSON URL.
- `cargo-zigbuild`, `cargo auditable` and `diffoscope` versions.
