// Moving and resizing widgets while editing. Run: node --test addons/levelix_board/tests/js
import assert from "node:assert/strict";
import test from "node:test";

import { appended, cellsMoved, gridOf, MIN_H, MIN_W, moved, pitchOf, resized, settle } from "../../static/src/lib/layout.js";

const cell = (id, x, y, w, h) => ({ id, x, y, w, h });
const at = (cells, id) => cells.find((c) => c.id === id);

test("the pitch of the grid and a pointer movement in whole cells", () => {
    const pitch = pitchOf(1500, 16, 40, 24); // (1500 - 23 * 16) / 24 + 16 = 63.17
    assert.ok(Math.abs(pitch.col - 63.1667) < 0.01);
    assert.equal(pitch.row, 56);
    assert.deepEqual(cellsMoved(130, 60, pitch), { dx: 2, dy: 1 });
    assert.deepEqual(cellsMoved(-100, -20, pitch), { dx: -2, dy: 0 });
    assert.deepEqual(cellsMoved(20, 20, pitch), { dx: 0, dy: 0 }); // less than half a step: it stays
});

test("a widget dropped on another pushes it down; nothing overlaps afterwards", () => {
    const cells = [cell("a", 0, 0, 12, 4), cell("b", 12, 0, 12, 4), cell("c", 0, 4, 12, 4)];
    const out = moved(cells, "b", -12, 0); // b onto a
    assert.deepEqual(at(out, "b"), cell("b", 0, 0, 12, 4)); // the dropped one stays where it was put
    assert.deepEqual(at(out, "a"), cell("a", 0, 4, 12, 4)); // a gave way
    assert.deepEqual(at(out, "c"), cell("c", 0, 8, 12, 4)); // and c below it
    for (const x of out) {
        for (const y of out) {
            if (x !== y) {
                assert.ok(!(x.x < y.x + y.w && y.x < x.x + x.w && x.y < y.y + y.h && y.y < x.y + x.h), `${x.id} overlaps ${y.id}`);
            }
        }
    }
});

test("gaps close upwards", () => {
    const out = settle([cell("a", 0, 0, 12, 4), cell("b", 0, 20, 12, 4), cell("c", 12, 9, 12, 4)]);
    assert.deepEqual(at(out, "b"), cell("b", 0, 4, 12, 4));
    assert.deepEqual(at(out, "c"), cell("c", 12, 0, 12, 4));
});

test("a widget cannot leave the page", () => {
    const cells = [cell("a", 6, 2, 12, 4)];
    assert.deepEqual(at(moved(cells, "a", 50, 0), "a"), cell("a", 12, 2, 12, 4)); // stopped at the right edge; the dropped widget stays where it was put
    assert.equal(at(moved(cells, "a", -50, -50), "a").x, 0);
    assert.equal(at(moved(cells, "a", 0, -50), "a").y, 0);
});

test("resizing keeps the minimum and the right edge of the page", () => {
    const cells = [cell("a", 18, 0, 6, 4)];
    assert.equal(at(resized(cells, "a", 10, 0), "a").w, 6); // already at the right edge
    assert.equal(at(resized(cells, "a", -10, 0), "a").w, MIN_W);
    assert.equal(at(resized(cells, "a", 0, -10), "a").h, MIN_H);
    assert.equal(at(resized(cells, "a", 0, 5), "a").h, 9);
});

test("making one bigger moves the neighbours instead of covering them", () => {
    const cells = [cell("a", 0, 0, 12, 4), cell("b", 12, 0, 12, 4), cell("c", 0, 4, 24, 4)];
    const out = resized(cells, "a", 6, 2); // a grows into b's columns and down
    assert.deepEqual(at(out, "a"), cell("a", 0, 0, 18, 6));
    assert.ok(at(out, "b").y >= 6 || at(out, "b").x >= 18); // b is out of the way
    assert.ok(at(out, "c").y >= 6);
});

test("the result is the same whichever order the widgets come in", () => {
    const cells = [cell("a", 0, 0, 12, 4), cell("b", 12, 0, 12, 4), cell("c", 0, 4, 12, 4)];
    const one = settle(moved(cells, "b", -12, 0), "b");
    const two = moved([...cells].reverse(), "b", -12, 0);
    assert.deepEqual(gridOf(one), gridOf(two));
});

test("what is stored, and where a new widget goes", () => {
    assert.deepEqual(gridOf([cell("a", 1, 2, 3, 4)]), { a: { x: 1, y: 2, w: 3, h: 4 } });
    const out = appended([cell("a", 0, 0, 12, 4), cell("b", 12, 0, 12, 6)], "n", { w: 30, h: 8 });
    assert.deepEqual(at(out, "n"), cell("n", 0, 6, 24, 8)); // below everything, never wider than the page
    assert.deepEqual(appended([], "n", { w: 12, h: 8 }), [cell("n", 0, 0, 12, 8)]);
});
