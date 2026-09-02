"""Bouton physique + anneau lumineux, avec un repli clavier pour le dev."""

from __future__ import annotations

import logging
import sys
import threading
import time

from .config import Bouton as ConfBouton
from .config import Leds as ConfLeds

log = logging.getLogger(__name__)


class BoutonBase:
    def attendre_appui(self) -> None:
        raise NotImplementedError

    def est_enfonce(self) -> bool:
        raise NotImplementedError

    def fermer(self) -> None:
        pass


class BoutonGpio(BoutonBase):
    """Gros bouton arcade cable entre la broche BCM et la masse."""

    def __init__(self, conf: ConfBouton) -> None:
        from gpiozero import Button

        self._btn = Button(conf.broche, pull_up=conf.pull_up, bounce_time=0.05)

    def attendre_appui(self) -> None:
        self._btn.wait_for_press()

    def est_enfonce(self) -> bool:
        return bool(self._btn.is_pressed)

    def fermer(self) -> None:
        self._btn.close()


class BoutonClavier(BoutonBase):
    """Entree = appui. Sert a developper le pipeline sans materiel."""

    def __init__(self, duree_simulee_s: float = 4.0) -> None:
        self.duree_simulee_s = duree_simulee_s
        self._relache_a = 0.0

    def attendre_appui(self) -> None:
        print("[Entree] pour poser une question, Ctrl-C pour quitter.", flush=True)
        sys.stdin.readline()
        self._relache_a = time.monotonic() + self.duree_simulee_s

    def est_enfonce(self) -> bool:
        return time.monotonic() < self._relache_a


# ---------------------------------------------------------------------------
# Lumiere : quatre etats, aucun ecran. C'est toute l'interface de l'objet.
# ---------------------------------------------------------------------------
class Leds:
    """repos (eteint) - ecoute (allume) - reflexion (pulse) - parole (clignote)."""

    def __init__(self, conf: ConfLeds) -> None:
        self._pwm = None
        if conf.backend == "gpio":
            try:
                from gpiozero import PWMLED

                self._pwm = PWMLED(conf.broche)
            except Exception as exc:  # pragma: no cover - depend du materiel
                log.warning("LED GPIO indisponible (%s)", exc)
        self._animation: threading.Thread | None = None
        self._arret = threading.Event()

    def _stopper_animation(self) -> None:
        self._arret.set()
        if self._animation and self._animation.is_alive():
            self._animation.join(timeout=1.0)
        self._arret.clear()
        self._animation = None

    def repos(self) -> None:
        self._stopper_animation()
        if self._pwm:
            self._pwm.value = 0.05  # veilleuse : la boite reste visible la nuit

    def ecoute(self) -> None:
        self._stopper_animation()
        if self._pwm:
            self._pwm.value = 1.0

    def reflexion(self) -> None:
        self._boucler(self._pulser)

    def parole(self) -> None:
        self._boucler(self._clignoter)

    def erreur(self) -> None:
        self._stopper_animation()
        if not self._pwm:
            return
        for _ in range(3):
            self._pwm.value = 1.0
            time.sleep(0.1)
            self._pwm.value = 0.0
            time.sleep(0.1)

    def _boucler(self, motif) -> None:
        self._stopper_animation()
        if not self._pwm:
            return
        self._animation = threading.Thread(target=motif, daemon=True)
        self._animation.start()

    def _pulser(self) -> None:
        import math

        t = 0.0
        while not self._arret.is_set():
            self._pwm.value = 0.15 + 0.85 * (0.5 + 0.5 * math.sin(t))
            t += 0.15
            time.sleep(0.03)

    def _clignoter(self) -> None:
        allume = True
        while not self._arret.is_set():
            self._pwm.value = 0.9 if allume else 0.35
            allume = not allume
            time.sleep(0.25)

    def fermer(self) -> None:
        self._stopper_animation()
        if self._pwm:
            self._pwm.off()
            self._pwm.close()


def fabriquer_bouton(conf: ConfBouton) -> BoutonBase:
    if conf.backend == "gpio":
        try:
            return BoutonGpio(conf)
        except Exception as exc:  # pragma: no cover - depend du materiel
            log.warning("GPIO indisponible (%s), repli clavier", exc)
    return BoutonClavier()
