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
        python3-venv \
        python3-pip \
    && rm -rf /var/lib/apt/lists/*

ENV AGENTLENS_PYAUTOGUI_PYTHON=/opt/agentlens-pyautogui/bin/python \
    DISPLAY_WIDTH=1920 \
    DISPLAY_HEIGHT=1080

RUN python3 -m venv /opt/agentlens-pyautogui \
    && /opt/agentlens-pyautogui/bin/pip install --no-cache-dir pyautogui pyperclip \
    && /opt/agentlens-pyautogui/bin/python -c \
        "import importlib.util; assert importlib.util.find_spec('pyautogui'); assert importlib.util.find_spec('pyperclip')" \
    && chmod -R a+rX /opt/agentlens-pyautogui

# This image only provides generic desktop automation dependencies. App-specific
# tasks should extend it and install Unity, Blender, Tableau, LibreOffice, etc.
