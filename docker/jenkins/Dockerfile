# Jenkins controller with the pipeline's tools baked in, all pinned.
# The official image deliberately ships none of these; installing them
# into a running container would evaporate on every recreation, so they
# live in an image built by the Ansible jenkins role on the CI node.
#
# docker CLI only — the daemon is the host's, reached through the
# mounted socket. kubectl matches the cluster minor (v1.36).
FROM jenkins/jenkins:2.568.1-lts-jdk21

ARG DOCKER_CLI_VERSION=29.7.1
ARG HELM_VERSION=v3.19.1
ARG KUBECTL_VERSION=v1.36.3
ARG TRIVY_VERSION=0.73.0

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && curl -fsSL "https://download.docker.com/linux/static/stable/x86_64/docker-${DOCKER_CLI_VERSION}.tgz" \
       | tar -xz --strip-components=1 -C /usr/local/bin docker/docker \
    && curl -fsSL "https://get.helm.sh/helm-${HELM_VERSION}-linux-amd64.tar.gz" \
       | tar -xz --strip-components=1 -C /usr/local/bin linux-amd64/helm \
    && curl -fsSL -o /usr/local/bin/kubectl "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl" \
    && chmod 0755 /usr/local/bin/kubectl \
    && curl -fsSL "https://github.com/aquasecurity/trivy/releases/download/v${TRIVY_VERSION}/trivy_${TRIVY_VERSION}_Linux-64bit.tar.gz" \
       | tar -xz -C /usr/local/bin trivy
USER jenkins
