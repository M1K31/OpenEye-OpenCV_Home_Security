// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

/**
 * Make a non-button element respond to the keyboard the way a button does.
 *
 * A `<div onClick={...}>` is invisible to keyboard and screen-reader users:
 * it cannot be focused and it does not react to Enter or Space. An audit on
 * 2026-08-22 found twelve such controls in this interface — cluster images,
 * feature cards, template cards, the timeline canvas — each of them the only
 * way to reach the action behind it.
 *
 * Prefer a real `<button>`. Reach for this only where the element cannot be a
 * button, usually because it wraps a large region or an image.
 *
 * Usage:
 *   <div onClick={openThing} onKeyDown={activateOnKey(openThing)}
 *        role="button" tabIndex={0} aria-label="Open thing">
 *
 * Space is prevented from its default so activating a control does not also
 * scroll the page — the behaviour a real button already has.
 */
export function activateOnKey(handler) {
  return (event) => {
    if (event.key !== 'Enter' && event.key !== ' ') return;
    event.preventDefault();
    if (typeof handler === 'function') handler(event);
  };
}

export default activateOnKey;
