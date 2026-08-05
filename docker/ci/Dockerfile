# CI agent image: the pinned production python base with the dev
# toolchain (ruff, pytest, app dependencies) preinstalled, so pipeline
# stages sync a delta instead of downloading the world every build.
# Built on the CI node by the Ansible jenkins role, same pattern as the
# controller image. The build context is the flat directory Ansible
# assembles: this file plus the two requirements files.
#
# Jenkins runs agent containers as -u 1000:1000; python:slim has no
# such user, which is exactly how build #1 died (pip had no writable
# HOME). The ci user exists so uid 1000 has a home, and delta installs
# go to ~/.local via PATH.
FROM python:3.12.12-slim-bookworm

RUN groupadd --gid 1000 ci \
    && useradd --uid 1000 --gid ci --create-home ci

ENV HOME=/home/ci \
    PATH=/home/ci/.local/bin:$PATH \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

COPY requirements.txt requirements-dev.txt ./
RUN pip install -r requirements-dev.txt
