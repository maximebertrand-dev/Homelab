---
title: "ADR 0024: A graphics card handed to the applications VM"
description: An entry-level GeForce is handed whole to the applications VM (PCI passthrough) for photo recognition and video conversion, with a driver maintained by Debian and containers that request it through CDI.
date: 2026-10-19
status: accepté
tags: [hardware, proxmox, immich, gpu]
---

# ADR 0024: A graphics card handed to the applications VM

## Context

The server's processor (Xeon E3-1220 v6, 4 cores) has no graphics unit. All the heavy work of the applications went
through it:

- photo recognition (faces, search by description);
- converting videos for phones and browsers.

During imports (about 11,500 photos in October), the applications VM stayed saturated for hours and the rest of the
server suffered. A GeForce GTX 1050 (Pascal, 2 GB, 75 W, no extra power connector) was added to the server on 19/10.

## Options considered

1. **Stay on the processor**: no change, but imports and conversions stay just as long.
2. **Hand the whole card to the applications VM (PCI passthrough, vfio)**: native performance, driver inside the
   VM; only one VM can use it.
3. **Driver on the host, shared with LXC containers**: goes against the one-VM-per-security-zone choice
   ([ADR 0010](0010-serveur-unique.md)), and the host would run the proprietary driver.
4. **Share the card between several VMs (vGPU)**: not available on a GeForce.

## Decision

Option 2, on the applications VM, where all the services that benefit from it run.

- **Host**: the card is reserved for `vfio-pci` from boot (host drivers kept away) and declared as a Proxmox
  "mapping". OpenTofu's token only has rights on that mapping, not on the rest of the hardware.
- **VM**: the card is handed over without its video ROM, which is useless without a screen; with it, the VM's BIOS
  froze at boot.
- **Driver**: Debian's (non-free, rebuilt by DKMS for every kernel, fixed by Debian updates) rather than NVIDIA's.
- **Containers**: NVIDIA's tools, from their repository (key stored in the Ansible role, fingerprint checked), in
  **CDI** mode. A container requests `nvidia.com/gpu=all`, Docker's configuration stays untouched, and the card's
  description is regenerated at every boot, before Docker.
- **Applications**: Immich runs recognition with CUDA and converts videos on the card (NVENC, NVDEC).

## Consequences

- **Measured on a 4K HDR film**: decoding at 157 frames/s, 4K HDR → 1080p conversion at 170 frames/s, i.e. 7 times
  real time. At rest, the card stays around 33 °C with its fan stopped.
- **Dependency on the driver**: without the card or its driver, the containers that request it no longer start. A
  probe (presence, temperature, load) alerts if the card disappears, for example after a new kernel, or if it runs
  hot. A degraded mode, which removes the card request, brings everything back to the processor.
- **Hardware checked at boot**: if the card is removed or replaced, the VM refuses to start until the mapping is
  removed.
- **Memory**: the VM's memory is reserved in full on the host, which direct memory access by the card requires.
- **Card limits**: 2 GB of graphics memory, no AV1, at most 8 simultaneous encodes on a GeForce. NVIDIA drops Pascal
  after its 580 branch, to be revisited when moving to Debian 14.
