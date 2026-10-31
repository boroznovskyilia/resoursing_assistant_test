# Final demonstration and submission checklist

This is a local preparation guide, not a sent submission. Actual-model evidence and
recording await Azure access; current limitations are in [NOT_DONE](../../NOT_DONE.md).

## Once credentials are available

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
