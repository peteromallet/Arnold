#!/bin/bash
# ============================================================================
# scripts/agent-jury/run_jury.sh
# Pi-native jury execution script
# Runs the full blind deliberation pipeline using llama.cpp on a Raspberry Pi
# ============================================================================

set -euo pipefail

# ─── Configuration ───────────────────────────────────────────────────────────
JURY_DIR="$(cd "$(dirname "$0")" && pwd)"
SESSION_ID="jury_$(date +%Y%m%d_%H%M%S)"
DELIB_DIR="${JURY_DIR}/deliberations/${SESSION_ID}"
mkdir -p "${DELIB_DIR}/verdicts"

# Pi hardware settings
LLAMA_CLI="${LLAMA_CLI:-llama-cli}"
MODEL_DIR="${MODEL_DIR:-/home/pi/models}"
THREADS="${THREADS:-4}"
TEMP="${TEMP:-0.7}"
MAX_TOKENS_JUROR="${MAX_TOKENS_JUROR:-1024}"
MAX_TOKENS_SYNTH="${MAX_TOKENS_SYNTH:-2048}"
TIMEOUT_JUROR="${TIMEOUT_JUROR:-120}"
TIMEOUT_SYNTH="${TIMEOUT_SYNTH:-60}"

# Model assignments (different models for different jurors = more diversity)
# All should be Q4_K_M quants fitting in Pi 5's 8GB
MODEL_RISK="${MODEL_DIR}/llama-3.1-8b-instruct-Q4_K_M.gguf"
MODEL_ETHICS="${MODEL_DIR}/mistral-7b-instruct-v0.3-Q4_K_M.gguf"
MODEL_UTILITY="${MODEL_DIR}/phi-3-medium-4k-instruct-Q4_K_M.gguf"
MODEL_SYSTEMS="${MODEL_DIR}/llama-3.1-8b-instruct-Q4_K_M.gguf"
MODEL_DEVIL="${MODEL_DIR}/qwen2.5-7b-instruct-Q4_K_M.gguf"
MODEL_ORCH="${MODEL_DIR}/mistral-7b-instruct-v0.3-Q4_K_M.gguf"
MODEL_SYNTH="${MODEL_DIR}/llama-3.1-8b-instruct-Q4_K_M.gguf"

# ─── Helpers ──────────────────────────────────────────────────────────────────
log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "${DELIB_DIR}/audit.log"; }

run_juror() {
    local juror_name="$1"
    local model="$2"
    local prompt_file="$3"
    local proposal_file="$4"
    local output_file="${DELIB_DIR}/verdicts/${juror_name}.json"

    log "Dispatching ${juror_name}..."

    # Combine lens prompt + proposal into a single prompt
    local combined_prompt
    combined_prompt=$(cat "${prompt_file}" <(echo -e "\n\n--- PROPOSAL TO EVALUATE ---\n") "${proposal_file}")

    # Write combined prompt for audit
    echo "${combined_prompt}" > "${DELIB_DIR}/verdicts/${juror_name}_prompt.txt"

    # Run inference with timeout
    if timeout "${TIMEOUT_JUROR}" ${LLAMA_CLI} \
        -m "${model}" \
        -p "${combined_prompt}" \
        --temp "${TEMP}" \
        --threads "${THREADS}" \
        --ctx-size 4096 \
        --n-predict "${MAX_TOKENS_JUROR}" \
        --no-display-prompt \
        --json-schema "${JURY_DIR}/schemas/verdict_schema.json" \
        2>> "${DELIB_DIR}/verdicts/${juror_name}_stderr.log" \
        > "${output_file}"; then

        # Validate JSON
        if jq empty "${output_file}" 2>/dev/null; then
            log "  ${juror_name}: VERDICT RECEIVED (valid JSON)"
            return 0
        else
            log "  ${juror_name}: INVALID JSON — retrying once"
            # Retry once with error feedback
            local retry_prompt
            retry_prompt=$(cat <<EOF
Your previous response was not valid JSON. You MUST respond with ONLY valid JSON
conforming to the schema. No markdown, no explanation outside the JSON object.

Previous invalid response was:
$(cat "${output_file}")

Please provide your verdict as valid JSON now.
EOF
)
            if timeout "${TIMEOUT_JUROR}" ${LLAMA_CLI} \
                -m "${model}" \
                -p "${retry_prompt}" \
                --temp 0.3 \
                --threads "${THREADS}" \
                --ctx-size 4096 \
                --n-predict "${MAX_TOKENS_JUROR}" \
                --no-display-prompt \
                2>> "${DELIB_DIR}/verdicts/${juror_name}_stderr.log" \
                > "${output_file}"; then

                if jq empty "${output_file}" 2>/dev/null; then
                    log "  ${juror_name}: VERDICT RECEIVED (retry valid)"
                    return 0
                fi
            fi
            log "  ${juror_name}: RETRY FAILED — marking DID NOT SUBMIT"
            echo '{"verdict":"DID_NOT_SUBMIT","error":"Invalid JSON after retry"}' > "${output_file}"
            return 1
        fi
    else
        log "  ${juror_name}: TIMEOUT — marking DID NOT SUBMIT"
        echo '{"verdict":"DID_NOT_SUBMIT","error":"Timeout"}' > "${output_file}"
        return 1
    fi
}

# ─── Main Pipeline ────────────────────────────────────────────────────────────

PROPOSAL_FILE="${1:-${JURY_DIR}/example_proposal.md}"

if [[ ! -f "${PROPOSAL_FILE}" ]]; then
    echo "ERROR: Proposal file not found: ${PROPOSAL_FILE}"
    echo "Usage: $0 [proposal_file.md]"
    exit 1
fi

log "============================================"
log "AGENT JURY SESSION: ${SESSION_ID}"
log "Proposal: ${PROPOSAL_FILE}"
log "============================================"

# ─── Phase 1: Validation & Anonymization (Orchestrator) ───────────────────────

log "PHASE 1+2: Validating and anonymizing proposal..."

ORCH_PROMPT=$(cat <<'ORCHPROMPT'
You are the Jury Orchestrator. Read the following proposal. If it is valid
(non-empty, under 2000 words, articulates a decision with stakes),
anonymize it by stripping all proper names, locations, organizations,
gendered pronouns, and specific dates. Replace with generic labels.

Output ONLY the anonymized proposal text. No commentary.
If the proposal is invalid, output "REJECTED: <reason>" on a single line.

PROPOSAL:
ORCHPROMPT
)

# Run orchestrator
ANON_PROPOSAL=$(timeout "${TIMEOUT_SYNTH}" ${LLAMA_CLI} \
    -m "${MODEL_ORCH}" \
    -p "${ORCH_PROMPT}
$(cat "${PROPOSAL_FILE}")" \
    --temp 0.3 \
    --threads "${THREADS}" \
    --ctx-size 4096 \
    --n-predict 1024 \
    --no-display-prompt \
    2>/dev/null)

if echo "${ANON_PROPOSAL}" | grep -q "^REJECTED:"; then
    log "PROPOSAL REJECTED: ${ANON_PROPOSAL}"
    echo "${ANON_PROPOSAL}"
    exit 1
fi

echo "${ANON_PROPOSAL}" > "${DELIB_DIR}/anonymized_proposal.txt"
log "Anonymization complete."

# ─── Phase 3+4: Parallel Blind Deliberation ───────────────────────────────────

log "PHASE 3+4: Launching blind parallel jury deliberation..."

JUROR_FAILURES=0

# Run all jurors in parallel background processes
run_juror "risk_analyst" "${MODEL_RISK}" \
    "${JURY_DIR}/jurors/risk_analyst.txt" \
    "${DELIB_DIR}/anonymized_proposal.txt" &
PID_RISK=$!

run_juror "ethicist" "${MODEL_ETHICS}" \
    "${JURY_DIR}/jurors/ethicist.txt" \
    "${DELIB_DIR}/anonymized_proposal.txt" &
PID_ETHICS=$!

run_juror "utility_maximizer" "${MODEL_UTILITY}" \
    "${JURY_DIR}/jurors/utility_maximizer.txt" \
    "${DELIB_DIR}/anonymized_proposal.txt" &
PID_UTIL=$!

run_juror "systems_thinker" "${MODEL_SYSTEMS}" \
    "${JURY_DIR}/jurors/systems_thinker.txt" \
    "${DELIB_DIR}/anonymized_proposal.txt" &
PID_SYS=$!

run_juror "devils_advocate" "${MODEL_DEVIL}" \
    "${JURY_DIR}/jurors/devils_advocate.txt" \
    "${DELIB_DIR}/anonymized_proposal.txt" &
PID_DEVIL=$!

# Wait for all
for pid in $PID_RISK $PID_ETHICS $PID_UTIL $PID_SYS $PID_DEVIL; do
    if ! wait "${pid}"; then
        ((JUROR_FAILURES++))
    fi
done

log "All jurors complete. Failures: ${JUROR_FAILURES}"

VALID_VERDICTS=$((5 - JUROR_FAILURES))
if [[ ${VALID_VERDICTS} -lt 3 ]]; then
    log "FATAL: Insufficient valid verdicts (${VALID_VERDICTS} < 3 required)"
    echo '{"final_verdict":"IMPASSE","error":"Insufficient valid verdicts"}' \
        > "${DELIB_DIR}/final_judgment.json"
    exit 1
fi

# ─── Phase 5: Anonymize juror identities for synthesis ────────────────────────

log "PHASE 5: Anonymizing juror identities for blind synthesis..."

# Collect valid verdicts, assign randomized labels
JUROR_LABELS=("Juror A" "Juror B" "Juror C" "Juror D" "Juror E")
# Shuffle labels
mapfile -t SHUFFLED < <(printf '%s\n' "${JUROR_LABELS[@]}" | shuf)

SYNTH_INPUT="You are the Blind Synthesizer. Below are anonymized verdicts from
multiple jurors on a blind jury. You do NOT know which lens each juror used.
You must synthesize these into a final judgment per the blind_synthesizer protocol.

ANONYMIZED PROPOSAL:
${ANON_PROPOSAL}

JUROR VERDICTS:
"

LABEL_IDX=0
for verdict_file in "${DELIB_DIR}"/verdicts/*.json; do
    juror_basename=$(basename "${verdict_file}" .json)
    # Skip non-verdict files (prompts, stderr)
    if [[ "${juror_basename}" == *_prompt ]] || [[ "${juror_basename}" == *_stderr ]]; then
        continue
    fi

    verdict_content=$(cat "${verdict_file}")

    # Skip DID_NOT_SUBMIT
    if echo "${verdict_content}" | jq -e '.verdict == "DID_NOT_SUBMIT"' 2>/dev/null; then
        continue
    fi

    SYNTH_INPUT+="
=== ${SHUFFLED[$LABEL_IDX]} ===
${verdict_content}
"
    ((LABEL_IDX++))
done

echo "${SYNTH_INPUT}" > "${DELIB_DIR}/synthesizer_input.txt"
log "Prepared ${LABEL_IDX} verdicts for synthesis."

# ─── Phase 6: Blind Synthesis ─────────────────────────────────────────────────

log "PHASE 6: Running Blind Synthesizer..."

SYNTH_PROMPT=$(cat "${JURY_DIR}/blind_synthesizer.txt")
SYNTH_PROMPT+="

${SYNTH_INPUT}"

if timeout "${TIMEOUT_SYNTH}" ${LLAMA_CLI} \
    -m "${MODEL_SYNTH}" \
    -p "${SYNTH_PROMPT}" \
    --temp 0.4 \
    --threads "${THREADS}" \
    --ctx-size 8192 \
    --n-predict "${MAX_TOKENS_SYNTH}" \
    --no-display-prompt \
    --json-schema "${JURY_DIR}/schemas/final_judgment_schema.json" \
    2>"${DELIB_DIR}/synthesizer_stderr.log" \
    > "${DELIB_DIR}/final_judgment.json"; then

    if jq empty "${DELIB_DIR}/final_judgment.json" 2>/dev/null; then
        log "Synthesis complete. Valid final judgment produced."
    else
        log "WARNING: Synthesis produced invalid JSON. Saving raw output."
        cp "${DELIB_DIR}/final_judgment.json" "${DELIB_DIR}/final_judgment_raw.txt"
    fi
else
    log "ERROR: Synthesis timed out."
    echo '{"final_verdict":"IMPASSE","error":"Synthesis timeout"}' \
        > "${DELIB_DIR}/final_judgment.json"
fi

# ─── Phase 7: Human Summary ───────────────────────────────────────────────────

log "PHASE 7: Generating human-readable summary..."

SUMMARY_PROMPT=$(cat <<'SUMMARY'
Based on the following final judgment JSON, write a concise markdown summary
suitable for a human decision-maker. Include:

1. **Verdict**: The final decision and confidence
2. **Jury Split**: How jurors divided
3. **Key Agreements**: What everyone agreed on
4. **Critical Dissents**: Any dissenting concerns that nearly or did override the majority
5. **Fatal Flaws**: Any fatal flaws identified
6. **Action Items**: What to do next
7. **Missing Information**: What we need to know before proceeding

Keep it under 500 words. Use clear, direct language.

FINAL JUDGMENT:
SUMMARY
)

SUMMARY_PROMPT+=$(cat "${DELIB_DIR}/final_judgment.json")

timeout 30 ${LLAMA_CLI} \
    -m "${MODEL_SYNTH}" \
    -p "${SUMMARY_PROMPT}" \
    --temp 0.3 \
    --threads "${THREADS}" \
    --ctx-size 4096 \
    --n-predict 768 \
    --no-display-prompt \
    > "${DELIB_DIR}/summary.md" 2>/dev/null

log "============================================"
log "JURY DELIBERATION COMPLETE"
log "Session: ${SESSION_ID}"
log "Final judgment: ${DELIB_DIR}/final_judgment.json"
log "Human summary:   ${DELIB_DIR}/summary.md"
log "Full audit log:  ${DELIB_DIR}/audit.log"
log "============================================"

# Print the verdict summary to stdout
if [[ -f "${DELIB_DIR}/summary.md" ]]; then
    echo ""
    echo "═══════════════════════════════════════════"
    cat "${DELIB_DIR}/summary.md"
    echo "═══════════════════════════════════════════"
fi
