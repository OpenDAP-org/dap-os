# OpenDAP OS: base distribution research

- **Date:** 2026-10-21
- **Status:** research, not a decision. Everything under "Recommendation" is a recommendation for the maintainers to decide on.
- **Scope:** pick the prebuilt distribution that OpenDAP OS (open-hardware handheld, Rust services, Slint/Wayland UI) gets its customized image from.

## 0. Constraints (from the maintainers)

1. The starting point is **executable prebuilt images and packages**, which we modify into a custom image. No Buildroot or Yocto. We do not compile the kernel or a toolchain.
2. **Mainline Linux ≥ 7.x**, ideally shipped as a distro package so that updating it is "just update the kernel".
3. A desktop-style system, not an embedded one: package manager, systemd (or similar), a Wayland compositor, Mesa, PipeWire, and Rust software on top.
4. SoC candidates: **NXP i.MX 8M Plus** (primary), **Rockchip RK3576**, **Rockchip RK3566**.
5. Board support comes only from **device tree plus overlays, applied by the bootloader**.

How this report marks evidence: a version string comes from a live query of the primary source on 2026-10-21, and the URL used is given next to it. Anything marked **UNVERIFIED** comes from memory or from secondary knowledge and was not checked against a primary source in this session. Web search was unavailable for part of the session, so some points are flagged for follow-up.

---

## 1. Key findings (read this first)

1. **Most mainstream distros already ship a kernel ≥ 7.** Mainline is 7.3 (released 2026-10-18), stable is 7.2.12 and the newest longterm is 6.18.58 ([kernel.org releases.json](https://www.kernel.org/releases.json)). Today every candidate except Debian *stable*, Alpine *v3.22/3.23 LTS* and Armbian *current* has a ≥7 kernel as a prebuilt arm64 package.
2. **The deciding factor for the primary SoC is the distro's kernel config, not the kernel version.** i.MX 8M Plus display needs `DRM_IMX_LCDIF` (LCDIFv3), `DRM_SAMSUNG_DSIM` (MIPI-DSI, which a handheld panel will very likely use), `DRM_IMX8MP_DW_HDMI_BRIDGE`, `DRM_IMX8MP_HDMI_PVI` and `PHY_FSL_SAMSUNG_HDMI_PHY`. A grep of each distro's arm64 config on 2026-10-21 gave:

   | Distro kernel config | LCDIF | DSIM (DSI) | 8MP HDMI | etnaviv | RK VOP2 + HDMI-QP | Panfrost | Rocket NPU |
   |---|---|---|---|---|---|---|---|
   | Fedora (kernel-ark `os-build`) | m | m | m | not checked (UNVERIFIED) | y / y | not checked (UNVERIFIED) | m |
   | postmarketOS `linux-postmarketos-stable` | m | m | m | m | y / y | m | not set |
   | openSUSE `kernel-source` arm64/default | m | **not set** | m | m | y / y | m | m |
   | Debian `debian/config/arm64/config` (+ `config`) | **absent** | **absent** | **absent** | m | y / y | m | absent |
   | Alpine `linux-stable` aarch64 | **absent** | **absent** | **absent** | m | y / y | m | m |
   | Arch Linux ARM `linux-aarch64` | **not set** | **not set** | **not set** | m | y / y | m | m |

   Sources: [kernel-ark configs](https://gitlab.com/cki-project/kernel-ark/-/tree/os-build/redhat/configs/fedora/generic/arm/aarch64), [pmaports linux-postmarketos-stable](https://gitlab.postmarketos.org/postmarketOS/pmaports/-/tree/main/device/main/linux-postmarketos-stable), [openSUSE kernel-source config/arm64/default](https://github.com/openSUSE/kernel-source/blob/master/config/arm64/default), [Debian kernel config](https://salsa.debian.org/kernel-team/linux/-/blob/debian/latest/debian/config/arm64/config), [Alpine stable.aarch64.config](https://gitlab.alpinelinux.org/alpine/aports/-/blob/master/community/linux-stable/stable.aarch64.config), [ALARM linux-aarch64 config](https://github.com/archlinuxarm/PKGBUILDs/blob/master/core/linux-aarch64/config).
   "Absent" means the symbol was not found in the files that were grepped. Debian's config is split across several files, so a featureset or flavour file could still set these symbols (**UNVERIFIED**, treat them as off until an actual `linux-image-arm64` `/boot/config-*` is checked).
   **So today, only Fedora and postmarketOS ship a generic kernel that drives the whole i.MX 8M Plus display pipeline, DSI included, without us changing the kernel.** For the RK3566 and RK3576, all the distros have VOP2, HDMI-QP and Panfrost enabled.
3. **No distro ships a prebuilt U-Boot for these SoCs that fits a custom board.** Every one of the three needs non-free DRAM-init blobs: the NXP LPDDR4 training firmware, or the Rockchip `rkbin` DDR TPL (and on RK3576 possibly BL31, **UNVERIFIED**). Debian's `u-boot-imx` and `u-boot-rockchip` contain no i.MX8M, RK356x or RK3576 targets ([targets.mk](https://salsa.debian.org/debian/u-boot/-/blob/debian/latest/debian/targets.mk)), and Fedora's `uboot-tools` contains none either ([aarch64-boards](https://src.fedoraproject.org/rpms/uboot-tools/blob/rawhide/f/aarch64-boards)). openSUSE ships `u-boot-quartz64-{a,b}-rk3566` and `u-boot-soquartz-*-rk3566` 2026.07 for reference RK3566 boards. On i.MX 8M Plus the DDR timing is board-specific anyway. **This is the single place where the "no builds" rule collides with reality.** Building U-Boot is a small cross-compile of a few minutes with a prebuilt distro cross-gcc, and it is unavoidable for a custom board unless the board copies a reference DDR layout exactly. Section 5 sets out how to keep it minimal.
4. **Mainline device-tree coverage at v7.3** (from [git.kernel.org v7.3 tree](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/arch/arm64/boot/dts?h=v7.3)):
   - **i.MX 8M Plus:** 114 `imx8mp*` .dts/.dtso files, of which 48 are overlays (`.dtso`, for example LVDS, DSI panels and cameras). `imx8mp.dtsi` describes GPU (`gpu@38000000`, `gpu@38008000`), NPU (`npu@38500000`) and two ISPs. Mainline U-Boot has many `imx8mp_*` defconfigs (`imx8mp_evk`, `imx8mp_debix_model_a`, `imx8mp_navqp`, `imx8mp_venice`, …), per the [u-boot configs](https://github.com/u-boot/u-boot/tree/master/configs).
   - **RK3576:** 15 boards, among them **`rk3576-anbernic-rg-vita-pro.dts` (a handheld)**, `rk3576-rock-4d`, `rk3576-armsom-sige5` and `rk3576-nanopi-m5`. `rk3576.dtsi` has `vop@27d00000`, `dsi@27d80000`, `hdmi@27da0000`, `gpu@27800000` and `video-codec@27b00000`, and `rockchip,rk3576-vop` is present in `rockchip_vop2_reg.c`. Mainline U-Boot has `generic-rk3576_defconfig`, `nanopi-m5-rk3576` and `nanopi-r76s-rk3576`. The listing was truncated at 1000 entries, so there may be more.
   - **RK3566:** 40 boards, among them **11 handhelds** (`anbernic-rg353p/ps/v/vs`, `rg503`, `rg-arc-d/s`, `powkiddy-rgb10max3/rgb20sx/rgb30/rk2023/x55`), `pinetab2` and `pinenote`. It is the most mature handheld SoC in mainline. Mainline U-Boot has `anbernic-rgxx3-rk3566_defconfig`, which covers a family of handhelds with a single generic image.

---

## 2. Kernel versions available today (prebuilt arm64)

All queried live on 2026-10-21.

| Distro / channel | Prebuilt arm64 kernel package | Version today | Source |
|---|---|---|---|
| **Debian 13 trixie** (stable) | `linux-image-arm64` | 6.12.107-1, with trixie-security at 6.12.113-1 | [madison](https://qa.debian.org/madison.php?package=linux-image-arm64&a=arm64) |
| **Debian trixie-backports** | `linux-image-arm64` | **7.2.9-1~bpo13+1** | same |
| **Debian forky** (testing) and **sid** | `linux-image-arm64` | **7.2.11-1** | same |
| Debian experimental | `linux` source | 7.3~rc7-1~exp1 | [sources.debian.org](https://sources.debian.org/src/linux/) |
| **Ubuntu 26.10** "stonking" (current stable) | `linux` | **7.3.0-9.9** | [Launchpad API](https://api.launchpad.net/devel/ubuntu/+archive/primary?ws.op=getPublishedSources&source_name=linux&exact_match=true&status=Published) |
| **Ubuntu 26.04 LTS** "resolute" | `linux` | **7.0.0-38.38** in -updates/-security, 7.0.0-39.39 in -proposed | same |
| **Fedora 44** | `kernel` | **7.2.11-200.fc44** (2026-10-15) | [Bodhi](https://bodhi.fedoraproject.org/updates/?packages=kernel&releases=F44) |
| Fedora 45 (frozen, pre-release) | `kernel` | 7.2.11-300.fc45 | [Bodhi](https://bodhi.fedoraproject.org/updates/?packages=kernel&releases=F45) |
| Fedora 43 | `kernel` | 7.2.11-100.fc43 | [mdapi](https://mdapi.fedoraproject.org/f43/pkg/kernel) |
| Fedora Rawhide | `kernel` | 7.3.0-65.fc46 (2026-10-19), then 7.4.0-0.rc0.20261021 | [Bodhi](https://bodhi.fedoraproject.org/updates/?packages=kernel) |
| **Alpine edge** | `linux-stable` / `linux-lts` | **7.2.11-r0** / 6.18.58-r0 | [pkgs.alpinelinux.org](https://pkgs.alpinelinux.org/packages?name=linux-stable&branch=edge&arch=aarch64) |
| Alpine v3.24 | `linux-stable` / `linux-lts` | 7.1.5-r0 / 6.18.58-r0 | same, `branch=v3.24` |
| Alpine v3.23 | `linux-stable` / `linux-lts` | 7.0.10-r0 / 6.18.58-r0 | same |
| (Alpine `linux-edge`) | not present in edge, v3.23 or v3.24 (last seen as 6.15.0 in v3.22) | n/a | same |
| **postmarketOS** (pmaports `main`) | `linux-postmarketos-stable` / `-mainline` / `-lts` | **7.2.11** / **7.3** / 6.18.57 | [pmaports](https://gitlab.postmarketos.org/postmarketOS/pmaports/-/tree/main/device/main) |
| postmarketOS v26.06 | `linux-postmarketos-stable` | 7.0.12 | pmaports branch `v26.06` |
| **Arch Linux ARM** | `linux-aarch64` | **7.2.11-1** | [archlinuxarm.org](https://archlinuxarm.org/packages/aarch64/linux-aarch64) |
| **openSUSE Tumbleweed** (ports) | `kernel-default`, `dtb-freescale`, `dtb-rockchip` | **7.2.11-1.1** | [download.opensuse.org](https://download.opensuse.org/ports/aarch64/tumbleweed/repo/oss/aarch64/) |
| **NixOS unstable** (nixpkgs `kernels-org.json`) | `linux_7_3`, `linux_7_2`, `linux_6_18` | **7.3**, 7.2.11, 6.18.57, testing 7.3-rc7 | [nixpkgs](https://github.com/NixOS/nixpkgs/blob/nixos-unstable/pkgs/os-specific/linux/kernel/kernels-org.json) |
| NixOS 26.05 | same file | 7.3, 7.2.11, 6.18.57 | branch `nixos-26.05` |
| **Armbian** rockchip64 | `linux-image-{current,edge,bleedingedge}-rockchip64` | branch major.minor **6.18 / 7.3 / 7.4**. The exact deb version could not be read because the apt index download timed out (**UNVERIFIED**) | [rockchip64_common.inc](https://github.com/armbian/build/blob/main/config/sources/families/include/rockchip64_common.inc) |
| Armbian imx8m | `linux-image-{current,edge}-imx8m` | 6.18 / 7.1 (edge lags) | [imx8_common.inc](https://github.com/armbian/build/blob/main/config/sources/families/include/imx8_common.inc) |
| Armbian rk35xx (RK3576 boards) | `linux-image-vendor-rk35xx` | **vendor 6.1 (`rk-6.1-rkr7.2`) / 6.12 (`rk-6.12-rkr1`)**, not mainline | [rockchip_vendor_common.inc](https://github.com/armbian/build/blob/main/config/sources/families/include/rockchip_vendor_common.inc) |
| **Mobian** | `linux-<ver>-rockchip` | newest rockchip build is 6.18 (7.2 only for some Qualcomm SoCs) | [repo.mobian.org pool](https://repo.mobian.org/pool/main/l/) |

### Cadence, from the data above

- Fedora, Arch Linux ARM, openSUSE TW, Alpine edge, pmOS and Debian sid all move to each new mainline-stable point release within days. They rebase to a new major version about 3–6 weeks after mainline releases it.
- Debian backports trails sid by about 1–3 weeks.
- Ubuntu ships a new major version only with each 6-month release, plus HWE kernels for the LTS.
- NixOS unstable carries the newest mainline release the same week.

---

## 3. Userspace stack versions (for the Wayland/Mesa/PipeWire stack)

| | Mesa | PipeWire | U-Boot (distro package) |
|---|---|---|---|
| Debian trixie / trixie-backports / sid | 25.0.7 / **26.1.6** / 26.1.6 | 1.4.2 / **1.6.9** / 1.6.9 | 2025.01 (exp: 2026.10~rc5) |
| Alpine v3.24 / edge | 26.1.6 / 26.2.5 | 1.6.8 / 1.6.9 | 2026.04 / 2026.10 (`u-boot-rockchip`, no `u-boot-imx`) |

Sources: [madison mesa](https://qa.debian.org/madison.php?package=mesa), [madison pipewire](https://qa.debian.org/madison.php?package=pipewire), [madison u-boot](https://qa.debian.org/madison.php?package=u-boot), [Alpine pkgs](https://pkgs.alpinelinux.org/packages?name=mesa&branch=edge&arch=aarch64).

Fedora, Arch, TW and NixOS carry current Mesa and PipeWire as a matter of course (**UNVERIFIED** exact versions).

GPU drivers in Mesa:

- i.MX 8M Plus: **etnaviv** (Vivante GC7000UL).
- RK3566 / RK3576: **Panfrost** (Mali-G52, Bifrost).
- The NPU path is Mesa **Teflon**: etnaviv for the i.MX8MP NPU, and the Rocket driver for Rockchip NPUs. Rocket's RK3576 coverage is **UNVERIFIED**, and no NPU node was found in `rk3576.dtsi` at v7.3.

---

## 4. Per-distribution assessment

### 4.1 Debian (13 trixie + trixie-backports kernel, or forky/sid)

- **Kernel:** 7.2.9 in trixie-backports and 7.2.11 in forky/sid, both as signed, generic `linux-image-arm64`. "Just update the kernel" works literally: `apt install -t trixie-backports linux-image-arm64`. The kernel is close to vanilla (Debian patches are few and mostly non-hardware). DTBs ship in the package (`/usr/lib/linux-image-<ver>/`).
- **SoC fit:**
  - RK3566 and RK3576: display (VOP2, HDMI-QP, DW-MIPI-DSI), Panfrost, Panthor, Hantro, rkvdec and Rockchip audio are all enabled. **Ready.**
  - i.MX 8M Plus: etnaviv, SAI, clocks and pinctrl are enabled, but LCDIF, DSIM and 8MP HDMI were **not found** in the config. **Not ready for display.** The fix is a config-enable MR to [kernel-team/linux on Salsa](https://salsa.debian.org/kernel-team/linux). Debian routinely accepts these: it lands in sid, then in backports within weeks. That stays within the "no compiling the kernel ourselves" rule.
- **Bootloader:** no usable prebuilt U-Boot for our SoCs, as shown in section 1.3. `u-boot-menu` writes `/boot/extlinux/extlinux.conf`. U-Boot's `sysboot`/PXE parser honours `fdt` and `fdtoverlays` lines, which is exactly our "overlays applied by the bootloader" model (**UNVERIFIED**: whether `u-boot-menu` exposes an overlay variable, or whether we template the `fdtoverlays` line ourselves).
- **Image workflow:** `mmdebstrap --architectures=arm64` builds a rootfs only from prebuilt .debs (it can run cross via qemu-user/binfmt or natively on an arm64 runner). Then `systemd-repart` or `genimage` produces the partitions. Alternatively, [mkosi](https://github.com/systemd/mkosi) with `Distribution=debian` does everything declaratively: it pins the snapshot, adds our .debs, and emits a disk image with A/B partitions.
- **Reproducibility:** excellent. [snapshot.debian.org](https://snapshot.debian.org/) lets a `SOURCE_DATE_EPOCH` and snapshot timestamp pin a build exactly, and Debian runs a reproducible-builds program.
- **Field updates:** apt itself for dev units. For products, the options are image-based A/B with `systemd-sysupdate` (mkosi integrates with it), or **RAUC** (packaged in Debian) with U-Boot bootcount/bootlimit. OSTree is packaged too but is less common on Debian.
- **libc:** glibc 2.41 in trixie. It is fully compatible with Rust's `aarch64-unknown-linux-gnu`, with Slint's Skia/FemtoVG renderers, and with any vendor userspace binaries.
- **Security lifetime:** trixie is supported by the security team until about mid-2028, and Debian LTS extends that to about 2030 (**UNVERIFIED** exact dates; see [debian.org/releases](https://www.debian.org/releases/) and [wiki.debian.org/LTS](https://wiki.debian.org/LTS)). Caveat: the *backports* kernel is not covered by the security team's DSAs. It gets fixes by tracking sid and new stable point releases, which is fast in practice.
- **Community:** the largest. Armbian, Mobian, Raspberry Pi OS and most SBC vendors build on it.
- **Compliance:** best in class. Every binary has a source package with a stable URL, plus snapshot.debian.org, so the GPL written offer can point at our pinned snapshot.
- **Fit:** very good. Rust services plus a compositor (for example cage, sway, labwc, or our own Smithay-based one; all in Debian except our own) plus Slint on Wayland.

### 4.2 Fedora (44 now, 45 imminent) aarch64

- **Kernel:** 7.2.11-200.fc44. Fedora rebases stable releases to every new mainline series. The kernel is close to vanilla, and the [kernel-ark](https://gitlab.com/cki-project/kernel-ark) config is the most complete for these SoCs: LCDIF, DSIM, 8MP HDMI, VOP2, HDMI-QP and Rocket are all enabled. **It is the only glibc distro whose stock kernel covers the i.MX 8M Plus display pipeline, DSI included, today.** Updating is just `dnf upgrade kernel`, or an image update.
- **Bootloader:** Fedora's aarch64 model is UEFI. U-Boot provides EFI (`bootefi`), and GRUB or systemd-boot loads the kernel. Board support is DT-from-firmware: U-Boot applies our overlays to its DT before the EFI handoff. Fedora also ships DTBs in `/boot/dtb-<ver>`. Fedora ships no U-Boot for our SoCs (section 1.3).
- **Image workflow:** mkosi (`Distribution=fedora`) or Fedora image-builder (osbuild) from prebuilt RPMs. For field updates, **bootc / OSTree** (Fedora IoT) gives atomic A/B-like updates with rollback out of the box.
- **Security lifetime:** about 13 months per release (F44 EOL 2027-06-02, F45 EOL 2027-11-24, per [Bodhi releases](https://bodhi.fedoraproject.org/releases/)). That means a yearly major rebase of the base, which is manageable with image-based updates but is real ongoing work.
- **libc:** glibc. **Compliance:** SRPMs for everything, with a good audit trail via Koji. **Community:** large on aarch64 servers. On embedded SBCs it is smaller than Debian, and handheld usage is rare.
- **Fit:** very good technically. The weak spot is the short lifecycle and the UEFI-on-U-Boot boot flow, which adds a layer to the overlay story.

### 4.3 postmarketOS (Alpine-based)

- **Kernel:** generic `linux-postmarketos-stable` 7.2.11, `-mainline` 7.3 and `-lts` 6.18.57 on `main`; v26.06 has 7.0.12. Its aarch64 config enables the full i.MX8MP display stack and Rockchip display, but not `VIDEO_ROCKCHIP_VDEC` and not Rocket.
- **SoC fit:** RK3566 handhelds and tablets (PineTab2, Anbernic RGxx3) are an active community area (**UNVERIFIED** current device-port status; the GitLab search API needs auth). The mainline-first policy matches our goal exactly. No RK3576 or i.MX8MP device ports were confirmed (**UNVERIFIED**).
- **Workflow:** `pmbootstrap` installs prebuilt apks into an image. A OpenDAP OS device package (`device-opendap-*`) would carry our DTB/overlays, deviceinfo and U-Boot binary. Alternatively, plain Alpine `apk --root … --initdb add` or `alpine-make-rootfs` from prebuilt packages.
- **UI stack:** Phosh, Plasma Mobile and Sxmo are available, but we would run our own compositor and Slint. systemd has been available as an option in postmarketOS since v24.12. The Alpine base itself uses OpenRC.
- **musl implications:**
  - Mesa and PipeWire work (Alpine ships both).
  - Rust works natively on `aarch64-unknown-linux-musl`, but the default malloc is slower (mitigate with mimalloc or jemalloc).
  - DNS and locale behave differently from glibc.
  - Prebuilt glibc-only binaries do not run. That covers vendor NPU/ISP userspace and the Skia prebuilts `skia-bindings` would download for Slint's Skia renderer; musl coverage there is **UNVERIFIED**, so plan on FemtoVG or the software renderer.
- **Lifetime:** pmOS stable releases every 6 months, and each Alpine release supports `main` for about 2 years (**UNVERIFIED**). Most device work happens on edge (rolling).
- **Compliance:** good. Alpine aports and pmaports are git, with distfiles mirrored.
- **Fit:** strongest community overlap with "mainline Linux handheld", but it is the most "mobile-distro-shaped" option, and the musl and OpenRC heritage is friction for the Rust/Slint/vendor-binary side.

### 4.4 Alpine Linux (plain)

- **Kernel:** `linux-stable` 7.2.11 on edge and 7.1.5 on v3.24; `linux-lts` 6.18.58. `linux-edge` no longer exists. The config lacks i.MX8MP display (section 1.2).
- **U-Boot:** `u-boot-rockchip` 2026.10 (contents seen for rock5b and rockpro64; no RK3566/RK3576 targets were found). No `u-boot-imx`.
- **Workflow:** `apk --root --initdb`, or `alpine-make-rootfs` and `mkimage` (aports/scripts). Small, fast and reproducible enough when the repo is pinned.
- **Fit:** OpenRC by default (there is no supported systemd) and musl. It meets the "desktop-style" bar less well than pmOS does. Use it only via pmOS, if at all.

### 4.5 Ubuntu (26.04 LTS, 26.10)

- **Kernel:** 7.0.0-38 on the 26.04 LTS and 7.3.0-9 on 26.10. LTS users get newer kernels via HWE point releases. Config coverage for i.MX8MP and RK3576 was **not checked (UNVERIFIED)**.
- **Workflow:** `mmdebstrap` and mkosi work exactly as for Debian, and `ubuntu-image` is also available. Lifetime: 5 years of standard support on the LTS (longer with Pro). Debian-equivalent compliance via Launchpad.
- **Trade-off versus Debian:** a newer kernel on the LTS track, but less mainline-SBC focus, and community SBC work goes to Debian/Armbian rather than Ubuntu. A viable alternative to Debian if the 7.x HWE cadence matters more than Debian's smaller kernel patch set.

### 4.6 Arch Linux ARM

- **Kernel:** `linux-aarch64` 7.2.11-1, rolling, with i.MX8MP display explicitly `not set`. Small volunteer team, no stable branch, no security-lifetime guarantees, and old snapshots are hard to pin reproducibly. **Not recommended** for a product base.

### 4.7 openSUSE Tumbleweed (ports aarch64)

- **Kernel:** `kernel-default` 7.2.11-1.1 with split `dtb-freescale` and `dtb-rockchip` packages, which is convenient. The config enables LCDIF and 8MP HDMI but **not DSIM** (MIPI-DSI), so a DSI panel on the i.MX8MP would not work.
- **U-Boot:** prebuilt packages for RK3566 reference boards (Quartz64, SOQuartz). **KIWI** or mkosi images, and **transactional-update** with btrfs snapshots for atomic updates.
- **Fit:** rolling only (Leap/SLE Micro have older kernels), and aarch64 is a "port", not a primary architecture. A good second opinion, but not a first choice.

### 4.8 NixOS (aarch64, binary cache)

- **Kernel:** `linux_7_3` and `linux_7_2` (7.2.11) on unstable and 26.05, built by Hydra for aarch64-linux and served from cache.nixos.org. The NixOS kernel config is generic, and i.MX8MP coverage is **UNVERIFIED**. Any config override forces a local kernel build, which violates constraint 1.
- **Overlays:** `hardware.deviceTree.overlays` merges overlays at *build* time, not in the bootloader. The bootloader model can be kept by templating `fdtoverlays` in extlinux (**UNVERIFIED**).
- **Strengths:** best-in-class reproducibility and atomic generations with rollback.
- **Weaknesses:** steep learning curve, a non-FHS layout that is friction for third-party binaries, and a small embedded/handheld product community.

### 4.9 Armbian

- **Kernels:** `linux-image-{current,edge}-rockchip64` (6.18 / 7.3), `-imx8m` (6.18 / 7.1), and `vendor-rk35xx` (Rockchip BSP 6.1/6.12) for RK3576-class boards.
- **They are not plain mainline.** The `patch/kernel/archive/rockchip64-7.3` directory carries **256 patches** on top of mainline, while `imx8m-7.1` carries 2 ([armbian/build](https://github.com/armbian/build/tree/main/patch/kernel/archive)). RK3576 boards in Armbian default to the **vendor** branch and the Radxa U-Boot fork (`rk35xx.conf`).
- **Consuming without the framework:** yes, technically. The packages are standard .debs in `apt.armbian.com` (aptly; suites trixie, noble, …; arm64). An mmdebstrap'd Debian image can add that repo and install `linux-image-edge-rockchip64` and `linux-dtb-edge-rockchip64` plus `armbian-firmware`. But we would inherit Armbian's patch stack and release cadence, and we would depend on a volunteer project's repo for a shipped product.
- **Prebuilt images:** per-board images exist; customization runs through the build framework (`customize-image.sh`, extensions), which is the "big build" style we want to avoid.
- **Best use for OpenDAP OS:** as a **reference** for U-Boot/DDR-blob handling, board bring-up patches and firmware packaging. Not as the base.

### 4.10 Mobian

- A Debian derivative with per-device kernels (the newest Rockchip one is 6.18). It does not target our SoCs and lags 7.x. It is useful only as precedent for "Debian + device packages + Phosh". Not a candidate.

---

## 5. Bootloader and board-support model (applies to every option)

1. **Boot chain per SoC:**
   - **i.MX8MP:** BootROM, then U-Boot SPL (needs the NXP `lpddr4_pmu_train_*` firmware from the `firmware-imx` package; redistribution is under NXP's EULA, so the compliance file needs to list it), then TF-A BL31 (mainline `imx8mp`), then U-Boot proper.
   - **RK3566 / RK3576:** BootROM, then the rkbin DDR TPL blob, then U-Boot SPL, then TF-A BL31 (mainline for RK3568/66; RK3576 mainline TF-A **UNVERIFIED**, may need the rkbin BL31), then U-Boot proper.
2. **Overlays applied by U-Boot.** Two options:
   - `extlinux.conf` with `fdt /dtbs/<ver>/<soc-board>.dtb` and `fdtoverlays /dtbs/<ver>/overlays/dap-*.dtbo`, using U-Boot's distro-boot/bootstd `sysboot`, without UEFI.
   - Under UEFI (Fedora), a U-Boot boot script that does `fdt apply` before `bootefi`.

   The **base DTB** should be an upstream-able `dap-handheld.dts` that we eventually submit to mainline, so that it ships inside every distro kernel package. Until then, the DTB and overlays live in a small DAP package versioned against the kernel ABI.
3. **The U-Boot build is the one unavoidable artifact.** It is a small cross-compile: mainline U-Boot plus our board defconfig, using the distro's prebuilt `gcc-aarch64-linux-gnu` and prebuilt TF-A and DDR blobs. It is not a kernel or toolchain build, but it does break the letter of constraint 1. **The maintainers needs to explicitly accept this exception.** The alternative is to use a vendor reference-board U-Boot binary (for example the `generic-rk3576` or `anbernic-rgxx3-rk3566` targets, or a SOM vendor's i.MX8MP image) with a DDR layout identical to the reference.

---

## 6. Comparison matrix

| | Debian | Fedora | postmarketOS | Ubuntu | openSUSE TW | NixOS | Armbian | Alpine | ALARM |
|---|---|---|---|---|---|---|---|---|---|
| Prebuilt kernel ≥7 today | 7.2.9 bpo / 7.2.11 sid | 7.2.11 | 7.2.11 / 7.3 | 7.0 LTS / 7.3 | 7.2.11 | 7.3 | 7.3 edge (patched) | 7.2.11 edge | 7.2.11 |
| Generic mainline kernel (few patches) | yes | yes | yes | mostly (**UNVERIFIED**) | yes | yes | **no** (256 patches on rockchip64) | yes | yes |
| i.MX8MP display incl. DSI in stock config | **no** (MR needed) | **yes** | **yes** | **UNVERIFIED** | no DSI | **UNVERIFIED** | **UNVERIFIED** | no | no |
| RK3566/RK3576 display in stock config | yes | yes | yes | **UNVERIFIED** | yes | **UNVERIFIED** | yes | yes | yes |
| Prebuilt U-Boot for our SoCs | no | no | per-device pkgs | no | RK3566 ref boards | no | per-board (built by framework) | no | no |
| Image from prebuilt pkgs | mmdebstrap, mkosi | mkosi, image-builder | pmbootstrap | mmdebstrap, mkosi | KIWI, mkosi | nix (cache) | framework | apk --root | pacstrap |
| Atomic/A-B updates | sysupdate, RAUC | **bootc/OSTree** | (apk; A/B DIY) | sysupdate, RAUC | transactional-update | generations | DIY | DIY | DIY |
| libc | glibc | glibc | musl | glibc | glibc | glibc | glibc | musl | glibc |
| Security lifetime per release | ~3 + 2 yrs LTS | ~13 months | 6-month releases | 5 yrs LTS | rolling | 7-month releases | follows Debian/Ubuntu + volunteer | ~2 yrs | none |
| Community (SBC/handheld) | largest | medium | strong handheld | medium | small | small | large SBC | medium | small |
| GPL compliance ease | best | very good | good | very good | good | good | medium | good | medium |

---

## 7. Ranked recommendation (a recommendation, not a decision)

### Rank 1: Fedora (44, moving to 45) aarch64. Best fit for i.MX 8M Plus *today*

- **Why:** it is the only mainstream glibc distro whose stock, near-vanilla kernel (7.2.11, rebased to every new mainline series) enables the complete i.MX8MP display pipeline (LCDIF, DSIM, HDMI) **and** the Rockchip one (VOP2, HDMI-QP, Rocket). It needs zero kernel changes from us. It also brings first-class atomic updates (bootc/OSTree), mkosi and image-builder, current Mesa and PipeWire, and full SRPM compliance.
- **Trade-offs:**
  - About a 13-month lifecycle, so a yearly base rebase (smoothed by image-based updates).
  - UEFI-on-U-Boot boot flow (overlays are applied by a U-Boot script before `bootefi`).
  - A smaller embedded/handheld community than Debian.
  - No U-Boot for our SoCs (the same as everyone else).

### Rank 2: Debian 13 trixie + trixie-backports kernel. Best long-term product base; #1 if the SoC ends up being Rockchip

- **Why:** the largest community, the best reproducibility (snapshot.debian.org) and the best GPL compliance, about 5 years of support including LTS, and a generic 7.2.x kernel package from backports that tracks sid within weeks. The extlinux/`fdtoverlays` model works without UEFI. For **RK3566/RK3576 it is ready today**.
- **Trade-offs:**
  - For the **i.MX8MP it needs a Debian kernel config MR** (LCDIF, DSIM, 8MP HDMI, HDMI PVI, Samsung HDMI PHY). It is upstreamable and stays within "no compiling the kernel ourselves", but it puts Debian's review timeline on our critical path.
  - The backports kernel is outside formal DSA coverage.
- **Mitigation:** file the MR now. It costs little and helps regardless of the final choice.

### Rank 3: postmarketOS (generic `linux-postmarketos-stable`)

- **Why:** a mainline-first philosophy identical to ours, a stock config that covers i.MX8MP display, and the strongest overlap with mainline-Linux handhelds (RK3566).
- **Trade-offs:**
  - musl: glibc-only binaries do not run, and the Slint Skia prebuilts are a risk.
  - The Alpine/OpenRC heritage, even though systemd is now available.
  - A 6-month release cadence, with device work concentrated on edge.
  - A smaller security and compliance organization than Debian or Fedora.

#### Not recommended as a base

- Armbian: a patched kernel, and vendor kernels on RK3576. Use it as a U-Boot and bring-up reference.
- Arch Linux ARM: no lifecycle.
- Alpine (plain): OpenRC.
- Mobian: no 7.x for our SoCs.
- NixOS: config overrides force kernel builds, and the community is small.
- openSUSE TW: no DSI on the i.MX8MP, and aarch64 is a port.

---

## 8. Concrete OpenDAP OS workflow (recommendation)

This section is written for Rank 1 and Rank 2 side by side. Both are glibc/systemd, so the DAP layer is identical.

### Prebuilt inputs (nothing compiled except U-Boot)

1. The distro repos pinned to a date: a Fedora compose ID, or a `snapshot.debian.org` timestamp for trixie plus trixie-backports.
2. The distro kernel package: `kernel-core` and `kernel-modules` on Fedora, `linux-image-arm64` from backports on Debian. Plus `linux-firmware` / `firmware-misc-nonfree`, Mesa (etnaviv/Panfrost), PipeWire and WirePlumber.
3. DAP packages, built by our CI as ordinary distro packages (RPM or .deb):
   - `dap-dt`: our board DTB and `.dtbo` overlays, compiled with the prebuilt `dtc` against the kernel's DT headers. It is versioned per kernel series until the DTS is upstream.
   - `dap-bootloader`: our U-Boot `flash.bin` (i.MX8MP) or `idbloader + u-boot.itb` (Rockchip), plus the install script.
   - `dap-services`: Rust daemons, cross-compiled with a rustup toolchain (prebuilt) for `aarch64-unknown-linux-gnu` against the distro sysroot.
   - `dap-shell`: the compositor (an existing packaged one, or our own Smithay/Rust one) plus the Slint UI and systemd units.
   - `dap-image-config`: users, presets, `extlinux.conf` / boot-script template with the `fdtoverlays` line, and the sysupdate/RAUC config.

**Image build:** one `mkosi` project (it supports both Fedora and Debian):

- `Distribution=` plus the pinned mirror, a package list and the local DAP repo.
- `systemd-repart` definitions for `boot`, `rootfs-A`, `rootfs-B` (read-only, verity optional) and `data`.
- A post-step that writes the U-Boot binary at the SoC-specific raw offset.

For Debian, `mmdebstrap` plus `genimage` is an equivalent lower-level path.

### Kernel updates ("just update the kernel")

- **Dev units:** `dnf upgrade kernel*` / `apt -t trixie-backports install linux-image-arm64`. The kernel postinst writes the new kernel, initramfs and DTBs. Our `dap-dt` hook regenerates `extlinux.conf`, keeping N-1 as a fallback entry.
- **Field units:** CI rebuilds the image whenever the pinned snapshot advances (a weekly/stable cadence, or immediately for a security fix), and ships it as an A/B image:
  - `systemd-sysupdate` or RAUC on Debian;
  - `bootc` on Fedora.

  U-Boot `bootcount`/`bootlimit` falls back to the previous slot if the new kernel fails to boot.

**What we customize, and nothing else:** the board DTS and overlays, the U-Boot board config, the package selection, the systemd units and presets, the compositor and Slint UI, the Rust services, the update/rollback policy, branding, and the compliance bundle (an SBOM generated from the package manifest, plus a source offer pointing at the pinned distro snapshot and our own sources).

### Immediate next steps

1. File the Debian kernel-config MR for i.MX8MP display. It is useful under both rankings.
2. Check `/boot/config-*` from actual `linux-image-arm64` and Ubuntu 26.10 kernels, to close the UNVERIFIED rows.
3. Have the maintainers explicitly decide whether the per-board U-Boot build is an accepted exception to constraint 1.
4. Bring up an i.MX8MP EVK or Debix board on the Fedora 44 kernel and the Debian backports kernel, with an extlinux and `fdtoverlays` panel overlay.
5. Push the DAP handheld DTS upstream as early as possible, so that every distro kernel package eventually carries our board.
