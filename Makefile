MAIN      := main
OUTPUT    := aventures
CHAPDIR   := chapter
CHAPLIST  := .chapters.generated.tex
CHAPTERS  := $(sort $(wildcard $(CHAPDIR)/*.tex))
LATEX     := pdflatex
LATEXFLAGS:= -interaction=nonstopmode -halt-on-error -file-line-error

.PHONY: all clean chapters show-chapters

all: $(OUTPUT).pdf

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

show-chapters:
	@printf '%s\n' $(CHAPTERS)

clean:
	rm -f $(OUTPUT).pdf $(OUTPUT).aux $(OUTPUT).log $(OUTPUT).toc $(OUTPUT).out \
	      $(OUTPUT).lof $(OUTPUT).lot $(CHAPLIST)
