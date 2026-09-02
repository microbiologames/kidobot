"""Capture micro (avec detection de fin de parole) et restitution audio.

Le module s'appuie sur `sounddevice` mais reste importable sans lui : sur un
poste de dev sans carte son, `MicroFactice` / `HautParleurFactice` prennent le
relais et permettent de derouler tout le pipeline.
"""

from __future__ import annotations

import logging
import math
import queue
import struct
import threading
import time
from collections.abc import Iterator

import numpy as np

from .config import Audio as ConfAudio

log = logging.getLogger(__name__)

TRAME_MS = 20  # webrtcvad n'accepte que 10, 20 ou 30 ms


def _sounddevice():
    import sounddevice as sd  # import tardif : absent sur les machines sans audio

    return sd


# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------
class Micro:
    """Capture 16 bits mono, decoupee en trames de 20 ms."""

    def __init__(self, conf: ConfAudio) -> None:
        self.conf = conf
        self.taille_trame = int(conf.frequence * TRAME_MS / 1000)

    def _flux(self) -> Iterator[bytes]:
        sd = _sounddevice()
        fifo: queue.Queue[bytes] = queue.Queue()

        def rappel(indata, frames, temps, statut):
            if statut:
                log.debug("statut capture: %s", statut)
            fifo.put(bytes(indata))

        flux = sd.RawInputStream(
            samplerate=self.conf.frequence,
            blocksize=self.taille_trame,
            device=self.conf.peripherique_entree or None,
            dtype="int16",
            channels=1,
            callback=rappel,
        )
        with flux:
            while True:
                yield fifo.get()

    def enregistrer_pendant_appui(self, bouton_enfonce) -> np.ndarray:
        """Mode 'maintien' : on enregistre tant que `bouton_enfonce()` est vrai."""
        trames: list[bytes] = []
        limite = time.monotonic() + self.conf.duree_max_question_s
        for trame in self._flux():
            trames.append(trame)
            if not bouton_enfonce() or time.monotonic() > limite:
                break
        return _vers_float(b"".join(trames))

    def enregistrer_jusqu_au_silence(self) -> np.ndarray:
        """Mode 'impulsion' : on s'arrete apres N ms de silence (VAD WebRTC)."""
        import webrtcvad

        vad = webrtcvad.Vad(self.conf.vad_agressivite)
        trames: list[bytes] = []
        silence_ms = 0
        parole_vue = False
        limite = time.monotonic() + self.conf.duree_max_question_s
        seuil_silence = self.conf.silence_fin_ms

        for trame in self._flux():
            trames.append(trame)
            parle = vad.is_speech(trame, self.conf.frequence)
            if parle:
                parole_vue = True
                silence_ms = 0
            else:
                silence_ms += TRAME_MS
            # On laisse 2 s a l'enfant pour se lancer avant d'exiger de la parole.
            attente_initiale = not parole_vue and silence_ms < 2000
            if not attente_initiale and silence_ms >= seuil_silence:
                break
            if time.monotonic() > limite:
                break
        return _vers_float(b"".join(trames))


class MicroFactice(Micro):
    """Renvoie 1 s de silence : utile pour les tests et le mode --texte."""

    def enregistrer_pendant_appui(self, bouton_enfonce) -> np.ndarray:
        return np.zeros(self.conf.frequence, dtype=np.float32)

    def enregistrer_jusqu_au_silence(self) -> np.ndarray:
        return np.zeros(self.conf.frequence, dtype=np.float32)


def _vers_float(pcm: bytes) -> np.ndarray:
    if not pcm:
        return np.zeros(0, dtype=np.float32)
    return np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0


# ---------------------------------------------------------------------------
# Restitution
# ---------------------------------------------------------------------------
class HautParleur:
    """Lecture PCM 16 bits. Interruptible : l'enfant peut couper la parole."""

    def __init__(self, conf: ConfAudio) -> None:
        self.conf = conf
        self._stop = threading.Event()

    def interrompre(self) -> None:
        self._stop.set()

    def jouer_pcm(self, pcm: bytes, frequence: int) -> None:
        if not pcm:
            return
        self._stop.clear()
        sd = _sounddevice()
        echantillons = np.frombuffer(pcm, dtype=np.int16)
        flux = sd.RawOutputStream(
            samplerate=frequence,
            device=self.conf.peripherique_sortie or None,
            dtype="int16",
            channels=1,
        )
        bloc = frequence // 10  # 100 ms : granularite de l'interruption
        with flux:
            for debut in range(0, len(echantillons), bloc):
                if self._stop.is_set():
                    break
                flux.write(echantillons[debut : debut + bloc].tobytes())

    def bip(self, frequence_hz: float, duree_ms: int, volume: float = 0.25) -> None:
        self.jouer_pcm(_sinus(frequence_hz, duree_ms, self.conf.frequence, volume), self.conf.frequence)


class HautParleurFactice(HautParleur):
    def jouer_pcm(self, pcm: bytes, frequence: int) -> None:
        log.info("[audio factice] %d ms", int(1000 * len(pcm) / 2 / max(frequence, 1)))

    def bip(self, frequence_hz: float, duree_ms: int, volume: float = 0.25) -> None:
        log.info("[bip factice] %.0f Hz", frequence_hz)


def _sinus(freq: float, duree_ms: int, frequence: int, volume: float) -> bytes:
    n = int(frequence * duree_ms / 1000)
    fondu = max(1, n // 20)  # evite le "clic" en debut/fin
    valeurs = bytearray()
    for i in range(n):
        gain = min(1.0, i / fondu, (n - i) / fondu)
        v = int(32767 * volume * gain * math.sin(2 * math.pi * freq * i / frequence))
        valeurs += struct.pack("<h", v)
    return bytes(valeurs)


# ---------------------------------------------------------------------------
# Signatures sonores : l'enfant doit comprendre l'etat de la boite sans ecran.
# ---------------------------------------------------------------------------
def bip_ecoute(hp: HautParleur) -> None:
    hp.bip(880, 120)


def bip_reflexion(hp: HautParleur) -> None:
    hp.bip(660, 90, volume=0.15)


def bip_erreur(hp: HautParleur) -> None:
    hp.bip(300, 200, volume=0.2)


def fabriquer(conf: ConfAudio, factice: bool = False) -> tuple[Micro, HautParleur]:
    if factice:
        return MicroFactice(conf), HautParleurFactice(conf)
    try:
        _sounddevice()
    except Exception as exc:  # pragma: no cover - depend de la machine
        log.warning("sounddevice indisponible (%s), passage en audio factice", exc)
        return MicroFactice(conf), HautParleurFactice(conf)
    return Micro(conf), HautParleur(conf)
