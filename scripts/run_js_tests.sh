#!/bin/sh
# Pure frontend logic (formatting, grid, frame -> chart options, batching, chat state, markdown): needs only node.
cd "$(dirname "$0")/.." && node --test addons/levelix_board/tests/js/lib.test.mjs addons/levelix_board/tests/js/charts.test.mjs addons/levelix_board/tests/js/layout.test.mjs addons/levelix_ai_core/tests/js/lib.test.mjs 2>&1 | grep -E "^✖|^ℹ (tests|pass|fail)"
