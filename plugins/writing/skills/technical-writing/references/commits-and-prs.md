# Commits, PRs, and changelogs

Read this file before you write a commit message, a PR description, a changelog
entry, or release notes. Every layer of the hub applies to them except Diátaxis.

## Contents

- Follow the repo first
- Write the commit message
- Write the PR description
- Write changelog entries and release notes
- Sources

## Follow the repo first

Read the repo's convention before you write. A convention that the repo already
follows beats every default below.

```bash
git log --oneline -20                    # subject style, prefixes, and case
git log -5                               # body style and trailers
ls .github/ | grep -i pull_request       # PR template, if any
```

Keep the repo's prefix scheme when it has one. Two common schemes are
Conventional Commits (`feat(api): ...`) and the "area: " prefix that Git itself
uses (`doc: ...`). Match the capitalization after the prefix too.

## Write the commit message

```text
<Subject: imperative, 50 characters or fewer, no period>

<The problem, in the present tense: what the code does now, and why
that is wrong. Wrap the body at 72 columns.>

<Why this change fixes the problem, and what you considered and
rejected. Leave the how to the diff.>

<Trailers that the repo uses, such as "Fixes #482".>
```

Follow these rules:

- Use the imperative mood: "Add retry to the uploader", not "Added retry" or
  "This commit adds retry". The subject completes the sentence "If applied, this
  commit will...".
- Keep the subject to 50 characters when you can, and never past 72. End it
  without a period.
- Leave one blank line between the subject and the body.
- State the problem in the present tense: "The uploader gives up after one
  timeout", not "The uploader used to give up".
- Make the message stand alone. A link can support the reason but can't replace
  it. Summarize the discussion, then link it.
- Skip the body only when the subject says everything: "Fix typo in
  `README.md`".
- Make one logical change per commit. A subject that needs "and" often describes
  two commits.

| Subject                                         | Problem                             | Better subject                                 |
| ----------------------------------------------- | ----------------------------------- | ---------------------------------------------- |
| "Fix bug"                                       | Names no bug.                       | "Stop retrying 4xx responses in the uploader"  |
| "Updated files"                                 | Past tense, and says nothing.       | "Rename `retry_count` to `max_retries`"        |
| "Phase 1"                                       | Means nothing outside the plan.     | "Move the converters into `pkg/convert`"       |
| "Add comprehensive error handling improvements" | Slop, and no specifics.             | "Return 400 for a malformed `since` parameter" |
| "Moving code from A to B."                      | Not imperative, ends with a period. | "Move the date helpers into `util/time.py`"    |

## Write the PR description

```markdown
<Title: the squash-commit subject. Imperative, 72 characters or fewer.>

<What changes and why, in two to four sentences. Open with the problem that the
reviewer cares about.>

## Verification

- `<command>`: <result, in one line>. <Link to the CI run.>
- <A manual check, and what it showed.>

## Risk and rollout

<Optional. Migrations, feature flags, deploy order, and how to roll back.>

## Review notes

<Optional. Where to start, what is mechanical, and what needs care.>

Fixes #<issue>. Design doc: <link>.
```

Follow these rules:

- Write for a reviewer who has one minute. The first two sentences tell the
  reviewer what changed and why.
- Open with the problem, then the change. Don't open with "This PR".
- State verification as commands and results. Link the logs and CI runs. Don't
  paste them.
- Name what you didn't test, and why.
- Point the reviewer at the risky part. A large mechanical change gets one
  sentence: "The rename in 40 files is mechanical. Review
  `pkg/convert/convert.go`."
- Don't list files or narrate your steps. The diff shows the files, and the
  reviewer doesn't need your history.
- Don't write "no breaking changes" unless you checked. Say what you checked.
- Use the repo's PR template when it has one, and fill in its sections. Delete a
  section that doesn't apply instead of writing "N/A" in it.
- Update the description when review changes the PR. A description that no
  longer matches the diff misleads every later reader of the history.

## Write changelog entries and release notes

- Write for the users of the product, not for its developers. Say what changed
  for them and what they must do.
- Put breaking changes and required actions first.
- Write one entry for each change that a user can see. Don't paste commit
  subjects.
- Follow the file's existing format. In a file that follows Keep a Changelog,
  group entries under "Added", "Changed", "Deprecated", "Removed", "Fixed", and
  "Security".
- Link the PR or the issue from each entry.
- Name the version and the date in a form that reads one way: "1.4.0,
  2026-10-23".

<!-- lint-prose off -->

Before:

> - Refactored config loader, misc fixes

<!-- lint-prose on -->

After:

> - **Changed:** The config loader reads `APP_CONFIG` before `config.yaml`. If
>   you set both, the environment variable now wins. Remove `APP_CONFIG` from
>   your environment to keep the old behavior. (#512)

## Sources

- Git project, "Describe your changes well" in
  [SubmittingPatches](https://git-scm.com/docs/SubmittingPatches): the
  imperative mood, the problem in the present tense, and the 50-character
  subject.
- Google engineering practices,
  ["Writing good CL descriptions"](https://google.github.io/eng-practices/review/developer/cl-descriptions.html):
  a first line that stands alone, and a body with the problem, the approach, and
  its shortcomings.
- Chris Beams,
  ["How to Write a Git Commit Message"](https://cbea.ms/git-commit/), 2014: the
  seven rules and the "If applied, this commit will" test.
- [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/): the change
  categories.
