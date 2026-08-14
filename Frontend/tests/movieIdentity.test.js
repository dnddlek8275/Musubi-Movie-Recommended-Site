import test from 'node:test';
import assert from 'node:assert/strict';

import {
  getInternalMovieId,
  hasMatchingMovieIdentity,
  normalizeInternalMovieId,
} from '../src/utils/movieIdentity.js';

test('movie_id is preferred over a generic id', () => {
  assert.equal(getInternalMovieId({ id: 296, movie_id: 196, tmdb_id: 969681 }), 196);
});

test('TMDB ID is never used as an internal movie ID fallback', () => {
  assert.equal(getInternalMovieId({ tmdb_id: 969681 }), null);
});

test('route and detail IDs must identify the same internal movie', () => {
  assert.equal(hasMatchingMovieIdentity('196', { id: 196, tmdb_id: 969681 }), true);
  assert.equal(hasMatchingMovieIdentity('296', { id: 196, tmdb_id: 969681 }), false);
});

test('invalid route IDs are rejected', () => {
  assert.equal(normalizeInternalMovieId('not-a-number'), null);
  assert.equal(normalizeInternalMovieId(-1), null);
});
