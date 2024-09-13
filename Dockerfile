FROM --platform=$TARGETPLATFORM lscr.io/linuxserver/webtop:latest

COPY . /config/agentd/

RUN apk update && \
    apk add build-base libffi-dev openssl-dev curl poetry python3-dev

RUN poetry config virtualenvs.in-project true

RUN ls /config/agentd

RUN cd /config/agentd && poetry env use /usr/bin/python3.12 && poetry install

# RUN mkdir -p /etc/services.d/agentd

# COPY uvicorn-run.sh /etc/services.d/agentd/run

# RUN chmod +x /etc/services.d/agentd/run