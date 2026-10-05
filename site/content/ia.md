---
title: L'IA dans ce projet
description: "Comment j'utilise un assistant IA pour construire et exploiter le homelab, ce qu'il fait, ce que je garde pour moi, et les règles que je me fixe."
date: 2026-10-05
---

## En bref

- Ce homelab est construit **avec l'aide d'un assistant IA** : Claude, d'Anthropic, utilisé dans mon éditeur de code.
  Je le dis ici, dans le README du dépôt, et chaque commit auquel il a contribué le mentionne.
- **Je décide, il propose.** Les choix d'architecture, les actions irréversibles et ce qui touche aux données de la
  famille passent par moi.
- **Les services n'ont pas besoin de l'IA pour tourner.** Elle sert à construire et à diagnostiquer ; les photos, les
  fichiers et les comptes de la famille ne lui sont jamais confiés.

## Comment je l'utilise

**Ce que fait l'assistant** : il rédige l'essentiel du code (OpenTofu, Ansible, scripts) et de la documentation,
propose des options quand une décision se présente, lance des commandes de diagnostic et de déploiement sur
l'infrastructure, et relit le résultat (sondes, journaux, captures d'écran).

**Ce que je fais** : je fixe les besoins, je choisis entre les options écrites dans chaque
[décision d'architecture](/adr/), je valide les actions irréversibles, et j'exploite la plateforme au quotidien. Les
changements les plus sensibles (règles du pare-feu en production, taille des machines, secrets) sont le plus
souvent appliqués par moi, à partir d'un plan relu.

Concrètement, c'est un travail en binôme : l'assistant va vite et n'oublie pas de documenter ; je connais la maison,
la famille qui utilise les services, et ce qu'on peut se permettre de casser.

## Les garde-fous

- **Proposer, expliquer, puis appliquer.** Un choix d'architecture est présenté avec ses options et ses
  conséquences avant d'être appliqué.
- **Aucune action destructrice sans mon accord explicite** : suppression de données ou de machine, effacement d'un
  disque, modification irréversible du stockage.
- **Ce qui est appliqué, c'est ce qui a été relu** : les changements d'infrastructure passent par un plan OpenTofu
  enregistré, puis appliqué tel quel.
- **Des accès limités et révocables** : l'assistant travaille depuis mon poste, à travers le VPN d'administration,
  avec des permissions restreintes ; ses accès sont listés dans la documentation interne pour pouvoir être audités
  et retirés. Son propre filtre de sécurité refuse en plus certaines actions (écrire un secret, appliquer des règles
  de pare-feu en production) : je les fais moi-même.
- **Les secrets ne passent pas en clair** : ils sont chiffrés dans le dépôt et déchiffrés seulement sur les machines
  qui en ont besoin ; les commandes sont écrites pour ne pas les afficher.
- **Tout est tracé** : chaque changement est un commit relisible, chaque incident a son post-mortem.

## Les données de la famille

Pendant un diagnostic, l'assistant lit du code, des configurations et des journaux techniques. Ces journaux peuvent
contenir des adresses IP ou des identifiants de connexion ; ils transitent alors par les serveurs d'Anthropic, selon
ses conditions d'utilisation. Je limite ces lectures au nécessaire : l'assistant ne lit jamais le contenu des photos
ni des fichiers (tout au plus leur nom, quand il apparaît dans un journal d'import).

L'intelligence artificielle qui reconnaît les visages et permet de chercher dans les photos (Immich) tourne
**sur le serveur de la maison**, sans service extérieur : les photos ne quittent pas le homelab, sauf chiffrées, pour
la sauvegarde.

## Quand l'IA se trompe

Elle se trompe, et je l'écris. Plusieurs pannes de ce projet viennent d'actions de l'assistant :

- un test de sécurité lancé depuis la maison a fait bannir toute la famille par le pare-feu applicatif
  ([post-mortem du 29/09](/postmortems/2026-09-29-maison-bannie-par-le-waf/)) ;
- une option de configuration inexistante a arrêté le pare-feu applicatif pendant une heure
  ([post-mortem du 30/09](/postmortems/2026-09-30-coupures-du-waf/)) ;
- un réglage déployé avant d'ouvrir le flux réseau dont il dépendait a coupé le portail de connexion plusieurs
  heures, et un gros import de photos lancé en journée a épuisé la mémoire du serveur.

Ma validation n'attrape pas tout. D'où le reste : une supervision qui alerte tôt, des zones réseau qui limitent les
dégâts, des sauvegardes vérifiées chaque nuit, et des post-mortems qui transforment chaque erreur en règle.

## Les limites que je me fixe

- **Je reste responsable** de tout ce qui tourne ici, quelle que soit la main qui a écrit le code.
- **Je ne publie pas ce que je ne peux pas défendre** : chaque décision est expliquée par écrit, et je dois pouvoir
  justifier n'importe quel fichier du dépôt.
- **L'IA ne décide rien sur les personnes** : comptes, accès et droits de la famille sont attribués par moi.
- **Pas d'usage gratuit** : un modèle d'IA consomme de l'énergie dans des centres de données. Je m'en sers pour
  construire et réparer, pas pour faire tourner les services au quotidien.
- **Transparence par défaut** : si l'IA a aidé, ça se voit (commits, README, cette page).
