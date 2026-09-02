import pytest

from kidobot import llm
from kidobot.config import LlmLocal


class LlmDePanne(llm.LlmBase):
    nom = "panne"

    def disponible(self):
        return True

    def repondre(self, systeme, question):
        raise llm.LlmIndisponible("simulee")
        yield  # pragma: no cover


class LlmQuiRepond(llm.LlmBase):
    nom = "faux"

    def repondre(self, systeme, question):
        yield "Bonjour "
        yield "Lou."


def test_bascule_sur_le_distant_quand_le_local_tombe():
    auto = llm.LlmAuto(LlmDePanne(), LlmQuiRepond())
    assert "".join(auto.repondre("s", "q")) == "Bonjour Lou."
    assert auto.dernier_utilise == "claude"


def test_reste_en_local_quand_il_repond():
    auto = llm.LlmAuto(LlmQuiRepond(), LlmDePanne())
    assert "".join(auto.repondre("s", "q")) == "Bonjour Lou."
    assert auto.dernier_utilise == "local"


def test_erreur_si_aucun_backend():
    class Absent(llm.LlmBase):
        def disponible(self):
            return False

    auto = llm.LlmAuto(Absent(), Absent())
    with pytest.raises(llm.LlmIndisponible):
        list(auto.repondre("s", "q"))


def test_lecture_sse_openai():
    assert llm._lire_sse_openai('data: {"choices":[{"delta":{"content":"salut"}}]}') == "salut"
    assert llm._lire_sse_openai("data: [DONE]") is None
    assert llm._lire_sse_openai(": ping") is None
    assert llm._lire_sse_openai('data: {"choices":[{"delta":{}}]}') is None


def test_local_indisponible_sans_serveur():
    assert not llm.LlmLocalHttp(LlmLocal(url="http://127.0.0.1:1")).disponible()
