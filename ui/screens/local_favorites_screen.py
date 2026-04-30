import sdl2
import threading
from core.favorites_matcher import favorites_matcher
import core.input
from ui.components import render_text, render_text_shadow, draw_panel, draw_selector

class LocalFavoritesScreen:
    def __init__(self, renderer, font):
        self.renderer = renderer
        self.font = font
        self.favorites = []
        self.loading = True
        self.error = None
        self.selected_idx = 0
        self.scroll_offset = 0
        self.items_per_page = 8
        self.scroll_timer = 0.3
        
        threading.Thread(target=self._load_favorites, daemon=True).start()

    def _load_favorites(self):
        try:
            favs = favorites_matcher.load_local_favorites()
            if not favs:
                self.error = "No favorites found on device."
            else:
                self.favorites = favs
        except Exception as e:
            self.error = f"Error loading favorites: {e}"
        finally:
            self.loading = False

    def handle_event(self, event):
        action = core.input.map_event(event)
        if not action: return None
        
        if action == "CANCEL":
            return "SWITCH_TO_SETTINGS"
            
        if self.loading or self.error or not self.favorites:
            return None

        if action == "UP":
            if self.selected_idx == 0:
                self.selected_idx = len(self.favorites) - 1
                self.scroll_offset = max(0, self.selected_idx - self.items_per_page + 1)
            else:
                self.selected_idx -= 1
                if self.selected_idx < self.scroll_offset:
                    self.scroll_offset = self.selected_idx
        elif action == "DOWN":
            if self.selected_idx == len(self.favorites) - 1:
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
            self.selected_idx = min(len(self.favorites) - 1, self.selected_idx + self.items_per_page)
            if self.selected_idx >= self.scroll_offset + self.items_per_page:
                self.scroll_offset = self.selected_idx - self.items_per_page + 1

        return None

    def update(self, dt):
        if self.loading or self.error or not self.favorites:
            return
            
        if core.input.is_pressed("UP"):
            self.scroll_timer -= dt
            if self.scroll_timer <= 0:
                self.scroll_timer = 0.08
                if self.selected_idx == 0:
                    self.selected_idx = len(self.favorites) - 1
                    self.scroll_offset = max(0, self.selected_idx - self.items_per_page + 1)
                else:
                    self.selected_idx -= 1
                    if self.selected_idx < self.scroll_offset:
                        self.scroll_offset = self.selected_idx
        elif core.input.is_pressed("DOWN"):
            self.scroll_timer -= dt
            if self.scroll_timer <= 0:
                self.scroll_timer = 0.08
                if self.selected_idx == len(self.favorites) - 1:
                    self.selected_idx = 0
                    self.scroll_offset = 0
                else:
                    self.selected_idx += 1
                    if self.selected_idx >= self.scroll_offset + self.items_per_page:
                        self.scroll_offset = self.selected_idx - self.items_per_page + 1
        else:
            self.scroll_timer = 0.3

    def draw(self):
        render_text_shadow(self.renderer, self.font, "Local SpruceOS Favorites", 320, 20, (0, 200, 255), center=True)
        
        if self.loading:
            render_text(self.renderer, self.font, "Loading...", 320, 240, (200, 200, 200), center=True)
        elif self.error:
            render_text(self.renderer, self.font, self.error, 320, 240, (255, 100, 100), center=True)
        elif not self.favorites:
            render_text(self.renderer, self.font, "No favorites list found.", 320, 240, (200, 200, 200), center=True)
        else:
            y_start = 80
            visible_items = self.favorites[self.scroll_offset:self.scroll_offset + self.items_per_page]
            
            for i, fav in enumerate(visible_items):
                actual_idx = self.scroll_offset + i
                y_pos = y_start + (i * 40)
                
                # Draw selector background if selected
                if actual_idx == self.selected_idx:
                    draw_panel(self.renderer, 40, y_pos - 5, 560, 35, bg_color=(60, 60, 100, 255))
                    draw_selector(self.renderer, 40, y_pos - 5, 560, 35)
                else:
                    draw_panel(self.renderer, 40, y_pos - 5, 560, 35, bg_color=(30, 30, 40, 255))
                
                name = str(fav.get('display_name', 'Unknown'))
                system = str(fav.get('game_system_name', 'SYS'))
                
                if len(name) > 35:
                    name = name[:32] + "..."
                    
                render_text(self.renderer, self.font, name, 50, y_pos, (255, 255, 255))
                render_text(self.renderer, self.font, f"[{system}]", 580, y_pos, (150, 150, 150), right=True)

            # Scrollbar indicator
            total = len(self.favorites)
            if total > self.items_per_page:
                progress = f"{self.selected_idx + 1} / {total}"
                render_text(self.renderer, self.font, progress, 580, 40, (150, 150, 150), right=True)

        footer_text = "L1/R1: Page | B: Back to Main Menu"
        render_text(self.renderer, self.font, footer_text, 320, 440, (150, 150, 150), center=True)
