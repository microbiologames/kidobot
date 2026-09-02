# Matériel

## 0. Jusqu'où peut-on descendre la Pi ?

Tout dépend d'une seule question : **la boîte garde-t-elle whisper ?**

C'est whisper, pas le LLM, qui fixe le plancher matériel. Une fois le LLM
déporté sur le PC de la maison, la transcription devient de loin la tâche la
plus lourde qui reste dans la boîte — et c'est aussi celle qui gagne le plus à
être déportée à son tour.

| Répartition | La boîte fait | Plancher | Prix carte |
|---|---|---|---|
| **A. Boîte autonome** | micro, whisper, piper, HP | **Pi 4 2 Go** | ~45 € |
| **B. Client léger** | micro, HP, bouton | **Pi Zero 2 W** | ~18 € |

### A. La boîte garde whisper et piper

Plancher : **Raspberry Pi 4 2 Go**, avec `stt.modele = "base"` et une voix
piper `low`. Sur Pi 4 la transcription dépasse le temps réel dès le modèle
`small`, et piper traîne sur les voix `medium` — donc on descend d'un cran sur
les deux. 1 Go de RAM suffirait, mais 2 Go coûtent 5 € de plus et évitent de
compter les octets.

En dessous, ça ne passe pas : un Pi Zero 2 W ou un Pi 3 sont trop justes pour
whisper *et* piper (piper y tourne « loin du temps réel »), et 512 Mo de RAM
rendent tout marginal.

### B. La boîte n'est plus qu'un micro et un haut-parleur

Plancher : **Raspberry Pi Zero 2 W**, 15-18 €. Elle capte le son, l'envoie au
PC, et joue ce qui revient. C'est `serveur/kidobot_serveur.py` qui fait le
travail à l'autre bout.

**Et c'est meilleur sur presque tous les axes, pas seulement moins cher :**

- **La latence s'effondre.** whisper était le terme dominant du budget (2 s sur
  Pi 5, 3 s sur Pi 4). Sur un PC, même sans GPU, c'est 0,3 à 0,5 s. Le premier
  son passe d'environ 4,5 s à environ 1,5 s. C'est un objet différent.
- **La compréhension monte d'un cran.** Vous pouvez faire tourner `large-v3`
  au lieu de `base`. Or la voix d'un enfant est sous-représentée dans les
  données d'entraînement de whisper : les questions mal comprises sont le
  premier mode d'échec de l'objet, et c'est exactement ce que ce changement
  corrige.
- **Plus de ventilateur.** Le refroidisseur actif du Pi 5 est audible dans une
  chambre. Le Zero 2 W se refroidit passivement, en silence. Pour un objet posé
  sur une table de chevet, ce n'est pas un détail.
- **Boîtier plus petit, 2 W au lieu de 8**, batterie enfin réaliste, pas de
  fentes d'aération à découper.

Ce qu'on perd :

- **Le son brut traverse le réseau local.** Il reste chez vous, sur votre
  machine — mais ce n'est plus « la voix ne quitte jamais la boîte ». Mettez un
  `jeton` partagé dans la configuration : votre réseau domestique héberge aussi
  des objets connectés et des invités.
- **La boîte ne fonctionne plus sans le PC.** Atténué par la voix de secours :
  `tts.secours = "espeak"` fait qu'elle dit toujours quelque chose, même moche,
  plutôt que de rester muette.
- **Le wifi du Zero 2 W est en 2,4 GHz uniquement.** Sans conséquence ici : on
  envoie un WAV complet après le relâchement du bouton (~150 Ko), pas un flux
  continu. C'est précisément pour ça que le protocole est en requête/réponse.

### Le pas d'après, pour information

Si l'on pousse la logique du client léger jusqu'au bout, la carte suivante est
un **ESP32-S3** (~10 €, quelques dizaines de mA). C'est ce que font les objets
commerciaux. Mais on quitte Python pour du firmware C, et ce dépôt ne vous sert
plus à rien : c'est un autre projet, à ne considérer que si vous en fabriquez
plusieurs.

### Recommandation

**Pi Zero 2 W en client léger**, puisque vous avez tranché pour la qualité :
c'est la configuration la moins chère, la plus rapide, la plus silencieuse, et
celle qui comprend le mieux votre enfant. Gardez juste un Pi 4 ou 5 sous la
main si vous voulez pouvoir tester le mode autonome un jour.

---

## 1. Nomenclature

Prix indicatifs TTC, hors frais de port. Convertissez en « ce que vous avez
déjà dans un tiroir » partout où c'est possible.

### Version client léger — ~90 € (recommandée avec un PC dans la maison)

| # | Pièce | Prix |
|---|---|---|
| 1 | Raspberry Pi Zero 2 W (avec header soudé) | 18 € |
| 2 | ReSpeaker 2-Mics Pi HAT v2 | 17 € |
| 3 | Haut-parleur 3 W 4 Ω, ⌀ 50 mm | 5 € |
| 4 | Bouton arcade lumineux 60 mm | 6 € |
| 5 | microSD A2 32 Go | 8 € |
| 6 | Alimentation micro-USB 2,5 A | 8 € |
| 7 | Boîtier contreplaqué 6 mm + visserie | 25 € |

**Total ≈ 87 €**, sans ventilateur, sans SSD, sans dissipateur. Le PC de la
maison fait la transcription, le modèle et la synthèse.

### Version autonome — ~200 €

| # | Pièce | Réf. typique | Prix |
|---|---|---|---|
| 1 | Raspberry Pi 5, 8 Go | — | 80 € |
| 2 | Refroidisseur actif officiel | obligatoire, le Pi 5 throttle sans | 6 € |
| 3 | Alimentation USB-C 27 W officielle | 5 V / 5 A | 14 € |
| 4 | HAT M.2 (PCIe) | Pimoroni NVMe Base / HAT officiel | 15 € |
| 5 | SSD NVMe 2230 ou 2242, 256 Go | — | 20 € |
| 6 | ReSpeaker 2-Mics Pi HAT v2 | 2 micros, bouton, 3 LED RGB, ampli 3 W | 17 € |
| 7 | Haut-parleur 3 W 4 Ω, ⌀ 50 mm | connecteur JST-PH 2,0 | 5 € |
| 8 | Bouton arcade lumineux 60 mm | 5 V, contact NO | 6 € |
| 9 | Boîtier contreplaqué 6 mm | découpe laser, ~150 × 120 × 90 mm | 25 € |
| 10 | Entretoises M2.5, nappe, mousse acoustique | — | 10 € |

**Total ≈ 198 €**

### Version bricolage — ~60 €, avec ce que vous avez déjà

Pour l'étape 1, quand vous voulez juste un objet qui marche ce week-end :
n'importe quelle Pi qui traîne, un micro USB (ou une vieille webcam), une
mini-enceinte, un bouton, et une boîte à chaussures. En mode client léger,
même une Pi 3 fait l'affaire.

## 1 bis. « Et les accélérateurs qu'on branche sur le Pi ? »

C'est la question qu'on se pose tous, et la réponse a changé début 2026.

### Pourquoi la plupart des accélérateurs ne servent à rien ici

La génération de tokens n'est **pas limitée par le calcul**, elle est limitée
par la **bande passante mémoire** : produire un token demande de relire la
totalité des poids du modèle depuis la RAM. Un modèle Q4 de 2,6 Go à 10 Go/s
utiles, ça fait ~4 tokens/seconde, et aucun calcul supplémentaire ne changera
ça. C'est pour cette raison que :

- **Raspberry Pi AI HAT+ (Hailo-8 / 8L, 13 ou 26 TOPS)** — inutile pour ce
  projet. Il exécute des modèles de vision compilés (détection d'objets, pose,
  segmentation). On ne peut pas y charger un Llama. Ses TOPS s'adressent à un
  goulot d'étranglement que nous n'avons pas.
- **Coral USB Accelerator (Edge TPU)** — même verdict, en pire : quelques Mo
  de SRAM, int8, réseaux convolutifs uniquement.

Ajouter des TOPS à un problème de bande passante ne fait rien. C'est la seule
règle à retenir pour trier les accessoires.

### L'exception : le Raspberry Pi AI HAT+ 2 (janvier 2026)

Celui-ci est différent, et il mérite d'être considéré sérieusement. Hailo-10H,
40 TOPS INT4, **8 Go de LPDDR4X qui lui sont propres**, ~130 $.

Le point clé n'est pas les TOPS, c'est la RAM embarquée : les poids résident
sur la carte, et ne traversent donc jamais le lien PCIe x1 du Pi. C'est
exactement le goulot d'étranglement décrit plus haut, contourné.

Chiffres rapportés (à confirmer, ils viennent de tests tiers) :

| Modèle | AI HAT+ 2 | Pi 5 CPU seul |
|---|---|---|
| Llama 3.2 1B | 30-50 tok/s | ~14 tok/s |
| Qwen2.5 1.5B | 20-35 tok/s | ~10 tok/s |
| Llama 3.1 8B (HEF natif, expérimental) | ~11 tok/s | ~2 tok/s |

Trois réserves avant de sortir la carte bleue :

1. **Le modèle doit être compilé pour le Hailo** (format HEF). Les modèles
   passés par une conversion GGUF communautaire tombent à ~2,6 tok/s sur un 3B,
   soit *moins bien que le CPU du Pi*. Le gain dépend entièrement de la
   disponibilité d'un HEF natif pour le modèle que vous voulez.
2. **Le catalogue est étroit.** Celui livré par Raspberry Pi tourne autour de
   1 à 1,5B ; le catalogue Hailo va jusqu'à 3B/3,8B, et le 8B est marqué
   expérimental. Un compilateur communautaire existe pour vos propres modèles.
   Vérifiez ce qui est réellement disponible **en français** avant d'acheter.
3. **Le KV cache mange les 8 Go.** Avec un modèle de 8B en INT4 (~5,2 Go), il
   reste de quoi tenir environ 2k tokens de contexte. Sans importance ici
   (prompt court, pas de mémoire entre les questions), rédhibitoire pour
   d'autres usages.

**Verdict pour ce projet :** c'est la première fois qu'un bon modèle *dans la
boîte* devient plausible. À 130 $, la carte coûte le prix d'un mini-PC
d'occasion qui ferait tourner un 14B plus vite — mais elle tient dans la boîte
et consomme quelques watts. Si l'autonomie totale compte plus que la qualité
maximale, c'est le bon achat.

Bonne nouvelle : **rien à changer dans le code.** `hailo-ollama` expose
`/v1/chat/completions`, donc il suffit de pointer `llm.local.url` dessus
(port 8000 ou 11434 selon l'installation) et de mettre `chemin_sante = "/"`,
puisque ce serveur ne connaît pas `/health`. Vous pouvez donc démarrer sans la
carte et l'ajouter plus tard sans rien réécrire.

### Si vous voulez vraiment un bon modèle *dans* la boîte

| Option | Modèle utilisable | Vitesse | Prix | Remarque |
|---|---|---|---|---|
| Raspberry Pi 5 16 Go | 4B Q4 | ~4-5 tok/s | 130 € | à la limite du confort |
| Pi 5 + AI HAT+ 2 (Hailo-10H) | 1,5B à 8B INT4 | 11-35 tok/s | +120 € | voir §1 bis : dépend d'un HEF natif |
| Radxa Rock 5B+ / Orange Pi 5 Plus (RK3588) | 4B à 8B Q4 | ~8-10 tok/s | 130 € | 2× la bande passante mémoire du Pi 5, NPU 6 TOPS via RKLLM, mais logiciel plus capricieux |
| Jetson Orin Nano Super 8 Go | 8B Q4 | 25-40 tok/s | 250 € | vrai GPU, 102 Go/s ; 15-25 W et un dissipateur qui prend de la place |
| **Un mini-PC dans un placard** | 14B à 30B | 30-60 tok/s | 0 à 300 € | la boîte devient un client LAN — voir README §1 |

La génération de tokens est limitée par la **bande passante mémoire**, pas par
le CPU : un modèle Q4 de 2,6 Go a besoin de lire ses 2,6 Go à chaque token.
Le Pi 5 plafonne autour de 10-12 Go/s utiles, d'où les ~4 tok/s sur un 4B.
C'est la seule règle à retenir pour arbitrer entre deux cartes.

---

## 2. Câblage

### Avec le ReSpeaker 2-Mics HAT (recommandé)

Le HAT s'empile sur le Pi et apporte déjà tout l'audio. Il occupe :

| Signal | Broche | Utilisé par |
|---|---|---|
| I2S (audio) | GPIO18, 19, 20, 21 | codec WM8960 |
| I2C (config codec) | GPIO2, GPIO3 | codec |
| Bouton embarqué | **GPIO17** | bouton poussoir du HAT |
| LED APA102 ×3 | GPIO5 (data), GPIO6 (clock), GPIO13 | anneau RGB |

Il ne reste plus qu'à câbler le gros bouton arcade :

```
  Bouton arcade, contact NO
     borne 1 ──────────────── GPIO17 (broche physique 11)
     borne 2 ──────────────── GND    (broche physique 9)
```

En parallèle du bouton du HAT : les deux fonctionnent, ce qui est pratique pour
tester sans ouvrir la boîte. `gpiozero` active la résistance de tirage interne,
aucun composant externe n'est nécessaire.

Pour la **LED du bouton arcade** (typiquement 20-30 mA, au-delà des 16 mA que
tolère une broche GPIO), passez par un transistor :

```
  GPIO22 ──[ 1 kΩ ]── base   2N2222 / BC547
                      émetteur ── GND
                      collecteur ── cathode LED
  LED anode ──[ 220 Ω ]── 5 V
```

et mettez `leds.broche = 22` dans la configuration. Les LED RGB du HAT sont en
SPI (APA102) et ne sont pas pilotées par ce dépôt : `bouton.Leds` s'adresse à
une LED simple en PWM. C'est volontaire — un seul point lumineux, quatre états,
c'est plus lisible pour un enfant qu'un anneau arc-en-ciel.

### Sans HAT (micro USB + enceinte)

Rien à souder. Le bouton se câble entre n'importe quelle broche BCM libre et la
masse (`bouton.broche = 17` par défaut), et vous listez vos périphériques audio
avec `python -m kidobot --diagnostic` pour remplir `audio.peripherique_entree`.

---

## 3. Acoustique et boîtier

Trois erreurs coûtent cher, et aucune ne se voit sur un schéma :

1. **Le micro entend le haut-parleur.** Mettez-les sur deux faces opposées, et
   posez le micro sur de la mousse ou du joint adhésif : la vibration se
   transmet par le bois bien plus que par l'air. En appui-pour-parler le
   problème est limité (on n'écoute pas pendant qu'on parle), mais si vous
   ajoutez un jour l'interruption à la voix, ça devient bloquant.
2. **Un haut-parleur nu sonne comme un téléphone.** Il lui faut un volume
   d'air fermé derrière. Une boîte étanche de 100 × 80 × 60 mm derrière le
   haut-parleur suffit à récupérer des graves — et l'intelligibilité avec.
3. **Le Pi 5 chauffe.** Le refroidisseur actif a besoin d'entrée et de sortie
   d'air. Des fentes en bas d'une face et en haut de la face opposée.

Dimensions qui marchent : **150 × 120 × 90 mm**. Assez grand pour le Pi + HAT
posés à plat, assez petit pour être porté par un enfant de 7 ans. Le bouton en
haut, au centre, incliné de 10° vers l'avant. Le micro sur la face avant, le
haut-parleur sur la face arrière ou en dessous.

**Un potentiomètre de volume physique** (ou juste deux positions) évite la
question du volume dans les réglages et protège les oreilles. Limitez le gain
maximal côté logiciel aussi (`alsamixer`, puis `sudo alsactl store`).

---

## 4. Alimentation

Restez sur secteur. Un Pi 5 qui infère consomme 6 à 9 W, une batterie
20 000 mAh tient 4 à 6 heures et il faut une sortie USB-C PD capable de
5 V / 5 A — pour un objet posé sur une table de chevet, le câble est plus
simple et plus fiable.

Si l'objet doit être nomade : batterie USB-C PD 20 000 mAh, et acceptez le
5 V / 3 A avec `usb_max_current_enable=1` dans `/boot/firmware/config.txt`
(le Pi bride alors les ports USB, ce qui est sans conséquence ici).

**Prévoyez un arrêt propre.** Une coupure brutale finit par corrompre le
système de fichiers. Le plus simple : un interrupteur relié à une broche GPIO
qui déclenche `sudo shutdown -h now`, avec un son de « bonne nuit ».

---

## 5. Démarrage

Le Pi 5 met ~20 s à démarrer, plus 5 à 25 s pour charger le modèle selon le
support (NVMe vs microSD). Deux options :

- **La boîte reste allumée** (2-3 W au repos, ~5 €/an). C'est ce que fait le
  service systemd fourni, et c'est ce qu'attend un enfant d'un objet.
- **Un son de réveil** joué par `kidobot.service` une fois tout prêt, pour que
  l'appui sur le bouton pendant le démarrage ne passe pas pour une panne.
