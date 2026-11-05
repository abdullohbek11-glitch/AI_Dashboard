#!/bin/sh
# Run the levelix_ai_core tests in the dev container and print only the verdict.
export DOCKER_HOST="unix://$HOME/.colima/default/docker.sock"
MODULE="${1:-levelix_ai_core}"
docker exec levelix-aidash odoo -d aidash -u "$MODULE" --test-tags "$MODULE" --test-enable \
  --http-port=8099 --stop-after-init --log-level=info > /tmp/aidash_ai_test.log 2>&1
grep -E "FAIL:|ERROR:|Traceback|Error:|AssertionError" -A8 /tmp/aidash_ai_test.log | grep -v "Starting" | head -${LINES_MAX:-60}
grep -E "odoo.tests.stats|tests when loading|failures, " /tmp/aidash_ai_test.log
