# OpenDAP OS requirements

Requirements for the OpenDAP OS distribution.

| ID | Requirement | Priority | Status |
|---|---|---|---|
| OS-001 | OpenDAP OS shall run a mainline Linux kernel, version 7 or later. | must | Confirmed |
| OS-002 | OpenDAP OS shall not require custom kernel builds. | must | Confirmed |
| OS-003 | OpenDAP OS shall stay desktop-style, not embedded-style. | must | Confirmed |
| OS-004 | OpenDAP OS shall be a trimmed image, tuned for the T1 SoC and hardware. | must | Confirmed |
| OS-005 | OpenDAP OS shall start from executable prebuilt images and packages of its base distribution, modified into a custom image. | must | Confirmed |
| OS-006 | OpenDAP OS shall not require embedded-style builds: no Buildroot or Yocto, and no compiling the kernel or the toolchain. | must | Confirmed |
| OS-007 | The kernel shall be updatable as a prebuilt package. | should | Draft |
| OS-008 | OpenDAP OS shall be the real host of all peripheral hardware on the board and on HATs: it shall flash, operate and debug every programmable chip (microcontrollers, FPGAs, other SoCs), including the board's RP coprocessor. | must | Confirmed |
| OS-009 | Developers shall be able to run OpenDAP OS on their host machine (container or QEMU), connect to it and control it, and change it through code and configuration files. | must | Confirmed |
| OS-010 | OpenDAP OS shall be built up from code and configuration, with OpenDAP software and drivers preinstalled, into a final image. | must | Confirmed |
| OS-011 | Images shall be signed, versioned and published as releases. | must | Confirmed |
| OS-012 | Flashing a release image shall be simple and direct. | must | Confirmed |
| OS-013 | OpenDAP OS shall receive updates both from the Linux distribution repositories and from OpenDAP software repositories. | must | Confirmed |
| OS-014 | OpenDAP OS should support over-the-air (OTA) updates. | should | Draft |
| OS-015 | Development tools that are not for end users (for example OpenOCD) shall come from a separate OpenDAP repository: available and tested on the device, not installed by default. | must | Confirmed |
| OS-016 | Headless development and automation shall run on QEMU; UI work may use UTM. | must | Confirmed |
| OS-017 | Recovery: the device shall be recoverable from MaskROM, and A/B updates shall roll back automatically when a new version fails. | must | Draft |
| OS-018 | The virtual T1 (QEMU) shall mimic the T1 hardware as closely as possible: 320 × 480 portrait display, the four buttons, audio output, battery, and the coprocessor and HAT presence where they can be emulated. | must | Confirmed |
| OS-019 | Running instances (virtual or real) shall be controllable remotely: a remote desktop, and headless automation over SSH (screenshots, input injection, scripted UI flows). | must | Confirmed |
| OS-020 | Playback shall be bit-perfect, including DSD (native and DoP). | must | Confirmed |
| OS-021 | The default image shall contain only what is mandatory; optional components (for example LLVM) shall be installable from the OpenDAP repositories instead. | must | Confirmed |
| OS-022 | The T1 shall use SD/TF storage both directly and through cache or preload levels in eMMC and RAM. | must | Confirmed |

## Context

- Base distribution: Debian trixie with the backports kernel ([ADR 0002](../adr/0002-debian-trixie-with-backports-kernel.md)).
- OS-017: Adopted from the earlier experiments on 2026-10-21 as **Draft**: consistent with the decisions already taken and with the product philosophy, pending the maintainers' confirmation. Part availability still has to be checked against the sourcing rule (T1-010).
- The virtual T1 emulates the battery with the kernel's `test_power` module, built at image time against the image's own kernel headers (qemu profile only, [ADR 0007](../adr/0007-kernel-modules-through-dkms.md)): `test_battery`, `test_ac` and `test_usb` appear in `/sys/class/power_supply`, driven through `/sys/module/test_power/parameters/` (capacity, status, AC/USB online, voltage, current).
- Pending: deep suspend (suspend-to-RAM) on the RK3566 depends on mainline TF-A support, not verified yet. Not a priority for now, but must be revisited.
- Audio direction from the image-composition research: PipeWire processes audio as 32-bit float, so bit-perfect 32-bit PCM and DSD need a playback engine with exclusive, direct ALSA access, next to PipeWire for shared use.
- Image size: acceptable as long as it works well and is not excessive for the device; reduce further only if needed. Dropping LLVM by default may require an OpenDAP build of Mesa limited to Panfrost, because Debian's Mesa depends on LLVM.
- **T1 hardware needs from board BOM v1.1** (`board/docs/specs/bom-v1.md`), to carry into the image:
  - DKMS modules ([ADR 0007](../adr/0007-kernel-modules-through-dkms.md)): `cs43130` (CS43198 DACs), `max17042_battery` (MAX17055 fuel gauge), `nxpwifi` and `btnxpuart` (IW612), and `panel-ilitek-ili9488` for the touch faceplate display until Debian ships a kernel ≥ 7.3.
  - BQ25895 charger: its watchdog restores a 2048 mA charge current when it expires, so the charger driver or an OpenDAP OS service must keep it serviced or disable it. Whether the mainline `bq25890_charger` driver does this is **UNVERIFIED**.
  - INA236 current monitors power up converting continuously; they are configured at boot.
  - RP2354A coprocessor firmware must select 1.8 V I/O (`VOLTAGE_SELECT = 1`).
- OS-020 scope (maintainers, 2026-10-22): bit-perfect up to DSD256 on the on-board outputs and up to the external DAC's limit over USB; higher DSD rates on-board are converted and labelled ([ADR 0006](../adr/0006-native-dsd-through-upstream-driver-work.md), [DSD512 research](../research/2026-10-dsd512.md)).
