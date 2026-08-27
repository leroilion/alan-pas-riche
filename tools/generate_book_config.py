#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import yaml


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--latex", type=Path)
    parser.add_argument("--epub", type=Path)
    return parser.parse_args()


def french_join(items: list[str]) -> str:
    items = [str(x).strip() for x in items if str(x).strip()]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} et {items[1]}"
    return ", ".join(items[:-1]) + f" et {items[-1]}"


def latex_escape(value: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(ch, ch) for ch in str(value))


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    title = str(data.get("title", "")).strip()
    players = data.get("players", []) or []
    authors = data.get("authors", []) or []

    if isinstance(players, str):
        players = [players]
    if isinstance(authors, str):
        authors = [authors]

    subtitle = str(data.get("subtitle", "")).strip()
    if not subtitle:
        joined_players = french_join(players)
        subtitle = f"Les aventures de {joined_players}" if joined_players else ""

    data["_title"] = title
    data["_players"] = [str(x) for x in players]
    data["_authors"] = [str(x) for x in authors]
    data["_subtitle"] = subtitle
    data["_author_text"] = french_join([str(x) for x in authors])

    return data


def write_latex(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    title = latex_escape(data["_title"])
    subtitle = latex_escape(data["_subtitle"])
    meta = latex_escape(data.get("meta", ""))
    author = latex_escape(data["_author_text"])
    tagline = latex_escape(data.get("tagline", ""))
    subject = latex_escape(data.get("subject", data.get("meta", "")))

    content = f"""%% Fichier généré automatiquement depuis book.yml.
%% Ne pas modifier à la main.

\\newcommand{{\\BookTitle}}{{{title}}}
\\newcommand{{\\BookSubtitle}}{{{subtitle}}}
\\newcommand{{\\BookMeta}}{{{meta}}}
\\newcommand{{\\BookAuthor}}{{{author}}}
\\newcommand{{\\BookTagline}}{{{tagline}}}
\\newcommand{{\\BookSubject}}{{{subject}}}
"""
    path.write_text(content, encoding="utf-8")


def write_epub(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    metadata = {
        "title": data["_title"],
        "subtitle": data["_subtitle"],
        "author": data["_authors"],
        "lang": str(data.get("lang", "fr-FR")),
        "subject": str(data.get("subject", data.get("meta", ""))),
        "description": str(data.get("tagline", "")),
    }

    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(
            metadata,
            f,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        )


def main() -> int:
    args = parse_args()
    data = load_config(args.config)

    if not args.latex and not args.epub:
        raise SystemExit("Il faut fournir --latex et/ou --epub.")

    if args.latex:
        write_latex(data, args.latex)
        print(f"[book-config] LaTeX généré : {args.latex}")

    if args.epub:
        write_epub(data, args.epub)
        print(f"[book-config] Métadonnées EPUB générées : {args.epub}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
