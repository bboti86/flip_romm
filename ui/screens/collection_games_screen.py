import sdl2
import threading
from core.romm_api import romm_api
from core.favorites_matcher import favorites_matcher
import core.input
from ui.components import render_text, render_text_shadow, draw_panel, draw_selector

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
        
        threading.Thread(target=self._fetch_games, daemon=True).start()

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
            return ("SWITCH_TO_COLLECTIONS", self.collection.get('_list_index', 0))
            
        if self.loading or self.error or not self.roms:
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

        footer_text = "START: Sync | L1/R1: Page | B: Back"
        render_text(self.renderer, self.font, footer_text, 320, 440, (150, 150, 150), center=True)
