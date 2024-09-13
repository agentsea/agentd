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
    wget

# Set environment variables for Python installation
ENV PYTHON_VERSION=3.12.0
ENV PYTHON_INSTALL_DIR=/opt/python$PYTHON_VERSION

# Download and build Python from source with modified flags
RUN mkdir -p /tmp/python-build && \
    cd /tmp/python-build && \
    wget https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tar.xz && \
    tar -xf Python-${PYTHON_VERSION}.tar.xz && \
    cd Python-${PYTHON_VERSION} && \
    CFLAGS="-Wno-error -O2" ./configure --prefix=${PYTHON_INSTALL_DIR} --enable-optimizations && \
    make -j$(nproc) CFLAGS="-Wno-error -O2" && \
    make altinstall && \
    rm -rf /tmp/python-build

# Update PATH to include the new Python installation
ENV PATH="${PYTHON_INSTALL_DIR}/bin:${PATH}"

# Verify Python installation
RUN python3.12 --version

# Install Poetry using the custom Python
RUN python3.12 -m pip install --no-cache-dir poetry