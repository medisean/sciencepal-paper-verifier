"""共用配置：从项目根目录 .env 读取 SciencePal 凭据，避免把密钥写进代码。"""
import os
from pathlib import Path


def load_env(env_path: Path | None = None) -> None:
    """极简 .env 加载器（不依赖 python-dotenv）。不会覆盖已存在的环境变量。"""
    if env_path is None:
        env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        raise FileNotFoundError(f"未找到 .env：{env_path}")
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


def get_config() -> tuple[str, str]:
    load_env()
    api_key = os.environ.get("SCIENCEPAL_API_KEY", "").strip()
    base_url = os.environ.get("SCIENCEPAL_BASE_URL", "https://sciencepal.ai/api").strip()
    if not api_key:
        raise RuntimeError("SCIENCEPAL_API_KEY 为空，请在 .env 中配置")
    return api_key, base_url


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent
