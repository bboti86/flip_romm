# RomM Collection Creator

A standalone, dockerized Next.js web application designed to automate the creation of RomM game collections. It allows you to paste a plain text list of games (e.g., from a top 100 list or a forum post), and it automatically fuzzy-matches those games against your RomM library and creates a collection for you.

## Features

- **Bulk Collection Generation**: Paste a list of game titles (one per line) and hit create.
- **Fuzzy Matching Logic**: Automatically ignores console tags in parentheses (e.g., `Adventure (Atari 2600)` becomes `Adventure`) and matches against your RomM library regardless of case or minor punctuation differences.
- **Missing ROM Identification**: Displays a clear summary of which games were successfully linked to your library and which games are missing.
- **Premium UI**: Designed with a clean, dark-mode glassmorphism interface.
- **Lightweight & Containerized**: Built using Next.js standalone output, making the docker image highly optimized.

## Deployment

This app is designed to run via Docker alongside your existing RomM instance.

1. Configure your environment variables in `docker-compose.yaml` (or via an `.env` file):
   ```yaml
   environment:
     - ROMM_URL=http://your-romm-url:8080
     - ROMM_API_KEY=your_romm_api_key
   ```
   *Note: Ensure your API key has the necessary write permissions in RomM to create collections and modify ROMs.*

2. Build and start the container:
   ```bash
   docker compose up -d --build
   ```

3. Access the web interface at `http://localhost:3000`.

## Tech Stack

- **Framework**: Next.js (App Router, React)
- **Styling**: Vanilla CSS (CSS Variables, Glassmorphism)
- **Backend API**: Next.js API Routes (`/api/collections/create`)
- **Deployment**: Docker & Docker Compose
