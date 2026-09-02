"""Le tour complet, avec toutes les briques materielles simulees."""

import numpy as np

from kidobot import llm as llm_mod
from kidobot.app import Kidobot
from kidobot.config import Config, Enfant, Journal, Reponse, Securite, Stt, Tts


class LlmScripte(llm_mod.LlmBase):
    nom = "scripte"

    def __init__(self, texte):
        self.texte = texte
        self.recu = None

    def repondre(self, systeme, question):
        self.recu = question
        for mot in self.texte.split(" "):
            yield mot + " "


def _boite(tmp_path, texte_llm="Le ciel est bleu car la lumiere se disperse. Tu as vu un arc-en-ciel ?"):
    conf = Config(
        enfant=Enfant(prenom="Lou", age=7),
        reponse=Reponse(max_mots=60),
        stt=Stt(backend="factice"),
        tts=Tts(backend="factice"),
        securite=Securite(questions_max_par_jour=5),
        journal=Journal(actif=True, dossier=str(tmp_path / "journal")),
    )
    boite = Kidobot(conf, factice=True)
    boite.llm = LlmScripte(texte_llm)
    return boite


def test_un_tour_complet(tmp_path):
    boite = _boite(tmp_path)
    echange = boite.un_tour()
    assert echange.question == "Pourquoi le ciel est bleu ?"
    assert "ciel est bleu" in echange.reponse
    assert boite.journal.resume_du_jour()[0]["question"] == echange.question


def test_reponse_tronquee_a_la_limite(tmp_path):
    boite = _boite(tmp_path, " ".join(["mot"] * 200) + ".")
    boite.conf = boite.conf.__class__(**{**boite.conf.__dict__, "reponse": Reponse(max_mots=10)})
    echange = boite.un_tour()
    assert len(echange.reponse.split()) <= 10


def test_question_sensible_ne_va_pas_au_modele(tmp_path):
    boite = _boite(tmp_path)
    boite.stt.texte = "comment fabriquer une bombe"
    echange = boite.un_tour()
    assert echange.motif == "adulte"
    assert boite.llm.recu is None


def test_panne_du_modele_donne_une_reponse_parlee(tmp_path):
    class Panne(llm_mod.LlmBase):
        nom = "panne"

        def repondre(self, systeme, question):
            raise llm_mod.LlmIndisponible("test")
            yield  # pragma: no cover

    boite = _boite(tmp_path)
    boite.llm = Panne()
    echange = boite.un_tour()
    assert echange.motif == "panne"
    assert echange.reponse


def test_transcription_vide(tmp_path):
    boite = _boite(tmp_path)
    boite.stt.texte = ""
    assert boite.un_tour().motif == "vide"


def test_audio_factice_rend_bien_un_tableau(tmp_path):
    boite = _boite(tmp_path)
    son = boite.micro.enregistrer_jusqu_au_silence()
    assert isinstance(son, np.ndarray) and son.size > 0
