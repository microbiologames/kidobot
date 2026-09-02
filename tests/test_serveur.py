"""Le serveur de la maison : validation d'entree et authentification.

`faster_whisper` n'est importe que dans `Moteurs.__init__`, donc le module
s'importe sans les dependances lourdes et ces tests tournent partout.
"""

import importlib.util
import io
import wave
from pathlib import Path

import pytest

_chemin = Path(__file__).resolve().parents[1] / "serveur" / "kidobot_serveur.py"
_spec = importlib.util.spec_from_file_location("kidobot_serveur", _chemin)
serveur = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(serveur)


def _wav(canaux: int = 1, largeur: int = 2) -> bytes:
    tampon = io.BytesIO()
    with wave.open(tampon, "wb") as f:
        f.setnchannels(canaux)
        f.setsampwidth(largeur)
        f.setframerate(16000)
        f.writeframes(b"\x00" * 3200)
    return tampon.getvalue()


def test_wav_mono_16_bits_accepte():
    serveur._valider_wav(_wav())


@pytest.mark.parametrize(
    ("donnees", "raison"),
    [
        (b"ceci n'est pas un wav", "octets arbitraires"),
        (_wav(canaux=2), "stereo"),
        (_wav(largeur=1), "8 bits"),
        (b"", "vide"),
    ],
)
def test_entrees_invalides_rejetees(donnees, raison):
    with pytest.raises((wave.Error, ValueError, EOFError)):
        serveur._valider_wav(donnees)


def test_le_jeton_est_obligatoire_quand_il_est_configure():
    class FauxGestionnaire:
        headers = {"Authorization": "Bearer mauvais"}
        jeton = "bon"
        _autorise = serveur.Gestionnaire._autorise

    assert not FauxGestionnaire._autorise(FauxGestionnaire())

    class Correct(FauxGestionnaire):
        headers = {"Authorization": "Bearer bon"}

    assert Correct._autorise(Correct())


def test_sans_jeton_configure_tout_passe():
    class Ouvert:
        headers = {}
        jeton = ""
        _autorise = serveur.Gestionnaire._autorise

    assert Ouvert._autorise(Ouvert())


def test_valeurs_par_defaut_de_la_ligne_de_commande():
    args = serveur.analyser(["--voix", "fr.onnx"])
    assert args.modele_whisper == "large-v3"  # la machine peut se le permettre
    assert args.hote == "0.0.0.0" and args.port == 8100
