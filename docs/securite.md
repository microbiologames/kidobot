# Garde-fous

Un objet qui écoute un enfant et lui répond seul mérite qu'on écrive noir sur
blanc ce qu'il fait, ce qu'il ne fait pas, et où sont ses limites.

## 1. Ce qui protège quoi

| Risque | Ce qui le couvre | Où |
|---|---|---|
| Écoute permanente | appui-pour-parler : le micro n'est ouvert que pendant l'appui | `app.un_tour` |
| Fuite de la voix | la transcription est **toujours** locale ; seul le texte peut sortir | `stt.py` |
| Sujets d'adulte | filtre déterministe → renvoi vers un parent, sans appeler le modèle | `securite.Gardien.verifier_question` |
| Réponses inadaptées | prompt système explicite (violence, sexe, mort, santé mentale, armes) | `prompts.py` |
| Réponses trop longues | limite dure en mots, appliquée après le modèle | `securite.nettoyer_pour_la_voix` |
| Usage compulsif | quota quotidien + plage horaire | `Gardien.verifier_quota` / `verifier_horaire` |
| Opacité pour les parents | journal en clair, une ligne par échange | `journal.py` |
| Attachement affectif | le prompt impose de dire que c'est une machine | `prompts.py` |

## 2. Le filtre de mots-clés est volontairement étroit

`securite.MOTS_ADULTE` contient une trentaine d'expressions, pas trois cents.
C'est délibéré : un filtre large casse l'objet.

« Pourquoi les gens meurent ? », « comment on fait les bébés ? », « c'est quoi
la guerre ? » sont des questions d'enfant parfaitement normales et **doivent
recevoir une réponse**. Une boîte qui répond « demande à un adulte » à une
question sur trois est une boîte qu'on débranche.

Le filtre déterministe ne sert donc qu'aux cas où l'on veut être certain de ne
pas laisser le modèle improviser : automutilation, contenu sexuel explicite,
drogues, fabrication d'armes. Toute la nuance est confiée au prompt, qui est
bien meilleur que des mots-clés pour ça — et c'est aussi pour ça que la qualité
du modèle compte (voir README §1, décision 3).

Les tests `tests/test_securite.py` verrouillent les deux directions : que les
questions sensibles soient renvoyées, et que les questions légitimes passent.

## 3. Le journal parental

`journal/AAAA-MM-JJ.jsonl`, une ligne par échange :

```json
{"horodatage":"2026-09-02T18:41:03","question":"pourquoi le ciel est bleu ?",
 "reponse":"Parce que la lumière du soleil...","backend":"local","duree_s":4.8}
```

Deux usages, et le second est le plus important :

1. Savoir ce que la boîte a raconté (et corriger le prompt quand elle raconte
   n'importe quoi).
2. **Se rendre compte de ce qui préoccupe votre enfant.** Les questions posées
   à une machine ne sont pas celles qu'on pose à ses parents. C'est la partie
   du projet dont on parle le moins et qui vaut le plus.

Dites-lui que ça existe. Un objet qui enregistre en cachette dans une chambre
d'enfant, c'est exactement ce qu'on essaie de ne pas construire.

## 4. Ce qui sort de la maison, précisément

| Backend | Audio | Texte de la question | Réponse |
|---|---|---|---|
| `local` (boîte) | reste | reste | reste |
| `local` (LAN) | reste | reste sur le réseau local | reste |
| `claude` | **reste** | part vers l'API Anthropic | revient |

Aucun enregistrement audio n'est conservé sur disque, ni envoyé nulle part :
le tableau `numpy` est transcrit puis abandonné.

En mode `claude`, ce qui part est une phrase de texte, sans identifiant, sans
prénom (le prénom est dans le prompt système, pas dans la question — si cela
vous gêne, retirez-le de `prompts.py`). Les données envoyées à l'API Anthropic
ne servent pas à entraîner les modèles par défaut, mais elles transitent et
sont conservées un temps côté fournisseur : c'est exactement la différence que
le mode LAN permet d'éliminer.

## 5. Les limites, honnêtement

- **Un modèle se trompe.** Aucun garde-fou ici n'empêche une réponse fausse.
  Un modèle 3B local se trompera régulièrement sur les dates, les nombres et
  les questions scientifiques précises. Le prompt demande d'admettre le doute,
  ce qui aide, mais ne le garantit pas. C'est l'argument principal en faveur
  d'un bon modèle (placard ou API) plutôt que d'un petit modèle embarqué.
- **La transcription se trompe aussi**, surtout sur une voix d'enfant, qui est
  sous-représentée dans les données d'entraînement de whisper. Attendez-vous à
  des questions mal comprises. `stt.small` est nettement meilleur que `base`
  sur ce point, et c'est pour ça qu'il est le défaut malgré sa lenteur.
- **Le filtre est contournable** par un enfant curieux qui reformule. C'est
  inévitable ; la réponse n'est pas un filtre plus gros mais le journal et la
  conversation qui suit.
- **Ce n'est pas un jouet certifié.** Pas de CE, pas de test de chute, une
  batterie lithium si vous en mettez une. Objet de maison, sous supervision.
