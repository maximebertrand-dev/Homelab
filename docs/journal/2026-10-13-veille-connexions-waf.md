---
title: "Veille des connexions, et le WAF à nouveau"
description: Une alerte quand des tentatives de connexion viennent d'une adresse jamais vue réussir, sans bruit avec la 5G ; des tableaux corrigés ; et une nuit où le WAF a été tué 139 fois.
date: 2026-10-13
tags: [journal, securite, supervision, waf]
---

# Veille des connexions, et le WAF à nouveau

## Qui essaie de se connecter, et d'où

Toutes les connexions venues d'Internet passent par le WAF, qui les journalise. Un petit service de la supervision
les relit chaque minute et tient une liste des adresses **connues** : une adresse le devient à sa première connexion
complète réussie (mot de passe et second facteur), et le reste.

- Des échecs depuis une adresse inconnue, **sans succès dans le quart d'heure**, déclenchent une alerte avec
  l'adresse, l'opérateur et le compte visé. Un proche qui se trompe de mot de passe puis réussit depuis une nouvelle
  adresse de téléphone ne déclenche rien : c'est ce qui rend la règle supportable avec la 5G, où l'adresse change
  souvent.
- Un mot de passe accepté **sans second facteur valide** déclenche une alerte prioritaire, même depuis une adresse
  connue : quelqu'un connaît le mot de passe.
- Chaque matin, un résumé discret liste les nouvelles adresses connues de la veille.

Au démarrage, les adresses ayant réussi une connexion dans les 30 jours de journaux disponibles ont été reprises.
Les règles du portail sont dans le dépôt public ; celles des applications à connexion propre viennent de
l'inventaire privé.

## Des alertes pour l'administrateur seulement

Le tableau de bord public de la supervision est consulté par la famille. Une nouvelle gravité, « admin », envoie
e-mail et notification sans jamais y apparaître ; le rôle de supervision accepte aussi des règles et des tableaux
venus d'ailleurs (dépôt privé), copiés tels quels.

## Ce qui a été corrigé

- Le tableau des journaux masquait près de la moitié des lignes : avec le filtre « tous les conteneurs », il ne
  gardait que les lignes venant de conteneurs, et les journaux système disparaissaient.
- La veille des failles essayait chaque nuit d'analyser sa propre image, construite sur place, sur un registre public ;
  et un changement de sa configuration n'était jamais vu par le conteneur, faute de redémarrage.
- Un défaut du moteur de conteneurs est revenu sur la machine de supervision : des conteneurs qui tournent mais
  dont le système de fichiers n'est plus monté pour Docker. Les recréer suffit ; un contrôle automatique est à venir.

## Le WAF, encore

Dans la nuit du 11 au 12/10, la sauvegarde automatique d'un téléphone vers le drive a fait tuer le WAF 139 fois : un
chemin d'envoi restait inspecté, donc chargé en entier en mémoire. Chaque arrêt abandonnait un fichier temporaire,
jusqu'à remplir le disque et casser les grosses réponses de tous les sites. Le détail, et ce qui change :
[post-mortem du 12/10](../postmortems/2026-10-12-waf-memoire-disque-plein.md).
