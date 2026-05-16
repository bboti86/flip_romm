import sdl2
import threading
import os
import time
from core.romm_api import romm_api
from core.favorites_matcher import favorites_matcher
import core.input
from core.logger import setup_logger
from ui.components import render_text, render_text_shadow, draw_panel, draw_selector

logger = setup_logger("coll_dl")

class CollectionDownloadScreen:
    def __init__(self, renderer, font, collection):
        self.renderer = renderer
        self.font = font
        self.collection = collection
        self.collection_name = collection.get('name', 'Unknown')
        self.collection_id = collection.get('id')
        
        self.status = "Initializing..."
        self.progress_text = ""
        self.loading = True
        self.done = False
        self.error = None
        
        # Scan results
        self.roms = []
        self.found_local = [] # (rom, path, system)
        self.missing_roms = []
        self.total_dl_size = 0
        
        # State
        self.phase = "SCANNING" # SCANNING, SUMMARY, DOWNLOADING, DONE
        self.selected_idx = 0
        self.scroll_offset = 0
        self.items_per_page = 8
        
        self.download_idx = 0
        self.download_progress = 0
        
        # System mapping (same as SyncScreen)
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
        
        threading.Thread(target=self._run_scan, daemon=True).start()

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
        # Strip common tags
        import re
        name = re.sub(r'\s*[\(\[].*?[\)\]]', '', name)
        return name.strip()

    def _run_scan(self):
        try:
            self.status = "Fetching platform data..."
            platforms = romm_api.get_platforms()
            platform_slugs = {p['id']: p.get('fs_slug', '').lower() for p in platforms} if platforms else {}
            
            self.status = "Fetching Collection ROMs..."
            self.roms = romm_api.get_roms_by_collection(self.collection_id)
            if not self.roms:
                self.error = "No ROMs found in this collection."
                self.loading = False
                return

            self.status = "Scanning local storage..."
            possible_dirs = ["/media/sdcard1/Roms", "/media/sdcard0/Roms", "/mnt/SDCARD/Roms"]
            valid_dirs = [d for d in possible_dirs if os.path.exists(d)]
            
            # Use same fuzzy logic as SyncScreen
            found_ids = set()
            self.found_local = []
            self.missing_roms = []
            
            # Optimization: Build a map for fuzzy matching
            target_map = {}
            for rom in self.roms:
                plat_id = rom.get('platform_id')
                slug = platform_slugs.get(plat_id, "")
                target_systems = self.slug_to_spruce.get(slug, [slug.upper() if slug else "UNKNOWN"])
                
                names = [rom.get('name')]
                for f in rom.get('files', []):
                    if f.get('file_name'): names.append(os.path.splitext(f['file_name'])[0])
                
                for n in names:
                    norm = favorites_matcher.normalize(n)
                    if norm:
                        if norm not in target_map: target_map[norm] = []
                        target_map[norm].append((rom, target_systems))

            # Scan files
            for rom_dir in valid_dirs:
                for root, dirs, files in os.walk(rom_dir):
                    # Skip junk
                    dirs[:] = [d for d in dirs if not d.startswith('.') and d.lower() not in ('imgs', 'manuals', 'videos', 'snaps', 'boxarts', 'media', 'images', 'titles')]
                    
                    rel = os.path.relpath(root, rom_dir)
                    curr_sys = rel.split(os.sep)[0].upper()
                    
                    for f in files:
                        if f.startswith('.'): continue
                        ext = os.path.splitext(f)[1].lower()
                        if ext in ('.png', '.jpg', '.txt', '.xml'): continue
                        
                        fname = os.path.splitext(f)[0]
                        norm_f = favorites_matcher.normalize(fname)
                        
                        match = None
                        if norm_f in target_map:
                            for rom, systems in target_map[norm_f]:
                                if curr_sys in systems or "UNKNOWN" in systems:
                                    match = rom
                                    break
                        
                        if match and match['id'] not in found_ids:
                            self.found_local.append((match, os.path.join(root, f), curr_sys))
                            found_ids.add(match['id'])

            # Identify missing
            for rom in self.roms:
                if rom['id'] not in found_ids:
                    self.missing_roms.append(rom)
            
            self.total_dl_size = sum(r.get('size', 0) for r in self.missing_roms)
            self.phase = "SUMMARY"
            self.loading = False
            
        except Exception as e:
            logger.error(f"Scan error: {e}")
            self.error = str(e)
            self.loading = False

    def _execute_download(self):
        self.phase = "DOWNLOADING"
        try:
            # Re-fetch platforms to ensure we have slugs
            platforms = romm_api.get_platforms()
            platform_slugs = {p['id']: p.get('fs_slug', '').lower() for p in platforms} if platforms else {}
            
            target_base = "/media/sdcard1/Roms"
            if not os.path.exists(target_base): target_base = "/media/sdcard0/Roms"
            if not os.path.exists(target_base): target_base = "/mnt/SDCARD/Roms"

            for i, rom in enumerate(self.missing_roms):
                self.download_idx = i + 1
                self.progress_text = f"[{i+1}/{len(self.missing_roms)}] {rom.get('name')}"
                
                slug = platform_slugs.get(rom.get('platform_id'), "")
                system_folder = self.slug_to_spruce.get(slug, [slug.upper() if slug else "UNKNOWN"])[0]
                
                target_dir = os.path.join(target_base, system_folder)
                os.makedirs(target_dir, exist_ok=True)
                
                filename = rom.get('fs_name')
                if not filename and rom.get('files'): filename = rom['files'][0].get('file_name')
                if not filename: filename = f"{rom.get('name')}.zip"
                
                dest_path = os.path.join(target_dir, filename)
                
                def prog_cb(curr, total):
                    if total > 0: self.download_progress = int((curr/total)*100)
                
                success, msg = romm_api.download_rom(rom['id'], dest_path, progress_callback=prog_cb)
                if success:
                    self.found_local.append((rom, dest_path, system_folder))
                else:
                    logger.error(f"Download failed for {rom.get('name')}: {msg}")

            # Final Step: Update collections.json
            self.status = "Updating device collection..."
            collections = favorites_matcher.load_collections()
            
            # Find or create collection
            target_coll = None
            for c in collections:
                if c.get('collection_name') == self.collection_name:
                    target_coll = c
                    break
            
            if not target_coll:
                target_coll = {"collection_name": self.collection_name, "game_list": []}
                collections.append(target_coll)
            
            # Merge game list
            existing_paths = {g.get('rom_file_path') for g in target_coll['game_list']}
            for rom, path, system in self.found_local:
                if path not in existing_paths:
                    target_coll['game_list'].append({
                        "rom_file_path": path,
                        "game_system_name": system
                    })
            
            favorites_matcher.save_collections(collections)
            self.phase = "DONE"
            
        except Exception as e:
            logger.error(f"Download error: {e}")
            self.error = str(e)
            self.phase = "DONE"

    def handle_event(self, event):
        action = core.input.map_event(event)
        if not action: return None
        
        if self.phase == "SUMMARY":
            if action == "UP":
                self.selected_idx = max(0, self.selected_idx - 1)
                if self.selected_idx < self.scroll_offset: self.scroll_offset = self.selected_idx
            elif action == "DOWN":
                total = len(self.roms)
                self.selected_idx = min(total - 1, self.selected_idx + 1)
                if self.selected_idx >= self.scroll_offset + self.items_per_page:
                    self.scroll_offset = self.selected_idx - self.items_per_page + 1
            elif action == "ACCEPT":
                threading.Thread(target=self._execute_download, daemon=True).start()
            elif action == "CANCEL":
                return "SWITCH_TO_COLLECTIONS"
        
        elif self.phase == "DONE" or self.error:
            if action == "ACCEPT" or action == "CANCEL":
                return "SWITCH_TO_COLLECTIONS"
                
        return None

    def draw(self):
        render_text_shadow(self.renderer, self.font, "Collection Download", 320, 20, (100, 200, 255), center=True)
        render_text(self.renderer, self.font, f"Collection: {self.collection_name}", 320, 50, (200, 200, 200), center=True)
        
        if self.loading:
            render_text(self.renderer, self.font, self.status, 320, 240, (255, 255, 255), center=True)
        elif self.error:
            render_text(self.renderer, self.font, f"ERROR: {self.error}", 320, 200, (255, 100, 100), center=True)
            render_text(self.renderer, self.font, "Press A or B to return", 320, 240, (150, 150, 150), center=True)
        elif self.phase == "SUMMARY":
            y_start = 100
            visible = self.roms[self.scroll_offset:self.scroll_offset + self.items_per_page]
            
            for i, rom in enumerate(visible):
                idx = self.scroll_offset + i
                y = y_start + (i * 35)
                
                is_local = any(l[0]['id'] == rom['id'] for l in self.found_local)
                color = (150, 255, 150) if is_local else (255, 150, 150)
                
                if idx == self.selected_idx:
                    draw_panel(self.renderer, 40, y - 5, 560, 30, bg_color=(60, 60, 100, 255))
                    draw_selector(self.renderer, 40, y - 5, 560, 30)
                
                name = self._get_clean_name(rom)
                if len(name) > 40: name = name[:37] + "..."
                status_icon = "●" if is_local else "○"
                render_text(self.renderer, self.font, f"{status_icon} {name}", 60, y, color)
                
                size_mb = rom.get('size', 0) / (1024 * 1024)
                if size_mb > 0:
                    render_text(self.renderer, self.font, f"{size_mb:.1f}MB", 580, y, (150, 150, 150), right=True)

            # Footer summary
            draw_panel(self.renderer, 0, 400, 640, 80, bg_color=(20, 20, 30, 255))
            sum_text = f"Total: {len(self.roms)} | Found: {len(self.found_local)} | Missing: {len(self.missing_roms)}"
            render_text(self.renderer, self.font, sum_text, 320, 415, (255, 255, 255), center=True)
            
            dl_text = f"Download Size: {self.total_dl_size / (1024 * 1024):.1f} MB"
            render_text(self.renderer, self.font, dl_text, 320, 435, (200, 200, 200), center=True)
            
            render_text(self.renderer, self.font, "A: Start Download | B: Cancel", 320, 455, (100, 255, 100), center=True)

        elif self.phase == "DOWNLOADING":
            render_text(self.renderer, self.font, "Downloading Games...", 320, 200, (255, 255, 255), center=True)
            render_text(self.renderer, self.font, self.progress_text, 320, 240, (200, 200, 200), center=True)
            
            # Progress bar
            draw_panel(self.renderer, 120, 280, 400, 20, bg_color=(50, 50, 50))
            draw_panel(self.renderer, 120, 280, int(400 * (self.download_progress/100)), 20, bg_color=(100, 255, 100))
            
        elif self.phase == "DONE":
            render_text(self.renderer, self.font, "Download Complete!", 320, 200, (0, 255, 0), center=True)
            render_text(self.renderer, self.font, f"Collection '{self.collection_name}' updated on device.", 320, 240, (255, 255, 255), center=True)
            render_text(self.renderer, self.font, "Press A or B to return", 320, 440, (150, 150, 150), center=True)
