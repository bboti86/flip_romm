# SpruceOS RomM Integration (`flip_romm`)

This is a self-contained, native SpruceOS application built with PySDL2 for the Miyoo Flip and similar retro gaming handhelds. It integrates local device favorites with a self-hosted **RomM** instance.

## Current Features

*   **Settings Management**: Store server endpoints and authorization credentials.
*   **Targeted Syncing**: Launch automated RomM-to-favorites procedures by targeting selective playlists. 
*   **Flexible Scanning**: Resolves relative nested structures effectively.
*   **Device Safeguards**: Provides quick rollback recovery points.

## Installation

1.  Copy components into `/mnt/SDCARD/App/flip_romm/`
2.  Fill your ROMM instance details in settings.json.
    *   `url`: Your RomM server URL (e.g., `http://[IP_ADDRESS]`).
    *   `api_key`: Your RomM API key.
3.  Launch it via the SpruceOS App menu.

## API Integration

Requires an authorization token configured inside standard settings menus.

## TODO

* [ ] Generate a new, tailored application icon (currently using inverted placeholders).
* [ ] Single game sync capabilities.
* [ ] Device-to-RomM local uploads.
* [ ] Bi-directional parity conflict checks.
* [ ] True binary ROM payload transfers.
* [ ] Saved progression mirroring.
* [ ] Cross-compatible OnionOS deployments. 
