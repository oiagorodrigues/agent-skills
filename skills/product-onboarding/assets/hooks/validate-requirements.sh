#!/usr/bin/env bash
# PostToolUse: Edit|Write|MultiEdit — validates docs/onboarding/REQUIREMENTS.md.
# Rejects untestable FRs and unmeasurable NFRs mechanically, so the rule is not a
# matter of the model's mood.
set -uo pipefail

target="$(cat | jq -r '.tool_input.file_path // empty' 2>/dev/null)"
case "$target" in */docs/onboarding/REQUIREMENTS.md) ;; *) exit 0 ;; esac
[ -f "$target" ] || exit 0

errs="$(awk -F'|' '
function t(s){ gsub(/^[ \t]+|[ \t]+$/,"",s); return s }
function bad(id,msg){ printf "  %s: %s\n", id, msg; n++ }
function ok_status(s){ return s=="implemented"||s=="partial"||s=="drifted"||s=="missing"||s=="undocumented"||s=="UNVERIFIED" }
function ok_moscow(s){ return s=="M"||s=="S"||s=="C"||s=="W" }

/^##/ { drift = ($0 ~ /[Dd]rift/) ? 1 : 0 }
drift { next }                       # the drift table cites IDs, it is not the FR table

/^[ \t]*\|[ \t]*FR-[0-9]+/ {
  id=t($2); seen_fr++
  if (NF < 10) { bad(id,"needs 8 columns: ID|Requirement|Actor|Source|Code evidence|Test|Status|MoSCoW"); next }
  for (i=3;i<=9;i++) if (t($i)=="") bad(id,"empty column " i)
  for (i=3;i<=9;i++) if (t($i) ~ /[<>]/) bad(id,"unfilled placeholder in column " i)
  if (!ok_status(t($8))) bad(id,"status \"" t($8) "\" not in implemented|partial|drifted|missing|undocumented|UNVERIFIED")
  if (!ok_moscow(t($9))) bad(id,"MoSCoW \"" t($9) "\" not in M|S|C|W")
  if (toupper(t($6))=="NONE" && t($8)!="missing" && t($8)!="UNVERIFIED")
    bad(id,"no code evidence, so status must be missing or UNVERIFIED")
  next
}
/^[ \t]*\|[ \t]*NFR-[0-9]+/ {
  id=t($2); seen_nfr++
  if (NF < 10) { bad(id,"needs 8 columns: ID|Attribute|Target|Measured|Source|Enforced at|Status|MoSCoW"); next }
  for (i=3;i<=9;i++) if (t($i)=="") bad(id,"empty column " i)
  for (i=3;i<=9;i++) if (t($i) ~ /[<>]/ && i!=4) bad(id,"unfilled placeholder in column " i)
  if (t($4) !~ /[0-9]/ && t($4)!="UNVERIFIED") bad(id,"target \"" t($4) "\" has no number — make it measurable (value, unit, window)")
  if (!ok_status(t($8))) bad(id,"status \"" t($8) "\" not in implemented|partial|drifted|missing|undocumented|UNVERIFIED")
  if (!ok_moscow(t($9))) bad(id,"MoSCoW \"" t($9) "\" not in M|S|C|W")
  next
}
/^##[ \t]*Open questions/ { q=1 }
/^[ \t]*`?Q[0-9]+/ { if (q) qn++ }
/^##[ \t]*Assumptions/ { a=1 }
END {
  if (!seen_fr) bad("doc","no FR rows")
  if (!seen_nfr) bad("doc","no NFR rows — NFRs drive the architecture, do not skip them")
  if (!a) bad("doc","missing \"## Assumptions\" section")
  if (!q) bad("doc","missing \"## Open questions\" section")
  else if (!qn) bad("doc","Open questions section has no Q1..Qn lines — always end with stakeholder questions")
}' "$target")"

[ -z "$errs" ] && exit 0
{
  echo "REQUIREMENTS.md failed validation:"
  printf '%s\n' "$errs"
  echo "Fix these rows before reporting done. An FR with no evidence and an NFR with no"
  echo "number are the two failure modes this skill exists to prevent."
} >&2
exit 2
