MAIN      := main
OUTPUT    := aventures
CHAPDIR   := chapter
CHAPLIST  := .chapters.generated.tex
CHAPTERS  := $(sort $(wildcard $(CHAPDIR)/*.tex))
LATEX     := pdflatex
LATEXFLAGS:= -interaction=nonstopmode -halt-on-error -file-line-error
PANDOC     := pandoc
PYTHON     := python3
EPUB_TOOL  := tools/prepare_epub.py
EPUB_TMP   := .epub-build
EPUB_SRC   := $(EPUB_TMP)/$(OUTPUT).tex

.PHONY: all pdf epub clean chapters show-chapters

# Construit les deux formats.
all: pdf epub

pdf: $(OUTPUT).pdf

# Génère automatiquement les \input{...} dans l'ordre alphabétique des fichiers.
# Avec des noms 0100_..., 0200_..., 0250_..., l'ordre est donc celui des numéros.
$(CHAPLIST): $(CHAPTERS) Makefile
	@echo "%% Fichier genere automatiquement par Makefile - ne pas modifier." > $(CHAPLIST)
	@for file in $(CHAPTERS); do \
		echo "\\input{$$file}" >> $(CHAPLIST); \
	done

chapters: $(CHAPLIST)

$(OUTPUT).pdf: $(MAIN).tex config.tex $(CHAPLIST) $(CHAPTERS)
	$(LATEX) $(LATEXFLAGS) -jobname=$(OUTPUT) $(MAIN).tex
	$(LATEX) $(LATEXFLAGS) -jobname=$(OUTPUT) $(MAIN).tex
	@rm -f $(OUTPUT).aux $(OUTPUT).log $(OUTPUT).toc $(OUTPUT).out $(OUTPUT).lof $(OUTPUT).lot

# L'EPUB est généré à partir d'une copie temporaire aplatie et adaptée à Pandoc.
# Le répertoire temporaire est supprimé même si Pandoc échoue.
epub: $(CHAPLIST) $(MAIN).tex config.tex $(CHAPTERS) $(EPUB_TOOL)
	@set -eu; \
	rm -rf "$(EPUB_TMP)"; \
	mkdir -p "$(EPUB_TMP)"; \
	trap 'rm -rf "$(EPUB_TMP)"' EXIT INT TERM; \
	$(PYTHON) "$(EPUB_TOOL)" \
		--input "$(MAIN).tex" \
		--output "$(EPUB_SRC)"; \
	$(PANDOC) "$(EPUB_SRC)" \
		--from=latex \
		--to=epub3 \
		--standalone \
		--toc \
		--metadata title="Alan pas riche" \
		--metadata subtitle="Recit de campagne - Donjons et Dragons" \
		--metadata author="" \
		--metadata lang="fr-FR" \
		--resource-path=".:$(EPUB_TMP)" \
		-o "$(OUTPUT).epub"

show-chapters:
	@printf '%s\n' $(CHAPTERS)

clean:
	rm -f $(OUTPUT).pdf $(OUTPUT).epub \
	      $(OUTPUT).aux $(OUTPUT).log $(OUTPUT).toc $(OUTPUT).out \
	      $(OUTPUT).lof $(OUTPUT).lot $(CHAPLIST)
	rm -rf $(EPUB_TMP)
