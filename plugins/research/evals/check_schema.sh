#!/usr/bin/env bash
#
# Deterministic, offline guard for the research contract. Proves schema.py
# enforces the Iron Law and the mode-wall in code -- no MCP, no network, no
# model. Every case asserts an exact exit code; the script exits 0 only if all
# pass. CI-able, and the runnable half of the fabrication-trap eval.
#
# Usage:  bash evals/check_schema.sh
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
SCHEMA="$HERE/../skills/research-contract/schema.py"
WORK="$(mktemp -d /tmp/research-eval-XXXXXX)"
trap 'rm -rf "$WORK"' EXIT

pass=0
fail=0

# expect <want-exit> <kind> <json-file> <label>
expect() {
    local want="$1" kind="$2" file="$3" label="$4"
    python3 "$SCHEMA" "$kind" "$file" "$WORK/out.md" >/dev/null 2>&1
    local got=$?
    if [ "$got" -eq "$want" ]; then
        echo "PASS  ($kind exit $got) $label"
        pass=$((pass + 1))
    else
        echo "FAIL  (wanted exit $want, got $got) $label"
        fail=$((fail + 1))
    fi
}

# --- REJECT: citation with no quote (existence is not support) -------------
cat > "$WORK/no_quote.json" <<'JSON'
{"sub_question":"q","question":"q","date":"2026-06-19","summary":"s","claims":[
 {"statement":"X","tier":"EMERGING","grade":"LOW","sub_question":"q","support":"ENTAILED","confidence":80,
  "citations":[{"identifier":"PMID:1","url":"https://pubmed.ncbi.nlm.nih.gov/1/"}]}]}
JSON
expect 1 notes "$WORK/no_quote.json" "citation without a quote is rejected"

# --- REJECT: grounded claim with no citation (no source = no claim) ---------
cat > "$WORK/no_cite.json" <<'JSON'
{"sub_question":"q","question":"q","date":"2026-06-19","summary":"s","claims":[
 {"statement":"X","tier":"EMERGING","grade":"LOW","sub_question":"q","support":"ENTAILED","confidence":80,"citations":[]}]}
JSON
expect 1 notes "$WORK/no_cite.json" "claim without a citation is rejected"

# --- REJECT: malformed identifier (verifier could not resolve it) ----------
cat > "$WORK/bad_id.json" <<'JSON'
{"sub_question":"q","question":"q","date":"2026-06-19","summary":"s","claims":[
 {"statement":"X","tier":"EMERGING","grade":"LOW","sub_question":"q","support":"ENTAILED","confidence":80,
  "citations":[{"identifier":"http://example.com/paper","url":"http://example.com","quote":"x"}]}]}
JSON
expect 1 notes "$WORK/bad_id.json" "non-PMID/DOI/NCT identifier is rejected"

# --- REJECT: grounded mode carrying hypotheses (the wall) ------------------
cat > "$WORK/grounded_hyp.json" <<'JSON'
{"question":"q","date":"2026-06-19","author":"a","mode":"grounded","disclaimer":"d","executive_summary":"e","claims":[],
 "hypotheses":[{"statement":"h","chain":[{"from":"a","relation":"r","to":"b","citation":0}],
  "citations":[{"identifier":"PMID:1","url":"u","quote":"q"}],"tier":"SPECULATIVE","competing":["x"],
  "discriminating_test":"t","falsification":"f","confidence":10}]}
JSON
expect 1 report "$WORK/grounded_hyp.json" "grounded mode + hypotheses is rejected"

# --- REJECT: hypothesis whose tier is not SPECULATIVE ----------------------
cat > "$WORK/hyp_tier.json" <<'JSON'
{"question":"q","date":"2026-06-19","author":"a","mode":"hypothesis","disclaimer":"d","executive_summary":"e","claims":[],
 "hypotheses":[{"statement":"h","chain":[{"from":"a","relation":"r","to":"b","citation":0}],
  "citations":[{"identifier":"PMID:1","url":"u","quote":"q"}],"tier":"ESTABLISHED","competing":["x"],
  "discriminating_test":"t","falsification":"f","confidence":10}]}
JSON
expect 1 report "$WORK/hyp_tier.json" "non-SPECULATIVE hypothesis is rejected"

# --- REJECT: report with no disclaimer (safety rail in code) ---------------
cat > "$WORK/no_disclaimer.json" <<'JSON'
{"question":"q","date":"2026-06-19","author":"a","mode":"grounded","executive_summary":"e","claims":[],"hypotheses":[]}
JSON
expect 1 report "$WORK/no_disclaimer.json" "report without a disclaimer is rejected"

# --- ACCEPT: a well-formed retriever report --------------------------------
cat > "$WORK/good_notes.json" <<'JSON'
{"sub_question":"Is there direct evidence?","question":"q","date":"2026-06-19","summary":"One cohort.","claims":[
 {"statement":"X may result in Y.","tier":"SPECULATIVE","grade":"VERY_LOW","ocebm_level":"4","sub_question":"Is there direct evidence?",
  "support":"ENTAILED","confidence":62,
  "citations":[{"identifier":"PMID:1","url":"https://pubmed.ncbi.nlm.nih.gov/1/","quote":"X occurred in 38% of the cohort.","source_type":"case-series"}]}]}
JSON
expect 0 notes "$WORK/good_notes.json" "well-formed retriever report renders"

# --- ACCEPT: a well-formed final report ------------------------------------
cat > "$WORK/good_report.json" <<'JSON'
{"question":"q","date":"2026-06-19","author":"a","mode":"grounded",
 "disclaimer":"For research and education; not medical advice; not a substitute for a licensed clinician.",
 "executive_summary":"e","hypotheses":[],
 "claims":[{"statement":"X reduces Y.","tier":"ESTABLISHED","grade":"HIGH","ocebm_level":"1","sub_question":"sq",
  "support":"ENTAILED","confidence":92,
  "citations":[{"identifier":"DOI:10.1/x","url":"https://doi.org/10.1/x","quote":"X reduced Y in a meta-analysis.","source_type":"systematic-review"}]}],
 "safety_flags":[{"intervention":"GET","harm":"PEM","commercial":"n/a","note":"NICE NG206 (2021)"}],
 "open_questions":["q"],"audit":{"sub_questions":1,"searches":10,"claims_dropped":0}}
JSON
expect 0 report "$WORK/good_report.json" "well-formed final report renders"

echo "----"
echo "check_schema: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
