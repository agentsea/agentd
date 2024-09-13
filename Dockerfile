FROM --platform=$TARGETPLATFORM lscr.io/linuxserver/webtop:latest

# Update package list and install dependencies using apt
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libssl-dev \
    curl \
    python3 \
    python3-dev \
    python3-pip && \
    rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip3 install --no-cache-dir poetry

# Copy your project
COPY . /app/agentd/

# Set working directory
WORKDIR /app/agentd

# Configure Poetry to create virtual environments inside the project directory
RUN poetry config virtualenvs.in-project true

# Install dependencies without specifying system Python
RUN poetry install --no-interaction --no-ansi

# Set up your service script
RUN mkdir -p /etc/services.d/agentd
COPY uvicorn-run.sh /etc/services.d/agentd/run
RUN chmod +x /etc/services.d/agentd/run

# Expose necessary ports
EXPOSE 8000