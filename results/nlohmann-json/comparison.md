# Basic vs improved pipeline: nlohmann-json

59 PR(s) run by both pipelines. Basic: the generation prompt has the PR text and diff only, and no coverage loop. Improved: the prompt also names the changed functions (change analysis) and shows upstream tests that use them (test context), and the coverage loop adds programs aimed at changed lines nobody reached. Fixing and classification are the same in both. Definitions as in report.md.

| Measure | Basic | Improved |
|---|---|---|
| Programs generated (mean per PR) | 19.9 | 23.2 |
| Compile success, as generated (new / both) | 69.0% / 65.4% | 78.1% / 73.2% |
| Compile success, after fix.py (new / both) | 80.0% / 76.4% | 89.2% / 85.2% |
| PRs with at least one behavioral difference | 14 of 59 | 22 of 59 |
| Differences by verdict (clusters) | intended 35, unintended 5, unclear 4 | intended 70, unintended 8, unclear 5 |
| Regression candidates | 2: #4958, #6005 | 3: #4958, #5890, #6005 |
| Clean results that are INCONCLUSIVE (coverage missing or low) | 15 | 10 |
| Seeded regressions found | 1/1 | 1/1 |
| LLM calls per PR (estimated) | 2.3 | 3.5 |

## Changed-line coverage (38 PRs measured by both)

| | Basic | Improved, before the coverage loop | Improved, after the coverage loop |
|---|---|---|---|
| Mean changed-line coverage | 79.1% | 80.1% | 86.2% |
| PRs with at least 80% reached | 23 | 27 | 30 |

Basic -> improved before the loop is the effect of change analysis and test context in the prompt; before -> after the loop is the effect of the coverage loop.

## Per PR

| PR | Coverage basic | Coverage improved (before -> after loop) | Differing basic | Differing improved | Verdict basic | Verdict improved |
|---|---|---|---|---|---|---|
| #4958 | n/a | n/a -> n/a | 15 | 19 | REGRESSION CANDIDATE | REGRESSION CANDIDATE |
| #5459 | 100% | 95% -> 95% | 3 | 8 | no regression flagged | no regression flagged |
| #5890 | n/a | n/a -> n/a | 20 | 25 | no regression flagged (no measurable changed lines) | REGRESSION CANDIDATE |
| #5908 | n/a | 75% -> 75% | 0 | 0 | no regression flagged (no measurable changed lines) | no regression flagged, INCONCLUSIVE: only 75% of changed lines reached |
| #5915 | 20% | 100% -> 100% | 0 | 6 | no regression flagged, INCONCLUSIVE: only 20% of changed lines reached | no regression flagged |
| #5920 | n/a | n/a -> n/a | 0 | 0 | no regression flagged (no measurable changed lines) | no regression flagged (no measurable changed lines) |
| #5921 | n/a | n/a -> n/a | 0 | 0 | no regression flagged (no measurable changed lines) | no regression flagged (no measurable changed lines) |
| #5926 | n/a | 94% -> 94% | 0 | 0 | no regression flagged (no measurable changed lines) | no regression flagged |
| #5931 | 0% | 0% -> 0% | 0 | 0 | no regression flagged, INCONCLUSIVE: only 0% of changed lines reached | no regression flagged, INCONCLUSIVE: only 0% of changed lines reached |
| #5936 | 100% | 100% -> 100% | 3 | 11 | no regression flagged | no regression flagged |
| #5940 | 74% | 72% -> 74% | 0 | 1 | no regression flagged, INCONCLUSIVE: only 74% of changed lines reached | no regression flagged, INCONCLUSIVE: only 74% of changed lines reached |
| #5942 | n/a | n/a -> n/a | 0 | 0 | no regression flagged (no measurable changed lines) | no regression flagged (no measurable changed lines) |
| #5964 | 100% | 100% -> 100% | 0 | 1 | no regression flagged | no regression flagged |
| #5966 | n/a | n/a -> n/a | 20 | 20 | no regression flagged (no measurable changed lines) | no regression flagged (no measurable changed lines) |
| #5968 | 91% | 91% -> 96% | 0 | 0 | no regression flagged | no regression flagged |
| #5969 | n/a | 100% -> 100% | 0 | 0 | no regression flagged (no measurable changed lines) | no regression flagged |
| #5971 | 100% | 100% -> 100% | 0 | 0 | no regression flagged | no regression flagged |
| #5975 | 76% | 69% -> 92% | 0 | 0 | no regression flagged, INCONCLUSIVE: only 76% of changed lines reached | no regression flagged |
| #5976 | 100% | 100% -> 100% | 0 | 0 | no regression flagged | no regression flagged |
| #5978 | 44% | 70% -> 70% | 0 | 0 | no regression flagged, INCONCLUSIVE: only 44% of changed lines reached | no regression flagged, INCONCLUSIVE: only 70% of changed lines reached |
| #5979 | 76% | 94% -> 94% | 0 | 0 | no regression flagged, INCONCLUSIVE: only 76% of changed lines reached | no regression flagged |
| #5980 | 74% | 88% -> 88% | 0 | 0 | no regression flagged, INCONCLUSIVE: only 74% of changed lines reached | no regression flagged |
| #5981 | 66% | 48% -> 48% | 0 | 0 | no regression flagged, INCONCLUSIVE: only 66% of changed lines reached | no regression flagged, INCONCLUSIVE: only 48% of changed lines reached |
| #5984 | 92% | n/a -> 7% | 0 | 0 | no regression flagged | no regression flagged, INCONCLUSIVE: only 7% of changed lines reached |
| #5990 | 100% | 100% -> 100% | 8 | 9 | no regression flagged | no regression flagged |
| #5991 | 100% | 100% -> 100% | 0 | 0 | no regression flagged | no regression flagged |
| #5992 | 100% | 100% -> 100% | 6 | 9 | no regression flagged | no regression flagged |
| #5996 | 70% | 100% -> 100% | 0 | 0 | no regression flagged, INCONCLUSIVE: only 70% of changed lines reached | no regression flagged |
| #5998 | 27% | 27% -> 27% | 0 | 0 | no regression flagged, INCONCLUSIVE: only 27% of changed lines reached | no regression flagged, INCONCLUSIVE: only 27% of changed lines reached |
| #5999 | 20% | 20% -> 100% | 0 | 1 | no regression flagged, INCONCLUSIVE: only 20% of changed lines reached | no regression flagged |
| #6000 | 57% | 92% -> 100% | 0 | 0 | no regression flagged, INCONCLUSIVE: only 57% of changed lines reached | no regression flagged |
| #6001 | 50% | 60% -> 70% | 0 | 0 | no regression flagged, INCONCLUSIVE: only 50% of changed lines reached | no regression flagged, INCONCLUSIVE: only 70% of changed lines reached |
| #6002 | 87% | 100% -> 100% | 3 | 2 | no regression flagged | no regression flagged |
| #6003 | n/a | n/a -> n/a | 0 | 0 | no regression flagged (no measurable changed lines) | no regression flagged (no measurable changed lines) |
| #6005 | n/a | n/a -> n/a | 20 | 25 | REGRESSION CANDIDATE | REGRESSION CANDIDATE |
| #6008 | 100% | 100% -> 100% | 0 | 0 | no regression flagged | no regression flagged |
| #6009 | n/a | n/a -> n/a | 0 | 0 | no regression flagged (no measurable changed lines) | no regression flagged (no measurable changed lines) |
| #6012 | 50% | 50% -> 50% | 20 | 25 | no regression flagged, INCONCLUSIVE: only 50% of changed lines reached | no regression flagged, INCONCLUSIVE: only 50% of changed lines reached |
| #6013 | n/a | 100% -> 100% | 0 | 0 | no regression flagged (no measurable changed lines) | no regression flagged |
| #6015 | n/a | 0% -> 100% | 0 | 0 | no regression flagged (no measurable changed lines) | no regression flagged |
| #6016 | 100% | 100% -> 100% | 0 | 0 | no regression flagged | no regression flagged |
| #6020 | 100% | 100% -> 100% | 0 | 0 | no regression flagged | no regression flagged |
| #6023 | 100% | 0% -> 100% | 0 | 0 | no regression flagged | no regression flagged |
| #6028 | 100% | 100% -> 100% | 0 | 0 | no regression flagged | no regression flagged |
| #6029 | 100% | 100% -> 100% | 0 | 5 | no regression flagged | no regression flagged |
| #6030 | 93% | 93% -> 93% | 0 | 1 | no regression flagged | no regression flagged |
| #6039 | 100% | 100% -> 100% | 0 | 0 | no regression flagged | no regression flagged |
| #6049 | n/a | n/a -> n/a | 0 | 0 | no regression flagged (no measurable changed lines) | no regression flagged (no measurable changed lines) |
| #6073 | n/a | n/a -> n/a | 12 | 8 | no regression flagged (no measurable changed lines) | no regression flagged (no measurable changed lines) |
| #6075 | 100% | n/a -> 100% | 5 | 9 | no regression flagged | no regression flagged |
| #6076 | 98% | 96% -> 99% | 2 | 5 | no regression flagged | no regression flagged |
| #6077 | 100% | 10% -> 10% | 0 | 0 | no regression flagged | no regression flagged, INCONCLUSIVE: only 10% of changed lines reached |
| #6078 | 55% | 86% -> 86% | 0 | 1 | no regression flagged, INCONCLUSIVE: only 55% of changed lines reached | no regression flagged |
| #6081 | 100% | n/a -> 100% | 0 | 0 | no regression flagged | no regression flagged |
| #6084 | n/a | n/a -> n/a | 0 | 0 | no regression flagged (no measurable changed lines) | no regression flagged (no measurable changed lines) |
| #6085 | n/a | n/a -> n/a | 0 | 0 | no regression flagged (no measurable changed lines) | no regression flagged (no measurable changed lines) |
| #6117 | 86% | 86% -> 86% | 0 | 0 | no regression flagged | no regression flagged |
| #6119 | 100% | 100% -> 100% | 5 | 5 | no regression flagged | no regression flagged |
| #6121 | 94% | 94% -> 99% | 0 | 4 | no regression flagged | no regression flagged |
