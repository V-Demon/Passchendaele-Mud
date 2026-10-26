#!/usr/bin/env bash
# ════════════════════════════════════════════════════════════════════════════
#  passchendaele_mega.sh — Orchestrateur pour Passchendaele-mud.py
#  « Through mud and wire, we find what they forgot to hide. »
# ════════════════════════════════════════════════════════════════════════════
set -euo pipefail

# ── Couleurs ──────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; MAGENTA='\033[0;35m'; CYAN='\033[0;36m'
BOLD='\033[1m'; NC='\033[0m'; DIM='\033[2m'

# ── Configuration ─────────────────────────────────────────────────────────
SCRIPT="${SCRIPT:-./Passchendaele-mud.py}"
TARGET="${1:-}"
MODE="${2:-full}"  # full, stealth, quick, custom
OUTPUT_DIR="${OUTPUT_DIR:-./passchendaele_results}"

# ── Fonctions ─────────────────────────────────────────────────────────────
log_info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

separator() {
    echo -e "${DIM}────────────────────────────────────────────────────────────────────────────${NC}"
}

header() {
    separator
    echo -e "${BOLD}${CYAN}$*${NC}"
    separator
}

usage() {
    cat <<EOF
${BOLD}${CYAN}passchendaele_mega.sh${NC} — Orchestrateur tactique pour Violent Dorking

${BOLD}USAGE :${NC}
  ./passchendaele_mega.sh <target> [mode]

${BOLD}MODES :${NC}
  ${GREEN}full${NC}      Dorking complet (toutes catégories, tous moteurs)
  ${GREEN}stealth${NC}   Mode furtif (Tor, delays élevés, rotation UA)
  ${GREEN}quick${NC}     Scan rapide (catégories critiques uniquement)
  ${GREEN}custom${NC}    Mode personnalisé (éditer le script)

${BOLD}EXEMPLES :${NC}
  ./passchendaele_mega.sh example.com full
  ./passchendaele_mega.sh example.com stealth
  ./passchendaele_mega.sh example.com quick

${BOLD}VARIABLES D'ENVIRONNEMENT :${NC}
  SCRIPT        Chemin vers Passchendaele-mud.py (défaut: ./Passchendaele-mud.py)
  OUTPUT_DIR    Dossier de sortie (défaut: ./passchendaele_results)

EOF
}

# ── Validation ────────────────────────────────────────────────────────────
if [[ -z "$TARGET" ]]; then
    usage
    exit 1
fi

if [[ ! -f "$SCRIPT" ]]; then
    log_error "Script introuvable: $SCRIPT"
    exit 1
fi

# ── Préparation ───────────────────────────────────────────────────────────
mkdir -p "$OUTPUT_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_BASE="$OUTPUT_DIR/${TARGET}_${MODE}_${TIMESTAMP}"

header "🪖 PASSCHENDAELE — Violent Dorking Engine"
log_info "Cible: $TARGET"
log_info "Mode: $MODE"
log_info "Output: $OUTPUT_BASE"
separator

# ── Exécution selon le mode ───────────────────────────────────────────────
case "$MODE" in
    full)
        log_info "Lancement du dorking COMPLET..."
        python3 "$SCRIPT" \
            --target "$TARGET" \
            --category all \
            --engine google,bing,duckduckgo \
            --max-results 20 \
            --max-pages 5 \
            --delay 2.0 \
            --jitter 1.0 \
            --output "${OUTPUT_BASE}.json" \
            --format json
        ;;

    stealth)
        log_info "Lancement du dorking STEALTH (Tor + delays élevés)..."
        log_warn "Assurez-vous que Tor est actif: sudo systemctl start tor"
        python3 "$SCRIPT" \
            --target "$TARGET" \
            --category all \
            --engine duckduckgo,bing \
            --max-results 10 \
            --max-pages 3 \
            --delay 5.0 \
            --jitter 3.0 \
            --tor \
            --stealth \
            --output "${OUTPUT_BASE}.json" \
            --format json
        ;;

    quick)
        log_info "Lancement du dorking RAPIDE (catégories critiques)..."
        python3 "$SCRIPT" \
            --target "$TARGET" \
            --category sensitive_files,auth_exposure,vulnerabilities \
            --engine duckduckgo \
            --max-results 10 \
            --max-pages 2 \
            --delay 1.0 \
            --output "${OUTPUT_BASE}.json" \
            --format json
        ;;

    custom)
        log_info "Mode CUSTOM — éditez le script pour personnaliser"
        # Exemple de personnalisation
        python3 "$SCRIPT" \
            --target "$TARGET" \
            --category sensitive_files,backups \
            --dork "site:$TARGET ext:env" \
            --dork "site:$TARGET \"password\" ext:txt" \
            --engine google \
            --max-results 15 \
            --output "${OUTPUT_BASE}.json" \
            --format json
        ;;

    *)
        log_error "Mode inconnu: $MODE"
        usage
        exit 1
        ;;
esac

# ── Génération du rapport HTML ────────────────────────────────────────────
log_info "Génération du rapport HTML..."
python3 "$SCRIPT" \
    --target "$TARGET" \
    --category all \
    --engine duckduckgo \
    --max-results 5 \
    --output "${OUTPUT_BASE}.html" \
    --format html

# ── Résumé ────────────────────────────────────────────────────────────────
separator
log_ok "Dorking terminé !"
log_info "Résultats JSON: ${OUTPUT_BASE}.json"
log_info "Rapport HTML: ${OUTPUT_BASE}.html"
separator

# ── Statistiques ──────────────────────────────────────────────────────────
if [[ -f "${OUTPUT_BASE}.json" ]]; then
    TOTAL=$(jq '.total_results' "${OUTPUT_BASE}.json" 2>/dev/null || echo "0")
    log_info "Total résultats: $TOTAL"

    if [[ "$TOTAL" -gt 0 ]]; then
        log_warn "⚠️  Des résultats ont été trouvés. Vérifiez manuellement avant toute action."
    fi
fi

separator
echo -e "${DIM}« In the mud of Flanders, secrets lie buried. We dig them up. »${NC}"
separator
