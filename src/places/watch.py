import os
import sys
import threading
import subprocess
import signal
import platform
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from .places_utils import load_source
import plistlib
import hashlib
import psutil  # Add this import

PID_FILE = "watcher.pid"


class PlacesEventHandler(FileSystemEventHandler):
    def __init__(self):
        super().__init__()
        self.observer = None
        self.env_watchers = {}
        self.watch_envs = self.load_watch_environments()
        self.ignore_changes = False
        self._file_hashes = {}
        self._watched_files = {"places.yaml", ".places/places.enc.yaml"}
        self._lock = threading.Lock()
        self._processing = set()

    def load_watch_environments(self):
        source = load_source("places.yaml")
        watch_envs = []
        envs = source.get("environments", {})
        for env_name, env_config in envs.items():
            if env_config.get("watch", False):
                print(f"Watching changes / auto-generating for environment: {env_name}")
                watch_envs.append(env_name)
        return watch_envs

    def reload_watch_environments(self):
        new_watch_envs = self.load_watch_environments()

        added_envs = [env for env in new_watch_envs if env not in self.watch_envs]
        if added_envs:
            print(f"New environments to watch: {', '.join(added_envs)}")

            subprocess.run(
                [sys.executable, "-m", "places.cli", "generate", "environment"]
                + added_envs
            )

        self.watch_envs = new_watch_envs

    def get_file_hash(self, path):
        try:
            hasher = hashlib.sha256()
            with open(path, "rb") as f:
                buf = f.read()
                hasher.update(buf)
            return hasher.hexdigest()
        except Exception as e:
            print(f"Error hashing file {path}: {e}")
            return None

    def on_modified(self, event):
        if event.is_directory:
            return

        try:
            event_path = Path(event.src_path).resolve()
            base_path = Path.cwd().resolve()
            rel_path = event_path.relative_to(base_path)
            rel_path_str = str(rel_path)

            if rel_path_str not in self._watched_files:
                return

            current_hash = self.get_file_hash(event_path)
            if current_hash is None:
                return

            previous_hash = self._file_hashes.get(rel_path_str)
            if current_hash == previous_hash:
                return

            self._file_hashes[rel_path_str] = current_hash

            with self._lock:
                if event_path in self._processing:
                    return
                self._processing.add(event_path)

            try:
                if rel_path_str == "places.yaml":
                    print("places.yaml changed. Running 'places encrypt'...")
                    subprocess.run([sys.executable, "-m", "places.cli", "encrypt"])
                    subprocess.run(
                        [sys.executable, "-m", "places.cli", "sync", "gitignore"]
                    )

                    self.reload_watch_environments()
                elif rel_path_str == ".places/places.enc.yaml":
                    print("places.enc.yaml changed. Running 'places decrypt'...")
                    subprocess.run([sys.executable, "-m", "places.cli", "decrypt"])
                    subprocess.run(
                        [sys.executable, "-m", "places.cli", "sync", "gitignore"]
                    )
                    if self.watch_envs:
                        print("Running 'places generate environment'...")
                        subprocess.run(
                            [
                                sys.executable,
                                "-m",
                                "places.cli",
                                "generate",
                                "environment",
                            ]
                            + self.watch_envs
                        )
            finally:
                with self._lock:
                    self._processing.discard(event_path)
        except Exception as e:
            print(f"Error processing file change: {e}")


def get_project_name():
    try:
        remote_url = subprocess.check_output(
            ["git", "config", "--get", "remote.origin.url"], text=True
        ).strip()

        project_name = remote_url.split("/")[-1].replace(".git", "")
        return project_name
    except:
        return Path.cwd().name


def create_systemd_service():
    project_name = get_project_name()
    service_name = f"places-watcher-{project_name}.service"
    service_path = Path.home() / ".config/systemd/user"
    service_path.mkdir(parents=True, exist_ok=True)

    executable_path = sys.executable
    places_path = os.getcwd()

    service_content = f"""[Unit]
Description=places watcher service
After=network.target

[Service]
Type=simple
WorkingDirectory={places_path}
Environment="PYTHONPATH={places_path}"
ExecStart={executable_path} -m places.cli watch start
Restart=always

[Install]
WantedBy=default.target
"""

    service_file = service_path / service_name
    with open(service_file, "w") as f:
        f.write(service_content)

    subprocess.run(["systemctl", "--user", "enable", service_name])
    subprocess.run(["systemctl", "--user", "start", service_name])

    return True, {
        "service_path": str(service_file),
        "log_cmd": "journalctl --user -u " + service_name,
    }


def create_macos_launch_agent():
    project_name = get_project_name()
    agent_name = f"com.places.watcher.{project_name}"
    agent_path = Path.home() / "Library/LaunchAgents"
    agent_path.mkdir(parents=True, exist_ok=True)

    executable_path = str(Path(sys.executable).resolve())
    places_path = str(Path.cwd().resolve())
    log_dir = Path.home() / "Library/Logs/places" / project_name
    log_dir.mkdir(parents=True, exist_ok=True)

    places_yaml = Path(places_path) / "places.yaml"
    places_enc_yaml = Path(places_path) / ".places" / "places.enc.yaml"
    log_file = log_dir / "places-watcher.log"
    err_log_file = log_dir / "places-watcher.err.log"

    for log in [log_file, err_log_file]:
        if not log.exists():
            log.touch(mode=0o644)
            os.chown(log, os.getuid(), os.getgid())

    venv_path = os.environ.get("VIRTUAL_ENV")
    env_vars = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": places_path,
        "LANG": "en_US.UTF-8",
        "LC_ALL": "en_US.UTF-8",
        "PYTHONUNBUFFERED": "1",
    }

    if venv_path:
        env_vars["VIRTUAL_ENV"] = venv_path
        venv_bin = str(Path(venv_path) / "bin")
        env_vars["PATH"] = f"{venv_bin}:{env_vars['PATH']}"

    plist_content = {
        "Label": agent_name,
        "ProgramArguments": [
            executable_path,
            "-m",
            "places.cli",
            "watch",
            "start",
        ],
        "WorkingDirectory": places_path,
        "WatchPaths": [str(places_yaml), str(places_enc_yaml)],
        "RunAtLoad": True,
        "StandardOutPath": str(log_file),
        "StandardErrorPath": str(err_log_file),
        "EnvironmentVariables": env_vars,
    }

    plist_file = agent_path / f"{agent_name}.plist"

    try:
        if not os.access(executable_path, os.X_OK):
            raise Exception(f"Python executable not accessible: {executable_path}")
        if not os.access(places_path, os.R_OK | os.X_OK):
            raise Exception(f"Working directory not accessible: {places_path}")
        if not places_yaml.exists():
            raise Exception(f"places.yaml not found at: {places_yaml}")

        with open(log_file, "w") as f:
            f.write(
                f"places Watcher Configuration:\n"
                f"Python: {executable_path}\n"
                f"Working Dir: {places_path}\n"
                f"Virtual Env: {venv_path or 'None'}\n"
            )

        with open(plist_file, "wb") as f:
            plistlib.dump(plist_content, f)

        os.chmod(plist_file, 0o644)

        subprocess.run(
            ["launchctl", "unload", str(plist_file)], capture_output=True, check=False
        )

        list_result = subprocess.run(
            ["launchctl", "list", agent_name], capture_output=True, text=True
        )

        if list_result.returncode != 0:
            print(
                "Warning: LaunchAgent may not be running. Try running 'launchctl load -w "
                + str(plist_file)
                + "'"
            )

        return True, {
            "service_path": str(plist_file),
            "log_path": str(log_file),
            "error_log_path": str(err_log_file),
        }

    except Exception as e:
        print(f"Error setting up LaunchAgent: {str(e)}")
        return False, {}


def get_macos_launch_agent_details():
    project_name = get_project_name()
    agent_name = f"com.places.watcher.{project_name}"
    agent_path = Path.home() / "Library/LaunchAgents" / f"{agent_name}.plist"
    return agent_name, agent_path


def setup_system_service():
    system = platform.system()
    if system == "Linux":
        success, paths = create_systemd_service()
        return success, paths
    elif system == "Darwin":  # macOS
        success, paths = create_macos_launch_agent()
        return success, paths
    return False, {}


def remove_systemd_service():
    project_name = get_project_name()
    service_name = f"places-watcher-{project_name}.service"
    service_path = Path.home() / ".config/systemd/user" / service_name

    if service_path.exists():
        subprocess.run(["systemctl", "--user", "stop", service_name])
        subprocess.run(["systemctl", "--user", "disable", service_name])
        service_path.unlink()
        return True, str(service_path)
    return False, None


def remove_macos_launch_agent():
    agent_name, agent_path = get_macos_launch_agent_details()

    subprocess.run(["launchctl", "unload", str(agent_path)], capture_output=True)
    subprocess.run(["launchctl", "remove", agent_name], capture_output=True)

    if agent_path.exists():
        agent_path.unlink()
        return True, str(agent_path)
    return False, None


def remove_system_service():
    system = platform.system()
    if system == "Linux":
        return remove_systemd_service()
    elif system == "Darwin":  # macOS
        return remove_macos_launch_agent()
    return False, None


def get_daemon_log_paths():
    project_name = get_project_name()
    log_dir = Path.home() / ".places" / "logs" / project_name
    log_dir.mkdir(parents=True, exist_ok=True)
    return {"log_file": log_dir / "watcher.log", "pid_file": log_dir / "watcher.pid"}


def daemonize():
    """Fork the process to run as a daemon."""
    working_dir = os.getcwd()

    try:
        pid = os.fork()
        if pid > 0:
            sys.exit(0)
    except OSError as err:
        sys.stderr.write(f"fork #1 failed: {err}\n")
        sys.exit(1)

    os.setsid()
    os.umask(0)

    try:
        pid = os.fork()
        if pid > 0:
            sys.exit(0)
    except OSError as err:
        sys.stderr.write(f"fork #2 failed: {err}\n")
        sys.exit(1)

    sys.stdout.flush()
    sys.stderr.flush()

    with open(os.devnull, "r") as f:
        os.dup2(f.fileno(), sys.stdin.fileno())

    os.chdir(working_dir)

    paths = get_daemon_log_paths()
    pid_file = paths["pid_file"]
    with open(pid_file, "w") as f:
        f.write(str(os.getpid()))
    os.chmod(pid_file, 0o644)


def start_watch(service=False, daemon=False):
    if service:
        success, paths = setup_system_service()
        if success:
            print(
                f"places watcher installed as system service on {platform.system()} at"
            )
            print(f"Service location: {paths.get('service_path')}")
            if "log_cmd" in paths:  # Linux
                print(f"View logs with: {paths.get('log_cmd')}")
            else:  # macOS
                print(f"Log file: {paths.get('log_path')}")
                print(f"Error log: {paths.get('error_log_path')}")
            print("Uninstall service with: places watch stop --service")
            return
        else:
            print(f"Failed to install system service on {platform.system()}")
            return

    if daemon:
        paths = get_daemon_log_paths()
        log_file = paths["log_file"]
        pid_file = paths["pid_file"]

        if pid_file.exists():
            pid_file.unlink()

        print("Starting places watcher as daemon")
        print(f"Log file: {log_file}")
        print(f"PID file: {pid_file}")
        print("Stop daemon with: places watch stop --daemon")

        log_handle = open(log_file, "a+")

        if platform.system() != "Windows":
            daemonize()

            os.dup2(log_handle.fileno(), sys.stdout.fileno())
            os.dup2(log_handle.fileno(), sys.stderr.fileno())

        try:
            _run_watcher()
        finally:
            if pid_file.exists():
                pid_file.unlink()
            log_handle.close()
        return

    _run_watcher()


def _run_watcher():
    """Extract the main watcher logic to avoid code duplication"""
    path = os.getcwd()
    places_dir = os.path.join(path, ".places")

    event_handler = PlacesEventHandler()

    subprocess.run([sys.executable, "-m", "places.cli", "encrypt"])

    if event_handler.watch_envs:
        print("Running initial generate command...")
        subprocess.run(
            [sys.executable, "-m", "places.cli", "generate", "environment"]
            + event_handler.watch_envs
        )

    for watched_file in event_handler._watched_files:
        file_path = Path(watched_file).resolve()
        file_hash = event_handler.get_file_hash(file_path)
        if file_hash:
            event_handler._file_hashes[watched_file] = file_hash

    observer = Observer()
    observer.schedule(event_handler, path=path, recursive=False)

    if os.path.exists(places_dir):
        observer.schedule(event_handler, path=places_dir, recursive=False)
        print(f"Watching directories:\n- {path}\n- {places_dir}")
    else:
        print(f"Watching directory:\n- {path}")

    observer.start()
    print("Watcher started. Press Ctrl+C to stop.")

    try:
        while True:
            import time

            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        observer.join()
        print("\nWatcher stopped.")


def check_running_watchers():
    """Check for any running places watchers and return their details."""
    running = {"service": None, "daemon": None, "processes": []}

    project_name = get_project_name()
    if platform.system() == "Linux":
        service_name = f"places-watcher-{project_name}.service"
        result = subprocess.run(
            ["systemctl", "--user", "is-active", service_name],
            capture_output=True,
            text=True,
        )
        if result.stdout.strip() == "active":
            running["service"] = service_name
    elif platform.system() == "Darwin":
        agent_name = f"com.places.watcher.{project_name}"
        result = subprocess.run(
            ["launchctl", "list", agent_name], capture_output=True, text=True
        )
        if result.returncode == 0:
            running["service"] = agent_name

    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            if proc.info["name"] and "python" in proc.info["name"].lower():
                cmdline = proc.info["cmdline"]
                if "watch" in cmdline and "start" in cmdline:
                    if "-d" in cmdline or "--daemon" in cmdline:
                        running["daemon"] = proc.info["pid"]
                    else:
                        running["processes"].append(proc.info["pid"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return running


def stop_watch(service=False, daemon=False):
    """Stop the watcher, handling all running instances."""
    running = check_running_watchers()
    stopped_something = False

    if service and running["service"]:
        success, service_path = remove_system_service()
        if success:
            print(f"Places watcher system service removed from {platform.system()}")
            print(f"Removed service: {service_path}")
            stopped_something = True
        else:
            print(f"Failed to remove system service on {platform.system()}")

    if daemon and running["daemon"]:
        try:
            os.kill(running["daemon"], signal.SIGTERM)
            print(f"Stopped daemon process (PID: {running['daemon']})")
            stopped_something = True
        except ProcessLookupError:
            print(f"Daemon process (PID: {running['daemon']}) not found")
        except Exception as e:
            print(f"Error stopping daemon: {e}")

    if not (service or daemon) or (daemon and running["processes"]):
        for pid in running["processes"]:
            try:
                os.kill(pid, signal.SIGTERM)
                print(f"Stopped watcher process (PID: {pid})")
                stopped_something = True
            except ProcessLookupError:
                continue
            except Exception as e:
                print(f"Error stopping process {pid}: {e}")

    pid_file = get_daemon_log_paths()["pid_file"]
    if pid_file.exists():
        try:
            pid_file.unlink()
        except Exception:
            pass

    if not stopped_something:
        if daemon:
            print("No daemon process is running")
        elif service:
            print("No service is running")
        else:
            print("No watcher processes are running")
