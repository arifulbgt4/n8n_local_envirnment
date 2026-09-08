# Meta setup: Facebook Messenger, Instagram, WhatsApp

## Shared callback

Use one public HTTPS callback:

`https://YOUR-PUBLIC-DOMAIN/webhook/meta-commerce`

The workflow exposes both:

- GET `/webhook/meta-commerce` for verification
- POST `/webhook/meta-commerce` for events

The GET verifier looks up the incoming `hub.verify_token` against active account rows synced from the Control Spreadsheet and returns `hub.challenge` only when valid.

## Facebook Messenger

For each Page, record separately in `02_ACCOUNTS`:

- Page ID
- Page Access Token
- Verify Token
- Meta App ID
- App Secret if you choose to store it
- Operations Spreadsheet ID

A Facebook Page ID such as `1347372081785892` is an external account ID, not your application's business ID.

Subscribe the Page/app to the messaging webhook fields needed by your use case. Enable message echoes if you want manual Page replies to switch conversations to HUMAN. The runtime stores bot outbound message IDs so bot echoes are ignored while real Page-owner messages can switch to HUMAN.

## Instagram

Use an Instagram professional account supported by the Meta messaging API you configure. Store its receiving account identifier and token on its own account row. Do not assume the Facebook Page ID and Instagram account ID are interchangeable.

## WhatsApp Cloud API

Store the WhatsApp `phone_number_id` as `External Account ID`, plus WABA ID and access token on the account row.

## Development vs public customers

Testing with app roles/test users can work before public release. Real non-role customers require the appropriate Meta app mode, product configuration, permissions/access level, and—when Meta requires it—App Review and/or Business Verification.

Meta changes its dashboard and review requirements over time. Prepare a clear use-case explanation, test instructions, privacy policy/data-deletion information if requested, and a screencast when the review flow asks for one. Do not treat n8n workflow publication as equivalent to Meta App Review approval.
