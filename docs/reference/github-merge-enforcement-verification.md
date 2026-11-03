---
title: GitHub Merge Enforcement Verification (#396)
slug: github-merge-enforcement-verification
doc_type: reference
section: reference
summary: Dated record of what GitHub itself enforces on the default branch of this repository and how its review integrations behaved on real pull requests, separating settings that were read from policy text and from behavior that could not be tested.
topics: [quality-gates, ci]
products: [azure-app-service]
content_sources:
  references:
    - type: self-generated
      justification: Observations of the GitHub REST API for this repository on 2026-11-03, made read-only with the owner account, and of the review timelines of eight pull requests. The page makes no Azure-behavior claim, and the settings it reports can change after the date.
---

# GitHub Merge Enforcement Verification (#396)

This page records what GitHub enforces on the default branch of this repository, and how the review integrations behaved on real pull requests, as issue [#396](https://github.com/yeongseon/azure-app-service-practical-guide/issues/396) asks. It is the remote-enforcement slice of [#247](https://github.com/yeongseon/azure-app-service-practical-guide/issues/247). It sets no policy: the review and merge rules are written in the repository's authoring contract, and the open draft pull requests [#239](https://github.com/yeongseon/azure-app-service-practical-guide/pull/239) and [#258](https://github.com/yeongseon/azure-app-service-practical-guide/pull/258) propose changes to them. Text that describes a rule is not a setting that enforces it, so the sections below keep what was read, what was observed and what could not be tested apart.

## 1. Basis

| Item | Value |
|---|---|
| Repository | `yeongseon/azure-app-service-practical-guide`, default branch `main`, head `8cda749f0fd258b207c06d5bf35e89875d21c78e` when the settings were read. |
| Read at | 2026-11-03T22:47:28Z, which is 07:47 on 2026-11-04 in Asia/Seoul. |
| Account and permission | The repository owner's account, whose permission on the repository is `admin`. Issue #247 recorded an HTTP 403 for a different credential, and a 403 does not show that protection is absent. With the `admin` permission the same read is answered with `404 Branch not protected`, which is an answer about the branch, and the `protected` flag of the branch summary agrees with it. |
| Method | Read-only `GET` requests to the GitHub REST API, listed in section 2, and the review timelines of eight pull requests. No setting was changed, no auto-merge was enabled, no review was bypassed, and no merge was attempted to test a block. |
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
| GitHub Actions | Enabled with all actions allowed. The default workflow token is `read`, workflows cannot approve pull requests (`can_approve_pull_request_reviews` is false), and pinning actions to a commit SHA is not required (`sha_pinning_required` is false). | `GET /repos/{repo}/actions/permissions` and `GET /repos/{repo}/actions/permissions/workflow` |
| Code owners | No `CODEOWNERS` file exists in the repository. | A listing of the repository files |

The only rule of the documentation contract that GitHub enforces itself is the merge method. The contract's other merge gates, the Oracle review, CI on the exact head and the image checks, are procedural. The contributing guide asks for external actions pinned to a verified commit SHA, and the setting that would require it is off.

## 3. Review integrations on real pull requests

| Pull request | Review request | Reviewer response |
|---|---|---|
| [#239](https://github.com/yeongseon/azure-app-service-practical-guide/pull/239), draft | A comment by the maintainer, `@codex review`, naming head `278598d`, at 2026-10-16T12:55:19Z. A request for a Copilot review by the maintainer at 2026-10-24T12:00:41Z. | Codex: a state comment after 22 seconds and a review receipt after about 3 minutes, which names the reviewed commit `278598db47`. Copilot: one review in the state `COMMENTED`, bound to `278598db47`, after about 5.5 minutes. |
| [#258](https://github.com/yeongseon/azure-app-service-practical-guide/pull/258), draft | Two requests for a Copilot review by the maintainer, at 2026-10-24T07:05:03Z and 07:08:12Z. | Copilot: two reviews in the state `COMMENTED`, bound to `29cb9717c6`, after about 2.5 and 3 minutes. |
| #249, #250, #399, #400, #401 and #402 | None. | None. |

- Every response followed an explicit request by the maintainer. Opening a pull request, and pushing new commits to one, produced no request and no review: #401 went from `7e00792` to `ea5439e` to `3afb0a0`, and #402 from `528cb3e` to `be6a46c`, and neither received a review request or a review.
- No response is an approval or a request for changes. The Copilot reviews are `COMMENTED` and the Codex responses are comments, so nothing here shows how GitHub treats an approval.
- A review is bound to a commit: each Copilot review names the commit that was the head when it was written, and the Codex receipt names the reviewed commit. On both #239 and #258 that commit is still the head, so no stale review occurred among them, and how GitHub handles one was not observed.

## 4. Merge behavior on this repository's own pull requests

Pull requests [#401](https://github.com/yeongseon/azure-app-service-practical-guide/pull/401) and [#402](https://github.com/yeongseon/azure-app-service-practical-guide/pull/402) were squash-merged by the owner's account on 2026-11-03, at 22:18:58Z as `838e9fa` and at 22:44:24Z as `8cda749`. Neither had a review or a review request. They were merged after the gates of the documentation contract passed: an Oracle review of at least 90 on the exact head and green CI on that head.

GitHub reported the mergeability of #401 as `clean` before the merge, with an empty review decision, and the mergeability of #402 as `unstable` while a check had failed or was pending. The state `blocked` was not seen. Both merge requests carried the expected head SHA in the `sha` parameter of the merge endpoint, which the endpoint documents as a guard against a head that moved. That guard belongs to the request, not to a repository setting, and the installed GitHub CLI (2.4.0) has no option for it. That the endpoint refuses a moved head was not tested here.

Both heads had the same 22 distinct checks: App and Infra CI Result, ASP.NET Core App, Bicep Templates, Build Documentation, Classify App and Infra Changes, Java Spring Boot App, Lab Evidence Verifiers, Node.js App, Node.js Container Smoke, Operating contract tests, PR metadata, PR title, Python Flask App, Shell Scripts, Validate CLI Explanation Tables, Validate Content Source Metadata, Validate Documentation Repetition, Validate Golden Contracts, Validate Golden Status, Validate MSLearn URLs, Validate PII and Validate Visual Content (advisory). None of them is required by GitHub. Validate MSLearn URLs runs only on pushes to `main`, so it is skipped on a pull request.

## 5. Result for each item of #396

| Item of the issue | Result |
|---|---|
| Report the tested head SHA, the review request or run, the reviewer response, the status checks and the protection settings | Reported in sections 2 to 4. The tested heads are `3afb0a05ead21f581eb3e0ea0468155ced0f28c8` for #401 and `be6a46cffe717dc373422ebfda752a84661db75a` for #402. |
| Test missing review and failing CI as blocked, without inferring from a 403 that protection is absent | Not blocked by GitHub. No protection and no ruleset exist, which was read with the `admin` permission and not inferred from a 403. Blocking could not be demonstrated by an attempted merge without risking a real merge into `main`, so none was attempted. Section 4 gives the mergeability states that GitHub reported. |
| If admin-only settings are not readable, record them as unknown and do not enable auto-merge or bypass review | They were readable. Auto-merge was not enabled and no review was bypassed. Section 6 lists what stays unknown. |
| Reuse the policy updates of #256, #258 and #239 without modifying those pull requests in parallel | Nothing was changed there. This page records provider facts and sets no policy. |

## 6. What this does not establish

- Whether the Copilot or Codex integration has an automatic trigger at an organization or account level. None fired on the eight pull requests above, but those settings are not readable through this repository's API.
- How GitHub treats an approval, a requested change, a stale review or a moved head, because no setting exists on `main` that would exercise them.
- That the settings are the same after 2026-11-03.
- Anything about a second reviewer or a required review, because none exists.

Nothing on the repository would make GitHub refuse a merge for a missing review or a failing check, so the contract's gates hold only while the people and agents who merge follow them. Settings that would enforce the gates remotely exist: a ruleset or a branch protection with required status checks, required reviews, dismissal of stale reviews, approval of the last push and resolution of conversations. None was changed here, and this page chooses no values. Deciding which of them to enable, and which checks to require, belongs to the maintainer, as does the guarded auto-merge that #247 still lists. Issue #247 stays open: this page covers its remote-enforcement slice only and marks none of its checklist done.

## See Also

- [Golden Evidence Model](golden-evidence-model.md)
- [Reference](index.md)
- [Issue #247: require review of the final PR commit](https://github.com/yeongseon/azure-app-service-practical-guide/issues/247)
- [Issue #256: align triage, development and agent workflows](https://github.com/yeongseon/azure-app-service-practical-guide/issues/256)

## Sources

- [About protected branches (GitHub Docs)](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
- [Automatically merging a pull request (GitHub Docs)](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/automatically-merging-a-pull-request)
- [Get branch protection (GitHub REST API)](https://docs.github.com/rest/branches/branch-protection#get-branch-protection)
