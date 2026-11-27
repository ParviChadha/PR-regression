# Report: nlohmann-json (baseline pipeline)

59 PR(s) checked, 1173 programs generated, 1173 in use (446 repaired by fix.py). Numbers come only from the files on disk; see the module docstring of pipeline/report.py for each definition.

## Summary

| Measure | Value |
|---|---|
| PRs checked | 59 |
| Compile success, as generated (new / both versions) | 69.0% / 65.4% |
| Compile success, after fix.py (new / both versions) | 80.0% / 76.4% |
| Deterministic on both versions | 893 of 896 compiled-on-both programs (99.7%) |
| PRs with at least one behavioral difference | 14 of 59 (23.7%) |
| Differences by verdict (clusters / programs) | intended 35 / 98, unintended 5 / 24, unclear 4 / 20 |
| Regression candidates | 2 of 59 classified: #4958, #6005 |
| Changed-line coverage measured | 59 of 59 PRs; at least 80% reached for 26 |
| Clean results that are INCONCLUSIVE (coverage missing or low) | 15: #5915, #5931, #5940, #5975, #5978, #5979, #5980, #5981, #5996, #5998, #5999, #6000, #6001, #6012, #6078 |
| Changed-line coverage before / after the loop (mean over 41 PRs) | 80.4% / 80.4% |
| C++ standard the programs were compiled with | c++17: 58 PR(s), c++20: 1 PR(s) |
| LLM calls (estimated) | 137 total, 2.3 per PR |
| Wall time of the run.py stage | 2240.3 s |

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
| #4958 | 20 (20) | 15/20 / 5/20 | compile_diff 14, invalid 1, output_diff 1, same 4 | 15 | REGRESSION CANDIDATE | n/a | 2 |
| #5459 | 20 (20) | 20/20 / 20/20 | output_diff 3, same 17 | 3 | no regression flagged | 100% of 20 lines | 2 |
| #5890 | 20 (20) | 0/20 / 0/20 | compile_diff 20 | 20 | no regression flagged (no measurable changed lines) | n/a | 2 |
| #5908 | 20 (20) | 15/20 / 15/20 | invalid 5, same 15 | 0 | no regression flagged (no measurable changed lines) | n/a | 3 |
| #5915 | 20 (20) | 2/20 / 2/20 | invalid 18, same 2 | 0 | no regression flagged, INCONCLUSIVE: only 20% of changed lines reached | 20% of 5 lines | 3 |
| #5920 | 20 (20) | 11/20 / 11/20 | invalid 9, same 11 | 0 | no regression flagged (no measurable changed lines) | n/a | 3 |
| #5921 | 20 (20) | 3/20 / 3/20 | invalid 17, same 3 | 0 | no regression flagged (no measurable changed lines) | n/a | 3 |
| #5926 | 20 (20) | 15/20 / 15/20 | invalid 5, same 15 | 0 | no regression flagged (no measurable changed lines) | n/a | 3 |
| #5931 | 20 (20) | 20/20 / 20/20 | same 20 | 0 | no regression flagged, INCONCLUSIVE: only 0% of changed lines reached | 0% of 15 lines | 2 |
| #5936 | 20 (20) | 20/20 / 20/20 | output_diff 3, same 17 | 3 | no regression flagged | 100% of 2 lines | 3 |
| #5940 | 20 (20) | 20/20 / 20/20 | invalid 1, same 19 | 0 | no regression flagged, INCONCLUSIVE: only 74% of changed lines reached | 74% of 153 lines | 2 |
| #5942 | 20 (20) | 0/20 / 0/20 | invalid 20 | 0 | no regression flagged (no measurable changed lines) | n/a | 3 |
| #5964 | 20 (20) | 20/20 / 20/20 | same 20 | 0 | no regression flagged | 100% of 15 lines | 2 |
| #5966 | 20 (20) | 1/20 / 0/20 | compile_diff 20 | 20 | no regression flagged (no measurable changed lines) | n/a | 4 |
| #5968 | 20 (20) | 19/20 / 19/20 | invalid 1, same 19 | 0 | no regression flagged | 91% of 22 lines | 3 |
| #5969 | 18 (18) | 0/18 / 0/18 | invalid 18 | 0 | no regression flagged (no measurable changed lines) | n/a | 3 |
| #5971 | 20 (20) | 20/20 / 20/20 | same 20 | 0 | no regression flagged | 100% of 13 lines | 1 |
| #5975 | 19 (19) | 19/19 / 19/19 | same 19 | 0 | no regression flagged, INCONCLUSIVE: only 76% of changed lines reached | 76% of 97 lines | 1 |
| #5976 | 20 (20) | 20/20 / 20/20 | same 20 | 0 | no regression flagged | 100% of 17 lines | 1 |
| #5978 | 20 (20) | 20/20 / 20/20 | same 20 | 0 | no regression flagged, INCONCLUSIVE: only 44% of changed lines reached | 44% of 48 lines | 2 |
| #5979 | 20 (20) | 20/20 / 20/20 | invalid 1, same 19 | 0 | no regression flagged, INCONCLUSIVE: only 76% of changed lines reached | 76% of 103 lines | 1 |
| #5980 | 20 (20) | 20/20 / 20/20 | same 20 | 0 | no regression flagged, INCONCLUSIVE: only 74% of changed lines reached | 74% of 83 lines | 1 |
| #5981 | 20 (20) | 20/20 / 20/20 | same 20 | 0 | no regression flagged, INCONCLUSIVE: only 66% of changed lines reached | 66% of 58 lines | 1 |
| #5984 | 20 (20) | 20/20 / 20/20 | same 20 | 0 | no regression flagged | 92% of 12 lines | 3 |
| #5990 | 20 (20) | 20/20 / 20/20 | output_diff 8, same 12 | 8 | no regression flagged | 100% of 6 lines | 4 |
| #5991 | 20 (20) | 19/20 / 19/20 | invalid 1, same 19 | 0 | no regression flagged | 100% of 6 lines | 3 |
| #5992 | 20 (20) | 20/20 / 20/20 | output_diff 6, same 14 | 6 | no regression flagged | 100% of 3 lines | 3 |
| #5996 | 20 (20) | 20/20 / 20/20 | same 20 | 0 | no regression flagged, INCONCLUSIVE: only 70% of changed lines reached | 70% of 10 lines | 1 |
| #5998 | 16 (16) | 16/16 / 16/16 | same 16 | 0 | no regression flagged, INCONCLUSIVE: only 27% of changed lines reached | 27% of 11 lines | 2 |
| #5999 | 20 (20) | 20/20 / 20/20 | same 20 | 0 | no regression flagged, INCONCLUSIVE: only 20% of changed lines reached | 20% of 5 lines | 2 |
| #6000 | 20 (20) | 20/20 / 20/20 | same 20 | 0 | no regression flagged, INCONCLUSIVE: only 57% of changed lines reached | 57% of 49 lines | 2 |
| #6001 | 20 (20) | 20/20 / 20/20 | same 20 | 0 | no regression flagged, INCONCLUSIVE: only 50% of changed lines reached | 50% of 10 lines | 2 |
| #6002 | 20 (20) | 20/20 / 20/20 | output_diff 3, same 17 | 3 | no regression flagged | 87% of 15 lines | 2 |
| #6003 | 20 (20) | 20/20 / 20/20 | flaky 1, same 19 | 0 | no regression flagged (no measurable changed lines) | n/a | 2 |
| #6005 | 20 (20) | 0/20 / 0/20 | compile_diff 20 | 20 | REGRESSION CANDIDATE | n/a | 2 |
| #6008 | 20 (20) | 20/20 / 20/20 | same 20 | 0 | no regression flagged | 100% of 2 lines | 1 |
| #6009 | 20 (20) | 19/20 / 19/20 | invalid 1, same 19 | 0 | no regression flagged (no measurable changed lines) | n/a | 3 |
| #6012 | 20 (20) | 20/20 / 0/20 | compile_diff 20 | 20 | no regression flagged, INCONCLUSIVE: only 50% of changed lines reached | 50% of 2 lines | 4 |
| #6013 | 20 (20) | 20/20 / 20/20 | same 20 | 0 | no regression flagged (no measurable changed lines) | n/a | 3 |
| #6015 | 20 (20) | 20/20 / 20/20 | same 20 | 0 | no regression flagged (no measurable changed lines) | n/a | 3 |
| #6016 | 20 (20) | 8/20 / 8/20 | invalid 12, same 8 | 0 | no regression flagged | 100% of 3 lines | 3 |
| #6020 | 20 (20) | 20/20 / 20/20 | same 20 | 0 | no regression flagged | 100% of 4 lines | 1 |
| #6023 | 20 (20) | 18/20 / 18/20 | invalid 2, same 18 | 0 | no regression flagged | 100% of 2 lines | 3 |
| #6028 | 20 (20) | 20/20 / 20/20 | same 20 | 0 | no regression flagged | 100% of 17 lines | 1 |
| #6029 | 20 (20) | 20/20 / 20/20 | same 20 | 0 | no regression flagged | 100% of 5 lines | 3 |
| #6030 | 20 (20) | 20/20 / 20/20 | same 20 | 0 | no regression flagged | 93% of 60 lines | 2 |
| #6039 | 20 (20) | 20/20 / 20/20 | same 20 | 0 | no regression flagged | 100% of 15 lines | 1 |
| #6049 | 20 (20) | 0/20 / 0/20 | invalid 20 | 0 | no regression flagged (no measurable changed lines) | n/a | 3 |
| #6073 | 20 (20) | 19/20 / 8/20 | compile_diff 12, same 8 | 12 | no regression flagged (no measurable changed lines) | n/a | 4 |
| #6075 (c++20) | 20 (20) | 20/20 / 20/20 | output_diff 5, same 15 | 5 | no regression flagged | 100% of 16 lines | 3 |
| #6076 | 20 (20) | 20/20 / 20/20 | output_diff 2, same 18 | 2 | no regression flagged | 98% of 119 lines | 3 |
| #6077 | 20 (20) | 20/20 / 20/20 | same 20 | 0 | no regression flagged | 100% of 10 lines | 1 |
| #6078 | 20 (20) | 20/20 / 20/20 | same 20 | 0 | no regression flagged, INCONCLUSIVE: only 55% of changed lines reached | 55% of 22 lines | 1 |
| #6081 | 20 (20) | 19/20 / 19/20 | invalid 1, same 19 | 0 | no regression flagged | 100% of 4 lines | 3 |
| #6084 | 20 (20) | 0/20 / 0/20 | invalid 20 | 0 | no regression flagged (no measurable changed lines) | n/a | 3 |
| #6085 | 20 (20) | 0/20 / 0/20 | invalid 20 | 0 | no regression flagged (no measurable changed lines) | n/a | 3 |
| #6117 | 20 (20) | 20/20 / 20/20 | same 20 | 0 | no regression flagged | 86% of 7 lines | 2 |
| #6119 | 20 (20) | 20/20 / 20/20 | output_diff 5, same 15 | 5 | no regression flagged | 100% of 3 lines | 3 |
| #6121 | 20 (20) | 20/20 / 20/20 | same 20 | 0 | no regression flagged | 94% of 64 lines | 1 |

## PR #4958: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 compile_diff [old] | 10 | intended (high) | The PR enables types convertible to std::string_view to be used as keys in operator[] and other functions by updating is_usable_as_basic_json_key_type. |
| C2 compile_diff [both] | 3 | unintended (medium) | While the PR allows types convertible to string_view to pass type trait checks, passing them directly to container operations like contains or erase still fails because the underlying std::map lookup expects types comparable via operator<. |
| C3 compile_diff [both] | 1 | unintended (medium) | Passing a custom type convertible to string_view to const operator[] passes the key trait check but fails during map lookup because the underlying container comparator cannot compare the custom type directly with std::string. |
| C4 output_diff | 1 | intended (high) | The PR explicitly updates is_usable_as_basic_json_key_type to return true for types convertible to std::string_view, matching this output change. |

### Finding: PR #4958 C2 (unintended, medium)

While the PR allows types convertible to string_view to pass type trait checks, passing them directly to container operations like contains or erase still fails because the underlying std::map lookup expects types comparable via operator<.

- Example program: `data/nlohmann-json/baseline/4958/gen_06.cpp` (3 in cluster)
- Old version: compile error: no matching function for call to ‘nlohmann::json_abi_v3_12_0::basic_json<>::contains(SearchKey&)’
- New version: compile error: no match for call to ‘(const std::less<void>) (const SearchKey&, const std::__cxx11::basic_string<char>&)’

### Finding: PR #4958 C3 (unintended, medium)

Passing a custom type convertible to string_view to const operator[] passes the key trait check but fails during map lookup because the underlying container comparator cannot compare the custom type directly with std::string.

- Example program: `data/nlohmann-json/baseline/4958/gen_03.cpp` (1 in cluster)
- Old version: compile error: no match for ‘operator[]’ (operand types are ‘const nlohmann::json_abi_v3_12_0::json’ {aka ‘const nlohmann::json_abi_v3_12_0::basic_json<>’}
- New version: compile error: no match for call to ‘(const std::less<void>) (const KeyWrapper&, const std::__cxx11::basic_string<char>&)’

## PR #5459: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 output_diff | 1 | intended (high) | The PR explicitly fixes the issue where 2^63-2 and 2^63-1 incorrectly compare equal to 2^63 due to floating point precision loss during widening, making x==y false instead of true as described in the PR description and issue #5401. |
| C2 output_diff | 1 | intended (high) | The PR changes mixed number comparisons to be exact instead of widening to float, ensuring that 2^63-1 (represented as uint64_t) is correctly evaluated as less than 2^63.0 rather than rounding up and comparing equal. |
| C3 output_diff | 1 | intended (high) | The PR replaces lossy float widening with exact comparisons for large unsigned integers near 2^64, correcting the previous behavior where max_uint erroneously compared equal to 2^64.0. |

## PR #5890: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 compile_diff [both] | 16 | unclear (high) | The test programs fail to compile on both versions due to invalid usage or missing headers/types not present in the public API. |
| C2 compile_diff [both] | 2 | unclear (high) | The test programs fail to compile on both versions because they use names and types that are not part of the public API. |
| C3 compile_diff [both] | 1 | unclear (high) | The test programs fail to compile on both versions due to trying to access private members or non-existent types. |
| C4 compile_diff [both] | 1 | unclear (high) | The test programs fail to compile on both versions because they reference types not defined in the public API. |

## PR #5908: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5915: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5920: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5921: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5926: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5931: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5936: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 output_diff | 1 | intended (high) | The PR description and commit message explicitly fix self-aliasing in json_pointer::operator/= by appending a copy, changing p /= p from producing duplicate empty segments (/a/b//) to successfully appending the pointer (/a/b/a/b). |
| C2 output_diff | 1 | intended (high) | Chained self-appends (ptr /= ptr applied twice) correctly benefit from the same fix for self-aliasing in json_pointer::operator/=, producing repeated valid segments rather than empty segments. |
| C3 output_diff | 1 | intended (high) | Appends where a json_pointer is assigned from another and then self-aliased (ptr2 /= ptr2 where ptr2(ptr1)) are covered by the same self-aliasing check (&ptr == this) in operator/=. |

## PR #5940: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5942: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5964: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5966: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 compile_diff [both] | 19 | intended (high) | The PR removes the duplicate is_editable member that failed to compile on the old version, allowing basic_json_view tests and valid programs to compile successfully. |
| C2 compile_diff [old] | 1 | intended (high) | Removing the duplicate member fixes the compilation error in json_view.hpp, allowing test programs that use json_document::parse to compile and run on the new version. |

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
| C1 output_diff | 1 | intended (high) | The PR explicitly states that exceptions about the root value should now include the byte range when both JSON_DIAGNOSTICS and JSON_DIAGNOSTIC_POSITIONS are set. |
| C2 output_diff | 1 | intended (high) | The PR explicitly states that exceptions about the root value should now include the byte range when both JSON_DIAGNOSTICS and JSON_DIAGNOSTIC_POSITIONS are set. |
| C3 output_diff | 1 | intended (high) | The PR explicitly states that exceptions about the root value should now include the byte range when both JSON_DIAGNOSTICS and JSON_DIAGNOSTIC_POSITIONS are set. |
| C4 output_diff | 1 | intended (high) | The PR explicitly states that exceptions about the root value should now include the byte range when both JSON_DIAGNOSTICS and JSON_DIAGNOSTIC_POSITIONS are set. |
| C5 output_diff | 1 | intended (high) | The PR explicitly states that exceptions about the root value should now include the byte range when both JSON_DIAGNOSTICS and JSON_DIAGNOSTIC_POSITIONS are set. |
| C6 output_diff | 1 | intended (high) | The PR explicitly states that exceptions about the root value should now include the byte range when both JSON_DIAGNOSTICS and JSON_DIAGNOSTIC_POSITIONS are set. |
| C7 output_diff | 1 | intended (high) | The PR updates json_view diagnostics similarly to basic_json diagnostics so root value exceptions include the byte range under both macros. |
| C8 output_diff | 1 | intended (high) | The PR updates json_view diagnostics similarly to basic_json diagnostics so root value exceptions include the byte range under both macros. |

## PR #5991: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5992: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 output_diff | 3 | intended (high) | The PR description and diff explicitly state that json_view::get<T>() now throws type_error.302 for number_integer_t (std::int64_t) when reading a boolean, matching basic_json behavior. |
| C2 output_diff | 1 | intended (high) | The PR description and diff state that json_view::get<T>() now throws type_error.302 for number_float_t (double) when reading a boolean, matching basic_json behavior. |
| C3 output_diff | 1 | intended (high) | The PR updates json_view::get<T>() to throw type_error.302 for number_integer_t regardless of whether the boolean value is true or false, matching basic_json behavior. |
| C4 output_diff | 1 | intended (high) | The PR's goal is to achieve parity with basic_json where ordinary arithmetic types like int still return 0/1 for booleans while number_integer_t throws type_error.302. |

## PR #5996: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5998: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #5999: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #6000: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #6001: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #6002: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 output_diff | 1 | intended (high) | The PR explicitly states that a BJData container count equal to SIZE_MAX now throws out_of_range.408 ('integer value overflow') instead of being parsed as 'no count'. |
| C2 output_diff | 1 | intended (high) | This BJData input uses SIZE_MAX as a container count for an optimized container, which the PR's store_ubjson_count() change correctly rejects with an out_of_range error. |
| C3 output_diff | 1 | intended (high) | The PR intends to reject container counts equal to SIZE_MAX for BJData objects/maps as well as arrays, raising an out_of_range.408 exception instead of failing later during number parsing. |

## PR #6003: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #6005: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 compile_diff [new] | 15 | unintended (high) | The PR removed the `null_result` parameter from `JSON_IMPLEMENT_OPERATOR`, but the macro body still references it at line 5441 for same-type scalar comparisons, breaking ordinary comparisons like `a == b`. |
| C2 compile_diff [both] | 4 | unintended (high) | Same-type scalar comparisons fail to compile due to the missing `null_result` macro parameter referenced in the library headers. |
| C3 compile_diff [both] | 1 | unintended (high) | Compilation fails inside the library headers due to the missing `null_result` macro parameter when compiling basic json operations. |

### Finding: PR #6005 C1 (unintended, high)

The PR removed the `null_result` parameter from `JSON_IMPLEMENT_OPERATOR`, but the macro body still references it at line 5441 for same-type scalar comparisons, breaking ordinary comparisons like `a == b`.

- Example program: `data/nlohmann-json/baseline/6005/gen_01.cpp` (15 in cluster)
- Old version: output: true
- New version: compile error: ‘null_result’ was not declared in this scope

### Finding: PR #6005 C2 (unintended, high)

Same-type scalar comparisons fail to compile due to the missing `null_result` macro parameter referenced in the library headers.

- Example program: `data/nlohmann-json/baseline/6005/gen_06.cpp` (4 in cluster)
- Old version: compile error: expected primary-expression before ‘>’ token
- New version: compile error: ‘null_result’ was not declared in this scope

### Finding: PR #6005 C3 (unintended, high)

Compilation fails inside the library headers due to the missing `null_result` macro parameter when compiling basic json operations.

- Example program: `data/nlohmann-json/baseline/6005/gen_16.cpp` (1 in cluster)
- Old version: compile error: expected ‘}’ before ‘;’ token
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
| C1 compile_diff [old] | 20 | intended (high) | The PR restores the two missing commits from #6005 to fix the compilation error caused by undeclared 'null_result' in the develop branch. |

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

## PR #6030: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #6039: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #6049: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #6073: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 compile_diff [old] | 11 | intended (high) | The PR explicitly fixes `json::parse` and `accept` with a plain function or function pointer as callback for containers, which failed to compile previously as shown in `can_compare_ne`. |
| C2 compile_diff [both] | 1 | intended (high) | The program passes a function (not a function pointer) `my_cb` directly as a callback to `ordered_json::parse`, but the library's `parse` overload expects a callback type like `parser_callback_t`, making this a type mismatch in the user code rather than a library error. |

## PR #6075: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 output_diff | 4 | intended (high) | The PR intends to store std::u8string as a JSON string in all configurations and allow round-tripping via get<std::u8string>() as documented in the description. |
| C2 output_diff | 1 | intended (high) | The PR adds a from_json overload for std::basic_string<char8_t> to read a JSON string, which previously threw type_error.302 because it only accepted arrays. |

## PR #6076: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
| C1 output_diff | 1 | intended (high) | The linked issue #6105 explicitly states that overlapping keys in ordered_json::unflatten() must throw type_error.313 instead of silently overwriting earlier values. |
| C2 output_diff | 1 | intended (high) | Linked issue #6105 and the PR diff show that a null value for a prefix key leaves the existing nested structure intact rather than overwriting it, as handled by `if (element.second.is_null()) { continue; }`. |

## PR #6077: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

## PR #6078: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|

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
| C1 output_diff | 3 | intended (high) | The PR specifically changes non-strict BON8 parsing to report a parse_error when an unterminated final string has a non-empty push-back buffer instead of silently dropping the trailing bytes. |
| C2 output_diff | 1 | intended (high) | SAX parsing with `strict = false` now correctly triggers the parse error handler and returns false for unterminated BON8 final strings, matching the PR goal. |
| C3 output_diff | 1 | intended (high) | With allow_exceptions set to false, an unterminated BON8 string now correctly results in a discarded value (`is_discarded() == true`) instead of returning a partial result. |

## PR #6121: clusters

| Cluster | Programs | Verdict | Reason |
|---|---|---|---|
