import assert from 'node:assert/strict';
import { test } from 'node:test';
import { matchProfileCode, normalizeModelId } from '../src/services/modelProfiles.ts';

const profiles = [
  { code: 'doubao-seedance-1-5-pro', remote_model_id: 'doubao-seedance-1-5-pro-251215' },
  { code: 'doubao-seedance-2-0', remote_model_id: 'doubao-seedance-2-0-260128' },
  { code: 'doubao-seedance-2-0-fast', remote_model_id: 'doubao-seedance-2-0-fast-260128' },
  { code: 'doubao-seedance-2-5', remote_model_id: 'doubao-seedance-2-5-260628' },
  { code: 'doubao-seedance-2-5-flash', remote_model_id: 'doubao-seedance-2-5-flash-261115' },
];

test('fast variants are not captured by the shorter base model', () => {
  assert.equal(matchProfileCode(profiles, 'doubao-seedance-2-0-fast-260128'), 'doubao-seedance-2-0-fast');
  assert.equal(matchProfileCode(profiles, 'doubao-seedance-2-5-flash-261115'), 'doubao-seedance-2-5-flash');
});

test('future vendor version suffixes still resolve to the same profile', () => {
  assert.equal(matchProfileCode(profiles, 'doubao-seedance-2-0-fast-270101'), 'doubao-seedance-2-0-fast');
  assert.equal(matchProfileCode(profiles, 'doubao-seedance-2-5-flash-270101'), 'doubao-seedance-2-5-flash');
  assert.equal(matchProfileCode(profiles, 'doubao-seedance-2-0-270101'), 'doubao-seedance-2-0');
});

test('short names, unknown models and normalisation', () => {
  assert.equal(matchProfileCode(profiles, 'doubao-seedance-2-0-fast'), 'doubao-seedance-2-0-fast');
  assert.equal(matchProfileCode(profiles, 'ep-20260908233754-lwzxm'), null);
  assert.equal(matchProfileCode(profiles, ''), null);
  assert.equal(normalizeModelId('doubao-seedance-2-5-260628'), 'doubao-seedance-2-5');
});
