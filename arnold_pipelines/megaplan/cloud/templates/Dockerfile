FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYENV_ROOT=/root/.pyenv \
    PATH=/root/.pyenv/shims:/root/.pyenv/bin:/root/.local/bin:/usr/local/bin:/usr/bin:/bin \
    NVM_DIR=/root/.nvm \
    BUN_INSTALL=/root/.bun

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
      bubblewrap \
      ca-certificates \
      curl \
      git \
      jq \
      libbz2-dev \
      libffi-dev \
      liblzma-dev \
      libncurses-dev \
      libreadline-dev \
      libsqlite3-dev \
      libssl-dev \
      util-linux \
      openssh-client \
      passwd \
      procps \
      ripgrep \
      sudo \
      tmux \
      tzdata \
      unzip \
      vim \
      wget \
      xz-utils \
      zlib1g-dev \
      zsh \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p -m 755 /etc/apt/keyrings \
    && wget -nv -O /etc/apt/keyrings/githubcli-archive-keyring.gpg https://cli.github.com/packages/githubcli-archive-keyring.gpg \
    && chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
    && mkdir -p -m 755 /etc/apt/sources.list.d \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends gh \
    && rm -rf /var/lib/apt/lists/*

# pyenv + the supported default Python 3.11 and the immutable-generation
# interpreter used by runtime manifests.  Keep 3.11 as the image default;
# 3.13 is explicit and shared so existing generation venvs remain executable.
RUN curl -fsSL https://pyenv.run | bash \
    && /root/.pyenv/bin/pyenv install 3.11.11 \
    && PYTHON_CONFIGURE_OPTS=--enable-shared /root/.pyenv/bin/pyenv install 3.13.6 \
    && /root/.pyenv/bin/pyenv global 3.11.11 \
    && /root/.pyenv/shims/pip install --upgrade pip pipx

# Immutable dependency generations may point at either interpreter.  Register
# both pyenv shared-library directories with the dynamic loader and prove the
# newer generation interpreter can actually start during image construction.
RUN printf '%s\n' \
      /root/.pyenv/versions/3.11.11/lib \
      /root/.pyenv/versions/3.13.6/lib \
      > /etc/ld.so.conf.d/pyenv.conf \
    && ldconfig \
    && test -f /root/.pyenv/versions/3.13.6/lib/libpython3.13.so.1.0 \
    && /root/.pyenv/versions/3.13.6/bin/python -c 'import sys; assert sys.version_info[:2] == (3, 13)'

# nvm + Node 20
RUN curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash \
    && . "$NVM_DIR/nvm.sh" \
    && nvm install 20 \
    && nvm alias default 20 \
    && ln -s "$NVM_DIR/versions/node/$(nvm current)/bin/node" /usr/local/bin/node \
    && ln -s "$NVM_DIR/versions/node/$(nvm current)/bin/npm"  /usr/local/bin/npm \
    && ln -s "$NVM_DIR/versions/node/$(nvm current)/bin/npx"  /usr/local/bin/npx

# Bun runtime used by Shannon.
RUN curl -fsSL https://bun.sh/install | bash \
    && ln -sf /root/.bun/bin/bun /usr/local/bin/bun \
    && bun --version

# Codex CLI + Claude Code, symlinked into /usr/local/bin so non-interactive
# shells see them. Shannon is no longer installed via npm — the megaplan-vendored
# fork at megaplan/vendor/shannon/index.ts is invoked directly via ``bun``.
ARG CODEX_VERSION="0.144.3"
RUN . "$NVM_DIR/nvm.sh" \
    && npm i -g "@openai/codex@${CODEX_VERSION}" @anthropic-ai/claude-code @railway/cli@4.12.0 \
    && NVBIN=$(ls -d /root/.nvm/versions/node/*/bin | head -1) \
    && NODE_ROOT=$(dirname "$NVBIN") \
    && cp -a "$NODE_ROOT" /opt/zero-recovery-node \
    && chown -R root:root /opt/zero-recovery-node \
    && chmod -R a-w /opt/zero-recovery-node \
    && ln -sf /opt/zero-recovery-node/bin/node /usr/local/bin/node \
    && ln -sf /opt/zero-recovery-node/bin/npm /usr/local/bin/npm \
    && ln -sf /opt/zero-recovery-node/bin/npx /usr/local/bin/npx \
    && ln -sf /opt/zero-recovery-node/bin/codex  /usr/local/bin/codex \
    && ln -sf /opt/zero-recovery-node/bin/claude /usr/local/bin/claude \
    && ln -sf /opt/zero-recovery-node/bin/railway /usr/local/bin/railway \
    && test "$(codex --version)" = "codex-cli ${CODEX_VERSION}" \
    && claude --version \
    && railway --version

# The finite recovery runner imports its admitted checkout directly with
# PYTHONPATH and deliberately has no network during structural smoke. Bake its
# small source-runtime dependency floor into the image instead of installing
# the unrelated project currently published as `arnold` on PyPI. A caller may
# still supply an exact package or git spec for a self-contained image.
ARG MEGAPLAN_INSTALL_SPEC=""
RUN if [ -n "$MEGAPLAN_INSTALL_SPEC" ]; then \
      pip install --no-cache-dir "$MEGAPLAN_INSTALL_SPEC"; \
    else \
      pip install --no-cache-dir \
        "PyYAML>=6.0" \
        "pydantic>=2.0" \
        "python-ulid>=3.0" \
        "psutil>=5.9" \
        "httpx>=0.27" \
        "discord.py>=2.6,<3"; \
    fi \
    && python3 -c 'import discord, httpx, psutil, pydantic, ulid, yaml'
RUN /usr/sbin/groupadd --gid 65532 finite-model \
    && /usr/sbin/useradd --uid 65532 --gid 65532 --no-create-home --shell /usr/sbin/nologin finite-model \
    && mkdir -p /run/megaplan-zero-recovery \
    && chown root:root /run/megaplan-zero-recovery \
    && chmod 0711 /run/megaplan-zero-recovery \
    && chmod 0755 /tmp /var/tmp /dev/shm
${TOOLCHAIN_BLOCK}
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
COPY healthserver.py /usr/local/bin/healthserver.py
COPY wrappers/ /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh /usr/local/bin/mp-* /usr/local/bin/arnold-*

WORKDIR /workspace

EXPOSE 8080

CMD ["/usr/local/bin/entrypoint.sh"]
