FROM --platform=$TARGETPLATFORM lscr.io/linuxserver/webtop:latest

# Install necessary packages without running 'apk update'
RUN apk add --no-cache \
    build-base \
    libffi-dev \
    openssl-dev \
    curl \
    python3-dev \
    py3-pip

# Install Poetry using pip
RUN pip3 install --no-cache-dir poetry

# Copy your project into the container
COPY . /app/agentd/

# Set the working directory
WORKDIR /app/agentd

# Configure Poetry to create virtual environments inside the project directory
RUN poetry config virtualenvs.in-project true

# Install dependencies without specifying the system Python interpreter
RUN poetry install --no-interaction --no-ansi

# Create the service directory
RUN mkdir -p /etc/services.d/agentd

# Copy the service script
COPY uvicorn-run.sh /etc/services.d/agentd/run

# Make the service script executable
RUN chmod +x /etc/services.d/agentd/run

# Expose the necessary port
EXPOSE 8000