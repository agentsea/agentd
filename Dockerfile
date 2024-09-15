FROM --platform=$TARGETPLATFORM lscr.io/linuxserver/webtop:latest

# Install necessary build tools and libraries
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
    git \
    poetry \ 
    wget

# Set environment variables for Python installation
ENV PYTHON_VERSION=3.12.0
ENV PYENV_ROOT="/config/.pyenv"
ENV PATH="$PYENV_ROOT/bin:$PATH"

# Install pyenv
RUN curl https://pyenv.run | bash

# Add pyenv to PATH and initialize
RUN echo 'export PYENV_ROOT="/config/.pyenv"' >> ~/.bashrc && \
    echo 'export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc && \
    echo 'eval "$(pyenv init --path)"' >> ~/.bashrc && \
    echo 'eval "$(pyenv init -)"' >> ~/.bashrc

# Install Python using pyenv (without setting it as global)
RUN /bin/bash -c "source ~/.bashrc && pyenv install ${PYTHON_VERSION}"

# Set working directory
WORKDIR /app

COPY pyproject.toml /app/

RUN poetry lock --no-update

# Generate requirements.txt file
RUN poetry export -f requirements.txt --output requirements.txt --without-hashes --without-urls

# Create a virtual environment
RUN /bin/bash -c "source ~/.bashrc && \
    $PYENV_ROOT/versions/${PYTHON_VERSION}/bin/python -m venv /app/venv"

# Activate the virtual environment and install dependencies
RUN /bin/bash -c "source /app/venv/bin/activate && \
    pip install --upgrade pip && \
    pip install -r requirements.txt"
