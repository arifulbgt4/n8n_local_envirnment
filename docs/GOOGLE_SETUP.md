# Google Sheets authentication

Google Sheets access uses Google OAuth2/Google Sheets credentials in n8n. It is not a Gmail sending token.

1. Create/select a Google Cloud project.
2. Enable Google Sheets API. Enable Google Drive API too if you later add Drive file operations.
3. Configure the OAuth consent screen.
4. Create an OAuth Client ID for a Web application.
5. In n8n, create a Google Sheets OAuth2 credential and copy n8n's OAuth redirect URL into the Google client's Authorized redirect URIs.
6. Authorize the Google account that owns or can edit the Control Spreadsheet and account Operations Spreadsheets.
7. Attach this same credential to every Google API HTTP Request node in the workflow.

The one installation runtime input remains only the Control Spreadsheet ID; OAuth is configured once beforehand.
