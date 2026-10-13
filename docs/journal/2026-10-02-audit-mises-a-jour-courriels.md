---
title: "Audit de sécurité, mises à jour du parc et e-mails"
description: Un audit en boîte noire et en boîte grise, des mises à jour programmables pour tout le parc avec une veille des failles, des journaux consultables et des e-mails qui passent enfin les filtres.
date: 2026-10-02
tags: [journal, securite, mises-a-jour, supervision, messagerie]
---

# Audit de sécurité, mises à jour du parc et e-mails

## Un audit, vu de l'extérieur et de l'intérieur

Le 29/09, la plateforme a été auditée sous trois angles : ce que voit quelqu'un sur Internet (boîte noire), ce que
peut faire quelqu'un qui a déjà un pied dedans (boîte grise : appareil de la maison, machine compromise, compte de la
famille), et l'écart entre les versions en service et les dernières publiées. 25 constats, classés par gravité.

Les plus simples ont été corrigés dans la journée, pour toutes les machines à la fois : résolution de noms par
diffusion coupée (LLMNR), SSH sans rebond et limité aux algorithmes modernes, journal d'audit des fichiers sensibles
envoyé aux journaux centralisés, droits d'un jeton resserrés, une galerie photo et un pare-feu mis à jour. Deux
décisions en sont sorties : la détection d'intrusion ([ADR 0021](../adr/0021-detection-intrusions.md)), dont les
premières règles sur les journaux tournent déjà, et une autorité de certification interne
([ADR 0022](../adr/0022-certificats-internes.md)).

Un test de l'audit a d'ailleurs fait bannir toute la maison par le WAF :
[post-mortem du 29/09](../postmortems/2026-09-29-maison-bannie-par-le-waf.md).

## Des mises à jour qu'on programme, une veille qui prévient

Chaque machine publie son état toutes les heures : correctifs de sécurité en attente, redémarrage requis. Une mise à
jour de tout le parc se programme depuis Semaphore (une date, un intervalle entre deux machines, l'hyperviseur en
dernier), avec une annonce aux membres de la famille ([ADR 0023](../adr/0023-mises-a-jour-et-veille.md)).

Chaque nuit, une veille compare les images en service aux failles connues (Trivy) et aux avis publiés par les
projets : une alerte par action à mener, regroupées, rappelées chaque semaine tant que rien n'est fait.

## Des journaux qu'on lit

Les journaux de toutes les machines étaient centralisés depuis le 28/09 ; ils se lisent maintenant dans un tableau
dédié (volume et erreurs par machine, refus du pare-feu, connexions SSH) et dans l'interface de VictoriaLogs, en
lecture seule, derrière le VPN et le SSO. L'occupation du stockage par jeu de données et l'envoi des e-mails sont
suivis et alertés comme le reste.

## Des e-mails qui arrivent

Le domaine envoie désormais ses e-mails (invitations, alertes, annonces) par un relais transactionnel, avec SPF,
DKIM et DMARC alignés ; la réception passe par le routage d'e-mails du fournisseur DNS. Fini les e-mails en double
et les messages classés en indésirables.

## Les incidents de la semaine

Deux coupures du WAF le 30/09 ([post-mortem](../postmortems/2026-09-30-coupures-du-waf.md)) et une sauvegarde
coupée par la maintenance de l'hébergeur le 01/10 ([post-mortem](../postmortems/2026-10-01-sauvegarde-maintenance-hebergeur.md)) :
chacun a laissé une alerte ou une vérification de plus.

## Et le site

Le site existe maintenant en anglais (`/en/`), avec les mêmes pages : la CI refuse une page qui n'existerait que dans
une langue.
