import sdl2
import threading
import os
from datetime import datetime
from core.romm_api import romm_api
from core.favorites_matcher import favorites_matcher
import core.input
from ui.components import render_text, render_text_shadow, draw_panel, draw_selector, render_text_wrapped, get_wrapped_lines

class CollectionGamesScreen:
    def __init__(self, renderer, font, collection):
        self.renderer = renderer
        self.font = font
        self.collection = collection
        self.roms = []
        self.fav_names = set()
        self.platform_slugs = {}
        self.loading = True
        self.error = None
        self.selected_idx = 0
        self.scroll_offset = 0
        self.items_per_page = 8
        self.scroll_timer = 0.3
        self.show_metadata = False
        self.metadata_loading = False
        self.current_metadata = None
        self.metadata_scroll_offset = 0
        self.metadata_scroll_timer = 0.3
        self.local_exists = False
        
        threading.Thread(target=self._fetch_games, daemon=True).start()

    def _check_local_exists(self, rom):
        if not rom: return False
        
        possible_dirs = ["/mnt/SDCARD/Roms", "/media/sdcard0/Roms", "/media/sdcard1/Roms"]
        
        # Get the base slug from RomM
        base_slug = self.platform_slugs.get(rom.get('platform_id', 0), '').lower()
        if not base_slug:
            # Fallback to platform_slug if available in the detailed meta
            base_slug = rom.get('platform_slug', '').lower()
            
        if not base_slug: return False
        
        # SpruceOS specific mapping (same as in sync_screen.py)
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
        
        # Folders to check on the device
        target_folders = slug_to_spruce.get(base_slug, [base_slug.upper(), base_slug])
        
        files_to_check = []
        if rom.get('files'):
            for f in rom['files']:
                if f.get('file_name'): files_to_check.append(f['file_name'].lower())
        
        # Also check fs_name from RomM
        fs_name = rom.get('fs_name')
        if fs_name:
            files_to_check.append(fs_name.lower())
            
        if not files_to_check:
            return False
            
        for d in possible_dirs:
            for sys_name in target_folders:
                sys_dir = os.path.join(d, sys_name)
                if os.path.exists(sys_dir):
                    try:
                        for root, dirs, files in os.walk(sys_dir):
                            local_files = [f.lower() for f in files]
                            # 1. Try exact filename matches
                            for f_name in files_to_check:
                                if f_name in local_files:
                                    return True
                            
                            # 2. Try matching display name against filenames (ignoring extensions)
                            rom_name = rom.get('name', '').lower()
                            if rom_name:
                                # Standardize names by removing punctuation and separators
                                def normalize(s):
                                    for char in ":!?-_.":
                                        s = s.replace(char, " ")
                                    return " ".join(s.split()) # Collapse multiple spaces and strip
                                
                                clean_rom_name = normalize(rom_name)
                                for lf in local_files:
                                    lf_no_ext = os.path.splitext(lf)[0]
                                    clean_lf = normalize(lf_no_ext)
                                    
                                    if clean_rom_name == clean_lf:
                                        return True
                                    
                                    # Also check if the RomM name is exactly the start of the file
                                    if clean_lf.startswith(clean_rom_name):
                                         if len(clean_rom_name) > 5:
                                             return True
                    except Exception as e:
                        pass
        return False

    def _fetch_metadata(self, rom):
        self.metadata_loading = True
        self.current_metadata = None
        self.metadata_scroll_offset = 0
        self.local_exists = False
        try:
            data = romm_api.get_rom_details(rom.get('id'))
            self.current_metadata = data if data else {}
            if self.current_metadata:
                self.local_exists = self._check_local_exists(self.current_metadata)
        except Exception as e:
            print(f"Error fetching metadata: {e}")
            self.current_metadata = {"error": "Failed to load metadata"}
        finally:
            self.metadata_loading = False

    def _fetch_games(self):
        try:
            # Load local favorites for matching
            local_favs = favorites_matcher.load_local_favorites()
            self.fav_names = set(f.get('display_name', '').lower().strip() for f in local_favs if f.get('display_name'))
            
            # Fetch platforms to map names/slugs
            platforms = romm_api._make_request("/platforms")
            if platforms:
                for p in platforms:
                    self.platform_slugs[p['id']] = p.get('fs_slug', '').upper()
                    
            # Fetch RomM ROMs for this collection
            collection_id = self.collection.get('id')
            if not collection_id:
                self.error = "Invalid collection data."
                self.loading = False
                return
                
            data = romm_api.get_roms_by_collection(collection_id)
            if data is None:
                self.error = "Failed to fetch games for this collection."
            else:
                self.roms = data
        except Exception as e:
            self.error = str(e)
        finally:
            self.loading = False

    def handle_event(self, event):
        action = core.input.map_event(event)
        if not action: return None
        
        if action == "CANCEL":
            if self.show_metadata:
                self.show_metadata = False
                return None
            return ("SWITCH_TO_COLLECTIONS", self.collection.get('_list_index', 0))
            
        if self.loading or self.error or not self.roms:
            return None

        if self.show_metadata:
            if action == "UP":
                if self.metadata_scroll_offset > 0:
                    self.metadata_scroll_offset -= 1
            elif action == "DOWN":
                self.metadata_scroll_offset += 1
            return None

        if action == "ACCEPT":
            self.show_metadata = True
            rom = self.roms[self.selected_idx]
            if rom:
                threading.Thread(target=self._fetch_metadata, args=(rom,), daemon=True).start()
            return None

        if action == "UP":
            if self.selected_idx == 0:
                self.selected_idx = len(self.roms) - 1
                self.scroll_offset = max(0, self.selected_idx - self.items_per_page + 1)
            else:
                self.selected_idx -= 1
                if self.selected_idx < self.scroll_offset:
                    self.scroll_offset = self.selected_idx
        elif action == "DOWN":
            if self.selected_idx == len(self.roms) - 1:
                self.selected_idx = 0
                self.scroll_offset = 0
            else:
                self.selected_idx += 1
                if self.selected_idx >= self.scroll_offset + self.items_per_page:
                    self.scroll_offset = self.selected_idx - self.items_per_page + 1
        elif action == "L_BUMPER":
            self.selected_idx = max(0, self.selected_idx - self.items_per_page)
            if self.selected_idx < self.scroll_offset:
                self.scroll_offset = self.selected_idx
        elif action == "R_BUMPER":
            self.selected_idx = min(len(self.roms) - 1, self.selected_idx + self.items_per_page)
            if self.selected_idx >= self.scroll_offset + self.items_per_page:
                self.scroll_offset = self.selected_idx - self.items_per_page + 1
        elif action == "START":
            return ("SWITCH_TO_SYNC", self.collection.get('id'))

        return None

    def update(self, dt):
        if self.loading or self.error or not self.roms:
            return
            
        if self.show_metadata:
            if core.input.is_pressed("UP"):
                self.metadata_scroll_timer -= dt
                if self.metadata_scroll_timer <= 0:
                    self.metadata_scroll_timer = 0.08
                    if self.metadata_scroll_offset > 0:
                        self.metadata_scroll_offset -= 1
            elif core.input.is_pressed("DOWN"):
                self.metadata_scroll_timer -= dt
                if self.metadata_scroll_timer <= 0:
                    self.metadata_scroll_timer = 0.08
                    self.metadata_scroll_offset += 1
            else:
                self.metadata_scroll_timer = 0.3
            return
            
        if core.input.is_pressed("UP"):
            self.scroll_timer -= dt
            if self.scroll_timer <= 0:
                self.scroll_timer = 0.08
                if self.selected_idx == 0:
                    self.selected_idx = len(self.roms) - 1
                    self.scroll_offset = max(0, self.selected_idx - self.items_per_page + 1)
                else:
                    self.selected_idx -= 1
                    if self.selected_idx < self.scroll_offset:
                        self.scroll_offset = self.selected_idx
        elif core.input.is_pressed("DOWN"):
            self.scroll_timer -= dt
            if self.scroll_timer <= 0:
                self.scroll_timer = 0.08
                if self.selected_idx == len(self.roms) - 1:
                    self.selected_idx = 0
                    self.scroll_offset = 0
                else:
                    self.selected_idx += 1
                    if self.selected_idx >= self.scroll_offset + self.items_per_page:
                        self.scroll_offset = self.selected_idx - self.items_per_page + 1
        else:
            self.scroll_timer = 0.3

    def draw(self):
        title = f"Collection: {self.collection.get('name', 'Unknown')}"
        if len(title) > 30:
            title = title[:27] + "..."
        render_text_shadow(self.renderer, self.font, title, 320, 20, (0, 255, 150), center=True)
        
        if self.loading:
            render_text(self.renderer, self.font, "Fetching games...", 320, 240, (200, 200, 200), center=True)
        elif self.error:
            render_text(self.renderer, self.font, self.error, 320, 240, (255, 100, 100), center=True)
        elif not self.roms:
            render_text(self.renderer, self.font, "No games in this collection.", 320, 240, (200, 200, 200), center=True)
        else:
            y_start = 80
            visible_items = self.roms[self.scroll_offset:self.scroll_offset + self.items_per_page]
            
            for i, rom in enumerate(visible_items):
                actual_idx = self.scroll_offset + i
                y_pos = y_start + (i * 40)
                
                rom_name = str(rom.get('name', 'Unknown'))
                is_fav = rom_name.lower().strip() in self.fav_names
                
                bg_color = (60, 60, 100, 255) if actual_idx == self.selected_idx else (30, 30, 40, 255)
                draw_panel(self.renderer, 40, y_pos - 5, 560, 35, bg_color=bg_color)
                
                if actual_idx == self.selected_idx:
                    draw_selector(self.renderer, 40, y_pos - 5, 560, 35)
                
                display_name = rom_name
                if len(display_name) > 35:
                    display_name = display_name[:32] + "..."
                    
                text_color = (255, 255, 100) if is_fav else (255, 255, 255)
                render_text(self.renderer, self.font, display_name, 50, y_pos, text_color)
                
                system = self.platform_slugs.get(rom.get('platform_id'), 'SYS')
                render_text(self.renderer, self.font, f"[{system}]", 580, y_pos, (150, 150, 150), right=True)

            total = len(self.roms)
            if total > self.items_per_page:
                progress = f"{self.selected_idx + 1} / {total}"
                render_text(self.renderer, self.font, progress, 580, 40, (150, 150, 150), right=True)

        footer_text = "A: Info | START: Sync | L1/R1: Page | B: Back"
        render_text(self.renderer, self.font, footer_text, 320, 440, (150, 150, 150), center=True)

        if self.show_metadata:
            draw_panel(self.renderer, 40, 40, 560, 400, bg_color=(20, 20, 30, 245), border_color=(100, 150, 255))
            rom = self.roms[self.selected_idx]
            
            rom_name = str(rom.get('name', 'Unknown'))
            is_fav = rom_name.lower().strip() in self.fav_names
            title = "★ " + rom_name if is_fav else rom_name
            if len(title) > 40: title = title[:37] + "..."
            render_text_shadow(self.renderer, self.font, title, 320, 50, (255, 255, 100) if is_fav else (255, 255, 255), center=True)
            
            if self.metadata_loading:
                render_text(self.renderer, self.font, "Loading remote metadata...", 320, 200, (200, 200, 200), center=True)
            else:
                meta = self.current_metadata or {}
                
                y_offset = 80
                
                def draw_kv(label, val, x, y, val_color=(200, 200, 200)):
                    import ctypes
                    import sdl2.sdlttf
                    render_text(self.renderer, self.font, label, x, y, (150, 150, 150))
                    w, h = ctypes.c_int(0), ctypes.c_int(0)
                    sdl2.sdlttf.TTF_SizeUTF8(self.font, label.encode('utf-8'), ctypes.byref(w), ctypes.byref(h))
                    render_text(self.renderer, self.font, str(val), x + w.value + 5, y, val_color)

                system = rom.get('platform_display_name') or meta.get('platform_display_name') or self.platform_slugs.get(rom.get('platform_id'), 'SYS')
                draw_kv("System:", system, 60, y_offset, (150, 200, 255))
                
                igdb = meta.get('igdb_metadata', {})
                mdatum = meta.get('metadatum', {})

                developer = meta.get('developer') or (mdatum.get('companies', [])[0] if mdatum.get('companies') else None)
                if developer:
                    dev_str = str(developer)
                    if len(dev_str) > 20: dev_str = dev_str[:17] + "..."
                    draw_kv("Dev:", dev_str, 60, y_offset + 20, (200, 200, 200))
                    
                release_ts = igdb.get('first_release_date') or mdatum.get('first_release_date')
                if release_ts:
                    if release_ts > 2147483647: # Check if ms
                        release_ts /= 1000.0
                    try:
                        date_str = datetime.fromtimestamp(release_ts).strftime('%Y-%m-%d')
                        draw_kv("Release:", date_str, 60, y_offset + 40, (200, 200, 200))
                    except: pass
                    
                genres = igdb.get('genres') or mdatum.get('genres') or []
                tags = meta.get('tags') or meta.get('regions') or []
                
                if tags:
                    t_str = ", ".join([str(t) for t in tags[:3]])
                    if len(t_str) > 20: t_str = t_str[:17] + "..."
                    draw_kv("Tags/Reg:", t_str, 60, y_offset + 60, (200, 200, 200))
                    
                if genres:
                    g_str = ", ".join(genres)
                    if len(g_str) > 40: g_str = g_str[:37] + "..."
                    draw_kv("Genres:", g_str, 60, y_offset + 80, (200, 200, 200))

                fs_size = meta.get('fs_size_bytes')
                if fs_size:
                    size_mb = fs_size / (1024*1024)
                    draw_kv("Size:", f"{size_mb:.1f} MB", 60, y_offset + 100, (200, 200, 200))
                    
                rating = meta.get('rating')
                if rating:
                    draw_kv("Rating:", rating, 360, y_offset, (255, 215, 0))
                    
                publisher = meta.get('publisher')
                if publisher:
                    pub_str = str(publisher)
                    if len(pub_str) > 20: pub_str = pub_str[:17] + "..."
                    draw_kv("Pub:", pub_str, 360, y_offset + 20, (200, 200, 200))

                age_ratings = igdb.get('age_ratings') or mdatum.get('age_ratings') or []
                if age_ratings:
                    ar_str = ""
                    for ar in age_ratings:
                        if isinstance(ar, dict):
                            cat = ar.get('category')
                            val = ar.get('rating')
                            mapping = {1: '3', 2: '7', 3: '12', 4: '16', 5: '18', 6: 'RP', 7: 'EC', 8: 'E', 9: 'E10+', 10: 'T', 11: 'M', 12: 'AO'}
                            if cat == 1 and val in mapping:
                                ar_str = f"ESRB {mapping[val]}"
                                break
                            elif cat == 2 and val in mapping:
                                ar_str = f"PEGI {mapping[val]}"
                            elif 'name' in ar:
                                ar_str = ar['name']
                                break
                            elif val in mapping:
                                ar_str = mapping[val]
                        else:
                            ar_str = str(ar)
                    if not ar_str and isinstance(age_ratings[0], dict):
                        ar_str = str(age_ratings[0].get('rating', ''))
                    if ar_str:
                        draw_kv("Age Rating:", ar_str, 360, y_offset + 40, (200, 200, 200))
                
                loc_color = (100, 255, 100) if self.local_exists else (255, 100, 100)
                loc_str = "Yes" if self.local_exists else "No"
                draw_kv("On Device:", loc_str, 360, y_offset + 60, loc_color)

                desc = meta.get('description') or meta.get('overview') or meta.get('summary') or "No description available."
                render_text(self.renderer, self.font, "Description:", 60, y_offset + 130, (150, 150, 150))
                
                lines = get_wrapped_lines(self.font, desc, 520)
                max_visible_lines = 6
                
                max_scroll = max(0, len(lines) - max_visible_lines)
                if self.metadata_scroll_offset > max_scroll:
                    self.metadata_scroll_offset = max_scroll
                    
                visible_lines = lines[self.metadata_scroll_offset : self.metadata_scroll_offset + max_visible_lines]
                
                current_y = y_offset + 160
                for line in visible_lines:
                    render_text(self.renderer, self.font, line, 60, current_y, (200, 200, 200))
                    current_y += 22
                    
                if len(lines) > max_visible_lines:
                    progress = f"D-Pad to Scroll ({self.metadata_scroll_offset + 1}/{max_scroll + 1})"
                    render_text(self.renderer, self.font, progress, 580, y_offset + 130, (150, 150, 150), right=True)
                
            render_text(self.renderer, self.font, "B: Close", 320, 410, (150, 150, 150), center=True)
