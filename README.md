Voici une analyse des deux scripts et un **README.md ultra-détaillé** prêt à l’emploi.

---

# PASSCHENDAELE v5b — Violent Dorking Engine

> « Through mud and wire, we find what they forgot to hide. »  
> *In the mud of Flanders, secrets lie buried. We dig them up.*

**Référence historique** : 3ᵉ bataille d’Ypres (Passchendaele), octobre-novembre 1917.  
Outil de **reconnaissance passive** (OSINT) basé sur le *Google Dorking* multi-moteurs, conçu pour découvrir des informations indexées publiquement (fichiers sensibles, configurations, credentials, panels d’administration, erreurs applicatives, etc.).

---

## 1. Vue d’ensemble

| Composant                    | Fichier                     | Rôle                                                                 |
|-----------------------------|-----------------------------|----------------------------------------------------------------------|
| **Moteur principal**        | `Passchendaele-mud.py`      | Bibliothèque de dorks + scraping multi-moteurs + export + scoring   |
| **Orchestrateur**           | `passchendaele_mega.sh`     | Wrapper Bash proposant des modes préconfigurés (full / stealth / quick / custom) |

L’outil interroge les moteurs de recherche (Google, Bing, DuckDuckGo, Yandex) avec des *dorks* avancés (`site:`, `ext:`, `inurl:`, `intitle:`, etc.), parse les résultats HTML, déduplique, filtre par domaine cible, et exporte en JSON / CSV / HTML avec scoring de criticité.

---

## 2. Architecture technique

### 2.1 Couches principales (`Passchendaele-mud.py`)

```
┌─────────────────────────────────────────────────────────────┐
│  CLI (argparse)                                             │
│  → DorkConfig (dataclass)                                   │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│  PasschendaeleEngine                                        │
│  ├── Bibliothèque DORK_LIBRARY (catégories + sévérité)      │
│  ├── Multi-engine (Google / Bing / DDG / Yandex)            │
│  ├── Déduplication (SHA-256 partiel + set d’URLs)           │
│  ├── Filtrage domaine                                       │
│  ├── Export (JSON / CSV / HTML)                             │
│  └── Affichage (Rich + ASCII art + résumé)                  │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│  SearchEngine (classe abstraite)                            │
│  ├── Session requests + Retry (urllib3)                     │
│  ├── UA rotation + headers réalistes                        │
│  ├── Rate-limiting (delay + jitter)                         │
│  ├── Support Tor (PySocks SOCKS5 127.0.0.1:9050)            │
│  └── Parsing regex spécifique à chaque moteur               │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Modèles de données

```python
@dataclass
class DorkResult:
    dork: str
    category: str
    severity: str          # CRITICAL / HIGH / MEDIUM / LOW
    url: str
    title: str
    snippet: str
    engine: str
    timestamp: str         # ISO 8601 UTC
    target: str
    sha256: str            # 16 premiers caractères du hash de l’URL
```

```python
@dataclass
class DorkConfig:
    target: str
    categories: List[str]
    engines: List[str]
    max_results_per_dork: int = 10
    max_pages: int = 3
    timeout: int = 15
    delay: float = 2.0
    jitter: float = 1.0
    tor: bool = False
    stealth: bool = False
    output: Optional[str] = None
    output_format: str = "json"
    custom_dorks: List[str] = field(default_factory=list)
```

### 2.3 Bibliothèque de dorks (`DORK_LIBRARY`)

| Catégorie            | Sévérité  | Exemples de dorks                                                                 |
|----------------------|-----------|-----------------------------------------------------------------------------------|
| `sensitive_files`    | CRITICAL  | `ext:env`, `.git/config`, `.aws/credentials`, `id_rsa`, `wp-config.php`          |
| `auth_exposure`      | CRITICAL  | `api_key`, `aws_secret_access_key`, `BEGIN RSA PRIVATE KEY`, `client_secret`     |
| `vulnerabilities`    | CRITICAL  | `sql syntax`, `mysql error`, `phpinfo.php`, `stack trace`, `fatal error`         |
| `cloud_storage`      | CRITICAL  | `s3.amazonaws.com`, `storage.googleapis.com`, `blob.core.windows.net`            |
| `backups`            | HIGH      | `ext:sql`, `ext:bak`, `database dump`, `inurl:backup`                            |
| `admin_panels`       | HIGH      | `inurl:admin`, `phpmyadmin`, `cpanel`, `intitle:"login" "admin"`                 |
| `code_exposure`      | HIGH      | `ext:php "password"`, `inurl:github.com "{target}"`                              |
| `directory_listing`  | MEDIUM    | `intitle:"index of /"`, `"[To Parent Directory]"`                                |
| `email_exposure`     | MEDIUM    | `@{target} ext:txt`, `mailto:`                                                   |
| `subdomains`         | MEDIUM    | `site:*.{target}`, `inurl:dev|staging|test|api`                                  |

---

## 3. Fonctionnalités clés

### 3.1 Multi-moteurs avec fallback
- **Google** : scraping HTML + détection CAPTCHA / rate-limit (pause 60 s)
- **Bing** : parsing des résultats `b_algo`
- **DuckDuckGo** (HTML) : extraction via paramètres `uddg=`
- **Yandex** : parsing basique des titres

### 3.2 OPSEC / Stealth
- Rotation de User-Agents (Chrome, Safari, Firefox, Googlebot, Bingbot)
- Delay + jitter aléatoire
- Mode `--stealth` : force `delay ≥ 5 s` et `jitter ≥ 3 s`
- Support Tor via PySocks (`--tor`)
- Headers HTTP réalistes
- Retry automatique sur 429 / 5xx

### 3.3 Qualité des résultats
- Déduplication stricte par URL
- Filtrage hors-cible (sauf catégorie « Sous-domaines »)
- Scoring de sévérité par catégorie
- Hash SHA-256 partiel pour identification unique

### 3.4 Exports
| Format | Contenu |
|--------|---------|
| **JSON** | Structure complète + `total_results` |
| **CSV**  | Toutes les colonnes du `DorkResult` |
| **HTML** | Rapport stylisé (thème sombre « boue / fil de fer ») avec couleurs de sévérité |

---

## 4. Installation

```bash
# Dépendances système
sudo apt update && sudo apt install -y python3 python3-pip tor jq

# Dépendances Python
pip3 install requests rich pysocks

# (Optionnel) Activer Tor
sudo systemctl enable --now tor
```

Placez les deux fichiers dans le même répertoire :

```bash
chmod +x passchendaele_mega.sh
chmod +x Passchendaele-mud.py   # ou laissez le nom original
```

---

## 5. Utilisation

### 5.1 Script Python direct

```bash
# Scan complet
python3 Passchendaele-mud.py --target example.com --category all

# Catégories ciblées
python3 Passchendaele-mud.py -t example.com -c sensitive_files,auth_exposure,vulnerabilities

# Dorks personnalisés
python3 Passchendaele-mud.py -t example.com \
  --dork 'site:example.com ext:env' \
  --dork 'site:example.com "DB_PASSWORD"'

# Mode stealth + Tor + export
python3 Passchendaele-mud.py -t example.com \
  --stealth --tor \
  --engine duckduckgo,bing \
  --output results.json --format json

# Rapport HTML
python3 Passchendaele-mud.py -t example.com -o report.html -f html
```

### 5.2 Orchestrateur Bash (`passchendaele_mega.sh`)

```bash
./passchendaele_mega.sh <target> [mode]
```

| Mode      | Description                                                                 | Paramètres typiques                          |
|-----------|-----------------------------------------------------------------------------|----------------------------------------------|
| `full`    | Toutes les catégories, 3 moteurs, max 20 résultats, 5 pages                | delay=2, jitter=1                            |
| `stealth` | Tor + delays élevés + moteurs discrets                                     | delay=5, jitter=3, Tor, DuckDuckGo+Bing      |
| `quick`   | Uniquement catégories critiques                                            | sensitive_files + auth_exposure + vulns      |
| `custom`  | Exemple de dorks personnalisés (à éditer)                                  | éditable dans le script                      |

**Variables d’environnement** :
- `SCRIPT` → chemin vers le Python (défaut : `./Passchendaele-mud.py`)
- `OUTPUT_DIR` → dossier de sortie (défaut : `./passchendaele_results`)

Exemple :

```bash
OUTPUT_DIR=./recon ./passchendaele_mega.sh example.com stealth
```

Le script génère automatiquement :
- `{target}_{mode}_{timestamp}.json`
- `{target}_{mode}_{timestamp}.html`
- Statistiques via `jq`

---

## 6. Options CLI complètes

```
--target / -t          Domaine cible (obligatoire)
--category / -c        Catégories (virgules) ou "all" (défaut: all)
--engine / -e          Moteurs (défaut: google,bing,duckduckgo)
--dork / -d            Dork personnalisé (répétable)
--max-results          Résultats max par dork (défaut: 10)
--max-pages            Pages max par moteur (défaut: 3)
--delay                Délai de base en secondes (défaut: 2.0)
--jitter               Jitter aléatoire (défaut: 1.0)
--tor                  Active le proxy SOCKS5 Tor
--stealth              Force delay/jitter élevés
--output / -o          Fichier de sortie
--format / -f          json | csv | html (défaut: json)
```

---

## 7. Points techniques importants

### 7.1 Parsing des moteurs
Les regex HTML sont **fragiles**. Les moteurs changent régulièrement leur structure. En cas d’échec massif :
- Vérifier la présence de CAPTCHA
- Réduire le nombre de pages / résultats
- Privilégier DuckDuckGo en mode stealth

### 7.2 Tor
Nécessite :
1. Tor en écoute sur `127.0.0.1:9050`
2. Package `PySocks`
3. Option `--tor`

### 7.3 Rate-limiting & CAPTCHA
- Google : détection « unusual traffic » → arrêt du moteur
- 429 → pause de 60 secondes (Google)
- Recommandation : ne jamais lancer un mode `full` sans Tor + delays élevés

### 7.4 Filtrage domaine
Sauf pour la catégorie « Sous-domaines », seules les URLs contenant le `target` dans le `netloc` sont conservées.

---

## 8. Limitations connues

| Limitation                              | Impact / Contournement                                      |
|-----------------------------------------|-------------------------------------------------------------|
| Scraping HTML fragile                   | Moteurs évoluent → parsers à mettre à jour régulièrement   |
| CAPTCHA / rate-limit                    | Mode stealth + Tor + délais longs                          |
| Pas d’API officielle                    | Violation potentielle des ToS des moteurs                  |
| Pas de validation des liens trouvés     | Les résultats doivent être vérifiés manuellement           |
| Yandex & Google plus stricts            | Préférer DuckDuckGo + Bing en production                   |
| Pas de support multi-threading          | Volontaire (OPSEC)                                         |

---

## 9. Recommandations d’usage éthique & légal

- **Uniquement** sur des cibles pour lesquelles vous avez une autorisation écrite (bug bounty, pentest, audit interne).
- Les dorks ne font que révéler des informations **déjà indexées publiquement**.
- Toute exploitation active (accès non autorisé, téléchargement de backups, etc.) est illégale.
- Conservez des logs et un scope clair.

---

## 10. Exemple de sortie JSON

```json
{
  "target": "example.com",
  "timestamp": "2025-10-26T12:34:56.789012+00:00",
  "total_results": 17,
  "results": [
    {
      "dork": "site:{target} ext:env",
      "category": "Fichiers Sensibles",
      "severity": "CRITICAL",
      "url": "https://example.com/.env.backup",
      "title": "Index of /.env.backup",
      "snippet": "...",
      "engine": "duckduckgo",
      "timestamp": "2025-10-26T12:35:01.123456+00:00",
      "target": "example.com",
      "sha256": "a1b2c3d4e5f67890"
    }
  ]
}
```

---

## 11. Roadmap / Améliorations possibles

- [ ] Support Brave Search & Startpage
- [ ] Intégration SerpAPI / Google Custom Search API (option payante)
- [ ] Validation automatique des liens (HEAD request + content-type)
- [ ] Scoring plus fin (mots-clés dans snippet + extension)
- [ ] Mode « continuous monitoring »
- [ ] Export Markdown / PDF
- [ ] Proxy list rotation (en plus de Tor)

---

## 12. Licence & Avertissement

Cet outil est fourni **à des fins éducatives et de sécurité offensive légitime uniquement**.  
Les auteurs déclinent toute responsabilité quant à une utilisation illégale ou non éthique.

---

**« In Flanders fields the poppies blow… We dig through mud, we find the truth. »**
