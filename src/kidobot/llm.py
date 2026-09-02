"""Les deux cerveaux : llama.cpp dans la boite, Claude par wifi.

Les deux backends exposent la meme interface `repondre()` qui rend un flux de
morceaux de texte. Le reste de l'application ne sait pas lequel repond, ce qui
permet de basculer de l'un a l'autre a chaud (panne reseau, modele local trop
lent, batterie faible...).
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterator

import httpx

from .config import Config, LlmClaude, LlmLocal

log = logging.getLogger(__name__)


class LlmIndisponible(RuntimeError):
    pass


class LlmBase:
    nom = "base"

    def repondre(self, systeme: str, question: str) -> Iterator[str]:
        raise NotImplementedError

    def disponible(self) -> bool:
        return True


# ---------------------------------------------------------------------------
# 1. Local : llama.cpp en serveur, API compatible OpenAI
# ---------------------------------------------------------------------------
class LlmLocalHttp(LlmBase):
    """Parle a un serveur d'inference local exposant `/v1/chat/completions`.

    Trois serveurs repondent a cette description et sont interchangeables ici :
    `llama-server` (llama.cpp) sur le CPU du Pi, le meme sur un PC du reseau
    local, et `hailo-ollama` si vous avez un AI HAT+ 2 (voir docs/hardware.md).

    On garde le modele dans un processus separe plutot que dans le notre :
    le chargement des ~2,5 Go de poids prend 5 a 25 s, on ne veut le payer
    qu'au demarrage de la machine, pas a chaque redemarrage de l'application.
    """

    nom = "local"

    def __init__(self, conf: LlmLocal) -> None:
        self.conf = conf

    def disponible(self) -> bool:
        """Le serveur ecoute-t-il ?

        `/health` n'existe que sur llama.cpp ; hailo-ollama et ollama rendent
        404 sur ce chemin tout en etant parfaitement fonctionnels. Un 404 prouve
        que quelque chose ecoute et route : c'est ce qu'on veut savoir. Seuls
        une erreur reseau ou un 5xx signifient reellement "indisponible".
        """
        try:
            r = httpx.get(f"{self.conf.url}{self.conf.chemin_sante}", timeout=2.0)
        except Exception:
            return False
        return r.status_code < 500

    def repondre(self, systeme: str, question: str) -> Iterator[str]:
        charge = {
            "model": self.conf.modele,
            "messages": [
                {"role": "system", "content": systeme},
                {"role": "user", "content": question},
            ],
            "temperature": self.conf.temperature,
            "max_tokens": self.conf.max_tokens,
            "stream": True,
            # Qwen3 et consorts : on coupe le mode reflexion, inutile ici et
            # il double le temps de reponse pour une question d'enfant.
            "chat_template_kwargs": {"enable_thinking": False},
        }
        try:
            with httpx.stream(
                "POST",
                f"{self.conf.url}/v1/chat/completions",
                json=charge,
                timeout=self.conf.timeout_s,
            ) as reponse:
                reponse.raise_for_status()
                for ligne in reponse.iter_lines():
                    morceau = _lire_sse_openai(ligne)
                    if morceau:
                        yield morceau
        except Exception as exc:
            raise LlmIndisponible(f"llama.cpp: {exc}") from exc


def _lire_sse_openai(ligne: str) -> str | None:
    if not ligne or not ligne.startswith("data:"):
        return None
    donnees = ligne[5:].strip()
    if donnees in ("", "[DONE]"):
        return None
    try:
        delta = json.loads(donnees)["choices"][0].get("delta", {})
    except (json.JSONDecodeError, KeyError, IndexError):
        return None
    return delta.get("content") or None


# ---------------------------------------------------------------------------
# 2. Distant : API Claude
# ---------------------------------------------------------------------------
class LlmClaudeApi(LlmBase):
    """Repli wifi. Nettement plus rapide et plus juste que le modele local,
    au prix d'une dependance reseau et d'un cout par question."""

    nom = "claude"

    def __init__(self, conf: LlmClaude) -> None:
        self.conf = conf
        self._client = None

    def _obtenir_client(self):
        if self._client is None:
            try:
                import anthropic
            except ImportError as exc:
                raise LlmIndisponible("paquet anthropic absent") from exc
            self._client = anthropic.Anthropic(timeout=float(self.conf.timeout_s))
        return self._client

    def disponible(self) -> bool:
        if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
            return False
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        return True

    def repondre(self, systeme: str, question: str) -> Iterator[str]:
        client = self._obtenir_client()
        parametres = {
            "model": self.conf.modele,
            "max_tokens": self.conf.max_tokens,
            # effort "low" : la reflexion adaptative reste active mais courte.
            # C'est le bon reglage pour du question/reponse enfant, ou la
            # latence compte davantage que la profondeur.
            "output_config": {"effort": self.conf.effort},
            "system": systeme,
            "messages": [{"role": "user", "content": question}],
        }
        try:
            yield from self._diffuser(client, parametres, repli_refus=True)
        except LlmIndisponible:
            raise
        except Exception as exc:
            log.warning("repli de refus indisponible (%s), appel simple", exc)
            try:
                yield from self._diffuser(client, parametres, repli_refus=False)
            except Exception as exc2:
                raise LlmIndisponible(f"claude: {exc2}") from exc2

    def _diffuser(self, client, parametres: dict, repli_refus: bool) -> Iterator[str]:
        if repli_refus:
            # Si un classificateur de securite refuse la requete, l'API bascule
            # elle-meme vers un modele adapte plutot que de rendre une reponse
            # vide : dans une chambre d'enfant, un silence est un bug.
            flux = client.beta.messages.stream(
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                **parametres,
            )
        else:
            flux = client.messages.stream(**parametres)

        with flux as diffusion:
            yield from diffusion.text_stream
            final = diffusion.get_final_message()

        if final.stop_reason == "refusal":
            categorie = getattr(final.stop_details, "category", None)
            log.info("refus du modele (categorie=%s)", categorie)
            raise LlmIndisponible("refus")


# ---------------------------------------------------------------------------
# 3. Selection : local d'abord, Claude en secours
# ---------------------------------------------------------------------------
class LlmAuto(LlmBase):
    nom = "auto"

    def __init__(self, local: LlmBase, distant: LlmBase) -> None:
        self.local = local
        self.distant = distant
        self.dernier_utilise = "aucun"

    def repondre(self, systeme: str, question: str) -> Iterator[str]:
        if self.local.disponible():
            try:
                # On materialise le premier morceau ici : si le local tombe des
                # le premier token, on peut encore basculer sans que l'enfant
                # ait entendu une demi-phrase.
                flux = self.local.repondre(systeme, question)
                premier = next(flux, "")
                self.dernier_utilise = "local"
                if premier:
                    yield premier
                yield from flux
                return
            except LlmIndisponible as exc:
                log.warning("bascule vers Claude: %s", exc)
        if not self.distant.disponible():
            raise LlmIndisponible("aucun backend disponible")
        self.dernier_utilise = "claude"
        yield from self.distant.repondre(systeme, question)


def fabriquer(conf: Config) -> LlmBase:
    local = LlmLocalHttp(conf.llm.local)
    distant = LlmClaudeApi(conf.llm.claude)
    if conf.llm.backend == "local":
        return local
    if conf.llm.backend == "claude":
        return distant
    return LlmAuto(local, distant)
