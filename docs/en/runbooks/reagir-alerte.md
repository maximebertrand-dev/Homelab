---
title: "Runbook: responding to an alert"
description: Where alerts arrive, and the first steps for each one.
tags: [monitoring, alerts, prometheus]
---

# Runbook: responding to an alert

**When to use it:** when an alert arrives (email, phone notification) or when a light turns red on the NOC.
**Estimated time:** a few minutes to qualify it; the rest depends on the alert.
**Prerequisites:** the administration VPN (Grafana, Alertmanager and SSH exist only behind it).

Rules: `infra/ansible/roles/supervision/files/alertes.yml`. Monitoring choices:
[ADR 0014](../adr/0014-supervision-noc.md); logs: [ADR 0020](../adr/0020-journaux-centralises.md).

## Where alerts arrive

| Severity | Destination | Reminder |
|---|---|---|
| critical | email + priority phone notification (ntfy) + NOC | every 6 h while it lasts, then a resolution message |
| warning | NOC (and Grafana) | — |
| security | email + notification, one per machine | every 12 h |
| watch (updates, known vulnerabilities) | email + notification, grouped | every week |
| info | low-priority notification | once a day |
| admin (rules from the private repository) | email + notification, never on the NOC | every 12 h, then a resolution message |

An active critical alert silences the warnings of the same machine (inhibition rule): deal with the critical one
first.

## First steps

| Alert | First steps |
|---|---|
| `MachineInjoignable` | The VM's console in Proxmox; if it is the hypervisor itself: emergency access through the remote management card |
| `VMArretee` | `qm status <vmid>` then `qm start <vmid>`; read `journalctl -b -1` in the VM after the restart |
| `ServicePublicIndisponible` | Test from the VPN; `docker compose ps` on the service's VM; the WAF's logs if only the WAF answers with an error ([example](../postmortems/2026-09-30-coupures-du-waf.md)) |
| `PoolZFSDegrade` | `zpool status -x`; identify the disk by its serial number; **detach nothing** before having the replacement disk |
| `DisqueEnEchecSMART`, `DefautsDisqueEnHausse` | `smartctl -a /dev/<disk>`; note the trend; order a disk if it keeps rising; check that the pool is healthy |
| `EspaceDisqueFaible`, `EspaceDisqueCritique` | `df -h` then `docker system df`; prune unused images |
| `StockageDonneesPresquePlein`, `StockagePoolPresquePlein` | Grafana "Stockage et e-mails"; `zfs list -o name,used,refer,usedbysnapshots,quota`; snapshots and staging areas first; beyond 80–90 %, ZFS slows down |
| `MemoireSaturee`, `ProcessusTuesFauteDeMemoire`, `ProcesseurSature` | `docker stats` to find the container; `journalctl -k \| grep -i oom`; revisit the VM's resources if it lasts |
| `CertificatBientotExpire`, `CertificatExpireImminent` | Renewal logs (HTTP-01 on the WAF, DNS-01 on the internal proxy) |
| `Sauvegarde…` | [Backup runbook](sauvegardes.md): on-demand check from Semaphore |
| `MiseAJourEchouee`, `PaquetsSecuriteEnAttente`, `RedemarrageEnAttente` | The update's log on the machine; rerun from Semaphore ("Mettre à jour le parc") |
| `CourrielsEnEchec`, `CourrielsReleveImpossible` | The email relay's console (activity, bounces); check the domain's SPF, DKIM and DMARC |
| `OutilInterneIndisponible`, `CibleDeCollecteInjoignable` | `docker compose ps` and the logs of the service concerned |
| `JournauxNonRecus` | On the machine: `systemctl status systemd-journal-upload`; on the monitoring side: the VictoriaLogs container |

## Searching the logs

Grafana → **"Journaux"** dashboard (volume and real errors per machine, lines filterable by machine, container and
LogsQL search), or **Explore** → **Journaux** data source for a free-form query (30 days of history). The
VictoriaLogs interface itself, read-only, is published behind the internal proxy (VPN and administrators' SSO),
handy for following logs live.

A line written to a container's error output is not an error: Docker files it under priority 3 whatever it says. The
dashboard counts only real error levels (systemd services' priority, `level=error`, nginx's `[error]`, panics).

| Need | Query |
|---|---|
| Real errors in the last hour, per machine | `_time:1h ("level=error" OR "[error]" OR (PRIORITY:<=3 !CONTAINER_NAME:*)) \| stats by (_HOSTNAME) count()` |
| SSH sign-ins this week | `_time:7d _SYSTEMD_UNIT:ssh.service Accepted` |
| Packets refused by the firewall | `_time:15m app_name:filterlog block` |
| One specific container | `_time:30m CONTAINER_NAME:<name>` |

## Silencing an alert

During planned maintenance: Alertmanager → *New Silence*, targeting the instance, for a bounded duration. Never
disable a rule in the code to silence an alert: fix the rule or the cause.

## Verification

The alert moves to "resolved" (resolution message for critical ones) and the NOC turns green again. If the cause is
not obvious or if the service was down, open a [post-mortem](../postmortems/).

## Testing the notification chain

Send Alertmanager a fake critical alert that expires on its own after five minutes (`POST /api/v2/alerts`): the email
and the notification must arrive within a minute.
