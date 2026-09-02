#!/usr/bin/env bash
# Telecharge la voix Piper francaise et un modele LLM quantifie.
set -euo pipefail

RACINE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RACINE"
mkdir -p models/piper models/llm

# --- Voix (~60 Mo) --------------------------------------------------------
VOIX_BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/siwis/medium"
for f in fr_FR-siwis-medium.onnx fr_FR-siwis-medium.onnx.json; do
    if [ ! -f "models/piper/$f" ]; then
        echo "==> $f"
        curl -fL --progress-bar -o "models/piper/$f" "$VOIX_BASE/$f"
    fi
done

# --- Modele LLM -----------------------------------------------------------
# Choisissez selon la carte : voir docs/architecture.md section 4.
#   MODELE=llama3.2-3b   ~2,0 Go, ~6 tok/s sur Pi 5  (defaut, bon compromis)
#   MODELE=gemma3-4b     ~2,6 Go, ~4 tok/s sur Pi 5  (meilleur francais)
#   MODELE=qwen3-1.7b    ~1,1 Go, ~10 tok/s sur Pi 5 (le plus rapide utilisable)
MODELE="${MODELE:-llama3.2-3b}"

case "$MODELE" in
  llama3.2-3b)
    DEPOT="bartowski/Llama-3.2-3B-Instruct-GGUF"
    FICHIER="Llama-3.2-3B-Instruct-Q4_K_M.gguf" ;;
  gemma3-4b)
    DEPOT="bartowski/google_gemma-3-4b-it-GGUF"
    FICHIER="google_gemma-3-4b-it-Q4_K_M.gguf" ;;
  qwen3-1.7b)
    DEPOT="Qwen/Qwen3-1.7B-GGUF"
    FICHIER="Qwen3-1.7B-Q4_K_M.gguf" ;;
  *) echo "MODELE inconnu: $MODELE"; exit 1 ;;
esac

if [ ! -f "models/llm/$FICHIER" ]; then
    echo "==> $FICHIER (plusieurs Go, patience)"
    curl -fL --progress-bar -o "models/llm/$FICHIER" \
        "https://huggingface.co/$DEPOT/resolve/main/$FICHIER"
fi

echo
echo "Modeles prets dans models/. Verifiez que systemd/llama-server.service"
echo "pointe bien sur models/llm/$FICHIER, puis :"
echo "  sudo cp systemd/*.service /etc/systemd/system/"
echo "  sudo systemctl enable --now llama-server kidobot"
