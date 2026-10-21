# Asset Health PoC scoring reference

Classification: PoC-authored reference. It is not an operational policy or a
validated failure-prediction model.

The demo score is a 0–100 summary of three observed components over a fixed
30-day snapshot:

- Availability: available eligible minutes divided by observed eligible
  minutes, weighted 40%.
- Charging success: successful starts divided by recorded start attempts,
  weighted 40%.
- Recurring faults: `100 × (1 − affected recurring-fault days / observed days)`,
  weighted 20%. A code is recurring only when the same station-side code was
  observed on at least two distinct days. A day with multiple recurring codes
  counts once.

The overall score is calculated only when all required components have usable
observations. Missing required data and a zero-attempt period produce
“insufficient data”; components are not silently reweighted. A missing fault
observation is not the same as an explicitly observed empty fault list.

Business importance is a separate business-provided context value and does not
change the technical health score. The default review order shows stations with
insufficient data separately, then scored stations from lowest score upward,
using business importance and station ID as tie-breakers.

These fixtures are deterministic and fictional. The score does not establish
root cause, physical safety, or future failure probability. Safety reports are
shown as independent human-review escalations.
