# Report: nlohmann-json

14 PR(s) checked, 316 programs generated, 316 in use (130 repaired by fix.py). Numbers come only from the files on disk; see the module docstring of pipeline/report.py for each definition.

## Summary

| Measure | Value |
|---|---|
| PRs checked | 14 |
| Compile success, as generated (new / both versions) | 71.5% / 65.5% |
| Compile success, after fix.py (new / both versions) | 81.0% / 78.2% |
| Deterministic on both versions | 246 of 247 compiled-on-both programs (99.6%) |
| PRs with at least one behavioral difference | 7 of 14 (50.0%) |
| Differences by verdict (clusters / programs) | intended 23 / 35, unintended 3 / 8, unclear 2 / 7 |
| Regression candidates | 1 of 14 classified: #4958 |
| Changed-line coverage measured | 14 of 14 PRs; at least 80% reached for 7 |
| Clean results that are INCONCLUSIVE (coverage missing or low) | 1: #6077 |
| Changed-line coverage before / after the loop (mean over 7 PRs) | 81.0% / 82.1% |
| LLM calls (estimated) | 50 total, 3.6 per PR |
| Wall time of the run.py stage | 210.8 s |

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
| #5459 | 25 (25) | 25/25 / 25/25 | output_diff 8, same 17 | 8 | no regression flagged | 95% of 20 lines | 3 |
| #6029 | 25 (25) | 21/25 / 20/25 | compile_diff 5, same 20 | 5 | no regression flagged | 100% of 5 lines | 5 |
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

## PR #6029: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 compile_diff [both] | 4 | unclear (high) | These test programs probe private internal detail structures not part of the public API, and fail to compile on the new version for unrelated reasons (using 'json' without 'using nlohmann::json'). |
| C2 compile_diff [old] | 1 | intended (high) | The PR introduces the new internal traits 'is_std_contiguous_byte_iterator' and 'is_byte_char_type' to support reading iterator pairs of std::string and std::vector as pointer ranges, making detection of these internal byte iterators available as intended. |

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

## PR #6121: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 compile_diff [both] | 3 | unclear (high) | The test program probes private library implementation details (`nlohmann::detail::token_text_buffer`) that are not part of the public API. |
| C2 output_diff | 1 | intended (high) | The PR explicitly changes the error message behavior for long tokens to truncate them with `...` instead of keeping the full text, as described in the PR description and fix for issue #6120. |
