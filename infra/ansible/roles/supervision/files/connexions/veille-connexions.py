#!/usr/bin/env python3
"""Veille des connexions : tentatives depuis une adresse inconnue.

Toutes les minutes, lit dans VictoriaLogs les requêtes de connexion vues par le WAF (règles de la configuration :
hôte, méthode, chemin, codes de retour → succès, mot de passe accepté, échec, échec du second facteur). Une adresse
devient « connue » à sa première connexion complète réussie et le reste (liste gardée dans l'état, au-delà de la
rétention des journaux) ; les adresses privées et celles de la configuration le sont d'office.

Des échecs depuis une adresse inconnue sans succès dans le délai (15 min par défaut : une personne de la famille qui se
trompe puis réussit depuis une nouvelle adresse 5G ne déclenche rien) envoient une alerte à Alertmanager :
- ConnexionsTentativesAdresseInconnue (gravité « admin ») : mots de passe refusés ;
- ConnexionsMotDePasseSansSecondFacteur (gravité « securite ») : mot de passe accepté mais second facteur raté ou
  jamais fait depuis une adresse inconnue, ou second facteur raté depuis une adresse connue (quelqu'un connaît le
  mot de passe, ou un nouveau compte qui n'a pas fini son enregistrement).
Chaque jour, un résumé des nouvelles adresses connues (gravité « info »). Mesures pour Prometheus sur :9801/metrics.

Variables : VICTORIALOGS, ALERTMANAGER, CONFIG (JSON), ETAT (fichier d'état), PORT.
"""
import concurrent.futures
import http.server
import ipaddress
import json
import os
import re
import socket
import sys
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

VICTORIALOGS = os.environ.get("VICTORIALOGS", "http://victorialogs:9428")
ALERTMANAGER = os.environ.get("ALERTMANAGER", "http://alertmanager:9093")
CONFIG = os.environ.get("CONFIG", "/etc/connexions/connexions.json")
ETAT = os.environ.get("ETAT", "/etat/etat.json")
PORT = int(os.environ.get("PORT", "9801"))
INTERVALLE = 60
RECOUVREMENT = 600          # relit les 10 dernières minutes : journaux arrivés en retard (requêtes dédoublonnées)
SILENCE_FIN = 3600          # une adresse suspecte sans nouvel échec depuis 1 h n'est plus signalée
HISTORIQUE = 7 * 86400      # tentatives inconnues gardées 7 jours pour le tableau
ACCES = re.compile(
    r'^\[NGINX\.ACCESS\] (?P<hote>\S+) (?P<ip>\S+) - (?P<id>\S+) \S+ \[[^\]]+\] '
    r'"(?P<methode>[A-Z]+) (?P<chemin>[^ ?"]*)[^"]*" (?P<statut>\d{3}) \S+ "(?P<referent>[^"]*)"'
)
TYPES_ECHEC = ("echec", "echec_second_facteur")

mesures = "homelab_connexions_lecture_ok 0\n"
verrou = threading.Lock()


def journal(evenement, **details):
    print(json.dumps({"quand": datetime.now(timezone.utc).isoformat(timespec="seconds"), "evenement": evenement,
                      **details}, ensure_ascii=False), flush=True)


def iso(horodatage):
    return datetime.fromtimestamp(horodatage, timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def heure_locale(horodatage):
    return datetime.fromtimestamp(horodatage).strftime("%d/%m %H:%M")


def logsql(requete, debut, fin):
    """Lignes de VictoriaLogs (JSON par ligne) entre deux instants."""
    donnees = urllib.parse.urlencode({"query": requete, "start": iso(debut), "end": iso(fin)}).encode()
    with urllib.request.urlopen(f"{VICTORIALOGS}/select/logsql/query", data=donnees, timeout=60) as reponse:
        return [json.loads(ligne) for ligne in reponse.read().decode().splitlines() if ligne.strip()]


def horodatage_vl(texte):
    texte = texte.rstrip("Z")
    entier, _, fraction = texte.partition(".")
    return datetime.fromisoformat(entier).replace(tzinfo=timezone.utc).timestamp() + float("0." + (fraction or "0"))


def service_vise(regle, referent):
    """Service de la règle ; pour le portail, application d'origine lue dans le paramètre « rd » du référent."""
    nom = regle["service"]
    if not regle.get("cible_depuis_referent"):
        return nom
    cible = urllib.parse.parse_qs(urllib.parse.urlparse(referent).query).get("rd", [""])[0]
    hote = urllib.parse.urlparse(cible).hostname or ""
    return f"{nom} ({hote.split('.')[0]})" if hote else nom


def classer(conf, ligne):
    """Événement de connexion d'une ligne du WAF, ou None."""
    trouve = ACCES.match(ligne)
    if not trouve:
        return None
    for regle in conf["regles"]:
        if (trouve["hote"] == regle["hote"] and trouve["methode"] == regle["methode"]
                and trouve["chemin"].lower() == regle["chemin"].lower() and int(trouve["statut"]) in regle["statuts"]):
            return {"ip": trouve["ip"], "id": trouve["id"], "type": regle["type"],
                    "service": service_vise(regle, trouve["referent"])}
    return None


def lire_evenements(conf, debut, fin):
    chemins = sorted({r["chemin"] for r in conf["regles"]})
    filtre = " OR ".join(f"i({json.dumps(c)})" for c in chemins)  # chemins sans tenir compte de la casse
    requete = f'CONTAINER_NAME:{json.dumps(conf["conteneur_waf"])} "[NGINX.ACCESS]" ({filtre}) | fields _time, _msg'
    evenements = []
    for ligne in logsql(requete, debut, fin):
        evenement = classer(conf, ligne.get("_msg", ""))
        if evenement:
            evenement["quand"] = horodatage_vl(ligne["_time"])
            evenements.append(evenement)
    return sorted(evenements, key=lambda e: e["quand"])


def lire_comptes(conf, debut, fin):
    """Comptes visés, lus dans les journaux des applications (Authelia : adresse comprise ; d'autres : par l'heure)."""
    comptes = []
    for source in conf.get("comptes", []):
        motif = re.compile(source["motif"])
        requete = f'CONTAINER_NAME:{json.dumps(source["conteneur"])} {json.dumps(source["mot_cle"])} | fields _time, _msg'
        for ligne in logsql(requete, debut, fin):
            trouve = motif.search(ligne.get("_msg", ""))
            if trouve:
                comptes.append({"quand": horodatage_vl(ligne["_time"]), "compte": trouve["compte"],
                                "ip": trouve.groupdict().get("ip"), "service": source.get("service")})
    return comptes


def rattacher_comptes(evenements, comptes):
    for evenement in evenements:
        if evenement["type"] not in TYPES_ECHEC:
            continue
        for compte in comptes:
            meme_adresse = compte["ip"] == evenement["ip"] and abs(compte["quand"] - evenement["quand"]) < 60
            meme_service = (not compte["ip"] and compte["service"] and evenement["service"].startswith(compte["service"])
                            and abs(compte["quand"] - evenement["quand"]) < 10)
            if meme_adresse or meme_service:
                evenement["compte"] = compte["compte"]
                break


def adresse_privee(ip):
    try:
        return ipaddress.ip_address(ip).is_private
    except ValueError:
        return False


def connue(conf, etat, ip):
    if ip in etat["connues"] or adresse_privee(ip):
        return True
    try:
        adresse = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(adresse in ipaddress.ip_network(r, strict=False) for r in conf.get("adresses_connues", []))


resolveur = concurrent.futures.ThreadPoolExecutor(max_workers=4)


def operateur(etat, ip):
    """Domaine du nom inverse (DNS) de l'adresse, ex. « free.fr » ; gardé une semaine."""
    cache = etat.setdefault("ptr", {})
    if ip in cache and time.time() - cache[ip][1] < 7 * 86400:
        return cache[ip][0]
    if adresse_privee(ip):
        domaine = "réseau local"
    else:
        try:
            nom = resolveur.submit(socket.gethostbyaddr, ip).result(timeout=3)[0].rstrip(".")
            morceaux = nom.split(".")
            if re.fullmatch(r"[0-9a-fA-F.:]+", nom) or nom.endswith(".arpa"):
                domaine = "inconnu"  # pas de vrai nom inverse (la réponse est l'adresse elle-même)
            else:
                domaine = ".".join(morceaux[-3:] if len(morceaux) > 2 and len(morceaux[-2]) <= 3 else morceaux[-2:])
        except Exception:  # pas de nom inverse, ou résolution trop lente
            domaine = "inconnu"
    cache[ip] = [domaine, time.time()]
    return domaine


def traiter(conf, etat, evenements):
    """Met à jour les adresses connues et les adresses suspectes à partir des nouveaux événements."""
    for e in evenements:
        if e["id"] in etat["vus"]:
            continue
        etat["vus"][e["id"]] = e["quand"]
        cle = f'{e["service"].split(" ")[0]}|{e["type"]}'
        etat["compteurs"][cle] = etat["compteurs"].get(cle, 0) + 1
        ip = e["ip"]
        if e["type"] == "succes":
            if not connue(conf, etat, ip):
                etat["nouvelles"].append({"ip": ip, "quand": e["quand"], "service": e["service"]})
                journal("adresse_connue", ip=ip, service=e["service"], operateur=operateur(etat, ip))
            fiche = etat["connues"].setdefault(ip, {"premiere": e["quand"], "connexions": 0, "services": []})
            fiche["derniere"] = max(fiche.get("derniere", 0), e["quand"])
            fiche["connexions"] += 1
            if e["service"] not in fiche["services"]:
                fiche["services"].append(e["service"])
            if ip in etat["suspects"]:
                journal("suspect_leve", ip=ip, raison="connexion réussie")
                etat["suspects"].pop(ip)
            continue
        # Adresse connue : seul un second facteur raté compte encore (un succès sur une application sans second
        # facteur ne doit pas couvrir quelqu'un qui connaît le mot de passe). Adresses privées : jamais.
        adresse_connue = connue(conf, etat, ip)
        if adresse_connue and (e["type"] != "echec_second_facteur" or adresse_privee(ip)):
            continue
        if ip not in etat["suspects"]:
            journal("suspect", ip=ip, service=e["service"], operateur=operateur(etat, ip))
        s = etat["suspects"].setdefault(ip, {"debut": e["quand"], "echecs": 0, "echecs_second_facteur": 0,
                                             "mot_de_passe_accepte": False, "services": [], "comptes": [],
                                             "adresse_connue": adresse_connue})
        s["dernier"] = max(s.get("dernier", 0), e["quand"])
        if e["type"] == "echec":
            s["echecs"] += 1
        elif e["type"] == "echec_second_facteur":
            s["echecs_second_facteur"] += 1
        elif e["type"] == "mot_de_passe":
            s["mot_de_passe_accepte"] = True
        if e["service"] not in s["services"]:
            s["services"].append(e["service"])
        if e.get("compte") and e["compte"] not in s["comptes"]:
            s["comptes"].append(e["compte"])


def alertes(conf, etat, maintenant):
    """Alertes à (re)envoyer pour les adresses suspectes sans succès depuis le délai."""
    delai = conf.get("delai_minutes", 15) * 60
    liste = []
    for ip, s in list(etat["suspects"].items()):
        if maintenant - s["dernier"] > SILENCE_FIN:
            etat["historique"].append({"ip": ip, **s})
            etat["suspects"].pop(ip)
            continue
        if maintenant - s["debut"] < delai:
            continue
        grave = s["mot_de_passe_accepte"] or s["echecs_second_facteur"] > 0
        op = operateur(etat, ip)
        services = ", ".join(s["services"])
        comptes = ", ".join(s["comptes"]) or "non identifié"
        if grave:
            nom, severite = "ConnexionsMotDePasseSansSecondFacteur", "securite"
            origine = "une adresse connue" if s.get("adresse_connue") else "une adresse inconnue"
            resume = f"Mot de passe accepté sans second facteur depuis {origine} : {ip} ({op})"
            detail = (f"Depuis {heure_locale(s['debut'])} : mot de passe accepté, second facteur "
                      f"{'raté ' + str(s['echecs_second_facteur']) + ' fois' if s['echecs_second_facteur'] else 'jamais validé'}"
                      f", {s['echecs']} mot(s) de passe refusé(s). Services : {services}. Comptes : {comptes}. "
                      "Si ce n'est pas un nouveau membre en train d'enregistrer sa double authentification, changer le "
                      "mot de passe du compte.")
        else:
            nom, severite = "ConnexionsTentativesAdresseInconnue", "admin"
            resume = f"{s['echecs']} échec(s) de connexion depuis une adresse inconnue : {ip} ({op})"
            detail = (f"Depuis {heure_locale(s['debut'])}, aucune connexion réussie depuis cette adresse. "
                      f"Services : {services}. Comptes visés : {comptes}.")
        liste.append({
            "labels": {"alertname": nom, "severite": severite, "instance": "connexions", "ip": ip},
            "annotations": {"resume": resume, "description": detail},
            "startsAt": iso(s["debut"] + delai), "endsAt": iso(maintenant + 5 * INTERVALLE),
        })
    etat["historique"] = [h for h in etat["historique"] if maintenant - h["dernier"] < HISTORIQUE]
    return liste


def resume_quotidien(conf, etat, maintenant):
    """Une fois par jour, à l'heure prévue : nouvelles adresses connues depuis le dernier résumé."""
    local = datetime.fromtimestamp(maintenant)
    jour = local.strftime("%Y-%m-%d")
    if local.hour < conf.get("resume_heure", 8) or etat.get("dernier_resume") == jour:
        return []
    etat["dernier_resume"] = jour
    nouvelles, etat["nouvelles"] = etat["nouvelles"], []
    if not nouvelles:
        return []
    lignes = [f"{n['ip']} ({operateur(etat, n['ip'])}) : {n['service']}, le {heure_locale(n['quand'])}"
              for n in nouvelles[:30]]
    return [{
        "labels": {"alertname": "ConnexionsNouvellesAdresses", "severite": "info", "instance": "connexions",
                   "travail": f"resume-{jour}"},
        "annotations": {"resume": f"{len(nouvelles)} nouvelle(s) adresse(s) connue(s) depuis hier",
                        "description": " ; ".join(lignes)},
        "startsAt": iso(maintenant), "endsAt": iso(maintenant + 1800),
    }]


def envoyer(liste):
    if not liste:
        return
    requete = urllib.request.Request(f"{ALERTMANAGER}/api/v2/alerts", data=json.dumps(liste).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(requete, timeout=15):
        pass


def echapper(valeur):
    return str(valeur).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def calculer_mesures(etat, maintenant, lecture_ok):
    lignes = [f"homelab_connexions_derniere_execution_timestamp {int(maintenant)}",
              f"homelab_connexions_lecture_ok {int(lecture_ok)}",
              f"homelab_connexions_adresses_connues {len(etat['connues'])}",
              f"homelab_connexions_adresses_suspectes {len(etat['suspects'])}"]
    recentes = sorted(etat["connues"].items(), key=lambda kv: kv[1].get("derniere", 0), reverse=True)[:300]
    for ip, fiche in recentes:
        etiquettes = f'ip="{ip}",operateur="{echapper(etat.get("ptr", {}).get(ip, ["?"])[0])}",' \
                     f'services="{echapper(", ".join(fiche["services"]))}"'
        lignes.append(f"homelab_connexions_adresse_connue_derniere_timestamp{{{etiquettes}}} {int(fiche.get('derniere', 0))}")
    lots = [("en cours", ip, fiche) for ip, fiche in etat["suspects"].items()] + \
           [("terminé", h["ip"], h) for h in etat["historique"]]
    for statut, ip, fiche in lots:
        etiquettes = (f'ip="{ip}",operateur="{echapper(etat.get("ptr", {}).get(ip, ["?"])[0])}",'
                      f'services="{echapper(", ".join(fiche["services"]))}",'
                      f'comptes="{echapper(", ".join(fiche["comptes"]))}",etat="{statut}",'
                      f'debut="{heure_locale(fiche["debut"])}",'
                      f'mot_de_passe_accepte="{int(fiche["mot_de_passe_accepte"])}"')
        lignes.append(f"homelab_connexions_tentatives_inconnues{{{etiquettes}}} "
                      f"{fiche['echecs'] + fiche['echecs_second_facteur']}")
    for cle, nombre in sorted(etat["compteurs"].items()):
        service, type_ = cle.split("|")
        lignes.append(f'homelab_connexions_evenements_total{{service="{echapper(service)}",type="{type_}"}} {nombre}')
    return "\n".join(lignes) + "\n"


class Mesures(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 (nom imposé par http.server)
        with verrou:
            corps = mesures.encode()
        self.send_response(200 if self.path == "/metrics" else 404)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def log_message(self, *_):
        pass


def charger_etat():
    try:
        with open(ETAT, encoding="utf-8") as fichier:
            etat = json.load(fichier)
    except FileNotFoundError:
        etat = {}
    for cle, defaut in (("connues", {}), ("suspects", {}), ("historique", []), ("nouvelles", []), ("vus", {}),
                        ("compteurs", {}), ("ptr", {})):
        etat.setdefault(cle, defaut)
    # Opérateurs mal déduits par une version précédente (adresse prise pour un nom) : à résoudre de nouveau.
    etat["ptr"] = {ip: v for ip, v in etat["ptr"].items() if not re.fullmatch(r"[0-9.:]+", v[0])}
    return etat


def sauver_etat(etat):
    temporaire = ETAT + ".tmp"
    with open(temporaire, "w", encoding="utf-8") as fichier:
        json.dump(etat, fichier, ensure_ascii=False)
    os.replace(temporaire, ETAT)


def amorcer(conf, etat, maintenant):
    """Premier démarrage : adresses ayant réussi une connexion complète dans les journaux disponibles = connues."""
    debut = maintenant - conf.get("amorcage_jours", 30) * 86400
    for e in lire_evenements(conf, debut, maintenant):
        if e["type"] == "succes":
            fiche = etat["connues"].setdefault(e["ip"], {"premiere": e["quand"], "connexions": 0, "services": []})
            fiche["derniere"] = max(fiche.get("derniere", 0), e["quand"])
            fiche["connexions"] += 1
            if e["service"] not in fiche["services"]:
                fiche["services"].append(e["service"])
    for ip in etat["connues"]:
        operateur(etat, ip)
    etat["curseur"] = maintenant
    journal("amorcage", adresses_connues=len(etat["connues"]), depuis_jours=conf.get("amorcage_jours", 30))


def boucle():
    global mesures
    with open(CONFIG, encoding="utf-8") as fichier:
        conf = json.load(fichier)
    etat = charger_etat()
    threading.Thread(target=http.server.ThreadingHTTPServer(("", PORT), Mesures).serve_forever, daemon=True).start()
    while "curseur" not in etat:
        try:
            amorcer(conf, etat, time.time() - 30)
            sauver_etat(etat)
        except Exception as erreur:  # VictoriaLogs pas encore prêt (démarrage de la pile) : on réessaie
            journal("amorcage_reporte", erreur=repr(erreur))
            time.sleep(INTERVALLE)
    while True:
        maintenant = time.time()
        fin = maintenant - 30  # laisse aux journaux le temps d'arriver
        lecture_ok = True
        try:
            debut = min(etat["curseur"], fin) - RECOUVREMENT
            evenements = lire_evenements(conf, debut, fin)
            if any(e["type"] in TYPES_ECHEC for e in evenements):
                rattacher_comptes(evenements, lire_comptes(conf, debut, fin))
            traiter(conf, etat, evenements)
            for ip in [i for i in etat["connues"] if i not in etat["ptr"]][:10]:  # opérateurs manquants, sans à-coup
                operateur(etat, ip)
            etat["curseur"] = fin
            etat["vus"] = {i: q for i, q in etat["vus"].items() if q > fin - 2 * RECOUVREMENT}
            envoyer(alertes(conf, etat, maintenant) + resume_quotidien(conf, etat, maintenant))
            sauver_etat(etat)
        except Exception as erreur:  # VictoriaLogs ou Alertmanager indisponible : on réessaie au tour suivant
            lecture_ok = False
            journal("erreur", erreur=repr(erreur))
        with verrou:
            mesures = calculer_mesures(etat, maintenant, lecture_ok)
        time.sleep(INTERVALLE)


if __name__ == "__main__":
    try:
        boucle()
    except KeyboardInterrupt:
        sys.exit(0)
