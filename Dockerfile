FROM --platform=$TARGETPLATFORM lscr.io/linuxserver/webtop:latest

ARG PYTHON_VERSION=3.12.0

# Install necessary packages
RUN apk add --no-cache \
    build-base \
    libffi-dev \
    openssl-dev \
    zlib-dev \
    bzip2-dev \
    readline-dev \
    sqlite-dev \
    ncurses-dev \
    xz-dev \
    tk-dev \
    gdbm-dev \
    db-dev \
    libpcap-dev \
    linux-headers \
    curl \
    wget

# Install Python using pyenv
RUN curl https://pyenv.run | bash
ENV PATH="/root/.pyenv/bin:$PATH"
RUN eval "$(pyenv init -)"
RUN pyenv install ${PYTHON_VERSION}
RUN pyenv global ${PYTHON_VERSION}

# Verify Python installation
RUN python --version

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python -

# Add pyenv and poetry to PATH
ENV PATH="/root/.pyenv/versions/${PYTHON_VERSION}/bin:/root/.local/bin:$PATH"

# Verify Poetry installation
RUN poetry --version