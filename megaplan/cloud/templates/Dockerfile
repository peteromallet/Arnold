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
      openssh-client \
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

# pyenv + Python 3.11
RUN curl -fsSL https://pyenv.run | bash \
    && /root/.pyenv/bin/pyenv install 3.11.11 \
    && /root/.pyenv/bin/pyenv global 3.11.11 \
    && /root/.pyenv/shims/pip install --upgrade pip pipx

# nvm + Node 20
RUN curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash \
    && . "$NVM_DIR/nvm.sh" \
    && nvm install 20 \
    && nvm alias default 20 \
    && ln -s "$NVM_DIR/versions/node/$(nvm current)/bin/node" /usr/local/bin/node \
    && ln -s "$NVM_DIR/versions/node/$(nvm current)/bin/npm"  /usr/local/bin/npm \
    && ln -s "$NVM_DIR/versions/node/$(nvm current)/bin/npx"  /usr/local/bin/npx

# Codex CLI + Claude Code + Shannon, symlinked into /usr/local/bin so non-interactive shells see them.
RUN . "$NVM_DIR/nvm.sh" \
    && npm i -g @openai/codex @anthropic-ai/claude-code @dexh/shannon@0.0.2 \
    && NVBIN=$(ls -d /root/.nvm/versions/node/*/bin | head -1) \
    && ln -sf "$NVBIN/codex"  /usr/local/bin/codex \
    && ln -sf "$NVBIN/claude" /usr/local/bin/claude \
    && ln -sf "$NVBIN/shannon" /usr/local/bin/shannon \
    && codex --version \
    && claude --version \
    && shannon --version

# Bun runtime used by Shannon.
RUN curl -fsSL https://bun.sh/install | bash \
    && ln -sf /root/.bun/bin/bun /usr/local/bin/bun \
    && bun --version

# Megaplan from source
RUN pip install --no-cache-dir git+https://github.com/peteromallet/megaplan.git \
    && megaplan --help > /dev/null
${TOOLCHAIN_BLOCK}
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
COPY healthserver.py /usr/local/bin/healthserver.py
COPY wrappers/ /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh /usr/local/bin/mp-*

WORKDIR /workspace

EXPOSE 8080

CMD ["/usr/local/bin/entrypoint.sh"]
