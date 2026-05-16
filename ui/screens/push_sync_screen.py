import sdl2
import threading
import os
import time
from core.romm_api import romm_api
from core.favorites_matcher import favorites_matcher
import core.input
from core.logger import setup_logger
from ui.components import render_text, render_text_shadow, draw_panel, draw_selector

logger = setup_logger("push_sync")

class PushSyncScreen:
    def __init__(self, renderer, font):
        self.renderer = renderer
        self.font = font
        
        self.status = "Initializing Scan..."
        self.loading = True
        self.phase = "SCANNING" # SCANNING, SUMMARY, UPLOADING, DONE
        self.error = None
        
        # Scan results
        self.missing_roms = []    # Local files not on RomM
        self.pending_saves = []    # Matched games with local saves
        self.pending_states = []   # Matched games with local states
        
        self.total_upload_count = 0
        self.current_upload_idx = 0
        self.current_item_name = ""
        self.upload_progress = 0
        
        # UI State
        self.selected_idx = 0
        self.scroll_offset = 0
        self.items_per_page = 8
        
        threading.Thread(target=self._run_scan, daemon=True).start()

    def _run_scan(self):
        try:
            self.status = "Fetching platforms..."
            platforms = romm_api.get_platforms()
            platform_slugs = {p.get('fs_slug', '').lower(): p['id'] for p in platforms} if platforms else {}
            
            self.status = "Fetching all ROMs from RomM..."
            all_romm_roms = romm_api.get_all_roms(use_cache=False)
            favorites_matcher.set_romm_roms(all_romm_roms)
            
            # Index RomM ROMs by name/CRC
            romm_name_lookup = {}
            for rom in all_romm_roms:
                norm_name = favorites_matcher.normalize(rom.get('name', ''))
                if norm_name: romm_name_lookup[norm_name] = rom
                for f in rom.get('files', []):
                    fn = f.get('file_name')
                    if fn:
                        norm_fn = favorites_matcher.normalize(os.path.splitext(fn)[0])
                        romm_name_lookup[norm_fn] = rom

            self.status = "Scanning local ROM folders..."
            possible_dirs = ["/media/sdcard1/Roms", "/media/sdcard0/Roms", "/mnt/SDCARD/Roms"]
            valid_dirs = [d for d in possible_dirs if os.path.exists(d)]
            
            local_roms = []
            for rom_dir in valid_dirs:
                for root, dirs, files in os.walk(rom_dir):
                    dirs[:] = [d for d in dirs if not d.startswith('.') and d.lower() not in ('imgs', 'manuals', 'videos', 'snaps', 'boxarts', 'media', 'images', 'titles')]
                    rel = os.path.relpath(root, rom_dir)
                    curr_sys = rel.split(os.sep)[0].upper()
                    
                    for f in files:
                        if f.startswith('.') or f.lower().endswith(('.png', '.jpg', '.txt', '.xml', '.db')): continue
                        local_roms.append({
                            'path': os.path.join(root, f),
                            'filename': f,
                            'system': curr_sys
                        })

            self.status = "Analyzing matches..."
            for local in local_roms:
                norm_name = favorites_matcher.normalize(os.path.splitext(local['filename'])[0])
                romm_match = romm_name_lookup.get(norm_name)
                
                if not romm_match:
                    # Find platform ID for upload
                    plat_id = None
                    for slug, pid in platform_slugs.items():
                        if local['system'] in favorites_matcher.slug_to_spruce.get(slug, []):
                            plat_id = pid
                            break
                    if plat_id:
                        self.missing_roms.append({**local, 'plat_id': plat_id})
                else:
                    # Matched! Check for saves/states
                    save_file, states = favorites_matcher.get_save_paths(local['path'], local['system'])
                    if save_file:
                        self.pending_saves.append({'rom_id': romm_match['id'], 'path': save_file, 'name': local['filename']})
                    for s in states:
                        self.pending_states.append({'rom_id': romm_match['id'], 'path': s, 'name': os.path.basename(s)})

            self.total_upload_count = len(self.missing_roms) + len(self.pending_saves) + len(self.pending_states)
            self.phase = "SUMMARY"
            self.loading = False
            
        except Exception as e:
            logger.error(f"Scan error: {e}")
            self.error = str(e)
            self.loading = False

    def _execute_push(self):
        self.phase = "UPLOADING"
        try:
            # 1. Upload ROMs
            for item in self.missing_roms:
                self.current_upload_idx += 1
                self.current_item_name = f"ROM: {item['filename']}"
                self.upload_progress = 0
                romm_api.upload_rom(item['path'], item['plat_id'])
            
            # 2. Upload Saves
            for item in self.pending_saves:
                self.current_upload_idx += 1
                self.current_item_name = f"Save: {item['name']}"
                self.upload_progress = 0
                romm_api.upload_save(item['rom_id'], item['path'])
                
            # 3. Upload States
            for item in self.pending_states:
                self.current_upload_idx += 1
                self.current_item_name = f"State: {item['name']}"
                self.upload_progress = 0
                romm_api.upload_state(item['rom_id'], item['path'])
            
            self.phase = "DONE"
        except Exception as e:
            logger.error(f"Push error: {e}")
            self.error = str(e)
            self.phase = "DONE"

    def handle_event(self, event):
        action = core.input.map_event(event)
        if not action: return None
        
        if self.phase == "SUMMARY":
            if action == "ACCEPT":
                threading.Thread(target=self._execute_push, daemon=True).start()
            elif action == "CANCEL":
                return "SWITCH_TO_SETTINGS"
        elif self.phase == "DONE" or self.error:
            if action == "ACCEPT" or action == "CANCEL":
                return "SWITCH_TO_SETTINGS"
        return None

    def draw(self):
        render_text_shadow(self.renderer, self.font, "Push Sync to RomM", 320, 20, (255, 150, 0), center=True)
        
        if self.loading:
            render_text(self.renderer, self.font, self.status, 320, 240, (255, 255, 255), center=True)
        elif self.error:
            render_text(self.renderer, self.font, f"ERROR: {self.error}", 320, 200, (255, 100, 100), center=True)
            render_text(self.renderer, self.font, "Press A or B to return", 320, 240, (150, 150, 150), center=True)
        elif self.phase == "SUMMARY":
            draw_panel(self.renderer, 100, 100, 440, 200, bg_color=(30, 30, 40, 255))
            render_text(self.renderer, self.font, "Push Summary", 320, 120, (255, 255, 255), center=True)
            
            y = 160
            render_text(self.renderer, self.font, f"Missing ROMs: {len(self.missing_roms)}", 120, y, (200, 200, 200))
            render_text(self.renderer, self.font, f"Pending Saves: {len(self.pending_saves)}", 120, y + 30, (200, 200, 200))
            render_text(self.renderer, self.font, f"Pending States: {len(self.pending_states)}", 120, y + 60, (200, 200, 200))
            
            footer = "A: Push Everything | B: Cancel"
            render_text(self.renderer, self.font, footer, 320, 440, (150, 150, 150), center=True)
            
        elif self.phase == "UPLOADING":
            render_text(self.renderer, self.font, "Uploading to RomM...", 320, 200, (255, 255, 255), center=True)
            render_text(self.renderer, self.font, f"[{self.current_upload_idx}/{self.total_upload_count}]", 320, 230, (150, 200, 255), center=True)
            render_text(self.renderer, self.font, self.current_item_name, 320, 260, (200, 200, 200), center=True)
            
        elif self.phase == "DONE":
            render_text(self.renderer, self.font, "Push Complete!", 320, 200, (0, 255, 0), center=True)
            render_text(self.renderer, self.font, f"Uploaded {self.total_upload_count} items.", 320, 240, (255, 255, 255), center=True)
            render_text(self.renderer, self.font, "Press A or B to return", 320, 440, (150, 150, 150), center=True)
