# Architecture

## 1. La machine à états

```
                appui                relâchement
     repos ─────────────> écoute ─────────────────> transcription
       ▲                    │                             │
       │                    │ (15 s max)                  │ vide / sensible
       │                    ▼                             ▼
       │                 troncature ──────────────> réponse fixe
       │                                                  │
       └──────────── parole <──── réflexion <─────────────┘
```

Chaque état a une signature **sonore** et **lumineuse**, parce qu'il n'y a pas
d'écran et qu'un enfant de 7 ans ne lit pas un log :

| État | LED | Son |
|---|---|---|
| repos | veilleuse 5 % | — |
| écoute | allumée fixe | bip aigu 880 Hz |
| réflexion | pulsation lente | bip grave discret |
| parole | clignotement doux | la réponse |
| erreur | 3 clignotements | bip bas 300 Hz |

L'implémentation est dans `app.Kidobot.un_tour()` — une fonction, lisible de
haut en bas, sans framework.

## 2. Le pipeline LLM → phrases → voix

C'est l'optimisation qui compte. Naïvement :

```
[========== génération 90 tokens ==========][== synthèse ==][== parole ==]
                     20 s                          6 s          24 s
```

En pipeline (`app._repondre_et_parler`) :

```
[= p1 =][= p2 =][= p3 =] ...            génération
        [tts1][tts2][tts3]              synthèse
             [==== parole continue ====]
```

Deux fils d'exécution : un producteur qui consomme le flux de tokens du LLM et
pousse les phrases complètes dans une `queue`, et le fil principal qui dépile,
synthétise et joue. Le premier son sort dès que la première phrase est prête.

La conséquence contre-intuitive : **la vitesse de génération n'a besoin d'être
que légèrement supérieure au débit de parole.** Piper parle à ~150 mots/minute,
soit ~3,5 tokens/seconde consommés. Un modèle qui génère à 5 tok/s ne fera
jamais attendre l'enfant après la première phrase. Un modèle qui génère à
50 tok/s ne fera pas parler la boîte plus vite — il réduira juste le délai
avant le premier mot, et de moins d'une seconde.

C'est ce qui rend un Raspberry Pi 5 viable là où l'intuition dit le contraire.

## 3. Budget de latence

Ordres de grandeur pour une question de 5 secondes. À vérifier chez vous : les
durées réelles sont journalisées dans `journal/AAAA-MM-JJ.jsonl`.

| Étape | Pi 5, modèle 3B | LAN / API | Levier |
|---|---|---|---|
| Fin d'appui → audio prêt | 0,05 s | 0,05 s | — |
| whisper `small` int8, 5 s d'audio | 2,0 s | 2,0 s | `base` → 0,8 s |
| Premier token | 0,3 s | 0,8 s (réseau) | prompt court + cache |
| Première phrase (~20 tokens) | 1,7 s | 0,3 s | `max_mots` |
| Piper, première phrase | 0,6 s | 0,6 s | voix `low` → 0,3 s |
| **Premier son** | **~4,6 s** | **~3,7 s** | |

**La transcription domine partout.** Si vous voulez gagner une seconde, changez
`stt.modele` avant de toucher au LLM. Deux optimisations non implémentées ici
mais faciles à ajouter si 4 s vous paraît long :

- transcrire par tranches **pendant** que l'enfant parle, pour que la
  transcription soit finie 200 ms après le relâchement du bouton ;
- pré-synthétiser une amorce (« Alors… ») jouée pendant la réflexion. Efficace
  sur la latence perçue, mais ça rend la boîte bavarde — à tester avec l'enfant
  avant de l'adopter.

## 4. Les backends LLM

`llm.py` expose une seule méthode, `repondre(systeme, question) -> Iterator[str]`.

- **`LlmLocalHttp`** parle à `llama-server` (llama.cpp) en HTTP, API compatible
  OpenAI. Le modèle vit dans un *autre processus*, volontairement : charger
  2,6 Go de poids prend 5 à 25 s, on ne veut le payer qu'au démarrage de la
  machine, pas à chaque redémarrage de l'application. Effet de bord agréable :
  `llm.local.url` peut pointer sur une autre machine du réseau, et le code ne
  fait pas la différence entre « dans la boîte » et « dans le placard ».
- **`LlmClaudeApi`** utilise le SDK Anthropic en streaming, `effort: "low"`
  (la réflexion adaptative reste active mais courte — c'est le bon réglage pour
  du question/réponse enfant, où la latence prime sur la profondeur), et active
  le repli serveur en cas de refus d'un classificateur de sécurité : dans une
  chambre d'enfant, une réponse vide est un bug.
- **`LlmAuto`** essaie le local, et bascule sur l'API si le serveur local ne
  répond pas *ou* échoue sur le premier token. Le premier morceau est
  matérialisé avant d'être transmis, ce qui garantit qu'on ne bascule jamais
  au milieu d'une phrase déjà prononcée.

### Choix du modèle local

| Modèle | Taille Q4_K_M | Pi 5 | Français |
|---|---|---|---|
| Llama 3.2 1B | 0,8 Go | ~14 tok/s | faible |
| Qwen3 1.7B | 1,1 Go | ~10 tok/s | correct |
| Llama 3.2 3B | 2,0 Go | ~6 tok/s | correct |
| Gemma 3 4B | 2,6 Go | ~4 tok/s | bon |

Recommandation : **Gemma 3 4B** si vous voulez la meilleure réponse et acceptez
4 tok/s (rappel : c'est encore au-dessus du débit de parole), **Llama 3.2 3B**
si vous voulez de la marge. En dessous de 1,7B, les réponses factuelles à des
questions d'enfant deviennent trop souvent fausses pour l'usage.

`llm.local` envoie `chat_template_kwargs: {enable_thinking: false}` : les
modèles de la famille Qwen3 raisonnent avant de répondre par défaut, ce qui
double le temps de réponse sans rien apporter ici.

## 5. Ce qui n'est pas là, et pourquoi

- **Pas de mot-réveil.** Un bouton est plus simple, plus privé, et plus juste
  pédagogiquement. Si vous en voulez un quand même : openWakeWord tourne sur
  Pi 5 pour ~15 % d'un cœur.
- **Pas de mémoire entre les questions.** Chaque appui repart de zéro. C'est un
  choix : ça évite les dérives de conversation, ça garde le prompt court (donc
  rapide), et ça correspond à l'usage réel — un enfant pose des questions sans
  rapport les unes avec les autres. Ajouter les 2 derniers échanges est trivial
  (`messages` dans `llm.py`) si vous constatez le besoin.
- **Pas d'outils / recherche web.** Un modèle qui cherche sur le web dans une
  chambre d'enfant est un autre produit, avec d'autres problèmes.
- **Pas d'interruption à la voix.** `HautParleur.interrompre()` existe et coupe
  la lecture en 100 ms ; il suffit de l'appeler sur un nouvel appui. Non câblé
  par défaut pour garder la boucle lisible.
