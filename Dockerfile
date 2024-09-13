FROM --platform=$TARGETPLATFORM lscr.io/linuxserver/webtop:latest

COPY . /app/agentd/

RUN apk update && \
    apk add build-base libffi-dev openssl-dev curl poetry python3-dev

# Configure Poetry to place virtual environments outside of the project directory
RUN poetry config virtualenvs.in-project false

RUN ls /app/agentd

RUN cd /app/agentd && poetry env use /usr/bin/python3.12 && poetry install

RUN mkdir -p /etc/services.d/agentd

COPY uvicorn-run.sh /etc/services.d/agentd/run

RUN chmod +x /etc/services.d/agentd/run