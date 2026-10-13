---
title: "Post-mortem : le WAF à court de mémoire, puis disque plein"
description: La sauvegarde automatique d'un téléphone a fait tuer le WAF 139 fois en une nuit ; chaque arrêt abandonnait un fichier d'envoi, jusqu'à remplir le disque et casser les grosses réponses de tous les sites.
date: 2026-10-12
tags: [incident, waf, modsecurity, memoire, stockage]
---

# Post-mortem : le WAF à court de mémoire, puis disque plein

## Résumé

| | |
|---|---|
| **Impact** | Du 11/10 vers 21 h 20 au 13/10 à 22 h 25 : envois de photos et vidéos du téléphone interrompus, puis, à partir du 12/10 au matin, réponses volumineuses en échec sur les sites publiés (listes, vignettes, lecture de vidéos) |
| **Services touchés** | Drive et photos d'abord, puis tout ce qui passe par le WAF dès que la réponse dépasse ce que nginx garde en mémoire |
| **Causes** | 1) un chemin d'envoi du drive encore inspecté, donc chargé en entier en mémoire ; 2) les fichiers temporaires des envois interrompus jamais effacés |
| **Détection** | Alerte `ProcessusTuesFauteDeMemoire` au premier arrêt (21 h 25), mais en simple avertissement ; alerte critique `EspaceDisqueCritique` 9 h 30 plus tard ; signalement par les utilisateurs le 13/10 |

## Contexte

Après l'incident du [30/09](2026-09-30-coupures-du-waf.md), les chemins d'envoi des photos et les envois **découpés
en morceaux** du drive ne passent plus par ModSecurity ni par AppSec : ces deux modules chargent tout le corps d'une
requête en mémoire pour l'inspecter. L'application de synchronisation du drive sur Android envoie pourtant une partie
des fichiers **d'un seul bloc**, par une requête `PUT` sur un autre chemin, resté inspecté.

## Chronologie

| Quand | Événement |
|---|---|
| 11/10 ≈ 21 h 20 | Le téléphone d'un membre de la famille lance la sauvegarde automatique de ses photos et vidéos vers le drive |
| 11/10 21 h 25 | Premier processus nginx tué faute de mémoire ; alerte `ProcessusTuesFauteDeMemoire` (avertissement : tableau de bord seulement) |
| 11/10 21 h → 12/10 7 h | 563 envois d'un seul bloc ; **139 processus nginx tués**, jusqu'à 20 par heure, chacun à plus de 1 Go sur une VM de 2 Go |
| 12/10 6 h 10 | Disque du WAF à plus de 85 % (avertissement) |
| 12/10 6 h 55 | Plus de 95 % : alerte critique par e-mail et notification |
| 12/10 matin | Disque plein : nginx ne peut plus écrire ses fichiers temporaires ; les grosses réponses échouent |
| 13/10 | Signalements : vidéos en erreur dans la galerie photo, listes vides dans une application sur téléphone |
| 13/10 22 h 25 | 144 fichiers temporaires abandonnés (11,5 Go) supprimés : disque à 31 %, services rétablis |

## Causes racines

**La mémoire.** La correction du 30/09 a été écrite à partir des chemins observés ce jour-là : les envois découpés
des clients de synchronisation et ceux de la galerie photo. Les envois d'un seul bloc de l'application Android
(fichiers sous le seuil de découpage) passent par `/remote.php/dav/files/`, qui restait inspecté. Chaque vidéo y était
chargée en entier en mémoire, une par requête simultanée.

**Le disque.** nginx écrit le corps d'un envoi dans un fichier temporaire, qu'il efface à la fin de la requête. Un
processus tué par le noyau n'efface rien : chaque arrêt laissait un fichier de 40 à 80 Mo. En une nuit, 11,5 Go sur
un disque de 16 Go. Une fois plein, plus aucune réponse volumineuse ne pouvait transiter : la panne s'est étendue
à des services qui n'avaient rien à voir avec les envois.

**La détection.** L'alerte sur les processus tués a fonctionné dès le premier arrêt, mais en avertissement : elle
n'apparaît que sur le tableau de bord. La première notification est venue du disque, neuf heures et demie plus tard,
et la correction a attendu le signalement des utilisateurs.

## Ce qui a bien marché / moins bien marché

- **Bien** : les journaux centralisés ont permis de relier en quelques minutes les arrêts de nginx, les envois en
  cause et les fichiers abandonnés ; aucune donnée perdue (les originaux restent sur le téléphone, qui renvoie).
- **Moins bien** : une correction limitée aux chemins vus le 30/09, sans inventaire des chemins d'envoi de chaque
  application ; la mémoire du WAF toujours à 2 Go, alors que 3 Go étaient prévus depuis le 30/09.

## Actions correctives

- [x] `/remote.php/dav/files/` ajouté aux chemins d'envoi du drive : ni ModSecurity ni AppSec. Restent appliqués :
  filtrage par pays, limite de débit, bannissements de CrowdSec et authentification de l'application.
- [x] Nettoyage toutes les heures des fichiers d'envoi abandonnés : plus de 2 h, ouverts par aucun processus.
- [ ] Mémoire de la VM du WAF portée à 3 Go.
- [ ] Notifier les processus tués faute de mémoire, au lieu de les afficher seulement : décision à prendre.
- [x] Règle retenue : tout chemin par lequel une application envoie des fichiers est déclaré comme chemin d'envoi,
  vérifié dans ses journaux d'accès, pas seulement dans sa documentation.
