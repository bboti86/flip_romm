import sdl2
import threading
import os
from core.romm_api import romm_api
from core.favorites_matcher import favorites_matcher
import core.input
import logging

logger = logging.getLogger(__name__)
from ui.components import render_text, render_text_shadow

class SyncScreen:
    def __init__(self, renderer, font, collection_id=None):
        self.renderer = renderer
        self.font = font
        self.collection_id = collection_id
        self.status = "Initializing..."
        self.done = False
        self.error = None
        
        threading.Thread(target=self._run_sync, daemon=True).start()

    def _run_sync(self):
        try:
            # Fetch platforms to get fs_slugs
            platforms = romm_api._make_request("/platforms")
            platform_slugs = {}
            if platforms:
                for p in platforms:
                    platform_slugs[p['id']] = p.get('fs_slug', '').lower()

            target_games = {} # basename -> set of allowed systems
            
            slug_to_spruce = {
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
            
            def add_target(game_name, plat_id):
                if not game_name: return
                basename = game_name.lower().strip()
                if basename not in target_games:
                    target_games[basename] = set()
                
                slug = platform_slugs.get(plat_id, "")
                if slug in slug_to_spruce:
                    target_games[basename].update([s.upper() for s in slug_to_spruce[slug]])
                elif slug:
                    target_games[basename].add(slug.upper())

            if self.collection_id:
                self.status = f"Fetching ROMs for Collection {self.collection_id}..."
                roms = romm_api.get_roms_by_collection(self.collection_id)
                if roms:
                    for rom in roms:
                        plat_id = rom.get('platform_id')
                        if rom.get('name'):
                            add_target(rom['name'], plat_id)
                        if rom.get('files'):
                            for f in rom['files']:
                                if f.get('file_name'):
                                    add_target(os.path.splitext(f['file_name'])[0], plat_id)
            else:
                self.status = "Fetching Collections..."
                collections = romm_api.get_collections()
                if not collections:
                    self.error = "No collections found or API error."
                    return
    
                self.status = "Fetching ROMs from Collections..."
                for coll in collections:
                    roms = romm_api.get_roms_by_collection(coll.get('id'))
                    if roms:
                        for rom in roms:
                            plat_id = rom.get('platform_id')
                            if rom.get('name'):
                                add_target(rom['name'], plat_id)
                            if rom.get('files'):
                                for f in rom['files']:
                                    if f.get('file_name'):
                                        add_target(os.path.splitext(f['file_name'])[0], plat_id)
            
            if not target_games:
                self.error = "No games found in collections."
                return
                
            self.status = "Scanning SD Card Roms folder(s)..."
            
            possible_rom_dirs = [
                "/media/sdcard0/Roms",
                "/media/sdcard1/Roms"
            ]
            valid_dirs = []
            seen_stats = set()
            for d in possible_rom_dirs:
                if os.path.exists(d):
                    try:
                        st = os.stat(d)
                        key = (st.st_dev, st.st_ino)
                        if key not in seen_stats:
                            seen_stats.add(key)
                            valid_dirs.append(d)
                    except OSError:
                        pass
                        
            if not valid_dirs:
                valid_dirs = ["."]
                
            found_matches = []
            logger.info(f"Target games to sync: {target_games}")
            
            for rom_dir in valid_dirs:
                logger.info(f"Scanning base directory: {rom_dir}")
                for root, dirs, files in os.walk(rom_dir):
                    # Skip hidden directories and media folders
                    dirs[:] = [d for d in dirs if not d.startswith('.') and d.lower() not in ('imgs', 'manuals', 'videos', 'snaps', 'boxarts', 'media', 'images', 'titles')]
                    
                    for file in files:
                        if file.startswith('.'):
                            continue
                            
                        ext = os.path.splitext(file)[1].lower()
                        if ext in ('.qoi', '.png', '.jpg', '.jpeg', '.pdf', '.txt', '.xml', '.dat'):
                            continue
                            
                        basename = os.path.splitext(file)[0].lower().strip()
                        
                        if basename in target_games:
                            allowed_systems = target_games[basename]
                            
                            rel_path = os.path.relpath(root, rom_dir)
                            system_name = rel_path.split(os.sep)[0]
                            if system_name == '.' or system_name == '':
                                system_name = "Unknown"
                                
                            if allowed_systems and system_name.upper() not in allowed_systems:
                                continue
                                
                            full_path = os.path.join(root, file)
                            display_name = os.path.splitext(file)[0]
                            
                            found_matches.append({
                                "rom_file_path": full_path,
                                "game_system_name": system_name,
                                "display_name": display_name
                            })
                            logger.info(f"Found match: {full_path} in system {system_name}")
            
            self.status = f"Found {len(found_matches)} matches. Saving..."
            
            if found_matches:
                existing_favs = favorites_matcher.load_local_favorites()
                existing_paths = {f.get('rom_file_path') for f in existing_favs}
                new_adds = [f for f in found_matches if f['rom_file_path'] not in existing_paths]
                
                if new_adds:
                    for item in new_adds:
                        logger.info(f"Adding new favorite to pyui-favorites.json: {item['rom_file_path']}")
                    existing_favs.extend(new_adds)
                    success = favorites_matcher.save_local_favorites(existing_favs)
                    if success:
                        self.status = f"Added {len(new_adds)} new favorites! (Total: {len(existing_favs)})"
                    else:
                        self.error = "Failed to save favorites file."
                else:
                    self.status = "All matching games are already in favorites."
            else:
                self.status = "No matches found on SD card."
                
        except Exception as e:
            self.error = f"Error during sync: {e}"
        finally:
            self.done = True

    def handle_event(self, event):
        action = core.input.map_event(event)
        if not action: return None
        
        if self.done or self.error:
            if action == "CANCEL" or action == "ACCEPT":
                return "SWITCH_TO_SETTINGS"
        return None

    def draw(self):
        render_text_shadow(self.renderer, self.font, "Sync Collections to Favorites", 320, 20, (0, 255, 150), center=True)
        
        if self.error:
            render_text(self.renderer, self.font, "SYNC ERROR", 320, 200, (255, 100, 100), center=True)
            err_msg = self.error if len(self.error) < 60 else self.error[:57] + "..."
            render_text(self.renderer, self.font, err_msg, 320, 240, (255, 200, 200), center=True)
        else:
            render_text(self.renderer, self.font, self.status, 320, 240, (200, 255, 200), center=True)
            
        if self.done or self.error:
            render_text(self.renderer, self.font, "Press A or B to return", 320, 440, (150, 150, 150), center=True)
