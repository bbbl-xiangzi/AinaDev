import test from 'node:test';
import assert from 'node:assert/strict';
import { formatAuditTime } from '../lib/audit-time.ts';

test('audit time uses Beijing time, including a date boundary', () => {
  assert.equal(formatAuditTime('2026-11-03T04:38:12Z'), '2026年11月03日 12:38:12');
  assert.equal(formatAuditTime('2026-11-03T20:00:01Z'), '2026年11月04日 04:00:01');
  assert.equal(formatAuditTime('2026-11-03T12:38:12+08:00'), '2026年11月03日 12:38:12');
});

test('missing and invalid timestamps do not break the audit table', () => {
  for (const value of [undefined, null, '', 'invalid']) assert.equal(formatAuditTime(value), '—');
});
