"""Machine a etats de la boite.

    repos ──appui──> ecoute ──relachement──> transcription
                                                  │
                                        reflexion + parole (en pipeline)
                                                  │
                                               repos

Le point important est le pipeline entre le LLM et la synthese : des que la
premiere phrase est complete, on la fait parler pendant que le modele redige
la suivante. Sur le modele local, cela fait passer le "temps avant premier
son" de ~7 s a ~3 s, ce qui change tout pour un enfant de 7 ans.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass

from . import audio as audio_mod
from . import bouton as bouton_mod
from . import journal as journal_mod
from . import llm as llm_mod
from . import prompts, securite, stt, tts
from .config import Config

log = logging.getLogger(__name__)


@dataclass
class Echange:
    question: str = ""
    reponse: str = ""
    backend: str = ""
    motif: str = ""
    duree_s: float = 0.0


class Kidobot:
    def __init__(self, conf: Config, factice: bool = False) -> None:
        self.conf = conf
        self.micro, self.hp = audio_mod.fabriquer(conf.audio, factice=factice)
        self.bouton = bouton_mod.BoutonClavier() if factice else bouton_mod.fabriquer_bouton(conf.bouton)
        self.leds = bouton_mod.Leds(conf.leds)
        self.stt = stt.fabriquer(conf.stt)
        self.llm = llm_mod.fabriquer(conf)
        self.tts = tts.fabriquer(conf.tts)
        self.gardien = securite.Gardien(conf.securite, conf.journal.dossier)
        self.journal = journal_mod.JournalParental(conf.journal)
        self.systeme = prompts.systeme(conf)

    # -- boucle principale --------------------------------------------------
    def tourner(self) -> None:
        log.info("Kidobot pret. Backend LLM: %s", self.llm.nom)
        self.leds.repos()
        try:
            while True:
                self.bouton.attendre_appui()
                echange = self.un_tour()
                log.info("Q: %s | R: %s (%.1fs, %s)",
                         echange.question, echange.reponse, echange.duree_s, echange.backend)
                self.leds.repos()
        except KeyboardInterrupt:
            log.info("arret demande")
        finally:
            self.fermer()

    def un_tour(self) -> Echange:
        debut = time.monotonic()
        echange = Echange()
        # Chaque question retente la voix principale : le PC de la maison a pu
        # se rallumer depuis la derniere fois.
        if isinstance(self.tts, tts.TtsAvecSecours):
            self.tts.reinitialiser()

        verdict = self.gardien.verifier_horaire()
        if not verdict.autorise:
            return self._reponse_fixe(echange, verdict.motif, debut)

        verdict = self.gardien.verifier_quota()
        if not verdict.autorise:
            return self._reponse_fixe(echange, verdict.motif, debut)

        # 1. Ecoute
        self.leds.ecoute()
        audio_mod.bip_ecoute(self.hp)
        if self.conf.bouton.mode == "maintien":
            son = self.micro.enregistrer_pendant_appui(self.bouton.est_enfonce)
        else:
            son = self.micro.enregistrer_jusqu_au_silence()

        # 2. Transcription
        self.leds.reflexion()
        audio_mod.bip_reflexion(self.hp)
        echange.question = self.stt.transcrire(son, self.conf.audio.frequence, self.conf.enfant.langue)

        if len(echange.question.strip()) < 2:
            return self._reponse_fixe(echange, "vide", debut)

        verdict = self.gardien.verifier_question(echange.question)
        if not verdict.autorise:
            return self._reponse_fixe(echange, verdict.motif, debut)

        # 3. Reflexion + parole en pipeline
        try:
            echange.reponse = self._repondre_et_parler(echange.question)
            echange.backend = getattr(self.llm, "dernier_utilise", self.llm.nom)
        except llm_mod.LlmIndisponible as exc:
            log.warning("LLM indisponible: %s", exc)
            return self._reponse_fixe(echange, "panne", debut)

        self.gardien.incrementer()
        echange.duree_s = time.monotonic() - debut
        self.journal.ecrire(echange.question, echange.reponse, echange.backend, echange.duree_s)
        return echange

    # -- pipeline LLM -> TTS -> haut-parleur --------------------------------
    def _repondre_et_parler(self, question: str) -> str:
        file_phrases: queue.Queue[str | None] = queue.Queue()
        morceaux: list[str] = []
        erreur: list[BaseException] = []

        def producteur() -> None:
            try:
                flux = self.llm.repondre(self.systeme, question)
                for phrase in securite.decouper_en_phrases(flux):
                    morceaux.append(phrase)
                    file_phrases.put(phrase)
            except BaseException as exc:  # noqa: BLE001 - remonte au thread principal
                erreur.append(exc)
            finally:
                file_phrases.put(None)

        fil = threading.Thread(target=producteur, daemon=True)
        fil.start()

        self.leds.parole()
        mots_dits = 0
        limite = self.conf.reponse.max_mots
        dits: list[str] = []
        while True:
            phrase = file_phrases.get()
            if phrase is None:
                break
            if mots_dits >= limite:
                continue  # on vide la file sans parler : la limite est ferme
            phrase = securite.nettoyer_pour_la_voix(phrase, limite - mots_dits)
            if not phrase:
                continue
            dits.append(phrase)
            mots_dits += len(phrase.split())
            pcm = self.tts.synthetiser(phrase)
            self.hp.jouer_pcm(pcm, self.tts.frequence)

        fil.join(timeout=1.0)
        if erreur:
            raise erreur[0]
        return " ".join(dits) or "".join(morceaux)

    def _reponse_fixe(self, echange: Echange, motif: str, debut: float) -> Echange:
        texte = prompts.REPONSES_FIXES.get(motif, prompts.REPONSES_FIXES["panne"])
        echange.reponse = texte
        echange.motif = motif
        echange.backend = "fixe"
        if motif in ("panne", "vide", "non_compris"):
            self.leds.erreur()
            audio_mod.bip_erreur(self.hp)
        else:
            self.leds.parole()
        self.hp.jouer_pcm(self.tts.synthetiser(texte), self.tts.frequence)
        echange.duree_s = time.monotonic() - debut
        self.journal.ecrire(echange.question, texte, "fixe", echange.duree_s, motif)
        return echange

    def fermer(self) -> None:
        self.leds.fermer()
        self.bouton.fermer()
