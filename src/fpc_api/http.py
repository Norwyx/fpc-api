"""HTTP con caché en disco (data/raw/) y User-Agent identificable."""
import gzip
import json
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
UA = "fpc-api/0.1 (open data project; https://github.com/fpc-api)"

_fetches = 0


def _read_cached(path: Path, max_age_days: float) -> str | None:
    if not path.exists():
        return None
    age = time.time() - path.stat().st_mtime
    if age > max_age_days * 86400:
        return None
    return path.read_text(encoding="utf-8")


def get(url: str, cache_key: str | None = None, max_age_days: float = 7.0) -> str:
    """GET → texto. Si cache_key existe y es fresco, no descarga."""
    global _fetches
    if cache_key:
        RAW.mkdir(parents=True, exist_ok=True)
        cached = _read_cached(RAW / f"{cache_key}.txt", max_age_days)
        if cached is not None:
            return cached
    req = Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
    last_err = None
    for attempt in range(3):
        try:
            with urlopen(req, timeout=30) as resp:
                body = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
                text = body.decode("utf-8")
                break
        except (HTTPError, URLError, TimeoutError) as e:
            last_err = e
            time.sleep(2 * (attempt + 1))
    else:
        raise RuntimeError(f"GET {url} falló tras 3 intentos: {last_err}")
    _fetches += 1
    time.sleep(0.4)
    if cache_key:
        (RAW / f"{cache_key}.txt").write_text(text, encoding="utf-8")
    return text


def fetches() -> int:
    return _fetches


def cache_forced(key: str) -> str | None:
    path = RAW / f"{key}.txt"
    return path.read_text(encoding="utf-8") if path.exists() else None


def json_get(url: str, cache_key: str | None = None, max_age_days: float = 7.0) -> dict:
    return json.loads(get(url, cache_key, max_age_days))
