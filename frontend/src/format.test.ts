import { describe, expect, it } from 'vitest'
import { formatSnapshot, healthLabel } from './format'

describe('health labels', () => {
  it('does not convert missing evidence into a health score', () => {
    expect(healthLabel(null)).toBe('Assessment needed')
  })

  it('uses stable score bands', () => {
    expect(healthLabel(85)).toBe('Stable')
    expect(healthLabel(84.9)).toBe('Watch')
    expect(healthLabel(64.9)).toBe('Investigate')
  })

  it('formats the snapshot date in UTC', () => {
    expect(formatSnapshot('2026-10-21T00:00:00Z')).toBe('Oct 21, 2026')
  })
})
