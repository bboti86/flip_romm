# SpruceOS RomM Integration (`flip_romm`)

This is a self-contained, native SpruceOS application built with PySDL2 for the Miyoo Flip and similar retro gaming handhelds. It integrates local device favorites with a self-hosted **RomM** instance.

## Key Features

*   **Intelligent Bulk Sync**: 
    *   Automatically matches RomM collection items with local files using robust name normalization (stripping tags like `(USA)`, `[!]`, etc.).
    *   Identifies missing games and provides a total download size estimate.
    *   Sequentially downloads missing titles with real-time progress tracking.
*   **Favorite Synchronization**: 
    *   Automatically adds matched local games and newly downloaded games to the SpruceOS Favorites list (`pyui-favorites.json`).
    *   Uses path-based verification for 100% reliable favorite detection in the app.
*   **Backup & Recovery**:
    *   **Automatic Backups**: Every time the app writes to your favorites list, it creates a `pyui-favorites.json.bak` copy of the previous state.
    *   **Restore Function**: The "Restore Favorites" option in settings acts as a **one-step undo**, reverting the file to its state immediately before the last operation (e.g., before the last "Download All" sync).
*   **Quick Actions**:
    *   **Favorite (Y)**: Instantly add/remove the selected game from your device favorites.
    *   **Download (X)**: Download a single missing game directly from the metadata view.
    *   **Sync All (START)**: Synchronize an entire collection with a single button press.
*   **Remote Metadata Viewer**: View rich game details (descriptions, ratings, release info) with local existence tracking.
*   **Flexible Scanning**: Recursively searches across all SD card mount points (`/media/sdcard1`, `/media/sdcard0`, `/mnt/SDCARD`) and subfolders.

## Installation

1.  Unzip all files from the release zip into `/mnt/SDCARD/App/`
2.  Fill your RomM instance details in `settings.json`.
    *   `url`: Your RomM server URL (e.g., `http://[IP_ADDRESS]`).
    *   `api_key`: Your RomM API key.
3.  Launch it via the SpruceOS App menu.

## Controls

| Button | Action |
| :--- | :--- |
| **D-Pad** | Navigate lists |
| **A** | Select / Open metadata view |
| **B** | Back / Cancel |
| **X** | Download single game (from metadata view) |
| **Y** | Toggle Favorite (if game is local) |
| **START** | Trigger "Download All" Sync for current collection |
| **L2 / R2** | Page Up / Down in lists |

## Security Considerations

> [!CAUTION]
> Exposing your RomM server to the public internet (e.g. via port forwarding or insecure reverse proxies) poses severe privacy risks. Ensure standard protections (Tailscale VPNs, Zero Trust Tunnels) wrap your payloads safely. This application is recommended for use only on closed or personal networks. The author takes no responsibility for the use or misuse of this application.  

## API Integration

Requires an authorization token configured inside standard settings menus. The app connects directly to the RomM API and does not currently support secondary authentication layers (like Authelia or Cloudflare Access) without bypass rules.

## TODO

### 🟢 High Feasibility
* [x] Generate a tailored application icon.
* [x] **Remote Metadata Viewer**: Show ratings/descriptions on game list.
* [x] **Single game sync** capabilities.
* [x] **Collection-Based Downloads**: Bulk download targeted playlists.

### 🟡 Medium Feasibility
* [x] **Intelligent Syncing**: Download only missing ROM components.
* [ ] **Favorite Parity**: Push local favorites back to RomM.
* [ ] **Screenshot Uploader**: Push capture assets directly up to metadata logs.
* [ ] **BIOS Integrity Check**: Confirm local hash compliance routines.

### 🔴 Low / Complex Feasibility / Out of scope for now
* [ ] **Bi-directional Save Sync** & timestamped conflict handlers.
* [ ] **True binary payloads** and persistent queue managers.
* [ ] **Auto-Upload on Exit** via firmware wrapper scripts.
* [ ] **Playback State Sync**: Log time played counts securely.
* [ ] Cross-compatible **OnionOS deployments**. 
