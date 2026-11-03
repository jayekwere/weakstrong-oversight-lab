import test from "node:test";
import assert from "node:assert/strict";
import {
  escapeHTML,
  filterRows,
  paginate,
  isError,
  percentage,
} from "../src/weakstrong/static/utils.mjs";
test("untrusted trace text is escaped", () => {
  assert.equal(escapeHTML('<script>"&'), "&lt;script&gt;&quot;&amp;");
});
test("strategy and category filters compose", () => {
  const rows = [
    { strategy: "a", family: "x" },
    { strategy: "b", family: "x" },
    { strategy: "a", family: "y" },
  ];
  assert.equal(filterRows(rows, "a", "x").length, 1);
  assert.equal(filterRows(rows, "all", "x").length, 2);
  assert.equal(paginate(rows, 1, 2).length, 1);
});
test("outcomes distinguish false negatives and deferrals", () => {
  assert.ok(isError({ label: true, prediction: false }));
  assert.ok(!isError({ label: true, prediction: null }));
  assert.equal(percentage(null), "N/A");
  assert.equal(percentage(0.25), "25.0%");
});
