---
title: "Login watch, and the WAF again"
description: An alert when login attempts come from an address never seen to succeed, without noise from 5G; dashboards fixed; and a night when the WAF was killed 139 times.
date: 2026-10-13
tags: [journal, security, monitoring, waf]
---

# Login watch, and the WAF again

## Who tries to log in, and from where

Every login coming from the Internet goes through the WAF, which logs it. A small monitoring service reads them back
every minute and keeps a list of **known** addresses: an address becomes known at its first complete successful login
(password and second factor), and stays known.

- Failures from an unknown address, **with no success within a quarter of an hour**, raise an alert with the address,
  the provider and the targeted account. A relative who mistypes a password then succeeds from a new phone address
  triggers nothing: that is what makes the rule bearable with 5G, where the address changes often.
- A password accepted **without a valid second factor** raises a priority alert, even from a known address: someone
  knows the password.
- Every morning, a quiet digest lists the new known addresses of the day before.

At start-up, the addresses that had logged in successfully within the 30 days of available logs were taken over. The
portal's rules live in the public repository; those of the applications with their own login come from the private
inventory.

## Alerts for the administrator only

The public monitoring dashboard is read by the family. A new severity, "admin", sends an email and a notification
without ever showing there; the monitoring role also accepts rules and dashboards from elsewhere (the private
repository), copied as they are.

## What was fixed

- The logs dashboard hid nearly half of the lines: with the "all containers" filter, it kept only lines coming from
  containers, and the system logs disappeared.
- The vulnerability watch tried every night to scan its own image, built locally, on a public registry; and a change
  to its configuration was never seen by the container, for lack of a restart.
- A container engine defect came back on the monitoring machine: containers that run but whose filesystem is no
  longer mounted for Docker. Recreating them is enough; an automatic check is still to come.

## The WAF, again

On the night of 11 to 12/10, a phone's automatic backup to the drive got the WAF killed 139 times: an upload path was
still inspected, so loaded whole into memory. Every kill left a temporary file behind, until the disk filled up and
large responses failed on every site. The details, and what changes:
[post-mortem of 12/10](../postmortems/2026-10-12-waf-memoire-disque-plein.md).
