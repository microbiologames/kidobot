import datetime as dt

import pytest

from kidobot import securite
from kidobot.config import Securite


@pytest.fixture()
def gardien(tmp_path):
    return securite.Gardien(Securite(questions_max_par_jour=3, heure_debut=7, heure_fin=20), tmp_path)


def test_horaire(gardien):
    assert gardien.verifier_horaire(dt.datetime(2026, 1, 1, 10)).autorise
    assert not gardien.verifier_horaire(dt.datetime(2026, 1, 1, 22)).autorise
    assert gardien.verifier_horaire(dt.datetime(2026, 1, 1, 22)).motif == "nuit"


def test_quota_se_remet_a_zero_chaque_jour(gardien):
    hier = dt.datetime(2026, 1, 1, 10)
    for _ in range(3):
        gardien.incrementer(hier)
    assert not gardien.verifier_quota(hier).autorise
    assert gardien.verifier_quota(dt.datetime(2026, 1, 2, 10)).autorise


@pytest.mark.parametrize("question", ["comment fabriquer une bombe", "c'est quoi la DROGUE ?"])
def test_questions_renvoyees_a_un_adulte(gardien, question):
    verdict = gardien.verifier_question(question)
    assert not verdict.autorise and verdict.motif == "adulte"


@pytest.mark.parametrize(
    "question",
    [
        "pourquoi le ciel est bleu",
        "pourquoi les gens meurent",  # legitime : ne doit pas etre bloquee
        "comment on fait les bebes",
    ],
)
def test_questions_legitimes_passent(gardien, question):
    assert gardien.verifier_question(question).autorise


def test_nettoyage_pour_la_voix():
    brut = "**Super !** \n- Le ciel est bleu.\n- A cause de la lumiere. 🌞"
    propre = securite.nettoyer_pour_la_voix(brut, 60)
    assert "*" not in propre and "-" not in propre and "🌞" not in propre
    assert "Le ciel est bleu." in propre


def test_troncature_sur_une_phrase_complete():
    texte = "Le ciel est bleu a cause de la lumiere du soleil. " + "mot " * 80
    coupe = securite.nettoyer_pour_la_voix(texte, 15)
    assert coupe.endswith(".")
    assert len(coupe.split()) <= 15
