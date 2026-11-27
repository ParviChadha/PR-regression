# Report: nlohmann-json

122 PR(s) checked, 2790 programs generated, 2790 in use (648 repaired by fix.py). Numbers come only from the files on disk; see the module docstring of pipeline/report.py for each definition.

## Summary

| Measure | Value |
|---|---|
| PRs checked | 122 |
| Compile success, as generated (new / both versions) | 81.5% / 77.5% |
| Compile success, after fix.py (new / both versions) | 91.6% / 88.8% |
| Deterministic on both versions | 2473 of 2478 compiled-on-both programs (99.8%) |
| PRs with at least one behavioral difference | 41 of 122 (33.6%) |
| Differences by verdict (clusters / programs) | intended 132 / 268, unintended 8 / 58, unclear 13 / 20 |
| Regression candidates | 3 of 122 classified: #4958, #5890, #6005 |
| Changed-line coverage measured | 122 of 122 PRs; at least 80% reached for 80 |
| Clean results that are INCONCLUSIVE (coverage missing or low) | 17: #5707, #5795, #5839, #5842, #5885, #5889, #5908, #5927, #5931, #5940, #5978, #5981, #5984, #5998, #6001, #6012, #6077 |
| Changed-line coverage before / after the loop (mean over 93 PRs) | 84.1% / 90.3% |
| LLM calls (estimated) | 412 total, 3.4 per PR |
| Wall time of the run.py stage | 1490.4 s |

## Seeded PRs with a known answer

A small set; recall here is not a general estimate.

| PR | Expected | Pipeline | Match | Note |
|---|---|---|---|---|
| #4958 | unintended | unintended found | yes | later regression reported in #5689 (string_view-convertible key types break lookups) |
| #5459 | intended | no regression flagged | yes | intended change; #5772 later fixed a hash inconsistency it caused (mixed case) |

Recall on seeded regressions: 1/1

## Per PR

| PR | Programs (in use) | Compile new / both | Status counts | Differing | Verdict | Coverage | Calls |
|---|---|---|---|---|---|---|---|
| #4958 | 25 (25) | 17/25 / 17/25 | compile_diff 8, output_diff 11, same 6 | 19 | REGRESSION CANDIDATE | n/a | 5 |
| #4965 | 8 (8) | 8/8 / 8/8 | output_diff 8 | 8 | no regression flagged | 98% of 64 lines | 5 |
| #5328 | 25 (25) | 24/25 / 24/25 | invalid 1, same 24 | 0 | no regression flagged | 93% of 30 lines | 4 |
| #5358 | 20 (20) | 20/20 / 20/20 | output_diff 7, same 13 | 7 | no regression flagged | 100% of 3 lines | 2 |
| #5459 | 25 (25) | 25/25 / 25/25 | output_diff 8, same 17 | 8 | no regression flagged | 95% of 20 lines | 3 |
| #5585 | 25 (25) | 25/25 / 25/25 | same 25 | 0 | no regression flagged | 100% of 44 lines | 3 |
| #5701 | 25 (25) | 25/25 / 25/25 | same 25 | 0 | no regression flagged | 100% of 1 lines | 2 |
| #5707 | 25 (25) | 25/25 / 25/25 | invalid 2, output_diff 1, same 22 | 1 | no regression flagged, INCONCLUSIVE: only 52% of changed lines reached | 52% of 23 lines | 4 |
| #5740 | 25 (25) | 6/25 / 3/25 | compile_diff 3, invalid 19, output_diff 2, same 1 | 5 | no regression flagged | 100% of 2 lines | 5 |
| #5758 | 25 (25) | 21/25 / 8/25 | compile_diff 16, invalid 1, output_diff 8 | 24 | no regression flagged (no measurable changed lines) | n/a | 5 |
| #5760 | 20 (20) | 18/20 / 18/20 | invalid 2, output_diff 12, same 6 | 12 | no regression flagged | 100% of 3 lines | 4 |
| #5766 | 25 (25) | 25/25 / 25/25 | output_diff 17, same 8 | 17 | no regression flagged | 100% of 24 lines | 4 |
| #5772 | 20 (20) | 20/20 / 20/20 | output_diff 12, same 8 | 12 | no regression flagged | 100% of 4 lines | 2 |
| #5776 | 25 (25) | 24/25 / 24/25 | invalid 1, same 24 | 0 | no regression flagged (no measurable changed lines) | n/a | 4 |
| #5779 | 25 (25) | 25/25 / 25/25 | same 25 | 0 | no regression flagged (no measurable changed lines) | n/a | 3 |
| #5781 | 25 (25) | 25/25 / 25/25 | same 25 | 0 | no regression flagged | 95% of 224 lines | 2 |
| #5782 | 25 (25) | 25/25 / 25/25 | same 25 | 0 | no regression flagged (no measurable changed lines) | n/a | 4 |
| #5791 | 10 (10) | 7/10 / 7/10 | invalid 3, same 7 | 0 | no regression flagged | 100% of 4 lines | 4 |
| #5792 | 25 (25) | 25/25 / 25/25 | same 25 | 0 | no regression flagged | 100% of 37 lines | 2 |
| #5793 | 25 (25) | 24/25 / 24/25 | invalid 1, same 24 | 0 | no regression flagged | 100% of 26 lines | 4 |
| #5795 | 25 (25) | 18/25 / 17/25 | compile_diff 1, invalid 7, same 17 | 1 | no regression flagged, INCONCLUSIVE: only 59% of changed lines reached | 59% of 22 lines | 5 |
| #5797 | 25 (25) | 25/25 / 25/25 | same 25 | 0 | no regression flagged (no measurable changed lines) | n/a | 4 |
| #5800 | 13 (13) | 13/13 / 13/13 | output_diff 8, same 5 | 8 | no regression flagged | 100% of 1 lines | 4 |
| #5802 | 20 (20) | 20/20 / 20/20 | output_diff 16, same 4 | 16 | no regression flagged | 100% of 1 lines | 2 |
| #5805 | 25 (25) | 0/25 / 0/25 | invalid 25 | 0 | no regression flagged (no measurable changed lines) | n/a | 4 |
| #5806 | 25 (25) | 25/25 / 25/25 | invalid 2, same 23 | 0 | no regression flagged | 100% of 38 lines | 2 |
| #5810 | 25 (25) | 25/25 / 25/25 | same 25 | 0 | no regression flagged | 100% of 18 lines | 3 |
| #5813 | 20 (20) | 20/20 / 20/20 | same 20 | 0 | no regression flagged (no measurable changed lines) | n/a | 3 |
| #5822 | 25 (25) | 25/25 / 25/25 | same 25 | 0 | no regression flagged | 90% of 19 lines | 3 |
| #5824 | 25 (25) | 24/25 / 24/25 | invalid 1, same 24 | 0 | no regression flagged (no measurable changed lines) | n/a | 4 |
| #5829 | 25 (25) | 25/25 / 25/25 | same 25 | 0 | no regression flagged (no measurable changed lines) | n/a | 4 |
| #5831 | 20 (20) | 19/20 / 19/20 | invalid 1, same 19 | 0 | no regression flagged | 100% of 5 lines | 3 |
| #5832 | 25 (25) | 25/25 / 25/25 | same 25 | 0 | no regression flagged | 96% of 25 lines | 2 |
| #5833 | 25 (25) | 25/25 / 25/25 | same 25 | 0 | no regression flagged | 100% of 17 lines | 3 |
| #5834 | 25 (25) | 25/25 / 25/25 | output_diff 2, same 23 | 2 | no regression flagged | 100% of 15 lines | 4 |
| #5835 | 25 (25) | 25/25 / 25/25 | same 25 | 0 | no regression flagged | 86% of 117 lines | 4 |
| #5836 | 25 (25) | 25/25 / 24/25 | compile_diff 1, same 24 | 1 | no regression flagged | 91% of 204 lines | 5 |
| #5837 | 25 (25) | 25/25 / 24/25 | compile_diff 1, output_diff 8, same 16 | 9 | no regression flagged | 100% of 14 lines | 5 |
| #5839 | 25 (25) | 25/25 / 25/25 | same 25 | 0 | no regression flagged, INCONCLUSIVE: only 63% of changed lines reached | 63% of 46 lines | 2 |
| #5840 | 25 (25) | 25/25 / 25/25 | same 25 | 0 | no regression flagged | 87% of 94 lines | 3 |
| #5842 | 6 (6) | 6/6 / 6/6 | same 6 | 0 | no regression flagged, INCONCLUSIVE: only 56% of changed lines reached | 56% of 27 lines | 3 |
| #5843 | 20 (20) | 20/20 / 20/20 | same 20 | 0 | no regression flagged | 100% of 3 lines | 1 |
| #5851 | 25 (25) | 25/25 / 25/25 | same 25 | 0 | no regression flagged | 100% of 62 lines | 2 |
| #5852 | 25 (25) | 20/25 / 20/25 | invalid 5, same 20 | 0 | no regression flagged | 89% of 18 lines | 4 |
| #5854 | 25 (25) | 25/25 / 25/25 | same 25 | 0 | no regression flagged | 100% of 19 lines | 4 |
| #5855 | 20 (20) | 19/20 / 19/20 | invalid 1, same 19 | 0 | no regression flagged | 100% of 1 lines | 3 |
| #5859 | 25 (25) | 25/25 / 25/25 | same 25 | 0 | no regression flagged | 100% of 2 lines | 3 |
| #5861 | 25 (25) | 25/25 / 25/25 | same 25 | 0 | no regression flagged | 84% of 302 lines | 2 |
| #5866 | 9 (9) | 8/9 / 6/9 | compile_diff 3, same 6 | 3 | no regression flagged | 92% of 12 lines | 5 |
| #5874 | 20 (20) | 20/20 / 20/20 | same 20 | 0 | no regression flagged (no measurable changed lines) | n/a | 1 |
| #5878 | 25 (25) | 25/25 / 25/25 | same 25 | 0 | no regression flagged | 100% of 15 lines | 3 |
| #5879 | 25 (25) | 24/25 / 24/25 | invalid 1, same 24 | 0 | no regression flagged | 94% of 35 lines | 4 |
| #5881 | 20 (20) | 19/20 / 19/20 | invalid 1, same 19 | 0 | no regression flagged (no measurable changed lines) | n/a | 3 |
| #5883 | 25 (25) | 25/25 / 25/25 | same 25 | 0 | no regression flagged | 94% of 223 lines | 4 |
| #5884 | 24 (24) | 24/24 / 24/24 | same 24 | 0 | no regression flagged | 95% of 82 lines | 3 |
| #5885 | 25 (25) | 25/25 / 25/25 | same 25 | 0 | no regression flagged, INCONCLUSIVE: only 38% of changed lines reached | 38% of 862 lines | 3 |
| #5886 | 23 (23) | 23/23 / 23/23 | same 23 | 0 | no regression flagged | 85% of 178 lines | 3 |
| #5887 | 25 (25) | 25/25 / 25/25 | same 25 | 0 | no regression flagged | 100% of 30 lines | 2 |
| #5889 | 25 (25) | 21/25 / 21/25 | invalid 4, same 21 | 0 | no regression flagged, INCONCLUSIVE: only 75% of changed lines reached | 75% of 168 lines | 4 |
| #5890 | 25 (25) | 0/25 / 0/25 | compile_diff 25 | 25 | REGRESSION CANDIDATE | n/a | 4 |
| #5902 | 25 (25) | 25/25 / 21/25 | compile_diff 4, same 21 | 4 | no regression flagged | 100% of 19 lines | 5 |
| #5908 | 25 (25) | 25/25 / 25/25 | same 25 | 0 | no regression flagged, INCONCLUSIVE: only 75% of changed lines reached | 75% of 220 lines | 2 |
| #5915 | 25 (25) | 25/25 / 25/25 | output_diff 6, same 19 | 6 | no regression flagged | 100% of 5 lines | 4 |
| #5916 | 25 (25) | 23/25 / 23/25 | invalid 2, same 23 | 0 | no regression flagged | 100% of 2 lines | 4 |
| #5918 | 20 (20) | 20/20 / 20/20 | output_diff 7, same 13 | 7 | no regression flagged | 100% of 1 lines | 2 |
| #5920 | 21 (21) | 21/21 / 21/21 | same 21 | 0 | no regression flagged (no measurable changed lines) | n/a | 2 |
| #5921 | 25 (25) | 4/25 / 4/25 | invalid 21, same 4 | 0 | no regression flagged (no measurable changed lines) | n/a | 4 |
| #5926 | 25 (25) | 20/25 / 20/25 | invalid 5, same 20 | 0 | no regression flagged | 94% of 16 lines | 4 |
| #5927 | 9 (9) | 9/9 / 9/9 | output_diff 4, same 5 | 4 | no regression flagged, INCONCLUSIVE: only 70% of changed lines reached | 70% of 23 lines | 4 |
| #5929 | 25 (25) | 25/25 / 25/25 | output_diff 5, same 20 | 5 | no regression flagged | 100% of 12 lines | 3 |
| #5930 | 25 (25) | 24/25 / 24/25 | invalid 1, output_diff 10, same 14 | 10 | no regression flagged | 97% of 31 lines | 5 |
| #5931 | 10 (10) | 10/10 / 10/10 | same 10 | 0 | no regression flagged, INCONCLUSIVE: only 0% of changed lines reached | 0% of 15 lines | 4 |
| #5936 | 25 (25) | 25/25 / 25/25 | output_diff 11, same 14 | 11 | no regression flagged | 100% of 6 lines | 4 |
| #5940 | 25 (25) | 25/25 / 25/25 | output_diff 1, same 24 | 1 | no regression flagged, INCONCLUSIVE: only 74% of changed lines reached | 74% of 153 lines | 4 |
| #5942 | 25 (25) | 23/25 / 23/25 | invalid 2, same 23 | 0 | no regression flagged (no measurable changed lines) | n/a | 4 |
| #5964 | 24 (24) | 23/24 / 23/24 | compile_diff 1, same 23 | 1 | no regression flagged | 100% of 15 lines | 3 |
| #5966 | 20 (20) | 20/20 / 0/20 | compile_diff 20 | 20 | no regression flagged (no measurable changed lines) | n/a | 4 |
| #5968 | 25 (25) | 23/25 / 23/25 | invalid 2, same 23 | 0 | no regression flagged | 96% of 22 lines | 4 |
| #5969 | 25 (25) | 25/25 / 25/25 | same 25 | 0 | no regression flagged | 100% of 5 lines | 3 |
| #5971 | 25 (25) | 25/25 / 25/25 | same 25 | 0 | no regression flagged | 100% of 2 lines | 3 |
| #5975 | 25 (25) | 25/25 / 25/25 | same 25 | 0 | no regression flagged | 92% of 97 lines | 4 |
| #5976 | 25 (25) | 25/25 / 25/25 | same 25 | 0 | no regression flagged | 100% of 17 lines | 2 |
| #5978 | 25 (25) | 25/25 / 25/25 | same 25 | 0 | no regression flagged, INCONCLUSIVE: only 70% of changed lines reached | 70% of 37 lines | 3 |
| #5979 | 25 (25) | 25/25 / 25/25 | same 25 | 0 | no regression flagged | 94% of 103 lines | 4 |
| #5980 | 25 (25) | 25/25 / 25/25 | same 25 | 0 | no regression flagged | 88% of 83 lines | 3 |
| #5981 | 25 (25) | 25/25 / 25/25 | same 25 | 0 | no regression flagged, INCONCLUSIVE: only 48% of changed lines reached | 48% of 58 lines | 2 |
| #5984 | 25 (25) | 25/25 / 25/25 | same 25 | 0 | no regression flagged, INCONCLUSIVE: only 7% of changed lines reached | 7% of 14 lines | 4 |
| #5990 | 20 (20) | 20/20 / 20/20 | output_diff 9, same 11 | 9 | no regression flagged | 100% of 9 lines | 2 |
| #5991 | 25 (25) | 24/25 / 24/25 | invalid 1, same 24 | 0 | no regression flagged | 100% of 6 lines | 4 |
| #5992 | 25 (25) | 24/25 / 24/25 | compile_diff 1, output_diff 8, same 16 | 9 | no regression flagged | 100% of 3 lines | 4 |
| #5996 | 24 (24) | 23/24 / 23/24 | invalid 1, same 23 | 0 | no regression flagged | 100% of 10 lines | 4 |
| #5998 | 25 (25) | 24/25 / 24/25 | invalid 1, same 24 | 0 | no regression flagged, INCONCLUSIVE: only 27% of changed lines reached | 27% of 11 lines | 4 |
| #5999 | 25 (25) | 24/25 / 24/25 | compile_diff 1, same 24 | 1 | no regression flagged | 100% of 5 lines | 4 |
| #6000 | 25 (25) | 25/25 / 25/25 | same 25 | 0 | no regression flagged | 100% of 49 lines | 3 |
| #6001 | 25 (25) | 23/25 / 23/25 | invalid 2, same 23 | 0 | no regression flagged, INCONCLUSIVE: only 70% of changed lines reached | 70% of 10 lines | 4 |
| #6002 | 20 (20) | 20/20 / 20/20 | output_diff 2, same 18 | 2 | no regression flagged | 100% of 15 lines | 2 |
| #6003 | 25 (25) | 25/25 / 25/25 | same 25 | 0 | no regression flagged (no measurable changed lines) | n/a | 4 |
| #6005 | 25 (25) | 0/25 / 0/25 | compile_diff 25 | 25 | REGRESSION CANDIDATE | n/a | 3 |
| #6008 | 20 (20) | 20/20 / 20/20 | same 20 | 0 | no regression flagged | 100% of 2 lines | 1 |
| #6009 | 20 (20) | 20/20 / 20/20 | same 20 | 0 | no regression flagged (no measurable changed lines) | n/a | 3 |
| #6012 | 25 (25) | 25/25 / 0/25 | compile_diff 25 | 25 | no regression flagged, INCONCLUSIVE: only 50% of changed lines reached | 50% of 2 lines | 5 |
| #6013 | 20 (20) | 18/20 / 18/20 | invalid 2, same 18 | 0 | no regression flagged | 100% of 1 lines | 3 |
| #6015 | 25 (25) | 25/25 / 25/25 | same 25 | 0 | no regression flagged | 100% of 3 lines | 4 |
| #6016 | 20 (20) | 20/20 / 20/20 | same 20 | 0 | no regression flagged | 100% of 3 lines | 2 |
| #6020 | 25 (25) | 25/25 / 25/25 | same 25 | 0 | no regression flagged | 100% of 4 lines | 3 |
| #6023 | 23 (23) | 22/23 / 22/23 | invalid 1, same 22 | 0 | no regression flagged | 100% of 2 lines | 4 |
| #6028 | 20 (20) | 20/20 / 20/20 | same 20 | 0 | no regression flagged | 100% of 17 lines | 2 |
| #6029 | 25 (25) | 21/25 / 20/25 | compile_diff 5, same 20 | 5 | no regression flagged | 100% of 5 lines | 5 |
| #6030 | 25 (25) | 24/25 / 24/25 | invalid 1, output_diff 1, same 23 | 1 | no regression flagged | 93% of 60 lines | 5 |
| #6039 | 20 (20) | 20/20 / 20/20 | same 20 | 0 | no regression flagged | 100% of 18 lines | 2 |
| #6049 | 20 (20) | 13/20 / 13/20 | invalid 7, same 13 | 0 | no regression flagged (no measurable changed lines) | n/a | 3 |
| #6073 | 25 (25) | 25/25 / 17/25 | compile_diff 8, same 17 | 8 | no regression flagged (no measurable changed lines) | n/a | 5 |
| #6075 | 25 (25) | 25/25 / 25/25 | same 25 | 0 | no regression flagged (no measurable changed lines) | n/a | 2 |
| #6076 | 25 (25) | 25/25 / 25/25 | output_diff 5, same 20 | 5 | no regression flagged | 99% of 119 lines | 3 |
| #6077 | 25 (25) | 25/25 / 25/25 | same 25 | 0 | no regression flagged, INCONCLUSIVE: only 10% of changed lines reached | 10% of 10 lines | 3 |
| #6078 | 25 (25) | 25/25 / 25/25 | output_diff 1, same 24 | 1 | no regression flagged | 86% of 22 lines | 3 |
| #6081 | 6 (6) | 6/6 / 6/6 | same 6 | 0 | no regression flagged | 100% of 4 lines | 3 |
| #6084 | 20 (20) | 0/20 / 0/20 | invalid 20 | 0 | no regression flagged (no measurable changed lines) | n/a | 3 |
| #6085 | 20 (20) | 2/20 / 2/20 | invalid 18, same 2 | 0 | no regression flagged (no measurable changed lines) | n/a | 3 |
| #6117 | 25 (25) | 25/25 / 25/25 | invalid 1, same 24 | 0 | no regression flagged | 86% of 7 lines | 3 |
| #6119 | 20 (20) | 20/20 / 20/20 | output_diff 5, same 15 | 5 | no regression flagged | 100% of 3 lines | 3 |
| #6121 | 25 (25) | 22/25 / 22/25 | compile_diff 3, output_diff 1, same 21 | 4 | no regression flagged | 99% of 70 lines | 6 |

## PR #4958: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 compile_diff [both] | 6 | unintended (high) | These test programs fail to compile on the new version because the custom key type lacks an operator< to compare against std::string when used in underlying container lookups. |
| C2 output_diff | 4 | intended (high) | The PR intended to enable std::string_view-convertible types as valid keys for operator[] and other lookup functions, which these programs now successfully support. |
| C3 output_diff | 3 | intended (high) | Enabling std::string_view-convertible types as keys allows writing and accessing values using such keys, as demonstrated here. |
| C4 compile_diff [both] | 1 | unintended (high) | This test case fails to compile on the new version due to the missing operator< between the custom key type and std::string in the underlying map. |
| C5 output_diff | 1 | intended (high) | The trait is_usable_as_basic_json_key_type was explicitly updated to return true for types convertible to std::string_view. |
| C6 compile_diff [both] | 1 | unintended (high) | Compilation fails on ordered_json because the custom type does not satisfy the comparator requirements of ordered_map. |
| C7 output_diff | 1 | intended (high) | The trait correctly evaluates to true for non-transparent usage when the key type is convertible to std::string_view. |
| C8 output_diff | 1 | intended (high) | The trait correctly recognizes cv-ref types of std::string_view convertible objects as usable keys. |
| C9 output_diff | 1 | intended (high) | The trait correctly evaluates to true for ordered_json with types convertible to std::string_view. |

### Finding: PR #4958 C1 (unintended, high)

These test programs fail to compile on the new version because the custom key type lacks an operator< to compare against std::string when used in underlying container lookups.

- Example program: `data/nlohmann-json/tests/4958/gen_02.cpp` (6 in cluster)
- Old version: compile error: no matching function for call to ‘nlohmann::json_abi_v3_12_0::basic_json<>::contains(MyKeyType)’
- New version: compile error: no match for call to ‘(const std::less<void>) (const MyKeyType&, const std::__cxx11::basic_string<char>&)’

### Finding: PR #4958 C4 (unintended, high)

This test case fails to compile on the new version due to the missing operator< between the custom key type and std::string in the underlying map.

- Example program: `data/nlohmann-json/tests/4958/gen_07.cpp` (1 in cluster)
- Old version: compile error: no match for ‘operator[]’ (operand types are ‘const nlohmann::json_abi_v3_12_0::json’ {aka ‘const nlohmann::json_abi_v3_12_0::basic_json<>’}
- New version: compile error: no match for call to ‘(const std::less<void>) (const ConstKeyType&, const std::__cxx11::basic_string<char>&)’

### Finding: PR #4958 C6 (unintended, high)

Compilation fails on ordered_json because the custom type does not satisfy the comparator requirements of ordered_map.

- Example program: `data/nlohmann-json/tests/4958/gen_13.cpp` (1 in cluster)
- Old version: compile error: no match for ‘operator[]’ (operand types are ‘nlohmann::json_abi_v3_12_0::ordered_json’ {aka ‘nlohmann::json_abi_v3_12_0::basic_json<nlohman
- New version: compile error: no matching function for call to ‘nlohmann::json_abi_v3_12_0::ordered_map<std::__cxx11::basic_string<char>, nlohmann::json_abi_v3_12_0::basi

## PR #4965: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 output_diff | 8 | intended (high) | The pull request explicitly adds support for JSON Merge Patch diff creation via the new public static method basic_json::merge_diff. |

## PR #5328: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5358: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 output_diff | 1 | intended (high) | The PR explicitly changes tokens like "01" that cannot be valid array indices to create objects instead of throwing a parse error. |
| C2 output_diff | 1 | intended (high) | The PR explicitly handles the empty reference token ("") by treating it as an object key rather than throwing an out-of-range exception. |
| C3 output_diff | 1 | intended (high) | The PR changes nested path traversal with non-index tokens like "01" on null values to correctly instantiate objects. |
| C4 output_diff | 1 | intended (high) | Tokens with multiple leading zeros like "00" cannot be valid array indices and are intended to create objects. |
| C5 output_diff | 1 | intended (high) | Constructing a json_pointer with a slash ("/") yields an empty reference token, which the PR now maps to an object key. |
| C6 output_diff | 1 | intended (high) | Deeply nested paths with leading-zero tokens like "007" correctly create objects instead of throwing a parse error. |
| C7 output_diff | 1 | intended (high) | Applies the same intended object creation behavior for non-index tokens on ordered_json. |

## PR #5459: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 output_diff | 1 | intended (high) | The PR aims to fix intransitive equality near 2^63 by comparing integers and floats exactly rather than widening them, so 2^63-2 and 2^63 no longer compare equal. |
| C2 output_diff | 1 | intended (high) | The PR fixes strict weak ordering violations for mixed integer/float comparisons near 2^63, changing `<` results to reflect exact comparison. |
| C3 output_diff | 1 | intended (high) | The PR extends exact comparison to large unsigned integers and floats, preventing lossy widening conversions. |
| C4 output_diff | 1 | intended (high) | The PR updates mixed negative integer and float comparisons to be exact. |
| C5 output_diff | 1 | intended (high) | Fixing transitivity of incomparability (equivalence) near 2^63 is explicitly stated in the pull request description and issue #5401. |
| C6 output_diff | 1 | intended (high) | Using these numbers as keys in associative containers like std::map requires a valid strict weak ordering, which this PR restores by preventing lossy collisions. |
| C7 output_diff | 1 | intended (high) | Symmetric comparison operators (float vs integer) are updated alongside integer vs float to maintain consistent and exact comparisons. |
| C8 output_diff | 1 | intended (high) | Relational operator outcomes are corrected from lossy approximations to exact comparisons as requested by the PR. |

## PR #5585: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5701: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5707: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 output_diff | 1 | intended (high) | The PR specifically changes from_bjdata() to return annotation keys in the order _ArrayType_, _ArraySize_, _ArrayData_ instead of _ArraySize_, _ArrayType_, _ArrayData_ to match the documentation and make ordered_json round-trips compare equal. |

## PR #5740: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 compile_diff [old] | 3 | intended (high) | The PR explicitly adds the tag_handler parameter to sax_parse signatures, allowing previously rejected calls with tag handlers to compile and parse correctly. |
| C2 output_diff | 2 | intended (high) | The added overloads and new parameter make sax_parse accept the new tag handler argument and successfully parse tagged CBOR / JSON inputs as intended by the PR. |

## PR #5758: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 compile_diff [old] | 13 | intended (high) | The PR adds the with_*_t alias templates to basic_json, which makes these test programs compile and work successfully as designed. |
| C2 output_diff | 8 | intended (high) | The PR introduces the new with_*_t member alias templates, so type trait probes successfully detect and use them now. |
| C3 compile_diff [both] | 1 | unclear (high) | The test program fails to compile on the new version due to an invalid numeric literal suffix in its own code ('3.14m'), making it an invalid test case for library functionality. |
| C4 compile_diff [both] | 1 | unclear (high) | The test program fails to compile on the new version due to passing std::allocator (a class template taking one argument) where an allocator template taking one typename is expected by with_allocator_t, representing a mistake in the test program. |
| C5 compile_diff [both] | 1 | unclear (high) | The test program fails to compile on the new version because it attempts to query json_serializer with template arguments incorrectly in its own std::is_same check. |

## PR #5760: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 output_diff | 4 | intended (high) | The PR explicitly states that NUL bytes inside UBJSON/BJData high-precision number payloads should be rejected with parse_error.115 rather than being accepted based on a prefix. |
| C2 output_diff | 2 | intended (high) | This case tests a high-precision number payload containing a trailing NUL byte, which the PR description specifically lists as a regression case now correctly rejected with parse_error.115. |
| C3 output_diff | 2 | intended (high) | The PR ensures that a NUL encountered within a high-precision payload reports the exact byte offset of the NUL (byte 4) rather than treating it as a standard end of input check after lexing. |
| C4 output_diff | 2 | intended (high) | This is a nested array regression case mentioned in the PR description, correctly rejected when containing a malformed high-precision number with a NUL byte. |
| C5 output_diff | 2 | intended (high) | The PR changes the high-precision payload reading loop to detect NUL bytes immediately during reading, causing it to report parse_error.115 at the NUL byte instead of reaching a later end-of-input error. |

## PR #5766: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 output_diff | 3 | intended (high) | The PR modified chunk error messages to omit 'or indefinite string type (0x7F)' when inside an indefinite-length string, which changes the exception message for invalid chunks as intended. |
| C2 output_diff | 2 | intended (high) | The PR introduces specific error messages for nested indefinite-length strings and binary arrays, matching the substring checks in these regression tests. |
| C3 output_diff | 2 | intended (high) | Nested indefinite-length strings are now correctly rejected per RFC 8949 §3.2.3, causing ordered_json parsing to throw a parse error. |
| C4 output_diff | 1 | intended (high) | The PR explicitly changes behavior to reject nested indefinite-length CBOR strings with parse_error.113. |
| C5 output_diff | 1 | intended (high) | The PR explicitly changes behavior to reject nested indefinite-length CBOR binary arrays with parse_error.113. |
| C6 output_diff | 1 | intended (high) | The PR rejects any second indefinite-length marker inside an indefinite-length string, preventing deeply nested or recursive chunks. |
| C7 output_diff | 1 | intended (high) | The chunk error message update correctly drops the mention of indefinite types when inside an indefinite-length context. |
| C8 output_diff | 1 | intended (high) | SAX parsing now correctly reports a parse error when encountering invalid nested indefinite-length strings. |
| C9 output_diff | 1 | intended (high) | When exceptions are disabled, parsing invalid nested indefinite-length strings correctly returns a discarded json value. |
| C10 output_diff | 1 | intended (high) | Nested indefinite-length strings inside arrays are correctly rejected with parse_error.113. |
| C11 output_diff | 1 | intended (high) | Nested indefinite-length strings used as object keys are correctly rejected with parse_error.113. |
| C12 output_diff | 1 | intended (high) | Deeply nested indefinite-length binary arrays are caught early at the second indefinite marker with parse_error.113 instead of failing later on EOF. |

## PR #5772: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 output_diff | 10 | intended (high) | The PR explicitly changes std::hash to make numbers that compare equal (such as 0, 0U, 0.0, and -0.0 normalized to 0.0) hash identically, satisfying a == b implies hash(a) == hash(b). |
| C2 output_diff | 1 | intended (high) | Resolving the hash mismatch allows unordered containers like std::unordered_set to correctly treat equal numbers of different types as duplicates, reducing the set size from 3 to 1 as intended. |
| C3 output_diff | 1 | intended (high) | Lookup in unordered containers using cross-type equal numbers now successfully finds the key instead of missing and throwing, which was the primary bug reported in #5400. |

## PR #5776: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5779: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5781: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5782: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5791: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5792: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5793: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5795: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 compile_diff [old] | 1 | unclear (high) | The test program probes an internal library detail (nlohmann::detail::detect_equal_comparable) that was newly added in this PR, so the compilation failure on the old version says nothing about the public API. |

## PR #5797: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5800: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 output_diff | 3 | intended (high) | The PR specifically changes one-character non-numeric array indices like '/x' to throw parse_error.109 instead of out_of_range.404. |
| C2 output_diff | 3 | intended (high) | The PR changes one-character non-numeric tokens such as '/x' accessed via json_pointer to report parse_error.109 instead of out_of_range.404. |
| C3 output_diff | 1 | intended (high) | The PR states that value(json_pointer, default) on an array with a one-character non-numeric token now throws parse_error.109 instead of returning the default value. |
| C4 output_diff | 1 | intended (high) | The PR changes the behavior for one-character non-numeric tokens like '/y' in array indexing via value(), causing it to throw parse_error.109 instead of returning the fallback value. |

## PR #5802: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 output_diff | 3 | intended (high) | The PR explicitly states that serializing discarded values to BON8 should throw type_error.321 instead of producing malformed output. |
| C2 output_diff | 2 | intended (high) | Discarded values at the top level now correctly throw type_error.321 as described in the PR description. |
| C3 output_diff | 2 | intended (high) | Nested discarded values in arrays now correctly trigger type_error.321 instead of being skipped. |
| C4 output_diff | 1 | intended (high) | Deeply nested discarded values in objects now correctly throw type_error.321. |
| C5 output_diff | 1 | intended (high) | Discarded values inside arrays are correctly rejected with type_error.321. |
| C6 output_diff | 1 | intended (high) | Discarded values inside objects are correctly rejected with type_error.321. |
| C7 output_diff | 1 | intended (high) | Multiple discarded values inside arrays correctly throw type_error.321. |
| C8 output_diff | 1 | intended (high) | Deeply nested discarded values in mixed structures correctly throw type_error.321. |
| C9 output_diff | 1 | intended (high) | Discarded values in ordered_json objects correctly trigger type_error.321 when serialized via to_bon8. |
| C10 output_diff | 1 | intended (high) | The thrown exception correctly carries error ID 321 for discarded values. |
| C11 output_diff | 1 | intended (high) | Discarded elements at the end of large arrays correctly throw type_error.321. |
| C12 output_diff | 1 | intended (high) | Throwing an exception on discarded values does not prevent subsequent successful serializations of valid JSON values. |

## PR #5805: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5806: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5810: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5813: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5822: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5824: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5829: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5831: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5832: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5833: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5834: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 output_diff | 2 | intended (high) | The PR explicitly introduces the public member `ordered_map::emplace_new_key`, which these probe programs test and correctly find supported on the new version. |

## PR #5835: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5836: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 compile_diff [old] | 1 | intended (high) | The PR explicitly introduces escape_into as a new helper function in detail to improve string formatting performance for json_pointer. |

## PR #5837: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 output_diff | 1 | intended (high) | The PR description explicitly states that json j = std::move(container) now moves elements instead of copying them, leaving the moved-from elements empty. |
| C2 output_diff | 1 | intended (high) | The PR description states that rvalue containers like std::list are moved from rather than copied. |
| C3 output_diff | 1 | intended (high) | The PR description states that rvalue containers like std::deque are moved from rather than copied. |
| C4 output_diff | 1 | intended (high) | The PR description states that rvalue containers like std::forward_list are moved from rather than copied. |
| C5 output_diff | 1 | intended (high) | The PR description notes that nested vectors support the new rvalue move conversion. |
| C6 output_diff | 1 | intended (high) | The PR description mentions that std::array rvalues are converted via the new moving overloads. |
| C7 output_diff | 1 | intended (high) | The PR description states that object-like containers from rvalues use the new moving constructors. |
| C8 output_diff | 1 | intended (high) | The PR description states that object-like containers from rvalues use the new moving constructors. |
| C9 compile_diff [old] | 1 | unclear (high) | The test program probes internal library details (external_constructor::construct_moving) which are not part of the public API. |

## PR #5839: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5840: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5842: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5843: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5851: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5852: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5854: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5855: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5859: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5861: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5866: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 compile_diff [old] | 2 | intended (high) | The PR specifically renames the prefix tree member 'slots' to 'table' to prevent macro collisions when Qt's keyword macros are defined. |
| C2 compile_diff [both] | 1 | unclear (high) | The test program itself is incomplete and fails to compile on the new version due to a syntax error ('R' macro/raw string literal left hanging). |

## PR #5874: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5878: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5879: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5881: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5883: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5884: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5885: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5886: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5887: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5889: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5890: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 compile_diff [new] | 19 | unintended (high) | The new version introduces a compilation error in basic_json_view due to referencing the undeclared template parameter 'Editable' instead of 'IsEditable' or similar, breaking previously compiling code. |
| C2 compile_diff [both] | 5 | unintended (high) | The library header fails to compile with the same syntax error in basic_json_view, breaking compilation on new. |
| C3 compile_diff [both] | 1 | unintended (high) | The library header compilation fails due to the same syntax error in basic_json_view, preventing even valid internal checks from proceeding. |

### Finding: PR #5890 C1 (unintended, high)

The new version introduces a compilation error in basic_json_view due to referencing the undeclared template parameter 'Editable' instead of 'IsEditable' or similar, breaking previously compiling code.

- Example program: `data/nlohmann-json/tests/5890/gen_01.cpp` (19 in cluster)
- Old version: output: Equal: 1
- New version: compile error: ‘Editable’ was not declared in this scope

### Finding: PR #5890 C2 (unintended, high)

The library header fails to compile with the same syntax error in basic_json_view, breaking compilation on new.

- Example program: `data/nlohmann-json/tests/5890/gen_04.cpp` (5 in cluster)
- Old version: compile error: ‘nlohmann::image_check’ has not been declared
- New version: compile error: ‘Editable’ was not declared in this scope

### Finding: PR #5890 C3 (unintended, high)

The library header compilation fails due to the same syntax error in basic_json_view, preventing even valid internal checks from proceeding.

- Example program: `data/nlohmann-json/tests/5890/gen_05.cpp` (1 in cluster)
- Old version: compile error: ‘constexpr const bool nlohmann::json_abi_v3_12_0::basic_json_view<nlohmann::json_abi_v3_12_0::basic_json<>, nlohmann::json_abi_v3_12_0::view
- New version: compile error: ‘Editable’ was not declared in this scope

## PR #5902: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 compile_diff [old] | 2 | unclear (high) | The test programs probe newly added internal detail components (`nlohmann::detail::is_trivial_element`) that are not part of the library's public API. |
| C2 compile_diff [old] | 2 | unclear (high) | The test programs probe newly added internal detail functions (`nlohmann::detail::from_json_make_array`) that are not part of the library's public API. |

## PR #5908: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5915: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 output_diff | 1 | intended (high) | The PR changes the initial sizing of the decoded string buffer to avoid extra reallocations, which alters the total memory usage for documents with escapes as stated in the description. |
| C2 output_diff | 1 | intended (high) | The PR increases the maximum inline nodes allocated with the header from 256 to 1024, which directly changes memory usage for dense numeric documents as described in the trade-off section. |
| C3 output_diff | 1 | intended (high) | This document has fewer than 1024 nodes and falls under the increased inline node allocation limit, intentionally resulting in higher memory usage due to inline allocation. |
| C4 output_diff | 1 | intended (high) | The change in memory usage for this document with 5000 nodes is an intended side effect of the new initial string buffer sizing logic. |
| C5 output_diff | 1 | intended (high) | As with C3, this document of 1024 nodes now benefits from the increased max_inline_nodes limit, changing its memory footprint as intended. |
| C6 output_diff | 1 | intended (high) | This document has 1025 nodes, sitting right above the new 1024 inline node limit, and reflects the updated memory allocation behavior. |

## PR #5916: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5918: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 output_diff | 7 | intended (high) | The PR fixes an issue where JSON Patch 'add' operations on a null parent silently converted the null into an object instead of throwing out_of_range.411, as described in the PR description and RFC 6902. |

## PR #5920: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5921: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5926: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5927: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 output_diff | 2 | intended (high) | The PR description explicitly states that from_cbor with cbor_tag_handler_t::ignore or store now skips tags in front of a text string map key. |
| C2 output_diff | 1 | intended (high) | This is covered by the PR goal to skip tags in front of map keys when using cbor_tag_handler_t::ignore. |
| C3 output_diff | 1 | intended (high) | The PR now attempts to read the tag argument when encountering extended tag headers before a key, leading to a correct unexpected end of input error instead of failing on the tag itself. |

## PR #5929: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 output_diff | 3 | intended (high) | The PR description explicitly states that optimized containers with count 0 and an invalid '$' type marker (such as 'x' or BJData-only markers like 'B' in UBJSON) now correctly trigger a parse error (parse_error.112) instead of being accepted as empty containers. |
| C2 output_diff | 1 | intended (high) | The PR description explicitly states that optimized object containers with count 0 and an invalid type marker now trigger parse_error.112 instead of returning an empty object. |
| C3 output_diff | 1 | intended (high) | The PR notes state that '[$#' now reports 112 instead of 110, and validates the type marker right after '$' even when count is 0, changing the error location and message appropriately. |

## PR #5930: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 output_diff | 5 | intended (high) | The PR description explicitly states that document sizes below 5 are now checked earlier and rejected with parse error 112 instead of failing later during element parsing. |
| C2 output_diff | 3 | intended (high) | The PR implements strict validation for BSON binary subtype 0x02, requiring an inner length matching the outer length minus 4 and reporting parse error 112 if validation fails. |
| C3 output_diff | 1 | intended (high) | Reading truncated binary subtype 0x02 now correctly identifies the failure during the inner length number read rather than generic binary input exhaustion. |
| C4 output_diff | 1 | intended (high) | The PR introduces early checks ensuring embedded documents end before their parent document, reporting the expected size violation earlier. |

## PR #5931: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5936: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 output_diff | 3 | intended (high) | The PR specifically fixes self-aliasing in json_pointer::operator/= by appending a copy, changing self-appends from undefined behavior producing trailing slashes to correctly duplicating tokens. |
| C2 output_diff | 1 | intended (high) | Multiple self-appends via operator/= now correctly duplicate the pointer tokens rather than hitting undefined behavior. |
| C3 output_diff | 1 | intended (high) | Self-appending a json_pointer results in a pointer equal to the duplicated sequence, which the PR's fix correctly achieves. |
| C4 output_diff | 1 | intended (high) | Self-appending via operator/= before subsequent operations now correctly builds the duplicated path. |
| C5 output_diff | 1 | intended (high) | Tokens containing numbers or slashes self-append correctly as intended by the self-aliasing fix. |
| C6 output_diff | 1 | intended (high) | Independent self-appends on multiple json_pointers are correctly handled by the safety check for `&ptr == this`. |
| C7 output_diff | 1 | intended (high) | Escaped characters in json_pointer tokens self-append correctly due to the added self-aliasing protection. |
| C8 output_diff | 1 | intended (high) | Equality checks between a self-appended json_pointer and the explicitly expanded path now evaluate to match. |
| C9 output_diff | 1 | intended (high) | Passing a self-reference via a helper function correctly triggers the `&ptr == this` check and successfully produces the copied path. |

## PR #5940: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 output_diff | 1 | intended (high) | The PR explicitly states its goal is to provide the strong exception guarantee for non-const operator[](json_pointer), rolling back partially created structures such as an array created during a failed pointer resolution. The test demonstrates this exact rollback behavior, changing the resulting JSON state from a partially padded array `{"arr":[]}` back to `null`. |

## PR #5942: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5964: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 compile_diff [both] | 1 | unclear (high) | The test program accesses private member 'magnitude_has_at_most_64_bits' of the serializer class, which is not part of the public API. |

## PR #5966: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 compile_diff [old] | 20 | intended (high) | The PR specifically sets out to fix a build failure caused by a duplicate `is_editable` member and an undeclared `Editable` parameter in `basic_json_view`. Removing this duplicate member fixes the compilation error demonstrated in these test programs, which is the exact goal stated in the PR. |

## PR #5968: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5969: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5971: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5975: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5976: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5978: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5979: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5980: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5981: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5984: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5990: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 output_diff | 1 | intended (high) | The PR specifically aims to include the byte range for root value exceptions when both JSON_DIAGNOSTICS and JSON_DIAGNOSTIC_POSITIONS are set. |
| C2 output_diff | 1 | intended (high) | This is the json_view equivalent of C1, intended to include byte ranges for root value exceptions in views. |
| C3 output_diff | 1 | intended (high) | Root value error on json_view with .at("b") now correctly reports its byte range due to the fix. |
| C4 output_diff | 1 | intended (high) | Root object exception now displays the byte range as intended by the PR. |
| C5 output_diff | 1 | intended (high) | Root array exception now correctly includes its byte range. |
| C6 output_diff | 1 | intended (high) | Root string exception now includes its byte range. |
| C7 output_diff | 1 | intended (high) | Root patch_inplace error now reports the byte range. |
| C8 output_diff | 1 | intended (high) | Root update() error now includes the byte range. |
| C9 output_diff | 1 | intended (high) | Root number_token error on a json_view now correctly includes the byte range. |

## PR #5991: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5992: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 output_diff | 4 | intended (high) | The PR specifically changes json_view::get<T>() of a boolean to throw type_error.302 for number_integer_t and number_unsigned_t, matching basic_json behavior. |
| C2 output_diff | 1 | intended (high) | get_to() goes through get<T>() and is explicitly mentioned in the PR description as adopting the same exception behavior for number types. |
| C3 compile_diff [both] | 1 | unclear (high) | The test program calls private library details (boolean_as) and non-public members (*doc.data()), which makes it invalid regarding public API behavior. |
| C4 output_diff | 1 | intended (high) | Accessing a boolean node via a view path and calling get<std::int64_t>() now correctly throws type_error.302 to match basic_json parity. |
| C5 output_diff | 1 | intended (high) | Getting a boolean as number_unsigned_t via json_view now correctly throws an exception instead of returning 0, aligning with basic_json. |
| C6 output_diff | 1 | intended (high) | Getting a boolean as number_float_t via json_view now correctly throws an exception instead of returning 1, aligning with basic_json. |

## PR #5996: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5998: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5999: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 compile_diff [both] | 1 | unclear (high) | The test program does not invoke dump(), which is the only feature affected by the missing capacity() method according to the PR description; the compile errors shown occur during parsing, which fails for reasons unrelated to this PR. |

## PR #6000: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #6001: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #6002: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 output_diff | 1 | intended (high) | The PR explicitly states that a BJData container count equal to SIZE_MAX (e.g. 0xFFFFFFFFFFFFFFFF for M) is now rejected with out_of_range.408 ('integer value overflow') instead of being parsed as no count or failing with unexpected end of input. |
| C2 output_diff | 1 | intended (high) | Like C1, this BJData input uses a container count of SIZE_MAX for marker M, which the PR specifically targets to reject with an out_of_range.408 overflow error. |

## PR #6003: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #6005: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 compile_diff [new] | 23 | unintended (high) | The PR removed the `null_result` parameter from `JSON_IMPLEMENT_OPERATOR` but forgot to remove its usage or handle it for operator==, causing compilation errors on ordinary scalar comparisons like `a == b`. |
| C2 compile_diff [both] | 2 | unintended (high) | Like C1, these programs fail inside the library headers due to the missing `null_result` macro parameter when operator== or operator< are expanded, even though the test programs also contain syntax errors. |

### Finding: PR #6005 C1 (unintended, high)

The PR removed the `null_result` parameter from `JSON_IMPLEMENT_OPERATOR` but forgot to remove its usage or handle it for operator==, causing compilation errors on ordinary scalar comparisons like `a == b`.

- Example program: `data/nlohmann-json/tests/6005/gen_01.cpp` (23 in cluster)
- Old version: output: null equal: 1
- New version: compile error: ‘null_result’ was not declared in this scope

### Finding: PR #6005 C2 (unintended, high)

Like C1, these programs fail inside the library headers due to the missing `null_result` macro parameter when operator== or operator< are expanded, even though the test programs also contain syntax errors.

- Example program: `data/nlohmann-json/tests/6005/gen_23.cpp` (2 in cluster)
- Old version: compile error: expected ‘,’ or ‘;’ before ‘nlohmann’
- New version: compile error: ‘null_result’ was not declared in this scope

## PR #6008: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #6009: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #6012: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 compile_diff [old] | 25 | intended (high) | The PR description and title explicitly state that this pull request restores the two missing commits from #6005 to fix the develop build error where 'null_result' was undeclared. |

## PR #6013: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #6015: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #6016: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #6020: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #6023: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #6028: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #6029: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 compile_diff [both] | 4 | unclear (high) | These test programs probe private internal detail structures not part of the public API, and fail to compile on the new version for unrelated reasons (using 'json' without 'using nlohmann::json'). |
| C2 compile_diff [old] | 1 | intended (high) | The PR introduces the new internal traits 'is_std_contiguous_byte_iterator' and 'is_byte_char_type' to support reading iterator pairs of std::string and std::vector as pointer ranges, making detection of these internal byte iterators available as intended. |

## PR #6030: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 output_diff | 1 | intended (high) | The PR specifically introduces bulk scanning of FILE buffers using C library internal fields on glibc and Apple, which is reflected in `supports_bulk_scan = true` and `bulk_window = true` in `file_input_adapter` as stated in the pull request description. |

## PR #6039: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #6049: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #6073: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 compile_diff [old] | 8 | intended (high) | The PR fixes a bug where passing a plain function or function pointer as a parser callback with a container (e.g. json::parse(string, cb)) failed to compile due to incorrect overload resolution via can_compare_ne. |

## PR #6075: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #6076: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 output_diff | 1 | intended (high) | The linked issue #6105 explicitly describes that ordered_json::unflatten() previously failed to reject overlapping keys and instead silently overwrote nested values, and the PR fixes this by throwing type_error.313. |
| C2 output_diff | 1 | intended (high) | As discussed in linked issue #6105, assigning null to a prefix that is overridden by a longer key is explicitly handled to leave the nested structure intact rather than overwriting it. |
| C3 output_diff | 1 | intended (high) | This is part of fixing overlapping keys for ordered_json as described in linked issue #6105, throwing type_error.313 when a prefix key conflicts with an existing value. |
| C4 output_diff | 1 | intended (high) | This fixes the overlapping key bug for arrays in ordered_json as detailed in issue #6105, throwing type_error.313 instead of silently ignoring the conflict. |
| C5 output_diff | 1 | intended (high) | Assigning null to parent prefixes that are followed by more deeply nested keys is handled correctly by preserving the nested structure per the fix in issue #6105. |

## PR #6077: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #6078: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 output_diff | 1 | intended (high) | The PR explicitly states that no-op arrays are empty and 'sax_parse reports start_array(0) for [$N#n (before: n)', which matches the difference observed in gen_06.cpp. |

## PR #6081: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #6084: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #6085: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #6117: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #6119: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 output_diff | 3 | intended (high) | The PR specifically changes BON8 parsing with strict=false to report parse_error.110 when a final string lacks 0xFF, rather than dropping the trailing bytes. |
| C2 output_diff | 1 | intended (high) | When allow_exceptions=false, an error during parsing results in a discarded json value, which matches the new parse error introduced by this PR. |
| C3 output_diff | 1 | intended (high) | The SAX parser propagates the new parse_error.110 when encountering an unterminated BON8 string even with strict=false. |

## PR #6121: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 compile_diff [both] | 3 | unclear (high) | The test program probes private library implementation details (`nlohmann::detail::token_text_buffer`) that are not part of the public API. |
| C2 output_diff | 1 | intended (high) | The PR explicitly changes the error message behavior for long tokens to truncate them with `...` instead of keeping the full text, as described in the PR description and fix for issue #6120. |
