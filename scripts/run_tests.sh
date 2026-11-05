#!/bin/sh
# Run the levelix_board tests in the dev container and print only the verdict.
#   scripts/run_tests.sh [module] [test-tags]
export DOCKER_HOST="unix://$HOME/.colima/default/docker.sock"
MODULE="${1:-levelix_board}"
TAGS="${2:-/$MODULE}"
docker exec levelix-aidash odoo -d aidash -u "$MODULE" --test-tags "$TAGS" --test-enable \
  --http-port=8099 --stop-after-init --log-level=info > /tmp/aidash_test.log 2>&1
grep -E "FAIL:|ERROR:|Traceback|Error:|AssertionError" -A8 /tmp/aidash_test.log | grep -v "Starting" | head -${LINES_MAX:-60}
grep -E "odoo.tests.stats|tests when loading|failures, " /tmp/aidash_test.log
