/* Pure hand-gesture geometry and timing helpers shared by the HUD runtime and tests. */
(() => {
  'use strict';
  const distance = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
  const isPinching = (landmarks, ratio = 0.38) => {
    if (!Array.isArray(landmarks) || landmarks.length < 21) return false;
    const palmWidth = Math.max(0.001, distance(landmarks[0], landmarks[9]));
    return distance(landmarks[4], landmarks[8]) < Math.max(0.025, palmWidth * ratio);
  };
  const isFist = landmarks => {
    if (!Array.isArray(landmarks) || landmarks.length < 21) return false;
    const wrist = landmarks[0];
    return [8, 12, 16, 20].every(index =>
      distance(landmarks[index], wrist) < distance(landmarks[index - 2], wrist) * 0.96
    );
  };
  const toViewport = (x, y, width, height, mirrored = true) => ({
    x: Math.max(0, Math.min(width - 1, (mirrored ? 1 - x : x) * width)),
    y: Math.max(0, Math.min(height - 1, y * height))
  });
  const updateSwipe = (x, now, state, options = {}) => {
    const minDelta = Number.isFinite(options.minDelta) ? options.minDelta : 0.18;
    const maxDuration = Number.isFinite(options.maxDuration) ? options.maxDuration : 650;
    const cooldown = Number.isFinite(options.cooldown) ? options.cooldown : 900;
    if (!Number.isFinite(x) || !Number.isFinite(now)) return { direction: 0, state };
    if (state.startX == null || now - state.startAt > maxDuration) {
      return { direction: 0, state: { ...state, startX: x, startAt: now } };
    }
    const delta = x - state.startX;
    if (Math.abs(delta) < minDelta || now - (state.lastAt ?? -Infinity) < cooldown) {
      return { direction: 0, state };
    }
    return {
      direction: delta > 0 ? 1 : -1,
      state: { ...state, startX: x, startAt: now, lastAt: now }
    };
  };
  const emptySwipeState = () => ({ startX: null, startAt: 0, lastAt: -Infinity });
  const api = Object.freeze({ distance, isPinching, isFist, toViewport, updateSwipe, emptySwipeState });
  if (typeof window !== 'undefined') window.JARVISGestureLogic = api;
  if (typeof globalThis !== 'undefined') globalThis.JARVISGestureLogic = api;
})();
