<!-- Titles follow CONTRIBUTING.md#title-convention. Apply exactly one priority:* label.
     Keep issue/PR numbers out of the title and link same-repository issues below. -->

## Summary

<!-- Explain what changed and why in plain English. Avoid agent transcripts. -->

## Changes

<!-- Focus on meaningful implementation, compatibility, and remaining work. -->

## Type of Change

<!-- Bug fix / feature / documentation / refactoring / CI or maintenance. -->

## Validation

<!-- Commands and actual results. Azure results require run ID, source commit,
     environment, capture date, evidence, recovery and cleanup. Otherwise NOT_RUN.
     Review procedure: DOCUMENTATION_CONTRACT.md#current-head-github-review-loop.
     REQUESTED, COMPLETE, FINDINGS_OPEN and BLOCKED are review states, not CI results.
     COMPLETE is not merge approval. Never invent a review URL or approval. -->

### GitHub review evidence

- Current head SHA:
- Reviewer identity and review URL/ID:
- Reviewed head SHA:
- Review outcome:
- Findings and thread dispositions:
- Required CI results for this head:
- Oracle and applicable image-review evidence:
- Remaining merge blockers:

## Checklist

- [ ] Relevant checks were run and their results recorded.
- [ ] Verification dates and claims reflect work actually performed.
- [ ] Scope and mandatory review gates were checked; no failing gate was bypassed.
- [ ] The change is the smallest that satisfies the issue; unrelated work is split out.
- [ ] Any GitHub review of the current head SHA is recorded above with its state; a request or an acknowledgement is not reported as a review result.
- [ ] Every finding of a recorded review has a disposition: fixed with evidence, not applicable with a reason, or deferred with a linked issue.
- [ ] No review result of an earlier head is reused as coverage of a later head.
- [ ] PR is non-draft and all mandatory gates pass before an expected-head-guarded squash merge.

## Related Issues

<!-- Closes #N for completed scope, or Refs #N with remaining work for partial scope. -->
