# Report: nlohmann-json

14 PR(s) checked, 330 programs generated, 330 in use (103 repaired by fix.py). Numbers come only from the files on disk; see the module docstring of pipeline/report.py for each definition.

## Summary

| Measure | Value |
|---|---|
| PRs checked | 14 |
| Compile success, as generated (new / both versions) | 68.5% / 62.7% |
| Compile success, after fix.py (new / both versions) | 77.6% / 74.8% |
| Deterministic on both versions | 246 of 247 compiled-on-both programs (99.6%) |
| PRs with at least one behavioral difference | 7 of 14 (50.0%) |
| Differences by verdict (clusters / programs) | intended 23 / 35, unintended 5 / 15, unclear 0 / 0 |
| Regression candidates | 3 of 14 classified: #4958, #6029, #6121 |
| Changed-line coverage measured | 14 of 14 PRs; at least 80% reached for 7 |
| Clean results that are INCONCLUSIVE (coverage missing or low) | 1: #6077 |
| Changed-line coverage before / after the loop (mean over 7 PRs) | 81.0% / 82.1% |
| LLM calls (estimated) | 53 total, 3.8 per PR |
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
| #6029 | 25 (25) | 21/25 / 20/25 | compile_diff 5, same 20 | 5 | REGRESSION CANDIDATE | 100% of 5 lines | 5 |
| #6049 | 25 (25) | 15/25 / 15/25 | invalid 10, same 15 | 0 | no regression flagged (no measurable changed lines) | n/a | 4 |
| #6073 | 25 (25) | 25/25 / 17/25 | compile_diff 8, same 17 | 8 | no regression flagged (no measurable changed lines) | n/a | 5 |
| #6075 | 25 (25) | 25/25 / 25/25 | same 25 | 0 | no regression flagged (no measurable changed lines) | n/a | 2 |
| #6076 | 25 (25) | 25/25 / 25/25 | output_diff 5, same 20 | 5 | no regression flagged | 99% of 119 lines | 3 |
| #6077 | 25 (25) | 25/25 / 25/25 | same 25 | 0 | no regression flagged, INCONCLUSIVE: only 10% of changed lines reached | 10% of 10 lines | 3 |
| #6078 | 25 (25) | 25/25 / 25/25 | output_diff 1, same 24 | 1 | no regression flagged | 86% of 22 lines | 3 |
| #6081 | 6 (6) | 6/6 / 6/6 | same 6 | 0 | no regression flagged | 100% of 4 lines | 3 |
| #6084 | 24 (24) | 0/24 / 0/24 | invalid 24 | 0 | no regression flagged (no measurable changed lines) | n/a | 4 |
| #6085 | 25 (25) | 0/25 / 0/25 | invalid 25 | 0 | no regression flagged (no measurable changed lines) | n/a | 4 |
| #6117 | 25 (25) | 25/25 / 25/25 | invalid 1, same 24 | 0 | no regression flagged | 86% of 7 lines | 3 |
| #6121 | 25 (25) | 22/25 / 22/25 | compile_diff 3, output_diff 1, same 21 | 4 | REGRESSION CANDIDATE | 99% of 70 lines | 6 |

## PR #4958: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 compile_diff [both] | 6 | unintended (high) | These test programs fail to compile on the new version with std::less/comparator errors because standard map types do not support transparent heterogeneous lookup with types implicitly convertible to string_view without a transparent comparator. |
| C2 output_diff | 4 | intended (high) | The PR's goal is to enable types convertible to std::string_view to be usable as basic_json keys in operator[] and related methods, which these programs now successfully support. |
| C3 output_diff | 3 | intended (high) | Allowing types convertible to std::string_view to be used with operator[] enables writing and reading values via such keys, matching the PR's objectives. |
| C4 compile_diff [both] | 1 | unintended (high) | Like C1, this program fails to compile on the new version due to lack of a transparent comparator supporting implicit conversions for const json instances. |
| C5 output_diff | 1 | intended (high) | The trait is_usable_as_basic_json_key_type is updated in the PR to return true for types convertible to std::string_view under C++17. |
| C6 compile_diff [both] | 1 | unintended (high) | This program fails to compile with ordered_json due to underlying container requirements with custom types convertible to string_view. |
| C7 output_diff | 1 | intended (high) | Reflects the updated trait is_usable_as_basic_json_key_type recognizing string_view convertible types when non-transparent. |
| C8 output_diff | 1 | intended (high) | Reflects the updated trait checking cv-ref qualified types that are convertible to std::string_view. |
| C9 output_diff | 1 | intended (high) | Reflects the updated trait correctly identifying types convertible to std::string_view when used with ordered_json. |

### Finding: PR #4958 C1 (unintended, high)

These test programs fail to compile on the new version with std::less/comparator errors because standard map types do not support transparent heterogeneous lookup with types implicitly convertible to string_view without a transparent comparator.

- Example program: `data/nlohmann-json/tests/4958/gen_02.cpp` (6 in cluster)
- Old version: compile error: no matching function for call to ‘nlohmann::json_abi_v3_12_0::basic_json<>::contains(MyKeyType)’
- New version: compile error: no match for call to ‘(const std::less<void>) (const MyKeyType&, const std::__cxx11::basic_string<char>&)’

### Finding: PR #4958 C4 (unintended, high)

Like C1, this program fails to compile on the new version due to lack of a transparent comparator supporting implicit conversions for const json instances.

- Example program: `data/nlohmann-json/tests/4958/gen_07.cpp` (1 in cluster)
- Old version: compile error: no match for ‘operator[]’ (operand types are ‘const nlohmann::json_abi_v3_12_0::json’ {aka ‘const nlohmann::json_abi_v3_12_0::basic_json<>’}
- New version: compile error: no match for call to ‘(const std::less<void>) (const ConstKeyType&, const std::__cxx11::basic_string<char>&)’

### Finding: PR #4958 C6 (unintended, high)

This program fails to compile with ordered_json due to underlying container requirements with custom types convertible to string_view.

- Example program: `data/nlohmann-json/tests/4958/gen_13.cpp` (1 in cluster)
- Old version: compile error: no match for ‘operator[]’ (operand types are ‘nlohmann::json_abi_v3_12_0::ordered_json’ {aka ‘nlohmann::json_abi_v3_12_0::basic_json<nlohman
- New version: compile error: no matching function for call to ‘nlohmann::json_abi_v3_12_0::ordered_map<std::__cxx11::basic_string<char>, nlohmann::json_abi_v3_12_0::basi

## PR #5459: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 output_diff | 1 | intended (high) | The PR fixes lossy integer-to-float conversions near boundaries like 2^63 that caused distinct integers to compare equal to the same float. |
| C2 output_diff | 1 | intended (high) | The PR corrects strict weak ordering for mixed number comparisons so that nearby integers are properly ordered rather than colliding with the float. |
| C3 output_diff | 1 | intended (high) | Unsigned integers near the upper float bounds are now compared exactly instead of rounding up and falsely equating to the float. |
| C4 output_diff | 1 | intended (high) | Negative integer and float comparisons near boundaries are handled with exact precision rather than lossy widening. |
| C5 output_diff | 1 | intended (high) | The PR explicitly resolves the issue where equivalence was intransitive; the new behavior correctly maintains strict weak ordering. |
| C6 output_diff | 1 | intended (high) | Using distinct numbers that previously collapsed due to precision loss as map keys now correctly distinguishes them, increasing the map size. |
| C7 output_diff | 1 | intended (high) | Symmetric comparison operators with float on the left-hand side now correctly reflect exact comparisons instead of false equalities. |
| C8 output_diff | 1 | intended (high) | Relational operators between large integers and floats are updated to use exact comparison, changing old false equalities into correct less-than relations. |

## PR #6029: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 compile_diff [both] | 4 | unintended (high) | The test program uses the unexported type alias `json` without qualifying it as `nlohmann::json`, causing a compilation error on the new version. |
| C2 compile_diff [old] | 1 | intended (high) | The PR introduces internal helpers like `is_std_contiguous_byte_iterator` and `is_byte_char_type`, allowing this test to compile successfully on the new version where it failed previously. |

### Finding: PR #6029 C1 (unintended, high)

The test program uses the unexported type alias `json` without qualifying it as `nlohmann::json`, causing a compilation error on the new version.

- Example program: `data/nlohmann-json/tests/6029/gen_21.cpp` (4 in cluster)
- Old version: compile error: ‘is_byte_char_type’ is not a member of ‘nlohmann::json_abi_v3_12_0::detail’
- New version: compile error: ‘json’ was not declared in this scope; did you mean ‘nlohmann::json_abi_v3_12_0::json’?

## PR #6049: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #6073: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 compile_diff [old] | 8 | intended (high) | The PR specifically aims to restore compilation of json::parse(container, function) when passing plain functions or function pointers as callbacks, which failed on develop due to iterator/sentinel overload selection. |

## PR #6075: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #6076: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 output_diff | 1 | intended (high) | Linked issue #6105 explicitly describes this bug in ordered_json where overlapping keys overwrite values instead of throwing type_error.313, and the PR diff adds the check to throw type_error.313 when non-null values conflict. |
| C2 output_diff | 1 | intended (high) | The PR diff explicitly states that if the conflicting later assignment is a null value, it leaves the existing structure as is (as when the shorter key comes first), which is demonstrated here. |
| C3 output_diff | 1 | intended (high) | This is another case of overlapping keys (root vs /x) in ordered_json addressed by linked issue #6105, now correctly throwing type_error.313 instead of silently overwriting. |
| C4 output_diff | 1 | intended (high) | This is an array-element overlapping key case covered by linked issue #6105, which now correctly rejects overlapping JSON pointers with type_error.313. |
| C5 output_diff | 1 | intended (high) | Subsequent null assignments to parent paths allow the existing nested structure to remain intact as per the new check logic added in the PR. |

## PR #6077: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #6078: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 output_diff | 1 | intended (high) | The PR explicitly states that a no-op array is empty and the reader now announces 0 elements for it instead of passing the declared count through to the SAX parser. |

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
| C1 compile_diff [both] | 3 | unintended (high) | The test uses invalid SFINAE probes (accessing `::head` rather than checking member existence via type traits properly) which fail to compile on the new version. |
| C2 output_diff | 1 | intended (high) | The PR explicitly truncates long tokens in error messages and inserts '...' when they exceed 8192 characters. |

### Finding: PR #6121 C1 (unintended, high)

The test uses invalid SFINAE probes (accessing `::head` rather than checking member existence via type traits properly) which fail to compile on the new version.

- Example program: `data/nlohmann-json/tests/6121/gen_29.cpp` (3 in cluster)
- Old version: compile error: ‘token_text_buffer’ in namespace ‘nlohmann::json_abi_v3_12_0::detail’ does not name a template type; did you mean ‘token_carry_buffer’?
- New version: compile error: ‘head’ in ‘class nlohmann::json_abi_v3_12_0::detail::token_text_buffer<wchar_t>’ does not name a type
