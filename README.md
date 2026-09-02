# Kidobot

Une boîte en bois. Un gros bouton. L'enfant appuie, pose sa question, la boîte
répond à voix haute. Pas d'écran, pas de mot-réveil, pas de compte à créer.

```
   ┌───────────────────┐
   │                   │   1. l'enfant appuie et garde le doigt dessus
   │       ( ● )       │   2. il parle
   │                   │   3. il lâche → la boîte réfléchit (LED qui pulse)
   │   ▒▒▒▒▒▒▒▒▒▒▒▒    │   4. elle répond en 60 mots maximum
   └───────────────────┘
```

---

## 1. La stratégie, en trois décisions

### Décision 1 — Ne construisez pas la boîte en premier

Le risque de ce projet n'est pas technique, il est produit : personne ne sait
si votre enfant utilisera l'objet plus de trois jours. Le prompt, la longueur
des réponses et le ton comptent dix fois plus que le boîtier.

D'où un chemin en quatre étapes, chacune utilisable telle quelle :

| Étape | Ce que vous faites | Durée | Coût |
|---|---|---|---|
| **0. Le carton** | Portable + micro USB, la touche Entrée fait office de bouton. `kidobot --factice` | une soirée | 0 € |
| **1. L'objet** | Raspberry Pi + bouton + haut-parleur, LLM par wifi | 2 week-ends | ~200 € |
| **2. L'autonomie** | Le modèle descend dans la boîte, ça marche sans internet | 1 week-end | 0 € |
| **3. La finition** | Boîtier bois, démarrage automatique, journal parental | 1 week-end | ~30 € |

L'étape 0 se fait avec ce dépôt sans acheter quoi que ce soit. Faites-la avant
de commander un seul composant : c'est là que vous découvrirez que les réponses
sont trop longues, que le modèle dit « bonne question ! » à chaque fois, et que
votre enfant demande surtout des blagues sur les pets.

### Décision 2 — « Local » a trois sens, choisissez le bon

C'est le vrai arbitrage du projet, et il est plus ouvert qu'il n'y paraît.

| | **Dans la boîte** (Pi 5) | **Dans la maison** (LAN) | **Wifi + API** |
|---|---|---|---|
| Modèle réaliste | 1,7B à 4B quantifié | 8B à 30B | frontière |
| Vitesse de génération | 4 à 12 tok/s | 30 à 60 tok/s | 50+ tok/s |
| Qualité des réponses | passable, se trompe | bonne | excellente |
| Marche sans internet | ✅ | ✅ (sans box internet) | ❌ |
| Données qui sortent | rien | rien | le texte transcrit |
| Coût | 0 €/question | 0 €/question | ~0,3 c€/question |
| Matériel en plus | — | un mini-PC ou le PC du salon | — |

À quoi s'ajoute, depuis janvier 2026, une quatrième voie : le **Raspberry Pi
AI HAT+ 2** (Hailo-10H, 8 Go de RAM dédiée, ~130 $) fait tourner des modèles
de 1,5B à 8B dans la boîte, à 11-35 tok/s. C'est la première fois qu'un bon
modèle embarqué devient plausible — avec des réserves sérieuses sur le
catalogue de modèles disponibles, détaillées dans
[docs/hardware.md §1 bis](docs/hardware.md). Attention : l'**ancien** AI HAT+
(Hailo-8/8L) ne sait pas faire tourner de LLM du tout, c'est un accélérateur
de vision.

**La colonne du milieu reste celle qu'on oublie, et c'est souvent la bonne.**
Un vieux PC avec 16 Go de RAM dans un placard, `llama-server` en service, et
la boîte devient un client léger sur le réseau local : la voix de l'enfant ne
sort pas de la maison, les réponses sont bonnes, et la boîte reste à 200 €.
Dans la configuration, il suffit de pointer `llm.local.url` sur l'IP du PC.

Et surtout : **ce n'est pas un choix définitif**. Les trois backends implémentent
la même interface, le mode `auto` essaie le local puis bascule sur l'API si le
local ne répond pas. Vous pouvez commencer par l'API et descendre le modèle dans
la boîte plus tard sans changer une ligne du reste.

### Décision 3 — Le point dur n'est pas la vitesse, c'est la qualité

Contre-intuitif, mais c'est le résultat qui structure toute l'architecture.

Piper (la synthèse vocale) parle à environ **150 mots/minute**, soit ~3,5
tokens/seconde consommés. Dès qu'on découpe la réponse en phrases et qu'on fait
parler la première pendant que le modèle rédige la deuxième, il suffit que le
modèle génère **plus vite que la voix ne parle**. Un Raspberry Pi 5 avec un
modèle 3B quantifié tient ce rythme. Un modèle 4B est à la limite. Autrement
dit : *un Pi 5 est assez rapide.*

Ce qu'un modèle 3B n'est pas, c'est assez **fiable**. Il invente des dates, il
répond à côté sur les questions abstraites, et il est nettement moins bon en
français que le modèle qu'on aurait mis dans le placard. Pour un objet dont
l'usage est d'expliquer le monde à un enfant de 7 ans, c'est ça, le vrai
problème — pas les secondes d'attente.

Le compromis retenu ici : **la transcription reste toujours locale** (la voix
de l'enfant ne quitte jamais la maison, quel que soit le backend), et seul le
texte transcrit peut partir sur le réseau. C'est ce qui rend le mode wifi
acceptable, et c'est facile à expliquer aux deux parents.

---

## 2. L'architecture

```
  bouton ──> micro ──> [ VAD ] ──> whisper (local) ──> texte
                                                        │
                                                   garde-fous
                                                        │
                                    ┌───────────────────┴─────────────┐
                                    │ llama.cpp (boîte ou LAN)        │
                                    │ ou API Claude                   │
                                    └───────────────────┬─────────────┘
                                                        │ flux de tokens
                                              découpage en phrases
                                                        │
                                     piper ──> haut-parleur ──> LED
                                                        │
                                                journal parental
```

Trois choses méritent l'attention dans ce schéma :

1. **Le découpage en phrases** (`securite.decouper_en_phrases`) transforme le
   flux de tokens en phrases complètes et lance la synthèse dès la première.
   C'est ce qui fait passer le délai avant le premier son de ~8 s à ~4 s.
2. **Les garde-fous sont déterministes** (quota, horaires, mots-clés) et
   séparés du prompt. Le prompt gère la nuance, le code gère les règles.
3. **Les réponses de secours ne passent pas par le modèle.** Quand le wifi
   tombe ou que la question est vide, la boîte parle quand même. Un silence,
   dans une chambre d'enfant, se lit comme une panne.

Budget de latence estimé sur Pi 5 pour une question de 5 secondes — ce sont des
ordres de grandeur à confirmer chez vous, `kidobot --diagnostic` et les temps
journalisés vous donneront vos vrais chiffres (détail dans
[docs/architecture.md](docs/architecture.md)) :

| Étape | Dans la boîte | LAN / API |
|---|---|---|
| Transcription (whisper small int8) | 2,0 s | 2,0 s |
| Premier token | 0,3 s | 0,8 s |
| Première phrase générée | 1,7 s | 0,3 s |
| Synthèse de la première phrase | 0,6 s | 0,6 s |
| **Premier son** | **~4,6 s** | **~3,7 s** |

La transcription domine. Si vous voulez gagner une seconde, c'est là qu'il faut
chercher (modèle `base` au lieu de `small`), pas sur le LLM.

---

## 3. Le matériel

Liste complète, câblage et alternatives : **[docs/hardware.md](docs/hardware.md)**.

Version courte, ~200 € :

| Pièce | Prix |
|---|---|
| Raspberry Pi 5 8 Go + refroidisseur actif + alim 27 W | 100 € |
| HAT M.2 + SSD NVMe 256 Go | 35 € |
| ReSpeaker 2-Mics Pi HAT v2 (2 micros, bouton, LED, sortie HP) | 17 € |
| Haut-parleur 3 W 4 Ω | 5 € |
| Gros bouton arcade lumineux 60 mm | 6 € |
| Boîtier (contreplaqué 6 mm découpé laser) + visserie | 30 € |

Le 8 Go suffit largement : un modèle 4B quantifié pèse 2,6 Go. Prenez le 16 Go
seulement si vous voulez tenter un 8B (qui sera trop lent, mais on ne juge pas).

Deux points souvent ratés :
- **Le SSD NVMe n'est pas du luxe.** Charger 2,6 Go de poids depuis une carte
  microSD prend 25 secondes au démarrage, contre 4 sur NVMe.
- **Éloignez le micro du haut-parleur** et découplez-le avec de la mousse,
  sinon la boîte s'entend elle-même.

---

## 4. Démarrer

### Sur votre portable, ce soir (aucun matériel)

```bash
git clone https://github.com/microbiologames/kidobot && cd kidobot
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,cloud]"
cp config/kidobot.example.toml config/kidobot.toml   # mettez le prénom et l'âge

export ANTHROPIC_API_KEY=sk-ant-...
python -m kidobot --texte "pourquoi le ciel est bleu ?"
```

Réglez le prompt (`src/kidobot/prompts.py`) et la longueur des réponses jusqu'à
ce que ça sonne juste. C'est 80 % du travail.

Puis, avec un micro USB :

```bash
pip install -e ".[stt]"
sudo apt install piper-tts espeak-ng
python -m kidobot            # Entrée = bouton
```

### Sur le Raspberry Pi

```bash
./scripts/install_pi.sh      # système, piper, whisper, llama.cpp
./scripts/fetch_models.sh    # voix française + modèle LLM
python -m kidobot --diagnostic
sudo cp systemd/*.service /etc/systemd/system/
sudo systemctl enable --now llama-server kidobot
```

`--diagnostic` teste chaque brique séparément (micro, transcription, LLM local,
LLM distant, voix) et dit laquelle est cassée. C'est la première commande à
lancer quand la boîte ne répond plus.

---

## 5. Ce que le code contient

```
src/kidobot/
  app.py         machine à états + pipeline LLM→phrases→voix
  prompts.py     le prompt système  ← le fichier le plus important du dépôt
  securite.py    quotas, horaires, filtre, nettoyage pour la voix
  llm.py         llama.cpp (HTTP) | API Claude | bascule automatique
  stt.py         faster-whisper (toujours local)
  tts.py         piper
  audio.py       capture + VAD + lecture interruptible + bips
  bouton.py      GPIO / clavier, et les quatre états de la LED
  journal.py     journal parental en JSONL
```

Toutes les briques matérielles ont un double factice, donc `pytest` déroule un
tour complet sans micro, sans GPIO et sans réseau.

---

## 6. Concevoir pour un enfant, pas pour soi

Ces choix-là ne sont pas techniques mais ce sont eux qui décident si l'objet
reste dans la chambre :

- **Appui pour parler, pas de mot-réveil.** Le micro n'est actif que pendant
  l'appui. C'est plus simple à comprendre, ça supprime les déclenchements
  fantômes, et ça enseigne au passage que parler à une machine est un acte
  volontaire. Un interrupteur physique sur la ligne du micro rend cette
  promesse vérifiable.
- **60 mots maximum, une seule idée.** Au-delà, l'enfant décroche et vous
  attendez la fin pour reposer une question.
- **« Je ne sais pas » est une fonctionnalité.** Le prompt demande explicitement
  au modèle de le dire et de proposer de chercher avec un adulte.
- **Un quota quotidien.** 40 questions par jour, ensuite la boîte dit qu'elle
  est fatiguée. La rareté entretient la magie ; l'illimité produit une machine
  à bruit de fond.
- **Le journal parental se lit *avec* l'enfant.** Toutes les questions et
  réponses sont en clair dans `journal/`. C'est autant un outil de surveillance
  qu'un sujet de conversation au dîner.
- **La boîte dit qu'elle est une machine** si on le lui demande. Pas d'ami
  imaginaire.

Détails et limites de ces garde-fous : [docs/securite.md](docs/securite.md).

---

## Licence

MIT. Faites-en ce que vous voulez, y compris un cadeau d'anniversaire.
