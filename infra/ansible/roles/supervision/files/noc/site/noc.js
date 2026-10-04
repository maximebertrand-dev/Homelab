// NOC du homelab : lit l'instantané /etat.json (produit par le collecteur) et l'affiche.
// Aucune donnée n'est insérée comme HTML : tout passe par textContent, la page ne peut pas être détournée.
"use strict";

const SVG = "http://www.w3.org/2000/svg";
const racine = document.documentElement;
let dernierEtat = null;
let prochainChargement = null;

// --- Utilitaires -----------------------------------------------------------------------------------

function el(balise, attributs = {}, ...enfants) {
  const noeud = document.createElement(balise);
  for (const [cle, valeur] of Object.entries(attributs)) {
    if (valeur === null || valeur === undefined || valeur === false) continue;
    if (cle === "classe") noeud.className = valeur;
    else if (cle === "texte") noeud.textContent = valeur;
    else noeud.setAttribute(cle, valeur === true ? "" : String(valeur));
  }
  for (const enfant of enfants.flat()) {
    if (enfant === null || enfant === undefined || enfant === false) continue;
    noeud.append(enfant instanceof Node ? enfant : document.createTextNode(String(enfant)));
  }
  return noeud;
}

function svg(balise, attributs = {}) {
  const noeud = document.createElementNS(SVG, balise);
  for (const [cle, valeur] of Object.entries(attributs)) noeud.setAttribute(cle, String(valeur));
  return noeud;
}

function remplacer(id, ...enfants) {
  const conteneur = document.getElementById(id);
  conteneur.replaceChildren(...enfants.flat().filter(Boolean));
}

const pourcent = (v, chiffres = 0) =>
  v === null || v === undefined ? "–" : `${(Math.min(v, 1) * 100).toFixed(chiffres).replace(".", ",")} %`;

function duree(secondes) {
  const j = Math.floor(secondes / 86400);
  const h = Math.floor((secondes % 86400) / 3600);
  const m = Math.floor((secondes % 3600) / 60);
  if (j > 0) return `${j} j ${h} h`;
  if (h > 0) return `${h} h ${m} min`;
  return `${m} min`;
}

function depuis(dateIso) {
  const ecart = Math.max(0, (Date.now() - new Date(dateIso).getTime()) / 1000);
  if (ecart < 60) return `il y a ${Math.round(ecart)} s`;
  if (ecart < 3600) return `il y a ${Math.round(ecart / 60)} min`;
  if (ecart < 86400) return `il y a ${Math.round(ecart / 3600)} h`;
  return `il y a ${Math.round(ecart / 86400)} j`;
}

const niveau = (v) => (v >= 0.9 ? "critique" : v >= 0.75 ? "haut" : "normal");

// --- Composants ------------------------------------------------------------------------------------

function pastille(ok) {
  return el("span", { classe: "pastille", "data-ok": ok === true ? "true" : ok === false ? "false" : ok, "aria-hidden": "true" });
}

function statut(ok, texteOk, texteKo) {
  return el("span", { classe: "statut", "data-ok": ok === true ? "true" : ok === false ? "false" : ok },
    pastille(ok), ok === true ? texteOk : texteKo);
}

function jauge(nom, valeur) {
  const v = valeur ?? 0;
  const barre = el("span");
  barre.style.width = `${Math.min(v, 1) * 100}%`;
  return el("div", { classe: "jauge", "data-niveau": niveau(v) },
    el("span", { classe: "jauge__nom", texte: nom }),
    el("span", { classe: "jauge__barre", role: "meter", "aria-label": nom, "aria-valuemin": 0, "aria-valuemax": 100,
      "aria-valuenow": Math.round(v * 100) }, barre),
    el("span", { classe: "jauge__valeur", texte: pourcent(valeur) }));
}

// Courbe sur 24 h : points [horodatage, valeur] ; max fixe (1 pour un ratio) ou calculé.
function courbe(points, { max = null, variante = "", titre = "" } = {}) {
  if (!points || points.length < 2) return null;
  const largeur = 100, hauteur = 40;
  const valeurs = points.map((p) => p[1]);
  const haut = max ?? Math.max(...valeurs, 1) * 1.15;
  const t0 = points[0][0], t1 = points[points.length - 1][0];
  const x = (t) => ((t - t0) / Math.max(1, t1 - t0)) * largeur;
  const y = (v) => hauteur - (Math.min(v, haut) / haut) * hauteur;
  const trace = points.map((p, i) => `${i ? "L" : "M"}${x(p[0]).toFixed(2)},${y(p[1]).toFixed(2)}`).join(" ");
  const dessin = svg("svg", { class: `courbe ${variante}`, viewBox: `0 0 ${largeur} ${hauteur}`, preserveAspectRatio: "none",
    role: "img", "aria-label": titre });
  dessin.append(
    svg("path", { class: "aire", d: `${trace} L${largeur},${hauteur} L0,${hauteur} Z` }),
    svg("path", { class: "ligne", d: trace }));
  return dessin;
}

function definitionsSvg() {
  const defs = svg("svg", { width: 0, height: 0, "aria-hidden": "true", class: "defs-cachees" });
  const degrade = svg("linearGradient", { id: "degrade-courbe", x1: 0, y1: 0, x2: 0, y2: 1 });
  degrade.append(
    svg("stop", { offset: "0", "stop-color": "#2dd4bf", "stop-opacity": ".35" }),
    svg("stop", { offset: "1", "stop-color": "#818cf8", "stop-opacity": "0" }));
  const conteneur = svg("defs");
  conteneur.append(degrade);
  defs.append(conteneur);
  document.body.prepend(defs);
}

// --- Rendu des blocs -------------------------------------------------------------------------------

const TITRES = {
  ok: ["Tous les systèmes sont opérationnels", "Services, machines et stockage fonctionnent normalement."],
  degrade: ["Fonctionnement dégradé", "Un élément demande de l'attention ; les services restent accessibles."],
  incident: ["Incident en cours", "Au moins une alerte critique est active : l'administrateur a été prévenu."],
  inconnu: ["État inconnu", "La collecte des données a échoué : la supervision est peut-être indisponible."],
};

function rendreBandeau(etat) {
  const [titre, detail] = TITRES[etat.etat] ?? TITRES.inconnu;
  const bandeau = document.getElementById("bandeau");
  bandeau.dataset.etat = etat.etat === "inconnu" ? "inconnu-erreur" : etat.etat;
  document.getElementById("etat-titre").textContent = titre;
  document.getElementById("etat-detail").textContent = detail;
  document.title = `${etat.etat === "ok" ? "●" : "▲"} NOC · homelab`;
}

function rendreChiffres(etat) {
  const services = etat.services ?? [];
  const machines = etat.machines ?? [];
  const enLigne = services.filter((s) => s.ok).length;
  const joignables = machines.filter((m) => m.ok).length;
  const dispos = services.map((s) => s.dispo_24h).filter((v) => v !== null && v !== undefined);
  const moyenne = dispos.length ? dispos.reduce((a, b) => a + b, 0) / dispos.length : null;
  const valeurs = {
    "c-services": [`${enLigne}/${services.length}`, enLigne < services.length],
    "c-machines": [`${joignables}/${machines.length}`, joignables < machines.length],
    "c-dispo": [pourcent(moyenne, 2), moyenne !== null && moyenne < 0.99],
    "c-alertes": [String((etat.alertes ?? []).length), (etat.alertes ?? []).length > 0],
  };
  for (const [id, [texte, mauvais]] of Object.entries(valeurs)) {
    const noeud = document.getElementById(id);
    noeud.textContent = texte;
    noeud.toggleAttribute("data-mauvais", mauvais);
  }
}

function rendreAlertes(alertes) {
  if (!alertes.length) {
    const icone = svg("svg", { viewBox: "0 0 24 24", "aria-hidden": "true" });
    icone.append(svg("path", { d: "M20 6 9 17l-5-5" }));
    remplacer("alertes", el("div", { classe: "vide" }, icone, "Aucune alerte en cours."));
    return;
  }
  remplacer("alertes", el("div", { classe: "alertes" }, alertes.map((a) =>
    el("article", { classe: "alerte", "data-severite": a.severite },
      el("span", { classe: "alerte__badge", texte: a.severite }),
      el("p", { classe: "alerte__resume", texte: a.resume || a.nom }),
      el("span", { classe: "alerte__depuis", texte: a.depuis ? depuis(a.depuis) : "" }),
      el("p", { classe: "alerte__description", texte: a.description })))));
}

function rendreServices(services, historique) {
  remplacer("services", services.map((s) => {
    const certificatBientot = s.certificat_jours !== null && s.certificat_jours < 14;
    const barre = el("span");
    barre.style.width = `${(s.dispo_7j ?? 0) * 100}%`;
    return el("article", { classe: "carte", "data-ok": String(s.ok) },
      el("div", { classe: "carte__tete" }, pastille(s.ok), el("h3", { texte: s.nom })),
      el("p", { classe: "carte__sous" }, el("a", { href: `https://${s.id}/`, rel: "noopener", texte: s.id })),
      s.description ? el("p", { classe: "carte__sous", texte: s.description }) : null,
      el("div", { classe: "mesures" },
        el("div", { classe: "mesure" }, el("p", { classe: "mesure__valeur", texte: s.ok ? `${s.latence_ms} ms` : "échec" }),
          el("p", { classe: "mesure__libelle", texte: "réponse" })),
        el("div", { classe: "mesure" }, el("p", { classe: "mesure__valeur", texte: pourcent(s.dispo_24h, 2) }),
          el("p", { classe: "mesure__libelle", texte: "dispo 24 h" })),
        el("div", { classe: "mesure", "data-avert": certificatBientot },
          el("p", { classe: "mesure__valeur", texte: s.certificat_jours === null ? "–" : `${s.certificat_jours} j` }),
          el("p", { classe: "mesure__libelle", texte: "certificat" }))),
      courbe(historique?.latence?.[s.id], { titre: `Temps de réponse de ${s.nom} sur 24 heures` }),
      el("div", { classe: "dispo", title: `Disponibilité sur 7 jours : ${pourcent(s.dispo_7j, 2)}` },
        el("div", { classe: "dispo__barre" }, barre)));
  }));
}

function rendreMachines(machines, historique) {
  remplacer("machines", machines.map((m) =>
    el("article", { classe: "carte", "data-ok": String(m.ok) },
      el("div", { classe: "carte__tete" }, pastille(m.ok), el("h3", { texte: m.nom })),
      el("p", { classe: "carte__sous", texte: m.role || " " }),
      m.ok ? el("div", { classe: "jauges" },
        jauge("Processeur", m.processeur), jauge("Mémoire", m.memoire), jauge("Disque", m.disque)) :
        el("p", { classe: "avertissement", texte: "Machine injoignable par la supervision." }),
      courbe(historique?.processeur?.[m.id], { max: 1, titre: `Processeur de ${m.nom} sur 24 heures` }),
      el("div", { classe: "carte__pied" },
        el("span", { texte: `en service ${duree(m.uptime_s)}` }),
        el("span", { texte: `${m.coeurs} cœurs · ${String(m.memoire_go).replace(".", ",")} Go` }),
        el("span", { texte: `charge ${String(m.charge ?? "–").replace(".", ",")}` })))));
}

function rendreStockage(stockage) {
  const pools = stockage.pools ?? [];
  const tete = el("div", { classe: "panneau__tete" },
    el("div", {}, ...pools.map((p) => el("p", {},
      el("strong", { texte: `Pool ${p.nom} ` }),
      statut(p.etat === "online" ? true : false, "sain (ONLINE)", p.etat.toUpperCase())))),
    // Sans relevé de l'hyperviseur, repli sur l'occupation du stockage des VM (local-zfs) ; sinon, le total est plus bas.
    !stockage.total && stockage.occupation !== null ? jauge("Occupation", stockage.occupation) : null);
  const lignes = (stockage.disques ?? []).map((d) => {
    const etat = !d.ok ? false : d.defauts > 0 ? "avert" : true;
    return el("tr", {},
      el("td", {}, el("strong", { texte: d.nom }), el("span", { classe: "discret masque-mobile", texte: ` ${d.modele}` })),
      el("td", {}, statut(etat, "SMART OK", d.ok ? "à surveiller" : "en échec")),
      el("td", { classe: "nombre", texte: d.temperature === null ? "–" : `${d.temperature} °C` }),
      el("td", { classe: "nombre masque-mobile", texte: `${(d.heures / 8766).toFixed(1).replace(".", ",")} ans` }),
      el("td", { classe: "nombre", texte: String(d.defauts) }));
  });
  // Jeux de données suivis (relevé de l'hyperviseur) et total du pool : place occupée sur la place permise.
  const jeux = [...(stockage.donnees ?? []), ...(stockage.total ? [{ nom: "Total", ...stockage.total }] : [])];
  const donnees = jeux.length ? el("div", { classe: "donnees" }, ...jeux.map((j) => el("div", {},
    jauge(j.nom, j.ratio),
    el("p", { classe: "discret", texte: `${octets(j.utilise)} sur ${octets(j.permis)}` })))) : null;
  remplacer("stockage", el("div", { classe: "panneau" }, tete, donnees,
    el("table", {},
      el("thead", {}, el("tr", {},
        el("th", { texte: "Disque" }), el("th", { texte: "Santé" }), el("th", { classe: "nombre", texte: "Temp." }),
        el("th", { classe: "nombre masque-mobile", texte: "En service" }), el("th", { classe: "nombre", texte: "Défauts" }))),
      el("tbody", {}, lignes))));
}

function octets(n) {
  const unites = ["o", "Ko", "Mo", "Go", "To"];
  let i = 0;
  while (n >= 1024 && i < unites.length - 1) { n /= 1024; i += 1; }
  return `${n.toFixed(i >= 3 ? 1 : 0).replace(".", ",")} ${unites[i]}`;
}

function rendreSauvegarde(s) {
  if (!s) {
    remplacer("sauvegarde", el("div", { classe: "panneau" }, el("p", { classe: "discret", texte: "Aucune sauvegarde encore exécutée." })));
    return;
  }
  const verification = s.verification === 1 ? true : s.verification === 0 ? false : "avert";
  const ligne = (libelle, ...contenu) => el("tr", {}, el("td", { texte: libelle }), el("td", {}, ...contenu));
  remplacer("sauvegarde", el("div", { classe: "panneau" },
    el("div", { classe: "panneau__tete" },
      el("p", {}, el("strong", { texte: "Dernier passage " }), statut(s.ok, "réussi", "en échec")),
      s.espace !== null ? jauge("Stockage distant", s.espace) : null),
    el("table", {}, el("tbody", {},
      ligne("Dernière réussite", el("span", { texte: s.depuis_reussite_s === null ? "jamais" : `il y a ${duree(s.depuis_reussite_s)}` })),
      ligne("Empreintes (SHA-256)", statut(verification, "conformes", s.verification === 0 ? "ÉCART" : "non vérifiées"),
        el("span", { classe: "discret", texte: ` ${s.fichiers_verifies} fichiers, ${octets(s.octets_verifies)}` })),
      ligne("Dernière vérification réussie", el("span", { texte: s.depuis_verification_s === null ? "jamais" : `il y a ${duree(s.depuis_verification_s)}` })),
      ligne("Durée, données ajoutées", el("span", { texte: `${duree(s.duree_s)}, ${octets(s.ajoute_octets)}` }))))));
}

function rendreVms(vms) {
  const lignes = vms.map((v) =>
    el("tr", {},
      el("td", {}, el("strong", { texte: v.nom }), el("span", { classe: "discret", texte: ` ${v.vmid}` })),
      el("td", {}, statut(v.allumee ? true : v.demarrage_auto ? false : "avert", "allumée", "arrêtée")),
      el("td", { classe: "nombre", texte: v.allumee ? pourcent(v.processeur, 1) : "–" }),
      el("td", { classe: "nombre", texte: `${String(v.memoire_go ?? "–").replace(".", ",")} Go` })));
  remplacer("vms", el("div", { classe: "panneau" },
    el("table", {},
      el("thead", {}, el("tr", {},
        el("th", { texte: "VM" }), el("th", { texte: "État" }),
        el("th", { classe: "nombre", texte: "CPU" }), el("th", { classe: "nombre", texte: "Mémoire allouée" }))),
      el("tbody", {}, lignes))));
}

const ETATS_TRANSFERT = { 1: [true, "en cours"], 2: [true, "terminé"], 3: [false, "en échec"], 4: ["avert", "programmé (nuit)"],
  5: ["avert", "interrompu"] };

function rendreTransferts(liste) {
  if (!liste.length) {
    remplacer("transferts", el("div", { classe: "panneau" }, el("p", { classe: "discret", texte: "Aucun transfert en cours ni récent." })));
    return;
  }
  const lignes = liste.map((t) => {
    const [ok, libelle] = ETATS_TRANSFERT[t.etat] ?? ["avert", "inconnu"];
    // Avancement en volume (copie de fichiers) ou, à défaut, en nombre de fichiers (envoi des photos).
    const enFichiers = !(t.total > 0) && t.fichiers_total > 0;
    // Terminé : 100 %, même si le journal n'a plus les lignes d'avancement (rotation).
    const part = t.etat === 2 ? 1 : t.total > 0 ? t.octets / t.total : enFichiers ? t.fichiers / t.fichiers_total : 0;
    const nombre = (n) => n.toLocaleString("fr-FR");
    const barre = el("span");
    barre.style.width = `${Math.min(part, 1) * 100}%`;
    const fin = t.etat === 1 ? (t.eta_s === null ? "–" : `dans ${duree(t.eta_s)}`)
      : t.depuis_fin_s !== null ? `il y a ${duree(t.depuis_fin_s)}` : "–";
    return el("tr", {},
      el("td", {}, el("strong", { texte: t.nom })),
      el("td", {}, statut(ok, libelle, libelle)),
      el("td", {}, el("div", { classe: "progression" },
        el("span", { classe: "progression__barre", role: "progressbar", "aria-valuemin": 0, "aria-valuemax": 100,
          "aria-valuenow": Math.round(part * 100), "aria-label": t.nom }, barre),
        el("span", { classe: "progression__valeur", texte: pourcent(part) }))),
      el("td", { classe: "nombre", texte: t.total > 0 ? `${octets(t.octets)} / ${octets(t.total)}`
        : enFichiers ? `${nombre(t.fichiers)} / ${nombre(t.fichiers_total)} fichiers` : "–" }),
      el("td", { classe: "nombre", texte: t.etat !== 1 ? "–"
        : enFichiers ? `${nombre(Math.round(t.debit_fichiers * 60))} fichiers/min` : `${octets(t.debit)}/s` }),
      el("td", { classe: "nombre", texte: fin }),
      el("td", { classe: "nombre", texte: String(t.erreurs) }));
  });
  remplacer("transferts", el("div", { classe: "panneau" },
    el("table", {},
      el("thead", {}, el("tr", {},
        el("th", { texte: "Travail" }), el("th", { texte: "État" }), el("th", { texte: "Avancement" }),
        el("th", { classe: "nombre", texte: "Copié" }), el("th", { classe: "nombre", texte: "Débit" }),
        el("th", { classe: "nombre", texte: "Fin" }), el("th", { classe: "nombre", texte: "Erreurs" }))),
      el("tbody", {}, lignes))));
}

let prochainChargementAdmin;

async function chargerAdmin() {
  clearTimeout(prochainChargementAdmin);
  try {
    const reponse = await fetch("/admin.json", { cache: "no-store", credentials: "same-origin", redirect: "manual" });
    if (reponse.ok) rendreTransferts((await reponse.json()).transferts ?? []);
  } catch { /* bloc facultatif : l'état général reste affiché */ }
  prochainChargementAdmin = setTimeout(chargerAdmin, 60 * 1000);
}

function rendreOutils(outils) {
  remplacer("outils", outils.map((o) => el("span", { classe: "puce" }, pastille(o.ok), o.nom)));
}

function rendre(etat) {
  dernierEtat = etat;
  rendreBandeau(etat);
  if (!etat.collecte?.ok) return;
  rendreChiffres(etat);
  rendreAlertes(etat.alertes ?? []);
  rendreServices(etat.services ?? [], etat.historique);
  rendreMachines(etat.machines ?? [], etat.historique);
  rendreStockage(etat.stockage ?? {});
  rendreSauvegarde(etat.sauvegarde ?? null);
  rendreVms(etat.vms ?? []);
  rendreOutils(etat.outils ?? []);
}

// --- Fraîcheur et chargement -----------------------------------------------------------------------

function majFraicheur() {
  const direct = document.getElementById("direct");
  const texte = document.getElementById("direct-texte");
  if (!dernierEtat) return;
  const age = (Date.now() - new Date(dernierEtat.genere).getTime()) / 1000;
  const limite = (dernierEtat.intervalle ?? 30) * 3;
  if (!dernierEtat.collecte?.ok) {
    direct.dataset.etat = "erreur";
    texte.textContent = "collecte en échec";
  } else if (age > limite) {
    direct.dataset.etat = "ancien";
    texte.textContent = `données figées (${depuis(dernierEtat.genere)})`;
  } else {
    direct.dataset.etat = "ok";
    texte.textContent = `en direct · ${depuis(dernierEtat.genere)}`;
  }
  document.getElementById("genere").textContent =
    `dernier instantané : ${new Date(dernierEtat.genere).toLocaleString("fr-FR")}`;
}

async function charger() {
  clearTimeout(prochainChargement);
  try {
    const reponse = await fetch("/etat.json", { cache: "no-store", credentials: "same-origin", redirect: "manual" });
    // Session SSO expirée : le WAF renvoie vers le portail ; recharger la page ramène à la connexion.
    if (reponse.type === "opaqueredirect" || reponse.status === 401) {
      window.location.reload();
      return;
    }
    if (!reponse.ok) throw new Error(`HTTP ${reponse.status}`);
    rendre(await reponse.json());
  } catch {
    document.getElementById("direct").dataset.etat = "erreur";
    document.getElementById("direct-texte").textContent = "hors connexion";
  }
  majFraicheur();
  prochainChargement = setTimeout(charger, (dernierEtat?.intervalle ?? 30) * 1000);
}

async function afficherUtilisateur() {
  try {
    const reponse = await fetch("/moi.json", { cache: "no-store", credentials: "same-origin" });
    const moi = await reponse.json();
    if (moi.utilisateur) {
      const noeud = document.getElementById("utilisateur");
      noeud.textContent = moi.utilisateur;
      noeud.hidden = false;
    }
    // Blocs réservés : le serveur refuse de toute façon /admin.json aux autres comptes.
    if (moi.admin === true) {
      document.getElementById("bloc-transferts").hidden = false;
      chargerAdmin();
    }
  } catch { /* information de confort uniquement */ }
}

// --- Thème (mémorisé dans le navigateur, comme sur le site) -----------------------------------------

function appliquerTheme(theme) {
  racine.dataset.theme = theme;
}

function initialiserTheme() {
  let theme = "auto";
  try { theme = localStorage.getItem("theme-noc") || "auto"; } catch { /* stockage indisponible */ }
  appliquerTheme(theme);
  document.getElementById("bascule-theme").addEventListener("click", () => {
    const sombre = racine.dataset.theme === "clair" ? false :
      racine.dataset.theme === "auto" ? !window.matchMedia("(prefers-color-scheme: light)").matches : true;
    const suivant = sombre ? "clair" : "sombre";
    appliquerTheme(suivant);
    try { localStorage.setItem("theme-noc", suivant); } catch { /* sans importance */ }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initialiserTheme();
  definitionsSvg();
  afficherUtilisateur();
  charger();
  setInterval(majFraicheur, 1000);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) charger(); });
});
