// Copyright (c) 2025 Smart Industries LLC (Mikel Smart)
// This file is part of OpenEye-OpenCV_Home_Security
//
// Assigning detections to a person must actually move them.
//
// The defect
// ----------
// The assign handler collects `d.id` from each detection and posts them to
// /faces/history/bulk-reassign. Every call site built its own object literal by
// hand, and all five omitted `id` — so the collected list was empty, a
// `length > 0` guard skipped the reassignment entirely, and the photo upload
// that follows still succeeded. The interface then reported "Assigned N
// detections" while the detection rows had not moved.
//
// Confirmed from the application log: creating a person from the detections
// view produced only
//     POST /api/faces/people/Mikayla/photos
// with no bulk-reassign call, twice, on two separate attempts.
//
// These tests cover the two shapes that carry the failure: what selection
// stores, and what the assign handler extracts. Both are plain data
// transformations, so they are tested directly rather than through the page.

import { describe, it, expect } from 'vitest';

/**
 * Mirrors toggleSelect: the map key is the detection id, and the stored value
 * must carry it regardless of what the caller passed.
 */
function storeSelection(previous, key, detection) {
  const next = { ...previous };
  if (next[key]) delete next[key];
  else next[key] = { id: key, ...detection };
  return next;
}

/** Mirrors the id collection in assignDetections. */
function collectFaceIds(detections) {
  return detections.map(d => d.id).filter(id => id !== undefined && id !== null);
}

describe('selection carries the detection id', () => {
  it('records the id even when the caller omits it', () => {
    // Exactly what both call sites passed: no id field.
    const fromCallSite = {
      snapshot_path: 'unknown/face_1.jpg',
      cluster_id: null,
      name: 'Unknown',
    };

    const selected = storeSelection({}, 42, fromCallSite);

    expect(selected[42].id).toBe(42);
    expect(collectFaceIds(Object.values(selected))).toEqual([42]);
  });

  it('does not overwrite an id the caller did supply', () => {
    const selected = storeSelection({}, 7, { id: 7, name: 'Yaleska' });
    expect(selected[7].id).toBe(7);
  });

  it('still removes an entry when toggled off', () => {
    const once = storeSelection({}, 1, { name: 'Unknown' });
    const twice = storeSelection(once, 1, { name: 'Unknown' });
    expect(twice[1]).toBeUndefined();
    expect(collectFaceIds(Object.values(twice))).toEqual([]);
  });
});

describe('the assign handler can identify what it was given', () => {
  it('collects ids from detections built by the assign buttons', () => {
    // The three "Assign to person…" call sites, with the id now included.
    const detections = [
      { id: 101, snapshot_path: 'a.jpg', cluster_id: null, name: 'Unknown' },
      { id: 102, snapshot_path: 'b.jpg', cluster_id: 5, name: 'unknown1' },
    ];

    expect(collectFaceIds(detections)).toEqual([101, 102]);
  });

  it('reproduces the bug when the id is dropped', () => {
    // The literal that shipped. Kept as a test so the failure mode is visible
    // rather than described: this is what produced a success message and no
    // reassignment.
    const asShipped = [
      { snapshot_path: 'a.jpg', cluster_id: null, name: 'Unknown' },
    ];

    expect(collectFaceIds(asShipped)).toEqual([]);
  });

  it('treats id 0 as a real id', () => {
    // `filter(Boolean)` would discard it. The guard tests for undefined and
    // null specifically, and must keep doing so.
    expect(collectFaceIds([{ id: 0, name: 'Unknown' }])).toEqual([0]);
  });

  it('keeps ids that are strings, as some endpoints return', () => {
    expect(collectFaceIds([{ id: '55', name: 'Unknown' }])).toEqual(['55']);
  });
});

// ---------------------------------------------------------------------------
// The two id conventions
// ---------------------------------------------------------------------------
//
// Fixing the missing id exposed a second defect underneath it. Two views load
// detections in two shapes and both reach the same handler: the person view
// passes API rows through, so `id` is numeric, while the combined view merges
// faces and objects and prefixes the ids to keep them distinct. Sending
// "face-123" to an endpoint declaring `face_ids: List[int]` is rejected with
// 422, which the interface rendered as "[object Object]".

import { faceIdOf } from '../DetectionsPage.jsx';
import { describeApiError } from '../../utils/apiError.js';

describe('resolving a face id from either convention', () => {
  it('reads a numeric id, as the person view supplies', () => {
    expect(faceIdOf({ id: 123 })).toBe(123);
  });

  it('reads a prefixed id, as the combined view supplies', () => {
    expect(faceIdOf({ id: 'face-123' })).toBe(123);
  });

  it('prefers an explicit face_id when present', () => {
    expect(faceIdOf({ id: 'face-123', face_id: 123 })).toBe(123);
  });

  it('refuses an object detection', () => {
    // A vehicle cannot be assigned to a person, and "object-45" must never be
    // sent as a face id.
    expect(faceIdOf({ id: 'object-45' })).toBeNull();
  });

  it('keeps id 0', () => {
    expect(faceIdOf({ id: 0 })).toBe(0);
    expect(faceIdOf({ id: 'face-0' })).toBe(0);
  });

  it('returns null rather than guessing at an unknown shape', () => {
    expect(faceIdOf({ id: 'cluster-7' })).toBeNull();
    expect(faceIdOf({})).toBeNull();
    expect(faceIdOf(null)).toBeNull();
  });
});

describe('reporting an API failure', () => {
  it('renders a validation array instead of [object Object]', () => {
    const error = {
      response: { data: { detail: [
        { type: 'int_parsing', loc: ['body', 'face_ids', 0],
          msg: 'Input should be a valid integer', input: 'face-123' },
      ] } },
    };

    const message = describeApiError(error);

    expect(message).not.toContain('[object Object]');
    expect(message).toContain('face_ids.0');
    expect(message).toContain('valid integer');
    expect(message).toContain('face-123');
  });

  it('joins several validation errors', () => {
    const error = {
      response: { data: { detail: [
        { loc: ['body', 'face_ids', 0], msg: 'bad', input: 'face-1' },
        { loc: ['body', 'face_ids', 1], msg: 'bad', input: 'face-2' },
      ] } },
    };
    expect(describeApiError(error).split(';')).toHaveLength(2);
  });

  it('passes a plain string detail through unchanged', () => {
    expect(describeApiError({ response: { data: { detail: 'No faces found' } } }))
      .toBe('No faces found');
  });

  it('falls back to the error message when there is no detail', () => {
    expect(describeApiError({ message: 'Network Error' })).toBe('Network Error');
  });

  it('always produces something to show', () => {
    expect(describeApiError({})).toBeTruthy();
    expect(describeApiError(null)).toBeTruthy();
  });
});

describe('the person view uses a third prefix', () => {
  it('unwraps the pd- key the person list builds', () => {
    // `pd-${detection.id ?? index}`, invented for list-key uniqueness and then
    // stored as the id. Reported from the interface as "none of the selected
    // detections is a face" over three plainly visible faces.
    expect(faceIdOf({ id: 'pd-123' })).toBe(123);
  });

  it('prefers the real id over the list key when both are present', () => {
    expect(faceIdOf({ id: 'pd-9', face_id: 123 })).toBe(123);
  });

  it('still refuses an object, whatever the prefix looks like', () => {
    expect(faceIdOf({ id: 'object-45' })).toBeNull();
    expect(faceIdOf({ id: 'pd-abc' })).toBeNull();
  });
});

describe('the fallback message', () => {
  it('is used when the server said nothing useful', () => {
    expect(describeApiError({}, 'Failed to enable 2FA')).toBe('Failed to enable 2FA');
  });

  it('never overrides what the server did say', () => {
    const error = { response: { data: { detail: 'Code already used' } } };
    expect(describeApiError(error, 'Failed to enable 2FA')).toBe('Code already used');
  });

  it('is preferred over the transport error', () => {
    // The call sites that supply one wrote a sentence about what the user was
    // doing. "Failed to enable 2FA" is more use than axios's "Network Error",
    // and this ordering is what keeps those sites reading as they did before.
    const error = { message: 'Network Error' };
    expect(describeApiError(error, 'Failed to enable 2FA')).toBe('Failed to enable 2FA');
  });

  it('falls through to the transport error when no fallback is given', () => {
    // The majority shape: `detail || err.message`, which must be unchanged.
    expect(describeApiError({ message: 'Network Error' })).toBe('Network Error');
  });

  it('ignores an empty fallback', () => {
    expect(describeApiError({ message: 'Network Error' }, '   ')).toBe('Network Error');
  });

  it('still renders validation errors ahead of any fallback', () => {
    const error = {
      response: { data: { detail: [
        { loc: ['body', 'name'], msg: 'Field required' },
      ] } },
    };
    expect(describeApiError(error, 'Could not save')).toContain('Field required');
  });
});
