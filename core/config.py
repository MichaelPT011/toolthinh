"""Central configuration for the browser-assisted Veo3 desktop clone."""

from pathlib import Path
import sys


def _runtime_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


ROOT_DIR = _runtime_root()
DATA_DIR = ROOT_DIR / "data"
OUTPUT_DIR = ROOT_DIR / "output"
DEFAULT_DOWNLOADS_DIR = Path.home() / "Downloads"
MANAGED_CHROME_DATA_DIR = DATA_DIR / "chrome-user-data"
MANAGED_BUNDLED_CHROME_DATA_DIR = DATA_DIR / "chrome-user-data-bundled"
MANAGED_BROWSER_DIR = DATA_DIR / "managed-browser"
UPDATE_CACHE_DIR = DATA_DIR / "updates"
VERSION_FILE = ROOT_DIR / "version.json"
BUNDLED_CHROME_DIR = ROOT_DIR / "chrome-win64"
BUNDLED_CHROME_NESTED_DIR = ROOT_DIR / "chrome-win64" / "chrome-win64"
CHROME_FOR_TESTING_JSON_URL = (
    "https://googlechromelabs.github.io/chrome-for-testing/"
    "last-known-good-versions-with-downloads.json"
)

OFFICIAL_UPDATE_REPO = "MichaelPT011/toolthinh"
OFFICIAL_UPDATE_MANIFEST_URL = f"https://raw.githubusercontent.com/{OFFICIAL_UPDATE_REPO}/main/latest.json"
OFFICIAL_RELEASE_PREFIX = f"https://github.com/{OFFICIAL_UPDATE_REPO}/releases/download/"

ACCOUNTS_FILE = DATA_DIR / "accounts.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
PROJECTS_DIR = DATA_DIR / "projects"

OUTPUT_VIDEOS = OUTPUT_DIR / "videos"
OUTPUT_IMAGES = OUTPUT_DIR / "images"
OUTPUT_WHISK = OUTPUT_DIR / "whisk"

DEFAULT_SETTINGS = {
    "video_delay_seconds": 5,
    "flow_delay_seconds": 2,
    "whisk_delay_seconds": 2,
    "output_dir": str(OUTPUT_DIR),
    "downloads_dir": str(DEFAULT_DOWNLOADS_DIR),
    "browser_path": "",
    "chrome_user_data_dir": str(MANAGED_CHROME_DATA_DIR),
    "chrome_profile_dir": "Default",
    "headless_automation": False,
    "show_browser_window": False,
    "watch_quiet_seconds": 4,
    "max_concurrent": 1,
    "batch_interval": 2,
    "update_manifest_url": OFFICIAL_UPDATE_MANIFEST_URL,
    "backend": "browser_assist",
}

VIDEO_TIMEOUT = 1800
IMAGE_TIMEOUT = 600
WHISK_TIMEOUT = 600
HTTP_TIMEOUT = 30

VIDEO_TOOL_URL = "https://labs.google/fx/tools/video-fx"
IMAGE_TOOL_URL = "https://labs.google/fx/tools/image-fx"
WHISK_TOOL_URL = "https://labs.google/fx/tools/whisk"
FLOW_HOME_URL = "https://labs.google/fx/tools/flow"
FLOW_LOGIN_URL = "https://accounts.google.com/ServiceLogin?continue=https%3A%2F%2Flabs.google%2Ffx%2Ftools%2Fflow"

APP_TITLE = "🧠Tool Veo3 của Thịnh"

SAFE_IMAGE_PRESET = {
    "num_images": 1,
    "download_quality": "1080p",
    "orientation": "landscape",
    "batch_mode": "parallel",
    "batch_concurrent": 2,
}

SAFE_VIDEO_PRESET = {
    "num_outputs": 1,
    "download_quality": "1080p",
    "aspect_ratio": "16:9",
    "duration": "8s",
    "batch_mode": "sequential",
    "batch_concurrent": 1,
}


def ensure_dirs() -> None:
    """Create all runtime directories used by the application."""
    for directory in [
        DATA_DIR,
        PROJECTS_DIR,
        OUTPUT_VIDEOS,
        OUTPUT_IMAGES,
        OUTPUT_WHISK,
        MANAGED_CHROME_DATA_DIR,
        MANAGED_BUNDLED_CHROME_DATA_DIR,
        MANAGED_BROWSER_DIR,
        UPDATE_CACHE_DIR,
    ]:
        directory.mkdir(parents=True, exist_ok=True)
