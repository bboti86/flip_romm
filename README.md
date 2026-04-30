# SpruceOS RomM Integration (`flip_romm`)

This is a self-contained, native SpruceOS application built with PySDL2 for the Miyoo Flip and similar retro gaming handhelds. It integrates local device favorites with a self-hosted **RomM** instance.

## Current Features

*   **Settings Management**: Store server endpoints and authorization credentials.
*   **Targeted Syncing**: Launch automated RomM-to-favorites procedures by targeting selective playlists. 
*   **Remote Metadata Viewer**: View rich game details (descriptions, ratings, release info) with local existence tracking.
*   **Flexible Scanning**: Resolves relative nested structures effectively.
*   **Device Safeguards**: Provides quick rollback recovery points.

## Installation

1.  Copy components into `/mnt/SDCARD/App/flip_romm/`
2.  Fill your ROMM instance details in settings.json.
    *   `url`: Your RomM server URL (e.g., `http://[IP_ADDRESS]`).
    *   `api_key`: Your RomM API key.
3.  Launch it via the SpruceOS App menu.

## Security Considerations

> [!CAUTION]
> Exposing your RomM server to the public internet (e.g. via port forwarding or insecure reverse proxies) poses severe privacy risks. Ensure standard protections (Tailscale VPNs, Zero Trust Tunnels) wrap your payloads safely. This application is recommended for use only on closed or personal networks. The author takes no responsibility for the use or misuse of this application.  
Keep in mind, the app will not be able to connect over a VPN or behind a reverse proxy that uses forward-auth or similar authentication. It must be able to connect directly to your RomM server.

## API Integration

Requires an authorization token configured inside standard settings menus.

## TODO

### 🟢 High Feasibility
* [ ] Generate a tailored application icon.
* [x] **Remote Metadata Viewer**: Show ratings/descriptions on game list.
* [ ] **"Discovery" Mode**: Offer one-click installations of random remote titles.

### 🟡 Medium Feasibility
* [ ] **Single game sync** capabilities.
* [ ] **Collection-Based Downloads**: Bulk download targeted playlists.
* [ ] **Intelligent Syncing**: Download only missing ROM components.
* [ ] **Favorite Parity**: Bi-directional favorite flag propagation.
* [ ] **Screenshot Uploader**: Push capture assets directly up to metadata logs.
* [ ] **BIOS Integrity Check**: Confirm local hash compliance routines.

### 🔴 Low / Complex Feasibility / Out of scope for now
* [ ] **Bi-directional Save Sync** & timestamped conflict handlers.
* [ ] **True binary payloads** and persistent queue managers.
* [ ] **Auto-Upload on Exit** via firmware wrapper scripts.
* [ ] **QR-Based Pairing** for initial verification shortcuts.
* [ ] **Playback State Sync**: Log time played counts securely.
* [ ] Cross-compatible **OnionOS deployments**. 
* [ ] **Multi-User Profiles**: Simple toggle schemas handling credential swaps.
* [ ] **Remote Scan Trigger**: Prompt server updates from controls.

