import { test } from "node:test";
import assert from "node:assert/strict";
import { hello } from "../src/index.mjs";

test("hello", () => {
  assert.equal(hello("ノック"), "こんにちは、ノック");
});
