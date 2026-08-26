FROM texlive/texlive:latest

WORKDIR /data

# Outils nécessaires aux builds PDF + EPUB.
# python3 est utilisé par tools/prepare_epub.py.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        graphviz \
        inkscape \
        ghostscript \
        bash \
        make \
        python3 \
        pandoc \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Compilation du projet monté dans /data.
# "make" construit désormais PDF + EPUB via la cible "all".
CMD ["make", "all"]


# docker build -f Dockerfile . --tag latex_builder

# Windows cmd :
# docker run --rm --volume %cd%:/data latex_builder
#
# Windows PowerShell :
# docker run --rm --volume ${PWD}:/data latex_builder
#
# Linux :
# docker run --rm --volume $(pwd):/data latex_builder
#
# Shell interactif PowerShell :
# docker run --rm --volume ${PWD}:/data -it --entrypoint /bin/bash latex_builder
