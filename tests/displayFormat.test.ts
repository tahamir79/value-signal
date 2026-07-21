import assert from "node:assert/strict";
import test from "node:test";
import { formatDisplayDate, formatShareQuantity } from "../src/lib/display-format";

test("formatDisplayDate renders human dates without raw ISO timestamps", () => {
  assert.equal(formatDisplayDate("2026-07-20"), "Jul 20, 2026");
  assert.equal(formatDisplayDate("2026-07-21T03:51:42.553875+00:00"), "Jul 21, 2026");
});

test("formatShareQuantity keeps small implied-share allocations readable", () => {
  assert.equal(formatShareQuantity(1 / 43.48), "0.0230");
  assert.equal(formatShareQuantity(1.25), "1.250");
  assert.equal(formatShareQuantity(12.3456), "12.35");
  assert.equal(formatShareQuantity(10), "10");
});
