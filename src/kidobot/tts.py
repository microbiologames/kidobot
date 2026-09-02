"""Synthese vocale locale, phrase par phrase.

Piper est le bon choix ici : ~50 Mo par voix, environ 0,3x le temps reel sur
Raspberry Pi 5, licence permissive, et des voix francaises correctes. On le
pilote en sous-processus et on lui envoie une phrase a la fois, ce qui permet
de commencer a parler avant que le modele ait fini d'ecrire.
"""

from __future__ import annotations

import logging
import subprocess

import httpx

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


class TtsDistant(TtsBase):
    """La synthese tourne sur le PC de la maison, une requete par phrase.

    Le decoupage en phrases du pipeline joue ici en notre faveur : chaque
    phrase est un aller-retour HTTP de quelques dizaines de millisecondes sur
    un reseau local, pendant que la precedente est encore en train d'etre
    prononcee. Le surcout reseau est donc entierement masque.
    """

    def __init__(self, conf: ConfTts) -> None:
        self.conf = conf
        self.frequence = 22050

    def synthetiser(self, phrase: str) -> bytes:
        entetes = {}
        if self.conf.jeton:
            entetes["Authorization"] = f"Bearer {self.conf.jeton}"
        r = httpx.post(
            f"{self.conf.url}/tts",
            json={"phrase": phrase, "vitesse": self.conf.vitesse},
            headers=entetes,
            timeout=self.conf.timeout_s,
        )
        r.raise_for_status()
        self.frequence = int(r.headers.get("X-Frequence", self.frequence))
        return r.content


class TtsAvecSecours(TtsBase):
    """Enveloppe une voix principale et une voix de repli locale.

    Une boite muette passe pour cassee ; une boite qui parle mal passe pour
    enrhumee. Quand le serveur de la maison est eteint, espeak-ng prend le
    relais : il est laid, mais il est local, minuscule et instantane.
    """

    def __init__(self, principale: TtsBase, secours: TtsBase) -> None:
        self.principale = principale
        self.secours = secours
        self.frequence = principale.frequence
        self.en_secours = False

    def synthetiser(self, phrase: str) -> bytes:
        if not self.en_secours:
            try:
                pcm = self.principale.synthetiser(phrase)
                if pcm:
                    self.frequence = self.principale.frequence
                    return pcm
                log.warning("voix principale muette, passage a la voix de secours")
            except Exception as exc:
                log.warning("voix principale indisponible (%s), voix de secours", exc)
            # On ne retente pas la principale pour les phrases suivantes de la
            # meme reponse : changer de voix au milieu d'une phrase est pire
            # que de terminer avec la voix moche.
            self.en_secours = True
        self.frequence = self.secours.frequence
        return self.secours.synthetiser(phrase)

    def reinitialiser(self) -> None:
        """A appeler entre deux questions pour retenter la voix principale."""
        self.en_secours = False


class TtsFactice(TtsBase):
    def synthetiser(self, phrase: str) -> bytes:
        log.info("[voix factice] %s", phrase)
        return b""


def _voix_simple(nom: str, conf: ConfTts) -> TtsBase:
    if nom == "piper":
        return Piper(conf)
    if nom == "espeak":
        return Espeak(conf)
    if nom == "distant":
        return TtsDistant(conf)
    return TtsFactice()


def fabriquer(conf: ConfTts) -> TtsBase:
    principale = _voix_simple(conf.backend, conf)
    # Le repli n'a de sens que si la voix principale peut disparaitre, donc
    # uniquement quand elle depend du reseau.
    if conf.backend == "distant" and conf.secours and conf.secours != conf.backend:
        return TtsAvecSecours(principale, _voix_simple(conf.secours, conf))
    return principale
