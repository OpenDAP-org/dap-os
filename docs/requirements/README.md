# Blackbird OS requirements

Requirements for the Blackbird OS distribution.

| ID | Requirement | Priority | Status |
|---|---|---|---|
| OS-001 | Blackbird OS shall run a mainline Linux kernel, version 7 or later. | must | Confirmed |
| OS-002 | Blackbird OS shall not require custom kernel builds. | must | Confirmed |
| OS-003 | Blackbird OS shall stay desktop-style, not embedded-style. | must | Confirmed |
| OS-004 | Blackbird OS shall be a trimmed image, tuned for the T1 SoC and hardware. | must | Confirmed |
| OS-005 | Blackbird OS shall start from executable prebuilt images and packages of its base distribution, modified into a custom image. | must | Confirmed |
| OS-006 | Blackbird OS shall not require embedded-style builds: no Buildroot or Yocto, and no compiling the kernel or the toolchain. | must | Confirmed |
| OS-007 | The kernel shall be updatable as a prebuilt package. | must | Draft |
| OS-008 | Blackbird OS shall be the real host of all peripheral hardware on the board and on HATs: it shall flash, operate and debug every programmable chip (microcontrollers, FPGAs, other SoCs), including the board's RP coprocessor. | must | Confirmed |
| OS-009 | Developers shall be able to run Blackbird OS on their host machine (container or QEMU), connect to it and control it, and change it through code and configuration files. | must | Confirmed |
| OS-010 | Blackbird OS shall be built up from code and configuration, with OpenDAP software and drivers preinstalled, into a final image. | must | Confirmed |
| OS-011 | Images shall be signed, versioned and published as releases. | must | Confirmed |
| OS-012 | Flashing a release image shall be simple and direct. | must | Confirmed |
| OS-013 | Blackbird OS shall receive updates both from the Linux distribution repositories and from OpenDAP software repositories. | must | Confirmed |
| OS-014 | Blackbird OS should support over-the-air (OTA) updates. | should | Draft |
| OS-015 | Development tools that are not for end users (for example OpenOCD) shall come from a separate OpenDAP repository: available and tested on the device, not installed by default. | must | Confirmed |
| OS-016 | Headless development and automation shall run on QEMU; UI work may use UTM. | must | Confirmed |
| OS-017 | Recovery: the device shall be recoverable from MaskROM, and A/B updates shall roll back automatically when a new version fails. | must | Draft |
| OS-018 | The virtual T1 (QEMU) shall mimic the T1 hardware as closely as possible: 320 × 480 portrait display, the four buttons, audio output, battery, and the coprocessor and HAT presence where they can be emulated. | must | Confirmed |
| OS-019 | Running instances (virtual or real) shall be controllable remotely: a remote desktop, and headless automation over SSH (screenshots, input injection, scripted UI flows). | must | Confirmed |
| OS-020 | Playback shall be bit-perfect, including DSD (native and DoP). | must | Confirmed |
| OS-021 | The default image shall contain only what is mandatory; optional components (for example LLVM) shall be installable from the OpenDAP repositories instead. | must | Confirmed |
| OS-022 | The T1 shall use SD/TF storage both directly and through cache or preload levels in eMMC and RAM. | must | Confirmed |
| OS-023 | Blackbird OS shall provide its own optimised builds of Linux packages where that serves the device (tuned for the SoC, trimmed dependencies, patches carried until upstream), from the OpenDAP repositories, instead of relying only on stock distribution packages. | must | Confirmed |
| OS-024 | The default image shall contain only OpenDAP's own ecosystem. Third-party software is never installed by default. Advanced packages outside the audiophile core (for example the software of special HATs) shall come from a separate OpenDAP repository and are not installed by default. | must | Confirmed |
| OS-025 | If verified boot is ever enforced, the owner shall be able to enrol their own keys or turn enforcement off, without losing data. | must | Confirmed |
| OS-026 | MQA files shall play as plain PCM, with no MQA decoding or rendering. | must | Confirmed |
| OS-027 | Third-party services and certifications (AirPlay, Roon Ready, Spotify, Tidal or Qobuz Connect, an LDAC receiver) are not part of the official image by default; each is evaluated on its own (SYS-035). | must | Confirmed |
| OS-028 | Blackbird OS shall be derivable: a third party shall be able to build its own distribution based on it, kept apart from it, changing the identity, themes, drivers, packages and configuration without patching the Blackbird OS image definition, the way Blackbird OS is based on Debian. | must | Confirmed |

## Open questions

- OS-028: how derivatives may use the Blackbird OS and OpenDAP names (for example "based on Blackbird OS"), and whether they may use the OpenDAP package repositories or need their own; their release signing keys are their own.

## Context

- OS-028 (maintainers, 2026-10-23): custom distributions based on Blackbird OS (themes, drivers and so on) are expected if the project grows; the repository has to be ready for them. Guide: [`derivatives.md`](../derivatives.md); decision: [ADR 0012](../adr/0012-derivable-image-definition.md).
- OS-023 (maintainers, 2026-10-22): the intent is OpenDAP's own optimised versions of Linux packages, not only stock packages. Debian stays the base (ADR 0002); optimised builds are published as normal packages in the OpenDAP repositories, reproducible and with their sources.
- Base distribution: Debian trixie with the backports kernel ([ADR 0002](../adr/0002-debian-trixie-with-backports-kernel.md)).
- Name and versions ([ADR 0011](../adr/0011-blackbird-os.md), superseding ADR 0009 and ADR 0010): the system is Blackbird OS; releases are identified by version number, with no codenames.
- OS-017: Adopted from the earlier experiments on 2026-10-21 as **Draft**: consistent with the decisions already taken and with the product philosophy, pending the maintainers' confirmation. Part availability still has to be checked against the sourcing rule (T1-010).
- The virtual T1 emulates the battery with the kernel's `test_power` module, built at image time against the image's own kernel headers (qemu profile only, [ADR 0007](../adr/0007-kernel-modules-through-dkms.md)): `test_battery`, `test_ac` and `test_usb` appear in `/sys/class/power_supply`, driven through `/sys/module/test_power/parameters/` (capacity, status, AC/USB online, voltage, current).
- Pending: deep suspend (suspend-to-RAM) on the RK3566 depends on mainline TF-A support, not verified yet. Not a priority for now, but must be revisited.
- Audio direction from the image-composition research: PipeWire processes audio as 32-bit float, so bit-perfect 32-bit PCM and DSD need a playback engine with exclusive, direct ALSA access, next to PipeWire for shared use.
- Image size: acceptable as long as it works well and is not excessive for the device; reduce further only if needed. Dropping LLVM by default may require an OpenDAP build of Mesa limited to Panfrost, because Debian's Mesa depends on LLVM.
- **T1 hardware needs from board BOM v1.1, updated for BOM v1.5** (`board/docs/specs/bom-v1.md`), to carry into the image:
  - DKMS modules ([ADR 0007](../adr/0007-kernel-modules-through-dkms.md)): `cs43130` (CS43198 DACs), `bq27xxx_battery` with its I2C front end (`BATTERY_BQ27XXX_I2C`, not set in Debian's arm64 kernel) for the BQ28Z610-R1 fuel gauge, `bq257xx` (MFD and charger; `MFD_BQ257XX` and `CHARGER_BQ257XX` not set in Debian) for the BQ25798 charger with its device ID added until upstream accepts it (board BOM v1.5, [board ADR 0014](https://github.com/opendap-project/board/blob/main/docs/adr/0014-two-cell-battery.md), OS-023; Debian facts from the [board 2S pre-freeze note](https://github.com/opendap-project/board/blob/main/docs/research/2026-10-battery-2s-prefreeze.md)), `nxpwifi` and `btnxpuart` (IW612), and `panel-ilitek-ili9488` for the touch faceplate display until Debian ships a kernel ≥ 7.3.
  - BQ25798 charger (board BOM v1.5; replaces the BQ25895): the mainline `bq257xx` charger init disables the charger watchdog (REG10 = 0), so settings persist if Linux hangs and there is no fallback to the power-on defaults; the board reviews this under BRD-049 (board 2S pre-freeze note). The device tree must not describe the charger's OTG output.
  - INA236 current monitors power up converting continuously; they are configured at boot.
  - RP2354A coprocessor firmware must select 1.8 V I/O (`VOLTAGE_SELECT = 1`).
- OS-020 scope (maintainers, 2026-10-22; revised the same day after the DSD research): on the on-board outputs, bit-perfect PCM up to 192 kHz, native DSD up to DSD256 and DoP up to DSD64, the limits of the SoC's I2S block and the CS43198; over USB, bit-perfect up to the external DAC's limit; anything above on-board is converted and labelled ([ADR 0006](../adr/0006-native-dsd-through-upstream-driver-work.md), [DSD512 research](../research/2026-10-dsd512.md)).
