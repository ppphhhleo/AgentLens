ARG BASE_IMAGE=agentlens/desktop-poc:latest
FROM ${BASE_IMAGE}

USER root

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        blender \
        default-jre \
        weka \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /workspace/data /workspace/output \
    && if [ -f /usr/share/doc/weka/examples/iris.arff ]; then \
        cp /usr/share/doc/weka/examples/iris.arff /workspace/data/iris.arff; \
    elif [ -f /usr/share/weka/data/iris.arff ]; then \
        cp /usr/share/weka/data/iris.arff /workspace/data/iris.arff; \
    fi

# This image is intentionally small in scope: it supports Weka and Blender
# smoke workflows for AgentLens desktop trajectory capture. It is not meant to
# reproduce the full Workflow-GYM VM suite.
