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
        
        # UI Elements logically grouped
        # Left column: Browsing/Viewing. Right column: Actions/Syncing
        self.fields = [
            {"label": "COLLECTIONS", "key": "nav_collections", "is_button": True},
            {"label": "SYNC SCREENSHOTS", "key": "nav_screenshot_sync", "is_button": True},
            {"label": "LOCAL FAVORITES", "key": "nav_local_favorites", "is_button": True},
            {"label": "PUSH FAVS TO ROMM", "key": "action_push_favorites", "is_button": True},
            {"label": "RESTORE FAVORITES", "key": "action_restore", "is_button": True},
            {"label": "EXIT APP", "key": "save", "is_button": True}
        ]

    def handle_event(self, event):
        action = core.input.map_event(event)
        if not action:
            return None

        num_fields = len(self.fields)
        cols = 2 if num_fields >= 6 else 1

        if action == "UP":
            if cols == 2:
                if self.selected_idx >= 2:
                    self.selected_idx -= 2
                else:
                    # Wrap around to the bottom
                    # e.g. 0 -> 4 or 5
                    # 1 -> 5 or 4
                    col = self.selected_idx % 2
                    last_row = (num_fields - 1) // 2
                    new_idx = last_row * 2 + col
                    if new_idx >= num_fields:
                        new_idx -= 2
                    self.selected_idx = new_idx
            else:
                self.selected_idx = (self.selected_idx - 1) % num_fields
        elif action == "DOWN":
            if cols == 2:
                if self.selected_idx + 2 < num_fields:
                    self.selected_idx += 2
                else:
                    # Wrap around to the top
                    self.selected_idx = self.selected_idx % 2
            else:
                self.selected_idx = (self.selected_idx + 1) % num_fields
        elif action == "LEFT":
            if cols == 2:
                if self.selected_idx % 2 == 1:
                    self.selected_idx -= 1
                else:
                    # wrap around to right
                    if self.selected_idx + 1 < num_fields:
                        self.selected_idx += 1
        elif action == "RIGHT":
            if cols == 2:
                if self.selected_idx % 2 == 0 and self.selected_idx + 1 < num_fields:
                    self.selected_idx += 1
                else:
                    # wrap around to left
                    if self.selected_idx % 2 == 1:
                        self.selected_idx -= 1
        elif action == "ACCEPT":
            field = self.fields[self.selected_idx]
            if field["key"] == "save":
                return "QUIT_APP"
            elif field["key"] == "nav_collections":
                return "SWITCH_TO_COLLECTIONS"
            elif field["key"] == "nav_local_favorites":
                return "SWITCH_TO_LOCAL_FAVORITES"
            elif field["key"] == "nav_screenshot_sync":
                return "SWITCH_TO_SCREENSHOT_SYNC"
            elif field["key"] == "nav_push_sync":
                return "SWITCH_TO_PUSH_SYNC"
            elif field["key"] == "action_push_favorites":
                return "SWITCH_TO_COLLECTION_PICKER"
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
        num_fields = len(self.fields)
        cols = 2 if num_fields >= 6 else 1
        
        for i, field in enumerate(self.fields):
            color = (0, 255, 255) if i == self.selected_idx else (200, 200, 200)
            
            if cols == 2:
                row = i // 2
                col = i % 2
                
                box_w = 260
                box_h = 45
                gap_x = 40
                gap_y = 15
                
                # Start X = (640 - (260*2 + 40)) / 2 = 40
                x_pos = 40 + col * (box_w + gap_x)
                y_pos = 170 + row * (box_h + gap_y)
                
                draw_panel(self.renderer, x_pos, y_pos, box_w, box_h, bg_color=(40, 40, 50, 255) if i != self.selected_idx else (60, 60, 150, 255))
                render_text(self.renderer, self.font, field["label"], x_pos + box_w//2, y_pos + 12, color, center=True)
            else:
                y_pos = 170 + i * 50
                draw_panel(self.renderer, 200, y_pos, 240, 40, bg_color=(40, 40, 50, 255) if i != self.selected_idx else (60, 60, 150, 255))
                render_text(self.renderer, self.font, field["label"], 320, y_pos + 10, color, center=True)
            
        # Footer
        footer_text = "D-Pad: Navigate | A: Select | B: Exit App"
        render_text(self.renderer, self.font, footer_text, 320, 440, (150, 150, 150), center=True)
