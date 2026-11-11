const test = require('node:test');
const assert = require('node:assert/strict');
require('./jarvis_gesture_logic.js');
const logic = globalThis.JARVISGestureLogic;

function hand() {
  return Array.from({ length: 21 }, (_, index) => ({ x: 0.5 + index * 0.001, y: 0.5 }));
}

test('pinch detection adapts to palm size and rejects missing landmarks', () => {
  const points = hand();
  points[0] = { x: 0.5, y: 0.8 };
  points[9] = { x: 0.5, y: 0.5 };
  points[4] = { x: 0.51, y: 0.45 };
  points[8] = { x: 0.52, y: 0.45 };
  assert.equal(logic.isPinching(points), true);
  points[8] = { x: 0.8, y: 0.45 };
  assert.equal(logic.isPinching(points), false);
  assert.equal(logic.isPinching([]), false);
});

test('fist detection requires all four fingertips to curl toward the wrist', () => {
  const points = hand();
  points[0] = { x: 0.5, y: 0.8 };
  for (const [tip, joint] of [[8, 6], [12, 10], [16, 14], [20, 18]]) {
    points[joint] = { x: 0.5, y: 0.55 };
    points[tip] = { x: 0.5, y: 0.6 };
  }
  assert.equal(logic.isFist(points), true);
  points[20] = { x: 0.5, y: 0.2 };
  assert.equal(logic.isFist(points), false);
});

test('viewport coordinates mirror the preview and stay inside the screen', () => {
  assert.deepEqual(logic.toViewport(0.2, 0.4, 1000, 500), { x: 800, y: 200 });
  assert.deepEqual(logic.toViewport(2, -1, 1000, 500), { x: 0, y: 0 });
});

test('swipe detection requires movement in a time window and respects cooldown', () => {
  let state = logic.emptySwipeState();
  let result = logic.updateSwipe(0.5, 1000, state);
  state = result.state;
  assert.equal(result.direction, 0);
  result = logic.updateSwipe(0.75, 1300, state);
  assert.equal(result.direction, 1);
  state = result.state;
  result = logic.updateSwipe(0.4, 1500, state);
  assert.equal(result.direction, 0);
  result = logic.updateSwipe(0.4, 2300, state);
  assert.equal(result.direction, 0);
  state = result.state;
  result = logic.updateSwipe(0.1, 2500, state);
  assert.equal(result.direction, -1);
});

test('slow drift outside the swipe window does not activate', () => {
  let state = logic.emptySwipeState();
  state = logic.updateSwipe(0.3, 1000, state).state;
  const result = logic.updateSwipe(0.8, 1800, state);
  assert.equal(result.direction, 0);
  assert.equal(result.state.startX, 0.8);
});
