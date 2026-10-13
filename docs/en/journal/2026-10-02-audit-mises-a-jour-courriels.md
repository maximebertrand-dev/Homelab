---
title: "Security audit, fleet updates and email"
description: A black-box and grey-box audit, schedulable updates for the whole fleet with vulnerability watch, readable logs, and emails that finally get past the filters.
date: 2026-10-02
tags: [journal, security, updates, monitoring, email]
---

# Security audit, fleet updates and email

## An audit, from outside and from inside

On 29/09 the platform was audited from three angles: what someone on the Internet sees (black box), what someone who
already has a foot in can do (grey box: a device at home, a compromised machine, a family account), and the gap
between the versions in service and the latest releases. 25 findings, ranked by severity.

The simplest ones were fixed the same day, on every machine at once: broadcast name resolution turned off (LLMNR),
SSH without forwarding and limited to modern algorithms, an audit trail of sensitive files sent to the centralised
logs, a token's permissions tightened, a photo gallery and a firewall updated. Two decisions came out of it: intrusion
detection ([ADR 0021](../adr/0021-detection-intrusions.md)), whose first log-based rules are already running, and an
internal certificate authority ([ADR 0022](../adr/0022-certificats-internes.md)).

One of the audit's tests got the whole household banned by the WAF:
[post-mortem of 29/09](../postmortems/2026-09-29-maison-bannie-par-le-waf.md).

## Updates you schedule, a watch that warns

Every machine publishes its state every hour: pending security patches, reboot required. An update of the whole fleet
is scheduled from Semaphore (a date, a delay between two machines, the hypervisor last), with an announcement to the
family members ([ADR 0023](../adr/0023-mises-a-jour-et-veille.md)).

Every night, a watch compares the images in service with known vulnerabilities (Trivy) and with the advisories
published by the projects: one alert per action to take, grouped, repeated every week until something is done.

## Logs you can read

The logs of every machine had been centralised since 28/09; they can now be read in a dedicated dashboard (volume and
errors per machine, firewall blocks, SSH logins) and in VictoriaLogs' own interface, read-only, behind the VPN and
SSO. Storage use per dataset and outgoing email are monitored and alerted like everything else.

## Emails that arrive

The domain now sends its emails (invitations, alerts, announcements) through a transactional relay, with aligned
SPF, DKIM and DMARC; incoming mail goes through the DNS provider's email routing. No more duplicate emails, no more
messages landing in spam.

## The week's incidents

Two WAF outages on 30/09 ([post-mortem](../postmortems/2026-09-30-coupures-du-waf.md)) and a backup cut by the
hosting provider's maintenance on 01/10 ([post-mortem](../postmortems/2026-10-01-sauvegarde-maintenance-hebergeur.md)):
each one left an extra alert or check behind.

## And the website

The site now exists in English (`/en/`), with the same pages: the CI rejects a page that would exist in only one
language.
