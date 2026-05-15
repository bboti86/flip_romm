import os
import json
import re
from .romm_api import romm_api
from .favorites_matcher import favorites_matcher

SCREENSHOT_DIR = "/mnt/SDCARD/Saves/screenshots"
SYNC_CACHE_FILE = "screenshot_sync.json"

class ScreenshotManager:
    def __init__(self):
        self.pending_screenshots = []
        self.synced_files = self._load_sync_cache()

    def _load_sync_cache(self):
        if os.path.exists(SYNC_CACHE_FILE):
            try:
                with open(SYNC_CACHE_FILE, 'r') as f:
                    return set(json.load(f))
            except:
                pass
        return set()

    def _save_sync_cache(self):
        try:
            with open(SYNC_CACHE_FILE, 'w') as f:
                json.dump(list(self.synced_files), f)
        except:
            pass

    def scan_screenshots(self):
        """Scan the device for new screenshots and match them to RomM ROMs."""
        self.pending_screenshots = []
        
        # 1. Ensure favorites are loaded
        favs = favorites_matcher.load_local_favorites()
        
        # 2. Ensure RomM ROMs are loaded (from cache if possible)
        all_roms = romm_api.get_all_roms(use_cache=True)
        favorites_matcher.set_romm_roms(all_roms)
        
        # 3. Get matched favorites (they have the rom_id mapping)
        matched_favs = favorites_matcher.get_matches()
        
        # Create a lookup map: normalized_name -> rom_id
        name_to_rom_id = {}
        for fav in matched_favs:
            if fav['is_matched'] and fav['romm_id']:
                norm_name = favorites_matcher.normalize(fav['local_name'])
                name_to_rom_id[norm_name] = fav['romm_id']

        print(f"DEBUG: Screenshot scan found {len(name_to_rom_id)} matched favorites to check against.")

        if not os.path.exists(SCREENSHOT_DIR):
            print(f"DEBUG: Screenshot directory {SCREENSHOT_DIR} not found.")
            # Fallback for testing
            if os.path.exists("screenshots"):
                scan_path = "screenshots"
            else:
                return []
        else:
            scan_path = SCREENSHOT_DIR

        try:
            files = os.listdir(scan_path)
            print(f"DEBUG: Scanning {len(files)} files in {scan_path}...")
        except Exception as e:
            print(f"DEBUG: Error listing directory {scan_path}: {e}")
            return []

        for filename in files:
            if not filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                continue
            
            if filename in self.synced_files:
                continue

            # 2. Parse filename
            game_name = filename
            if "-cheevo-" in filename:
                game_name = filename.split("-cheevo-")[0]
            else:
                game_name = re.sub(r'-\d{6,}.*$', '', filename.split('.')[0])

            norm_game_name = favorites_matcher.normalize(game_name)
            rom_id = name_to_rom_id.get(norm_game_name)
            
            if rom_id:
                print(f"DEBUG: Matched screenshot {filename} to ROM ID {rom_id}")
                self.pending_screenshots.append({
                    'filename': filename,
                    'full_path': os.path.join(scan_path, filename),
                    'game_name': game_name,
                    'rom_id': rom_id
                })
            else:
                # Log failures to help debug normalization issues
                print(f"DEBUG: No match for {filename} (Normalized: {norm_game_name})")

        return self.pending_screenshots

    def upload_screenshot(self, screenshot_item):
        """Upload a single screenshot to RomM."""
        filename = screenshot_item['filename']
        rom_id = screenshot_item['rom_id']
        file_path = screenshot_item['full_path']
        
        result = romm_api.upload_screenshot(rom_id, file_path)
        if result:
            self.synced_files.add(filename)
            self._save_sync_cache()
            return True
        return False

screenshot_manager = ScreenshotManager()
