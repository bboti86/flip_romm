import sdl2
from core.config import config
import core.input
from ui.components import render_text, render_text_shadow, draw_panel, TextInput, OnScreenKeyboard

class SettingsScreen:
    def __init__(self, renderer, font):
        self.renderer = renderer
        self.font = font
        self.selected_idx = 0
        
        self.restore_msg = None
        
        # UI Elements
        self.fields = [
            {"label": "LOCAL FAVORITES ->", "key": "nav_local_favorites", "is_button": True},
            {"label": "COLLECTIONS ->", "key": "nav_collections", "is_button": True},
            {"label": "RESTORE FAVORITES", "key": "action_restore", "is_button": True},
            {"label": "EXIT", "key": "save", "is_button": True}
        ]

    def handle_event(self, event):
        action = core.input.map_event(event)
        if not action:
            return None

        if action == "UP":
            self.selected_idx = (self.selected_idx - 1) % len(self.fields)
        elif action == "DOWN":
            self.selected_idx = (self.selected_idx + 1) % len(self.fields)
        elif action == "ACCEPT":
            field = self.fields[self.selected_idx]
            if field["key"] == "save":
                return "QUIT_APP"
            elif field["key"] == "nav_collections":
                return "SWITCH_TO_COLLECTIONS"
            elif field["key"] == "nav_local_favorites":
                return "SWITCH_TO_LOCAL_FAVORITES"
            elif field["key"] == "action_restore":
                from core.favorites_matcher import favorites_matcher
                success, msg = favorites_matcher.restore_favorites_backup()
                self.restore_msg = msg
        elif action == "CANCEL":
            return "QUIT_APP"

        return None

    def draw(self):
        # Header
        render_text_shadow(self.renderer, self.font, "RomM Integration", 320, 20, (255, 200, 0), center=True)
        
        # Status message
        if self.restore_msg:
            render_text(self.renderer, self.font, self.restore_msg, 320, 80, (255, 150, 150), center=True)
        else:
            render_text(self.renderer, self.font, "Configuration loaded from settings.json", 320, 80, (150, 255, 150), center=True)
        render_text(self.renderer, self.font, f"URL: {config.romm_url}", 320, 110, (200, 200, 200), center=True)
        
        # Fields
        for i, field in enumerate(self.fields):
            color = (0, 255, 255) if i == self.selected_idx else (200, 200, 200)
            y_pos = 170 + i * 50
            
            draw_panel(self.renderer, 200, y_pos, 240, 40, bg_color=(40, 40, 50, 255) if i != self.selected_idx else (60, 60, 150, 255))
            render_text(self.renderer, self.font, field["label"], 320, y_pos + 10, color, center=True)
            
        # Footer
        footer_text = "D-Pad: Move | A: Select | B: Quit"
        render_text(self.renderer, self.font, footer_text, 320, 440, (150, 150, 150), center=True)
