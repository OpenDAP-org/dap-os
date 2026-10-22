# ADR 0004: Image lifecycle

- **Status:** Accepted
- **Date:** 2026-10-21

## Context

OpenDAP OS is built from code and configuration (OS-010), runs on developer hosts (OS-009, OS-016), ships as signed, versioned releases (OS-011), flashes simply (OS-012) and updates from Debian and OpenDAP repositories (OS-013), likely over the air (OS-014). Research: [`../research/2026-10-os-lifecycle.md`](../research/2026-10-os-lifecycle.md).

## Decision

- **One image definition** (mkosi) with three outputs: `t1` (the device), `qemu` and `oci`. U-Boot and the signed FIT images are written by an OpenDAP step, because mkosi has no U-Boot mode.
- **Device image:** A/B partitions; a read-only erofs root protected by dm-verity; the verity root hash inside a signed FIT image verified by U-Boot.
- **Development:** QEMU on the host; OpenDAP services are deployed to a running instance as development system extensions, never by modifying the verified root.
- **Packages:** OpenDAP software is packaged with `cargo-deb` into an OpenDAP APT repository managed with aptly and snapshots. Every image build pins a snapshot.debian.org date, and every release ships a source archive for GPL compliance.
- **Flashing:** `dap flash` in the toolkit, built on the `rockusb` crate, over MaskROM / loader USB.
- **Updates:** RAUC bundles with U-Boot's RAUC boot method and a health check before an update is accepted, served over static HTTP through the package endpoint. Third-party capabilities are signed bundles on the data partition, outside the base image.
- **Development tools on the device** (such as OpenOCD, packaged by OpenDAP from a pinned upstream commit because Debian's build lacks the Linux GPIO backend) come from a separate repository and are not installed by default (OS-015).
