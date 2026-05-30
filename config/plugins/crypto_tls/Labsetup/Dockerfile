FROM handsonsecurity/seed-ubuntu:medium

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3-pip poppler-utils \
    && pip3 install --no-cache-dir pypdf \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
