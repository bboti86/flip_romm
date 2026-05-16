import json
import os
import shutil

FAVORITES_FILE = "/mnt/SDCARD/Saves/pyui-favorites.json" # Default location in SpruceOS
COLLECTIONS_FILE = "/media/sdcard0/Collections/collections.json"

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

    def normalize(self, s):
        """Standardize strings for fuzzy matching with unicode support."""
        if not s: return ""
        import re
        import unicodedata
        
        # 1. Unicode normalization (convert ä to a, etc.)
        s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')
        
        # 2. Handle common variations (ae -> a, etc. for some matches)
        s = s.replace('ae', 'a').replace('oe', 'o').replace('ue', 'u')
        
        # 3. Remove common prefixes and suffixes
        s = re.sub(r"^(Disney's|Marvel's|The|A|An)\s+", "", s, flags=re.IGNORECASE)
        s = re.sub(r",\s+(The|A|An)$", "", s, flags=re.IGNORECASE)
        
        # 4. Remove region tags and brackets
        s = re.sub(r'\s*[\(\[].*?[\)\]]', '', s)
        
        # 5. Remove ALL non-alphanumeric characters (keep only letters, numbers, and spaces)
        s = re.sub(r'[^a-zA-Z0-9\s]', ' ', s)
        
        # 6. Lowercase and collapse whitespace
        return " ".join(s.lower().split())

    def get_local_zip_crc(self, file_path):
        """Get the CRC of the first file in a ZIP without extracting."""
        if not file_path or not file_path.lower().endswith('.zip'):
            return None
        import zipfile
        try:
            with zipfile.ZipFile(file_path, 'r') as z:
                infos = z.infolist()
                if infos:
                    # Return CRC as hex string, lowercased
                    return hex(infos[0].CRC & 0xFFFFFFFF)[2:].zfill(8).lower()
        except Exception as e:
            print(f"Error reading ZIP CRC for {file_path}: {e}")
        return None

    def get_matches(self):
        """
        Match local favorites against RomM roms using name normalization and CRC.
        """
        results = []
        
        # Create lookup dictionaries for RomM ROMs
        romm_name_lookup = {}
        romm_crc_lookup = {}
        
        for rom in self.romm_roms:
            # 1. Index by names
            if 'name' in rom and rom['name']:
                romm_name_lookup[rom['name'].lower().strip()] = rom
                romm_name_lookup[self.normalize(rom['name'])] = rom
            
            # 2. Index by filenames
            if 'files' in rom and rom['files']:
                for f in rom['files']:
                    if 'file_name' in f and f['file_name']:
                        basename = os.path.splitext(f['file_name'])[0]
                        romm_name_lookup[basename.lower().strip()] = rom
                        romm_name_lookup[self.normalize(basename)] = rom
                    
                    # 3. Index by CRC
                    if 'crc_hash' in f and f['crc_hash']:
                        crc = f['crc_hash'].lower().strip()
                        romm_crc_lookup[crc] = rom
            
            # Global CRC if available
            if 'crc_hash' in rom and rom['crc_hash']:
                romm_crc_lookup[rom['crc_hash'].lower().strip()] = rom
                        
        for fav in self.local_favorites:
            display_name = fav.get('display_name', '')
            rom_path = fav.get('rom_file_path', '')
            if not display_name:
                continue
            
            romm_rom = None
            
            # Strategy 1: CRC Matching (High precision, for ZIPs)
            local_crc = self.get_local_zip_crc(rom_path)
            if local_crc:
                romm_rom = romm_crc_lookup.get(local_crc)
            
            # Strategy 2: Improved Name Normalization
            if not romm_rom:
                match_key_exact = display_name.lower().strip()
                match_key_norm = self.normalize(display_name)
                romm_rom = romm_name_lookup.get(match_key_exact) or romm_name_lookup.get(match_key_norm)
            
            is_matched = romm_rom is not None
            
            results.append({
                'local_name': display_name,
                'system': fav.get('game_system_name', ''),
                'path': rom_path,
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
            
    def load_collections(self):
        """Load SpruceOS collections."""
        file_path = COLLECTIONS_FILE
        if not os.path.exists(file_path):
            # Fallback for PC testing: check if absolute path directory exists
            # If not, check for local file in current directory
            dir_name = os.path.dirname(file_path)
            if dir_name and not os.path.exists(dir_name):
                file_path = os.path.basename(file_path)
            elif not dir_name:
                pass # Already a relative path
        
        if not os.path.exists(file_path):
            return []
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading collections: {e}")
            return []

    def save_collections(self, collections):
        """Save SpruceOS collections."""
        file_path = COLLECTIONS_FILE
        dir_name = os.path.dirname(file_path)
        if dir_name and not os.path.exists(dir_name):
            file_path = os.path.basename(file_path)
            
        try:
            # Create backup
            if os.path.exists(file_path):
                shutil.copy2(file_path, file_path + ".bak")
                
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(collections, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving collections: {e}")
            return False

    def add_to_collection(self, collection_name, rom_file_path, system_name):
        """Add a game to a specific SpruceOS collection."""
        collections = self.load_collections()
        
        target_coll = None
        for coll in collections:
            if coll.get('collection_name') == collection_name:
                target_coll = coll
                break
        
        if not target_coll:
            target_coll = {
                "collection_name": collection_name,
                "game_list": []
            }
            collections.append(target_coll)
            
        # Check if already in list
        for game in target_coll['game_list']:
            if game.get('rom_file_path') == rom_file_path:
                return True # Already exists
                
        target_coll['game_list'].append({
            "rom_file_path": rom_file_path,
            "game_system_name": system_name
        })
        
        return self.save_collections(collections)
            
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

    def get_matched_rom_ids(self):
        """Return a unique list of RomM IDs for currently matched favorites."""
        matches = self.get_matches()
        rom_ids = []
        for m in matches:
            if m['is_matched'] and m['romm_id']:
                rom_ids.append(m['romm_id'])
        return list(set(rom_ids))

favorites_matcher = FavoritesMatcher()
