import assert from 'node:assert/strict';

const { eventVisibilityFromApi } = await import('../src/services/forum_backend_bridge.js');

assert.equal(
  eventVisibilityFromApi('PUBLIC'),
  'Public',
  'public server events stay public in the local UI model',
);
assert.equal(
  eventVisibilityFromApi('PRIVATE'),
  'Membres',
  'server-private events hydrate as structure-internal, not admin-only Privé',
);
assert.equal(
  eventVisibilityFromApi(undefined),
  'Membres',
  'missing server visibility defaults to structure-internal access',
);

console.log('backend bridge regressions: PASS');
