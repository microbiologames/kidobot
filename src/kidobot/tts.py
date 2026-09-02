"""Synthese vocale locale, phrase par phrase.

Piper est le bon choix ici : ~50 Mo par voix, environ 0,3x le temps reel sur
Raspberry Pi 5, licence permissive, et des voix francaises correctes. On le
pilote en sous-processus et on lui envoie une phrase a la fois, ce qui permet
de commencer a parler avant que le modele ait fini d'ecrire.
"""

from __future__ import annotations

import logging
import subprocess

from .config import Tts as ConfTts

log = logging.getLogger(__name__)


class TtsBase:
    frequence = 22050

    def synthetiser(self, phrase: str) -> bytes:
        """Rend du PCM 16 bits mono a `self.frequence`."""
        raise NotImplementedError


class Piper(TtsBase):
    def __init__(self, conf: ConfTts) -> None:
        self.conf = conf
        self.frequence = 22050  # frequence des voix piper "medium"

    def synthetiser(self, phrase: str) -> bytes:
        cmd = [
            self.conf.binaire,
            "--model", self.conf.voix,
            "--output_raw",
            "--length_scale", f"{1.0 / max(self.conf.vitesse, 0.1):.2f}",
        ]
        try:
            res = subprocess.run(
                cmd,
                input=phrase.encode("utf-8"),
                capture_output=True,
                timeout=30,
                check=False,
            )
        except FileNotFoundError as exc:
            log.error("binaire piper introuvable: %s", exc)
            return b""
        if res.returncode != 0:
            log.error("piper a echoue: %s", res.stderr.decode("utf-8", "replace")[-300:])
            return b""
        return res.stdout


class Espeak(TtsBase):
    """Repli d'urgence : moche mais present sur toutes les distributions."""

    def __init__(self, conf: ConfTts) -> None:
        self.conf = conf
        self.frequence = 22050

    def synthetiser(self, phrase: str) -> bytes:
        cmd = ["espeak-ng", "-v", "fr", "-s", "150", "--stdout"]
        try:
            res = subprocess.run(
                cmd, input=phrase.encode("utf-8"), capture_output=True, check=False
            )
        except FileNotFoundError:
            return b""
        # On retire l'entete WAV (44 octets) pour rendre du PCM brut.
        return res.stdout[44:] if len(res.stdout) > 44 else b""


class TtsFactice(TtsBase):
    def synthetiser(self, phrase: str) -> bytes:
        log.info("[voix factice] %s", phrase)
        return b""


def fabriquer(conf: ConfTts) -> TtsBase:
    if conf.backend == "piper":
        return Piper(conf)
    if conf.backend == "espeak":
        return Espeak(conf)
    return TtsFactice()
