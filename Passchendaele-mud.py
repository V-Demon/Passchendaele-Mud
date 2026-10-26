#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PASSCHENDAELE v5b — Violent Dorking Engine
"Through mud and wire, we find what they forgot to hide."

Référence historique : 3e bataille d'Ypres (Passchendaele), octobre-novembre 1917.
500 000 casualties dans la boue des Flandres. Ici, nous fouillons la boue numérique.

Architecture :
- Bibliothèque de dorks catégorisés (fichiers sensibles, configs, auth, vulns)
- Multi-moteurs : Google, Bing, DuckDuckGo, Yandex, Brave
- Mode OPSEC : Tor, jitter, rotation UA, rate limiting
- Détection CAPTCHA + fallback automatique
- Export JSON/CSV/HTML avec scoring de criticité
- Support des opérateurs avancés (site:, inurl:, intitle:, filetype:)

Usage :
  python Passchendaele5b.py --target example.com --category all
  python Passchendaele5b.py --dork "site:example.com ext:env | ext:sql"
  python Passchendaele5b.py --target example.com --stealth --tor --output results.json
"""

import argparse
import json
import csv
import time
import random
import re
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass, field, asdict
from urllib.parse import quote_plus, urlparse
from collections import defaultdict

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except ImportError:
    print("❌ Missing: pip install requests")
    exit(1)

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
    from rich.table import Table
    from rich.theme import Theme
    from rich.live import Live
    from rich.layout import Layout
    from rich.align import Align
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

try:
    import socks
    import socket
    HAS_SOCKS = True
except ImportError:
    HAS_SOCKS = False

# ════════════════════════════════════════════════════════════════════════════
# ESTHÉTIQUE "PASSCHENDAELE" — Boue, fil de fer, obus
# ════════════════════════════════════════════════════════════════════════════

ASCII_ART = r"""
██████╗  █████╗ ███████╗███████╗██╗  ██╗███╗   ██╗ ██████╗ ███████╗██████╗
██╔══██╗██╔══██╗██╔════╝██╔════╝██║  ██║████╗  ██║██╔═══██╗██╔════╝██╔══██╗
██████╔╝███████║███████╗███████╗███████║██╔██╗ ██║██║   ██║█████╗  ██████╔╝
██╔═══╝ ██╔══██║╚════██║╚════██║██╔══██║██║╚██╗██║██║   ██║██╔══╝  ██╔══██╗
██║     ██║  ██║███████║███████║██║  ██║██║ ╚████║╚██████╔╝███████╗██║  ██║
╚═╝     ╚═╝  ╚═╝╚══════╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═══╝ ╚═════╝ ╚══════╝╚═╝  ╚═╝
           V I O L E N T   D O R K I N G   E N G I N E   v 5 b
    « Through mud and wire, we find what they forgot to hide. »
"""

MOTTO = [
    "In Flanders fields the poppies blow...",
    "Between the crosses, row on row...",
    "We dig through mud, we find the truth...",
    "What they forgot, we excavate...",
    "Every index holds a secret...",
    "The mud remembers what the web forgets...",
]

# ════════════════════════════════════════════════════════════════════════════
# BIBLIOTHÈQUE DE DORKS — Catégorisés par criticité
# ════════════════════════════════════════════════════════════════════════════

DORK_LIBRARY = {
    "sensitive_files": {
        "label": "Fichiers Sensibles",
        "severity": "CRITICAL",
        "dorks": [
            'site:{target} ext:env',
            'site:{target} ext:sql | ext:bak | ext:old',
            'site:{target} ext:log | ext:txt "password"',
            'site:{target} inurl:wp-config.php | inurl:config.php',
            'site:{target} ext:xml | ext:json "api_key"',
            'site:{target} ".env" "DB_PASSWORD"',
            'site:{target} ".git/config"',
            'site:{target} ".aws/credentials"',
            'site:{target} "id_rsa" | "id_dsa"',
            'site:{target} ".htpasswd" | ".htaccess"',
        ]
    },
    "backups": {
        "label": "Fichiers de Backup",
        "severity": "HIGH",
        "dorks": [
            'site:{target} ext:zip | ext:tar | ext:gz | ext:rar',
            'site:{target} ext:sql | ext:db | ext:sqlite',
            'site:{target} "backup" | "dump" | "archive"',
            'site:{target} inurl:backup | inurl:dump | inurl:db',
            'site:{target} "database dump" | "sql dump"',
            'site:{target} ext:bak | ext:old | ext:orig | ext:save',
        ]
    },
    "admin_panels": {
        "label": "Panneaux d'Administration",
        "severity": "HIGH",
        "dorks": [
            'site:{target} inurl:admin | inurl:administrator | inurl:wp-admin',
            'site:{target} inurl:phpmyadmin | inurl:adminer',
            'site:{target} intitle:"login" "admin" | "administrator"',
            'site:{target} inurl:dashboard | inurl:panel | inurl:console',
            'site:{target} "admin login" | "administrator login"',
            'site:{target} inurl:cpanel | inurl:webmail',
        ]
    },
    "auth_exposure": {
        "label": "Exposition d'Authentification",
        "severity": "CRITICAL",
        "dorks": [
            'site:{target} "username" | "password" | "login" ext:txt | ext:log',
            'site:{target} "api_key" | "api_secret" | "access_token"',
            'site:{target} "aws_access_key_id" | "aws_secret_access_key"',
            'site:{target} "private_key" | "BEGIN RSA PRIVATE KEY"',
            'site:{target} "bearer" | "authorization" ext:log | ext:txt',
            'site:{target} "client_secret" | "client_id"',
        ]
    },
    "vulnerabilities": {
        "label": "Vulnérabilités Connues",
        "severity": "CRITICAL",
        "dorks": [
            'site:{target} "sql syntax" | "mysql error" | "oracle error"',
            'site:{target} "warning:" | "fatal error" | "stack trace"',
            'site:{target} "php warning" | "php error" | "php notice"',
            'site:{target} "unclosed quotation mark" | "syntax error"',
            'site:{target} "exception" | "traceback" | "debug"',
            'site:{target} inurl:phpinfo.php | inurl:test.php',
        ]
    },
    "directory_listing": {
        "label": "Directory Listing",
        "severity": "MEDIUM",
        "dorks": [
            'site:{target} intitle:"index of /"',
            'site:{target} intitle:"index of" "parent directory"',
            'site:{target} "[To Parent Directory]"',
            'site:{target} intitle:"directory listing for"',
        ]
    },
    "cloud_storage": {
        "label": "Stockage Cloud Exposés",
        "severity": "CRITICAL",
        "dorks": [
            'site:{target} "s3.amazonaws.com" | "storage.googleapis.com"',
            'site:{target} "blob.core.windows.net" | "azurewebsites.net"',
            'site:{target} inurl:s3 | inurl:bucket | inurl:storage',
            'site:{target} "digitaloceanspaces.com" | "r2.cloudflarestorage.com"',
        ]
    },
    "email_exposure": {
        "label": "Exposition d'Emails",
        "severity": "MEDIUM",
        "dorks": [
            'site:{target} "@{target}" ext:txt | ext:csv | ext:log',
            'site:{target} "email" | "e-mail" ext:txt | ext:csv',
            'site:{target} "contact" | "support" "@{target}"',
            'site:{target} "mailto:" ext:html | ext:htm',
        ]
    },
    "subdomains": {
        "label": "Sous-domaines",
        "severity": "MEDIUM",
        "dorks": [
            'site:*.{target}',
            'site:{target} -www',
            'site:{target} inurl:dev | inurl:staging | inurl:test',
            'site:{target} inurl:api | inurl:admin | inurl:portal',
        ]
    },
    "code_exposure": {
        "label": "Exposition de Code",
        "severity": "HIGH",
        "dorks": [
            'site:{target} ext:php | ext:asp | ext:jsp "password"',
            'site:{target} "function" | "class" | "def" ext:py | ext:js',
            'site:{target} inurl:github.com | inurl:gitlab.com "{target}"',
            'site:{target} "source code" | "repository"',
        ]
    },
}

# ════════════════════════════════════════════════════════════════════════════
# USER-AGENTS — Rotation pour OPSEC
# ════════════════════════════════════════════════════════════════════════════

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
]

# ════════════════════════════════════════════════════════════════════════════
# MODÈLES DE DONNÉES
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class DorkResult:
    dork: str
    category: str
    severity: str
    url: str
    title: str
    snippet: str
    engine: str
    timestamp: str
    target: str
    sha256: str = ""

    def __post_init__(self):
        if not self.sha256:
            self.sha256 = hashlib.sha256(self.url.encode()).hexdigest()[:16]

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

# ════════════════════════════════════════════════════════════════════════════
# MOTEURS DE RECHERCHE — Multi-engine avec fallback
# ════════════════════════════════════════════════════════════════════════════

class SearchEngine:
    """Base commune pour les moteurs de recherche"""

    def __init__(self, config: DorkConfig):
        self.config = config
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        session = requests.Session()

        # Retry avec backoff
        retry = Retry(
            total=3,
            backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        # Proxy Tor si activé
        if self.config.tor and HAS_SOCKS:
            socks.set_default_proxy(socks.SOCKS5, "127.0.0.1", 9050)
            socket.socket = socks.socksocket

        return session

    def _get_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    def _delay(self):
        """Rate limiting avec jitter"""
        base = self.config.delay
        jitter = random.uniform(0, self.config.jitter) if self.config.jitter > 0 else 0
        time.sleep(base + jitter)

    def search(self, query: str) -> List[Dict]:
        raise NotImplementedError


class GoogleEngine(SearchEngine):
    """Google Custom Search (scraping HTML)"""

    name = "google"

    def search(self, query: str) -> List[Dict]:
        results = []
        for page in range(self.config.max_pages):
            start = page * 10
            url = f"https://www.google.com/search?q={quote_plus(query)}&start={start}&num=10"

            try:
                self._delay()
                resp = self.session.get(url, headers=self._get_headers(), timeout=self.config.timeout)

                if resp.status_code == 429:
                    print(f"⚠️  Google rate limit atteint. Pause de 60s...")
                    time.sleep(60)
                    continue

                if "captcha" in resp.text.lower() or "unusual traffic" in resp.text.lower():
                    print(f"⚠️  Google CAPTCHA détecté. Arrêt du moteur Google.")
                    break

                # Parsing basique des résultats
                # Note: Google change souvent sa structure HTML, ceci est un parser simplifié
                pattern = r'<a href="/url\?q=(https?://[^&]+)&[^"]*"[^>]*>(.*?)</a>'
                matches = re.findall(pattern, resp.text, re.IGNORECASE)

                for url_found, title in matches[:self.config.max_results_per_dork]:
                    if "google.com" not in url_found and "youtube.com" not in url_found:
                        results.append({
                            "url": url_found,
                            "title": re.sub(r'<[^>]+>', '', title),
                            "snippet": "",
                            "engine": self.name
                        })

            except Exception as e:
                print(f"⚠️  Google error: {e}")
                continue

        return results


class BingEngine(SearchEngine):
    """Bing Search (scraping HTML)"""

    name = "bing"

    def search(self, query: str) -> List[Dict]:
        results = []
        for page in range(self.config.max_pages):
            first = page * 10 + 1
            url = f"https://www.bing.com/search?q={quote_plus(query)}&first={first}"

            try:
                self._delay()
                resp = self.session.get(url, headers=self._get_headers(), timeout=self.config.timeout)

                if resp.status_code == 429:
                    print(f"⚠️  Bing rate limit atteint.")
                    break

                # Parsing basique
                pattern = r'<li class="b_algo"><h2><a href="([^"]+)"[^>]*>(.*?)</a></h2><p[^>]*>(.*?)</p>'
                matches = re.findall(pattern, resp.text, re.IGNORECASE | re.DOTALL)

                for url_found, title, snippet in matches[:self.config.max_results_per_dork]:
                    results.append({
                        "url": url_found,
                        "title": re.sub(r'<[^>]+>', '', title),
                        "snippet": re.sub(r'<[^>]+>', '', snippet)[:200],
                        "engine": self.name
                    })

            except Exception as e:
                print(f"⚠️  Bing error: {e}")
                continue

        return results


class DDGEngine(SearchEngine):
    """DuckDuckGo HTML (scraping)"""

    name = "duckduckgo"

    def search(self, query: str) -> List[Dict]:
        results = []
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"

        try:
            self._delay()
            resp = self.session.get(url, headers=self._get_headers(), timeout=self.config.timeout)

            if resp.status_code != 200:
                return results

            # Parsing des résultats DDG HTML
            pattern = r'<a rel="nofollow" class="result__a" href="([^"]+)"[^>]*>(.*?)</a>.*?<a class="result__snippet"[^>]*>(.*?)</a>'
            matches = re.findall(pattern, resp.text, re.IGNORECASE | re.DOTALL)

            for url_found, title, snippet in matches[:self.config.max_results_per_dork]:
                # DDG utilise des redirections, on extrait l'URL réelle
                if "uddg=" in url_found:
                    from urllib.parse import unquote, parse_qs, urlparse
                    parsed = urlparse(url_found)
                    params = parse_qs(parsed.query)
                    if "uddg" in params:
                        url_found = unquote(params["uddg"][0])

                results.append({
                    "url": url_found,
                    "title": re.sub(r'<[^>]+>', '', title),
                    "snippet": re.sub(r'<[^>]+>', '', snippet)[:200],
                    "engine": self.name
                })

        except Exception as e:
            print(f"⚠️  DuckDuckGo error: {e}")

        return results


class YandexEngine(SearchEngine):
    """Yandex Search (scraping HTML)"""

    name = "yandex"

    def search(self, query: str) -> List[Dict]:
        results = []
        url = f"https://yandex.com/search/?text={quote_plus(query)}"

        try:
            self._delay()
            resp = self.session.get(url, headers=self._get_headers(), timeout=self.config.timeout)

            if resp.status_code != 200:
                return results

            # Parsing basique Yandex
            pattern = r'<a class="Link Link_theme_normal Organic-Title__link" href="([^"]+)"[^>]*>(.*?)</a>'
            matches = re.findall(pattern, resp.text, re.IGNORECASE)

            for url_found, title in matches[:self.config.max_results_per_dork]:
                results.append({
                    "url": url_found,
                    "title": re.sub(r'<[^>]+>', '', title),
                    "snippet": "",
                    "engine": self.name
                })

        except Exception as e:
            print(f"⚠️  Yandex error: {e}")

        return results


# ════════════════════════════════════════════════════════════════════════════
# MOTEUR PRINCIPAL — Orchestrateur de dorks
# ════════════════════════════════════════════════════════════════════════════

class PasschendaeleEngine:
    """Moteur principal de violent dorking"""

    def __init__(self, config: DorkConfig):
        self.config = config
        self.results: List[DorkResult] = []
        self.seen_urls: Set[str] = set()

        # Initialisation des moteurs
        self.engines = {
            "google": GoogleEngine(config),
            "bing": BingEngine(config),
            "duckduckgo": DDGEngine(config),
            "yandex": YandexEngine(config),
        }

        # Console Rich
        if HAS_RICH:
            self.console = Console(theme=Theme({
                "info": "cyan",
                "success": "green",
                "danger": "bold red",
                "warning": "yellow",
                "mud": "bright_black",
                "wire": "magenta",
            }))
        else:
            self.console = None

    def _print(self, message: str, style: str = "info"):
        if self.console:
            self.console.print(f"[{style}]{message}[/{style}]")
        else:
            print(message)

    def _get_dorks(self) -> List[Tuple[str, str, str]]:
        """Retourne la liste des dorks à exécuter: (dork, category, severity)"""
        dorks = []

        # Dorks personnalisés
        for dork in self.config.custom_dorks:
            dorks.append((dork, "custom", "MEDIUM"))

        # Dorks de la bibliothèque
        for cat in self.config.categories:
            if cat == "all":
                for cat_data in DORK_LIBRARY.values():
                    for dork in cat_data["dorks"]:
                        dorks.append((dork, cat_data["label"], cat_data["severity"]))
            elif cat in DORK_LIBRARY:
                cat_data = DORK_LIBRARY[cat]
                for dork in cat_data["dorks"]:
                    dorks.append((dork, cat_data["label"], cat_data["severity"]))

        return dorks

    def _execute_dork(self, dork: str, category: str, severity: str, engine_name: str) -> List[DorkResult]:
        """Exécute un dork sur un moteur spécifique"""
        engine = self.engines.get(engine_name)
        if not engine:
            return []

        # Substitution de la cible
        query = dork.replace("{target}", self.config.target)

        try:
            raw_results = engine.search(query)
        except Exception as e:
            self._print(f"⚠️  Erreur moteur {engine_name}: {e}", "warning")
            return []

        results = []
        for r in raw_results:
            url = r["url"]

            # Dé-duplication
            if url in self.seen_urls:
                continue
            self.seen_urls.add(url)

            # Filtrage des URLs hors cible (sauf pour subdomains)
            if category != "Sous-domaines":
                parsed = urlparse(url)
                if self.config.target not in parsed.netloc:
                    continue

            results.append(DorkResult(
                dork=dork,
                category=category,
                severity=severity,
                url=url,
                title=r.get("title", ""),
                snippet=r.get("snippet", ""),
                engine=engine_name,
                timestamp=datetime.now(timezone.utc).isoformat(),
                target=self.config.target,
            ))

        return results

    def run(self):
        """Exécute le dorking complet"""
        self._print(Panel.fit(
            f"[wire]{ASCII_ART}[/]\n"
            f"[mud]{random.choice(MOTTO)}[/]",
            border_style="magenta"
        ) if HAS_RICH else ASCII_ART)

        dorks = self._get_dorks()
        if not dorks:
            self._print("❌ Aucun dork à exécuter.", "danger")
            return

        self._print(f"\n🎯 Cible: [bold]{self.config.target}[/]")
        self._print(f"📚 Dorks: [bold]{len(dorks)}[/]")
        self._print(f"🔍 Moteurs: [bold]{', '.join(self.config.engines)}[/]")
        self._print(f"🧅 Tor: [bold]{'ACTIVÉ' if self.config.tor else 'DÉSACTIVÉ'}[/]\n")

        # Progression
        if HAS_RICH:
            progress = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                console=self.console
            )
            task = progress.add_task("[cyan]Dorking en cours...", total=len(dorks) * len(self.config.engines))
            progress.start()

        total_dorks = len(dorks)
        for i, (dork, category, severity) in enumerate(dorks, 1):
            self._print(f"\n[{i}/{total_dorks}] {category} ({severity})", "info")

            for engine_name in self.config.engines:
                results = self._execute_dork(dork, category, severity, engine_name)
                self.results.extend(results)

                if HAS_RICH:
                    progress.update(task, advance=1)

                if results:
                    self._print(f"  ✓ {engine_name}: {len(results)} résultats", "success")

        if HAS_RICH:
            progress.stop()

        self._print(f"\n✅ Total: [bold]{len(self.results)}[/] résultats uniques trouvés.", "success")

    def export(self):
        """Export les résultats"""
        if not self.config.output:
            return

        output_path = Path(self.config.output)

        if self.config.output_format == "json":
            data = {
                "target": self.config.target,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "total_results": len(self.results),
                "results": [asdict(r) for r in self.results]
            }
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        elif self.config.output_format == "csv":
            with open(output_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "dork", "category", "severity", "url", "title",
                    "snippet", "engine", "timestamp", "target", "sha256"
                ])
                writer.writeheader()
                for r in self.results:
                    writer.writerow(asdict(r))

        elif self.config.output_format == "html":
            html = self._generate_html_report()
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html)

        self._print(f"💾 Exporté vers: [bold]{output_path}[/]", "success")

    def _generate_html_report(self) -> str:
        """Génère un rapport HTML"""
        severity_colors = {
            "CRITICAL": "#ff0000",
            "HIGH": "#ff6600",
            "MEDIUM": "#ffaa00",
            "LOW": "#00aa00",
        }

        rows = ""
        for r in self.results:
            color = severity_colors.get(r.severity, "#666666")
            rows += f"""
            <tr>
                <td><span style="color:{color};font-weight:bold">{r.severity}</span></td>
                <td>{r.category}</td>
                <td><a href="{r.url}" target="_blank">{r.url}</a></td>
                <td>{r.title}</td>
                <td>{r.engine}</td>
            </tr>
            """

        return f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Passchendaele Report — {self.config.target}</title>
    <style>
        body {{ font-family: 'Courier New', monospace; background: #0a0604; color: #ffb347; padding: 20px; }}
        h1 {{ color: #ff3d9a; text-shadow: 0 0 10px rgba(255,61,154,0.5); }}
        table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
        th, td {{ border: 1px solid #3a2410; padding: 8px; text-align: left; }}
        th {{ background: #1a0f07; color: #ffd27f; }}
        tr:nth-child(even) {{ background: #120a05; }}
        a {{ color: #00e5ff; }}
        .meta {{ color: #a87020; margin-bottom: 20px; }}
    </style>
</head>
<body>
    <h1>🪖 PASSCHENDAELE — Violent Dorking Report</h1>
    <div class="meta">
        <strong>Cible:</strong> {self.config.target}<br>
        <strong>Date:</strong> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}<br>
        <strong>Résultats:</strong> {len(self.results)}
    </div>
    <table>
        <thead>
            <tr>
                <th>Sévérité</th>
                <th>Catégorie</th>
                <th>URL</th>
                <th>Titre</th>
                <th>Moteur</th>
            </tr>
        </thead>
        <tbody>
            {rows}
        </tbody>
    </table>
    <p style="margin-top: 40px; color: #5a3d10; font-style: italic;">
        "In the mud of Flanders, secrets lie buried. We dig them up."
    </p>
</body>
</html>"""

    def print_summary(self):
        """Affiche un résumé des résultats"""
        if not self.results:
            self._print("❌ Aucun résultat.", "danger")
            return

        if HAS_RICH:
            table = Table(title="📊 Résumé par Catégorie", show_lines=True)
            table.add_column("Catégorie", style="cyan")
            table.add_column("Sévérité", style="bold")
            table.add_column("Count", justify="right", style="green")

            by_cat = defaultdict(list)
            for r in self.results:
                by_cat[(r.category, r.severity)].append(r)

            for (cat, sev), results in sorted(by_cat.items(), key=lambda x: len(x[1]), reverse=True):
                sev_style = "red" if sev == "CRITICAL" else "yellow" if sev == "HIGH" else "green"
                table.add_row(cat, f"[{sev_style}]{sev}[/{sev_style}]", str(len(results)))

            self.console.print(table)

            # Top 10 URLs
            self.console.print("\n[bold]🏆 Top 10 URLs les plus intéressantes:[/bold]")
            for i, r in enumerate(self.results[:10], 1):
                self.console.print(f"  {i}. [{r.severity}] {r.url}")

# ════════════════════════════════════════════════════════════════════════════
# POINT D'ENTRÉE CLI
# ════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="PASSCHENDAELE v5b — Violent Dorking Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  # Dorking complet sur example.com
  python Passchendaele5b.py --target example.com --category all

  # Dorking ciblé (fichiers sensibles uniquement)
  python Passchendaele5b.py --target example.com --category sensitive_files,backups

  # Dork personnalisé
  python Passchendaele5b.py --target example.com --dork "site:example.com ext:env"

  # Mode stealth avec Tor
  python Passchendaele5b.py --target example.com --stealth --tor --output results.json

  # Export HTML
  python Passchendaele5b.py --target example.com --output report.html --format html

Catégories disponibles:
  sensitive_files, backups, admin_panels, auth_exposure, vulnerabilities,
  directory_listing, cloud_storage, email_exposure, subdomains, code_exposure, all
        """
    )

    parser.add_argument("--target", "-t", required=True, help="Cible (domaine ou URL)")
    parser.add_argument("--category", "-c", default="all", help="Catégories (séparées par virgules) ou 'all'")
    parser.add_argument("--engine", "-e", default="google,bing,duckduckgo", help="Moteurs (séparés par virgules)")
    parser.add_argument("--dork", "-d", action="append", default=[], help="Dork personnalisé (répétable)")
    parser.add_argument("--max-results", type=int, default=10, help="Résultats max par dork")
    parser.add_argument("--max-pages", type=int, default=3, help="Pages max par moteur")
    parser.add_argument("--delay", type=float, default=2.0, help="Délai entre requêtes (secondes)")
    parser.add_argument("--jitter", type=float, default=1.0, help="Jitter aléatoire (secondes)")
    parser.add_argument("--tor", action="store_true", help="Activer Tor (SOCKS5 9050)")
    parser.add_argument("--stealth", action="store_true", help="Mode stealth (delay+jitter élevés)")
    parser.add_argument("--output", "-o", help="Fichier de sortie")
    parser.add_argument("--format", "-f", choices=["json", "csv", "html"], default="json", help="Format d'export")

    args = parser.parse_args()

    # Mode stealth
    if args.stealth:
        args.delay = max(args.delay, 5.0)
        args.jitter = max(args.jitter, 3.0)

    # Configuration
    config = DorkConfig(
        target=args.target,
        categories=[c.strip() for c in args.category.split(",")],
        engines=[e.strip() for e in args.engine.split(",")],
        max_results_per_dork=args.max_results,
        max_pages=args.max_pages,
        delay=args.delay,
        jitter=args.jitter,
        tor=args.tor,
        stealth=args.stealth,
        output=args.output,
        output_format=args.format,
        custom_dorks=args.dork,
    )

    # Vérification Tor
    if config.tor and not HAS_SOCKS:
        print("❌ Tor activé mais PySocks non installé. pip install PySocks")
        exit(1)

    # Exécution
    engine = PasschendaeleEngine(config)
    engine.run()
    engine.print_summary()
    engine.export()

if __name__ == "__main__":
    main()