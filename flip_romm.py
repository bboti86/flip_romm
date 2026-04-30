import sys
import os
import time
from core.logger import setup_logger

logger = setup_logger("main")

# Add libs path
sys.path.append(os.path.join(os.path.dirname(__file__), 'libs'))

import sdl2
import sdl2.ext
import sdl2.sdlttf
import core.input
from ui.screens.settings_screen import SettingsScreen
from ui.screens.collections_screen import CollectionsScreen
from ui.screens.collection_games_screen import CollectionGamesScreen
from ui.screens.local_favorites_screen import LocalFavoritesScreen
from ui.screens.sync_screen import SyncScreen

class Logger:
    def __init__(self, filename):
        self.terminal = sys.stdout
        self.log = open(filename, "w")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.log.flush()

    def flush(self):
        self.terminal.flush()
        self.log.flush()

def rotate_logs(base_path):
    log1 = base_path + ".1"
    log2 = base_path + ".2"
    if os.path.exists(log1):
        if os.path.exists(log2):
            os.remove(log2)
        os.rename(log1, log2)
    if os.path.exists(base_path):
        os.rename(base_path, log1)

def main():
    log_path = os.path.join(os.path.dirname(__file__), 'runtime.log')
    rotate_logs(log_path)
    
    sys.stdout = Logger(log_path)
    sys.stderr = sys.stdout
    
    logger.info("--- RomM Integration Starting ---")
    
    sdl2.ext.init()
    if sdl2.sdlttf.TTF_Init() == -1:
        logger.error(f"TTF_Init Error: {sdl2.sdlttf.TTF_GetError().decode('utf-8')}")
        sys.exit(1)
        
    core.input.init_joysticks()
    
    WIDTH, HEIGHT = 640, 480
    
    try:
        window = sdl2.ext.Window("RomM Integration", size=(WIDTH, HEIGHT), flags=sdl2.SDL_WINDOW_SHOWN | sdl2.SDL_WINDOW_FULLSCREEN)
    except Exception:
        window = sdl2.ext.Window("RomM Integration", size=(WIDTH, HEIGHT), flags=sdl2.SDL_WINDOW_SHOWN)
        
    window.show()
    
    renderer = sdl2.ext.Renderer(window, flags=sdl2.SDL_RENDERER_ACCELERATED | sdl2.SDL_RENDERER_PRESENTVSYNC)
    sdl2.SDL_SetRenderDrawBlendMode(renderer.sdlrenderer, sdl2.SDL_BLENDMODE_BLEND)
    sdl2.SDL_StartTextInput()
    
    font_path = os.path.join(os.path.dirname(__file__), 'assets', 'font.ttf')
    if not os.path.exists(font_path):
        logger.warning("Missing font asset, text rendering will fail")
        sys.exit(1)

    font = sdl2.sdlttf.TTF_OpenFont(font_path.encode('utf-8'), 20)
    
    current_screen = SettingsScreen(renderer, font)
    last_time = sdl2.SDL_GetTicks()
    
    running = True
    while running:
        now = sdl2.SDL_GetTicks()
        dt = (now - last_time) / 1000.0
        last_time = now

        events = sdl2.ext.get_events()
        for event in events:
            if event.type == sdl2.SDL_QUIT:
                running = False
            else:
                result = current_screen.handle_event(event)
                
                if result is not None:
                    if isinstance(result, tuple):
                        action = result[0]
                        data = result[1]
                    else:
                        action = result
                        data = None
                        
                    if action == "QUIT_APP":
                        logger.info("Quitting Application")
                        running = False
                    elif action == "SWITCH_TO_SETTINGS":
                        logger.info("Switching to Settings")
                        current_screen = SettingsScreen(renderer, font)
                    elif action == "SWITCH_TO_LOCAL_FAVORITES":
                        logger.info("Switching to Local Favorites")
                        current_screen = LocalFavoritesScreen(renderer, font)
                    elif action == "SWITCH_TO_SYNC":
                        logger.info(f"Switching to Sync: {data}")
                        current_screen = SyncScreen(renderer, font, data)
                    elif action == "SWITCH_TO_COLLECTIONS":
                        logger.info("Switching to Collections")
                        current_screen = CollectionsScreen(renderer, font, initial_idx=data if data is not None else 0)
                    elif action == "SWITCH_TO_COLLECTION_GAMES":
                        logger.info(f"Switching to Collection Games: {data}")
                        current_screen = CollectionGamesScreen(renderer, font, data)

        if hasattr(current_screen, 'update'):
            current_screen.update(dt)

        renderer.clear(sdl2.ext.Color(20, 20, 20))
        current_screen.draw()
        renderer.present()

    sdl2.SDL_StopTextInput()
    sdl2.sdlttf.TTF_CloseFont(font)
    sdl2.sdlttf.TTF_Quit()
    sdl2.ext.quit()
    sys.exit()

if __name__ == "__main__":
    main()
