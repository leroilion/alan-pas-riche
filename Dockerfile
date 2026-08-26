FROM texlive/texlive:latest

WORKDIR /data

# Outils externes utiles aux documents LaTeX
RUN apt-get update && \
    apt-get install -y \
        graphviz \
        inkscape \
        ghostscript \
        bash \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Compilation du projet monté dans /data
CMD ["make", "SHELL_ESCAPE=1"]


# docker build -f Dockerfile . --tag latex_builder

# windows cmd : docker run --rm --volume %cd%:/data latex_builder
# windows powershell : docker run --rm --volume ${PWD}:/data latex_builder
# Linux : docker run --rm --volume $(pwd):/data latex_builder

# windows powershell : docker run --rm --volume ${PWD}:/data -it --entrypoint /bin/bash latex_builder
