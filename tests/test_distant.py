"""Client leger : STT et TTS delegues au PC de la maison."""

import json
import threading
import wave
from http.server import BaseHTTPRequestHandler, HTTPServer

import numpy as np
import pytest

from kidobot import stt, tts
from kidobot.config import Stt as ConfStt
from kidobot.config import Tts as ConfTts


class FauxServeur(BaseHTTPRequestHandler):
    JETON = "secret"
    PCM = b"\x01\x02" * 800
    recu_langue = None

    def do_POST(self):  # noqa: N802
        if self.headers.get("Authorization") != f"Bearer {self.JETON}":
            self.send_response(401)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        corps = self.rfile.read(int(self.headers["Content-Length"]))
        if self.path == "/stt":
            FauxServeur.recu_langue = self.headers.get("X-Langue")
            # On verifie que ce qui arrive est bien un WAV mono 16 bits lisible.
            import io

            with wave.open(io.BytesIO(corps), "rb") as f:
                assert f.getnchannels() == 1 and f.getsampwidth() == 2
            reponse = json.dumps({"texte": "pourquoi le ciel est bleu"}).encode()
            self._envoyer(200, reponse, "application/json")
        elif self.path == "/tts":
            assert json.loads(corps)["phrase"]
            self._envoyer(200, self.PCM, "audio/L16", {"X-Frequence": "16000"})
        else:
            self._envoyer(404, b"{}", "application/json")

    def _envoyer(self, code, corps, mime, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(corps)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(corps)

    def log_message(self, *args):
        pass


@pytest.fixture()
def serveur():
    srv = HTTPServer(("127.0.0.1", 0), FauxServeur)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def test_stt_distant(serveur):
    moteur = stt.fabriquer(ConfStt(backend="distant", url=serveur, jeton="secret"))
    audio = (np.sin(np.linspace(0, 400, 16000)) * 0.3).astype(np.float32)
    assert moteur.transcrire(audio, 16000, "fr") == "pourquoi le ciel est bleu"
    assert FauxServeur.recu_langue == "fr"


def test_stt_distant_sans_jeton_ne_plante_pas(serveur):
    """Un serveur injoignable ou refusant doit rendre une chaine vide, pas une
    exception : la boite jouera sa reponse 'je n'ai pas entendu'."""
    moteur = stt.fabriquer(ConfStt(backend="distant", url=serveur, jeton="faux"))
    assert moteur.transcrire(np.zeros(16000, dtype=np.float32), 16000, "fr") == ""


def test_tts_distant(serveur):
    voix = tts.TtsDistant(ConfTts(backend="distant", url=serveur, jeton="secret"))
    assert voix.synthetiser("Bonjour Lou.") == FauxServeur.PCM
    assert voix.frequence == 16000  # lu dans l'en-tete de la reponse


def test_repli_sur_la_voix_locale_quand_le_serveur_est_eteint():
    conf = ConfTts(backend="distant", url="http://127.0.0.1:1", timeout_s=1, secours="factice")
    voix = tts.fabriquer(conf)
    assert isinstance(voix, tts.TtsAvecSecours)
    voix.synthetiser("Le serveur est eteint.")
    assert voix.en_secours


def test_le_repli_ne_bascule_pas_au_milieu_dune_reponse(serveur):
    conf = ConfTts(backend="distant", url=serveur, jeton="mauvais", secours="factice")
    voix = tts.fabriquer(conf)
    voix.synthetiser("phrase une")
    assert voix.en_secours
    # Toutes les phrases suivantes restent sur la voix de secours...
    voix.synthetiser("phrase deux")
    assert voix.en_secours
    # ...jusqu'a la question suivante, qui retente la principale.
    voix.reinitialiser()
    assert not voix.en_secours


def test_pas_de_repli_quand_la_voix_est_deja_locale():
    assert isinstance(tts.fabriquer(ConfTts(backend="espeak")), tts.Espeak)
