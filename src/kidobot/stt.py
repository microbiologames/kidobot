"""Transcription de la question. Elle tourne TOUJOURS en local.

C'est un choix de conception assume : meme quand le LLM est distant, la voix
de l'enfant ne quitte jamais la maison. Seul le texte transcrit part sur le
reseau. Cela change completement la conversation avec les parents.
"""

from __future__ import annotations

import io
import logging
import subprocess
import tempfile
import wave
from pathlib import Path

import httpx
import numpy as np

from .config import Stt as ConfStt

log = logging.getLogger(__name__)


class SttBase:
    def transcrire(self, audio: np.ndarray, frequence: int, langue: str) -> str:
        raise NotImplementedError


class FasterWhisper(SttBase):
    """faster-whisper (CTranslate2) : le meilleur rapport vitesse/qualite sur ARM64.

    Sur Raspberry Pi 5, `small` en int8 transcrit 5 s de parole en ~1,5 s.
    `base` descend a ~0,7 s mais confond davantage les mots d'enfant.
    """

    def __init__(self, conf: ConfStt) -> None:
        from faster_whisper import WhisperModel

        self._modele = WhisperModel(conf.modele, device="cpu", compute_type=conf.calcul)

    def transcrire(self, audio: np.ndarray, frequence: int, langue: str) -> str:
        if frequence != 16000:
            audio = _reechantillonner(audio, frequence, 16000)
        segments, _ = self._modele.transcribe(
            audio,
            language=langue,
            beam_size=1,             # greedy : deux fois plus rapide, suffisant ici
            vad_filter=True,
            condition_on_previous_text=False,
            # Amorce le decodage avec le vocabulaire attendu d'un enfant.
            initial_prompt="Une question posee par un enfant.",
        )
        return " ".join(s.text.strip() for s in segments).strip()


class WhisperCpp(SttBase):
    """Repli : binaire whisper.cpp appele en sous-processus."""

    def __init__(self, conf: ConfStt) -> None:
        self.conf = conf

    def transcrire(self, audio: np.ndarray, frequence: int, langue: str) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / "question.wav"
            ecrire_wav(wav, audio, frequence)
            cmd = [
                self.conf.binaire,
                "-m", self.conf.modele_gguf,
                "-f", str(wav),
                "-l", langue,
                "-nt", "-np",
                "--threads", "4",
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
            if res.returncode != 0:
                log.error("whisper.cpp a echoue: %s", res.stderr[-400:])
                return ""
            return res.stdout.strip()


class SttDistant(SttBase):
    """La transcription tourne sur le PC de la maison.

    C'est ce qui permet de descendre la boite jusqu'au Pi Zero 2 W : whisper
    est de loin la brique la plus lourde du pipeline, et c'est aussi celle qui
    profite le plus d'une vraie machine (un modele `large` comprend nettement
    mieux une voix d'enfant qu'un `base`, et c'est le premier mode d'echec de
    l'objet). On envoie le WAV complet apres le relachement du bouton, pas un
    flux : une requete unique est bien plus robuste au wifi 2,4 GHz encombre
    qu'un streaming continu.
    """

    def __init__(self, conf: ConfStt) -> None:
        self.conf = conf

    def transcrire(self, audio: np.ndarray, frequence: int, langue: str) -> str:
        tampon = io.BytesIO()
        _ecrire_wav_flux(tampon, audio, frequence)
        entetes = {"Content-Type": "audio/wav", "X-Langue": langue}
        if self.conf.jeton:
            entetes["Authorization"] = f"Bearer {self.conf.jeton}"
        try:
            r = httpx.post(
                f"{self.conf.url}/stt",
                content=tampon.getvalue(),
                headers=entetes,
                timeout=self.conf.timeout_s,
            )
            r.raise_for_status()
            return r.json().get("texte", "").strip()
        except Exception as exc:
            log.error("transcription distante indisponible: %s", exc)
            return ""


class SttFactice(SttBase):
    def __init__(self, texte: str = "Pourquoi le ciel est bleu ?") -> None:
        self.texte = texte

    def transcrire(self, audio: np.ndarray, frequence: int, langue: str) -> str:
        return self.texte


def ecrire_wav(chemin: Path, audio: np.ndarray, frequence: int) -> None:
    with open(chemin, "wb") as f:
        _ecrire_wav_flux(f, audio, frequence)


def _ecrire_wav_flux(flux, audio: np.ndarray, frequence: int) -> None:
    pcm = np.clip(audio, -1.0, 1.0)
    with wave.open(flux, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(frequence)
        f.writeframes((pcm * 32767).astype(np.int16).tobytes())


def _reechantillonner(audio: np.ndarray, source: int, cible: int) -> np.ndarray:
    if source == cible or audio.size == 0:
        return audio
    n = int(len(audio) * cible / source)
    return np.interp(
        np.linspace(0, len(audio) - 1, n, dtype=np.float64),
        np.arange(len(audio)),
        audio,
    ).astype(np.float32)


def fabriquer(conf: ConfStt) -> SttBase:
    if conf.backend == "factice":
        return SttFactice()
    if conf.backend == "distant":
        return SttDistant(conf)
    if conf.backend == "whisper-cpp":
        return WhisperCpp(conf)
    try:
        return FasterWhisper(conf)
    except Exception as exc:  # pragma: no cover - depend de l'installation
        log.warning("faster-whisper indisponible (%s), STT factice", exc)
        return SttFactice("(transcription indisponible)")
