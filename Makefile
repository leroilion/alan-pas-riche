MAIN       := main
OUTPUT     := aventures
CHAPDIR    := chapter
CHAPLIST   := .chapters.generated.tex
CHAPTERS   := $(sort $(wildcard $(CHAPDIR)/*.tex))
LATEX      := pdflatex
LATEXFLAGS := -interaction=nonstopmode -halt-on-error -file-line-error
PANDOC     := pandoc
PYTHON     := python3

BOOK_CONFIG      := book.yml
BOOK_CONFIG_TOOL := tools/generate_book_config.py
BOOK_TEX         := .book.generated.tex

EPUB_TOOL     := tools/prepare_epub.py
EPUB_CSS      := tools/epub.css
EPUB_TMP      := .epub-build
EPUB_SRC      := $(EPUB_TMP)/$(OUTPUT).tex
EPUB_METADATA := $(EPUB_TMP)/metadata.yaml

EPUB_IMAGE_MAX_WIDTH  ?= 1200
EPUB_IMAGE_MAX_HEIGHT ?= 1600
EPUB_IMAGE_QUALITY    ?= 82

.PHONY: all pdf epub epub-color clean chapters show-chapters metadata

all: pdf epub

pdf: $(OUTPUT).pdf

$(CHAPLIST): $(CHAPTERS) Makefile
	@echo "%% Fichier genere automatiquement par Makefile - ne pas modifier." > $(CHAPLIST)
	@for file in $(CHAPTERS); do \
		echo "\\input{$$file}" >> $(CHAPLIST); \
	done

$(BOOK_TEX): $(BOOK_CONFIG) $(BOOK_CONFIG_TOOL)
	$(PYTHON) "$(BOOK_CONFIG_TOOL)" \
		--config "$(BOOK_CONFIG)" \
		--latex "$(BOOK_TEX)"

metadata: $(BOOK_TEX)

chapters: $(CHAPLIST)

$(OUTPUT).pdf: $(MAIN).tex config.tex $(BOOK_TEX) $(CHAPLIST) $(CHAPTERS)
	$(LATEX) $(LATEXFLAGS) -jobname=$(OUTPUT) $(MAIN).tex
	$(LATEX) $(LATEXFLAGS) -jobname=$(OUTPUT) $(MAIN).tex
	@rm -f $(OUTPUT).aux $(OUTPUT).log $(OUTPUT).toc $(OUTPUT).out $(OUTPUT).lof $(OUTPUT).lot

epub: $(CHAPLIST) $(MAIN).tex config.tex $(BOOK_CONFIG) $(BOOK_CONFIG_TOOL) $(CHAPTERS) $(EPUB_TOOL) $(EPUB_CSS)
	@set -eu; \
	rm -rf "$(EPUB_TMP)"; \
	mkdir -p "$(EPUB_TMP)"; \
	trap 'rm -rf "$(EPUB_TMP)"' EXIT INT TERM; \
	$(PYTHON) "$(BOOK_CONFIG_TOOL)" \
		--config "$(BOOK_CONFIG)" \
		--epub "$(EPUB_METADATA)"; \
	$(PYTHON) "$(EPUB_TOOL)" \
		--input "$(MAIN).tex" \
		--output "$(EPUB_SRC)" \
		--optimize-images \
		--grayscale \
		--image-max-width "$(EPUB_IMAGE_MAX_WIDTH)" \
		--image-max-height "$(EPUB_IMAGE_MAX_HEIGHT)" \
		--image-quality "$(EPUB_IMAGE_QUALITY)"; \
	$(PANDOC) "$(EPUB_SRC)" \
		--from=latex \
		--to=epub3 \
		--standalone \
		--toc \
		--css "$(EPUB_CSS)" \
		--metadata-file "$(EPUB_METADATA)" \
		--resource-path=".:$(EPUB_TMP)" \
		-o "$(OUTPUT).epub"

epub-color: $(CHAPLIST) $(MAIN).tex config.tex $(BOOK_CONFIG) $(BOOK_CONFIG_TOOL) $(CHAPTERS) $(EPUB_TOOL) $(EPUB_CSS)
	@set -eu; \
	rm -rf "$(EPUB_TMP)"; \
	mkdir -p "$(EPUB_TMP)"; \
	trap 'rm -rf "$(EPUB_TMP)"' EXIT INT TERM; \
	$(PYTHON) "$(BOOK_CONFIG_TOOL)" \
		--config "$(BOOK_CONFIG)" \
		--epub "$(EPUB_METADATA)"; \
	$(PYTHON) "$(EPUB_TOOL)" \
		--input "$(MAIN).tex" \
		--output "$(EPUB_SRC)" \
		--optimize-images \
		--image-max-width "$(EPUB_IMAGE_MAX_WIDTH)" \
		--image-max-height "$(EPUB_IMAGE_MAX_HEIGHT)" \
		--image-quality "$(EPUB_IMAGE_QUALITY)"; \
	$(PANDOC) "$(EPUB_SRC)" \
		--from=latex \
		--to=epub3 \
		--standalone \
		--toc \
		--css "$(EPUB_CSS)" \
		--metadata-file "$(EPUB_METADATA)" \
		--resource-path=".:$(EPUB_TMP)" \
		-o "$(OUTPUT).epub"

show-chapters:
	@printf '%s\n' $(CHAPTERS)

clean:
	rm -f $(OUTPUT).pdf $(OUTPUT).epub \
	      $(OUTPUT).aux $(OUTPUT).log $(OUTPUT).toc $(OUTPUT).out \
	      $(OUTPUT).lof $(OUTPUT).lot $(CHAPLIST) $(BOOK_TEX)
	rm -rf $(EPUB_TMP)
