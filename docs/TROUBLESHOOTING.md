# Troubleshooting

## Meta verification returns 403

Run Step 03 first. Confirm the account is Active and its Verify Token exactly matches the token entered in Meta.

## Incoming customer message finds no account

Compare the webhook receiving identifier with `02_ACCOUNTS -> External Account ID`:

- Facebook: Page ID / recipient.id
- WhatsApp: metadata.phone_number_id
- Instagram: receiving Instagram account identifier used by your webhook payload

## Product price becomes 0

Confirm your sheet header is recognized. `Price (৳)` is supported by the normalization design; do not replace missing prices with guessed values.

## AI stops replying after a human message

Check `HumanSupportQueue -> Mode`. If it is `HUMAN`, set it to `AI` and run Step 06 or wait for the production human-control schedule.

## Bot replies switch to HUMAN by mistake

Confirm the send-message response message ID is being stored in `bot_outbound_messages`; Page echo detection must compare echo `message_id` against this table.

## n8n shows localhost webhook URL

Set `N8N_WEBHOOK_URL` to your public HTTPS ngrok/domain URL, restart the containers, then re-open the Webhook node.
