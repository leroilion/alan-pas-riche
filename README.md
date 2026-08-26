# Alan pas riche

Ce dépôt contient le récit des aventures vécues au cours de la campagne de Donjons & Dragons **Alan pas riche**.

Les événements joués autour de la table sont progressivement transformés en récit romanesque, session après session.

## Lire le récit

La dernière version compilée du récit est disponible sur GitHub Pages :

**[📖 Lire et télécharger « Alan pas riche »](https://leroilion.github.io/alan-pas-riche/)**

Cette page est automatiquement mise à jour après chaque nouvelle compilation réussie sur la branche `main`.

## Principe

Un fichier `.tex` peut représenter :

- une session complète ;
- un événement important méritant son propre chapitre ;
- exceptionnellement plusieurs petites scènes liées entre elles.

Le récit reste fidèle aux événements joués autour de la table. La mise en roman ajoute les descriptions, les transitions, les perceptions et les pensées nécessaires à la narration, sans réécrire les décisions des joueurs ni inventer des conséquences qui n'ont pas eu lieu.

Les règles d'écriture — rythme des paragraphes, ce que les personnages ont le
droit de savoir, commandes à utiliser — sont décrites dans [STYLE.md](STYLE.md).
Ce fichier est prévu pour être collé tel quel dans une conversation avec une IA
chargée d'enrichir un chapitre.

## Structure

```text
alan-pas-riche/
├── .github/
│   └── workflows/
│       └── build-pdf.yml
├── chapter/
│   ├── 0000_preambule.tex
│   ├── 0001_nom_du_chapitre.tex
│   └── ...
├── img/
├── Makefile
├── main.tex
├── config.tex
├── STYLE.md
└── README.md
```

Le fichier `.chapters.generated.tex` est généré automatiquement lors de la compilation et ne doit pas être modifié manuellement.

## Ajouter un chapitre

Créer un fichier dans `chapter/` avec un préfixe numérique sur 4 chiffres :

```text
0002_route_vers_phandalin.tex
0030_nom_evenement.tex
```

Les numéros servent uniquement à déterminer l'ordre d'import des fichiers. Ils peuvent être espacés afin de permettre l'insertion ultérieure d'un événement entre deux chapitres.

Chaque fichier contient son propre titre :

```latex
\chapter{Titre du chapitre}
\sessioninfo{Session 2}{Date ou indication facultative}

Texte du récit...
```

Le second paramètre de `\sessioninfo` peut être laissé vide :

```latex
\sessioninfo{Session 2}{}
```

## Apartés du narrateur

Les remarques qui sortent volontairement du récit peuvent être placées dans un bloc `narrateur`.

```latex
\begin{narrateur}
Texte de l'aparté du narrateur.
\end{narrateur}
```

Ce bloc est destiné notamment aux remarques humoristiques, private jokes ou précisions méta liées à ce qui s'est réellement passé autour de la table.

Il apparaît dans le livre sous la forme d'un encadré discret en italique afin de le distinguer clairement de la narration principale.

## Illustrations

Les images sont placées dans le répertoire `img/`.

Pour ajouter une illustration :

```latex
\illustration[0.75\textwidth]
  {image.png}
  {Légende de l'image.}
  {identifiant-unique}
```

Le premier paramètre, facultatif, définit la largeur de l'image. Par défaut, une illustration occupe `0.85\textwidth`.

Le dernier paramètre doit être un identifiant unique utilisé pour créer le `label` LaTeX.

## Séparation de scènes

Pour marquer une rupture à l'intérieur d'un même chapitre :

```latex
\scenebreak
```

Cela insère une séparation visuelle entre les deux scènes sans créer de nouvelle section ou de nouveau chapitre.

## Compilation

Compiler le livre avec :

```bash
make
```

Le PDF produit est :

```text
aventures.pdf
```

Le Makefile reconstruit automatiquement `.chapters.generated.tex`, puis exécute deux compilations LaTeX afin de mettre à jour le sommaire et les références.

Pour afficher l'ordre dans lequel les chapitres seront intégrés :

```bash
make show-chapters
```

Pour supprimer les fichiers générés :

```bash
make clean
```

## Compilation et publication automatiques

Une GitHub Action compile automatiquement le livre à chaque push sur la branche `main`.

La pipeline :

1. installe TeX Live ;
2. compile `aventures.pdf` ;
3. prépare le site GitHub Pages ;
4. publie la nouvelle version du PDF.

La dernière version publiée du récit est ainsi toujours disponible sur GitHub Pages.

Le lien vers le PDF utilise le SHA du commit courant comme paramètre de version afin d'éviter qu'un navigateur ne conserve une ancienne version du document dans son cache.

## Organisation du récit

Le livre est construit progressivement au fil de la campagne.

Un chapitre peut donc correspondre à une session entière ou, lorsque les événements le justifient, à une partie particulière d'une session.

L'objectif est de conserver une trace fidèle des aventures vécues par les personnages tout en leur donnant la forme d'un véritable récit.