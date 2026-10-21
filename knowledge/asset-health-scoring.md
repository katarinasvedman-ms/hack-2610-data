---
title: Asset Health PoC illustrative scoring
source: Authored PoC reference
version: 0.1.0
date: 2026-10-21
classification: DEMO_ONLY
section: Scoring definition
---

# Asset Health PoC illustrative scoring

**Demo-only reference. Not manufacturer-approved maintenance guidance, validated
failure prediction, or a safety standard.**

## Scope

The score is a transparent prioritization aid for the fixed, synthetic 30-day
snapshot. It does not identify a root cause or certify that equipment is safe.
Business importance is a separate demo input and is never folded into health.

## Formula

- Availability contributes 40%: observed available minutes divided by observed
  eligible minutes, multiplied by 100.
- Charging success contributes 40%: successful starts divided by recorded start
  attempts, multiplied by 100. A start attempt includes both successful and
  failed starts.
- Recurring station-side faults contribute 20%: 100 multiplied by one minus
  the number of observed days affected by a recurring station-side code divided
  by the number of days with known fault observations.

The same station-side code is recurring when it appears on at least two distinct
days. Count each affected day once, even if multiple recurring codes occur that
day. Authentication, roaming, and payment failures are not station-side faults.

The weighted score is the sum of each component score multiplied by its weight.
The displayed score is rounded to one decimal place. The formula and weights are
illustrative and unvalidated.

## Evidence and ordering

Each component requires its own denominator and observed evidence. The API does
not silently reweight missing components. A zero-attempt window has no charging
success score and is classified as insufficient data. Incomplete days are
excluded from that component's denominator and shown in its coverage text.

Insufficient-data stations are presented separately for assessment. Scored
stations default to lowest health first, then highest business importance, then
station ID. Health-only and importance-first sorts are also available.
A safety-escalation flag is separate from the score.
