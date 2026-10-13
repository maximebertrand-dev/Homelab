---
title: "Post-mortem: the WAF ran out of memory, then out of disk"
description: A phone's automatic backup got the WAF killed 139 times in one night; every kill left an upload file behind, until the disk filled up and large responses failed on every site.
date: 2026-10-12
tags: [incident, waf, modsecurity, memory, storage]
---

# Post-mortem: the WAF ran out of memory, then out of disk

## Summary

| | |
|---|---|
| **Impact** | From 11/10 around 9:20 pm to 13/10 at 10:25 pm: photo and video uploads from the phone interrupted, then, from the morning of 12/10, large responses failing on the published sites (lists, thumbnails, video playback) |
| **Services affected** | The drive and photos first, then anything behind the WAF as soon as a response exceeds what nginx keeps in memory |
| **Causes** | 1) one upload path of the drive still inspected, so loaded whole into memory; 2) the temporary files of interrupted uploads never deleted |
| **Detection** | `ProcessusTuesFauteDeMemoire` alert at the first kill (9:25 pm), but only as a warning; critical `EspaceDisqueCritique` alert 9.5 hours later; users reported it on 13/10 |

## Context

After the [30/09](2026-09-30-coupures-du-waf.md) incident, the photo upload paths and the drive's **chunked** uploads
no longer go through ModSecurity or AppSec: both modules load the whole request body into memory to inspect it. The
drive's Android sync app, however, sends part of the files **in one piece**, with a `PUT` request on another path that
was still inspected.

## Timeline

| When | Event |
|---|---|
| 11/10 ≈ 9:20 pm | A family member's phone starts its automatic backup of photos and videos to the drive |
| 11/10 9:25 pm | First nginx process killed for lack of memory; `ProcessusTuesFauteDeMemoire` alert (warning: dashboard only) |
| 11/10 9 pm → 12/10 7 am | 563 single-piece uploads; **139 nginx processes killed**, up to 20 an hour, each above 1 GB on a 2 GB VM |
| 12/10 6:10 am | WAF disk above 85% (warning) |
| 12/10 6:55 am | Above 95%: critical alert by email and notification |
| 12/10 morning | Disk full: nginx can no longer write its temporary files; large responses fail |
| 13/10 | Reports: videos in error in the photo gallery, empty lists in an app on the phone |
| 13/10 10:25 pm | 144 abandoned temporary files (11.5 GB) deleted: disk at 31%, services back |

## Root causes

**Memory.** The 30/09 fix was written from the paths seen that day: chunked uploads from the sync clients and uploads
from the photo gallery. The Android app's single-piece uploads (files below the chunking threshold) go through
`/remote.php/dav/files/`, which was still inspected. Every video was loaded whole into memory, once per concurrent
request.

**Disk.** nginx writes an upload's body to a temporary file, which it deletes when the request ends. A process killed
by the kernel deletes nothing: each kill left a 40 to 80 MB file behind. In one night, 11.5 GB on a 16 GB disk. Once
full, no large response could get through: the outage spread to services that had nothing to do with uploads.

**Detection.** The alert on killed processes worked from the first kill, but as a warning: it only shows on the
dashboard. The first notification came from the disk, nine and a half hours later, and the fix waited for users to
report it.

## What went well / less well

- **Well**: the centralised logs tied together, within minutes, the nginx kills, the uploads behind them and the
  abandoned files; no data lost (the originals stay on the phone, which uploads again).
- **Less well**: a fix limited to the paths seen on 30/09, with no inventory of each application's upload paths; the
  WAF still had 2 GB of memory, although 3 GB had been planned since 30/09.

## Corrective actions

- [x] `/remote.php/dav/files/` added to the drive's upload paths: neither ModSecurity nor AppSec. Still applied:
  country filtering, rate limiting, CrowdSec bans and the application's own authentication.
- [x] Hourly cleanup of abandoned upload files: older than 2 hours, open by no process.
- [ ] WAF VM memory raised to 3 GB.
- [ ] Notify on processes killed for lack of memory, instead of only showing them: decision pending.
- [x] Rule adopted: every path through which an application uploads files is declared as an upload path, checked in
  its access logs, not only in its documentation.
