# Règles d'écriture du récit

Ce fichier décrit **comment** écrire les chapitres d'« Alan pas riche ».

Il est destiné aussi bien à un humain qu'à une IA (Claude, ChatGPT, autre). Pour
faire enrichir un chapitre par une IA, coller ce fichier entier dans la
conversation avant de donner les notes de session.

## 1. Fidélité

Le récit reste fidèle à ce qui s'est joué autour de la table.

La mise en roman ajoute les descriptions, les transitions, les perceptions et
les pensées nécessaires à la narration. Elle ne réécrit pas les décisions des
joueurs et n'invente pas de conséquences qui n'ont pas eu lieu.

## 2. Ne jamais devancer ce que les personnages savent

Un nom, un lien de parenté, une appartenance, une intention : rien n'entre dans
le texte tant que les personnages ne l'ont pas appris à la table.

Cela vaut particulièrement pour le lore officiel des Royaumes Oubliés. Connaître
un détail canonique ne donne pas le droit de l'écrire : si le MJ ne l'a pas
énoncé, il n'existe pas encore dans le récit.

Exemples :

- « le fils de Neverember » — correct, le nom de famille a été retenu à la table
- « le fils de Dagult Neverember » — incorrect, le prénom du père n'a pas été retenu
- « Renaer Neverember » — incorrect, le prénom du fils n'a jamais été prononcé
- « une elfe » — correct
- « Lyra Sunstricke » — incorrect tant que le groupe ne connaît pas son nom

Le narrateur peut poser une question. Il ne donne pas la réponse à l'avance.

## 3. Le rythme : blocs et lignes isolées

C'est la règle la plus importante pour le confort de lecture.

### Les blocs

La narration — description, action, contexte, explication — se regroupe en
**blocs de 3 à 6 phrases**, soit 250 à 400 caractères environ.

Un enchaînement de paragraphes d'une seule phrase se lit à plat : tout a le même
poids, l'œil n'a plus de repère.

### Les lignes isolées

Une ligne seule est un **effet**, pas une mise en page. Elle est réservée à :

- une bascule : *« Une immense faille s'ouvrait devant eux. »*
- une chute : *« il fallait sortir de cette cellule. »*
- une réplique ou un gag : *« On ne gâche pas. »*
- un silence avant un pic d'action

### Le test de la transition

Avant d'isoler une ligne, se demander : **fonctionne-t-elle contre ce qui
précède, ou annonce-t-elle ce qui suit ?**

Si elle annonce ce qui suit, ce n'est pas une chute mais une transition. Sa place
est en tête du bloc suivant, pas sur sa propre ligne.

```
❌  La discussion ne tarda pas à devenir délicate.

    Il comprit rapidement qu'il avait devant lui quatre des prisonniers...

✅  La discussion ne tarda pas à devenir délicate. Il comprit rapidement
    qu'il avait devant lui quatre des prisonniers...
```

### Enchaînements

Deux lignes isolées à la suite forment un duo — c'est souvent là que se joue la
blague ou le retournement :

```
Morrÿs n'eut pas le temps de réagir.

La créature non plus.
```

Au-delà de trois, l'effet se dilue. Seuls les pics d'action le justifient.

## 4. Les commandes du livre

Il existe une commande pour chaque besoin. Ne pas les contourner à la main.

| Besoin | Commande | À ne pas faire |
| --- | --- | --- |
| En-tête de session | `\sessioninfo{Session}{Date}` | un `center` + `textit` écrit à la main |
| Rupture de scène | `\scenebreak` | `\bigskip`, `\vspace`, ou des lignes vides |
| Aparté méta / private joke | `\begin{narrateur}` | des parenthèses dans le récit |
| Réplique mise en avant | `\begin{quote}\itshape` | des guillemets seuls |
| Illustration | `\illustration[largeur]{fichier}{légende}{id}` | `includegraphics` direct |

Attention : plusieurs lignes vides consécutives ne produisent **rien** de plus
qu'une seule dans le PDF. Pour créer un espace, c'est `\scenebreak`.

## 5. Ce que la mise en page ne doit pas faire

La typographie du livre est celle d'un roman : alinéa en début de paragraphe,
pas d'espace entre les paragraphes. C'est volontaire.

Si un chapitre paraît étouffant, le problème vient des paragraphes trop courts,
pas de l'espacement. On corrige le texte, pas `config.tex`.
