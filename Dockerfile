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
ENV PYENV_ROOT="/root/.pyenv"
ENV PATH="$PYENV_ROOT/bin:$PATH"

# Install pyenv
RUN curl https://pyenv.run | bash

# Add pyenv to PATH and initialize
RUN echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc && \
    echo '[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc && \
    echo 'eval "$(pyenv init -)"' >> ~/.bashrc

# # Install Python using pyenv
# RUN /bin/bash -c "source ~/.bashrc && pyenv install ${PYTHON_VERSION} && pyenv global ${PYTHON_VERSION}"

# # Verify Python installation
# RUN /bin/bash -c "source ~/.bashrc && python --version"

# # Install Poetry
# RUN /bin/bash -c "source ~/.bashrc && curl -sSL https://install.python-poetry.org | python -"

# # Add Poetry to PATH (note the change from /root to /config)
# ENV PATH="/config/.local/bin:$PATH"

# # Add Poetry to .bashrc for interactive shells
# RUN echo 'export PATH="/config/.local/bin:$PATH"' >> ~/.bashrc

# # Verify Poetry installation
# RUN /bin/bash -c "source ~/.bashrc && /config/.local/bin/poetry --version"

# # Set working directory
# WORKDIR /app