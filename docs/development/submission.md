# Final demonstration and submission checklist

This is a local preparation guide, not a sent submission. Actual-model evaluation
and the local recording are complete; current limitations are in
[NOT_DONE](../../NOT_DONE.md).

## Prepared local demo

The [versioned transcript](demo-transcript.md) records the genuine Azure-backed UI
session on 2 November 2026: factual SQL, semantic recommendations, booking Confirm
after a real API process restart, and Reject. Local files are under
`.runtime/demo/20261102/`, including `resourcing-assistant-demo.mp4` (2m35s, English
captions, no audio), `resourcing-assistant-raw.webm` (continuous4m54s), delivered
answers, process/database evidence and verification results. An explicitly labelled
8x edit shortens only the semantic-response waiting interval; replies are unchanged.
The isolated demo runtime was stopped afterwards; main saved chats were untouched.
The original source hash and all24 source-table invariants passed. Only one confirmed
40-hour soft booking was added in the demo copy; repeat Confirm and Reject added none.
Video upload and repository sharing have not happened.

## Re-recording procedure

1. Add supplied endpoint/key to .env, run `make setup` without overwriting saved state,
   and start `make run`. Verify health and an actual DSPy chat/embedding smoke call.
2. Run `make test`, browser checks and `make evaluate`. Review every reported failure,
   preserve all runs, and complete manual semantic/refusal evidence review. Copy the
   actual per-case table/settings into README; never substitute source-oracle results.
3. Record three conversations in the UI: a factual multi-table question with SQL; a
   ranked semantic recommendation with source evidence; and a soft-booking proposal.
4. For booking, show person/project/visible dates/hours and no pre-confirm booking;
   stop the actual API (Ctrl+C), restart the same `make run`/runtime, reopen the same
   conversation, and Confirm. Show one stable booking receipt on repeated readback.
   Demonstrate Reject separately with zero new booking. Do not clear runtime on restart.
5. Verify reference time April1 2026 in UI; audit time remains actual UTC. Mask credentials
   and keep .env/ordinary source secrets out of recording, Git and report artifacts.

Suggested prompts are public assignment examples, not hard-coded application templates:
EMEA/Python/availability; experienced data engineers for a migration; Amanda Evans on
ENG-2026-0001 for40h in April. The real interpreter must support changed filters too.

## Public-repository security check — 2 November 2026

Baseline `48feed3`: all24 reachable commits,312 Git blobs and141 tracked files were
checked. Official Gitleaks v8.30.1 passed both complete Git history and a snapshot of
the tracked working tree with zero findings. The downloaded release checksum was
verified; source files and credentials were not uploaded to any scanner service.
An additional exact scan found no configured Azure key or its encoded variants in
Git objects, tracked files or the uncompressed assignment document package.

`.env` is ignored, untracked and mode0600. `.env.example` is tracked with empty key
and endpoint fields. Ignore checks cover secret env variants, runtime databases/logs,
dependencies, caches, build output and browser artifacts. None of these private or
generated paths was found in Git history. The bundled mock database is intentional;
all four supplied-file hashes still match the original assignment files.

Local reports are under `.runtime/publication-audit/20261102/` and stay out of Git.
No Git remote was configured at audit time; no push, upload or external message was
performed. The submission draft below intentionally awaits actual delivery links.

## Before sharing

Fresh Git-clone setup/run/build/test commands must work with local source/tokenizer,
without hidden runtime state. Check README, one-page DESIGN and honest NOT_DONE against
actual behavior, meaningful Git history and accessible reviewer links. The email asks
for a recording; the brief also allows a transcript. Prefer the recording.

Publishing, sharing links and sending any message require applicable explicit owner
instruction. No recipient address was provided in the pasted invitation. Deadline is
2026-11-02, exact time/timezone unspecified. Do not invent an address or publish a
repository merely because local development is authorized.

Draft message for owner review after evidence is complete:

> Hi Clarise,
> Here are the repository and demo recording: [insert actual reviewed links].
> Setup, evaluation results, design decisions and remaining limitations are documented
> in README.md, DESIGN.md and NOT_DONE.md.
> Kind regards,
> Ilia

The placeholders above are not real links or a claim that submission is ready.
