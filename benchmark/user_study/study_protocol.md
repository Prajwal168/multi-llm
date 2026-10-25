# RQ5 user study protocol

RQ5: does provenance, the human approval checkpoint, and execution-stage
streaming improve user-perceived transparency and debuggability?
Metrics (from the paper, Section IV-C "additional measurements"): plan
rejection rate, and human ratings of transparency and trust
(debuggability is asked as a rating item, Section IV-F).

## Conditions (within-subject, counterbalanced order)

| Condition id      | What the participant sees |
|-------------------|---------------------------|
| baseline          | Arm A output only: one answer, no provenance, no plan, no checkpoint |
| full              | Full UI: plan + approval checkpoint, provenance (sources, chunks, relevance decision), streamed per-task verification status |
| no_provenance     | Full UI with the provenance panel hidden |
| no_checkpoint     | Full UI, plan auto-approved |
| blocking          | Full UI, execution results shown only after every task finished (no streaming) |

The current UI has no toggles for `no_provenance`, `no_checkpoint` or
`blocking`; each needs a small feature flag in App.jsx (hide the
Retrieval & Context panel; skip the approval buttons; buffer
`taskProgress` until the `done` event).

## Procedure per trial

1. Give the participant a task from tasks.json (same task set, different
   tasks per condition; balance strata).
2. Log `approve` / `reject` at the checkpoint through /api/study/event
   (see study_router.py). A rejection returns the query for revision;
   count it once per plan shown.
3. After the run, participant rates 1-5 (Likert):
   - transparency: "I could tell where the answer's content came from."
   - trust: "I trust this answer enough to rely on it."
   - debuggability: "If something in the answer were wrong, I could tell which stage caused it."
4. Append a row to ratings.csv: participant,condition,task_id,transparency,trust,debuggability.
5. For the debuggability item, seed one known fault (e.g. force a web
   fallback or a failed verification) in a subset of trials so the
   rating is about a real diagnosis task.

## Reporting
metrics.py prints plan_rejection_rate per condition and mean rating
with 95% bootstrap CI per condition and item.
