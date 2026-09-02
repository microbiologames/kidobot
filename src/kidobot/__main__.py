"""Point d'entree : `kidobot` (boucle normale) ou `kidobot --texte "..."`."""

from __future__ import annotations

import argparse
import logging
import sys
import time

from . import config as config_mod
from . import llm as llm_mod
from . import prompts, securite
from .app import Kidobot


def _journaliser(verbeux: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbeux else logging.INFO,
        format="%(asctime)s %(levelname).1s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="kidobot", description="La boite a questions.")
    p.add_argument("-c", "--config", help="chemin du fichier TOML")
    p.add_argument("--texte", help="poser une question en texte, sans micro ni bouton")
    p.add_argument("--factice", action="store_true", help="aucun materiel : tout est simule")
    p.add_argument("--diagnostic", action="store_true", help="verifier les briques une a une")
    p.add_argument("-v", "--verbeux", action="store_true")
    args = p.parse_args(argv)

    _journaliser(args.verbeux)
    conf = config_mod.charger(args.config)

    if args.diagnostic:
        return _diagnostic(conf)
    if args.texte:
        return _question_texte(conf, args.texte)

    Kidobot(conf, factice=args.factice).tourner()
    return 0


def _question_texte(conf, question: str) -> int:
    """Boucle complete sans materiel : utile pour regler le prompt."""
    gardien = securite.Gardien(conf.securite, conf.journal.dossier)
    verdict = gardien.verifier_question(question)
    if not verdict.autorise:
        print(prompts.REPONSES_FIXES[verdict.motif])
        return 0

    cerveau = llm_mod.fabriquer(conf)
    debut = time.monotonic()
    dits = 0
    try:
        flux = cerveau.repondre(prompts.systeme(conf), question)
        for brute in securite.decouper_en_phrases(flux):
            if dits >= conf.reponse.max_mots:
                break
            phrase = securite.nettoyer_pour_la_voix(brute, conf.reponse.max_mots - dits)
            dits += len(phrase.split())
            print(phrase, flush=True)
    except llm_mod.LlmIndisponible as exc:
        print(f"[LLM indisponible: {exc}]", file=sys.stderr)
        print(prompts.REPONSES_FIXES["panne"])
        return 1
    print(f"\n({time.monotonic() - debut:.1f}s, backend={getattr(cerveau, 'dernier_utilise', cerveau.nom)})",
          file=sys.stderr)
    return 0


def _sonder(url: str) -> tuple[bool, str]:
    import httpx

    try:
        r = httpx.get(f"{url}/sante", timeout=3.0)
    except Exception as exc:
        return False, f"({type(exc).__name__} - le PC est-il allume ?)"
    return r.status_code < 500, f"(HTTP {r.status_code})"


def _diagnostic(conf) -> int:
    """Verifie chaque brique separement : c'est ce qu'on lance en premier
    quand la boite ne repond plus."""
    ok = True

    def ligne(nom: str, etat: bool, detail: str = "") -> None:
        nonlocal ok
        ok = ok and etat
        print(f"{'OK  ' if etat else 'ERR '} {nom:<22} {detail}")

    try:
        import sounddevice as sd

        entrees = [d["name"] for d in sd.query_devices() if d["max_input_channels"] > 0]
        ligne("micro", bool(entrees), ", ".join(entrees[:2]))
    except Exception as exc:
        ligne("micro", False, str(exc))

    if conf.stt.backend == "distant" or conf.tts.backend == "distant":
        # Panne numero un du mode client leger : le PC de la maison est eteint.
        for nom, url in (("serveur stt", conf.stt.url), ("serveur voix", conf.tts.url)):
            joignable, detail = _sonder(url)
            ligne(nom, joignable, f"{url} {detail}")

    try:
        from . import stt as stt_mod

        moteur = stt_mod.fabriquer(conf.stt)
        ligne("transcription", not isinstance(moteur, stt_mod.SttFactice), conf.stt.backend)
    except Exception as exc:
        ligne("transcription", False, str(exc))

    local = llm_mod.LlmLocalHttp(conf.llm.local)
    ligne("llm local", local.disponible(), conf.llm.local.url)

    distant = llm_mod.LlmClaudeApi(conf.llm.claude)
    ligne("llm claude", distant.disponible(), conf.llm.claude.modele)

    from . import tts as tts_mod

    voix = tts_mod.fabriquer(conf.tts)
    ligne("voix", bool(voix.synthetiser("Bonjour.")), conf.tts.backend)

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
