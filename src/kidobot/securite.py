"""Garde-fous cotes boite : ils ne remplacent pas le prompt, ils l'encadrent.

Principe : le prompt systeme gere la nuance, ce module gere le deterministe
(quota, heures, mots-cles rouges, nettoyage de la sortie avant la synthese).
"""

from __future__ import annotations

import datetime as dt
import re
import unicodedata
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from .config import Securite as ConfSecurite

# Volontairement court et explicite. Un filtre trop large frustre l'enfant sur
# des questions legitimes ("pourquoi les gens meurent ?" merite une reponse) :
# on ne bloque que ce qu'on veut vraiment renvoyer a un adulte.
MOTS_ADULTE = {
    "suicide",
    "me tuer",
    "se tuer",
    "me faire du mal",
    "porno",
    "pornographie",
    "sexe",
    "viol",
    "drogue",
    "cocaine",
    "heroine",
    "fabriquer une bombe",
    "faire une bombe",
    "acheter une arme",
    "fabriquer une arme",
}


@dataclass
class Verdict:
    autorise: bool
    motif: str = ""


def _normaliser(texte: str) -> str:
    sans_accent = unicodedata.normalize("NFKD", texte.lower())
    sans_accent = "".join(c for c in sans_accent if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sans_accent).strip()


class Gardien:
    def __init__(self, conf: ConfSecurite, dossier_etat: Path | str = "journal") -> None:
        self.conf = conf
        self._compteur = Path(dossier_etat) / "compteur.txt"

    # -- avant d'appeler le modele -----------------------------------------
    def verifier_horaire(self, maintenant: dt.datetime | None = None) -> Verdict:
        maintenant = maintenant or dt.datetime.now()
        debut, fin = self.conf.heure_debut, self.conf.heure_fin
        if debut <= maintenant.hour < fin:
            return Verdict(True)
        return Verdict(False, "nuit")

    def verifier_quota(self, maintenant: dt.datetime | None = None) -> Verdict:
        jour, n = self._lire_compteur(maintenant)
        if n >= self.conf.questions_max_par_jour:
            return Verdict(False, "quota")
        return Verdict(True)

    def incrementer(self, maintenant: dt.datetime | None = None) -> None:
        jour, n = self._lire_compteur(maintenant)
        self._compteur.parent.mkdir(parents=True, exist_ok=True)
        self._compteur.write_text(f"{jour} {n + 1}", encoding="utf-8")

    def _lire_compteur(self, maintenant: dt.datetime | None = None) -> tuple[str, int]:
        aujourdhui = (maintenant or dt.datetime.now()).date().isoformat()
        if not self._compteur.exists():
            return aujourdhui, 0
        try:
            jour, n = self._compteur.read_text(encoding="utf-8").split()
        except ValueError:
            return aujourdhui, 0
        return (aujourdhui, 0) if jour != aujourdhui else (aujourdhui, int(n))

    def verifier_question(self, question: str) -> Verdict:
        if not self.conf.rediriger_vers_adulte:
            return Verdict(True)
        norme = _normaliser(question)
        for mot in MOTS_ADULTE:
            if _normaliser(mot) in norme:
                return Verdict(False, "adulte")
        return Verdict(True)


# -- apres le modele, avant la synthese vocale ------------------------------
_MARKDOWN = re.compile(r"[*_`#>]|^\s*[-•]\s+", re.MULTILINE)
_EMOJI = re.compile("[\U0001f000-\U0001faff☀-➿]", re.UNICODE)


def nettoyer_pour_la_voix(texte: str, max_mots: int) -> str:
    """Retire ce qui se lit mal a voix haute et coupe proprement si trop long."""
    texte = _MARKDOWN.sub(" ", texte)
    texte = _EMOJI.sub("", texte)
    texte = re.sub(r"\s+", " ", texte).strip()

    mots = texte.split()
    if len(mots) <= max_mots:
        return texte
    # On coupe a la derniere phrase complete plutot qu'au milieu d'un mot.
    tronque = " ".join(mots[:max_mots])
    fin = max(tronque.rfind("."), tronque.rfind("!"), tronque.rfind("?"))
    return tronque[: fin + 1] if fin > 20 else tronque.rstrip(",;: ") + "."


def decouper_en_phrases(flux: Iterable[str]) -> Iterator[str]:
    """Accumule un flux de tokens et rend des phrases completes.

    C'est le truc qui divise la latence percue par deux : on lance la synthese
    de la premiere phrase pendant que le modele ecrit encore la suivante.
    """
    tampon = ""
    for morceau in flux:
        tampon += morceau
        while True:
            coupe = _prochaine_coupure(tampon)
            if coupe is None:
                break
            phrase, tampon = tampon[:coupe].strip(), tampon[coupe:].lstrip()
            if phrase:
                yield phrase
    if tampon.strip():
        yield tampon.strip()


def _prochaine_coupure(texte: str, mini: int = 25) -> int | None:
    for i, c in enumerate(texte):
        if i + 1 < mini:
            continue
        if c in ".!?" and (i + 1 == len(texte) or texte[i + 1] in " \n"):
            return i + 1
    return None
