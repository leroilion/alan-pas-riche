# D&D Session Extractor

## Installation

Python 3.11 ou 3.12 est conseillé.

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

## Utilisation

Place la vidéo dans le dossier courant, c'est-à-dire le dossier depuis lequel
la commande est exécutée, puis indique simplement son nom :

```bat
python main.py "2026-09-29 19-01-48.mkv"
```

Le nom du fichier permet de déterminer automatiquement la date `2026-09-29`.
Les résultats sont écrits dans :

```text
C:\Users\CheynetJeremy\Documents\personnel\pdf\alan_pas_riche\sessions\2026-09-29
```

Résultats :

```text
2026-09-29\
  transcription.txt
  transcription_timestamped.txt
  transcription.json
  screenshots.txt
  screenshots.json
  screenshots\
    00h00m00s.jpg
    ...
```

Un chemin absolu ou relatif peut également être fourni si la vidéo se trouve
dans un sous-dossier :

```bat
python main.py ".\videos\2026-09-29 19-01-48.mkv"
```

## Modes

Screenshots seulement :

```bat
python main.py "2026-09-29 19-01-48.mkv" --screenshots-only
```

Transcription seulement :

```bat
python main.py "2026-09-29 19-01-48.mkv" --transcription-only
```

## Détection des images

Les paramètres sont regroupés en haut de `main.py`.

- `CHANGE_THRESHOLD` : diminuer cette valeur si certains changements ne sont
  pas détectés.
- `STABLE_THRESHOLD` : tolérance utilisée pendant la stabilisation de la
  nouvelle scène.
- `STABLE_FOR_SECONDS` : durée pendant laquelle la nouvelle scène doit rester
  stable.
- `MIN_SECONDS_BETWEEN_SHOTS` : délai minimal entre deux captures.
- `DETECTION_ROI` : permet de ne surveiller que la zone Roll20 et d'ignorer les
  webcams ou le chat.

Par défaut, la vidéo entière est surveillée.
