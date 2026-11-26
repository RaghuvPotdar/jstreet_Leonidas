---
description: Implement or review a Leonidas change using independent reviewers and cross-review.
disable-model-invocation: true
---
Coordinate this task in the main Claude Code session: $ARGUMENTS

1. Inspect repository instructions, working-tree status, relevant specs,
   and the existing simulation flow. Preserve user edits. For an
   implementation task, delegate edits to leonidas-implementer.
   For a review-only task, keep the working tree untouched.
2. Give leonidas-rtl-reviewer and leonidas-verification-reviewer the same
   candidate, scope, changed paths, relevant diff, and test evidence.
   Invoke them separately and collect both independent reviews before
   sharing either report. Keep the candidate fixed during review.
3. Give each reviewer the other's findings and request a cross-review.
   Have them confirm or dispute each relevant finding with evidence.
   Keep stable finding IDs across rounds. Resolve disagreements using
   the spec, a cycle trace, or a directed simulation.
4. Send confirmed defects and verification gaps to leonidas-implementer.
   Rerun applicable checks and both reviews after each revision.
   In review-only mode, report the findings and end the run.
5. Finish with PASS only when both reviewers pass the same final candidate,
   all confirmed findings are closed, and applicable simulations pass.
   If a necessary simulator, spec decision, or subagent is unavailable,
   report BLOCKED and identify the missing evidence. Default to four
   review rounds. If issues remain at the limit or a round makes no
   progress, report them as unresolved without claiming PASS.

Skill routing. Agents preload their everyday skills. This command
remains in charge of delegation, review rounds, and completion. Load
the occasional skills below with the Skill tool, then pass the
applicable instructions in the delegation prompt:
- A simulation or check fails: load superpowers:systematic-debugging and
  give its root-cause method to leonidas-implementer before any fix.
- Before reporting PASS: apply superpowers:verification-before-completion
  yourself. Rerun the final checks on the final candidate and quote the output.
- A design review touches area, Fmax, or SRAM sizing: load
  claude-for-hardware:rtl-area-timing for leonidas-architect.
- Pin lists or host-interface tables risk drifting from the RTL: load
  claude-for-hardware:soc-integration for leonidas-architect.
- Tapeout precheck or GDS submission: run /claude-for-hardware:tapeout-check
  only on user request. Do this outside the review loop.
"Claude for Hardware" is the claude-for-hardware plugin namespace. No
/claude-for-hardware skill or command exists. If a named skill cannot
be resolved or loaded, report it by name in the final report, and do
not claim its guidance was applied.

Report changed paths, exact test commands and outcomes, reviewer verdicts,
and remaining findings. Do not commit or push.

