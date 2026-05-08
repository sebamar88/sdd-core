const assert = require("node:assert/strict");
const { sum } = require("./app");

assert.equal(sum(2, 2), 4);
console.log("PASS: sum(2, 2) === 4");
