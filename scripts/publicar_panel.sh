#!/usr/bin/env bash
# Publica el panel web (web/index.html + web/data.json) en el repositorio PÚBLICO del panel
# (GitHub Pages). Solo copia la página y las cifras: nada de código, configuración ni claves.
# Necesita el secreto PANEL_TOKEN (token con permiso de escritura SOLO en ese repositorio).
set -euo pipefail
if [ -z "${PANEL_TOKEN:-}" ]; then
  echo "Sin PANEL_TOKEN: el panel web no se publica (falta configurar el secreto)."
  exit 0
fi
REPO="${PANEL_REPO:-Alejandroacpt/panel-trading}"
python scripts/exportar_panel.py
tmp=$(mktemp -d)
git clone --quiet --depth 1 "https://x-access-token:${PANEL_TOKEN}@github.com/${REPO}.git" "$tmp" 2>/dev/null \
  || { echo "No se pudo clonar ${REPO}: revisa que exista y que el token tenga acceso."; exit 0; }
cp web/index.html web/data.json "$tmp"/
printf 'User-agent: *\nDisallow: /\n' > "$tmp/robots.txt"
touch "$tmp/.nojekyll"
cd "$tmp"
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git checkout -q -B main
git add -A
if git diff --cached --quiet; then echo "Panel sin cambios"; exit 0; fi
git commit -q -m "Panel $(date -u +'%Y-%m-%d %H:%M')"
for i in 1 2 3; do git push -q origin main && break; sleep 5; git pull -q --rebase origin main || true; done
echo "Panel publicado en https://$(echo "$REPO" | cut -d/ -f1 | tr 'A-Z' 'a-z').github.io/$(echo "$REPO" | cut -d/ -f2)/"
