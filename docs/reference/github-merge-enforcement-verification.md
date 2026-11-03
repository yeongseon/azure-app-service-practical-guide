---
title: GitHub Merge Enforcement Verification (#396)
slug: github-merge-enforcement-verification
doc_type: reference
section: reference
summary: Dated record of what GitHub itself enforces on the default branch of this repository and how its review integrations behaved on real pull requests, including a review test on the pull request that adds this page, separating settings that were read from policy text and from behavior that was not tested.
topics: [quality-gates, ci]
products: [azure-app-service]
content_sources:
  references:
    - type: self-generated
      justification: Observations of the GitHub REST API for this repository on 2026-11-03, made with the owner account, of the review timelines of eight pull requests, and of the review requests made on the pull request that adds this page. The page makes no Azure-behavior claim, and the settings it reports can change after the date.
---

# GitHub Merge Enforcement Verification (#396)

This page records what GitHub enforces on the default branch of this repository, and how the review integrations behaved on real pull requests, as issue [#396](https://github.com/yeongseon/azure-app-service-practical-guide/issues/396) asks. It is the remote-enforcement slice of [#247](https://github.com/yeongseon/azure-app-service-practical-guide/issues/247). It sets no policy: the review and merge rules are written in the repository's authoring contract, and the open draft pull requests [#239](https://github.com/yeongseon/azure-app-service-practical-guide/pull/239) and [#258](https://github.com/yeongseon/azure-app-service-practical-guide/pull/258) propose changes to them. Text that describes a rule is not a setting that enforces it, so the sections below keep what was read, what was observed and what was not tested apart.

## 1. Basis

| Item | Value |
|---|---|
| Repository | `yeongseon/azure-app-service-practical-guide`, default branch `main`, head `8cda749f0fd258b207c06d5bf35e89875d21c78e` when the settings were read. |
| Read at | 2026-11-03T22:47:28Z, which is 07:47 on 2026-11-04 in Asia/Seoul. |
| Account and permission | The repository owner's account, whose permission on the repository is `admin`. Issue #247 recorded an HTTP 403 for a different credential, and a 403 does not show that protection is absent. With the `admin` permission the same read is answered with `404 Branch not protected`, which is an answer about the branch, and the `protected` flag of the branch summary agrees with it. |
| Method | Read-only `GET` requests to the GitHub REST API, listed in section 2, and the review timelines of eight pull requests. Then a review test on the pull request that adds this page (section 3), for which review requests were made with the owner's account. No setting was changed, no auto-merge was enabled, no review was bypassed, and no merge was attempted to test a block. |
| What the date means | The date is when the settings were read. It is not a test date of any workflow, and the settings can change at any time. |

## 2. Provider settings that were read

| Setting | Observed | Request |
|---|---|---|
| Branch protection of `main` | None. The protection endpoint answers `404 Branch not protected`, and the branch summary reports `protected: false` with no required status checks (`contexts: []`, enforcement `off`). | `GET /repos/{repo}/branches/main/protection` and `GET /repos/{repo}/branches/main` |
| Rulesets | None. The repository has no ruleset, and none applies to `main`. | `GET /repos/{repo}/rulesets` and `GET /repos/{repo}/rules/branches/main`, both `[]` |
| Required status checks, required reviews, dismissal of stale reviews, approval of the last push, resolution of conversations | Not configured, because neither mechanism above exists. | A consequence of the two rows above |
| Merge methods | Squash only: `allow_squash_merge` is true, and `allow_merge_commit` and `allow_rebase_merge` are false. | `GET /repos/{repo}` |
| Auto-merge | Disabled: `allow_auto_merge` is false. | `GET /repos/{repo}` |
| Deletion of the branch after a merge | Not automatic: `delete_branch_on_merge` is false. | `GET /repos/{repo}` |
| GitHub Actions | Enabled with all actions allowed. The default workflow token is `read`. The setting that lets workflows approve pull requests through the default `GITHUB_TOKEN` is off (`can_approve_pull_request_reviews` is false), which says nothing about approval with another credential. Pinning actions to a commit SHA is not required (`sha_pinning_required` is false). | `GET /repos/{repo}/actions/permissions` and `GET /repos/{repo}/actions/permissions/workflow` |
| Code owners | No `CODEOWNERS` file is tracked in the repository. | A listing of the tracked files |

Among the merge requirements examined here, only the merge method is configured remotely. No branch protection or ruleset requirement is configured for the other gates of the contract's merge policy, the Oracle review, CI on the exact head and the image checks, so those gates are procedural. The contributing guide asks for external actions pinned to a verified commit SHA, and the setting that would require it is off.

## 3. Review integrations on real pull requests

| Pull request | Review request | Reviewer response |
|---|---|---|
| [#239](https://github.com/yeongseon/azure-app-service-practical-guide/pull/239), draft | A comment by the maintainer, `@codex review`, naming head `278598d`, at 2026-10-16T12:55:19Z. A request for a Copilot review by the maintainer at 2026-10-24T12:00:41Z. | Codex: a state comment after 22 seconds and a review receipt after 3 minutes 7 seconds, which names the reviewed commit `278598db47`. Copilot: one review in the state `COMMENTED`, bound to `278598db47`, after 5 minutes 29 seconds. |
| [#258](https://github.com/yeongseon/azure-app-service-practical-guide/pull/258), draft | Two requests for a Copilot review by the maintainer, at 2026-10-24T07:05:03Z and 07:08:12Z. | Copilot: two reviews in the state `COMMENTED`, bound to `29cb9717c6`, after 2 minutes 27 seconds and 3 minutes 15 seconds. |
| [#403](https://github.com/yeongseon/azure-app-service-practical-guide/pull/403), opened at 2026-11-03T22:58:20Z with head `3bbce81` | Codex: no request by a person before the first response. A comment `@codex review` naming `3bbce81` at 23:02:59Z, made with the owner's account. Copilot: a request at 23:02:58Z, and a second one at 23:18:52Z for the head `a22bf38` that a later commit produced, both made with the owner's account. | Codex: at 22:58:28Z, 8 seconds after the pull request was opened, a message that the Codex usage limits had been reached. At 23:03:11Z, 12 seconds after the request, a state comment that the code review of `3bbce81` had `Failed`, with the review trigger `Manual request`, and at 23:03:13Z a message that the usage limits for code reviews had been reached. Copilot: at 23:06:53Z, 3 minutes 55 seconds after the request, one review in the state `COMMENTED`, bound to `3bbce81`, with one inline comment on line 39 of this page; at 23:22:18Z, 3 minutes 26 seconds after the second request, one review in the state `COMMENTED`, bound to `a22bf38`, with no inline comment. |
| #249, #250, #399, #400, #401 and #402 | None. | None: no review, no review request, no Codex comment and no Codex reaction. |

- Every Copilot review in these records followed an explicit request: three on #239 and #258 by the maintainer, and two on #403 with the owner's account. On the six pull requests of the last row no Copilot request or review appears in the timelines.
- The Codex connector names its own triggers in the summary comment on #403: opening a pull request for review, marking a draft as ready, and a `@codex review` or `@codex security review` comment. Its first response on #403 came 8 seconds after the pull request was opened and before any request, which is consistent with a run at opening that failed on the usage limit. The comment does not say which trigger fired. On the six pull requests of the last row no Codex comment, review or reaction exists, so whether the opening trigger was active then, and left no trace, is not established.
- The outcomes follow the vocabulary of #247. The Copilot review of `3bbce81` is complete with an open finding: it asked to scope the sentence about workflow approval to the default `GITHUB_TOKEN`, and the commit that follows `3bbce81` does so in section 2. The Copilot review of `a22bf38` is complete with no inline finding. The Codex review of `3bbce81` is blocked by a usage limit, which #247 says is not review success.
- A subsequent commit was not reviewed by itself. `a22bf38` was pushed to #403 at 23:09:29Z, and at 23:18:40Z, 9 minutes 11 seconds later, the timeline, the reviews, the comments and the reactions of the pull request showed no request, review, Codex comment or reaction for it. The Codex connector names no push trigger. That is an observation of one window on one pull request, not a statement about longer delays or other pull requests.
- The review of `3bbce81` stayed on the pull request in the state `COMMENTED`, bound to a commit that was no longer the head. GitHub did not dismiss or change it. No dismissal setting is configured on `main`, so this shows only what happens to a `COMMENTED` review when no setting applies.
- No response in these records is an approval or a request for changes. The Copilot reviews are `COMMENTED` and the Codex responses are comments, so nothing here shows how GitHub treats an approval.
- A review is bound to a commit: each Copilot review names the commit that was the head when it was written, and the Codex receipt on #239 names the reviewed commit. On #239 and #258 that commit is still the head.

## 4. Merge behavior on this repository's own pull requests

Pull requests [#401](https://github.com/yeongseon/azure-app-service-practical-guide/pull/401) and [#402](https://github.com/yeongseon/azure-app-service-practical-guide/pull/402) were squash-merged by the owner's account on 2026-11-03, at 22:18:58Z as `838e9fa` and at 22:44:24Z as `8cda749`. Neither had a review or a review request. The merging agent applied the procedural gates of the documentation contract, and the merge-gate comment on each pull request, [on #401](https://github.com/yeongseon/azure-app-service-practical-guide/pull/401#issuecomment-6616823344) and [on #402](https://github.com/yeongseon/azure-app-service-practical-guide/pull/402#issuecomment-6617383364), records the Oracle review and the CI results on the exact head and was posted before the merge. GitHub enforced none of them.

GitHub reported the mergeability of #401 as `clean` before the merge, with an empty review decision, and the mergeability of #402 as `unstable` while a check had failed or was pending. The state `blocked` was not seen. These two states were read while the pull requests were open, and the raw responses were not retained. Both merge requests carried the expected head SHA in the `sha` parameter of the merge endpoint, which its documentation describes as the SHA that the head of the pull request must match for the merge to be allowed (see Sources). The requests were not retained, and that the endpoint refuses a moved head was not tested here. The installed GitHub CLI (2.4.0) rejected the `--match-head-commit` option, so the REST endpoint was used.

Both heads had the same 22 distinct checks: App and Infra CI Result, ASP.NET Core App, Bicep Templates, Build Documentation, Classify App and Infra Changes, Java Spring Boot App, Lab Evidence Verifiers, Node.js App, Node.js Container Smoke, Operating contract tests, PR metadata, PR title, Python Flask App, Shell Scripts, Validate CLI Explanation Tables, Validate Content Source Metadata, Validate Documentation Repetition, Validate Golden Contracts, Validate Golden Status, Validate MSLearn URLs, Validate PII and Validate Visual Content (advisory). None of them is required by GitHub. Validate MSLearn URLs runs only on pushes to `main`, so it is skipped on a pull request.

## 5. Result for each item of #396

| Item of the issue | Result |
|---|---|
| Report the tested head SHA, the review request or run, the reviewer response, the status checks and the protection settings | Reported in sections 2 to 4. The heads tested for merging are `3afb0a05ead21f581eb3e0ea0468155ced0f28c8` for #401 and `be6a46cffe717dc373422ebfda752a84661db75a` for #402. The review requests and responses on #403, on its first head and after a later commit, are in section 3. |
| Test missing review and failing CI as blocked, without inferring from a 403 that protection is absent | No required-review or required-check enforcement was configured at the recorded read, which rests on affirmative reads made with the `admin` permission and not on a 403. Merges without any review were observed, on #401 and #402. The rejection of a merge while CI is failing was not tested: with no protection configured, an attempted merge could merge into `main`, so none was attempted. |
| If admin-only settings are not readable, record them as unknown and do not enable auto-merge or bypass review | They were readable. Auto-merge was not enabled and no review was bypassed. Section 6 lists what stays unknown. |
| Reuse the policy updates of #256, #258 and #239 without modifying those pull requests in parallel | Nothing was changed there. This page records provider facts and sets no policy. |

## 6. What this does not establish

- Whether Copilot or Codex has automatic triggers beyond those that the Codex connector names itself, and whether the Codex opening trigger was active before 2026-11-03. The integration settings were not read here, and the absence of a trace on a pull request is not the absence of a run.
- How GitHub treats an approval, a requested change, a moved head or a stale review under a dismissal setting. No such case appears in the records above and none was exercised.
- How a review requirement or a second reviewer would change any of this: none was configured and none was exercised.
- That the settings are the same after 2026-11-03.

No setting was found that would make GitHub refuse a merge for a missing review or a failing check. That conclusion is derived from the settings, and only the missing-review half was observed, in two merges. Settings that could enforce the gates remotely exist: a ruleset or a branch protection with required status checks, required reviews, dismissal of stale reviews, approval of the last push and resolution of conversations, as the GitHub documentation under Sources describes them. None was changed here, none was tested, and this page chooses no values. Deciding which of them to enable, and which checks to require, belongs to the maintainer, as does the guarded auto-merge that #247 still lists. Issue #247 stays open: this page covers its remote-enforcement slice only and marks none of its checklist done.

## See Also

- [Golden Evidence Model](golden-evidence-model.md)
- [Reference](index.md)
- [Issue #247: require review of the final PR commit](https://github.com/yeongseon/azure-app-service-practical-guide/issues/247)
- [Issue #256: align triage, development and agent workflows](https://github.com/yeongseon/azure-app-service-practical-guide/issues/256)

## Sources

- [About protected branches (GitHub Docs)](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
- [Automatically merging a pull request (GitHub Docs)](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/automatically-merging-a-pull-request)
- [Get branch protection (GitHub REST API)](https://docs.github.com/rest/branches/branch-protection#get-branch-protection)
- [Merge a pull request (GitHub REST API)](https://docs.github.com/en/rest/pulls/pulls#merge-a-pull-request)
