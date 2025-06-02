import os
import re
import sys
import requests
import subprocess
from pathlib import Path
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET

CURRENT_DIR = Path(__file__).parent.resolve()
SERVERS_DIR = CURRENT_DIR / "servers"
SERVERS_DIR.mkdir(exist_ok=True)
SOFTWARE_OPTIONS = [
    "Vanilla", "Forge", "Fabric", "NeoForge", "Quilt",
    "Spigot", "Paper", "Purpur", "Pufferfish", "Folia",
    "BungeeCord", "Velocity", "Waterfall", "Nukkit", "PocketMine-MP"
]

DUMMY_VERSIONS = [f"1.{i}" for i in range(100, 0, -1)]

def version_key(v):
    return tuple(int(x) for x in v.split('.'))

def fetch_pufferfish_versions():
    url = "https://ci.pufferfish.host/view/all/api/json"
    try:
        res = requests.get(url)
        res.raise_for_status()
        data = res.json()

        versions = [job["name"] for job in data["jobs"]]
        return versions[::-1][:100]  # max 100 versions
    except Exception as e:
        print(f"Failed to fetch Pufferfish versions: {e}")
        return DUMMY_VERSIONS

def download_pufferfish_server(version, dest_folder):
    try:
        base_url = "https://ci.pufferfish.host/view/all/api/json"
        res = requests.get(base_url)
        res.raise_for_status()
        data = res.json()

        version_url = None
        for job in data.get("jobs", []):
            if job.get("name") == version:
                version_url = job.get("url")
                break
        
        if not version_url:
            print(f"Version {version} not found in Jenkins jobs!")
            return False

        version_api_url = version_url.rstrip('/') + "/api/json"
        res = requests.get(version_api_url)
        res.raise_for_status()
        version_data = res.json()

        if not version_data.get('builds'):
            print("No builds found for this version!")
            return False
        
        latest_build_url = version_data['builds'][0]['url']
        latest_build_api_url = latest_build_url.rstrip('/') + "/api/json"

        res = requests.get(latest_build_api_url)
        res.raise_for_status()
        build_data = res.json()

        if not build_data.get('artifacts'):
            print("No artifacts found in the latest build!")
            return False
        
        relative_path = build_data['artifacts'][0]['relativePath']

        artifact_url = latest_build_url.rstrip('/') + "/artifact/" + relative_path

        print(f"Downloading Pufferfish server jar for version {version}...")
        dest_folder = Path(dest_folder)
        dest_folder.mkdir(parents=True, exist_ok=True)
        jar_path = dest_folder / f"pufferfish-server-{version}.jar"

        with requests.get(artifact_url, stream=True) as r:
            r.raise_for_status()
            with open(jar_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

        print(f"Downloaded Pufferfish server jar to {jar_path}")
        return jar_path

    except Exception as e:
        print(f"Error downloading Pufferfish server jar: {e}")
        return False

def fetch_purpur_versions():
    url = "https://api.purpurmc.org/v2/purpur/"
    try:
        res = requests.get(url)
        res.raise_for_status()
        data = res.json()
        versions = data.get("versions", [])
        return versions[::-1][:100]
    except Exception as e:
        print(f"Failed to fetch Purpur versions: {e}")
        return DUMMY_VERSIONS

def download_purpur_server(version, dest_folder):
    info_url = f"https://api.purpurmc.org/v2/purpur/{version}"
    try:
        res = requests.get(info_url)
        res.raise_for_status()
        data = res.json()
        
        latest_build = data.get("builds", {}).get("latest")
        if not latest_build:
            print(f"No latest build found for version {version}")
            return False
        
        jar_url = f"https://api.purpurmc.org/v2/purpur/{version}/{latest_build}/download"
        
        print(f"Downloading Purpur server jar for version {version} build {latest_build}...")
        jar_path = Path(dest_folder) / f"purpur_server.{version}.jar"
        
        with requests.get(jar_url, stream=True) as r:
            r.raise_for_status()
            with open(jar_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        
        print(f"Downloaded Purpur server jar to {jar_path}")
        return jar_path

    except Exception as e:
        print(f"Error downloading Purpur server jar: {e}")
        return False

def fetch_spigot_versions():
    url = "https://hub.spigotmc.org/versions/"
    version_pattern = re.compile(r"^\d+(\.\d+){1,2}$")
    try:
        res = requests.get(url)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        versions = []
        for a in soup.find_all("a", href=True):
            href = a['href']
            if href.endswith(".json"):
                version = href.replace(".json", "")
                if version_pattern.match(version):
                    versions.append(version)
        # Sort descending by numeric version parts
        versions.sort(key=version_key, reverse=True)
        return versions[:100]
    except Exception as e:
        print(f"Failed to fetch Spigot versions: {e}")
        return DUMMY_VERSIONS
    
def download_spigot_server(version, dest_folder):
    try:
        url = f"https://cdn.getbukkit.org/spigot/spigot-{version}.jar"
        print(f"Downloading Spigot server jar for version {version}...")
        jar_path = dest_folder / f"spigot-{version}.jar"
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(jar_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        print(f"Downloaded server jar to {jar_path}")
        return jar_path
    except Exception as e:
        print(f"Error downloading Spigot server jar: {e}")
        return False

def run_quilt_installer(installer_path, target_folder, mc_version):
    installer_path = Path(installer_path)
    target_folder = Path(target_folder)

    if not installer_path.exists():
        print(f"Installer not found: {installer_path}")
        return False

    target_folder.mkdir(parents=True, exist_ok=True)

    try:
        print(f"Running Quilt Installer for Minecraft {mc_version}...")
        subprocess.run([
            "java", "-jar", str(installer_path),
            "install", "server", mc_version,
            "--download-server",
            "--create-scripts",
            f"--install-dir={str(target_folder)}"
        ],
        cwd=target_folder,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL)
        
        print("Quilt server setup completed.")
        return True

    except subprocess.CalledProcessError as e:
        print(f"Error running Quilt installer: {e}")
        return False

def fetch_quilt_versions():
    url = "https://meta.quiltmc.org/v3/versions/installer"  # Quilt API for versions
    try:
        res = requests.get(url)
        res.raise_for_status()
        data = res.json()
        versions = [v["version"] for v in data]
        return versions[:100]  # Latest 100 versions
    except Exception as e:
        print(f"Failed to fetch Quilt versions: {e}")
        return DUMMY_VERSIONS

def download_quilt_installer(version, dest_folder):
    installer_url = f"https://maven.quiltmc.org/repository/release/org/quiltmc/quilt-installer/{version}/quilt-installer-{version}.jar"
    jar_path = Path(dest_folder) / f"quilt-installer-{version}.jar"
    try:
        print(f"Downloading Quilt installer for version {version}...")
        with requests.get(installer_url, stream=True) as r:
            r.raise_for_status()
            with open(jar_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        print(f"Downloaded Quilt installer to {jar_path}")
        return jar_path
    except Exception as e:
        print(f"Error downloading Quilt installer: {e}")
        return False

def run_neoforge_installer(installer_path, target_folder):
    installer_path = Path(installer_path)
    target_folder = Path(target_folder)

    if not installer_path.exists():
        print(f"Installer not found: {installer_path}")
        return False

    target_folder.mkdir(parents=True, exist_ok=True)

    try:
        print(f"Running NeoForge Installer for Minecraft...")
        subprocess.run(
            ["java", "-jar", str(installer_path), "--installServer"],
            cwd=target_folder,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        print("NeoForge server setup completed.")
        return True

    except subprocess.CalledProcessError as e:
        print(f"Error running NeoForge installer: {e}")
        return False

def fetch_neoforge_versions():
    url = "https://maven.neoforged.net/releases/net/neoforged/neoforge/maven-metadata.xml"
    try:
        res = requests.get(url)
        res.raise_for_status()
        root = ET.fromstring(res.content)
        versions = [v.text for v in root.findall("./versioning/versions/version")]
        return versions[::-1][:100]  # Latest 100 versions (in reverse order)
    except Exception as e:
        print(f"Failed to fetch NeoForge versions: {e}")
        return DUMMY_VERSIONS

def download_neoforge_installer(version, dest_folder):
    url = f"https://maven.neoforged.net/releases/net/neoforged/neoforge/{version}/neoforge-{version}-installer.jar"
    jar_path = Path(dest_folder) / f"neoforge-{version}-installer.jar"
    try:
        print(f"Downloading NeoForge installer for version {version}...")
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(jar_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        print(f"Downloaded NeoForge installer to {jar_path}")
        return jar_path
    except Exception as e:
        print(f"Error downloading NeoForge installer: {e}")
        return False

def run_fabric_installer(installer_path, target_folder, mc_version):
    installer_path = Path(installer_path)
    target_folder = Path(target_folder)

    if not installer_path.exists():
        print(f"Installer not found: {installer_path}")
        return False

    target_folder.mkdir(parents=True, exist_ok=True)

    try:
        print(f"Running Fabric Installer for Minecraft {mc_version}...")
        subprocess.run(
            ["java", "-jar", str(installer_path), "server", mc_version, "-downloadMinecraft"],
            cwd=target_folder,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        print("Fabric server setup completed.")
        return True

    except subprocess.CalledProcessError as e:
        print(f"Error running Fabric installer: {e}")
        return False

def fetch_fabric_versions():
    url = "https://meta.fabricmc.net/v2/versions/loader"
    try:
        res = requests.get(url)
        res.raise_for_status()
        data = res.json()
        versions = [v["version"] for v in data]
        return versions[:100]
    except Exception as e:
        print(f"Failed to fetch Fabric versions: {e}")
        return DUMMY_VERSIONS

def download_fabric_installer(version, dest_folder):
    installer_url = "https://meta.fabricmc.net/v2/versions/installer"
    try:
        res = requests.get(installer_url)
        res.raise_for_status()
        installers = res.json()
        installer_version = installers[0]["version"]
        installer_jar_url = f"https://maven.fabricmc.net/net/fabricmc/fabric-installer/{installer_version}/fabric-installer-{installer_version}.jar"

        print(f"Downloading Fabric installer for version {version}...")
        jar_path = Path(dest_folder) / f"fabric-installer-{installer_version}.jar"
        with requests.get(installer_jar_url, stream=True) as r:
            r.raise_for_status()
            with open(jar_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

        print(f"Downloaded Fabric installer to {jar_path}")
        return jar_path
    except Exception as e:
        print(f"Error downloading Fabric installer: {e}")
        return False

def fetch_pocketmine_versions():
    url = "https://api.github.com/repos/pmmp/PocketMine-MP/releases"
    try:
        res = requests.get(url)
        res.raise_for_status()
        releases = res.json()
        versions = []
        for release in releases:
            assets = release.get("assets", [])
            if any(asset["name"].endswith(".phar") for asset in assets):
                versions.append(release["tag_name"])
        return versions[:100]
    except Exception as e:
        print(f"Failed to fetch PocketMine versions: {e}")
        return DUMMY_VERSIONS

def download_pocketmine_server(version, dest_folder):
    dest_folder = Path(dest_folder)
    dest_folder.mkdir(parents=True, exist_ok=True)

    api_url = f"https://api.github.com/repos/pmmp/PocketMine-MP/releases/tags/{version}"

    try:
        res = requests.get(api_url)
        res.raise_for_status()
        release = res.json()
        assets = release.get("assets", [])

        phar_asset = next((a for a in assets if a["name"].endswith(".phar")), None)
        if not phar_asset:
            print(f"No PHAR asset found for version {version}")
            return False

        download_url = phar_asset["browser_download_url"]
        phar_path = dest_folder / phar_asset["name"]

        print(f"Downloading PocketMine-MP {version} PHAR...")
        with requests.get(download_url, stream=True) as r:
            r.raise_for_status()
            with open(phar_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

        print(f"Downloaded PocketMine-MP PHAR to {phar_path}")
        return phar_path
    except Exception as e:
        print(f"Error downloading PocketMine-MP: {e}")
        return False

def run_forge_installer(installer_path, target_folder):
    installer_path = Path(installer_path)
    target_folder = Path(target_folder)

    if not installer_path.exists():
        print(f"Installer not found: {installer_path}")
        return False

    target_folder.mkdir(parents=True, exist_ok=True)

    try:
        print(f"Running Forge Installer for Minecraft...")  # optional logging
        subprocess.run(
            ["java", "-jar", str(installer_path), "--installServer"],
            cwd=target_folder,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        print("Forge server setup completed.")
        return True

    except subprocess.CalledProcessError as e:
        print(f"Error running Forge installer: {e}")
        return False

def fetch_forge_versions():
    url = "https://files.minecraftforge.net/maven/net/minecraftforge/forge/maven-metadata.xml"
    try:
        res = requests.get(url)
        res.raise_for_status()
        root = ET.fromstring(res.content)
        versions = [v.text for v in root.findall("./versioning/versions/version")]
        return versions[:100]  # Return the latest 100 versions
    except Exception as e:
        print(f"Failed to fetch Forge versions: {e}")
        return DUMMY_VERSIONS
    
def download_forge_installer(version, dest_folder):
    url = f"https://maven.minecraftforge.net/net/minecraftforge/forge/{version}/forge-{version}-installer.jar"
    jar_path = Path(dest_folder) / f"forge-{version}-installer.jar"
    try:
        print(f"Downloading Forge installer for version {version}...")
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(jar_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        print(f"Downloaded Forge installer to {jar_path}")
        return jar_path
    except Exception as e:
        print(f"Error downloading Forge installer: {e}")
        return False

def fetch_nukkit_versions():
    return ["Last Successful Build"]
    
def download_nukkit_server(dest_folder):
    url = "https://ci.opencollab.dev/job/NukkitX/job/Nukkit/job/master/lastSuccessfulBuild/artifact/target/nukkit-1.0-SNAPSHOT.jar"
    jar_path = Path(dest_folder) / f"nukkit.jar"
    try:
        print(f"Downloading latest Nukkit server jar...")
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(jar_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        print(f"Downloaded Nukkit server jar to {jar_path}")
        return jar_path
    except Exception as e:
        print(f"Error downloading Nukkit server jar: {e}")
        return False

def fetch_bungeecord_versions():
    url = "https://ci.md-5.net/job/BungeeCord/api/json?tree=builds[number]"
    try:
        res = requests.get(url)
        res.raise_for_status()
        data = res.json()
        build_numbers = [str(build['number']) for build in data.get('builds', [])]
        return build_numbers[:100]
    except Exception as e:
        print(f"Failed to fetch BungeeCord builds: {e}")
        return DUMMY_VERSIONS

def download_bungeecord_server(version, dest_folder):
    try:
        download_url = f"https://ci.md-5.net/job/BungeeCord/{version}/artifact/bootstrap/target/BungeeCord.jar"
        file_name = f"BungeeCord-{version}.jar"
        jar_path = dest_folder / file_name

        print(f"Downloading BungeeCord build #{version}...")
        with requests.get(download_url, stream=True) as r:
            r.raise_for_status()
            with open(jar_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

        print(f"Downloaded BungeeCord jar to {jar_path}")
        return jar_path
    except Exception as e:
        print(f"Error downloading BungeeCord jar: {e}")
        return False

def fetch_waterfall_versions():
    url = "https://api.papermc.io/v2/projects/waterfall"
    try:
        res = requests.get(url)
        res.raise_for_status()
        data = res.json()
        return data["versions"][::-1][:100]
    except Exception as e:
        print(f"Failed to fetch Waterfall versions: {e}")
        return DUMMY_VERSIONS

def download_waterfall_server(version, dest_folder):
    try:
        builds_url = f"https://api.papermc.io/v2/projects/waterfall/versions/{version}"
        builds_res = requests.get(builds_url)
        builds_res.raise_for_status()
        builds_data = builds_res.json()
        latest_build = builds_data["builds"][-1]

        file_name = f"waterfall-{version}-{latest_build}.jar"
        download_url = f"https://api.papermc.io/v2/projects/waterfall/versions/{version}/builds/{latest_build}/downloads/{file_name}"

        print(f"Downloading Waterfall jar for version {version} (build {latest_build})...")
        jar_path = dest_folder / file_name
        with requests.get(download_url, stream=True) as r:
            r.raise_for_status()
            with open(jar_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

        print(f"Downloaded Waterfall jar to {jar_path}")
        return jar_path
    except Exception as e:
        print(f"Error downloading Waterfall jar: {e}")
        return False

def fetch_velocity_versions():
    url = "https://api.papermc.io/v2/projects/velocity"
    try:
        res = requests.get(url)
        res.raise_for_status()
        data = res.json()
        return data["versions"][::-1][:100]
    except Exception as e:
        print(f"Failed to fetch Velocity versions: {e}")
        return DUMMY_VERSIONS

def download_velocity_server(version, dest_folder):
    try:
        builds_url = f"https://api.papermc.io/v2/projects/velocity/versions/{version}"
        builds_res = requests.get(builds_url)
        builds_res.raise_for_status()
        builds_data = builds_res.json()
        latest_build = builds_data["builds"][-1]

        file_name = f"velocity-{version}-{latest_build}.jar"
        download_url = f"https://api.papermc.io/v2/projects/velocity/versions/{version}/builds/{latest_build}/downloads/{file_name}"

        print(f"Downloading Velocity jar for version {version} (build {latest_build})...")
        jar_path = dest_folder / file_name
        with requests.get(download_url, stream=True) as r:
            r.raise_for_status()
            with open(jar_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

        print(f"Downloaded Velocity jar to {jar_path}")
        return jar_path
    except Exception as e:
        print(f"Error downloading Velocity jar: {e}")
        return False

def fetch_folia_versions():
    url = "https://api.papermc.io/v2/projects/folia"
    try:
        res = requests.get(url)
        res.raise_for_status()
        data = res.json()
        return data["versions"][::-1][:100]
    except Exception as e:
        print(f"Failed to fetch Folia versions: {e}")
        return DUMMY_VERSIONS

def download_folia_server(version, dest_folder):
    try:
        builds_url = f"https://api.papermc.io/v2/projects/folia/versions/{version}"
        builds_res = requests.get(builds_url)
        builds_res.raise_for_status()
        builds_data = builds_res.json()
        latest_build = builds_data["builds"][-1]

        file_name = f"folia-{version}-{latest_build}.jar"
        download_url = f"https://api.papermc.io/v2/projects/folia/versions/{version}/builds/{latest_build}/downloads/{file_name}"

        print(f"Downloading Folia server jar for version {version} (build {latest_build})...")
        jar_path = dest_folder / file_name
        with requests.get(download_url, stream=True) as r:
            r.raise_for_status()
            with open(jar_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

        print(f"Downloaded Folia server jar to {jar_path}")
        return jar_path
    except Exception as e:
        print(f"Error downloading Folia server jar: {e}")
        return False

def fetch_paper_versions():
    url = "https://api.papermc.io/v2/projects/paper"
    try:
        res = requests.get(url)
        res.raise_for_status()
        data = res.json()
        return data["versions"][::-1][:100]
    except Exception as e:
        print(f"Failed to fetch Paper versions: {e}")
        return DUMMY_VERSIONS
    
def download_paper_server(version, dest_folder):
    try:
        builds_url = f"https://api.papermc.io/v2/projects/paper/versions/{version}"
        builds_res = requests.get(builds_url)
        builds_res.raise_for_status()
        builds_data = builds_res.json()
        latest_build = builds_data["builds"][-1]

        file_name = f"paper-{version}-{latest_build}.jar"
        download_url = f"https://api.papermc.io/v2/projects/paper/versions/{version}/builds/{latest_build}/downloads/{file_name}"

        print(f"Downloading Paper server jar for version {version} (build {latest_build})...")
        jar_path = dest_folder / file_name
        with requests.get(download_url, stream=True) as r:
            r.raise_for_status()
            with open(jar_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

        print(f"Downloaded Paper server jar to {jar_path}")
        return jar_path
    except Exception as e:
        print(f"Error downloading Paper server jar: {e}")
        return False

def fetch_vanilla_versions():
    url = "https://launchermeta.mojang.com/mc/game/version_manifest.json"
    try:
        res = requests.get(url)
        res.raise_for_status()
        data = res.json()
        versions = [v["id"] for v in data["versions"] if v["type"] == "release"]
        return versions[:100]
    except Exception as e:
        print(f"Failed to fetch vanilla versions: {e}")
        return DUMMY_VERSIONS

def download_vanilla_server(version, dest_folder):
    manifest_url = "https://launchermeta.mojang.com/mc/game/version_manifest.json"
    try:
        res = requests.get(manifest_url)
        res.raise_for_status()
        manifest = res.json()
        version_info = next((v for v in manifest["versions"] if v["id"] == version), None)
        if not version_info:
            print("Version info not found in manifest!")
            return False

        version_json_url = version_info["url"]
        res = requests.get(version_json_url)
        res.raise_for_status()
        version_data = res.json()
        server_jar_url = version_data["downloads"]["server"]["url"]

        print(f"Downloading Vanilla server jar for version {version}...")
        jar_path = dest_folder / f"minecraft_server.{version}.jar"
        with requests.get(server_jar_url, stream=True) as r:
            r.raise_for_status()
            with open(jar_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

        print(f"Downloaded server jar to {jar_path}")
        return jar_path
    except Exception as e:
        print(f"Error downloading server jar: {e}")
        return False

def check_php_installed():
    try:
        subprocess.run(["php", "-v"], capture_output=True, check=True)
        return True
    except Exception:
        return False

def create_start_script(dest_folder, jar_path, ram_mb):
    ram_mb = int(ram_mb)
    is_windows = os.name == "nt"
    script_path = dest_folder / ("start.bat" if is_windows else "start.sh")

    content = (
        f'java -Xmx{ram_mb}M -Xms{ram_mb}M -jar "{jar_path.name}" nogui\n'
    )
    if not is_windows:
        content = f"#!/bin/bash\n{content}"

    with open(script_path, "w") as f:
        f.write(content)
    if not is_windows:
        os.chmod(script_path, 0o755)

    print(f"Created start script at {script_path}")
    return script_path

def create_start_script_neoforge(dest_folder, version, ram_mb):
    ram_mb = int(ram_mb)
    is_windows = os.name == "nt"
    script_path = dest_folder / ("start_neoforge.bat" if is_windows else "start_neoforge.sh")

    win_args = f"libraries/net/neoforged/neoforge/{version}/win_args.txt"

    content = f'java -Xmx{ram_mb}M -Xms{ram_mb}M @user_jvm_args.txt @{win_args} nogui\n'

    if not is_windows:
        content = f"#!/bin/bash\n{content}"

    with open(script_path, "w") as f:
        f.write(content)

    if not is_windows:
        os.chmod(script_path, 0o755)

    print(f"Created NeoForge start script at {script_path}")
    return script_path

def create_start_script_pocketmine(dest_folder, phar_path):
    dest_folder = Path(dest_folder)
    phar_path = Path(phar_path)
    is_windows = os.name == "nt"
    
    if not check_php_installed():
        print("PHP was not found on your system. Please install it manually.")
    
    script_path = dest_folder / ("start.bat" if is_windows else "start.sh")
    
    content = f'php "{phar_path.name}"\n'
    if not is_windows:
        content = f"#!/bin/bash\n{content}"
    
    with open(script_path, "w") as f:
        f.write(content)
    
    if not is_windows:
        os.chmod(script_path, 0o755)
    
    print(f"Created PocketMine-MP start script at {script_path}")
    return script_path

def choose_server_name():
    while True:
        name = input("Enter a name for your server: ").strip()
        path = SERVERS_DIR / name
        if not path.exists():
            path.mkdir()
            return name
        else:
            print("Server with that name exists. Choose a different name.")

def choose_software():
    for i, option in enumerate(SOFTWARE_OPTIONS, 1):
        print(f"[{i}] {option}")
    while True:
        choice = input("Choose server software by number: ")
        try:
            choice = int(choice)
            if 1 <= choice <= len(SOFTWARE_OPTIONS):
                return SOFTWARE_OPTIONS[choice - 1]
        except:
            pass
        print("Invalid choice.")

def choose_version(software):
    if software == "Vanilla":
        versions = fetch_vanilla_versions()
    elif software == "Paper":
        versions = fetch_paper_versions()
    elif software == "Folia":
        versions = fetch_folia_versions()
    elif software == "Velocity":
        versions = fetch_velocity_versions()
    elif software == "Waterfall":
        versions = fetch_waterfall_versions()
    elif software == "BungeeCord":
        versions = fetch_bungeecord_versions()
    elif software == "Nukkit":
        versions = fetch_nukkit_versions()
    elif software == "Forge":
        versions = fetch_forge_versions()
    elif software == "PocketMine-MP":
        versions = fetch_pocketmine_versions()
    elif software == "Fabric":
        versions = fetch_fabric_versions()
    elif software == "NeoForge":
        versions = fetch_neoforge_versions()
    elif software == "Quilt":
        versions = fetch_quilt_versions()
    elif software == "Spigot":
        versions = fetch_spigot_versions()
    elif software == "Spigot":
        versions = fetch_purpur_versions()
    elif software == "Purpur":
        versions = fetch_purpur_versions()
    elif software == "Pufferfish":
        versions = fetch_pufferfish_versions()

    else:
        versions = DUMMY_VERSIONS

    page = 1
    page_size = 10
    total_pages = (len(versions) + page_size - 1) // page_size

    while True:
        start = (page - 1) * page_size
        end = start + page_size
        print(f"\nVersions Page {page}/{total_pages}:")
        for i, v in enumerate(versions[start:end], start=start + 1):
            print(f"[{i}] {v}")
        choice = input("Choose version number or type P<page>: ").strip()
        if choice.upper().startswith("P"):
            try:
                new_page = int(choice[1:])
                if 1 <= new_page <= total_pages:
                    page = new_page
                else:
                    page = 1
            except:
                print("Invalid page input.")
        else:
            try:
                idx = int(choice)
                if 1 <= idx <= len(versions):
                    return versions[idx - 1]
                else:
                    print("Invalid version number.")
            except:
                print("Invalid input.")

def create_server():
    print("\n--- Create New Server ---\n")
    name = choose_server_name()
    software = choose_software()
    version = choose_version(software)
    if software.lower() in ["fabric", "quilt"]:
        mc_version = input("Minecraft Version: ")
    
    server_path = SERVERS_DIR / name
    server_path.mkdir(parents=True, exist_ok=True)

    eula_path = server_path / "eula.txt"
    eula_path.write_text("eula=true\n")
    print("EULA accepted automatically.")
    
    ram = input("Enter RAM allocation in MB: ")
    print(f"Setting up server '{name}' with {software} version {version} and {ram}MB RAM...")

    if software.lower() == "vanilla":
        jar_path = download_vanilla_server(version, server_path)
        if not jar_path:
            print("Failed to download server jar. Aborting.")
            return
        server_exec_path = jar_path
    elif software.lower() == "paper":
        jar_path = download_paper_server(version, server_path)
        if not jar_path:
            print("Failed to download server jar. Aborting.")
            return
        server_exec_path = jar_path
    elif software.lower() == "folia":
        jar_path = download_folia_server(version, server_path)
        if not jar_path:
            print("Failed to download server jar. Aborting.")
            return
        server_exec_path = jar_path
    elif software.lower() == "velocity":
        jar_path = download_velocity_server(version, server_path)
        if not jar_path:
            print("Failed to download server jar. Aborting.")
            return
        server_exec_path = jar_path
    elif software.lower() == "waterfall":
        jar_path = download_waterfall_server(version, server_path)
        if not jar_path:
            print("Failed to download server jar. Aborting.")
            return
        server_exec_path = jar_path
    elif software.lower() == "bungeecord":
        jar_path = download_bungeecord_server(version, server_path)
        if not jar_path:
            print("Failed to download server jar. Aborting.")
            return
        server_exec_path = jar_path
    elif software.lower() == "nukkit":
        jar_path = download_nukkit_server(server_path)
        if not jar_path:
            print("Failed to download server jar. Aborting.")
            return
        server_exec_path = jar_path
    elif software.lower() == "forge":
        jar_path = download_forge_installer(version, server_path)
        if not jar_path:
            print("Failed to download server jar. Aborting.")
            return
        run_forge_installer(jar_path, server_path)
        jar_path = jar_path.with_name(jar_path.name.replace("-installer", "-shim"))
        server_exec_path = jar_path
    elif software.lower() == "pocketmine-mp":
        phar_path = download_pocketmine_server(version, server_path)
        if not phar_path:
            print("Failed to download server phar. Aborting.")
            return
        server_exec_path = phar_path
    elif software.lower() == "fabric":
        jar_path = download_fabric_installer(version, server_path)
        if not jar_path:
            print("Failed to download server jar. Aborting.")
            return
        run_fabric_installer(jar_path, server_path, mc_version)
        jar_path = jar_path.with_name("fabric-server-launch.jar")
        server_exec_path = jar_path
    elif software.lower() == "neoforge":
        jar_path = download_neoforge_installer(version, server_path)
        if not jar_path:
            print("Failed to download server jar. Aborting.")
            return
        run_neoforge_installer(jar_path, server_path)
        server_exec_path = jar_path
    elif software.lower() == "quilt":
        jar_path = download_quilt_installer(version, server_path)
        if not jar_path:
            print("Failed to download server jar. Aborting.")
            return
        run_quilt_installer(jar_path, server_path, mc_version)
        jar_path = jar_path.with_name("quilt-server-launch.jar")
        server_exec_path = jar_path
    elif software.lower() == "spigot":
        jar_path = download_spigot_server(version, server_path)
        if not jar_path:
            print("Failed to download server jar. Aborting.")
            return
        server_exec_path = jar_path
    elif software.lower() == "purpur":
        jar_path = download_purpur_server(version, server_path)
        if not jar_path:
            print("Failed to download server jar. Aborting.")
            return
        server_exec_path = jar_path
    elif software.lower() == "pufferfish":
        jar_path = download_pufferfish_server(version, server_path)
        if not jar_path:
            print("Failed to download server jar. Aborting.")
            return
        server_exec_path = jar_path
    else:
        jar_path = server_path / f"{software}-{version}.jar"
        jar_path.write_text(f"This is a dummy {software} server jar for version {version}")
        server_exec_path = jar_path

    ext = server_exec_path.suffix.lower()
    if ext == ".jar":
        if software.lower() == "neoforge":
            start_script = create_start_script_neoforge(server_path, version, ram)
        else:
            start_script = create_start_script(server_path, server_exec_path, ram)
    elif ext == ".phar":
        start_script = create_start_script_pocketmine(server_path, server_exec_path)
    else:
        print(f"Unknown server executable extension: {ext}, no start script created.")
        start_script = None

    # Write metadata
    (server_path / "server.properties").write_text(
        f"server-name={name}\nsoftware={software}\nversion={version}\nram={ram}MB\n"
    )

    print("Server setup complete!")

    if os.name == "nt":
        os.startfile(server_path)
    else:
        print(f"Open the folder {server_path} to see your server files.")

    print("Starting the server...")

    if os.name == "nt":
        subprocess.Popen(f'start cmd /k "{start_script}"', shell=True, cwd=server_path)
    else:
        terminals = [
            ["gnome-terminal", "--", "bash", "-c", f"./{start_script.name}; exec bash"],
            ["x-terminal-emulator", "-e", f"./{start_script.name}"],
            ["xterm", "-e", f"./{start_script.name}"],
            ["konsole", "-e", f"./{start_script.name}"],
            ["mate-terminal", "-e", f"./{start_script.name}"],
        ]
        for term in terminals:
            try:
                subprocess.Popen(term, cwd=server_path)
                break
            except FileNotFoundError:
                continue
        else:
            print(f"Could not open a terminal automatically. Run the script manually: {start_script}")

def list_existing_servers():
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
        choice = input("Choose server number to run or type P<page>: ").strip()
        if choice.upper().startswith("P"):
            try:
                new_page = int(choice[1:])
                if 1 <= new_page <= total_pages:
                    page = new_page
                else:
                    page = 1
            except:
                print("Invalid page input.")
        else:
            try:
                idx = int(choice)
                if 1 <= idx <= len(servers):
                    return servers[idx - 1]
                else:
                    print("Invalid server number.")
            except:
                print("Invalid input.")

def run_server():
    print("\n--- Run Existing Server ---\n")
    server_name = list_existing_servers()
    if not server_name:
        return
    server_path = SERVERS_DIR / server_name
    print(f"Running server: {server_name}")

    # Look for start.bat or start.sh
    start_script = None
    if (server_path / "start.bat").exists():
        start_script = server_path / "start.bat"
    elif (server_path / "start.sh").exists():
        start_script = server_path / "start.sh"

    if not start_script:
        print("No start script found in server folder!")
        return

    if os.name == "nt":
        subprocess.Popen(f'start cmd /k "{start_script}"', shell=True, cwd=server_path)
        os.startfile(server_path)
    else:
        terminals = [
            ["gnome-terminal", "--", "bash", "-c", f"./{start_script.name}; exec bash"],
            ["x-terminal-emulator", "-e", f"./{start_script.name}"],
            ["xterm", "-e", f"./{start_script.name}"],
            ["konsole", "-e", f"./{start_script.name}"],
            ["mate-terminal", "-e", f"./{start_script.name}"],
        ]
        for term in terminals:
            try:
                subprocess.Popen(term, cwd=server_path)
                os.system(f'xdg-open "{server_path}"')
                break
            except FileNotFoundError:
                continue
        else:
            print(f"Could not open a terminal automatically. Run the script manually: {start_script}")

def main():
    while True:
        print("\n--- Minecraft Server Manager ---")
        print("[1] Create New Server")
        print("[2] Run Existing Server")
        print("[3] Exit")
        choice = input("Choose an option: ")
        if choice == "1":
            create_server()
        elif choice == "2":
            run_server()
        elif choice == "3":
            print("Bye!")
            break
        else:
            print("Invalid choice.")

if __name__ == "__main__":
    if getattr(sys, 'frozen', False):
        # Running as a PyInstaller bundle
        CURRENT_DIR = Path(sys.executable).parent.resolve()
    else:
        # Running as a normal Python script
        CURRENT_DIR = Path(__file__).parent.resolve()

    SERVERS_DIR = CURRENT_DIR / "servers"
    SERVERS_DIR.mkdir(exist_ok=True)
    main()