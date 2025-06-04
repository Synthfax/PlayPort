import requests
from pathlib import Path
import os
import subprocess
import sys
import re
import json
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

# --- Global Configurations and Data ---

# Define a base directory for all servers relative to the script's location
# This will be initialized correctly in main() based on whether it's frozen (PyInstaller) or not.
SERVERS_DIR = Path("./servers") 

# List of supported server software options for user selection
SOFTWARE_OPTIONS = [
    "Vanilla", "Forge", "Fabric", "NeoForge", "Quilt",
    "Spigot", "Paper", "Purpur", "Pufferfish", "Folia",
    "BungeeCord", "Velocity", "Waterfall", "Nukkit", "PocketMine-MP"
]

# Dictionary mapping software types to their API/download URLs
# Comments indicate whether the URL is a direct template or requires further resolution.
versions_urls = {
    "vanilla": "https://launchermeta.mojang.com/mc/game/version_manifest.json", # Requires multiple API calls to find server JAR URL.
    "paper": "https://api.papermc.io/v2/projects/paper", # Requires API call to get latest build number.
    "folia": "https://api.papermc.io/v2/projects/folia", # Requires API call to get latest build number.
    "velocity": "https://api.papermc.io/v2/projects/velocity", # Requires API call to get latest build number.
    "waterfall": "https://api.papermc.io/v2/projects/waterfall", # Requires API call to get latest build number.
    "bungeecord": "https://ci.md-5.net/job/BungeeCord/api/json?tree=builds[number]", # Requires API call to get build numbers.
    "nukkit": "https://ci.opencollab.dev/job/NukkitX/job/Nukkit/job/master/lastSuccessfulBuild/artifact/target/nukkit-1.0-SNAPSHOT.jar", # Static URL for the latest snapshot.
    "forge": "https://files.minecraftforge.net/maven/net/minecraftforge/forge/maven-metadata.xml", # Requires XML parsing.
    "pocketmine-mp": "https://api.github.com/repos/pmmp/PocketMine-MP/releases", # Requires API call to find the .phar asset URL. Note: Changed key to match SOFTWARE_OPTIONS.
    "fabric": "https://meta.fabricmc.net/v2/versions/loader", # Requires API call to get loader versions.
    "neoforge": "https://maven.neoforged.net/releases/net/neoforged/neoforge/maven-metadata.xml", # Requires XML parsing.
    "quilt": "https://meta.quiltmc.org/v3/versions/installer", # Requires API call to get installer versions.
    "spigot": "https://hub.spigotmc.org/versions/", # Requires HTML parsing.
    "purpur": "https://api.purpurmc.org/v2/purpur/", # Requires API call to get versions.
    "pufferfish": "https://ci.pufferfish.host/view/all/api/json", # Requires multiple API calls to resolve artifact URL.
}

# Dummy versions for fallback if API calls fail
DUMMY_VERSIONS = [f"1.{i}" for i in range(100, 0, -1)]

# --- Utility Functions ---

def version_key(v):
    """
    Helper function to sort version strings numerically.
    Handles versions with multiple dots and hyphens by attempting to convert
    each segment to an integer, falling back to 0 for non-numeric parts.
    """
    parts = re.split(r'[.-]', v) # Split by both dot and hyphen
    numeric_parts = []
    for part in parts:
        try:
            numeric_parts.append(int(part))
        except ValueError:
            numeric_parts.append(0) # Treat non-numeric parts as 0 for sorting purposes
    return tuple(numeric_parts)

def fetch_versions(software: str) -> list:
    """
    Fetches available versions for a given server software from its API.

    Args:
        software (str): The name of the server software (e.g., "paper", "forge").

    Returns:
        list: A list of available version strings, or DUMMY_VERSIONS if fetching fails.
    """
    software = software.lower()
    url = versions_urls.get(software)

    # Specific handling for Nukkit: always return "Latest" as the only option
    if software == "nukkit":
        return ["Latest"]

    if url is None:
        print(f"No version fetching URL defined for {software}. Returning dummy versions.")
        return DUMMY_VERSIONS

    try:
        res = requests.get(url, timeout=10) # Added timeout for robustness
        res.raise_for_status() # Raise an exception for HTTP errors

        if software in ["forge", "neoforge"]:
            root = ET.fromstring(res.content)
            versions = [v.text for v in root.findall("./versioning/versions/version")]
            # Sort versions numerically and take the latest 100
            versions.sort(key=version_key, reverse=True)
            return versions[:100]
        
        if software == "spigot":
            version_pattern = re.compile(r"^\d+(\.\d+){1,2}$") # Matches versions like 1.16.5 or 1.20
            soup = BeautifulSoup(res.text, "html.parser")
            versions = []
            for a in soup.find_all("a", href=True):
                href = a['href']
                if href.endswith(".json"):
                    version = href.replace(".json", "")
                    if version_pattern.match(version):
                        versions.append(version)
            versions.sort(key=version_key, reverse=True)
            return versions[:100]

        data = res.json()

        if software == "vanilla":
            # Filter for release versions and take the latest 100
            return [v["id"] for v in data["versions"] if v["type"] == "release"][:100]
        if software == "pufferfish":
            # Pufferfish lists jobs, which are versions
            return [job["name"] for job in data.get("jobs", [])][::-1][:100] # Reverse to get latest first
        if software == "purpur":
            # Purpur lists versions directly
            return data.get("versions", [])[::-1][:100] # Reverse to get latest first
        if software in ["fabric", "quilt"]:
            # Fabric/Quilt list versions
            return [v["version"] for v in data][:100]
        if software == "pocketmine-mp": # Corrected key
            versions = []
            # Find releases that have a .phar asset
            for release in data:
                if any(asset["name"].endswith(".phar") for asset in release.get("assets", [])):
                    versions.append(release.get("tag_name", "unknown"))
            return versions[:100]
        if software == "bungeecord":
            # BungeeCord lists build numbers
            return [str(build['number']) for build in data.get('builds', [])][:100]
        
        # Default for PaperMC-based APIs (Paper, Folia, Velocity, Waterfall)
        return data.get("versions", [])[::-1][:100]

    except requests.exceptions.RequestException as req_err:
        print(f"Network or API error fetching versions for {software}: {req_err}")
    except (json.JSONDecodeError, ET.ParseError) as parse_err:
        print(f"Error parsing response for {software}: {parse_err}")
    except Exception as e:
        print(f"An unexpected error occurred while fetching versions for {software}: {e}")
    
    return DUMMY_VERSIONS # Return dummy versions on any failure

def download_server_jar(server_type: str, version: str = None, dest_folder: Path = Path(".")):
    """
    Downloads a Minecraft server or installer JAR/PHAR file based on the specified server type and version.

    Args:
        server_type (str): The type of server to download (e.g., "paper", "purpur", "fabric").
                           Valid types are keys in the `versions_urls` dictionary.
        version (str, optional): The specific version of the server/installer to download.
                                 Required for most server types. For 'nukkit', it's not needed.
                                 For 'bungeecord', this should be the build number.
        dest_folder (Path): The destination directory to save the downloaded JAR.

    Returns:
        Path or False: The path to the downloaded JAR/PHAR file if successful, otherwise False.
    """
    dest_folder.mkdir(parents=True, exist_ok=True)

    try:
        if server_type not in versions_urls:
            print(f"Error: Unknown server type '{server_type}'. Please choose from: {', '.join(versions_urls.keys())}")
            return False

        # Custom print message for Nukkit
        if server_type == "nukkit":
            print(f"Downloading latest Nukkit server jar...")
        else:
            print(f"Attempting to download {server_type} server file...")


        download_url = None
        file_name = None

        # --- Logic for Pufferfish Server ---
        if server_type == "pufferfish":
            if not version:
                print("Error: 'version' is required for Pufferfish server (e.g., '1.19', '1.20.1').")
                return False
            base_url = versions_urls["pufferfish"]
            res = requests.get(base_url, timeout=10)
            res.raise_for_status()
            data = res.json()

            version_url = next((job.get("url") for job in data.get("jobs", []) if job.get("name") == version), None)
            if not version_url:
                print(f"Version {version} not found in Jenkins jobs for Pufferfish!")
                return False

            version_api_url = version_url.rstrip('/') + "/api/json"
            res = requests.get(version_api_url, timeout=10)
            res.raise_for_status()
            version_data = res.json()

            if not version_data.get('builds'):
                print("No builds found for this Pufferfish version!")
                return False

            latest_build_url = version_data['builds'][0]['url']
            latest_build_api_url = latest_build_url.rstrip('/') + "/api/json"

            res = requests.get(latest_build_api_url, timeout=10)
            res.raise_for_status()
            build_data = res.json()

            if not build_data.get('artifacts'):
                print("No artifacts found in the latest Pufferfish build!")
                return False

            relative_path = build_data['artifacts'][0]['relativePath']
            download_url = latest_build_url.rstrip('/') + "/artifact/" + relative_path
            file_name = f"pufferfish-server-{version}.jar"

        # --- Logic for Purpur Server ---
        elif server_type == "purpur":
            if not version:
                print("Error: 'version' is required for Purpur server (e.g., '1.19.4', '1.20.1').")
                return False
            info_url = f"{versions_urls['purpur']}{version}"
            res = requests.get(info_url, timeout=10)
            res.raise_for_status()
            data = res.json()
            
            latest_build = data.get("builds", {}).get("latest")
            if not latest_build:
                print(f"No latest build found for Purpur version {version}")
                return False
            
            download_url = f"https://api.purpurmc.org/v2/purpur/{version}/{latest_build}/download"
            file_name = f"purpur_server.{version}.jar"

        # --- Logic for Spigot Server ---
        elif server_type == "spigot":
            if not version:
                print("Error: 'version' is required for Spigot server (e.g., '1.19.4', '1.20.1').")
                return False
            download_url = f"https://cdn.getbukkit.org/spigot/spigot-{version}.jar"
            file_name = f"spigot-{version}.jar"

        # --- Logic for Quilt Installer ---
        elif server_type == "quilt":
            if not version:
                print("Error: 'version' is required for Quilt installer (e.g., '0.19.0').")
                return False
            download_url = f"https://maven.quiltmc.org/repository/release/org/quiltmc/quilt-installer/{version}/quilt-installer-{version}.jar"
            file_name = f"quilt-installer-{version}.jar"

        # --- Logic for NeoForge Installer ---
        elif server_type == "neoforge":
            if not version:
                print("Error: 'version' is required for NeoForge installer (e.g., '20.4.220').")
                return False
            download_url = f"https://maven.neoforged.net/releases/net/neoforged/neoforge/{version}/neoforge-{version}-installer.jar"
            file_name = f"neoforge-{version}-installer.jar"

        # --- Logic for Fabric Installer ---
        elif server_type == "fabric":
            installer_url = versions_urls["fabric"] # This URL returns installer versions, not loader versions.
            res = requests.get(installer_url, timeout=10)
            res.raise_for_status()
            installers = res.json()
            # The API returns a list of installer versions, usually latest is first
            installer_version = installers[0]["version"] 
            download_url = f"https://maven.fabricmc.net/net/fabricmc/fabric-installer/{installer_version}/fabric-installer-{installer_version}.jar"
            file_name = f"fabric-installer-{installer_version}.jar"

        # --- Logic for PocketMine-MP Server ---
        elif server_type == "pocketmine-mp":
            if not version:
                print("Error: 'version' is required for PocketMine-MP (e.g., '4.0.0').")
                return False
            api_url = f"https://api.github.com/repos/pmmp/PocketMine-MP/releases/tags/{version}"
            res = requests.get(api_url, timeout=10)
            res.raise_for_status()
            release = res.json()
            assets = release.get("assets", [])

            phar_asset = next((a for a in assets if a["name"].endswith(".phar")), None)
            if not phar_asset:
                print(f"No PHAR asset found for PocketMine-MP version {version}")
                return False

            download_url = phar_asset["browser_download_url"]
            file_name = phar_asset["name"]

        # --- Logic for Forge Installer ---
        elif server_type == "forge":
            if not version:
                print("Error: 'version' is required for Forge installer (e.g., '1.19.4-45.0.49').")
                return False
            download_url = f"https://maven.minecraftforge.net/net/minecraftforge/forge/{version}/forge-{version}-installer.jar"
            file_name = f"forge-{version}-installer.jar"

        # --- Logic for Nukkit Server ---
        elif server_type == "nukkit":
            download_url = versions_urls["nukkit"] # Static URL for the latest snapshot.
            file_name = f"nukkit.jar"

        # --- Logic for BungeeCord Server ---
        elif server_type == "bungeecord":
            if not version:
                print("Error: 'version' (build number) is required for BungeeCord (e.g., '1700').")
                return False
            download_url = f"https://ci.md-5.net/job/BungeeCord/{version}/artifact/bootstrap/target/BungeeCord.jar"
            file_name = f"BungeeCord-{version}.jar"

        # --- Logic for PaperMC-based Servers (Waterfall, Velocity, Folia, Paper) ---
        elif server_type in ["waterfall", "velocity", "folia", "paper"]:
            if not version:
                print(f"Error: 'version' is required for {server_type} server (e.g., '1.19', '1.20.1').")
                return False
            builds_url = f"{versions_urls[server_type]}/versions/{version}"
            builds_res = requests.get(builds_url, timeout=10)
            builds_res.raise_for_status()
            builds_data = builds_res.json()
            latest_build = builds_data["builds"][-1] # Get the latest build number.

            file_name = f"{server_type}-{version}-{latest_build}.jar"
            download_url = f"https://api.papermc.io/v2/projects/{server_type}/versions/{version}/builds/{latest_build}/downloads/{file_name}"

        # --- Logic for Vanilla Minecraft Server ---
        elif server_type == "vanilla":
            if not version:
                print("Error: 'version' is required for Vanilla server (e.g., '1.19.4', '1.20.1').")
                return False
            manifest_url = versions_urls["vanilla"]
            res = requests.get(manifest_url, timeout=10)
            res.raise_for_status()
            manifest = res.json()
            version_info = next((v for v in manifest["versions"] if v["id"] == version), None)
            if not version_info:
                print(f"Vanilla version {version} not found in manifest!")
                return False

            version_json_url = version_info["url"]
            res = requests.get(version_json_url, timeout=10)
            res.raise_for_status()
            version_data = res.json()
            server_jar_url = version_data["downloads"]["server"]["url"]
            download_url = server_jar_url
            file_name = f"minecraft_server.{version}.jar"

        # If no download URL or file name was determined for a recognized type
        if not download_url or not file_name:
            print(f"Error: Could not determine download URL or file name for '{server_type}'.")
            return False

        jar_path = dest_folder / file_name
        # The specific print message for Nukkit is already handled above.
        # For other types, this general message is appropriate.
        if server_type != "nukkit":
            print(f"Downloading {server_type} server file to {jar_path} from {download_url}...")

        with requests.get(download_url, stream=True, timeout=300) as r: # Increased timeout for large files
            r.raise_for_status()
            with open(jar_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

        print(f"Successfully downloaded {server_type} server file to {jar_path}")
        return jar_path

    except requests.exceptions.RequestException as req_err:
        print(f"Network or API error downloading {server_type} server file: {req_err}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred while downloading {server_type} server file: {e}")
        return False

# --- Installer Runner Functions ---

def run_installer(installer_path: Path, target_folder: Path, mc_version: str = None) -> Path | bool:
    """
    Runs a specific Minecraft server installer (Forge, Fabric, NeoForge, Quilt).
    This function executes the installer JAR.

    Args:
        installer_path (Path): The path to the installer JAR file.
        target_folder (Path): The directory where the server should be installed.
        mc_version (str, optional): The target Minecraft version, required for Fabric/Quilt.

    Returns:
        Path or bool: The path to the main server executable if successful, False otherwise.
    """
    if not installer_path.exists():
        print(f"Installer not found: {installer_path}")
        return False

    target_folder.mkdir(parents=True, exist_ok=True)

    command = ["java", "-jar", str(installer_path)]
    software_name = installer_path.stem.lower()
    
    # Determine the expected output executable path
    output_exec_path = None

    if "forge" in software_name:
        command.append("--installServer")
        # Forge installer typically creates a forge-<mc_version>-<forge_version>.jar or similar
        # We'll try to find it after the install.
        output_exec_path = target_folder # Will search for the largest JAR in this folder later
    elif "neoforge" in software_name:
        command.append("--installServer")
        # NeoForge installer does not produce a new executable JAR, it sets up files.
        # We return True to indicate success, not a path.
        pass # No output_exec_path needed for NeoForge's return value
    elif "fabric" in software_name:
        if not mc_version:
            print("Error: Minecraft version is required for Fabric installer.")
            return False
        command.extend(["server", mc_version, "-downloadMinecraft"])
        output_exec_path = target_folder / "fabric-server-launch.jar"
    elif "quilt" in software_name:
        if not mc_version:
            print("Error: Minecraft version is required for Quilt installer.")
            return False
        command.extend([
            "install", "server", mc_version,
            "--download-server", "--create-scripts", f"--install-dir={str(target_folder)}"
        ])
        output_exec_path = target_folder / "quilt-server-launch.jar"
    else:
        print(f"Unsupported installer type for generic run_installer: {installer_path.name}")
        return False

    print(f"Running installer: {' '.join(command)} in {target_folder}...")
    try:
        # Removed printing stdout and stderr to remove all outputs from installers
        subprocess.run(
            command,
            cwd=target_folder,
            check=True, # Raise CalledProcessError for non-zero exit codes
            capture_output=True, # Still capture output, but won't print it
            text=True # Decode stdout/stderr as text
        )
        print(f"{software_name.replace('_installer', '').title()} server setup completed.")
        
        # Special handling for NeoForge: installation is successful, but no new JAR to return
        if "neoforge" in software_name:
            return True # Indicate success without returning a path

        # For Forge, find the actual executable JAR after installation
        if "forge" in software_name:
            candidate_jars = [f for f in target_folder.glob("*.jar") if "installer" not in f.name.lower()]
            if candidate_jars:
                # Pick the largest JAR that is not the installer itself
                actual_forge_jar = max(candidate_jars, key=os.path.getsize)
                print(f"Detected Forge executable: {actual_forge_jar.name}")
                return actual_forge_jar
            else:
                print("Warning: Could not find a clear Forge executable JAR after installation.")
                return False # Indicate failure to find executable
        
        return output_exec_path # Return the expected executable path for others
    except subprocess.CalledProcessError as e:
        print(f"Error running {software_name.replace('_installer', '').title()} installer: {e}")
        # Removed printing STDOUT/STDERR from error output as well
        return False
    except Exception as e:
        print(f"An unexpected error occurred while running {software_name.replace('_installer', '').title()} installer: {e}")
        return False

# --- Start Script Creation Functions ---

def create_start_script(dest_folder: Path, server_exec_path: Path, ram_mb: str) -> Path:
    """Creates a generic start script for JAR files."""
    ram_mb_int = int(ram_mb)
    is_windows = sys.platform == "win32"
    script_name = "start.bat" if is_windows else "start.sh"
    script_path = dest_folder / script_name

    content = f'java -Xmx{ram_mb_int}M -Xms{ram_mb_int}M -jar "{server_exec_path.name}" nogui'
    if is_windows:
        content += '\npause' # Keep window open on Windows
    else:
        content = f"#!/bin/bash\n{content}\n" # Add shebang for Linux/macOS

    script_path.write_text(content)
    if not is_windows:
        os.chmod(script_path, 0o755) # Make executable on Linux/macOS

    print(f"Created start script at {script_path}")
    return script_path

def create_start_script_neoforge(dest_folder: Path, version: str, ram_mb: str) -> Path:
    """Creates a start script specifically for NeoForge, which uses a different launch mechanism."""
    ram_mb_int = int(ram_mb)
    is_windows = sys.platform == "win32"
    script_name = "start.bat" if is_windows else "start.sh"
    script_path = dest_folder / script_name

    # NeoForge uses argument files for launching
    args_file = f"libraries/net/neoforged/neoforge/{version}/{'win_args.txt' if is_windows else 'unix_args.txt'}"
    
    content = f'java -Xmx{ram_mb_int}M -Xms{ram_mb_int}M @user_jvm_args.txt @{args_file} nogui'
    if is_windows:
        content += '\npause'
    else:
        content = f"#!/bin/bash\n{content}\n"

    script_path.write_text(content)
    if not is_windows:
        os.chmod(script_path, 0o755)

    print(f"Created NeoForge start script at {script_path}")
    return script_path

def create_start_script_pocketmine(dest_folder: Path, phar_path: Path) -> Path:
    """Creates a start script for PocketMine-MP (PHAR files)."""
    is_windows = sys.platform == "win32"
    script_name = "start.bat" if is_windows else "start.sh"
    script_path = dest_folder / script_name
    
    # Check if PHP is installed (best effort, user might need to install it)
    try:
        subprocess.run(["php", "-v"], capture_output=True, check=True, timeout=5)
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        print("Warning: PHP was not found on your system. PocketMine-MP requires PHP to run. Please install it manually.")
    
    content = f'php "{phar_path.name}"'
    if is_windows:
        content += '\npause'
    else:
        content = f"#!/bin/bash\n{content}\n"
    
    script_path.write_text(content)
    if not is_windows:
        os.chmod(script_path, 0o755)
    
    print(f"Created PocketMine-MP start script at {script_path}")
    return script_path

def open_folder_in_os(folder_path: Path):
    """Opens a given folder in the OS's default file explorer."""
    if sys.platform == "win32":
        os.startfile(folder_path)
    elif sys.platform == "darwin": # macOS
        subprocess.Popen(["open", str(folder_path)])
    else: # Linux and other Unix-like
        subprocess.Popen(["xdg-open", str(folder_path)]) # Common for many Linux desktops
        print(f"Opened folder: {folder_path}")

# --- User Interaction Functions ---

def choose_server_name() -> str | None:
    """Prompts the user to choose a server name and ensures it's unique."""
    while True:
        name = input("Enter a name for your new server (or type 'cancel' to go back): ").strip()
        if name.lower() == 'cancel':
            return None
        if not name:
            print("Server name cannot be empty.")
        elif (SERVERS_DIR / name).exists():
            print(f"A server named '{name}' already exists. Please choose a different name.")
        else:
            return name

def choose_software() -> str | None:
    """Prompts the user to choose server software from a predefined list."""
    print("\nAvailable server software:")
    for i, option in enumerate(SOFTWARE_OPTIONS, 1):
        print(f"[{i}] {option}")
    print("[0] Cancel")
    while True:
        choice = input("Choose server software by number or name: ").strip()
        if choice == '0':
            return None
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(SOFTWARE_OPTIONS):
                return SOFTWARE_OPTIONS[idx]
        else:
            # Allow case-insensitive matching for names
            for opt in SOFTWARE_OPTIONS:
                if opt.lower() == choice.lower():
                    return opt
        print("Invalid choice. Please try again.")

def choose_version(software_type: str) -> str | None:
    """
    Prompts the user to choose a version for the selected software.
    Includes pagination for long lists of versions.
    """
    software_lower = software_type.lower()
    versions = fetch_versions(software_lower)

    if not versions:
        print(f"No versions found for {software_type}.")
        return None
    
    # Removed the specific print message for Nukkit here.
    # The version list will naturally show "[1] Latest" if fetch_versions returns ["Latest"].

    page = 1
    page_size = 10
    total_pages = (len(versions) + page_size - 1) // page_size

    while True:
        start = (page - 1) * page_size
        end = start + page_size
        print(f"\nVersions Page {page}/{total_pages}:")
        for i, v in enumerate(versions[start:end], start=start + 1):
            print(f"[{i}] {v}")
        print("[0] Cancel")

        choice = input("Choose version number, type P<page number> (e.g., P2), or '0' to cancel: ").strip()

        if choice == '0':
            return None
        elif choice.upper().startswith("P"):
            try:
                new_page = int(choice[1:])
                if 1 <= new_page <= total_pages:
                    page = new_page
                else:
                    print("Page number out of range.")
            except ValueError:
                print("Invalid page input. Please use 'P' followed by a number (e.g., P2).")
        else:
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(versions):
                    return versions[idx]
                else:
                    print("Invalid version number.")
            except ValueError:
                print("Invalid input. Please enter a number, 'P<page number>', or '0'.")

# --- Main Server Management Functions ---

def create_server():
    """Guides the user through creating a new Minecraft server."""
    print("\n--- Create New Server ---\n")
    name = choose_server_name()
    if name is None: return # User cancelled

    software = choose_software()
    if software is None: return # User cancelled

    version = choose_version(software)
    # For Nukkit, version is "latest" but not used in download_server_jar directly
    # For other types, if version is None, it means fetching failed or user didn't select.
    if version is None and software.lower() != "nukkit":
        print("No valid version selected. Aborting server creation.")
        return
    
    mc_version = None
    # For installers like Fabric/Quilt, we need the target Minecraft version separately
    if software.lower() in ["fabric", "quilt"]:
        mc_version = input("Enter the target Minecraft Version (e.g., '1.20.1') for the installer: ").strip()
        if not mc_version:
            print("Minecraft version is required for Fabric/Quilt installers. Aborting.")
            return

    server_path = SERVERS_DIR / name
    # Directory is created here, after name validation
    server_path.mkdir(parents=True, exist_ok=True)

    eula_path = server_path / "eula.txt"
    eula_path.write_text("eula=true\n")
    print("EULA accepted automatically.")
    
    ram = input("Enter RAM allocation in MB (e.g., 2048): ").strip()
    if not ram.isdigit() or int(ram) <= 0:
        print("Invalid RAM allocation. Please enter a positive number. Aborting.")
        return

    print(f"Setting up server '{name}' with {software} version {version if version else 'latest'} and {ram}MB RAM...")

    # Unified download call
    jar_or_phar_path = download_server_jar(software.lower(), version, server_path)
    
    if not jar_or_phar_path:
        print("Failed to download server file. Aborting.")
        return

    server_exec_path = jar_or_phar_path # Default executable path

    # Handle installers: run the installer after download
    if software.lower() in ["forge", "fabric", "neoforge", "quilt"]:
        print(f"Downloaded {software} installer. Now running the installer...")
        installed_server_path = run_installer(jar_or_phar_path, server_path, mc_version)
        
        # Check the return value from run_installer
        if installed_server_path is False: # Installer failed
            print(f"Failed to run {software} installer. Aborting.")
            return
        elif installed_server_path is not True: # Installer returned a new path (Forge, Fabric, Quilt)
            server_exec_path = installed_server_path 
        # If installed_server_path is True (for NeoForge), server_exec_path remains jar_or_phar_path, which is correct.

    # Create start script based on server type
    start_script = None
    if server_exec_path.suffix.lower() == ".jar":
        if software.lower() == "neoforge":
            # For NeoForge, version is needed for the args file path in the start script
            start_script = create_start_script_neoforge(server_path, version, ram)
        else:
            start_script = create_start_script(server_path, server_exec_path, ram)
    elif server_exec_path.suffix.lower() == ".phar":
        start_script = create_start_script_pocketmine(server_path, server_exec_path)
    else:
        print(f"Unknown server executable extension: {server_exec_path.suffix}, no start script created.")
        start_script = None

    if not start_script:
        print("Failed to create start script. Server might not be runnable automatically.")
        return

    # Write metadata to server.properties
    (server_path / "server.properties").write_text(
        f"server-name={name}\nsoftware={software}\nversion={version if version else 'latest'}\nram={ram}MB\n"
    )

    print("Server setup complete!")

    # Open the server folder
    open_folder_in_os(server_path)

    print("Starting the server...")

    # Execute the start script in a new terminal
    if sys.platform == "win32":
        subprocess.Popen(f'start cmd /k "{start_script}"', shell=True, cwd=server_path)
    else:
        terminals = [
            ["gnome-terminal", "--", "bash", "-c", f"cd '{server_path}' && ./'{start_script.name}'; exec bash"],
            ["x-terminal-emulator", "-e", f"bash -c 'cd \"{server_path}\" && ./{start_script.name}; exec bash'"],
            ["xterm", "-e", f"bash -c 'cd \"{server_path}\" && ./{start_script.name}; exec bash'"],
            ["konsole", "-e", f"bash -c 'cd \"{server_path}\" && ./{start_script.name}; exec bash'"],
            ["mate-terminal", "-e", f"bash -c 'cd \"{server_path}\" && ./{start_script.name}; exec bash'"],
            ["lxterminal", "-e", f"bash -c 'cd \"{server_path}\" && ./{start_script.name}; exec bash'"],
        ]
        for term_cmd in terminals:
            try:
                subprocess.Popen(term_cmd, cwd=server_path) # cwd is used for some terminals, but the cd in command is more reliable
                break
            except FileNotFoundError:
                continue
        else:
            print(f"Could not open a terminal automatically. Run the script manually: {start_script}")

def list_existing_servers() -> str | None:
    """Lists existing servers and allows the user to select one."""
    servers = [f.name for f in SERVERS_DIR.iterdir() if f.is_dir()]
    if not servers:
        print("No existing servers found.")
        return None

    page = 1
    page_size = 10
    total_pages = (len(servers) + page_size - 1) // page_size

    while True:
        start = (page - 1) * page_size
        end = start + page_size
        print(f"\nServers Page {page}/{total_pages}:")
        for i, s in enumerate(servers[start:end], start=start + 1):
            print(f"[{i}] {s}")
        print("[0] Cancel")
        
        choice = input("Choose server number to run, type P<page number> (e.g., P2), or '0' to cancel: ").strip()
        if choice == '0':
            return None
        elif choice.upper().startswith("P"):
            try:
                new_page = int(choice[1:])
                if 1 <= new_page <= total_pages:
                    page = new_page
                else:
                    print("Page number out of range.")
            except ValueError:
                print("Invalid page input. Please use 'P' followed by a number (e.g., P2).")
        else:
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(servers):
                    return servers[idx]
                else:
                    print("Invalid server number.")
            except ValueError:
                print("Invalid input. Please enter a number, 'P<page number>', or '0'.")

def run_server():
    """Runs an existing Minecraft server by executing its start script."""
    print("\n--- Run Existing Server ---\n")
    server_name = list_existing_servers()
    if not server_name:
        return
    server_path = SERVERS_DIR / server_name
    print(f"Running server: {server_name}")

    start_script = None
    if (server_path / "start.bat").exists():
        start_script = server_path / "start.bat"
    elif (server_path / "start.sh").exists():
        start_script = server_path / "start.sh"

    if not start_script:
        print("No start script found in server folder! Please create one manually.")
        return

    # Open the server folder
    open_folder_in_os(server_path)

    # Execute the start script in a new terminal
    if sys.platform == "win32":
        subprocess.Popen(f'start cmd /k "{start_script}"', shell=True, cwd=server_path)
    else:
        terminals = [
            ["gnome-terminal", "--", "bash", "-c", f"cd '{server_path}' && ./'{start_script.name}'; exec bash"],
            ["x-terminal-emulator", "-e", f"bash -c 'cd \"{server_path}\" && ./{start_script.name}; exec bash'"],
            ["xterm", "-e", f"bash -c 'cd \"{server_path}\" && ./{start_script.name}; exec bash'"],
            ["konsole", "-e", f"bash -c 'cd \"{server_path}\" && ./{start_script.name}; exec bash'"],
            ["mate-terminal", "-e", f"bash -c 'cd \"{server_path}\" && ./{start_script.name}; exec bash'"],
            ["lxterminal", "-e", f"bash -c 'cd \"{server_path}\" && ./{start_script.name}; exec bash'"],
        ]
        for term_cmd in terminals:
            try:
                subprocess.Popen(term_cmd, cwd=server_path)
                break
            except FileNotFoundError:
                continue
        else:
            print(f"Could not open a terminal automatically. Run the script manually: {start_script}")

# --- Main Application Loop ---

def main():
    """Main function to run the Minecraft Server Manager."""
    global SERVERS_DIR # Ensure we modify the global variable

    # Determine the base directory for servers based on execution environment
    if getattr(sys, 'frozen', False):
        # Running as a PyInstaller bundle
        CURRENT_DIR = Path(sys.executable).parent.resolve()
    else:
        # Running as a normal Python script
        CURRENT_DIR = Path(__file__).parent.resolve()

    SERVERS_DIR = CURRENT_DIR / "servers"
    SERVERS_DIR.mkdir(exist_ok=True) # Ensure the main servers directory exists

    while True:
        print("\n--- Minecraft Server Manager ---")
        print("[1] Create New Server")
        print("[2] Run Existing Server")
        print("[3] Exit")
        choice = input("Choose an option: ").strip()
        if choice == "1":
            create_server()
        elif choice == "2":
            run_server()
        elif choice == "3":
            print("Goodbye!")
            break
        else:
            print("Invalid choice. Please enter 1, 2, or 3.")

if __name__ == "__main__":
    main()
