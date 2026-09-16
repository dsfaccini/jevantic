# Observed workloads

Observed: 2026-09-16. These examples do not constitute an accepted feature list for Jevantic.

| Workload | Input and judgment | Surrounding code | Evidence |
| --- | --- | --- | --- |
| Agent command review | Proposed command and safety context | Determines whether execution may proceed | Vercel benchmark and forthcoming Gateway integration |
| Semantic checking | Writing, actions, or candidate context plus criteria | Flags problems for investigation or revision | Every's experiments |
| Recruiting enrichment | Jobs and people evaluated against shared criteria | Stores features and compares candidates locally | Eventum reports prelaunch production use |
| Listing filtering | Event title and optional description | Rejects semantic exclusions after deterministic checks | Near Here's prospective deployment evaluation |
| Staged code review | Git diffs and changed tests | Selects evidence, scores impact, routes findings | Experimental source inspected; not executed |

## Reusable features

Eventum asks the same 30 questions about jobs, engineers, and prospects. It stores answers and uses cosine similarity for initial matching. Nightly job enrichment asks 44 questions in two calls. Judgments become retained application data, not only immediate branches.

[Source](https://www.eventum.ai/case-studies/how-eventum-cut-llm-screening-costs-104x-with-typesafe)

## Repeated checks during work

Every tested writing criteria, context selection, reply assessment, and action screening. Its proposed application checks work while a generating model operates. The author wants additional accuracy validation before production.

[Source](https://every.to/also-true-for-humans/mini-vibe-check-typesafe-s-jev-judged-everything-i-ve-written-in-0-7-seconds)

## Explicit sequences

Jev Review screens files using several Noul questions, follows strong signals, selects a diff hunk, classifies a mechanism, scores severity, and conditionally chooses a reviewer. Code controls thresholds and follow-up calls. Findings are described as investigation prompts.

[Repository](https://github.com/devagrawal09/jev-review), source: src/review/workflow.ts and src/review/judgments.ts. The first reading did not capture a revision; re-check before relying on implementation details.

## Evaluation limits

Near Here's headline 50 records influenced prompt selection. Its additional 21 records did not establish a general accuracy advantage. Generated expected labels were not independently human-adjudicated. The task definition remains useful evidence.

[Source](https://nearhere.events/blog/typesafe-jev-mistral-gemini-event-validation)

Vercel's fx safety reviewer and Malte Ubl's unspecified classifier evaluation are separate observations.

[fx announcement](https://x.com/rauchg/status/2100307962262872105), [separate classifier](https://x.com/cramforce/status/2100269198727602468)
