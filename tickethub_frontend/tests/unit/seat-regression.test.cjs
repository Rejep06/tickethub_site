const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const E = require(path.join(process.env.TH_TEST_BUILD, 'lib/seat-editor.js'));
const V = require(path.join(process.env.TH_TEST_BUILD, 'lib/seat-viewport.js'));
const raw = (id = 'a', extra = {}) => ({ id, plan: 'plan', sector: '101', row: '1', number: '7', x: '.2', y: '.3', adjacency_group: '', adjacency_position: null, ...extra });

test('Reading an imported snapshot with blank labels never throws', () => {
 const seats = E.seatDrafts([raw('a', { row: '' }), raw('b', { sector: '', number: '' })]);
 assert.equal(seats.length, 2); assert.equal(seats[0].row, ''); assert.equal(seats[1].sector, ''); assert.equal(seats[1].number, '');
 assert.equal(E.seatIssues(seats).length, 2);
});
test('Numeric zero labels are preserved as zero, not treated as empty', () => {
 const [seat] = E.seatDrafts([raw('a', { sector: 101, row: 0, number: 0 })]);
 assert.equal(seat.sector, '101'); assert.equal(seat.row, '0'); assert.equal(seat.number, '0');
 assert.deepEqual(E.seatIssues([seat]), []);
});
test('Null/missing labels do not get invented names or throw TypeError', () => {
 const [seat] = E.seatDrafts([raw('a', { sector: null, row: undefined })]);
 assert.equal(seat.sector, ''); assert.equal(seat.row, '');
 const issues = E.seatIssues([seat]); assert.match(issues[0].messages.join(' '), /Сектор/); assert.match(issues[0].messages.join(' '), /Ряд/);
});
test('Overlong imported labels stay intact and have specific diagnostics', () => {
 const source = raw('a', { sector: 'А'.repeat(51), row: 'Р'.repeat(31), number: '9'.repeat(31) });
 const [seat] = E.seatDrafts([source]); assert.equal(seat.sector, source.sector); assert.equal(seat.row, source.row); assert.equal(seat.number, source.number);
 assert.equal(E.seatIssues([seat])[0].messages.length, 3); assert.match(E.seatIssues([seat])[0].messages[0], /50.*51/);
});
test('Read diagnostics do not trim or mutate imported identity values', () => {
 const source = raw('a', { row: '  ', sector: ' A ' }); const before = JSON.stringify(source);
 const [seat] = E.seatDrafts([source]); E.seatIssues([seat]);
 assert.equal(seat.row, '  '); assert.equal(seat.sector, ' A '); assert.equal(JSON.stringify(source), before);
});
test('Invalid imported coordinates stay available for correction, not at (0,0)', () => {
 const seats = E.seatDrafts([raw('a', { x: null }), raw('b', { y: 'not-a-coordinate' }), raw('c', { x: 2 })]);
 assert.equal(seats[0].x, ''); assert.equal(seats[1].y, 'not-a-coordinate'); assert.equal(seats[2].x, '2');
 assert.equal(seats.filter(E.hasSeatPosition).length, 0); assert.equal(E.seatIssues(seats).length, 3);
 assert.deepEqual(E.selectRectangle(seats, { x: 0, y: 0 }, { x: 1, y: 1 }), []);
});
test('Writing null or blank coordinates remains forbidden', () => {
 for (const value of [null, undefined, '', ' ', Infinity, NaN]) assert.throws(() => E.coordinate(value), /INVALID_GEOMETRY/);
 assert.equal(E.coordinate(0), '0.000000');
});
test('Unchanged invalid snapshot has zero dirty changes and no automatic mutations', () => {
 const seats = E.seatDrafts([raw('a', { row: '' }), raw('b', { number: '' })]);
 assert.equal(E.changeCount(E.draftChanges(seats, seats, 7)), 0);
 assert.deepEqual(E.planChanges(seats, seats, 7), { expected_version: 7, create: [], update: [], delete: [] });
});
test('Dirty-state diff cannot throw because of an incomplete edited label', () => {
 const seats = E.seatDrafts([raw()]); const next = [{ ...seats[0], row: '' }];
 assert.equal(E.changeCount(E.draftChanges(seats, next, 7)), 1);
 assert.throws(() => E.planChanges(seats, next, 7), /INVALID_SEAT_LABEL/);
});
test('Repair the first invalid seat while the second remains untouched', () => {
 const old = E.seatDrafts([raw('a', { row: '' }), raw('b', { number: '' })]);
 const next = [{ ...old[0], row: '10' }, old[1]]; const payload = E.planChanges(old, next, 7);
 assert.equal(E.seatIssues(next).length, 1); assert.equal(payload.update.length, 1); assert.equal(payload.update[0].id, 'a');
 assert.equal(payload.update[0].row, '10'); assert.equal(payload.expected_version, 7); assert.deepEqual(payload.create, []); assert.deepEqual(payload.delete, []);
});
test('A valid seat can be edited without rewriting unrelated bad imports', () => {
 const old = E.seatDrafts([raw('bad', { row: '' }), raw('good', { number: '8' })]);
 const next = E.transformSeats(old, new Set(['good']), { dx: .1 }); const payload = E.planChanges(old, next, 4);
 assert.deepEqual(payload.update.map(s => s.id), ['good']); assert.equal(next[0].row, '');
});
test('Editing an incomplete seat is rejected until required fields are fixed', () => {
 const old = E.seatDrafts([raw('bad', { row: '' })]);
 assert.throws(() => E.planChanges(old, [{ ...old[0], x: '.25' }], 1), /INVALID_SEAT_LABEL/);
});
test('New seats keep the original strict validation', () => {
 assert.throws(() => E.newSeatDrafts([{ sector: '101', row: '', number: '1', x: .2, y: .3 }]), /INVALID_SEAT_LABEL/);
});
test('Deleting a bad imported draft uses its actual ID without validating its old labels', () => {
 const old = E.seatDrafts([raw('bad', { row: '' })]);
 assert.deepEqual(E.planChanges(old, [], 5), { expected_version: 5, create: [], update: [], delete: ['bad'] });
});
test('Existing duplicate identities are visible instead of crashing render', () => {
 const old = E.seatDrafts([raw('a'), raw('b')]);
 assert.equal(E.seatIssues(old).length, 2); assert.equal(E.changeCount(E.draftChanges(old, old, 1)), 0);
 assert.throws(() => E.validateSeats(old), /DUPLICATE_SEAT/);
});
test('An existing duplicate identity can be repaired one record at a time', () => {
 const old = E.seatDrafts([raw('a'), raw('b')]); const next = [old[0], { ...old[1], number: '8' }];
 assert.equal(E.seatIssues(next).length, 0); assert.equal(E.planChanges(old, next, 1).update.length, 1);
});
test('Mutation cannot introduce a duplicate identity even beside bad imports', () => {
 const old = E.seatDrafts([raw('bad', { row: '' }), raw('a'), raw('b', { number: '8' })]);
 assert.throws(() => E.planChanges(old, [old[0], old[1], { ...old[2], number: '7' }], 1), /DUPLICATE_SEAT/);
});
test('Publishing/full validation still rejects imported missing labels', () => {
 assert.throws(() => E.validateSeats(E.seatDrafts([raw('bad', { row: '' })])), /INVALID_SEAT_LABEL/);
});
test('Coordinate formatting alone is not a write', () => {
 const old = E.seatDrafts([raw()]); const next = [{ ...old[0], x: '0.200', y: '.3000' }];
 assert.equal(E.changeCount(E.draftChanges(old, next, 1)), 0); assert.equal(E.changeCount(E.planChanges(old, next, 1)), 0);
});
test('Unknown IDs and bad versions remain blocked on writes', () => {
 const old = E.seatDrafts([raw()]);
 assert.throws(() => E.planChanges(old, [{ ...old[0], id: 'foreign' }], 1), /INVALID_SEAT_ID/);
 assert.throws(() => E.planChanges(old, old, 0), /VERSION_CONFLICT/);
});
test('A dense group of invalid imports can be diagnosed without a quadratic identity build', () => {
 const seats = E.seatDrafts(Array.from({ length: 10000 }, (_, i) => raw(String(i), { row: '', number: '' })));
 assert.equal(E.seatIssues(seats).length, 10000);
});
test('Zoom/pan do not mutate API coordinates or identity labels', () => {
 const seats = [raw('a'), raw('b', { number: '8', x: '.25' })]; const before = JSON.stringify(seats);
 const model = V.buildSeatModel(seats, 1.6); const size = { width: 960, height: 540 };
 let camera = V.fitCamera(model.world, size); camera = V.zoomAt(camera, { x: 400, y: 200 }, 2, model.world, size);
 camera = V.clampCamera({ ...camera, x: camera.x - 50 }, model.world, size);
 assert.equal(JSON.stringify(seats), before); assert.ok(camera.scale > 0);
});
