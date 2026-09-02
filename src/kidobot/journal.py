"""Journal parental.

Tout ce que la boite entend et repond est ecrit en clair, en local, dans un
fichier JSONL par jour. C'est la contrepartie du micro dans la chambre : les
parents peuvent tout relire, et rien ne part ailleurs.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from .config import Journal as ConfJournal


class JournalParental:
    def __init__(self, conf: ConfJournal) -> None:
        self.conf = conf
        self.dossier = Path(conf.dossier)

    def ecrire(
        self,
        question: str,
        reponse: str,
        backend: str,
        duree_s: float,
        motif: str = "",
    ) -> None:
        if not self.conf.actif:
            return
        self.dossier.mkdir(parents=True, exist_ok=True)
        maintenant = dt.datetime.now()
        ligne = {
            "horodatage": maintenant.isoformat(timespec="seconds"),
            "question": question,
            "reponse": reponse,
            "backend": backend,
            "duree_s": round(duree_s, 2),
        }
        if motif:
            ligne["motif"] = motif
        fichier = self.dossier / f"{maintenant.date().isoformat()}.jsonl"
        with fichier.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ligne, ensure_ascii=False) + "\n")

    def resume_du_jour(self, jour: dt.date | None = None) -> list[dict]:
        jour = jour or dt.date.today()
        fichier = self.dossier / f"{jour.isoformat()}.jsonl"
        if not fichier.exists():
            return []
        lignes = fichier.read_text(encoding="utf-8").splitlines()
        return [json.loads(ligne) for ligne in lignes if ligne.strip()]
