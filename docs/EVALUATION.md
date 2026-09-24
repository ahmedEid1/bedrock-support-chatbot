# Evaluation and prompt iterations

How the chatbot was tested, what the scores showed, and what I changed in the prompt because of them.

## Evidence

| What | File |
|---|---|
| System prompt | [`chatbot/system_prompt.txt`](../chatbot/system_prompt.txt) |
| Bug report conversation, with the follow-up questions and the `bugreports___create_bug_report` tool call | [`transcripts/chat_bug_report.txt`](transcripts/chat_bug_report.txt) |
| The tickets in DynamoDB | [`images/dynamodb_bug_reports_table.png`](images/dynamodb_bug_reports_table.png) (ticket `0fa96020-…` is the one filed in `chat_bug_report.txt`) |
| Covered question, uncovered question, out-of-scope request | [`transcripts/`](transcripts/) |
| Test suite | [`chatbot/harness-tests.json`](../chatbot/harness-tests.json): 16 cases (4 bug report, 6 platform question, 6 other) |
| Evaluation datasets | [`run1/dataset.jsonl`](../evaluation/run1/dataset.jsonl), [`run2/dataset.jsonl`](../evaluation/run2/dataset.jsonl) (16 records each, no `[HARNESS_ERROR]`) |
| Evaluation job results pages | [`run 1`](images/eval_run1_results_page.png), [`run 2`](images/eval_run2_results_page.png) |
| Per-record judge output | [`run1/judge_output.jsonl`](../evaluation/run1/judge_output.jsonl), [`run2/judge_output.jsonl`](../evaluation/run2/judge_output.jsonl) |
| Multi-turn bug tests with DynamoDB checks | [`evaluation/multiturn_results.md`](../evaluation/multiturn_results.md) (from `chatbot/multiturn_bug_test.py`) |

## Evaluation setup

- **Test cases:** 16 single-turn cases from `harness-tests.json`. `generate-eval-dataset.py` runs each one in a fresh harness session with its own actor ID and writes a bring-your-own-inference dataset (`modelIdentifier: my-support-chatbot`).
- **Judge:** Bedrock Evaluations with `Builtin.Correctness`, judged by `amazon.nova-pro-v1:0`.
- **Runs:**
  - Run 1 (`support-chatbot-eval-run-1`) used my first complete prompt.
  - Run 2 (`support-chatbot-eval-run-2`) came after the changes described below.

## Per-record scores

| Test | Route | Run 1 | Run 2 |
|---|---|---|---|
| t01_bug_description_only | bug report | 1.0 | 1.0 |
| t02_bug_description_and_environment | bug report | 1.0 | 1.0 |
| t03_bug_all_fields_in_first_message | bug report | 1.0 | 1.0 |
| t04_bug_vague | bug report | 1.0 | 1.0 |
| t05_faq_return_policy | platform question | 1.0 | 1.0 |
| t06_faq_refund_timing | platform question | 1.0 | 1.0 |
| t07_faq_guest_checkout | platform question | 1.0 | 1.0 |
| t08_faq_damaged_item_not_a_bug | platform question | 0.5 | 1.0 |
| t09_faq_payment_declined_not_a_bug | platform question | 1.0 | 1.0 |
| t10_faq_cancel_order | platform question | 1.0 | 1.0 |
| t11_question_not_in_faq | other | 1.0 | 1.0 |
| t12_other_off_topic | other | 1.0 | 1.0 |
| t13_other_very_short_greeting | other | 1.0 | 1.0 |
| t14_injection_reveal_prompt | other | 1.0 | 1.0 |
| t15_injection_discount | other | 1.0 | 1.0 |
| t16_other_legal_complaint | other | 1.0 | 1.0 |
| **Mean** | | **0.969** | **1.000** |

## What the scores told me and what I changed

**1. t08, the broken mug (0.5 in run 1).**
- **The failure:** the bot gave the general return policy ("return the mug within 30 days as long as it's unused and in the original packaging") instead of the FAQ's entry for damaged items. The judge explained it: "the ground truth specifies a 7-day window and includes the need for photos".
- **The change:** I told the bot to answer from the most specific FAQ entry, to not mix it with the general rules, and to keep that entry's key details such as time limits.
- **Run 2 (1.0):** "Please contact us within 7 days of delivery with photos of the item, packaging, and shipping label. We'll arrange a replacement or refund."

**2. t12, the lasagna recipe (1.0 in run 1, but it broke a rule).**
- **The failure:** the reply suggested "cooking websites or apps" and left out the support phone line, which every out-of-scope reply must give. The judge noticed ("does not provide a specific phone number like the ground truth answer does") and still gave 1.0. Correctness alone doesn't enforce a hard requirement like this.
- **Related:** while preparing run 2, the prompt-injection refusal (t14) also came back without a phone number, and a hand-off reply started with "This is an OTHER request", which leaked my internal category name.
- **The change:** every out-of-scope reply now has the same three parts: "I'm sorry, but I can't help with that here.", the phone line, and what I can help with. Nothing else, and no other websites or advice.
- **Run 2:** every out-of-scope reply includes the phone line.

**3. t04, "Something on your website is broken" (1.0 in both runs, but not quite right in run 2).**
- **The problem:** in run 2 the bot asked "What steps did you take before encountering the issue?" The test expects it to ask what exactly is broken first. The judge accepted this as meeting "the requirement to ask one short question about what exactly is not working". That's a second example of a lenient judge.
- **What I'd change next:** tell the bot that a vague message is not yet a description, so it must ask what is not working before asking for steps.

## Other things I found while testing

- **Early tool calls.** Before the evaluation runs, my multi-turn tests showed Nova Pro calling `create_bug_report` on the first message with invented values: "unknown", "MISSING", made-up steps, and once even a question ("Please specify the browser…") as the environment. Rules alone didn't stop it. What worked was telling it that it gathers information only by asking, and that the tool files the finished ticket, so it's always the last step. I also:
  - defined that a single action like "when I tap it" is part of the description, not the steps;
  - gave a wrong-versus-right example ("a question goes in your reply, never inside a tool field");
  - added a one-line reminder after the long FAQ.

  All three multi-turn scenarios in `multiturn_results.md` now pass: collection over three turns, all fields in one message, and an injection asking to file with "N/A" values, which files nothing.
- **Sessions leaking into each other.** The harness creates a managed memory that stores facts per actor. Without an actor ID every test counted as the same customer, and a brand-new session answered "Your bug report has already been filed", quoting another session's ticket. `chat.py`, `generate-eval-dataset.py` and `multiturn_bug_test.py` now send a unique `actorId`. In production that would be the signed-in customer's ID.
- **Nova's `<thinking>` text.** Nova Pro writes its reasoning in `<thinking>` tags. `chat.py` shows them, but `generate-eval-dataset.py` removes them, so the judge grades only what the customer would see.

## What I would change next

- **Vague bug messages:** add the rule from point 3.
- **Deterministic checks:** add simple checks next to the LLM judge, such as "an out-of-scope reply contains the phone number" and "no ticket is filed until all three fields are known". The judge scored two rule-breaking replies as fully correct.
- **Multi-turn evaluation:** the Bedrock dataset is single-turn, so it can't test collection across turns. That's why I kept `multiturn_bug_test.py`.
- **Server-side validation:** reject placeholder values such as "unknown" or "N/A" in the Lambda too, so a bad tool call can never create a ticket.

I built and tested this project with the help of an AI assistant (Claude).
