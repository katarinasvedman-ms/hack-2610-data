export function healthLabel(score: number | null): string {
  if (score === null) return 'Assessment needed'
  if (score >= 85) return 'Stable'
  if (score >= 65) return 'Watch'
  return 'Investigate'
}

export function formatSnapshot(value: string): string {
  return new Intl.DateTimeFormat('en', {
    dateStyle: 'medium',
    timeZone: 'UTC',
  }).format(new Date(value))
}
