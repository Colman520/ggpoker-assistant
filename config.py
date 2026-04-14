import json
import os


class Config:
    """GGPoker 助手配置管理"""

    DEFAULT_CONFIG = {
        "window_title_keyword": "GGPoker",
        "capture_interval": 0.8,
        "simulation_count": 20000,
        "default_opponents": 5,
        "regions": {
            "my_cards": [0.42, 0.72, 0.16, 0.12],
            "community_cards": [0.25, 0.38, 0.50, 0.10],
            "pot": [0.42, 0.30, 0.16, 0.05],
            "bet_amount": [0.42, 0.85, 0.16, 0.04],
        },
        "recognition": {
            "match_threshold": 0.80,
            "card_aspect_ratio": 0.7,
            "suit_min_pixel_ratio": 0.015,
            "spade_brightness_threshold": 70,
        },
        "gui": {
            "opacity": 0.88,
            "always_on_top": True,
            "position": [50, 50],
            "width": 320,
            "height": 520,
        },
    }

    def __init__(self, config_path="config.json"):
        self.config_path = config_path
        self.data = self._deep_copy(self.DEFAULT_CONFIG)
        self.load()

    def _deep_copy(self, obj):
        if isinstance(obj, dict):
            return {k: self._deep_copy(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._deep_copy(i) for i in obj]
        return obj

    def load(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    self._deep_update(self.data, saved)
                print(f"✅ 已加载配置: {self.config_path}")
            except Exception as e:
                print(f"⚠️ 配置加载失败，使用默认配置: {e}")
        else:
            print("ℹ️ 使用默认配置（首次运行）")

    def save(self):
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
        print(f"✅ 配置已保存: {self.config_path}")

    def _deep_update(self, base, update):
        for key, value in update.items():
            if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                self._deep_update(base[key], value)
            else:
                base[key] = value

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value
