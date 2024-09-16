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
    wget

# Set environment variables for Python installation
ENV PYTHON_VERSION=3.12.0
ENV PYENV_ROOT="/config/.pyenv"
ENV PATH="$PYENV_ROOT/bin:$PATH"

# Install pyenv as root
RUN curl https://pyenv.run | bash

# Change ownership of pyenv directories to user 'abc'
RUN chown -R abc:abc /config/.pyenv

# Create the application directory and set ownership to 'abc'
RUN mkdir -p /config/app && chown -R abc:abc /config/app

# Switch to non-root user 'abc'
USER abc

# Create a shell script for environment setup
RUN echo 'export PYENV_ROOT="/config/.pyenv"' > /config/app/pyenv_setup.sh && \
    echo 'export PATH="$PYENV_ROOT/bin:$PYENV_ROOT/shims:$PATH"' >> /config/app/pyenv_setup.sh && \
    echo 'eval "$(pyenv init --path)"' >> /config/app/pyenv_setup.sh && \
    echo 'eval "$(pyenv init -)"' >> /config/app/pyenv_setup.sh && \
    chmod +x /config/app/pyenv_setup.sh

# Set working directory to '/config/app'
WORKDIR /config/app

# Copy project files
COPY --chown=abc:abc pyproject.toml poetry.lock /config/app/

# Install Python using pyenv as 'abc' by sourcing the setup script
RUN /bin/bash -c "source /config/app/pyenv_setup.sh && pyenv install ${PYTHON_VERSION}"

# Set the global Python version
RUN /bin/bash -c "source /config/app/pyenv_setup.sh && pyenv global ${PYTHON_VERSION}"

# Create a virtual environment using the installed Python version
RUN /bin/bash -c "source /config/app/pyenv_setup.sh && python -m venv /config/app/venv"

# Update PATH to include the virtual environment's bin directory
ENV PATH="/config/app/venv/bin:$PATH"

# Install project dependencies using Poetry (assuming you have a pyproject.toml)
RUN /bin/bash -c "source /config/app/pyenv_setup.sh && source /config/app/venv/bin/activate && pip install poetry && poetry install"

# Switch back to root if needed
USER root
