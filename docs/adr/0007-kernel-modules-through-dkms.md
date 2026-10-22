# ADR 0007: Kernel modules through DKMS when Debian does not ship them

- **Status:** Accepted
- **Date:** 2026-10-22

## Context

Several drivers the T1 needs are in mainline but not enabled in Debian's kernel configuration, or not yet in the kernel version backports ships (for example the CS43198 DAC driver, battery fuel gauges, NXP Bluetooth, and the IW612 Wi-Fi driver, which arrives in 7.3). Research: [board component selection](https://github.com/opendap-project/board/blob/main/docs/research/2026-10-component-selection.md).

## Decision

DAP OS does not depend on Debian enabling modules. When a module the T1 needs is missing, DAP OS ships it through **DKMS**, built from the mainline source of that driver against Debian's kernel. The Debian kernel itself stays unmodified (OS-002).
