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
import { faceIdOf } from '../DetectionsPage.jsx';

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

/**
 * Mirrors the id collection in assignDetections.
 *
 * Uses the real faceIdOf rather than reimplementing it, so this cannot drift
 * from the handler the way an earlier copy of this helper did.
 */
function collectFaceIds(detections) {
  return detections.map(faceIdOf).filter(id => id !== null);
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

  it('yields nothing when the id is dropped, as the shipped literal did', () => {
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

  it('normalises a numeric string, which the endpoint needs as a number', () => {
    expect(collectFaceIds([{ id: '55', name: 'Unknown' }])).toEqual([55]);
  });
});

// ---------------------------------------------------------------------------
// Render keys and API identifiers are separate fields
// ---------------------------------------------------------------------------
//
// They were one field, and it caused three separate bugs. The combined feed
// merges faces and objects, where face 12 and object 12 collide, so ids were
// prefixed to `face-12`; the person view invented `pd-12` for the same reason.
// Those strings then reached an endpoint declaring `face_ids: List[int]`, which
// rejected every request — and a selection that stored the key instead of the
// id could not be reassigned at all.
//
// `listKey` now carries uniqueness for rendering and `id` stays exactly what
// the server sent. faceIdOf no longer decodes prefixes: a prefixed value is a
// view putting a render key back into `id`, and that should fail where it is
// used rather than be tolerated indefinitely.

import { describeApiError } from '../../utils/apiError.js';

describe('identifying a face detection', () => {
  it('uses the id the server sent', () => {
    expect(faceIdOf({ id: 123, type: 'person' })).toBe(123);
  });

  it('accepts rows from the person endpoint, which carry no type', () => {
    expect(faceIdOf({ id: 123 })).toBe(123);
  });

  it('refuses an object detection', () => {
    // A vehicle cannot be assigned to a person. `type` is carried into the
    // selection for exactly this check, since a stored selection is detached
    // from the row it came from.
    expect(faceIdOf({ id: 12, type: 'vehicle' })).toBeNull();
    expect(faceIdOf({ id: 12, type: 'package' })).toBeNull();
    expect(faceIdOf({ id: 12, type: 'animal' })).toBeNull();
  });

  it('keeps id 0', () => {
    expect(faceIdOf({ id: 0 })).toBe(0);
  });

  it('accepts a numeric string, as some endpoints return', () => {
    expect(faceIdOf({ id: '55' })).toBe(55);
  });

  it('refuses a prefixed value instead of decoding it', () => {
    // The regression guard for this whole change. If a view puts its render
    // key back into `id`, the assign handler must refuse and say so — the
    // silent version of this shipped, reported success, and moved nothing.
    expect(faceIdOf({ id: 'face-123' })).toBeNull();
    expect(faceIdOf({ id: 'pd-123' })).toBeNull();
    expect(faceIdOf({ id: 'object-45' })).toBeNull();
  });

  it('returns null rather than guessing at an unknown shape', () => {
    expect(faceIdOf({})).toBeNull();
    expect(faceIdOf(null)).toBeNull();
  });
});

describe('a detection carries both fields', () => {
  it('keeps them distinct, so neither can stand in for the other', () => {
    // What the loader now builds for the merged feed.
    const face = { id: 12, listKey: 'face-12', type: 'person' };
    const object = { id: 12, listKey: 'object-12', type: 'vehicle' };

    // Same server id, different rows: the keys are what keep them apart.
    expect(face.listKey).not.toBe(object.listKey);
    expect(faceIdOf(face)).toBe(12);
    expect(faceIdOf(object)).toBeNull();
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
