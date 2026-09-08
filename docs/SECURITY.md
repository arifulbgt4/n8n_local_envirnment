# Security and abuse protection

## AI cost guard order

Before expensive AI/media calls, the runtime should enforce:

1. webhook message dedupe
2. bot-echo filtering
3. HUMAN-mode guard
4. per-customer messages/minute
5. repeated-message protection
6. AI turns/hour
7. AI turns/day
8. estimated daily token budget
9. response cache / deterministic routing when possible
10. only then transcription, vision, or LLM calls

Blocked spam is not automatically escalated to HUMAN.

## Human handoff

Customer receives no automatic “sent to human support” message. AI handoff writes DB + HumanSupportQueue and stops silently.

## Secrets

Never commit `.env` or real credentials. This project allows Meta tokens in the Control Spreadsheet because spreadsheet-driven administration is a product requirement. Treat the sheet as sensitive infrastructure and limit access.
