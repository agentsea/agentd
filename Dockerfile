FROM --platform=$TARGETPLATFORM lscr.io/linuxserver/webtop:latest@sha256:41109089fcf80d45b25e6e3d0d8a9ae9bd13568af2d020266e55c7159fc9f2eb

RUN uname -m
RUN cat /etc/alpine-release

# Install necessary build tools and libraries
RUN echo "http://dl-cdn.alpinelinux.org/alpine/v3.20/community" >> /etc/apk/repositories && \
    apk update && \
    apk add --no-cache \
    build-base \
    libffi-dev \
    openssl-dev \
    zlib-dev \
    bzip2-dev \
    readline-dev \
    sqlite-dev \
    ncurses-dev \
    xz-dev \
    bash \
    tk-dev \
    gdbm-dev \
    db-dev \
    libpcap-dev \
    linux-headers \
    curl \
    git \
    wget \
    scrot \
    xrandr \
    libx11 \
    libxext \
    libxcb \
    xauth \
    xwd \
    imagemagick \
    procps \
    xdotool \
    speech-dispatcher \
    xclip \
    gtk-murrine-engine \
    sassc \
    rsync \
    bc \
    optipng \
    zip \
    unzip \
    xmlstarlet \
    coreutils \
    glib-dev \
    libxml2-utils \
    mesa-gl \
    xvfb \
    mesa-dri-gallium \
    redis

# RUN echo $USER
RUN pwd
RUN echo $HOME
RUN echo $USER
RUN echo $LOGNAME
RUN echo $SHELL

RUN which readlink && readlink --version

# Set up X11 directories as root
RUN mkdir -p /tmp/.X11-unix && \
    chmod 1777 /tmp/.X11-unix && \
    mkdir -p /var/lib/dbus && \
    dbus-uuidgen > /var/lib/dbus/machine-id

RUN mkdir -p /config/.themes /config/.icons /config/.wallpapers /config/.local /config/.config/gtk-3.0 && \
    chown -R abc:abc /config/.themes /config/.icons /config/.wallpapers /config/.local /config/.config/gtk-3.0

# Set up runtime directory
RUN mkdir -p /tmp/runtime-abc && \
    chown abc:abc /tmp/runtime-abc && \
    chmod 700 /tmp/runtime-abc


RUN mkdir -p /config/.cache/fontconfig && \
    chown -R abc:abc /config/.cache && \
    # Pre-generate font caches (optional but helps)
    fc-cache -fv

RUN mkdir -p /config/.config/glib-2.0
RUN chown -R abc:abc /config/.config/glib-2.0

# Switch to user 'abc'
USER abc
RUN env

# Set environment variables
ENV HOME=/config \
    XDG_RUNTIME_DIR=/tmp/runtime-abc \
    XDG_CACHE_HOME=/config/.cache \
    FONTCONFIG_PATH=/etc/fonts \
    FONTCONFIG_FILE=/etc/fonts/fonts.conf \
    FONTCONFIG_CACHE=/config/.cache/fontconfig \
    MOZ_HEADLESS=1 \
    MOZ_DISABLE_GLX_TEST=1 \
    MOZ_DISABLE_RDD_SANDBOX=1 \
    MOZ_DISABLE_GPU_SANDBOX=1 \
    MOZ_X11_EGL=1 \
    LIBGL_ALWAYS_SOFTWARE=1 \
    DISPLAY=:99 \
    DBUS_SESSION_BUS_ADDRESS=unix:path=/tmp/dbus.sock

# Initialize D-Bus and X server
RUN dbus-daemon --session --address=unix:path=/tmp/dbus.sock --print-address --nopidfile && \
    (Xvfb :99 -screen 0 1024x768x24 -nolisten tcp -nolisten unix & sleep 2 && \
    xauth add :99 MIT-MAGIC-COOKIE-1 $(mcookie))

# Initialize Firefox profile
RUN firefox --createprofile "default /config/.mozilla/firefox/default" && \
    timeout 30s firefox --headless --no-remote --profile /config/.mozilla/firefox/default about:blank || true

# Cleanup
RUN rm -rf /config/.cache/* /config/.mozilla/firefox/default/lock /config/.mozilla/firefox/default/.parentlock


# Install WhiteSur Themes and Wallpapers
RUN export HOME=/config USER=abc LOGNAME=abc SHELL=/bin/bash && \
    \
    # Install WhiteSur GTK Theme
    git clone https://github.com/vinceliuice/WhiteSur-gtk-theme.git --depth=1 /config/.themes/WhiteSur-gtk-theme && \
    /bin/bash -ex /config/.themes/WhiteSur-gtk-theme/install.sh -d /config/.themes && /bin/bash -ex /config/.themes/WhiteSur-gtk-theme/tweaks.sh -f -r && \
    rm -rf /config/.themes/WhiteSur-gtk-theme && \
    \
    # Install WhiteSur Icon Theme
    git clone https://github.com/vinceliuice/WhiteSur-icon-theme.git --depth=1 /config/.icons/WhiteSur-icon-theme && \
    /bin/bash -ex /config/.icons/WhiteSur-icon-theme/install.sh -d /config/.icons && \
    rm -rf /config/.icons/WhiteSur-icon-theme && \
    \
    # Install WhiteSur Wallpapers
    git clone https://github.com/vinceliuice/WhiteSur-wallpapers.git --depth=1 /config/.wallpapers/WhiteSur-wallpapers && \
    /bin/bash -ex /config/.wallpapers/WhiteSur-wallpapers/install-wallpapers.sh -t monterey && \
    rm -rf /config/.wallpapers/WhiteSur-wallpapers

RUN chown -R abc:abc /config/.themes /config/.icons /config/.local /config/.wallpapers

# Set Monterey-light.jpg as the desktop background using xfconf-query
COPY --chown=abc:abc xfce4-desktop.xml /config/.config/xfce4/xfconf/xfce-perchannel-xml/

# Set the GTK and Icon theme for user 'abc'
RUN echo '[Settings]' > /config/.config/gtk-3.0/settings.ini && \
    echo 'gtk-theme-name=WhiteSur-Light' >> /config/.config/gtk-3.0/settings.ini && \
    echo 'gtk-icon-theme-name=WhiteSur' >> /config/.config/gtk-3.0/settings.ini

RUN xfconf-query -c xsettings -p /Net/ThemeName    -s "WhiteSur-Light" \
    && xfconf-query -c xsettings -p /Net/IconThemeName -s "WhiteSur"       \
    && xfconf-query -c xfwm4     -p /general/theme     -s "WhiteSur-Light" \
    && xfconf-query -c xsettings -p /Gtk/CursorThemeName -s "WhiteSur-cursors" \
    && xfconf-query -c xsettings -p /Gtk/FontName        -s "Ubuntu 11"

# # Set environment variables for Python installation
# ENV PYTHON_VERSION=3.12.1
# ENV PYENV_ROOT="/config/.pyenv"
# ENV PATH="$PYENV_ROOT/bin:$PATH"

# # Install pyenv as root
# RUN curl https://pyenv.run | bash

# # Change ownership of pyenv directories to user 'abc'
# RUN chown -R abc:abc /config/.pyenv

# # Create the application directory and set ownership to 'abc'
# RUN mkdir -p /config/app && chown -R abc:abc /config/app

# # Ensure the cache directory exists and is owned by 'abc'
# RUN mkdir -p /config/app/.cache && chown -R abc:abc /config/app/.cache

# # Switch to non-root user 'abc'
# USER abc

# # Create a shell script for environment setup
# RUN echo 'export PYENV_ROOT="/config/.pyenv"' > /config/app/pyenv_setup.sh && \
#     echo 'export PATH="$PYENV_ROOT/bin:$PYENV_ROOT/shims:$PATH"' >> /config/app/pyenv_setup.sh && \
#     echo 'eval "$(pyenv init --path)"' >> /config/app/pyenv_setup.sh && \
#     echo 'eval "$(pyenv init -)"' >> /config/app/pyenv_setup.sh && \
#     chmod +x /config/app/pyenv_setup.sh

# # Set working directory to '/config/app'
# WORKDIR /config/app

# # Copy project files (only pyproject.toml and poetry.lock to leverage caching)
# COPY --chown=abc:abc pyproject.toml README.md poetry.lock /config/app/

# # Install Python using pyenv as 'abc' by sourcing the setup script
# RUN XDG_CACHE_HOME=/config/app/.cache /bin/bash -c \
#     "source /config/app/pyenv_setup.sh && pyenv install ${PYTHON_VERSION}" || \
#     { echo "Build failed. Showing config.log:"; cat /tmp/python-build.*/Python-*/config.log; exit 1; }

# # Set the global Python version
# RUN XDG_CACHE_HOME=/config/app/.cache /bin/bash -c \
#     "source /config/app/pyenv_setup.sh && pyenv global ${PYTHON_VERSION}"

# # Ensure 'abc' owns the pyenv directory after installation
# USER root
# RUN chown -R abc:abc /config/.pyenv
# USER abc

# # Create a virtual environment using the installed Python version
# RUN XDG_CACHE_HOME=/config/app/.cache /bin/bash -c \
#     "source /config/app/pyenv_setup.sh && python -m venv /config/app/venv"

# # Update PATH to include the virtual environment's bin directory
# ENV PATH="/config/app/venv/bin:$PATH"

# # Set environment variable to prevent poetry from using keyring
# ENV POETRY_NO_KEYRING=1

# # Upgrade pip to the latest version
# RUN XDG_CACHE_HOME=/config/app/.cache /bin/bash -c \
#     "source /config/app/pyenv_setup.sh && \
#      source /config/app/venv/bin/activate && \
#      pip install --no-cache-dir --upgrade pip"

# # Install project dependencies using Poetry
# RUN XDG_CACHE_HOME=/config/app/.cache \
#     POETRY_CACHE_DIR=/config/app/.cache/pypoetry \
#     /bin/bash -c "source /config/app/pyenv_setup.sh && \
#     source /config/app/venv/bin/activate && \
#     pip install --no-cache-dir poetry && \
#     poetry install --no-root"

# # Copy the rest of your application code
# COPY --chown=abc:abc . /config/app/

# # Create the logs and recordings directories and set ownership to 'abc'
# RUN mkdir -p /config/app/logs && chown -R abc:abc /config/app/logs
# RUN mkdir -p /config/app/recordings && chown -R abc:abc /config/app/recordings

# # Switch back to root to set up the s6-overlay v3 service
USER root

# ENV S6_LOGGING=1
# ENV S6_VERBOSITY=2
# ENV S6_KEEP_ENV=1
# ENV S6_RC_VERBOSE=1

# RUN touch /config/app/audit.log && chown abc:abc /config/app/audit.log && chmod 644 /config/app/audit.log
# RUN touch /config/app/logs/uvicorn_env.log && chown abc:abc /config/app/logs/uvicorn_env.log && chmod 644 /config/app/logs/uvicorn_env.log
# RUN touch /config/app/logs/redis_env.log && chown abc:abc /config/app/logs/redis_env.log && chmod 644 /config/app/logs/redis_env.log
# RUN touch /config/app/logs/redis.log && chown abc:abc /config/app/logs/redis.log && chmod 644 /config/app/logs/redis.log

# RUN mkdir -p /config/app/logs/uvicorn && chown -R abc:abc /config/app/logs/uvicorn

# RUN mkdir -p /config/app/celery && chown -R abc:abc /config/app/celery && chmod 744 /config/app/celery
# RUN mkdir -p /config/.agentsea && chown -R abc:abc /config/.agentsea
# RUN mkdir -p /config/.agentsea/data && chown -R abc:abc /config/.agentsea/data

# # Create the s6-overlay v3 service directory for your application
# RUN mkdir -p /etc/s6-overlay/s6-rc.d/uvicorn

# # Create Redis service directory
# RUN mkdir -p /etc/s6-overlay/s6-rc.d/redis

# # Copy the s6-overlay v3 run script into the service directory
# COPY uvicorn_run /etc/s6-overlay/s6-rc.d/uvicorn/run


# # Copy the s6-overlay v3 run script into the service directory
# COPY redis_run /etc/s6-overlay/s6-rc.d/redis/run

# # Make the run script executable
# RUN chmod +x /etc/s6-overlay/s6-rc.d/uvicorn/run

# # Make the run script executable for redis
# RUN chmod +x /etc/s6-overlay/s6-rc.d/redis/run

# # Create the 'type' file for the service
# RUN echo 'longrun' > /etc/s6-overlay/s6-rc.d/uvicorn/type

# # Create the 'type' file for Redis service
# RUN echo 'longrun' > /etc/s6-overlay/s6-rc.d/redis/type

# # Enable the service by creating a symlink in the 'user' bundle
# RUN ln -s ../uvicorn /etc/s6-overlay/s6-rc.d/user/contents.d/uvicorn

# # Enable Redis service by creating a symlink in the 'user' bundle
# RUN ln -s ../redis /etc/s6-overlay/s6-rc.d/user/contents.d/redis

# # Set up logging for the service
# RUN mkdir -p /etc/s6-overlay/s6-rc.d/uvicorn/log

# # make the log run script executable
# COPY uvicorn_log_run /etc/s6-overlay/s6-rc.d/uvicorn/log/run

# # make the log run script executable
# RUN chmod +x /etc/s6-overlay/s6-rc.d/uvicorn/log/run

# # Create the 'data' directory for the service and set the user
# # RUN mkdir -p /etc/s6-overlay/s6-rc.d/uvicorn/data && \
# #     echo 'abc' > /etc/s6-overlay/s6-rc.d/uvicorn/data/user

# RUN echo 'abc' > /etc/s6-overlay/s6-rc.d/uvicorn/user

# # Set the user for Redis service
# RUN echo 'abc' > /etc/s6-overlay/s6-rc.d/redis/user

# # Expose the port uvicorn is running on (if needed)
# EXPOSE 8000

# Expose Redis Port, we don't need to because it should only be used internally but this is there just incase
# EXPOSE 6379