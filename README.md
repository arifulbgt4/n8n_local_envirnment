# n8n Local Environment

A simple local Docker setup for running **n8n** with persistent workflow/credential storage.

This repository is intended for local development and testing, including the Facebook automation workflow.

## Prerequisites

Install these first:

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- Git

Verify Docker is running:

```bash
docker --version
```

## Quick Start

### 1. Clone this repository

```bash
git clone https://github.com/arifulbgt4/n8n_local_envirnment.git
cd n8n_local_envirnment
```

### 2. Create persistent n8n storage

Run this only once:

```bash
docker volume create n8n_data
```

The `n8n_data` Docker volume keeps your workflows, credentials, executions, and local n8n configuration even if the container is removed or upgraded.

### 3. Start n8n

```bash
docker run -d \
  --name n8n \
  --restart unless-stopped \
  -p 5678:5678 \
  -e TZ=Asia/Dhaka \
  -e GENERIC_TIMEZONE=Asia/Dhaka \
  -e N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS=true \
  -e N8N_RUNNERS_ENABLED=true \
  -v n8n_data:/home/node/.n8n \
  docker.n8n.io/n8nio/n8n
```

### 4. Open n8n

Open this URL in your browser:

```text
http://localhost:5678
```

On the first run, n8n will ask you to create the local owner account.

---

## Common Commands

### View running container

```bash
docker ps
```

### View n8n logs

```bash
docker logs -f n8n
```

Press `Ctrl + C` to stop following the logs. This does not stop n8n.

### Stop n8n

```bash
docker stop n8n
```

### Start n8n again

```bash
docker start n8n
```

### Restart n8n

```bash
docker restart n8n
```

### Check container status

```bash
docker ps -a --filter name=n8n
```

---

## Updating n8n

Your workflows and credentials are stored in the `n8n_data` volume, so you can replace the container without losing them.

### 1. Pull the latest n8n image

```bash
docker pull docker.n8n.io/n8nio/n8n
```

### 2. Stop and remove the old container

```bash
docker stop n8n
docker rm n8n
```

### 3. Start a new container

```bash
docker run -d \
  --name n8n \
  --restart unless-stopped \
  -p 5678:5678 \
  -e TZ=Asia/Dhaka \
  -e GENERIC_TIMEZONE=Asia/Dhaka \
  -e N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS=true \
  -e N8N_RUNNERS_ENABLED=true \
  -v n8n_data:/home/node/.n8n \
  docker.n8n.io/n8nio/n8n
```

Then open:

```text
http://localhost:5678
```

---

## Facebook Webhook Development

Facebook/Meta cannot call `localhost` directly. For webhook development, expose local n8n through a public HTTPS tunnel such as **ngrok**.

### 1. Start n8n

Make sure n8n is available at:

```text
http://localhost:5678
```

### 2. Start ngrok

If ngrok is already installed:

```bash
ngrok http 5678
```

ngrok will return a public HTTPS URL similar to:

```text
https://example-name.ngrok-free.app
```

### 3. Use the public URL for the Facebook callback

For example, if the n8n production webhook path is:

```text
/webhook/facebook
```

then use:

```text
https://example-name.ngrok-free.app/webhook/facebook
```

as the Meta/Facebook webhook callback URL.

> Use the **Production URL** from the n8n Webhook node when the workflow is active. The Test URL is intended for temporary manual testing.

If your free ngrok URL changes after restarting ngrok, update the callback URL in Meta Developer settings.

---

## Facebook GET + POST Webhook

For the Facebook workflow, the same webhook path can be configured to support both methods:

```text
GET  -> webhook verification
POST -> Facebook events/messages
```

Typical flow:

```text
Webhook
├── GET  -> IF verify token -> Respond with hub.challenge
└── POST -> Respond 200 -> Process Facebook event
```

The workflow must be active when Meta sends requests to the production webhook URL.

---

## Local Secure Cookie Warning

If n8n shows a secure-cookie error while using plain local HTTP, you can use the following environment variable **for local development only**:

```text
N8N_SECURE_COOKIE=false
```

To apply it, remove and recreate the container:

```bash
docker stop n8n
docker rm n8n
```

Then start it with:

```bash
docker run -d \
  --name n8n \
  --restart unless-stopped \
  -p 5678:5678 \
  -e TZ=Asia/Dhaka \
  -e GENERIC_TIMEZONE=Asia/Dhaka \
  -e N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS=true \
  -e N8N_RUNNERS_ENABLED=true \
  -e N8N_SECURE_COOKIE=false \
  -v n8n_data:/home/node/.n8n \
  docker.n8n.io/n8nio/n8n
```

Do not use `N8N_SECURE_COOKIE=false` for a public production deployment.

---

## Backup n8n Data

Create a backup of the persistent Docker volume:

```bash
docker run --rm \
  -v n8n_data:/data \
  -v "$PWD":/backup \
  alpine \
  tar czf /backup/n8n-data-backup.tar.gz -C /data .
```

This creates:

```text
n8n-data-backup.tar.gz
```

in the current directory.

Do not commit backup files containing credentials to a public repository.

---

## Completely Reset n8n

> Warning: this permanently deletes the local n8n workflows, credentials, and configuration stored in the Docker volume.

```bash
docker stop n8n
docker rm n8n
docker volume rm n8n_data
```

Then start again from the **Quick Start** section.

---

## Troubleshooting

### Port 5678 is already in use

Check which Docker container is using the port:

```bash
docker ps
```

You can use another host port if needed:

```bash
docker run -d \
  --name n8n \
  --restart unless-stopped \
  -p 5679:5678 \
  -e TZ=Asia/Dhaka \
  -e GENERIC_TIMEZONE=Asia/Dhaka \
  -e N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS=true \
  -e N8N_RUNNERS_ENABLED=true \
  -v n8n_data:/home/node/.n8n \
  docker.n8n.io/n8nio/n8n
```

Then open:

```text
http://localhost:5679
```

### Container name `n8n` already exists

Check it:

```bash
docker ps -a --filter name=n8n
```

If it is stopped, simply run:

```bash
docker start n8n
```

If you intentionally want to recreate it:

```bash
docker rm n8n
```

The `n8n_data` volume remains untouched.

### n8n is not opening

Check logs:

```bash
docker logs n8n
```

Also verify Docker Desktop is running.

---

## Security Notes

- Never commit Facebook access tokens, app secrets, Google credentials, database passwords, or API keys to this repository.
- Store external service credentials inside n8n Credentials or local environment variables.
- Keep the `n8n_data` volume private because it contains sensitive n8n application data.
- This setup is intended primarily for local development. Use HTTPS, proper authentication, backups, and production-grade infrastructure when hosting n8n publicly.

## Official Documentation

- n8n documentation: https://docs.n8n.io/
- n8n Docker image: https://docker.n8n.io/
- Docker documentation: https://docs.docker.com/
