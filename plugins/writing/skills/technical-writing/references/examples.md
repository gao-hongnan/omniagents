# Before-and-after rewrites

Read this file when you want to see a rule at work. Each pair names the rules
that it applies. The "Before" text breaks rules on purpose, so the checker skips
it.

## Contents

- One reading per sentence (Global English)
- Sentences to the reader (Google developer style)
- One statement at a time (STE)
- One mode per doc (Diátaxis)
- Rhythm
- Machine-writing tells
- A PR description
- A commit message

## One reading per sentence (Global English)

<!-- lint-prose off -->

> The script only fails on growth. Since the budget is committed, it can't
> drift.

<!-- lint-prose on -->

> The script fails only when the count grows. Only a commit can change the
> budget, because Git tracks the budget file.

"Only" moves next to the condition that it limits. "Since" could mean "because"
or "after", so the rewrite says "because". "It" could mean the script or the
budget, so the noun comes back.

<!-- lint-prose off -->

> Restart the client and/or server. Update the API key(s) via the console, e.g.
> the Keys page.

<!-- lint-prose on -->

> Restart the client, the server, or both. To update the API keys, open the
> **Keys** page in the console.

"And/or" becomes "a, b, or both". The optional plural goes. "Via" and "e.g."
become plain words, and the goal moves before the action.

<!-- lint-prose off -->

> Phase 1 moves the converters and Phase 2 the runtime.

<!-- lint-prose on -->

> Phase 1 moves the converters, and Phase 2 moves the runtime.

The second clause gets its verb back.

## Sentences to the reader (Google developer style)

<!-- lint-prose off -->

> 1. The config file should be edited to add your token.
> 2. Simply run the deploy script — it will upload everything.
> 3. Click Save if you want to keep the draft.

<!-- lint-prose on -->

> 1. In `config.yaml`, set `auth.token` to your token.
> 2. Run `./deploy.sh`. The script uploads the build and prints its URL.
> 3. Optional: To keep the draft, click **Save**.

Each step is a command, with the location or goal first. "Should", the passive,
and "simply" go. The em dash becomes two sentences, and "will" becomes the
present tense. The result follows the action, and the UI label is bold.

## One statement at a time (STE)

<!-- lint-prose off -->

> After making sure the service is stopped, which you can do by running
> systemctl stop app, and backing up the data directory, upgrade the package and
> then restart the service and check the logs for errors.

<!-- lint-prose on -->

> 1. Stop the service: `systemctl stop app`.
> 2. Back up the data directory.
> 3. Upgrade the package.
> 4. Start the service: `systemctl start app`.
> 5. Check the logs for errors: `journalctl -u app`.

One sentence of 36 words carried five instructions. Each instruction now gets
its own step. "Start" pairs with "stop", so one action keeps one word.

<!-- lint-prose off -->

> 1. Run `db reset`. Warning: this deletes all data.

<!-- lint-prose on -->

> 1. Back up the database. The next step deletes every table and its data.
> 2. Run `db reset`.

The warning now comes before the step that it guards, and it opens with the
command.

## One mode per doc (Diátaxis)

A tutorial opening:

<!-- lint-prose off -->

> In this tutorial you will learn about webhooks, how they work, why they
> matter, and the various configuration options available.

<!-- lint-prose on -->

> In this tutorial, we build a webhook receiver that logs every push to a
> repository. At the end, you have a running server and one log line for each
> push.

The opening promises a result, not a lesson. The configuration options move to
the reference.

A how-to title:

<!-- lint-prose off -->

> Webhook configuration

<!-- lint-prose on -->

> How to verify webhook signatures

The title names the reader's task as a verb phrase.

A reference entry:

<!-- lint-prose off -->

> The timeout option is pretty important and you should probably set it to
> something reasonable, usually around 30 seconds, depending on your network.

<!-- lint-prose on -->

> `timeout`: the longest time, in seconds, that a request waits for a response.
> Type: integer. Default: `30`. Allowed: 1 to 300. A request that exceeds
> `timeout` raises `TimeoutError`.

The entry only describes. The advice and the hedges go, and the limit becomes a
fact.

An explanation:

<!-- lint-prose off -->

> There are pros and cons to sharding by tenant. Pros: isolation, simpler
> deletes. Cons: uneven shard sizes, harder cross-tenant queries. It depends on
> your use case.

<!-- lint-prose on -->

> We shard by tenant because a tenant's data must be deletable in one operation,
> and a shard for each tenant makes that one `DROP`. The cost is uneven shards:
> our largest tenant holds 30 percent of all rows. We accept that cost, because
> moving one large tenant is cheaper than finding a deleted tenant's rows across
> every shard.

The rewrite takes a position and says what the position costs.

## Rhythm

<!-- lint-prose off -->

> The cache is fast. It stores results. It expires after an hour. It is shared.
> It reduces load.

<!-- lint-prose on -->

> The cache keeps each result for an hour, and every worker shares it. A
> repeated query returns in under a millisecond, without a second trip to the
> database.

Five clipped sentences that start with "It" become two sentences of different
lengths, each with a specific fact.

## Machine-writing tells

<!-- lint-prose off -->

> In today's fast-paced development landscape, our robust CLI seamlessly
> empowers developers to unlock blazing-fast workflows — it's not just a tool,
> it's a game-changer!

<!-- lint-prose on -->

> `logslice` filters JSON log lines by time range and by field. On `<machine>`,
> it reads a 1 GB file in `<measured time>`.

Every tell goes, and a measurement replaces the claims. The placeholders show
where the measured values go. Never invent them.

## A PR description

<!-- lint-prose off -->

> ## Summary
>
> This PR introduces comprehensive improvements to the retry logic! 🚀 I started
> by exploring the codebase and found that the uploader had some issues. Then I
> refactored the retry module, updated the tests, and fixed some edge cases.
>
> ## Changes
>
> - Modified `uploader.py`
> - Modified `retry.py`
> - Modified `test_uploader.py`
>
> ## Test results
>
> (40 lines of pasted pytest output)
>
> All tests pass ✅

<!-- lint-prose on -->

> **Stop retrying 4xx responses in the uploader**
>
> The uploader retries every failed request, including 4xx responses that can't
> succeed. A bad token causes five retries for each file and ends in a timeout
> instead of the real 401. This change retries network errors, 429, and 5xx
> responses, and raises any other 4xx at once.
>
> ## Verification
>
> - `pytest tests/uploader`: 212 passed, including a new test for a 401
>   response. [CI run](https://ci.example.com/runs/1234)
> - A manual upload with an expired token fails at once with `401 Unauthorized`.
>
> ## Risk and rollout
>
> Callers that caught `TimeoutError` for a bad token now get `HTTPError` with
> the status code. `sync.py` was the only such caller, and this PR updates it.

The briefing opens with the problem and the change. Verification names commands
and results and links the log. The risk section names the one caller that
changes.

## A commit message

<!-- lint-prose off -->

> Updated retry logic and fixed some bugs in uploader and tests.

<!-- lint-prose on -->

```text
Stop retrying 4xx responses in the uploader

The uploader retries every failed request, so a bad token causes five
retries for each file and ends in a timeout instead of a 401.

Retry only network errors, 429, and 5xx responses. Raise any other 4xx
at once, so that the caller sees the real status code.

Fixes #482
```

The subject is an imperative of 43 characters with no period. The body states
the problem in the present tense, then the fix and its reason.
