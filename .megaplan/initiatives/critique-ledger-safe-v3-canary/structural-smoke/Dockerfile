ARG PRODUCTION_IMAGE
FROM ${PRODUCTION_IMAGE}

COPY fake_codex.py /opt/zero-recovery-node/bin/codex-offline-structural-smoke
COPY verify_offline_smoke.py /usr/local/bin/verify-zero-recovery-offline-smoke
RUN rm -f /opt/zero-recovery-node/bin/codex \
    && mv /opt/zero-recovery-node/bin/codex-offline-structural-smoke \
        /opt/zero-recovery-node/bin/codex \
    && chown root:root /opt/zero-recovery-node/bin/codex \
    && chmod 0555 /opt/zero-recovery-node/bin/codex \
    && chown root:root /usr/local/bin/verify-zero-recovery-offline-smoke \
    && chmod 0555 /usr/local/bin/verify-zero-recovery-offline-smoke

LABEL org.openai.arnold.evidence="offline-structural-smoke-not-model-provider-proof"
