/**
 * Tests for splitting detections into "needs a human" and "just needs a count".
 *
 * The page used to list every detection as its own card with an "Assign to
 * person" button, including the ones carrying no image — which asks somebody to
 * identify a face they cannot see. Most detections are also a confident match
 * and need no decision at all.
 *
 * The numbers here come from a real installation: 701 detections carrying
 * confidence exactly 0.0 because clustering named them afterwards, and 64
 * genuine matches at 0.40 or above.
 */

import { describe, it, expect } from 'vitest';
import { splitDetections } from '../DetectionsPage';

const detection = (over = {}) => ({
  id: Math.random(),
  name: 'unknown1',
  confidence: 0.5,
  snapshot_path: 'face_cam_1.jpg',
  timestamp: '2026-08-17T18:00:00',
  ...over,
});

describe('the review queue', () => {
  it('includes an unrecognised face that has an image', () => {
    const { review } = splitDetections([
      detection({ name: 'Unknown', confidence: 0, snapshot_path: 'a.jpg' }),
    ]);

    expect(review).toHaveLength(1);
    expect(review[0]._reason).toBe('not recognised');
  });

  it('includes a borderline match that has an image', () => {
    const { review } = splitDetections([
      detection({ name: 'Mikel', confidence: 0.44 }),
    ]);

    expect(review).toHaveLength(1);
    expect(review[0]._reason).toBe('uncertain match');
  });

  it('excludes anything without an image, however uncertain', () => {
    /**
     * The point of the whole change. A card with no face cannot be identified,
     * so putting it in a queue that asks for identification is asking for the
     * impossible.
     */
    const { review } = splitDetections([
      detection({ name: 'Unknown', confidence: 0, snapshot_path: null }),
      detection({ name: 'Mikel', confidence: 0.44, snapshot_path: null }),
    ]);

    expect(review).toHaveLength(0);
  });

  it('excludes a confident match', () => {
    const { review } = splitDetections([detection({ confidence: 0.92 })]);

    expect(review).toHaveLength(0);
  });

  it('does not treat a cluster-assigned name as a 0% match', () => {
    /**
     * 701 rows on the real install carry confidence exactly 0.0 — they were
     * never recognised, clustering named them later and never touched the
     * column. Reading that zero as a confidence would flood a queue meant to
     * hold a handful.
     */
    const rows = Array.from({ length: 701 }, () =>
      detection({ name: 'unknown1', confidence: 0 }));

    const { review, people } = splitDetections(rows);

    expect(review).toHaveLength(0);
    expect(people[0].clustered).toBe(701);
  });
});

describe('the per-person summary', () => {
  it('collapses many detections into one entry', () => {
    const rows = Array.from({ length: 50 }, () => detection({ confidence: 0.9 }));

    const { people } = splitDetections(rows);

    expect(people).toHaveLength(1);
    expect(people[0].total).toBe(50);
  });

  it('counts how many carry a photo', () => {
    const { people } = splitDetections([
      detection({ confidence: 0.9, snapshot_path: 'a.jpg' }),
      detection({ confidence: 0.9, snapshot_path: null }),
      detection({ confidence: 0.9, snapshot_path: null }),
    ]);

    expect(people[0].total).toBe(3);
    expect(people[0].withImages).toBe(1);
  });

  it('keeps a thumbnail when any detection has one', () => {
    const { people } = splitDetections([
      detection({ confidence: 0.9, snapshot_path: null }),
      detection({ confidence: 0.9, snapshot_path: 'later.jpg' }),
    ]);

    expect(people[0].thumbnail).toBeTruthy();
  });

  it('reports the best match rather than an average', () => {
    const { people } = splitDetections([
      detection({ confidence: 0.62 }),
      detection({ confidence: 0.91 }),
    ]);

    expect(people[0].bestConfidence).toBeCloseTo(0.91);
  });

  it('tracks the most recent sighting', () => {
    const { people } = splitDetections([
      detection({ confidence: 0.9, timestamp: '2026-08-17T10:00:00' }),
      detection({ confidence: 0.9, timestamp: '2026-08-17T20:00:00' }),
    ]);

    expect(people[0].lastSeen).toBe('2026-08-17T20:00:00');
  });

  it('separates different people and orders by volume', () => {
    const rows = [
      ...Array.from({ length: 10 }, () => detection({ name: 'unknown2', confidence: 0.9 })),
      ...Array.from({ length: 40 }, () => detection({ name: 'unknown1', confidence: 0.9 })),
    ];

    const { people } = splitDetections(rows);

    expect(people.map((p) => p.name)).toEqual(['unknown1', 'unknown2']);
  });

  it('handles an empty list', () => {
    const { review, people } = splitDetections([]);

    expect(review).toEqual([]);
    expect(people).toEqual([]);
  });
});
