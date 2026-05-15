import threading
from core.romm_api import romm_api
from core.favorites_matcher import favorites_matcher
import core.input
from ui.components import render_text, render_text_shadow, draw_panel

class FavoritePushStatusScreen:
    def __init__(self, renderer, font, collection):
        self.renderer = renderer
        self.font = font
        self.collection = collection
        self.status = "Initializing..."
        self.loading = True
        self.success = False
        self.message = ""
        
        threading.Thread(target=self._push_favorites, daemon=True).start()

    def _push_favorites(self):
        try:
            self.status = "Extracting matched favorites..."
            rom_ids = favorites_matcher.get_matched_rom_ids()
            
            if not rom_ids:
                self.loading = False
                self.message = "No matched favorites found to push."
                return

            self.status = f"Pushing {len(rom_ids)} favorites to '{self.collection['name']}'..."
            success, msg = romm_api.add_roms_to_collection(self.collection['id'], rom_ids)
            
            self.success = success
            self.message = msg
        except Exception as e:
            self.success = False
            self.message = f"Error: {str(e)}"
        finally:
            self.loading = False

    def handle_event(self, event):
        action = core.input.map_event(event)
        if not action: return None
        
        if not self.loading:
            if action == "ACCEPT" or action == "CANCEL":
                return "SWITCH_TO_SETTINGS"
        return None

    def draw(self):
        render_text_shadow(self.renderer, self.font, "Pushing Favorites", 320, 20, (0, 255, 150), center=True)
        
        y_pos = 200
        if self.loading:
            render_text(self.renderer, self.font, self.status, 320, y_pos, (255, 255, 255), center=True)
        else:
            color = (100, 255, 100) if self.success else (255, 100, 100)
            render_text(self.renderer, self.font, self.message, 320, y_pos, color, center=True)
            render_text(self.renderer, self.font, "Press A or B to return to Settings", 320, 280, (150, 150, 150), center=True)
