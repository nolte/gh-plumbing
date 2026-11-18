#!/usr/bin/env bash
# Assertion for the refusal jobs of .github/workflows/test-setup-vale.yml.
#
# The action ran with `continue-on-error: true`. This passes only when it
# failed, reported the EXPECTED result, and left no `vale` of its own on PATH
# or under RUNNER_TEMP -- so the job is green exactly when the action refused.
#
# Environment: OUTCOME (steps.<id>.outcome), RESULT (steps.<id>.outputs.result),
# EXPECTED, RUNNER_TEMP.
set -euo pipefail

: "${RUNNER_TEMP:?RUNNER_TEMP must be set}"
status=0

if [[ "${OUTCOME:-}" != "failure" ]]; then
  echo "::error::The action's outcome is '${OUTCOME:-}', expected 'failure'. It accepted what it must refuse."
  status=1
fi
if [[ "${RESULT:-}" != "${EXPECTED:?EXPECTED must be set}" ]]; then
  echo "::error::The action reported result '${RESULT:-}', expected '${EXPECTED}'."
  status=1
fi
if where=$(command -v vale) && [[ "$where" == "$RUNNER_TEMP"/* ]]; then
  echo "::error::A vale from this run is on PATH: ${where}"
  status=1
fi
leftover=$(find "$RUNNER_TEMP" -name vale -type f -print -quit)
if [[ -n "$leftover" ]]; then
  echo "::error::A vale binary was left under RUNNER_TEMP: ${leftover}"
  status=1
fi

if [[ "$status" -eq 0 ]]; then
  echo "Refused as expected: outcome=${OUTCOME}, result=${RESULT}, no vale on PATH or under RUNNER_TEMP."
fi
exit "$status"
