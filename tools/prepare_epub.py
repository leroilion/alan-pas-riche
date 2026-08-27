#!/usr/bin/env python3
r"""
Prépare une source LaTeX temporaire pour Pandoc.

Le script :
- développe récursivement les \input{} et \include{} ;
- extrait le contenu entre \begin{document} et \end{document} ;
- convertit les macros spécifiques au livre vers du LaTeX compris par Pandoc ;
- rend visibles les informations de session ;
- convertit toutes les illustrations, y compris les légendes avec commandes LaTeX imbriquées ;
- peut préparer des copies optimisées des images pour liseuse (redimensionnement,
  niveaux de gris et JPEG) sans modifier les images originales ;
- remplace les références de figures/pagination par un texte adapté à l'EPUB ;
- recrée une table des illustrations sans numéros de page.

Les sources du projet ne sont jamais modifiées. Le Makefile écrit les fichiers
intermédiaires dans .epub-build/ puis supprime ce répertoire après le build.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    from PIL import Image, ImageOps
except ImportError:  # pragma: no cover - message explicite dans le conteneur
    Image = None
    ImageOps = None


INPUT_RE = re.compile(r"\\(?:input|include)\s*\{([^{}]+)\}")
BEGIN_DOCUMENT = r"\begin{document}"
END_DOCUMENT = r"\end{document}"


@dataclass
class Illustration:
    source: str
    caption: str
    short_id: str
    label: str
    converted_source: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prépare le LaTeX de la campagne pour Pandoc/EPUB."
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)

    parser.add_argument(
        "--optimize-images",
        action="store_true",
        help=(
            "Crée des copies JPEG optimisées des illustrations dans le répertoire "
            "temporaire de sortie. Les originaux ne sont jamais modifiés."
        ),
    )
    parser.add_argument(
        "--grayscale",
        action="store_true",
        help="Convertit les copies optimisées en niveaux de gris.",
    )
    parser.add_argument(
        "--image-max-width",
        type=int,
        default=1200,
        help="Largeur maximale en pixels des copies optimisées (défaut : 1200).",
    )
    parser.add_argument(
        "--image-max-height",
        type=int,
        default=1600,
        help="Hauteur maximale en pixels des copies optimisées (défaut : 1600).",
    )
    parser.add_argument(
        "--image-quality",
        type=int,
        default=82,
        help="Qualité JPEG, de 1 à 95 (défaut : 82).",
    )
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
            raise RuntimeError(f"Inclusion LaTeX récursive détectée: {chain}")

        expanded = read_text(target)
        return expand_inputs(expanded, target.parent, (*stack, target))

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


def skip_spaces(text: str, pos: int) -> int:
    while pos < len(text) and text[pos].isspace():
        pos += 1
    return pos


def read_balanced(text: str, pos: int, opening: str, closing: str) -> tuple[str, int]:
    """Lit un groupe équilibré en tenant compte des accolades imbriquées."""
    if pos >= len(text) or text[pos] != opening:
        raise ValueError(f"Groupe {opening}{closing} attendu à la position {pos}")

    depth = 1
    i = pos + 1
    start = i
    while i < len(text):
        ch = text[i]
        if ch == "\\":
            # Une accolade échappée n'ouvre/ne ferme pas de groupe.
            i += 2
            continue
        if ch == opening:
            depth += 1
        elif ch == closing:
            depth -= 1
            if depth == 0:
                return text[start:i], i + 1
        i += 1

    raise ValueError(f"Groupe {opening}{closing} non fermé")


def replace_macro(
    text: str,
    macro_name: str,
    mandatory_args: int,
    replacer,
    optional_first_arg: bool = False,
) -> str:
    """Remplace une macro LaTeX en analysant correctement les accolades imbriquées."""
    token = "\\" + macro_name
    out: list[str] = []
    cursor = 0

    while True:
        start = text.find(token, cursor)
        if start == -1:
            out.append(text[cursor:])
            break

        # Évite de confondre \illustrationX avec \illustration.
        after = start + len(token)
        if after < len(text) and (text[after].isalpha() or text[after] == "@"):
            out.append(text[cursor:after])
            cursor = after
            continue

        out.append(text[cursor:start])
        pos = skip_spaces(text, after)
        optional = None

        try:
            if optional_first_arg and pos < len(text) and text[pos] == "[":
                optional, pos = read_balanced(text, pos, "[", "]")
                pos = skip_spaces(text, pos)

            args: list[str] = []
            for _ in range(mandatory_args):
                value, pos = read_balanced(text, pos, "{", "}")
                args.append(value)
                pos = skip_spaces(text, pos)
        except ValueError as exc:
            print(
                f"[epub] avertissement: impossible d'analyser {token}: {exc}",
                file=sys.stderr,
            )
            out.append(token)
            cursor = after
            continue

        out.append(replacer(optional, args))
        cursor = pos

    return "".join(out)


def find_image_path(file_name: str, project_root: Path) -> Path | None:
    requested = Path(file_name.strip())

    candidates = []
    if requested.is_absolute():
        candidates.append(requested)
    else:
        candidates.extend(
            [
                project_root / requested,
                project_root / "img" / requested,
            ]
        )

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()

    ignored = {".git", ".epub-build", "_site"}
    matches: list[Path] = []
    for path in project_root.rglob(requested.name):
        if any(part in ignored for part in path.parts):
            continue
        if path.is_file():
            matches.append(path)

    if not matches:
        return None

    matches.sort(key=lambda p: (len(p.parts), p.as_posix()))
    return matches[0].resolve()


def safe_filename(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return value.strip("._") or "image"


def optimize_image(
    source: Path,
    output_dir: Path,
    short_id: str,
    max_width: int,
    max_height: int,
    quality: int,
    grayscale: bool,
) -> Path:
    if Image is None or ImageOps is None:
        raise RuntimeError(
            "Pillow est nécessaire pour --optimize-images. "
            "Installez le paquet python3-pil dans l'image Docker."
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"{safe_filename(short_id)}.jpg"

    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened)

        # Le JPEG ne gère pas la transparence : on la compose sur fond blanc.
        if image.mode in {"RGBA", "LA"} or (
            image.mode == "P" and "transparency" in image.info
        ):
            rgba = image.convert("RGBA")
            background = Image.new("RGBA", rgba.size, "white")
            image = Image.alpha_composite(background, rgba).convert("RGB")
        else:
            image = image.convert("RGB")

        if grayscale:
            image = image.convert("L")

        max_width = max(1, max_width)
        max_height = max(1, max_height)
        scale = min(
            1.0,
            max_width / image.width,
            max_height / image.height,
        )
        if scale < 1.0:
            new_size = (
                max(1, round(image.width * scale)),
                max(1, round(image.height * scale)),
            )
            image = image.resize(new_size, Image.Resampling.LANCZOS)

        image.save(
            output,
            format="JPEG",
            quality=max(1, min(95, quality)),
            optimize=True,
            progressive=True,
        )

    return output


def strip_simple_latex(text: str) -> str:
    """Produit un texte lisible pour les références et la table des figures."""
    previous = None
    while previous != text:
        previous = text
        text = re.sub(
            r"\\(?:textit|emph|textbf|textsc|mbox)\{([^{}]*)\}",
            r"\1",
            text,
        )
    text = text.replace(r"\&", "&")
    text = text.replace("~", " ")
    text = re.sub(r"\\[A-Za-z@]+\*?", "", text)
    text = text.replace("{", "").replace("}", "")
    text = re.sub(r"\s+", " ", text).strip()
    return html.unescape(text)


def convert_session_info(text: str) -> str:
    def repl(_optional: str | None, args: list[str]) -> str:
        first = args[0].strip()
        second = args[1].strip()
        if second:
            content = f"{first} --- {second}"
        else:
            content = first
        return (
            "\n\\begin{sessioninfo}\n"
            f"\\emph{{{content}}}\n"
            "\\end{sessioninfo}\n"
        )

    return replace_macro(text, "sessioninfo", 2, repl)


def convert_illustrations(
    text: str,
    project_root: Path,
    output_path: Path,
    optimize_images: bool,
    grayscale: bool,
    max_width: int,
    max_height: int,
    quality: int,
) -> tuple[str, list[Illustration]]:
    illustrations: list[Illustration] = []
    generated_images = output_path.parent / "images"

    def repl(optional: str | None, args: list[str]) -> str:
        source_name, caption, short_id = (arg.strip() for arg in args)
        label = f"fig:{short_id}"
        source_path = find_image_path(source_name, project_root)

        if source_path is None:
            print(
                f"[epub] avertissement: illustration introuvable: {source_name}",
                file=sys.stderr,
            )
            converted_source = source_name
        elif optimize_images:
            converted = optimize_image(
                source_path,
                generated_images,
                short_id,
                max_width,
                max_height,
                quality,
                grayscale,
            )
            # Le Makefile ajoute .epub-build au resource-path de Pandoc.
            converted_source = converted.relative_to(output_path.parent).as_posix()
            before = source_path.stat().st_size
            after = converted.stat().st_size
            print(
                f"[epub] image: {source_name} -> {converted.name} "
                f"({before / 1024:.0f} KiB -> {after / 1024:.0f} KiB)"
            )
        else:
            converted_source = source_path.relative_to(project_root).as_posix()

        item = Illustration(
            source=source_name,
            caption=caption,
            short_id=short_id,
            label=label,
            converted_source=converted_source,
        )
        illustrations.append(item)

        # Le label doit être le même que dans config.tex : fig:<id>.
        return (
            "\n\\begin{figure}\n"
            "\\centering\n"
            f"\\includegraphics{{{converted_source}}}\n"
            f"\\caption{{{caption}}}\n"
            f"\\label{{{label}}}\n"
            "\\end{figure}\n"
        )

    converted_text = replace_macro(
        text,
        "illustration",
        3,
        repl,
        optional_first_arg=True,
    )
    return converted_text, illustrations


def simplify_references(text: str, illustrations: list[Illustration]) -> str:
    """Transforme les références PDF en références textuelles adaptées à l'EPUB."""
    captions = {
        item.label: strip_simple_latex(item.caption).rstrip(" .")
        for item in illustrations
    }

    # Le numéro de page n'a aucun sens dans un EPUB reflowable.
    text = re.sub(
        r"\s*[,;:]?\s*(?:[Pp]age)\s*~?\s*\\pageref\{[^{}]+\}",
        "",
        text,
    )
    text = re.sub(r"\\pageref\{[^{}]+\}", "", text)

    def figure_text(label: str, include_word: bool = True) -> str:
        caption = captions.get(label)
        if caption:
            prefix = "figure " if include_word else ""
            return f"{prefix}« {caption} »"
        return "figure" if include_word else "illustration"

    # \autoref{fig:...} contient déjà le mot « figure » dans le PDF.
    text = re.sub(
        r"\\autoref\{([^{}]+)\}",
        lambda m: figure_text(m.group(1), True),
        text,
    )

    # « figure~\ref{...} » : on remplace l'ensemble pour ne pas écrire
    # « figure figure ... ».
    text = re.sub(
        r"(?:[Ff]igure)\s*~?\s*\\ref\{([^{}]+)\}",
        lambda m: figure_text(m.group(1), True),
        text,
    )

    # Référence de figure isolée.
    text = re.sub(
        r"\\ref\{(fig:[^{}]+)\}",
        lambda m: figure_text(m.group(1), True),
        text,
    )

    # Les hyperliens LaTeX inter-chapitres sont mal réécrits par Pandoc lors
    # du découpage EPUB. On conserve donc leur texte visible sans lien cassé.
    text = re.sub(
        r"\\hyperref\[[^\]]+\]\{([^{}]+)\}",
        r"\1",
        text,
    )

    # Nettoyage de ponctuation laissé par la suppression de « page X ».
    text = re.sub(r"\s+,", ",", text)
    text = re.sub(r",\s*\.", ".", text)
    text = re.sub(r"\s+([.;:!?])", r"\1", text)
    return text


def build_illustration_list(illustrations: list[Illustration]) -> str:
    if not illustrations:
        return ""

    lines = [r"\chapter*{Table des illustrations}", r"\begin{itemize}"]
    for item in illustrations:
        caption = item.caption.strip()
        lines.append(rf"\item {caption}")
    lines.append(r"\end{itemize}")
    return "\n".join(lines)


def normalize_for_epub(
    text: str,
    project_root: Path,
    output_path: Path,
    optimize_images: bool,
    grayscale: bool,
    max_width: int,
    max_height: int,
    quality: int,
) -> str:
    text = convert_session_info(text)
    text, illustrations = convert_illustrations(
        text,
        project_root,
        output_path,
        optimize_images,
        grayscale,
        max_width,
        max_height,
        quality,
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

    # Éléments propres à la composition papier/PDF.
    text = re.sub(r"\\tableofcontents\b", "", text)
    text = re.sub(r"\\maketitle\b", "", text)
    text = re.sub(r"\\makecampaigntitle\b", "", text)
    text = re.sub(r"\\(?:frontmatter|mainmatter|backmatter)\b", "", text)
    text = re.sub(r"\\(?:newpage|clearpage|cleardoublepage|pagebreak)\b", "", text)
    text = re.sub(r"\\markboth\s*\{[^{}]*\}\s*\{[^{}]*\}", "", text)
    text = re.sub(
        r"\\addcontentsline\s*\{[^{}]*\}\s*\{[^{}]*\}\s*\{[^{}]*\}",
        "",
        text,
    )

    text = simplify_references(text, illustrations)

    # Pandoc ne sait pas générer la listoffigures LaTeX. On en recrée une
    # version EPUB sans numéros de page.
    illustration_list = build_illustration_list(illustrations)
    text = text.replace(r"\listoffigures", illustration_list)

    # Nettoyage léger.
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip() + "\n"


def main() -> int:
    args = parse_args()

    input_path = args.input.resolve()
    output_path = args.output.resolve()
    project_root = Path.cwd().resolve()

    if not input_path.exists():
        print(f"[epub] erreur: source introuvable: {input_path}", file=sys.stderr)
        return 2

    if args.optimize_images and (args.image_max_width <= 0 or args.image_max_height <= 0):
        print("[epub] erreur: les dimensions maximales doivent être positives", file=sys.stderr)
        return 2

    text = read_text(input_path)
    text = expand_inputs(text, input_path.parent, (input_path,))
    text = extract_document_body(text)
    text = normalize_for_epub(
        text,
        project_root,
        output_path,
        args.optimize_images,
        args.grayscale,
        args.image_max_width,
        args.image_max_height,
        args.image_quality,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")
    print(f"[epub] source Pandoc temporaire: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
