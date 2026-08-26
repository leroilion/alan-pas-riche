#!/usr/bin/env python3
r"""
Prépare une source LaTeX temporaire pour Pandoc.

Le script :
- développe récursivement les \input{} et \include{} ;
- extrait uniquement le contenu compris entre \begin{document} et \end{document} ;
- convertit les macros spécifiques au livre de Kael vers du LaTeX standard ;
- résout les chemins des illustrations par nom de fichier ;
- supprime les éléments propres à la pagination PDF ;
- simplifie les références internes pour l'EPUB.

Il ne modifie jamais les sources du projet. Le Makefile écrit la sortie dans
.epub-build/ puis supprime ce répertoire après la génération de l'EPUB.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


INPUT_RE = re.compile(r"\\(?:input|include)\s*\{([^{}]+)\}")

ILLUSTRATION_RE = re.compile(
    r"""\\illustration
        (?:\s*\[(?P<width>[^\]]*)\])?
        \s*\{(?P<file>[^{}]+)\}
        \s*\{(?P<caption>[^{}]*)\}
        \s*\{(?P<id>[^{}]*)\}
    """,
    re.VERBOSE | re.DOTALL,
)

BEGIN_DOCUMENT = r"\begin{document}"
END_DOCUMENT = r"\end{document}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def resolve_tex_file(base_dir: Path, name: str) -> Path | None:
    candidate = Path(name)

    if candidate.suffix == "":
        candidate = candidate.with_suffix(".tex")

    if candidate.is_absolute():
        return candidate if candidate.exists() else None

    direct = (base_dir / candidate).resolve()
    if direct.exists():
        return direct

    project_relative = (Path.cwd() / candidate).resolve()
    if project_relative.exists():
        return project_relative

    return None


def expand_inputs(
    text: str,
    current_dir: Path,
    stack: tuple[Path, ...] = (),
) -> str:
    r"""Développe récursivement les \input et \include existants."""

    def replace(match: re.Match[str]) -> str:
        name = match.group(1).strip()
        target = resolve_tex_file(current_dir, name)

        if target is None:
            print(
                f"[epub] avertissement: fichier inclus introuvable: {name}",
                file=sys.stderr,
            )
            return match.group(0)

        target = target.resolve()

        if target in stack:
            chain = " -> ".join(str(p) for p in (*stack, target))
            raise RuntimeError(
                f"Inclusion LaTeX récursive détectée: {chain}"
            )

        expanded = read_text(target)
        return expand_inputs(
            expanded,
            target.parent,
            (*stack, target),
        )

    previous = None

    while previous != text:
        previous = text
        text = INPUT_RE.sub(replace, text)

    return text


def extract_document_body(text: str) -> str:
    start = text.find(BEGIN_DOCUMENT)
    end = text.rfind(END_DOCUMENT)

    if start == -1 or end == -1 or end <= start:
        return text

    return text[start + len(BEGIN_DOCUMENT):end]


def find_image(file_name: str, project_root: Path) -> str:
    """Résout une illustration fournie uniquement par son nom de fichier."""

    requested = Path(file_name.strip())

    if requested.exists():
        return requested.as_posix()

    direct = project_root / requested
    if direct.exists():
        return direct.relative_to(project_root).as_posix()

    ignored = {
        ".git",
        ".epub-build",
        "_site",
    }

    matches: list[Path] = []

    for path in project_root.rglob(requested.name):
        if any(part in ignored for part in path.parts):
            continue

        if path.is_file():
            matches.append(path)

    if not matches:
        print(
            f"[epub] avertissement: illustration introuvable: {file_name}",
            file=sys.stderr,
        )
        return file_name.strip()

    matches.sort(
        key=lambda p: (
            len(p.parts),
            p.as_posix(),
        )
    )

    return matches[0].relative_to(project_root).as_posix()


def convert_illustrations(text: str, project_root: Path) -> str:
    def replace(match: re.Match[str]) -> str:
        image = find_image(
            match.group("file"),
            project_root,
        )
        caption = match.group("caption").strip()
        label = match.group("id").strip()

        parts = [
            r"\begin{figure}",
            r"\centering",
            rf"\includegraphics{{{image}}}",
        ]

        if caption:
            parts.append(
                rf"\caption{{{caption}}}"
            )

        if label:
            parts.append(
                rf"\label{{{label}}}"
            )

        parts.append(
            r"\end{figure}"
        )

        return "\n".join(parts)

    return ILLUSTRATION_RE.sub(
        replace,
        text,
    )


def simplify_page_references(text: str) -> str:
    r"""
    Supprime les références à des numéros de page fixes.

    Exemple :

        \hyperref[chap:resume-personnage]{Résumé du personnage},
        page~\pageref{chap:resume-personnage}

    devient :

        \hyperref[chap:resume-personnage]{Résumé du personnage}

    Dans un EPUB reflowable, un numéro de page n'a pas de sens.
    """

    # Cas principal :
    # \hyperref[label]{texte}, page~\pageref{label}
    #
    # On conserve uniquement l'hyperref.
    same_target_pattern = re.compile(
        r"""
        (?P<link>
            \\hyperref
            \[
                (?P<label>[^\]]+)
            \]
            \{
                (?P<text>[^{}]+)
            \}
        )
        \s*
        [,;:]?
        \s*
        (?:[Pp]age)
        \s*~?\s*
        \\pageref
        \{
            (?P=label)
        \}
        """,
        re.VERBOSE,
    )

    text = same_target_pattern.sub(
        lambda match: match.group("link"),
        text,
    )

    # Cas où on trouve simplement :
    # page~\pageref{...}
    #
    # On supprime tout le morceau.
    text = re.sub(
        r"""
        (?:[Pp]age)
        \s*~?\s*
        \\pageref
        \{
            [^{}]+
        \}
        """,
        "",
        text,
        flags=re.VERBOSE,
    )

    # Dernière sécurité :
    # un \pageref isolé n'a de toute façon aucun intérêt en EPUB.
    text = re.sub(
        r"""
        \\pageref
        \{
            [^{}]+
        \}
        """,
        "",
        text,
        flags=re.VERBOSE,
    )

    # Nettoyage d'éventuels espaces laissés avant une ponctuation.
    text = re.sub(
        r"[ \t]+([,.;:!?])",
        r"\1",
        text,
    )

    return text


def normalize_for_epub(
    text: str,
    project_root: Path,
) -> str:
    text = convert_illustrations(
        text,
        project_root,
    )

    # Ruptures narratives.
    text = text.replace(
        r"\scenebreak",
        "\n\n\\begin{center}* * *\\end{center}\n\n",
    )

    text = text.replace(
        r"\referencebreak",
        "\n\n\\begin{center}* * *\\end{center}\n\n",
    )

    # Pandoc génère lui-même la table des matières.
    text = re.sub(
        r"\\tableofcontents\b",
        "",
        text,
    )

    text = re.sub(
        r"\\maketitle\b",
        "",
        text,
    )

    # Les sauts de page n'ont pas de sens dans un EPUB reflowable.
    text = re.sub(
        r"\\(?:newpage|clearpage|pagebreak)\b",
        "",
        text,
    )

    # Suppression / simplification des références de pages.
    text = simplify_page_references(
        text,
    )

    # Nettoyage léger des séries de lignes vides.
    text = re.sub(
        r"\n{4,}",
        "\n\n\n",
        text,
    )

    return text.strip() + "\n"


def main() -> int:
    args = parse_args()

    input_path = args.input.resolve()
    output_path = args.output.resolve()
    project_root = Path.cwd().resolve()

    if not input_path.exists():
        print(
            f"[epub] erreur: source introuvable: {input_path}",
            file=sys.stderr,
        )
        return 2

    text = read_text(
        input_path,
    )

    text = expand_inputs(
        text,
        input_path.parent,
        (input_path,),
    )

    text = extract_document_body(
        text,
    )

    text = normalize_for_epub(
        text,
        project_root,
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        text,
        encoding="utf-8",
    )

    print(
        f"[epub] source Pandoc temporaire: {output_path}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
