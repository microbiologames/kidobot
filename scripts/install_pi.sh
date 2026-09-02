#!/usr/bin/env bash
# Installe les dependances systeme de Kidobot sur Raspberry Pi OS (Bookworm, 64 bits).
# Idempotent : relancable sans dommage.
set -euo pipefail

RACINE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RACINE"

echo "==> Paquets systeme"
sudo apt-get update
sudo apt-get install -y \
    python3-venv python3-dev build-essential cmake git \
    portaudio19-dev libsndfile1 \
    alsa-utils espeak-ng \
    libgpiod2 python3-libgpiod

echo "==> Environnement Python"
[ -d .venv ] || python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip wheel
pip install -e ".[stt,cloud,pi]"

echo "==> Piper (synthese vocale)"
if ! command -v piper >/dev/null 2>&1; then
    ARCH="$(uname -m)"
    case "$ARCH" in
        aarch64) CIBLE="linux_aarch64" ;;
        x86_64)  CIBLE="linux_x86_64" ;;
        *) echo "architecture $ARCH non geree, installez piper a la main"; exit 1 ;;
    esac
    mkdir -p /opt/piper && cd /tmp
    curl -fsSL -o piper.tar.gz \
        "https://github.com/rhasspy/piper/releases/latest/download/piper_${CIBLE}.tar.gz"
    sudo tar -xzf piper.tar.gz -C /opt
    sudo ln -sf /opt/piper/piper /usr/local/bin/piper
    cd "$RACINE"
fi
piper --version || true

echo "==> llama.cpp"
if [ ! -x /opt/llama.cpp/build/bin/llama-server ]; then
    sudo mkdir -p /opt/llama.cpp
    sudo chown "$USER" /opt/llama.cpp
    git clone --depth 1 https://github.com/ggml-org/llama.cpp /opt/llama.cpp || true
    cmake -S /opt/llama.cpp -B /opt/llama.cpp/build \
        -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON
    cmake --build /opt/llama.cpp/build --config Release -j"$(nproc)" --target llama-server
fi

echo "==> Configuration"
[ -f config/kidobot.toml ] || cp config/kidobot.example.toml config/kidobot.toml

cat <<'FIN'

Termine. Ensuite :

  ./scripts/fetch_models.sh          telecharge la voix et le modele LLM
  source .venv/bin/activate
  python -m kidobot --diagnostic     verifie chaque brique

Si vous utilisez le ReSpeaker 2-Mics HAT, installez d'abord son pilote
(https://github.com/HinTak/seeed-voicecard) et redemarrez, puis relevez le nom
de la carte avec `arecord -l` pour remplir audio.peripherique_entree.
FIN
