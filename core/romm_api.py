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
            error_detail = e.read().decode('utf-8')
            print(f"HTTP Error {e.code} on {method} {url}: {error_detail}")
            return None
        except Exception as e:
            print(f"Error connecting to RomM API ({url}): {e}")
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

    def get_all_roms(self, use_cache=True):
        """Fetch all roms from RomM handling pagination, with local caching."""
        cache_dir = "cache"
        cache_file = os.path.join(cache_dir, "all_roms.json")
        
        if use_cache and os.path.exists(cache_file):
            try:
                # Check if cache is older than 24 hours (optional, but good for freshness)
                # For now, just use it if it exists to speed up the UI
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading all_roms cache: {e}")

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
            
        if all_roms:
            try:
                os.makedirs(cache_dir, exist_ok=True)
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(all_roms, f)
            except Exception as e:
                print(f"Error saving all_roms cache: {e}")
                
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

    def add_roms_to_collection(self, collection_id, rom_ids):
        """Add multiple ROMs to a collection in RomM by updating the collection's ROM list."""
        if not config.romm_url or not config.romm_api_key:
            return False, "API not configured"
            
        # 1. Fetch current collection details to get existing ROMs
        get_endpoint = f"/collections/{collection_id}"
        current_collection = self._make_request(get_endpoint)
        if not current_collection:
            return False, "Failed to fetch collection details"
            
        # 2. Merge existing ROM IDs with new ones
        existing_ids = set(current_collection.get('rom_ids', []))
        new_ids = set(rom_ids)
        combined_ids = list(existing_ids.union(new_ids))
        
        # 3. Prepare PUT data (RomM v3 expects form data for PUT /api/collections/{id})
        # Note: is_public is a query parameter in RomM v3
        is_public = current_collection.get('is_public', False)
        put_endpoint = f"/collections/{collection_id}?is_public={'true' if is_public else 'false'}"
        
        # rom_ids must be a JSON-encoded string
        form_data = {
            "name": current_collection.get('name'),
            "description": current_collection.get('description', ""),
            "rom_ids": json.dumps(combined_ids)
        }
        
        # 4. Execute PUT using x-www-form-urlencoded
        url = config.romm_url.rstrip("/") + "/api" + put_endpoint
        headers = self._get_headers()
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        
        data = urllib.parse.urlencode(form_data).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers=headers, method="PUT")
        
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode('utf-8'))
                if result:
                    return True, f"Collection updated with {len(new_ids)} new ROMs"
        except urllib.error.HTTPError as e:
            error_detail = e.read().decode('utf-8')
            print(f"HTTP Error {e.code} on PUT {url}: {error_detail}")
        except Exception as e:
            print(f"Error updating collection ({url}): {e}")
            
        return False, "Failed to update collection"

    def get_platforms(self):
        """Fetch all platforms from RomM."""
        if not config.romm_url or not config.romm_api_key:
            return []
            
        data = self._make_request("/platforms")
        if data is not None:
            return data # Should be a list of platforms
        return []

    def upload_rom(self, file_path, platform_id, filename=None):
        """Upload a ROM file to RomM using multipart/form-data."""
        if not config.romm_url or not config.romm_api_key:
            return None
            
        if not filename:
            filename = os.path.basename(file_path)
            
        # RomM v3 endpoint usually needs the trailing slash for POST
        url = config.romm_url.rstrip("/") + "/api/roms/"
        
        # Create a unique boundary
        boundary = "FlipRommBoundary" + os.urandom(8).hex()
        
        # Build the multipart body
        # RomM v3 requires the field name to match the filename header
        header = (
            f"--{boundary}\r\n"
            f"Content-Disposition: form-data; name=\"{filename}\"; filename=\"{filename}\"\r\n"
            f"Content-Type: application/octet-stream\r\n\r\n"
        ).encode('utf-8')
        footer = f"\r\n--{boundary}--\r\n".encode('utf-8')
        
        try:
            file_size = os.path.getsize(file_path)
            total_size = len(header) + file_size + len(footer)
            
            headers = {
                "Authorization": f"Bearer {config.romm_api_key}",
                "x-upload-platform": str(platform_id),
                "x-upload-filename": filename,
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Content-Length": str(total_size)
            }
            
            # For handhelds, we try to avoid loading too much into memory.
            # However, constructing a streaming multipart request with urllib is complex.
            # Since most handheld ROMs (GBA, NES, etc.) are small, we'll build the body in memory
            # but print a warning for very large files.
            if file_size > 100 * 1024 * 1024:
                print(f"Warning: Uploading large file {filename} ({file_size} bytes). This may stress device memory.")
                
            with open(file_path, 'rb') as f:
                body = header + f.read() + footer
                
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=3600) as response:
                return json.loads(response.read().decode('utf-8'))
                
        except urllib.error.HTTPError as e:
            error_detail = e.read().decode('utf-8')
            print(f"HTTP Error {e.code} on ROM upload: {error_detail}")
            return None
        except Exception as e:
            print(f"Error uploading ROM ({filename}): {e}")
            return None

    def upload_screenshot(self, rom_id, file_path):
        """Upload a screenshot for a specific ROM using multipart/form-data."""
        if not config.romm_url or not config.romm_api_key:
            return None
            
        # RomM v3 expects rom_id as a query parameter
        url = f"{config.romm_url.rstrip('/')}/api/screenshots?rom_id={rom_id}"
        filename = os.path.basename(file_path)
        
        # Create a unique boundary
        boundary = "FlipRommScreenshotBoundary" + os.urandom(8).hex()
        
        # Build the multipart body
        def _get_file_part(name, filename, content_type):
            return (
                f"--{boundary}\r\n"
                f"Content-Disposition: form-data; name=\"{name}\"; filename=\"{filename}\"\r\n"
                f"Content-Type: {content_type}\r\n\r\n"
            ).encode('utf-8')

        try:
            # For screenshots, we assume they are relatively small, so reading into memory is fine
            with open(file_path, 'rb') as f:
                file_content = f.read()
            
            # Construct the payload
            # Field name must be 'screenshotFile'
            part_file = _get_file_part("screenshotFile", filename, "image/png")
            footer = f"\r\n--{boundary}--\r\n".encode('utf-8')
            
            body = part_file + file_content + footer
            
            headers = {
                "Authorization": f"Bearer {config.romm_api_key}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Content-Length": str(len(body))
            }
            
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=60) as response:
                return json.loads(response.read().decode('utf-8'))
                
        except urllib.error.HTTPError as e:
            error_detail = e.read().decode('utf-8')
            print(f"HTTP Error {e.code} on screenshot upload: {error_detail}")
            return None
        except Exception as e:
            print(f"Error uploading screenshot ({filename}): {e}")
            return None

romm_api = RommAPI()
