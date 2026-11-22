# Report: nlohmann-json

5 PR(s) checked, 115 programs generated, 115 in use (17 repaired by fix.py). Numbers come only from the files on disk; see the module docstring of pipeline/report.py for each definition.

## Summary

| Measure | Value |
|---|---|
| PRs checked | 5 |
| Compile success, as generated (new / both versions) | 95.7% / 80.9% |
| Compile success, after fix.py (new / both versions) | 95.7% / 90.4% |
| Deterministic on both versions | 104 of 104 compiled-on-both programs (100.0%) |
| PRs with at least one behavioral difference | 4 of 5 (80.0%) |
| Differences by verdict (clusters / programs) | intended 13 / 24, unintended 3 / 5, unclear 0 / 0 |
| Regression candidates | 2 of 5 classified: #4958, #6121 |
| Changed-line coverage measured | 5 of 5 PRs; at least 80% reached for 3 |
| Clean results that are INCONCLUSIVE (coverage missing or low) | 1: #6078 |
| Changed-line coverage before / after the loop (mean over 4 PRs) | 86.0% / 88.1% |
| LLM calls (estimated) | 18 total, 3.6 per PR |
| Wall time of the run.py stage | 98.1 s |

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
| #4958 | 20 (20) | 18/20 / 12/20 | compile_diff 8, output_diff 10, same 2 | 18 | REGRESSION CANDIDATE | n/a | 4 |
| #5459 | 20 (20) | 20/20 / 20/20 | output_diff 2, same 18 | 2 | no regression flagged | 100% of 20 lines | 2 |
| #6076 | 25 (25) | 25/25 / 25/25 | output_diff 5, same 20 | 5 | no regression flagged | 99% of 119 lines | 3 |
| #6078 | 25 (25) | 25/25 / 25/25 | same 25 | 0 | no regression flagged, INCONCLUSIVE: only 55% of changed lines reached | 55% of 22 lines | 3 |
| #6121 | 25 (25) | 22/25 / 22/25 | compile_diff 3, output_diff 1, same 21 | 4 | REGRESSION CANDIDATE | 99% of 70 lines | 6 |

## PR #4958: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 output_diff | 7 | intended (high) | The PR updates is_usable_as_basic_json_key_type to allow types convertible to std::string_view as keys, enabling custom string-viewable types to be used in operator[]. |
| C2 compile_diff [old] | 6 | intended (high) | Fixes compilation failures when passing classes with conversion to std::string_view into operator[], which is the main goal of issue #3912 and this PR. |
| C3 compile_diff [both] | 1 | unintended (medium) | The test fails to compile on the new version due to an internal comparator type mismatch error when using a const json object with a custom string_view key. |
| C4 output_diff | 1 | intended (high) | Directly tests the new type trait check std::is_convertible<KeyType, std::string_view>::value added in the PR, which evaluates to true for convertible types. |
| C5 output_diff | 1 | intended (high) | Enables successful map lookups using keys that convert to std::string_view instead of failing or picking an unintended conversion. |
| C6 compile_diff [new] | 1 | unintended (high) | Breaks usage of ordered_json with transparent comparators when using keys that convert to std::string_view, leading to a substitution failure inside ordered_map. |
| C7 output_diff | 1 | intended (high) | Validates that multiple distinct custom keys supporting std::string_view conversion are now correctly recognized and usable in operator[]. |

### Finding: PR #4958 C3 (unintended, medium)

The test fails to compile on the new version due to an internal comparator type mismatch error when using a const json object with a custom string_view key.

- Example program: `data/nlohmann-json/tests/4958/gen_03.cpp` (1 in cluster)
- Old version: compile error: no match for ‘operator[]’ (operand types are ‘const nlohmann::json_abi_v3_12_0::json’ {aka ‘const nlohmann::json_abi_v3_12_0::basic_json<>’}
- New version: compile error: no match for call to ‘(const std::less<void>) (const ViewHolder&, const std::__cxx11::basic_string<char>&)’

### Finding: PR #4958 C6 (unintended, high)

Breaks usage of ordered_json with transparent comparators when using keys that convert to std::string_view, leading to a substitution failure inside ordered_map.

- Example program: `data/nlohmann-json/tests/4958/gen_25.cpp` (1 in cluster)
- Old version: output: supported: 0
- New version: compile error: no matching function for call to ‘nlohmann::json_abi_v3_12_0::ordered_map<std::__cxx11::basic_string<char>, nlohmann::json_abi_v3_12_0::basi

## PR #5459: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 output_diff | 1 | intended (high) | The PR fixes intransitive mixed integer/float comparisons near 2^63 where values like 2^63-2 and 2^63-1 previously incorrectly compared equal to 2^63. |
| C2 output_diff | 1 | intended (high) | The PR ensures exact comparison between large integers and floats instead of lossy widening, so 2^63-1 correctly compares less than 2^63 instead of being rounded up and treated as equal. |

## PR #6076: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 output_diff | 1 | intended (high) | Linked issue #6105 explicitly describes this bug in ordered_json where overlapping keys overwrite values instead of throwing type_error.313, and the PR diff adds the check to throw type_error.313 when non-null values conflict. |
| C2 output_diff | 1 | intended (high) | The PR diff explicitly states that if the conflicting later assignment is a null value, it leaves the existing structure as is (as when the shorter key comes first), which is demonstrated here. |
| C3 output_diff | 1 | intended (high) | This is another case of overlapping keys (root vs /x) in ordered_json addressed by linked issue #6105, now correctly throwing type_error.313 instead of silently overwriting. |
| C4 output_diff | 1 | intended (high) | This is an array-element overlapping key case covered by linked issue #6105, which now correctly rejects overlapping JSON pointers with type_error.313. |
| C5 output_diff | 1 | intended (high) | Subsequent null assignments to parent paths allow the existing nested structure to remain intact as per the new check logic added in the PR. |

## PR #6078: clusters

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
