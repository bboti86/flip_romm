import sdl2
import threading
import os
import core.input
from core.screenshot_manager import screenshot_manager
from ui.components import render_text, render_text_shadow, draw_panel, draw_selector

class ScreenshotSyncScreen:
    def __init__(self, renderer, font):
        self.renderer = renderer
        self.font = font
        self.screenshots = []
        self.loading = True
        self.selected_idx = 0
        self.scroll_offset = 0
        self.items_per_page = 6
        self.status_msg = "Scanning for screenshots..."
        self.syncing = False
        
        # Start scanning in a thread
        threading.Thread(target=self._scan, daemon=True).start()

    def _scan(self):
        self.loading = True
        try:
            self.screenshots = screenshot_manager.scan_screenshots()
            if not self.screenshots:
                self.status_msg = "No new screenshots found."
            else:
                self.status_msg = f"Found {len(self.screenshots)} pending screenshots."
        except Exception as e:
            self.status_msg = f"Error scanning: {str(e)}"
        finally:
            self.loading = False

    def _sync_all(self):
        if self.syncing: return
        self.syncing = True
        count = 0
        total = len(self.screenshots)
        
        for item in list(self.screenshots):
            self.status_msg = f"Uploading {count+1}/{total}: {item['game_name']}..."
            if screenshot_manager.upload_screenshot(item):
                self.screenshots.remove(item)
                count += 1
            # Adjust selection if it goes out of bounds
            if self.selected_idx >= len(self.screenshots):
                self.selected_idx = max(0, len(self.screenshots) - 1)
        
        self.status_msg = f"Successfully pushed {count} screenshots!"
        self.syncing = False

    def _sync_selected(self):
        if self.syncing or not self.screenshots: return
        self.syncing = True
        
        item = self.screenshots[self.selected_idx]
        self.status_msg = f"Uploading {item['game_name']}..."
        
        if screenshot_manager.upload_screenshot(item):
            self.screenshots.pop(self.selected_idx)
            if self.selected_idx >= len(self.screenshots):
                self.selected_idx = max(0, len(self.screenshots) - 1)
            self.status_msg = "Upload complete!"
        else:
            self.status_msg = "Upload failed."
            
        self.syncing = False

    def handle_event(self, event):
        action = core.input.map_event(event)
        if not action: return None
        
        if action == "CANCEL":
            return "SWITCH_TO_SETTINGS"
            
        if self.loading or self.syncing:
            return None

        if self.screenshots:
            if action == "UP":
                self.selected_idx = (self.selected_idx - 1) % len(self.screenshots)
                if self.selected_idx < self.scroll_offset:
                    self.scroll_offset = self.selected_idx
                elif self.selected_idx >= self.scroll_offset + self.items_per_page:
                    self.scroll_offset = self.selected_idx - self.items_per_page + 1
            elif action == "DOWN":
                self.selected_idx = (self.selected_idx + 1) % len(self.screenshots)
                if self.selected_idx >= self.scroll_offset + self.items_per_page:
                    self.scroll_offset = self.selected_idx - self.items_per_page + 1
                elif self.selected_idx < self.scroll_offset:
                    self.scroll_offset = self.selected_idx
            elif action == "ACCEPT":
                threading.Thread(target=self._sync_selected, daemon=True).start()
            elif action == "START":
                threading.Thread(target=self._sync_all, daemon=True).start()

        return None

    def draw(self):
        render_text_shadow(self.renderer, self.font, "Screenshot Sync", 320, 20, (255, 150, 50), center=True)
        
        # Status Bar
        draw_panel(self.renderer, 40, 60, 560, 40, bg_color=(40, 40, 60, 255))
        color = (255, 255, 255)
        if "Success" in self.status_msg: color = (100, 255, 100)
        elif "Error" in self.status_msg or "failed" in self.status_msg: color = (255, 100, 100)
        render_text(self.renderer, self.font, self.status_msg, 320, 70, color, center=True)

        if self.loading:
            render_text(self.renderer, self.font, "Scanning files...", 320, 240, (200, 200, 200), center=True)
        elif not self.screenshots:
            render_text(self.renderer, self.font, "No pending screenshots to sync.", 320, 240, (150, 150, 150), center=True)
        else:
            y_start = 120
            item_h = 50
            visible_items = self.screenshots[self.scroll_offset:self.scroll_offset + self.items_per_page]
            
            for i, item in enumerate(visible_items):
                actual_idx = self.scroll_offset + i
                y_pos = y_start + (i * (item_h + 5))
                
                if actual_idx == self.selected_idx:
                    draw_panel(self.renderer, 40, y_pos - 5, 560, item_h, bg_color=(80, 80, 120, 255))
                    draw_selector(self.renderer, 40, y_pos - 5, 560, item_h)
                else:
                    draw_panel(self.renderer, 40, y_pos - 5, 560, item_h, bg_color=(30, 30, 40, 255))
                
                name = item['game_name']
                render_text(self.renderer, self.font, name, 50, y_pos - 2, (255, 255, 255))
                
                # Show filename on the second line (truncated if necessary)
                fname = item['filename']
                if len(fname) > 55: fname = fname[:52] + "..."
                render_text(self.renderer, self.font, fname, 60, y_pos + 18, (150, 150, 150))

        footer_text = "START: Upload All | A: Upload Single | B: Back"
        render_text(self.renderer, self.font, footer_text, 320, 440, (150, 150, 150), center=True)
