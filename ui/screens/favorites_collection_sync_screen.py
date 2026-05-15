import sdl2
import threading
from core.romm_api import romm_api
from core.favorites_matcher import favorites_matcher
import core.input
from ui.components import render_text, render_text_shadow, draw_panel, draw_selector

class FavoritesCollectionSyncScreen:
    def __init__(self, renderer, font, collection):
        self.renderer = renderer
        self.font = font
        self.collection = collection
        self.collection_id = collection.get('id')
        self.collection_name = collection.get('name', 'Unknown')
        
        self.loading = True
        self.status_text = "Preparing sync..."
        self.error = None
        
        self.local_favorites = []
        self.matched_roms = []
        self.already_in_collection_ids = set()
        self.to_add_roms = []
        self.missing_in_romm = []
        
        self.sync_started = False
        self.sync_complete = False
        self.sync_result = ""
        
        self.show_missing_list = False
        self.missing_index = 0
        self.uploading_rom = None
        self.upload_error = None
        self.platforms_map = {} # system_name -> platform_id
        
        # Start matching thread
        threading.Thread(target=self._prepare_sync, daemon=True).start()

    def _prepare_sync(self):
        try:
            self.status_text = "Loading local favorites..."
            self.local_favorites = favorites_matcher.load_local_favorites()
            if not self.local_favorites:
                self.error = "No local favorites found."
                return

            self.status_text = "Fetching RomM platforms..."
            platforms = romm_api.get_platforms()
            for p in platforms:
                # Use fs_slug as the primary key for mapping (e.g. 'gba')
                fs_slug = p.get('fs_slug', '').lower()
                if fs_slug:
                    self.platforms_map[fs_slug] = p.get('id')

            self.status_text = "Fetching all RomM ROMs..."
            all_romm_roms = romm_api.get_all_roms()
            favorites_matcher.set_romm_roms(all_romm_roms)
            
            self._do_matching()
            self.status_text = "Ready to sync."
            
        except Exception as e:
            self.error = str(e)
        finally:
            self.loading = False

    def _do_matching(self):
        """Perform matching and update lists."""
        matches = favorites_matcher.get_matches()
        
        self.status_text = "Fetching collection content..."
        collection_roms = romm_api.get_roms_by_collection(self.collection_id)
        self.already_in_collection_ids = {rom['id'] for rom in collection_roms}
        
        self.to_add_roms = []
        self.missing_in_romm = []
        
        for m in matches:
            if m['is_matched']:
                rom_id = m['romm_id']
                if rom_id not in self.already_in_collection_ids:
                    self.to_add_roms.append(m)
            else:
                self.missing_in_romm.append(m)

    def _execute_sync(self):
        self.sync_started = True
        self.status_text = "Adding ROMs to collection..."
        
        rom_ids = [m['romm_id'] for m in self.to_add_roms]
        if not rom_ids:
            self.sync_complete = True
            self.sync_result = "Nothing to add."
            return

        success, message = romm_api.add_roms_to_collection(self.collection_id, rom_ids)
        self.sync_complete = True
        self.sync_result = message if success else f"Error: {message}"

    def _upload_missing_rom(self, rom_entry):
        self.uploading_rom = rom_entry['local_name']
        self.upload_error = None
        
        system = rom_entry.get('system', '').lower()
        platform_id = self.platforms_map.get(system)
        
        if not platform_id:
            # Try fuzzy platform match
            for slug, pid in self.platforms_map.items():
                if slug in system or system in slug:
                    platform_id = pid
                    break
        
        if not platform_id:
            self.upload_error = f"Platform '{system}' not found in RomM"
            self.uploading_rom = None
            return

        success_data = romm_api.upload_rom(rom_entry['path'], platform_id)
        
        if success_data:
            # Re-fetch ROMs and redo matching after successful upload
            self.status_text = "Refreshing matches..."
            all_romm_roms = romm_api.get_all_roms(use_cache=False) # Force refresh cache
            favorites_matcher.set_romm_roms(all_romm_roms)
            self._do_matching()
            self.uploading_rom = None
        else:
            self.upload_error = "Upload failed. Check logs."
            self.uploading_rom = None

    def handle_event(self, event):
        action = core.input.map_event(event)
        if not action: return None
        
        if action == "CANCEL":
            if self.show_missing_list:
                self.show_missing_list = False
                return None
            return "SWITCH_TO_COLLECTIONS"
            
        if self.loading or self.error or self.sync_started or self.uploading_rom:
            return None
            
        if self.show_missing_list:
            if action == "UP":
                self.missing_index = max(0, self.missing_index - 1)
            elif action == "DOWN":
                self.missing_index = min(len(self.missing_in_romm) - 1, self.missing_index + 1)
            elif action == "ACCEPT" and self.missing_in_romm:
                rom_entry = self.missing_in_romm[self.missing_index]
                threading.Thread(target=self._upload_missing_rom, args=(rom_entry,), daemon=True).start()
            return None

        if action == "ACCEPT" and not self.sync_started and self.to_add_roms:
            threading.Thread(target=self._execute_sync, daemon=True).start()
        elif action == "X_BUTTON" and self.missing_in_romm:
            self.show_missing_list = True
            self.missing_index = 0
            
        return None

    def draw(self):
        render_text_shadow(self.renderer, self.font, "Sync Favorites to RomM", 320, 20, (0, 255, 150), center=True)
        render_text(self.renderer, self.font, f"Collection: {self.collection_name}", 320, 50, (200, 200, 200), center=True)
        
        if self.loading:
            render_text(self.renderer, self.font, self.status_text, 320, 240, (255, 255, 255), center=True)
        elif self.error:
            render_text(self.renderer, self.font, f"Error: {self.error}", 320, 240, (255, 100, 100), center=True)
            render_text(self.renderer, self.font, "Press B to go back", 320, 280, (150, 150, 150), center=True)
        elif self.uploading_rom:
            render_text(self.renderer, self.font, f"Uploading {self.uploading_rom}...", 320, 240, (255, 255, 255), center=True)
            render_text(self.renderer, self.font, "This may take a while depending on file size.", 320, 270, (150, 150, 150), center=True)
        elif self.sync_complete:
            render_text(self.renderer, self.font, "Sync Finished!", 320, 180, (0, 255, 0), center=True)
            render_text(self.renderer, self.font, self.sync_result, 320, 220, (255, 255, 255), center=True)
            
            y = 280
            render_text(self.renderer, self.font, f"Games added: {len(self.to_add_roms)}", 100, y, (200, 200, 200))
            y += 30
            render_text(self.renderer, self.font, f"Missing from RomM: {len(self.missing_in_romm)}", 100, y, (255, 150, 100))
            
            render_text(self.renderer, self.font, "Press B to return to collections", 320, 440, (150, 150, 150), center=True)
        elif self.sync_started:
            render_text(self.renderer, self.font, self.status_text, 320, 240, (255, 255, 255), center=True)
        elif self.show_missing_list:
            # Missing games list view
            render_text(self.renderer, self.font, "Missing Games (Local Files)", 320, 85, (255, 100, 100), center=True)
            draw_panel(self.renderer, 30, 110, 580, 310, bg_color=(20, 20, 30, 255))
            
            visible_count = 8
            start_idx = max(0, min(self.missing_index - visible_count // 2, len(self.missing_in_romm) - visible_count))
            
            for i in range(visible_count):
                idx = start_idx + i
                if idx >= len(self.missing_in_romm): break
                
                rom = self.missing_in_romm[idx]
                y = 130 + i * 35
                
                color = (255, 255, 255)
                if idx == self.missing_index:
                    draw_selector(self.renderer, 40, y - 5, 560, 30)
                    color = (255, 255, 100)
                
                name_text = rom['local_name'][:45] + "..." if len(rom['local_name']) > 45 else rom['local_name']
                render_text(self.renderer, self.font, f"[{rom['system']}] {name_text}", 60, y, color)
            
            if self.upload_error:
                render_text(self.renderer, self.font, f"Error: {self.upload_error}", 320, 420, (255, 50, 50), center=True)
            else:
                render_text(self.renderer, self.font, "A: Upload Selected | B: Back", 320, 440, (255, 255, 255), center=True)
        else:
            # Summary screen
            draw_panel(self.renderer, 40, 100, 560, 260, bg_color=(30, 30, 40, 255))
            
            y = 120
            render_text(self.renderer, self.font, f"Total Favorites: {len(self.local_favorites)}", 60, y, (255, 255, 255))
            y += 40
            render_text(self.renderer, self.font, f"Already in Collection: {len(self.already_in_collection_ids)}", 60, y, (150, 150, 150))
            y += 40
            render_text(self.renderer, self.font, f"To be Added: {len(self.to_add_roms)}", 60, y, (0, 255, 100))
            y += 40
            render_text(self.renderer, self.font, f"Not Found in RomM: {len(self.missing_in_romm)}", 60, y, (255, 100, 100))
            
            y += 65
            if self.missing_in_romm:
                render_text(self.renderer, self.font, "Press X to view missing games & upload", 320, y, (255, 100, 100), center=True)
            
            if self.to_add_roms:
                render_text(self.renderer, self.font, "A: Start Sync | B: Cancel", 320, 440, (255, 255, 255), center=True)
            else:
                render_text(self.renderer, self.font, "Nothing to sync. B: Back", 320, 440, (150, 150, 150), center=True)
