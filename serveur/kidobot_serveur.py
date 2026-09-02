#!/usr/bin/env python3
"""Serveur Kidobot : transcription et synthese vocale sur le PC de la maison.

A lancer sur la machine du placard, a cote de `llama-server`. La boite devient
alors un client leger : elle n'a plus qu'a capter le son, l'envoyer ici, et
jouer ce qui revient. C'est ce qui permet de descendre jusqu'au Pi Zero 2 W.

    python serveur/kidobot_serveur.py \
        --modele-whisper large-v3 --calcul int8 \
        --voix models/piper/fr_FR-siwis-medium.onnx

Deux points de conception :

- Aucune dependance web. `http.server` de la bibliotheque standard suffit
  largement pour deux requetes par question sur un reseau local, et cela evite
  d'installer un framework sur la machine familiale.
- Requete/reponse, pas de streaming. La boite envoie un WAV complet apres le
  relachement du bouton. C'est plus simple, et surtout bien plus robuste a un
  wifi 2,4 GHz encombre qu'un flux continu.
"""

from __future__ import annotations

import argparse
import hmac
import io
import json
import logging
import subprocess
import sys
import threading
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

log = logging.getLogger("kidobot-serveur")

TAILLE_MAX = 10 * 1024 * 1024  # ~5 min d'audio 16 kHz : large, mais borne


class Moteurs:
    """Charge whisper une fois pour toutes et serialise les acces au GPU/CPU."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self._verrou = threading.Lock()
        log.info("chargement de whisper %s (%s)...", args.modele_whisper, args.calcul)
        from faster_whisper import WhisperModel

        self.whisper = WhisperModel(
            args.modele_whisper, device=args.peripherique, compute_type=args.calcul
        )
        log.info("whisper pret")

    def transcrire(self, wav: bytes, langue: str) -> str:
        with self._verrou:
            segments, _ = self.whisper.transcribe(
                io.BytesIO(wav),
                language=langue,
                beam_size=self.args.beam,
                vad_filter=True,
                condition_on_previous_text=False,
                initial_prompt="Une question posee par un enfant.",
            )
            return " ".join(s.text.strip() for s in segments).strip()

    def synthetiser(self, phrase: str, vitesse: float) -> tuple[bytes, int]:
        cmd = [
            self.args.binaire_piper,
            "--model", self.args.voix,
            "--output_raw",
            "--length_scale", f"{1.0 / max(vitesse, 0.1):.2f}",
        ]
        res = subprocess.run(
            cmd, input=phrase.encode("utf-8"), capture_output=True, check=False
        )
        if res.returncode != 0:
            log.error("piper: %s", res.stderr.decode("utf-8", "replace")[-300:])
            return b"", self.args.frequence_voix
        return res.stdout, self.args.frequence_voix


class Gestionnaire(BaseHTTPRequestHandler):
    moteurs: Moteurs
    jeton: str = ""

    protocol_version = "HTTP/1.1"

    # -- utilitaires -------------------------------------------------------
    def _autorise(self) -> bool:
        if not self.jeton:
            return True
        fourni = self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        # Comparaison a temps constant : le jeton est court et le reseau local
        # n'est pas un sanctuaire (objets connectes, invites, enfants curieux).
        return hmac.compare_digest(fourni, self.jeton)

    def _repondre(self, code: int, corps: bytes, type_mime: str, extra: dict | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", type_mime)
        self.send_header("Content-Length", str(len(corps)))
        for cle, valeur in (extra or {}).items():
            self.send_header(cle, str(valeur))
        self.end_headers()
        self.wfile.write(corps)

    def _erreur(self, code: int, message: str) -> None:
        self._repondre(code, json.dumps({"erreur": message}).encode(), "application/json")

    def _lire_corps(self) -> bytes | None:
        taille = int(self.headers.get("Content-Length", 0))
        if taille <= 0 or taille > TAILLE_MAX:
            self._erreur(413, "corps absent ou trop volumineux")
            return None
        return self.rfile.read(taille)

    # -- routes ------------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802 - impose par BaseHTTPRequestHandler
        if self.path.rstrip("/") in ("", "/sante"):
            self._repondre(200, b'{"etat":"ok"}', "application/json")
        else:
            self._erreur(404, "inconnu")

    def do_POST(self) -> None:  # noqa: N802
        if not self._autorise():
            self._erreur(401, "jeton invalide")
            return
        route = self.path.rstrip("/")
        if route == "/stt":
            self._route_stt()
        elif route == "/tts":
            self._route_tts()
        else:
            self._erreur(404, "inconnu")

    def _route_stt(self) -> None:
        corps = self._lire_corps()
        if corps is None:
            return
        try:
            _valider_wav(corps)
        except Exception as exc:
            self._erreur(400, f"WAV invalide: {exc}")
            return
        langue = self.headers.get("X-Langue", "fr")[:5]
        texte = self.moteurs.transcrire(corps, langue)
        log.info("stt (%.0f ko) -> %r", len(corps) / 1024, texte)
        self._repondre(200, json.dumps({"texte": texte}).encode("utf-8"), "application/json")

    def _route_tts(self) -> None:
        corps = self._lire_corps()
        if corps is None:
            return
        try:
            charge = json.loads(corps)
            phrase = str(charge["phrase"])[:1000]
            vitesse = float(charge.get("vitesse", 1.0))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            self._erreur(400, f"requete invalide: {exc}")
            return
        pcm, frequence = self.moteurs.synthetiser(phrase, vitesse)
        self._repondre(200, pcm, "audio/L16", {"X-Frequence": frequence})

    def log_message(self, fmt: str, *args) -> None:
        log.debug(fmt, *args)


def _valider_wav(donnees: bytes) -> None:
    """Refuse tout ce qui n'est pas un WAV mono 16 bits lisible."""
    with wave.open(io.BytesIO(donnees), "rb") as f:
        if f.getnchannels() != 1 or f.getsampwidth() != 2:
            raise ValueError("attendu : mono 16 bits")


def analyser(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Serveur STT/TTS de Kidobot.")
    p.add_argument("--hote", default="0.0.0.0", help="0.0.0.0 pour ecouter sur le LAN")
    p.add_argument("--port", type=int, default=8100)
    p.add_argument("--modele-whisper", default="large-v3",
                   help="tiny|base|small|medium|large-v3 — prenez large-v3, la machine peut")
    p.add_argument("--peripherique", default="auto", help="auto|cpu|cuda")
    p.add_argument("--calcul", default="int8", help="int8|float16 (float16 si GPU)")
    p.add_argument("--beam", type=int, default=5, help="1 = plus rapide, 5 = plus juste")
    p.add_argument("--binaire-piper", default="piper")
    p.add_argument("--voix", required=True, help="chemin du .onnx piper")
    p.add_argument("--frequence-voix", type=int, default=22050)
    p.add_argument("--jeton", default="", help="secret partage avec la boite (recommande)")
    p.add_argument("-v", "--verbeux", action="store_true")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = analyser(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbeux else logging.INFO,
        format="%(asctime)s %(levelname).1s %(message)s",
        datefmt="%H:%M:%S",
    )
    Gestionnaire.moteurs = Moteurs(args)
    Gestionnaire.jeton = args.jeton
    if not args.jeton:
        log.warning("aucun jeton : n'importe quelle machine du reseau peut "
                    "utiliser ce serveur. Utilisez --jeton en production.")

    serveur = ThreadingHTTPServer((args.hote, args.port), Gestionnaire)
    log.info("a l'ecoute sur http://%s:%d", args.hote, args.port)
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        log.info("arret")
    finally:
        serveur.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
