import sdl2
import threading
import os
import time
from core.romm_api import romm_api
from core.favorites_matcher import favorites_matcher
import core.input
from core.logger import setup_logger
from ui.components import render_text, render_text_shadow, draw_panel

logger = setup_logger("sync")

class SyncScreen:
    def __init__(self, renderer, font, collection=None):
        self.renderer = renderer
        self.font = font
        self.collection = collection
        self.collection_id = collection.get('id') if collection else None
        self.status = "Initializing..."
        self.progress_text = ""
        self.done = False
        self.error = None
        
        # State tracking
        self.roms = []
        self.missing_roms = []
        self.local_found = [] # List of (rom, path, system)
        self.total_size = 0
        
        self.awaiting_confirmation = False
        self.downloading = False
        self.current_dl_idx = 0
        self.current_dl_progress = 0
        
        # Mapping
        self.slug_to_spruce = {
            "nes": ["FC", "NES"],
            "snes": ["SFC", "SNES"],
            "gb": ["GB"],
            "gbc": ["GBC"],
            "gba": ["GBA"],
            "genesis": ["MD", "GENESIS", "MEGADRIVE"],
            "megadrive": ["MD", "GENESIS", "MEGADRIVE"],
            "game-gear": ["GG", "GAMEGEAR"],
            "gg": ["GG", "GAMEGEAR"],
            "master-system": ["MS", "MASTERSYSTEM"],
            "ms": ["MS"],
            "n64": ["N64"],
            "nintendo-64": ["N64"],
            "ps1": ["PS", "PSX", "PS1"],
            "psx": ["PS", "PSX", "PS1"],
            "playstation": ["PS", "PSX", "PS1"],
            "psp": ["PSP"],
            "arcade": ["ARCADE", "MAME", "FBA", "NEOGEO", "FBNEO", "CPS1", "CPS2", "CPS3"],
            "mame": ["ARCADE", "MAME", "FBA", "NEOGEO", "FBNEO", "CPS1", "CPS2", "CPS3"],
            "pce": ["PCE", "TG16"],
            "pcecd": ["PCECD"],
            "segacd": ["SCD", "SEGACD"],
            "scd": ["SCD", "SEGACD"],
        }
        
        threading.Thread(target=self._prepare_sync, daemon=True).start()

    def normalize(self, s):
        if not s: return ""
        for char in ":!?-_.()[]":
            s = s.replace(char, " ")
        return " ".join(s.split()).lower()

    def _prepare_sync(self):
        try:
            self.status = "Fetching platform data..."
            platforms = romm_api._make_request("/platforms")
            platform_slugs = {p['id']: p.get('fs_slug', '').lower() for p in platforms} if platforms else {}

            if self.collection_id:
                self.status = "Fetching Collection ROMs..."
                self.roms = romm_api.get_roms_by_collection(self.collection_id)
            else:
                self.status = "Fetching all Collections..."
                colls = romm_api.get_collections()
                all_roms = []
                for c in colls:
                    roms = romm_api.get_roms_by_collection(c.get('id'))
                    if roms: all_roms.extend(roms)
                # Deduplicate by ID
                seen_ids = set()
                self.roms = []
                for r in all_roms:
                    if r['id'] not in seen_ids:
                        self.roms.append(r)
                        seen_ids.add(r['id'])

            if not self.roms:
                self.error = "No ROMs found to sync."
                self.done = True
                return

            self.status = "Scanning SD Card(s)..."
            possible_dirs = ["/media/sdcard1/Roms", "/media/sdcard0/Roms", "/mnt/SDCARD/Roms"]
            valid_dirs = [d for d in possible_dirs if os.path.exists(d)]
            if not valid_dirs: valid_dirs = ["."]

            # Build target map for faster matching
            # Map normalized names to list of (rom, target_systems)
            target_map = {}
            for rom in self.roms:
                plat_id = rom.get('platform_id')
                slug = platform_slugs.get(plat_id, "")
                target_systems = self.slug_to_spruce.get(slug, [slug.upper() if slug else "UNKNOWN"])
                
                names_to_check = [rom.get('name')]
                for f in rom.get('files', []):
                    if f.get('file_name'):
                        names_to_check.append(os.path.splitext(f['file_name'])[0])
                
                for name in names_to_check:
                    norm = self.normalize(name)
                    if norm:
                        if norm not in target_map: target_map[norm] = []
                        target_map[norm].append((rom, target_systems, name))

            found_rom_ids = set()
            
            for rom_dir in valid_dirs:
                for root, dirs, files in os.walk(rom_dir):
                    # Skip junk
                    dirs[:] = [d for d in dirs if not d.startswith('.') and d.lower() not in ('imgs', 'manuals', 'videos', 'snaps', 'boxarts', 'media', 'images', 'titles')]
                    
                    rel_path = os.path.relpath(root, rom_dir)
                    current_system = rel_path.split(os.sep)[0].upper()
                    if current_system == '.' or not current_system: current_system = "UNKNOWN"

                    for f in files:
                        if f.startswith('.'): continue
                        ext = os.path.splitext(f)[1].lower()
                        if ext in ('.qoi', '.png', '.jpg', '.jpeg', '.pdf', '.txt', '.xml', '.dat'): continue
                        
                        fname_no_ext = os.path.splitext(f)[0]
                        norm_f = self.normalize(fname_no_ext)
                        
                        # Match logic
                        match_rom = None
                        
                        # 1. Exact normalized match
                        if norm_f in target_map:
                            for rom, systems, orig_name in target_map[norm_f]:
                                if current_system in systems or "UNKNOWN" in systems:
                                    match_rom = rom
                                    break
                        
                        # 2. Fuzzy normalized match (contains)
                        if not match_rom:
                            for norm_target, rom_list in target_map.items():
                                # Check if one is a subset of the other (e.g. "Brain Drain" vs "Brain Drain (SGB)")
                                # Require a minimum length to avoid false positives with very short names
                                if (norm_target in norm_f or norm_f in norm_target) and len(norm_target) >= 6:
                                    for rom, systems, orig_name in rom_list:
                                        if current_system in systems or "UNKNOWN" in systems:
                                            match_rom = rom
                                            break
                                if match_rom: break

                        if match_rom and match_rom['id'] not in found_rom_ids:
                            self.local_found.append((match_rom, os.path.join(root, f), current_system))
                            found_rom_ids.add(match_rom['id'])
                            logger.info(f"Matched local: {f} -> {match_rom.get('name')}")

            # Identify missing
            self.missing_roms = [r for r in self.roms if r['id'] not in found_rom_ids]
            self.total_size = sum(r.get('size', 0) for r in self.missing_roms)
            
            if not self.missing_roms:
                self.status = "All games are local. Proceeding to favorites sync..."
                self._execute_sync()
            else:
                self.status = f"Found {len(self.missing_roms)} missing games."
                self.awaiting_confirmation = True

        except Exception as e:
            err_msg = re.sub(r' +', ' ', str(e).replace('\n', ' '))
            logger.error(f"Prepare sync error: {err_msg}")
            self.error = str(e)
            self.done = True

    def _execute_sync(self):
        try:
            # 1. Add existing locals to favorites
            self.status = "Favoriting existing games..."
            existing_favs = favorites_matcher.load_local_favorites()
            existing_paths = {f.get('rom_file_path') for f in existing_favs}
            
            added_count = 0
            for rom, path, system in self.local_found:
                if path not in existing_paths:
                    display_name = self._get_clean_name(rom)
                    existing_favs.append({
                        "rom_file_path": path,
                        "game_system_name": system,
                        "display_name": display_name
                    })
                    added_count += 1
            
            if added_count > 0:
                favorites_matcher.save_local_favorites(existing_favs)
                logger.info(f"Added {added_count} existing games to favorites.")

            # 2. Download missing if confirmed
            if self.downloading:
                # Pre-fetch platforms to avoid loop requests
                platforms = romm_api._make_request("/platforms")
                platform_slugs = {p['id']: p.get('fs_slug', '').lower() for p in platforms} if platforms else {}

                for i, rom in enumerate(self.missing_roms):
                    self.current_dl_idx = i + 1
                    self.status = f"Downloading {i+1}/{len(self.missing_roms)}..."
                    self.progress_text = rom.get('name', 'Unknown')
                    
                    target_base = "/media/sdcard1/Roms"
                    if not os.path.exists(target_base): target_base = "/media/sdcard0/Roms"
                    
                    plat_id = rom.get('platform_id')
                    slug = platform_slugs.get(plat_id, "")
                    systems = self.slug_to_spruce.get(slug, [slug.upper() if slug else "UNKNOWN"])
                    system_folder = systems[0]
                    
                    target_dir = os.path.join(target_base, system_folder)
                    os.makedirs(target_dir, exist_ok=True)
                    
                    filename = rom.get('fs_name')
                    if not filename and rom.get('files'): filename = rom['files'][0].get('file_name')
                    if not filename: filename = f"{rom.get('name')}.zip"
                    
                    dest_path = os.path.join(target_dir, filename)
                    
                    def prog_cb(downloaded, total):
                        if total > 0:
                            self.current_dl_progress = int((downloaded / total) * 100)
                        else:
                            self.current_dl_progress = 0
                    
                    success, msg = romm_api.download_rom(rom['id'], dest_path, progress_callback=prog_cb)
                    if success:
                        existing_favs = favorites_matcher.load_local_favorites()
                        if dest_path not in {f.get('rom_file_path') for f in existing_favs}:
                            existing_favs.append({
                                "rom_file_path": dest_path,
                                "game_system_name": system_folder,
                                "display_name": self._get_clean_name(rom)
                            })
                            favorites_matcher.save_local_favorites(existing_favs)
                    else:
                        logger.error(f"Failed to download {rom.get('name')}: {msg}")

            self.status = "Sync Complete!"
            self.progress_text = ""
            self.done = True
        except Exception as e:
            logger.error(f"Execute sync error: {e}")
            self.error = str(e)
            self.done = True

    def _get_clean_name(self, rom):
        if not rom: return "Unknown Game"
        for source in ['igdb_metadata', 'ss_metadata', 'steam_metadata']:
            meta = rom.get(source)
            if meta and isinstance(meta, dict) and meta.get('name'):
                return meta['name']
        name = rom.get('name')
        if not name and rom.get('files'):
            name = rom['files'][0].get('file_name')
        if not name: name = "Unknown Game"
        for junk in ['.zip', '.7z', '.nes', '.sfc', '.smc', '.gb', '.gbc', '.gba', '.bin', '.iso', '.md', '.gen', '.sms', '.gg']:
            if name.lower().endswith(junk):
                name = name[:-len(junk)]
        import re
        name = re.sub(r'\s*[\(\[].*?[\)\]]', '', name)
        
        return name.strip()

    def _is_fav(self, rom):
        """Robust favorite check against multiple variants and paths."""
        if not rom: return False
        
        # 1. Check by path (most reliable)
        _, _, target_path = self._get_target_paths(rom)
        if target_path:
            target_path_lower = target_path.lower()
            for f in favorites_matcher.local_favorites:
                f_path = f.get('rom_file_path')
                if f_path and f_path.lower() == target_path_lower:
                    return True

        # 2. Check clean name (metadata preferred)
        clean_name = self._get_clean_name(rom).lower().strip()
        if clean_name in self.fav_names: return True
        
        # 3. Check RomM internal name variants
        rom_name = rom.get('name', '').lower().strip()
        if rom_name in self.fav_names: return True
        
        import re
        stripped_name = re.sub(r'\s*[\(\[].*?[\)\]]', '', rom.get('name', '')).lower().strip()
        if stripped_name in self.fav_names: return True
        
        return False

    def handle_event(self, event):
        action = core.input.map_event(event)
        if not action: return None
        
        if self.awaiting_confirmation:
            if action == "ACCEPT":
                self.awaiting_confirmation = False
                self.downloading = True
                threading.Thread(target=self._execute_sync, daemon=True).start()
            elif action == "CANCEL":
                # Only sync local, no downloads
                self.awaiting_confirmation = False
                self.downloading = False
                threading.Thread(target=self._execute_sync, daemon=True).start()
            return None

        if self.done or self.error:
            if action == "CANCEL" or action == "ACCEPT":
                if self.collection:
                    return ("SWITCH_TO_COLLECTION_GAMES", self.collection)
                return "SWITCH_TO_SETTINGS"
        return None

    def draw(self):
        render_text_shadow(self.renderer, self.font, "Collection Sync", 320, 40, (100, 200, 255), center=True)
        
        if self.awaiting_confirmation:
            draw_panel(self.renderer, 100, 150, 440, 200, bg_color=(30, 30, 50, 240))
            render_text(self.renderer, self.font, "Download Missing Games?", 320, 180, (255, 255, 255), center=True)
            
            size_mb = self.total_size / (1024 * 1024)
            info = f"Total: {len(self.missing_roms)} games ({size_mb:.1f} MB)"
            render_text(self.renderer, self.font, info, 320, 220, (200, 200, 200), center=True)
            
            render_text(self.renderer, self.font, "A: Download All | B: Sync Local Only", 320, 300, (150, 255, 150), center=True)
            return

        if self.error:
            render_text(self.renderer, self.font, "ERROR", 320, 200, (255, 100, 100), center=True)
            render_text(self.renderer, self.font, self.error[:60], 320, 240, (255, 200, 200), center=True)
        else:
            render_text(self.renderer, self.font, self.status, 320, 200, (200, 255, 200), center=True)
            if self.progress_text:
                render_text(self.renderer, self.font, self.progress_text, 320, 240, (255, 255, 255), center=True)
                
                # Progress bar
                draw_panel(self.renderer, 120, 280, 400, 20, bg_color=(50, 50, 50))
                draw_panel(self.renderer, 120, 280, int(400 * (self.current_dl_progress/100)), 20, bg_color=(100, 255, 100))

        if self.done or self.error:
            render_text(self.renderer, self.font, "Press A or B to return", 320, 440, (150, 150, 150), center=True)
