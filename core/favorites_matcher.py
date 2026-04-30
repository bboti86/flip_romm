import json
import os
import shutil

FAVORITES_FILE = "/mnt/SDCARD/Saves/pyui-favorites.json" # Default location in SpruceOS

class FavoritesMatcher:
    def __init__(self):
        self.local_favorites = []
        self.romm_roms = []

    def load_local_favorites(self):
        """Load favorites from SpruceOS."""
        # For testing locally, fallback to relative path if absolute doesn't exist
        file_path = FAVORITES_FILE
        if not os.path.exists(file_path):
            file_path = "pyui-favorites.json"
            
        if not os.path.exists(file_path):
            print(f"Warning: Favorites file {file_path} not found.")
            self.local_favorites = []
            return self.local_favorites
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.local_favorites = json.load(f)
        except Exception as e:
            print(f"Error loading favorites: {e}")
            self.local_favorites = []
            
        return self.local_favorites

    def set_romm_roms(self, roms):
        """Set the ROMs fetched from RomM API."""
        self.romm_roms = roms

    def get_matches(self):
        """
        Match local favorites against RomM roms.
        Returns a list of dictionaries with matching status.
        """
        results = []
        
        # Create a lookup dictionary for RomM ROMs
        # Try matching by name (case-insensitive)
        romm_lookup = {}
        for rom in self.romm_roms:
            if 'name' in rom and rom['name']:
                name_key = rom['name'].lower().strip()
                romm_lookup[name_key] = rom
            
            # If the API returns files, we could also index by file name
            if 'files' in rom and rom['files']:
                for f in rom['files']:
                    if 'file_name' in f and f['file_name']:
                        # Remove extension for matching
                        basename = os.path.splitext(f['file_name'])[0].lower().strip()
                        romm_lookup[basename] = rom
                        
        for fav in self.local_favorites:
            display_name = fav.get('display_name', '')
            if not display_name:
                continue
                
            match_key = display_name.lower().strip()
            
            is_matched = match_key in romm_lookup
            romm_rom = romm_lookup.get(match_key)
            
            results.append({
                'local_name': display_name,
                'system': fav.get('game_system_name', ''),
                'path': fav.get('rom_file_path', ''),
                'is_matched': is_matched,
                'romm_id': romm_rom['id'] if romm_rom else None,
                'romm_name': romm_rom['name'] if romm_rom else None
            })
            
        return results

    def save_local_favorites(self, favorites):
        """Save favorites and create a backup of the current file."""
        file_path = FAVORITES_FILE
        if not os.path.exists(os.path.dirname(file_path)) and file_path.startswith("/mnt/SDCARD"):
            file_path = "pyui-favorites.json"
            
        # Create backup if the file exists
        if os.path.exists(file_path):
            try:
                shutil.copy2(file_path, file_path + ".bak")
            except Exception as e:
                print(f"Error creating backup: {e}")
                
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(favorites, f, indent=4)
            self.local_favorites = favorites
            return True
        except Exception as e:
            print(f"Error saving favorites: {e}")
            return False
            
    def restore_favorites_backup(self):
        """Restore favorites from the backup file."""
        file_path = FAVORITES_FILE
        if not os.path.exists(os.path.dirname(file_path)) and file_path.startswith("/mnt/SDCARD"):
            file_path = "pyui-favorites.json"
            
        bak_path = file_path + ".bak"
        if os.path.exists(bak_path):
            try:
                shutil.copy2(bak_path, file_path)
                self.load_local_favorites()
                return True, "Backup restored successfully."
            except Exception as e:
                return False, f"Error restoring backup: {e}"
        return False, "No backup file found."

    def add_single_favorite(self, display_name, system_name, rom_path):
        """Add a single game to SpruceOS favorites."""
        favs = self.load_local_favorites()
        
        # Check if already exists to avoid duplicates
        for f in favs:
            if f.get('rom_file_path') == rom_path:
                return True, "Already in favorites"
                
        new_fav = {
            "display_name": display_name,
            "game_system_name": system_name,
            "rom_file_path": rom_path
        }
        favs.append(new_fav)
        if self.save_local_favorites(favs):
            return True, "Added to favorites"
        else:
            return False, "Failed to save favorites"

favorites_matcher = FavoritesMatcher()
