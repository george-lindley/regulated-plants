import hashlib
import json
import os
import socket
import threading
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request


class DataManager:
    def __init__(
        self,
        app,
        mode: str,
        base_url: str,
        token: str,
        manifest_path: str,
        cache_dir: str,
        manifest_ttl_seconds: int = 3600,
        remote_timeout_seconds: int = 90,
    ):
        self.app = app
        self.mode = (mode or "local_sample").strip()
        self.base_url = (base_url or "").strip()
        self.token = (token or "").strip()
        self.manifest_path = manifest_path or "/manifest.json"
        self.cache_dir = cache_dir or "data_cache"
        self.manifest_ttl_seconds = max(0, int(manifest_ttl_seconds or 0))
        self.remote_timeout_seconds = max(1, int(remote_timeout_seconds or 0))
        self.last_checked = 0.0
        self.current_version = None
        self.lock = threading.Lock()
        self.refresh_in_progress = False

    @classmethod
    def from_app(cls, app):
        return cls(
            app=app,
            mode=app.config.get("DATA_MODE", "local_sample"),
            base_url=app.config.get("DATA_REMOTE_BASE_URL"),
            token=app.config.get("DATA_REMOTE_TOKEN"),
            manifest_path=app.config.get("DATA_MANIFEST_PATH", "/manifest.json"),
            cache_dir=app.config.get("DATA_CACHE_DIR", "data_cache"),
            manifest_ttl_seconds=app.config.get("DATA_MANIFEST_TTL_SECONDS", 3600),
            remote_timeout_seconds=app.config.get("DATA_REMOTE_TIMEOUT_SECONDS", 90),
        )

    def ensure_ready(self, force: bool = False):
        if self.mode != "remote_production":
            data_paths = self._local_paths()
            self._apply_data_paths(data_paths, version="local_sample")
            return data_paths

        if not self.base_url:
            raise ValueError("DATA_REMOTE_BASE_URL is required for remote_production mode")

        cache_dir = self._resolve_path(self.cache_dir)
        os.makedirs(cache_dir, exist_ok=True)
        cache_paths = self._cache_paths(cache_dir)
        cache_ready = self._cache_paths_ready(cache_paths)

        # Cache-first boot for production reliability.
        if cache_ready:
            local_manifest = self._read_json(cache_paths["manifest"])
            version = self._manifest_version(local_manifest) or "cached"
            data_paths = self._paths_from_cache(cache_paths)
            with self.lock:
                self._apply_data_paths(data_paths, version=version, changed=False, manifest=local_manifest)
            if force or not self._within_ttl():
                self._schedule_refresh()
            return data_paths

        # First-ever cold boot: block until initial data is downloaded.
        with self.lock:
            self.last_checked = time.time()
        data_paths, version, changed, manifest = self._sync_remote_data(cache_paths=cache_paths)
        with self.lock:
            self._apply_data_paths(data_paths, version=version, changed=changed, manifest=manifest)
        return data_paths

    def maybe_refresh(self):
        if self.mode != "remote_production" or self.manifest_ttl_seconds <= 0:
            return
        if self._within_ttl():
            return
        self._schedule_refresh()

    def _within_ttl(self) -> bool:
        if self.manifest_ttl_seconds <= 0:
            return False
        if self.last_checked <= 0:
            return False
        return (time.time() - self.last_checked) < self.manifest_ttl_seconds

    def _project_root(self) -> str:
        return os.path.abspath(os.path.join(self.app.root_path, os.pardir))

    def _resolve_path(self, path: str) -> str:
        if not path:
            return ""
        if os.path.isabs(path):
            return path
        return os.path.abspath(os.path.join(self._project_root(), path))

    def _local_paths(self) -> dict:
        db_path = self._resolve_path(self.app.config.get("LOCAL_SAMPLE_DB_PATH", "weeds.db"))
        geojson_dir = self._resolve_path(
            self.app.config.get(
                "LOCAL_SAMPLE_GEOJSON_DIR",
                os.path.join("app", "static", "data", "geographic"),
            )
        )
        return {
            "database_path": db_path,
            "geojson_dir": geojson_dir,
            "geojson_url_path": "/data/geojson/",
        }

    def _current_paths(self) -> dict:
        return {
            "database_path": self.app.config.get("DATABASE_PATH"),
            "geojson_dir": self.app.config.get("GEOJSON_DIR"),
            "geojson_url_path": self.app.config.get("GEOJSON_URL_PATH", "/data/geojson/"),
        }

    def _cache_is_ready(self) -> bool:
        db_path = self.app.config.get("DATABASE_PATH")
        geojson_dir = self.app.config.get("GEOJSON_DIR")
        if not db_path or not geojson_dir:
            return False
        return os.path.exists(db_path) and os.path.isdir(geojson_dir)

    def _cache_paths(self, cache_dir: str) -> dict:
        return {
            "cache_dir": cache_dir,
            "database_path": os.path.join(cache_dir, "weeds.db"),
            "geojson_dir": os.path.join(cache_dir, "geojson"),
            "manifest": os.path.join(cache_dir, "manifest.json"),
        }

    def _paths_from_cache(self, cache_paths: dict) -> dict:
        return {
            "database_path": cache_paths["database_path"],
            "regulatory_sources_path": None,
            "geojson_dir": cache_paths["geojson_dir"],
            "geojson_url_path": "/data/geojson/",
        }

    def _cache_paths_ready(self, cache_paths: dict) -> bool:
        db_path = cache_paths["database_path"]
        geojson_dir = cache_paths["geojson_dir"]
        if not (os.path.exists(db_path) and os.path.isdir(geojson_dir)):
            return False
        return any(name.lower().endswith(".geojson") for name in os.listdir(geojson_dir))

    def _release_metadata(self, manifest: dict, version: str = None) -> dict:
        manifest = manifest if isinstance(manifest, dict) else {}
        return {
            "version": version or manifest.get("version"),
            "generated_at": manifest.get("generated_at") or manifest.get("generatedAt"),
            "last_updated": manifest.get("last_updated") or manifest.get("lastUpdated"),
            "metrics": manifest.get("metrics"),
            "history": (
                manifest.get("release_history")
                or manifest.get("releaseHistory")
                or manifest.get("history")
                or manifest.get("releases")
            ),
        }

    def _apply_data_paths(self, data_paths: dict, version: str = None, changed: bool = False, manifest: dict = None):
        if not data_paths:
            return
        self.app.config["DATABASE_PATH"] = data_paths["database_path"]
        self.app.config["REGULATORY_SOURCES_PATH"] = data_paths.get("regulatory_sources_path")
        self.app.config["GEOJSON_DIR"] = data_paths["geojson_dir"]
        self.app.config["GEOJSON_URL_PATH"] = data_paths.get("geojson_url_path", "/data/geojson/")
        if version:
            self.app.config["DATA_VERSION"] = version

        release_metadata = self._release_metadata(manifest, version=version)
        if release_metadata.get("version"):
            self.app.config["DATA_RELEASE_VERSION"] = release_metadata["version"]
        self.app.config["DATA_RELEASE_GENERATED_AT"] = release_metadata.get("generated_at")
        self.app.config["DATA_RELEASE_LAST_UPDATED"] = release_metadata.get("last_updated")
        if isinstance(release_metadata.get("metrics"), dict):
            self.app.config["DATA_RELEASE_METRICS"] = release_metadata["metrics"]
        else:
            self.app.config.pop("DATA_RELEASE_METRICS", None)
        if isinstance(release_metadata.get("history"), list):
            self.app.config["DATA_RELEASE_HISTORY"] = release_metadata["history"]
        else:
            self.app.config.pop("DATA_RELEASE_HISTORY", None)

        if changed or version != self.current_version:
            self.app.extensions.pop("state_db", None)
            self.app.extensions.pop("species_db", None)

        self.current_version = version

    def _manifest_version(self, manifest: dict) -> str:
        if not isinstance(manifest, dict):
            return "remote"
        return (
            manifest.get("version")
            or manifest.get("generated_at")
            or manifest.get("last_updated")
            or "remote"
        )

    def _sync_remote_data(self, cache_paths: dict = None):
        if cache_paths is None:
            cache_dir = self._resolve_path(self.cache_dir)
            os.makedirs(cache_dir, exist_ok=True)
            cache_paths = self._cache_paths(cache_dir)

        manifest = self._fetch_remote_manifest()
        local_manifest = self._read_json(cache_paths["manifest"])
        changed = manifest != local_manifest
        version = self._manifest_version(manifest)

        # Download only changed/missing artifacts, and only publish the new
        # local manifest after all downloads verify successfully.
        self._download_artifacts(manifest, cache_paths)
        if changed:
            self._write_json(cache_paths["manifest"], manifest)

        return self._paths_from_cache(cache_paths), version, changed, manifest

    def _download_artifacts(self, manifest: dict, cache_paths: dict):
        cache_dir = cache_paths["cache_dir"]
        artifacts = manifest.get("artifacts", {})
        db_entry = artifacts.get("weeds_db") or manifest.get("weeds_db")
        geojson_files = manifest.get("geojson_files") or manifest.get("geojson", {}).get("files") or []
        geojson_base = (
            artifacts.get("geojson_base_path")
            or manifest.get("geojson_base_path")
            or "/artifacts/geojson"
        )

        if not db_entry:
            raise ValueError("Manifest missing weeds_db artifact")

        db_entry = self._normalize_entry(db_entry)
        download_targets = [(db_entry, cache_paths["database_path"])]

        geojson_dir = cache_paths["geojson_dir"]
        os.makedirs(geojson_dir, exist_ok=True)

        for item in geojson_files:
            if isinstance(item, str):
                entry = {"path": self._join_path(geojson_base, item)}
            else:
                entry = self._normalize_entry(item)
                if not entry.get("path"):
                    name = entry.get("name") or entry.get("filename")
                    if name:
                        entry["path"] = self._join_path(geojson_base, name)
                    else:
                        continue

            filename = os.path.basename(entry["path"])
            if not filename:
                continue
            dest_path = os.path.join(geojson_dir, filename)
            download_targets.append((entry, dest_path))

        staging_dir = os.path.join(cache_dir, ".staging", str(uuid.uuid4()))
        os.makedirs(staging_dir, exist_ok=True)
        pending_replacements = []

        try:
            for entry, dest_path in download_targets:
                expected = (entry.get("sha256") or entry.get("checksum") or "").strip()
                if expected and os.path.exists(dest_path):
                    current = self._sha256(dest_path)
                    if current.lower() == expected.lower():
                        continue

                stage_name = f"{len(pending_replacements):04d}_{os.path.basename(dest_path)}"
                stage_path = os.path.join(staging_dir, stage_name)
                data = self._download_entry_bytes(entry)
                with open(stage_path, "wb") as f:
                    f.write(data)

                if expected:
                    actual = self._sha256(stage_path)
                    if actual.lower() != expected.lower():
                        raise ValueError(
                            f"Checksum mismatch for {dest_path} "
                            f"(expected {expected}, got {actual})"
                        )

                pending_replacements.append((stage_path, dest_path))

            for stage_path, dest_path in pending_replacements:
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                os.replace(stage_path, dest_path)
        finally:
            if os.path.isdir(staging_dir):
                for name in os.listdir(staging_dir):
                    try:
                        os.remove(os.path.join(staging_dir, name))
                    except OSError:
                        pass
                try:
                    os.rmdir(staging_dir)
                except OSError:
                    pass

    def _normalize_entry(self, entry):
        if isinstance(entry, dict):
            return dict(entry)
        if isinstance(entry, str):
            return {"path": entry}
        return {}

    def _join_path(self, base: str, name: str) -> str:
        base = (base or "").rstrip("/")
        name = (name or "").lstrip("/")
        return f"{base}/{name}"

    def _download_entry_bytes(self, entry: dict) -> bytes:
        path = entry.get("path")
        if not path:
            return b""
        url = urllib.parse.urljoin(self.base_url.rstrip("/") + "/", path.lstrip("/"))

        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        headers["Accept"] = "application/octet-stream"

        return self._fetch_bytes(url, headers=headers)

    def _fetch_json(self, url: str) -> dict:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        data = self._fetch_bytes(url, headers=headers)
        return json.loads(data.decode("utf-8"))

    def _fetch_remote_manifest(self) -> dict:
        manifest_url = urllib.parse.urljoin(
            self.base_url.rstrip("/") + "/",
            self.manifest_path.lstrip("/"),
        )
        first = self._fetch_json(manifest_url)
        if not isinstance(first, dict):
            raise ValueError("Invalid manifest payload")

        # Support pointer-style manifest documents:
        # { "manifest_path": "/releases/<version>/manifest.json", "version": "..." }
        pointer_path = (
            first.get("manifest_path")
            or first.get("release_manifest_path")
            or first.get("current_manifest_path")
        )
        if pointer_path and "artifacts" not in first:
            second_url = urllib.parse.urljoin(
                self.base_url.rstrip("/") + "/",
                str(pointer_path).lstrip("/"),
            )
            second = self._fetch_json(second_url)
            if not isinstance(second, dict):
                raise ValueError("Invalid release manifest payload")
            if "version" not in second and first.get("version"):
                second["version"] = first.get("version")
            return second

        return first

    def _fetch_bytes(self, url: str, headers: dict = None) -> bytes:
        req = urllib.request.Request(url, headers=headers or {})
        attempts = 3
        last_exc = None

        for attempt in range(1, attempts + 1):
            try:
                with urllib.request.urlopen(req, timeout=self.remote_timeout_seconds) as resp:
                    return resp.read()
            except urllib.error.HTTPError as exc:
                # Retry transient server-side failures only.
                if exc.code >= 500 and attempt < attempts:
                    last_exc = exc
                    time.sleep(1)
                    continue
                raise
            except (TimeoutError, socket.timeout, urllib.error.URLError) as exc:
                last_exc = exc
                if attempt < attempts:
                    time.sleep(1)
                    continue
                raise

        if last_exc:
            raise last_exc
        raise RuntimeError(f"Failed to fetch bytes from {url}")

    def _sha256(self, path: str) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def _read_json(self, path: str) -> dict:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _write_json(self, path: str, data: dict):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)

    def _schedule_refresh(self):
        with self.lock:
            if self.refresh_in_progress:
                return
            self.refresh_in_progress = True
            self.last_checked = time.time()

        thread = threading.Thread(target=self._refresh_worker, daemon=True)
        thread.start()

    def _refresh_worker(self):
        try:
            cache_dir = self._resolve_path(self.cache_dir)
            os.makedirs(cache_dir, exist_ok=True)
            cache_paths = self._cache_paths(cache_dir)
            data_paths, version, changed, manifest = self._sync_remote_data(cache_paths=cache_paths)
            with self.lock:
                self._apply_data_paths(data_paths, version=version, changed=changed, manifest=manifest)
        except Exception as exc:
            self.app.logger.error(f"Periodic data refresh failed: {exc}")
        finally:
            with self.lock:
                self.refresh_in_progress = False
