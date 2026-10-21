variable "etat_passphrase" {
  description = "Phrase de passe de chiffrement de l'état. Fournie par variable d'environnement."
  type        = string
  sensitive   = true
}

variable "cloudflare_api_token" {
  description = "Jeton API Cloudflare (droits : Zone DNS Edit, Cloudflare Tunnel Edit)."
  type        = string
  sensitive   = true
}

variable "account_id" {
  description = "Identifiant du compte Cloudflare."
  type        = string
}

variable "vitrine_zone_id" {
  description = "Zone ID de maximebertrand.net."
  type        = string
}

variable "vitrine_domain" {
  description = "Domaine du site vitrine."
  type        = string
  default     = "maximebertrand.net"
}

variable "site_public" {
  description = "Nom du site public (documentation / portfolio) servi par le tunnel."
  type        = string
  default     = "maximebertrand.net"
}

variable "site_origin" {
  description = "Service vers lequel cloudflared renvoie le trafic du site (cloudflared tourne à côté de nginx)."
  type        = string
  default     = "http://nginx:8080"
}

variable "publier_status" {
  description = "Publier la page de statut (quand Uptime Kuma sera déployé)."
  type        = bool
  default     = false
}

variable "status_origin" {
  description = "Service interne de la page de statut (Uptime Kuma)."
  type        = string
  default     = "http://status.home.maximebertrand.net:3001"
}

variable "ip_publique" {
  description = "Adresse IPv4 publique de la box (services publiés en direct, voir l'ADR 0008). Valeur privée."
  type        = string
  default     = ""
}

variable "services_publics" {
  description = "Sous-domaines publiés en direct derrière le WAF (enregistrements « DNS only »)."
  type        = list(string)
  default     = []
}

variable "enregistrements_messagerie" {
  description = <<-EOT
    Enregistrements d'envoi des e-mails du homelab (relais transactionnel) : SPF, DKIM, DMARC, MX de retour, tels que
    le relais les indique. Clé = libellé libre ; nom = nom complet ; priorite pour les MX seulement.
  EOT
  type = map(object({
    type     = string
    nom      = string
    contenu  = string
    priorite = optional(number)
  }))
  default = {}

  validation {
    condition     = alltrue([for e in values(var.enregistrements_messagerie) : contains(["TXT", "MX", "CNAME"], e.type)])
    error_message = "Types acceptés pour la messagerie : TXT, MX, CNAME."
  }
}

variable "enregistrements_verification" {
  description = <<-EOT
    Enregistrements TXT par lesquels un service tiers vérifie que le domaine nous appartient (portail de développeurs,
    outil de webmestre…). Clé = libellé libre ; nom = nom complet ; contenu = valeur donnée par le service.
  EOT
  type = map(object({
    nom     = string
    contenu = string
  }))
  default = {}
}
