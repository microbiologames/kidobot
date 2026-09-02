"""Chargement et validation de la configuration TOML."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAUT = Path("config/kidobot.toml")
EXEMPLE = Path("config/kidobot.example.toml")


@dataclass(frozen=True)
class Enfant:
    prenom: str = "toi"
    age: int = 7
    langue: str = "fr"


@dataclass(frozen=True)
class Reponse:
    max_mots: int = 60
    relance: bool = True


@dataclass(frozen=True)
class Bouton:
    backend: str = "clavier"
    broche: int = 17
    pull_up: bool = True
    mode: str = "maintien"


@dataclass(frozen=True)
class Leds:
    backend: str = "aucun"
    broche: int = 27


@dataclass(frozen=True)
class Audio:
    peripherique_entree: str = ""
    peripherique_sortie: str = ""
    frequence: int = 16000
    vad_agressivite: int = 2
    silence_fin_ms: int = 900
    duree_max_question_s: int = 15


@dataclass(frozen=True)
class Stt:
    backend: str = "faster-whisper"
    modele: str = "small"
    calcul: str = "int8"
    binaire: str = "whisper-cli"
    modele_gguf: str = ""


@dataclass(frozen=True)
class LlmLocal:
    url: str = "http://127.0.0.1:8080"
    modele: str = "kidobot-local"
    temperature: float = 0.6
    max_tokens: int = 220
    timeout_s: int = 60


@dataclass(frozen=True)
class LlmClaude:
    modele: str = "claude-opus-5"
    effort: str = "low"
    max_tokens: int = 400
    timeout_s: int = 30


@dataclass(frozen=True)
class Llm:
    backend: str = "auto"
    local: LlmLocal = field(default_factory=LlmLocal)
    claude: LlmClaude = field(default_factory=LlmClaude)


@dataclass(frozen=True)
class Tts:
    backend: str = "piper"
    binaire: str = "piper"
    voix: str = ""
    vitesse: float = 1.0


@dataclass(frozen=True)
class Securite:
    rediriger_vers_adulte: bool = True
    questions_max_par_jour: int = 40
    heure_debut: int = 7
    heure_fin: int = 20


@dataclass(frozen=True)
class Journal:
    actif: bool = True
    dossier: str = "journal"


@dataclass(frozen=True)
class Config:
    enfant: Enfant = field(default_factory=Enfant)
    reponse: Reponse = field(default_factory=Reponse)
    bouton: Bouton = field(default_factory=Bouton)
    leds: Leds = field(default_factory=Leds)
    audio: Audio = field(default_factory=Audio)
    stt: Stt = field(default_factory=Stt)
    llm: Llm = field(default_factory=Llm)
    tts: Tts = field(default_factory=Tts)
    securite: Securite = field(default_factory=Securite)
    journal: Journal = field(default_factory=Journal)


def _construire(cls: type, brut: dict[str, Any]) -> Any:
    """Instancie une dataclass en ignorant les cles inconnues du TOML."""
    champs = {f.name for f in cls.__dataclass_fields__.values()}
    inconnues = set(brut) - champs
    if inconnues:
        raise ValueError(f"{cls.__name__}: cles inconnues {sorted(inconnues)}")
    return cls(**{k: v for k, v in brut.items() if k in champs})


def charger(chemin: Path | str | None = None) -> Config:
    """Charge la config ; retombe sur l'exemple, puis sur les valeurs par defaut."""
    candidats = [Path(chemin)] if chemin else [DEFAUT, EXEMPLE]
    fichier = next((c for c in candidats if c.exists()), None)
    if fichier is None:
        return Config()

    brut = tomllib.loads(fichier.read_text(encoding="utf-8"))
    llm_brut = dict(brut.get("llm", {}))
    llm = Llm(
        backend=llm_brut.get("backend", "auto"),
        local=_construire(LlmLocal, llm_brut.get("local", {})),
        claude=_construire(LlmClaude, llm_brut.get("claude", {})),
    )
    return Config(
        enfant=_construire(Enfant, brut.get("enfant", {})),
        reponse=_construire(Reponse, brut.get("reponse", {})),
        bouton=_construire(Bouton, brut.get("bouton", {})),
        leds=_construire(Leds, brut.get("leds", {})),
        audio=_construire(Audio, brut.get("audio", {})),
        stt=_construire(Stt, brut.get("stt", {})),
        llm=llm,
        tts=_construire(Tts, brut.get("tts", {})),
        securite=_construire(Securite, brut.get("securite", {})),
        journal=_construire(Journal, brut.get("journal", {})),
    )
