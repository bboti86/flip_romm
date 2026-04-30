import json
import os
import urllib.request
import urllib.error
import urllib.parse
from .config import config

class RommAPI:
    def __init__(self):
        pass

    def _get_headers(self):
        return {
            "Authorization": f"Bearer {config.romm_api_key}",
            "Content-Type": "application/json"
        }
    
    def _make_request(self, endpoint, method="GET", data=None):
        url = config.romm_url.rstrip("/") + "/api" + endpoint
        headers = self._get_headers()
        
        req = urllib.request.Request(url, headers=headers, method=method)
        if data:
            req.data = json.dumps(data).encode('utf-8')
            req.add_header('Content-Type', 'application/json')
            
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            print(f"HTTP Error {e.code}: {e.read().decode('utf-8')}")
            return None
        except Exception as e:
            print(f"Error connecting to RomM API: {e}")
            return None

    def get_collections(self):
        """Fetch all collections from RomM."""
        if not config.romm_url or not config.romm_api_key:
            return None
            
        data = self._make_request("/collections")
        if data is not None:
            return data # Should be a list of collections
        return []

    def get_roms(self, limit=5000, offset=0):
        """Fetch roms from RomM."""
        if not config.romm_url or not config.romm_api_key:
            return None
            
        endpoint = f"/roms?limit={limit}&offset={offset}"
        data = self._make_request(endpoint)
        if data is not None and 'items' in data:
            return data['items']
        return []

    def get_all_roms(self):
        """Fetch all roms from RomM handling pagination."""
        all_roms = []
        limit = 1000
        offset = 0
        
        while True:
            roms = self.get_roms(limit=limit, offset=offset)
            if not roms:
                break
            all_roms.extend(roms)
            if len(roms) < limit:
                break
            offset += limit
            
        return all_roms

    def get_roms_by_collection(self, collection_id):
        """Fetch roms for a specific collection from RomM."""
        if not config.romm_url or not config.romm_api_key:
            return None
            
        endpoint = f"/roms?collection_id={collection_id}&limit=1000"
        data = self._make_request(endpoint)
        if data is not None and 'items' in data:
            return data['items']
        return []

    def get_rom_details(self, rom_id):
        """Fetch detailed metadata for a specific ROM with caching."""
        cache_dir = "cache"
        if not os.path.exists(cache_dir):
            try:
                os.makedirs(cache_dir, exist_ok=True)
            except Exception:
                pass
                
        cache_file = os.path.join(cache_dir, f"rom_{rom_id}.json")
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass

        if not config.romm_url or not config.romm_api_key:
            return None
            
        endpoint = f"/roms/{rom_id}"
        data = self._make_request(endpoint)
        
        if data:
            try:
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f)
            except Exception:
                pass
                
        return data

    def download_rom(self, rom_id, target_path, progress_callback=None, file_name=None):
        """Stream download a ROM from RomM."""
        try:
            # We NEED the file ID and file name for the v3 endpoint
            # Even if file_name is passed, we need the file ID
            details = self.get_rom_details(rom_id)
            if not details or not details.get('files'):
                return False, "No files found for this ROM"
            
            # Take the first file
            rom_file = details['files'][0]
            file_id = rom_file.get('id')
            actual_file_name = file_name or rom_file.get('file_name')
            
            if not file_id or not actual_file_name:
                return False, "File metadata missing"

            # RomM v3 download endpoint: /api/roms/{file_id}/files/content/{file_name}
            url = f"{config.romm_url.rstrip('/')}/api/roms/{file_id}/files/content/{urllib.parse.quote(actual_file_name)}"
            headers = self._get_headers()
            
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as response:
                total_size = int(response.headers.get('content-length', 0))
                downloaded_size = 0
                block_size = 1024 * 128 # 128KB blocks
                
                # Ensure directory exists
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                
                with open(target_path, 'wb') as f:
                    while True:
                        buffer = response.read(block_size)
                        if not buffer:
                            break
                        f.write(buffer)
                        downloaded_size += len(buffer)
                        if progress_callback:
                            progress_callback(downloaded_size, total_size)
                return True, "Download complete"
        except Exception as e:
            error_msg = str(e)
            print(f"Error downloading ROM: {error_msg}")
            # Clean up partial file if it exists
            if os.path.exists(target_path):
                try: os.remove(target_path)
                except: pass
            return False, error_msg

romm_api = RommAPI()
