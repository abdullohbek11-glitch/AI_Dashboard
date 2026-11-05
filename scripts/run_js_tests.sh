#!/bin/sh
# Pure frontend logic (formatting, grid, frame -> chart options, batching): needs only node.
cd "$(dirname "$0")/.." && node --test addons/levelix_board/tests/js/lib.test.mjs 2>&1 | grep -E "^✖|^ℹ (tests|pass|fail)"
