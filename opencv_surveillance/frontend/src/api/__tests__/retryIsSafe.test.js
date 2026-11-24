// Copyright (c) 2025-2026 Smart Industries LLC (Mikel Smart)
// This file is part of OpenEye-OpenCV_Home_Security
//
// A failed request may only be replayed when replaying it cannot do the work
// twice.
//
// The defect
// ----------
// isRetryableError() returned true for every network error and every 5xx, and
// the response interceptor replayed the request up to maxRetries times without
// ever looking at the method. A POST that reached the server, succeeded, and
// then failed to return a response — a proxy timeout, a dropped connection —
// is indistinguishable from one that never arrived, and was replayed. That
// produces a second camera, a second automation rule, a second exported clip.
//
// Separately, `config` was destructured from the error and dereferenced
// immediately. An error raised in the REQUEST interceptor has no config, so
// `config.__retryCount` threw a TypeError that replaced the real error with a
// misleading one.
//
// What is safe to replay
// ----------------------
// GET, HEAD and OPTIONS have no side effects, so replaying one cannot create
// anything. 429 is the one status where any method is safe, because the server
// rejected the request without acting on it.
//
// PUT and DELETE are idempotent by HTTP contract and are still excluded. A
// replayed DELETE whose first attempt succeeded returns 404, so the interface
// reports "not found" for work that was in fact done. Not retrying costs a
// little resilience; retrying costs the correctness of what the user is told.

import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

// The predicate is module-private, so it is lifted out of the source rather
// than exported purely for a test — exporting it would invite it being called
// from somewhere other than the interceptor.
const here = path.dirname(fileURLToPath(import.meta.url));
const source = fs.readFileSync(path.join(here, '..', 'apiClient.js'), 'utf8');
const start = source.indexOf('const REPLAYABLE_METHODS');
const end = source.indexOf('\n};', source.indexOf('const isRetryableError')) + 3;
// eslint-disable-next-line no-new-func
const isRetryableError = new Function(
  `${source.slice(start, end)}\nreturn isRetryableError;`
)();

const error = (method, status) => ({
  config: method === undefined ? undefined : { method },
  response: status === undefined ? null : { status },
});

describe('replaying a failed request', () => {
  it('retries a GET that failed with no response', () => {
    expect(isRetryableError(error('get'))).toBe(true);
  });

  it('retries a GET that failed with a 5xx', () => {
    expect(isRetryableError(error('get', 500))).toBe(true);
  });

  it('does not retry a GET that failed with a 4xx', () => {
    expect(isRetryableError(error('get', 404))).toBe(false);
  });

  it.each(['post', 'patch', 'put', 'delete'])(
    'does not replay a %s that failed with no response',
    (method) => {
      // The defect: this is the case that created duplicate cameras.
      expect(isRetryableError(error(method))).toBe(false);
    }
  );

  it.each(['post', 'patch', 'put', 'delete'])(
    'does not replay a %s that failed with a 5xx',
    (method) => {
      // A 500 can be raised after the write committed.
      expect(isRetryableError(error(method, 500))).toBe(false);
    }
  );

  it.each(['get', 'post', 'patch', 'put', 'delete'])(
    'retries a %s rejected with 429',
    (method) => {
      // The server declined to act, so nothing happened to be repeated.
      expect(isRetryableError(error(method, 429))).toBe(true);
    }
  );

  it('is not fooled by an uppercase method', () => {
    expect(isRetryableError({ config: { method: 'POST' }, response: null })).toBe(false);
  });

  it('treats a missing method as a GET rather than throwing', () => {
    expect(isRetryableError({ config: {}, response: null })).toBe(true);
  });

  it('does not retry, or throw, when there is no config at all', () => {
    // Errors raised in the request interceptor carry no config. This used to
    // reach `config.__retryCount` and throw a TypeError over the real error.
    expect(() => isRetryableError(error(undefined))).not.toThrow();
    expect(isRetryableError(error(undefined))).toBe(false);
  });
});
