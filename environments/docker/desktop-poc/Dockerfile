ARG BASE_IMAGE=ghcr.io/agent-infra/sandbox:latest
FROM ${BASE_IMAGE}

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        imagemagick \
        scrot \
        wmctrl \
        x11-utils \
        xdotool \
        python3-pip \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --no-cache-dir pyautogui pyperclip \
    || python3 -m pip install --no-cache-dir --break-system-packages pyautogui pyperclip

# This image only provides generic desktop automation dependencies. App-specific
# tasks should extend it and install Unity, Blender, Tableau, LibreOffice, etc.
