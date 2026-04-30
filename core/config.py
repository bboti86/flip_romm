import os
import json

SETTINGS_FILE = "settings.json"

DEFAULT_SETTINGS = {
    "romm_url": "",
    "romm_api_key": ""
}

class Config:
    def __init__(self):
        self.settings = DEFAULT_SETTINGS.copy()
        self.load()

    def load(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r') as f:
                    data = json.load(f)
                    self.settings.update(data)
            except Exception as e:
                print(f"Error loading settings: {e}")

    def save(self):
        try:
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")

    @property
    def romm_url(self):
        return self.settings.get("romm_url", "")

    @romm_url.setter
    def romm_url(self, value):
        self.settings["romm_url"] = value
        self.save()

    @property
    def romm_api_key(self):
        return self.settings.get("romm_api_key", "")

    @romm_api_key.setter
    def romm_api_key(self, value):
        self.settings["romm_api_key"] = value
        self.save()

config = Config()
