import requests
from pathlib import Path
import os
import subprocess
import sys
import re
import json
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from tkinter.font import Font
from threading import Thread
from queue import Queue

from PIL import Image, ImageTk
import ctypes

# --- Global Configurations and Data ---

# Define a base directory for all servers relative to the script's location
SERVERS_DIR = Path("./servers") 

# List of supported server software options for user selection
SOFTWARE_OPTIONS = [
    "Vanilla", "Forge", "Fabric", "NeoForge", "Quilt",
    "Spigot", "Paper", "Purpur", "Pufferfish", "Folia",
    "BungeeCord", "Velocity", "Waterfall", "Nukkit", "PocketMine-MP"
]

# Dictionary mapping software types to their API/download URLs
versions_urls = {
    "vanilla": "https://launchermeta.mojang.com/mc/game/version_manifest.json",
    "paper": "https://api.papermc.io/v2/projects/paper",
    "folia": "https://api.papermc.io/v2/projects/folia",
    "velocity": "https://api.papermc.io/v2/projects/velocity",
    "waterfall": "https://api.papermc.io/v2/projects/waterfall",
    "bungeecord": "https://ci.md-5.net/job/BungeeCord/api/json?tree=builds[number]",
    "nukkit": "https://ci.opencollab.dev/job/NukkitX/job/Nukkit/job/master/lastSuccessfulBuild/artifact/target/nukkit-1.0-SNAPSHOT.jar",
    "forge": "https://files.minecraftforge.net/maven/net/minecraftforge/forge/maven-metadata.xml",
    "pocketmine-mp": "https://api.github.com/repos/pmmp/PocketMine-MP/releases",
    "fabric": "https://meta.fabricmc.net/v2/versions/installer",
    "neoforge": "https://maven.neoforged.net/releases/net/neoforged/neoforge/maven-metadata.xml",
    "quilt": "https://meta.quiltmc.org/v3/versions/installer",
    "spigot": "https://hub.spigotmc.org/versions/",
    "purpur": "https://api.purpurmc.org/v2/purpur/",
    "pufferfish": "https://ci.pufferfish.host/view/all/api/json",
}

# Dummy versions for fallback if API calls fail
DUMMY_VERSIONS = [f"1.{i}" for i in range(100, 0, -1)]

# --- GUI Application Class ---

class PlayPort(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PlayPort - Minecraft Server Manager")
        self.geometry("1000x700")
        self.minsize(900, 600)
        self.configure(bg="#121212")
        
        # Set window icon (using Windows API for better icon support)
        try:
            self.iconbitmap(default=self.resource_path("icon.ico"))
        except:
            pass
        
        # Make window DPI aware for better scaling on high-DPI displays
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except:
            pass
        
        # Configure style
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Custom colors
        self.bg_color = "#121212"
        self.fg_color = "#e0e0e0"
        self.accent_color = "#d32f2f"
        self.secondary_color = "#424242"
        self.highlight_color = "#ff5252"
        
        # Configure styles
        self.style.configure('TFrame', background=self.bg_color)
        self.style.configure('TLabel', background=self.bg_color, foreground=self.fg_color, font=('Segoe UI', 10))
        self.style.configure('TButton', 
                           background=self.secondary_color, 
                           foreground=self.fg_color,
                           borderwidth=1,
                           relief='raised',
                           font=('Segoe UI', 10))
        self.style.map('TButton',
                      background=[('active', self.accent_color), ('pressed', self.highlight_color)],
                      foreground=[('active', 'white'), ('pressed', 'white')])
        self.style.configure('TEntry', 
                            fieldbackground=self.secondary_color, 
                            foreground=self.fg_color,
                            insertcolor=self.fg_color,
                            font=('Segoe UI', 10))
        self.style.configure('TCombobox', 
                           fieldbackground=self.secondary_color, 
                           foreground=self.fg_color,
                           selectbackground=self.accent_color,
                           font=('Segoe UI', 10))
        self.style.configure('TNotebook', background=self.bg_color, borderwidth=0)
        self.style.configure('TNotebook.Tab', 
                            background=self.secondary_color, 
                            foreground=self.fg_color,
                            padding=[10, 5],
                            font=('Segoe UI', 10, 'bold'))
        self.style.map('TNotebook.Tab',
                     background=[('selected', self.accent_color)],
                     foreground=[('selected', 'white')])
        self.style.configure('Treeview', 
                           background=self.secondary_color, 
                           foreground=self.fg_color,
                           fieldbackground=self.secondary_color,
                           font=('Segoe UI', 10))
        self.style.map('Treeview',
                     background=[('selected', self.accent_color)],
                     foreground=[('selected', 'white')])
        self.style.configure('Vertical.TScrollbar', 
                           background=self.secondary_color,
                           troughcolor=self.bg_color,
                           arrowcolor=self.fg_color)
        self.style.configure('Horizontal.TScrollbar', 
                           background=self.secondary_color,
                           troughcolor=self.bg_color,
                           arrowcolor=self.fg_color)
        self.style.configure('TProgressbar',
                           troughcolor=self.bg_color,
                           background=self.accent_color,
                           lightcolor=self.highlight_color,
                           darkcolor=self.accent_color)
        
        # Configure fonts
        self.title_font = Font(family="Segoe UI", size=16, weight="bold")
        self.subtitle_font = Font(family="Segoe UI", size=12, weight="bold")
        self.normal_font = Font(family="Segoe UI", size=10)
        
        # Queue for thread-safe GUI updates
        self.queue = Queue()
        
        # Initialize UI
        self.create_widgets()
        
        # Check for updates periodically
        self.after(100, self.process_queue)
        
        # Determine the base directory for servers
        if getattr(sys, 'frozen', False):
            CURRENT_DIR = Path(sys.executable).parent.resolve()
        else:
            CURRENT_DIR = Path(__file__).parent.resolve()
        
        global SERVERS_DIR
        SERVERS_DIR = CURRENT_DIR / "servers"
        SERVERS_DIR.mkdir(exist_ok=True)
        
        # Load server list
        self.load_server_list()
    
    def resource_path(self, relative_path):
        """ Get absolute path to resource, works for dev and for PyInstaller """
        try:
            # PyInstaller creates a temp folder and stores path in _MEIPASS
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")

        return os.path.join(base_path, relative_path)
    
    def create_widgets(self):
        """Create all GUI widgets."""
        # Main container
        self.main_frame = ttk.Frame(self)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Header
        self.header_frame = ttk.Frame(self.main_frame)
        self.header_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Logo and title
        self.logo_frame = ttk.Frame(self.header_frame)
        self.logo_frame.pack(side=tk.LEFT, padx=5)
        
        # Try to load logo image
        try:
            logo_img = Image.open(self.resource_path("playport_logo.png"))
            logo_img = logo_img.resize((40, 40), Image.LANCZOS)
            self.logo = ImageTk.PhotoImage(logo_img)
            logo_label = ttk.Label(self.logo_frame, image=self.logo, background=self.bg_color)
            logo_label.pack(side=tk.LEFT, padx=5)
        except:
            pass
        
        self.title_label = ttk.Label(self.header_frame, 
                                   text="PlayPort - Minecraft Server Manager", 
                                   font=self.title_font,
                                   foreground=self.highlight_color)
        self.title_label.pack(side=tk.LEFT, padx=5)
        
        # Notebook for tabs
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Create Server Tab
        self.create_server_tab()
        
        # Run Server Tab
        self.run_server_tab()
        
        # Console Tab
        self.console_tab()
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        self.status_bar = ttk.Label(self.main_frame, 
                                  textvariable=self.status_var,
                                  relief=tk.SUNKEN,
                                  anchor=tk.W,
                                  font=self.normal_font)
        self.status_bar.pack(fill=tk.X, pady=(5, 0))
    
    def create_server_tab(self):
        """Create the 'Create Server' tab."""
        self.create_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.create_tab, text="Create Server")
        
        # Form frame
        form_frame = ttk.Frame(self.create_tab)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Server Name
        ttk.Label(form_frame, text="Server Name:", font=self.subtitle_font).grid(
            row=0, column=0, sticky=tk.W, padx=10, pady=(10, 5))
        self.server_name_entry = ttk.Entry(form_frame, font=self.normal_font)
        self.server_name_entry.grid(
            row=0, column=1, sticky=tk.EW, padx=10, pady=(10, 5), columnspan=2)
        
        # Server Software
        ttk.Label(form_frame, text="Server Software:", font=self.subtitle_font).grid(
            row=1, column=0, sticky=tk.W, padx=10, pady=5)
        self.software_combo = ttk.Combobox(
            form_frame, values=SOFTWARE_OPTIONS, state="readonly", font=self.normal_font)
        self.software_combo.grid(
            row=1, column=1, sticky=tk.EW, padx=10, pady=5, columnspan=2)
        self.software_combo.bind("<<ComboboxSelected>>", self.on_software_select)
        
        # Version Selection
        ttk.Label(form_frame, text="Version:", font=self.subtitle_font).grid(
            row=2, column=0, sticky=tk.W, padx=10, pady=5)
        self.version_combo = ttk.Combobox(
            form_frame, state="readonly", font=self.normal_font)
        self.version_combo.grid(
            row=2, column=1, sticky=tk.EW, padx=10, pady=5)
        
        self.fetch_versions_btn = ttk.Button(
            form_frame, text="Fetch Versions", command=self.fetch_versions_threaded)
        self.fetch_versions_btn.grid(row=2, column=2, padx=10, pady=5)
        
        # Minecraft Version (for Fabric/Quilt)
        self.mc_version_label = ttk.Label(
            form_frame, text="Minecraft Version:", font=self.subtitle_font)
        self.mc_version_entry = ttk.Entry(form_frame, font=self.normal_font)
        
        # RAM Allocation
        ttk.Label(form_frame, text="RAM Allocation (MB):", font=self.subtitle_font).grid(
            row=4, column=0, sticky=tk.W, padx=10, pady=5)
        self.ram_entry = ttk.Entry(form_frame, font=self.normal_font)
        self.ram_entry.grid(row=4, column=1, sticky=tk.EW, padx=10, pady=5)
        self.ram_entry.insert(0, "2048")
        
        # Create Server Button
        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=5, column=0, columnspan=3, pady=20, sticky=tk.EW)
        
        self.create_btn = ttk.Button(
            btn_frame, text="Create Server", command=self.create_server_threaded)
        self.create_btn.pack(fill=tk.X, padx=10)
        
        # Progress bar
        self.progress = ttk.Progressbar(
            form_frame, orient=tk.HORIZONTAL, length=100, mode='determinate')
        self.progress.grid(row=6, column=0, columnspan=3, sticky=tk.EW, padx=10, pady=5)
        self.progress.grid_remove()
        
        # Configure grid weights
        form_frame.grid_columnconfigure(1, weight=1)
        form_frame.grid_rowconfigure(5, weight=1)
    
    def run_server_tab(self):
        """Create the 'Run Server' tab."""
        self.run_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.run_tab, text="Run Server")
        
        # Main frame
        main_frame = ttk.Frame(self.run_tab)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Server List
        ttk.Label(main_frame, text="Available Servers:", font=self.subtitle_font).pack(
            anchor=tk.W, padx=10, pady=(10, 5))
        
        # Treeview for server list with scrollbar
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.server_tree = ttk.Treeview(tree_frame, columns=('software', 'version', 'ram'), 
                                      selectmode='browse', show='headings')
        self.server_tree.heading('#0', text='Name')
        self.server_tree.heading('software', text='Software')
        self.server_tree.heading('version', text='Version')
        self.server_tree.heading('ram', text='RAM (MB)')
        
        self.server_tree.column('#0', width=200, anchor=tk.W)
        self.server_tree.column('software', width=150, anchor=tk.W)
        self.server_tree.column('version', width=150, anchor=tk.W)
        self.server_tree.column('ram', width=100, anchor=tk.W)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.server_tree.yview)
        self.server_tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack widgets
        self.server_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Button frame
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Buttons
        self.run_btn = ttk.Button(
            btn_frame, text="Run Server", command=self.run_server_threaded)
        self.run_btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        self.open_folder_btn = ttk.Button(
            btn_frame, text="Open Folder", command=self.open_server_folder)
        self.open_folder_btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        self.delete_btn = ttk.Button(
            btn_frame, text="Delete Server", command=self.delete_server)
        self.delete_btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        self.refresh_btn = ttk.Button(
            btn_frame, text="Refresh List", command=self.load_server_list)
        self.refresh_btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
    
    def console_tab(self):
        """Create the console output tab."""
        self.console_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.console_tab, text="Console")
        
        # Console frame
        console_frame = ttk.Frame(self.console_tab)
        console_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Console output
        self.console = scrolledtext.ScrolledText(
            console_frame, bg=self.secondary_color, fg=self.fg_color,
            insertbackground=self.fg_color, font=('Consolas', 10))
        self.console.pack(fill=tk.BOTH, expand=True)
        self.console.configure(state='disabled')
        
        # Button frame
        btn_frame = ttk.Frame(console_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Buttons
        self.clear_console_btn = ttk.Button(
            btn_frame, text="Clear Console", command=self.clear_console)
        self.clear_console_btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        self.copy_btn = ttk.Button(
            btn_frame, text="Copy to Clipboard", command=self.copy_console)
        self.copy_btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
    
    def on_software_select(self, event):
        """Handle software selection change."""
        software = self.software_combo.get()
        self.version_combo.set('')
        
        # Show/hide Minecraft version field for Fabric/Quilt
        if software.lower() in ["fabric", "quilt"]:
            self.mc_version_label.grid(row=3, column=0, sticky=tk.W, padx=10, pady=5)
            self.mc_version_entry.grid(row=3, column=1, sticky=tk.EW, padx=10, pady=5, columnspan=2)
        else:
            self.mc_version_label.grid_remove()
            self.mc_version_entry.grid_remove()
    
    def fetch_versions_threaded(self):
        """Start version fetching in a separate thread."""
        software = self.software_combo.get()
        if not software:
            messagebox.showwarning("Warning", "Please select a server software first.")
            return
        
        self.fetch_versions_btn.config(state=tk.DISABLED)
        self.version_combo.config(state=tk.DISABLED)
        self.status_var.set(f"Fetching versions for {software}...")
        
        Thread(target=self.fetch_versions, args=(software,), daemon=True).start()
    
    def fetch_versions(self, software):
        """Fetch available versions for the selected software."""
        try:
            versions = fetch_versions(software.lower())
            
            if not versions:
                self.queue.put(("error", f"No versions found for {software}."))
                return
            
            self.queue.put(("set_versions", versions))
            self.queue.put(("status", f"Found {len(versions)} versions for {software}"))
        except Exception as e:
            self.queue.put(("error", f"Error fetching versions: {str(e)}"))
        finally:
            self.queue.put(("enable_fetch_btn",))
    
    def create_server_threaded(self):
        """Start server creation in a separate thread."""
        # Validate inputs
        name = self.server_name_entry.get().strip()
        if not name:
            messagebox.showwarning("Warning", "Please enter a server name.")
            return
        
        if (SERVERS_DIR / name).exists():
            messagebox.showwarning("Warning", f"A server named '{name}' already exists.")
            return
        
        software = self.software_combo.get()
        if not software:
            messagebox.showwarning("Warning", "Please select server software.")
            return
        
        version = self.version_combo.get()
        if not version and software.lower() != "nukkit":
            messagebox.showwarning("Warning", "Please select a version.")
            return
        
        ram = self.ram_entry.get().strip()
        if not ram.isdigit() or int(ram) <= 0:
            messagebox.showwarning("Warning", "Please enter a valid RAM allocation (positive number).")
            return
        
        mc_version = None
        if software.lower() in ["fabric", "quilt"]:
            mc_version = self.mc_version_entry.get().strip()
            if not mc_version:
                messagebox.showwarning("Warning", "Please enter a Minecraft version for Fabric/Quilt.")
                return
        
        # Disable UI during creation
        self.create_btn.config(state=tk.DISABLED)
        self.server_name_entry.config(state=tk.DISABLED)
        self.software_combo.config(state=tk.DISABLED)
        self.version_combo.config(state=tk.DISABLED)
        self.mc_version_entry.config(state=tk.DISABLED)
        self.ram_entry.config(state=tk.DISABLED)
        self.fetch_versions_btn.config(state=tk.DISABLED)
        
        # Show progress bar
        self.progress.grid()
        self.progress["value"] = 0
        self.status_var.set(f"Creating {name} server...")
        
        # Start creation in a thread
        Thread(target=self.create_server, args=(name, software, version, mc_version, ram), daemon=True).start()
    
    def create_server(self, name, software, version, mc_version, ram):
        """Create the server in a background thread."""
        try:
            server_path = SERVERS_DIR / name
            server_path.mkdir(parents=True, exist_ok=True)
            
            # Accept EULA automatically
            eula_path = server_path / "eula.txt"
            eula_path.write_text("eula=true\n")
            self.queue.put(("log", "EULA accepted automatically."))
            
            # Update progress
            self.queue.put(("progress", 10))
            
            # Download server file
            self.queue.put(("log", f"Downloading {software} server file..."))
            jar_or_phar_path = download_server_jar(software.lower(), version, server_path)
            
            if not jar_or_phar_path:
                self.queue.put(("error", "Failed to download server file."))
                return
            
            self.queue.put(("progress", 40))
            self.queue.put(("log", f"Downloaded server file to {jar_or_phar_path}"))
            
            server_exec_path = jar_or_phar_path
            
            # Handle installers
            if software.lower() in ["forge", "fabric", "neoforge", "quilt"]:
                self.queue.put(("log", f"Running {software} installer..."))
                installed_server_path = run_installer(jar_or_phar_path, server_path, mc_version)
                
                if installed_server_path is False:
                    self.queue.put(("error", f"Failed to run {software} installer."))
                    return
                elif installed_server_path is not True:
                    server_exec_path = installed_server_path
                    self.queue.put(("log", f"Installer completed. Server executable: {server_exec_path}"))
                
                self.queue.put(("progress", 70))
            
            # Create start script
            self.queue.put(("log", "Creating start script..."))
            start_script = None
            
            if server_exec_path.suffix.lower() == ".jar":
                if software.lower() == "neoforge":
                    start_script = create_start_script_neoforge(server_path, version, ram)
                else:
                    start_script = create_start_script(server_path, server_exec_path, ram)
            elif server_exec_path.suffix.lower() == ".phar":
                start_script = create_start_script_pocketmine(server_path, server_exec_path)
            
            if not start_script:
                self.queue.put(("log", "Warning: Failed to create start script."))
            
            self.queue.put(("progress", 90))
            
            # Write metadata
            (server_path / "server.properties").write_text(
                f"server-name={name}\nsoftware={software}\nversion={version if version else 'latest'}\nram={ram}MB\n"
            )
            
            self.queue.put(("progress", 100))
            self.queue.put(("log", f"Server '{name}' setup complete!"))
            self.queue.put(("success", f"Server '{name}' created successfully!"))
            
            # Open folder
            self.queue.put(("open_folder", server_path))
            
            # Start server
            self.queue.put(("start_server", server_path))
            
            # Refresh server list
            self.queue.put(("load_server_list",))
        
        except Exception as e:
            self.queue.put(("error", f"An error occurred while creating server: {str(e)}"))
        finally:
            self.queue.put(("enable_create_ui",))
    
    def run_server_threaded(self):
        """Start server in a separate thread."""
        selected = self.server_tree.focus()
        if not selected:
            messagebox.showwarning("Warning", "Please select a server first.")
            return
        
        server_name = self.server_tree.item(selected, "text")
        server_path = SERVERS_DIR / server_name
        
        self.run_btn.config(state=tk.DISABLED)
        self.status_var.set(f"Starting {server_name} server...")
        
        Thread(target=self.run_server, args=(server_path,), daemon=True).start()
    
    def run_server(self, server_path):
        """Run the selected server."""
        try:
            start_script = None
            if (server_path / "start.bat").exists():
                start_script = server_path / "start.bat"
            elif (server_path / "start.sh").exists():
                start_script = server_path / "start.sh"
            
            if not start_script:
                self.queue.put(("error", "No start script found in server folder!"))
                return
            
            # Open folder
            self.queue.put(("open_folder", server_path))
            
            # Start server
            self.queue.put(("start_server", server_path))
            
            self.queue.put(("log", f"Started server: {server_path.name}"))
            self.queue.put(("status", f"Running {server_path.name} server"))
        
        except Exception as e:
            self.queue.put(("error", f"Error starting server: {str(e)}"))
        finally:
            self.queue.put(("enable_run_btn",))
    
    def open_server_folder(self):
        """Open the selected server's folder."""
        selected = self.server_tree.focus()
        if not selected:
            messagebox.showwarning("Warning", "Please select a server first.")
            return
        
        server_name = self.server_tree.item(selected, "text")
        server_path = SERVERS_DIR / server_name
        
        try:
            os.startfile(server_path)
            self.status_var.set(f"Opened folder: {server_name}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open folder: {str(e)}")
    
    def delete_server(self):
        """Delete the selected server."""
        selected = self.server_tree.focus()
        if not selected:
            messagebox.showwarning("Warning", "Please select a server first.")
            return
        
        server_name = self.server_tree.item(selected, "text")
        
        if not messagebox.askyesno("Confirm", f"Are you sure you want to delete server '{server_name}'?"):
            return
        
        server_path = SERVERS_DIR / server_name
        
        try:
            import shutil
            shutil.rmtree(server_path)
            self.load_server_list()
            self.status_var.set(f"Deleted server: {server_name}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not delete server: {str(e)}")
    
    def load_server_list(self):
        """Load the list of existing servers."""
        self.server_tree.delete(*self.server_tree.get_children())
        
        servers = [f for f in SERVERS_DIR.iterdir() if f.is_dir()]
        if not servers:
            self.status_var.set("No servers found")
            return
        
        for server in servers:
            server_properties = server / "server.properties"
            software = "Unknown"
            version = "Unknown"
            ram = "Unknown"
            
            if server_properties.exists():
                try:
                    props = {}
                    with open(server_properties, 'r') as f:
                        for line in f:
                            if '=' in line:
                                key, value = line.strip().split('=', 1)
                                props[key] = value
                    
                    software = props.get('software', 'Unknown')
                    version = props.get('version', 'Unknown')
                    ram = props.get('ram', 'Unknown')
                except:
                    pass
            
            self.server_tree.insert('', 'end', text=server.name, 
                                  values=(software, version, ram))
        
        self.status_var.set(f"Found {len(servers)} servers")
    
    def clear_console(self):
        """Clear the console output."""
        self.console.config(state='normal')
        self.console.delete(1.0, tk.END)
        self.console.config(state='disabled')
    
    def copy_console(self):
        """Copy console content to clipboard."""
        self.clipboard_clear()
        self.clipboard_append(self.console.get(1.0, tk.END))
        self.status_var.set("Console content copied to clipboard")
    
    def log_message(self, message):
        """Add a message to the console."""
        self.console.config(state='normal')
        self.console.insert(tk.END, message + "\n")
        self.console.see(tk.END)
        self.console.config(state='disabled')
    
    def process_queue(self):
        """Process messages from the queue to update the GUI safely."""
        while not self.queue.empty():
            try:
                msg = self.queue.get_nowait()
                
                if msg[0] == "log":
                    self.log_message(msg[1])
                elif msg[0] == "error":
                    messagebox.showerror("Error", msg[1])
                    self.log_message(f"ERROR: {msg[1]}")
                elif msg[0] == "success":
                    messagebox.showinfo("Success", msg[1])
                    self.log_message(f"SUCCESS: {msg[1]}")
                elif msg[0] == "status":
                    self.status_var.set(msg[1])
                elif msg[0] == "set_versions":
                    self.version_combo.config(state='normal')
                    self.version_combo['values'] = msg[1]
                    self.version_combo.config(state='readonly')
                elif msg[0] == "enable_fetch_btn":
                    self.fetch_versions_btn.config(state=tk.NORMAL)
                    self.version_combo.config(state='readonly')
                elif msg[0] == "enable_create_ui":
                    self.create_btn.config(state=tk.NORMAL)
                    self.server_name_entry.config(state=tk.NORMAL)
                    self.software_combo.config(state='readonly')
                    self.version_combo.config(state='readonly')
                    self.mc_version_entry.config(state=tk.NORMAL)
                    self.ram_entry.config(state=tk.NORMAL)
                    self.fetch_versions_btn.config(state=tk.NORMAL)
                    self.progress.grid_remove()
                elif msg[0] == "enable_run_btn":
                    self.run_btn.config(state=tk.NORMAL)
                elif msg[0] == "progress":
                    self.progress["value"] = msg[1]
                elif msg[0] == "open_folder":
                    os.startfile(msg[1])
                elif msg[0] == "start_server":
                    self.start_server(msg[1])
                elif msg[0] == "load_server_list":
                    self.load_server_list()
                
            except Exception as e:
                self.log_message(f"Error processing queue message: {str(e)}")
        
        self.after(100, self.process_queue)
    
    def start_server(self, server_path):
        """Start the server process."""
        start_script = None
        if (server_path / "start.bat").exists():
            start_script = server_path / "start.bat"
        elif (server_path / "start.sh").exists():
            start_script = server_path / "start.sh"
        
        if not start_script:
            self.log_message("ERROR: No start script found in server folder!")
            return
        
        try:
            subprocess.Popen(
                f'start cmd /k "{start_script}"', 
                shell=True, 
                cwd=server_path,
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
        except Exception as e:
            self.log_message(f"ERROR: Failed to start server: {str(e)}")

# --- Utility Functions ---

def version_key(v):
    """Helper function to sort version strings numerically."""
    parts = re.split(r'[.-]', v)
    numeric_parts = []
    for part in parts:
        try:
            numeric_parts.append(int(part))
        except ValueError:
            numeric_parts.append(0)
    return tuple(numeric_parts)

def fetch_versions(software: str) -> list:
    """Fetches available versions for a given server software from its API."""
    software = software.lower()
    url = versions_urls.get(software)

    if software == "nukkit":
        return ["Latest"]

    if url is None:
        print(f"No version fetching URL defined for {software}. Returning dummy versions.")
        return DUMMY_VERSIONS

    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()

        if software in ["forge", "neoforge"]:
            root = ET.fromstring(res.content)
            versions = [v.text for v in root.findall("./versioning/versions/version")]
            versions.sort(key=version_key, reverse=True)
            return versions[:100]

        if software == "spigot":
            version_pattern = re.compile(r"^\d+(\.\d+){1,2}$")
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
            return [v["id"] for v in data["versions"] if v["type"] == "release"][:100]
        if software == "pufferfish":
            return [job["name"] for job in data.get("jobs", [])][::-1][:100]
        if software == "purpur":
            return data.get("versions", [])[::-1][:100]
        if software in ["fabric", "quilt"]:
            return [v["version"] for v in data][:100]
        if software == "pocketmine-mp":
            versions = []
            for release in data:
                if any(asset["name"].endswith(".phar") for asset in release.get("assets", [])):
                    versions.append(release.get("tag_name", "unknown"))
            return versions[:100]
        if software == "bungeecord":
            return [str(build['number']) for build in data.get('builds', [])][:100]

        return data.get("versions", [])[::-1][:100]

    except requests.exceptions.RequestException as req_err:
        print(f"Network or API error fetching versions for {software}: {req_err}")
    except (json.JSONDecodeError, ET.ParseError) as parse_err:
        print(f"Error parsing response for {software}: {parse_err}")
    except Exception as e:
        print(f"An unexpected error occurred while fetching versions for {software}: {e}")

    return DUMMY_VERSIONS

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
            installer_url = versions_urls["fabric"]
            res = requests.get(installer_url, timeout=10)
            res.raise_for_status()
            installers = res.json()
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
            download_url = versions_urls["nukkit"]
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
            latest_build = builds_data["builds"][-1]

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

        if not download_url or not file_name:
            print(f"Error: Could not determine download URL or file name for '{server_type}'.")
            return False

        jar_path = dest_folder / file_name
        print(f"Downloading {server_type} server file to {jar_path} from {download_url}...")

        with requests.get(download_url, stream=True, timeout=300) as r:
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
        output_exec_path = target_folder
    elif "neoforge" in software_name:
        command.append("--installServer")
        pass
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
        subprocess.run(
            command,
            cwd=target_folder,
            check=True,
            capture_output=True,
            text=True
        )
        print(f"{software_name.replace('_installer', '').title()} server setup completed.")

        if "neoforge" in software_name:
            return True

        if "forge" in software_name:
            candidate_jars = [f for f in target_folder.glob("*.jar") if "installer" not in f.name.lower()]
            if candidate_jars:
                actual_forge_jar = max(candidate_jars, key=os.path.getsize)
                print(f"Detected Forge executable: {actual_forge_jar.name}")
                return actual_forge_jar
            else:
                print("Warning: Could not find a clear Forge executable JAR after installation.")
                return False

        return output_exec_path
    except subprocess.CalledProcessError as e:
        print(f"Error running {software_name.replace('_installer', '').title()} installer: {e}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred while running {software_name.replace('_installer', '').title()} installer: {e}")
        return False

# --- Start Script Creation Functions ---

def create_start_script(dest_folder: Path, server_exec_path: Path, ram_mb: str) -> Path:
    """Creates a generic start script for JAR files."""
    ram_mb_int = int(ram_mb)
    script_name = "start.bat"
    script_path = dest_folder / script_name

    content = f'@echo off\njava -Xmx{ram_mb_int}M -Xms{ram_mb_int}M -jar "{server_exec_path.name}" nogui\npause'

    script_path.write_text(content)
    print(f"Created start script at {script_path}")
    return script_path

def create_start_script_neoforge(dest_folder: Path, version: str, ram_mb: str) -> Path:
    """Creates a start script specifically for NeoForge, which uses a different launch mechanism."""
    ram_mb_int = int(ram_mb)
    script_name = "start.bat"
    script_path = dest_folder / script_name

    args_file = f"libraries/net/neoforged/neoforge/{version}/win_args.txt"

    content = f'@echo off\njava -Xmx{ram_mb_int}M -Xms{ram_mb_int}M @user_jvm_args.txt @{args_file} nogui\npause'

    script_path.write_text(content)
    print(f"Created NeoForge start script at {script_path}")
    return script_path

def create_start_script_pocketmine(dest_folder: Path, phar_path: Path) -> Path:
    """Creates a start script for PocketMine-MP (PHAR files)."""
    script_name = "start.bat"
    script_path = dest_folder / script_name

    content = f'@echo off\nphp "{phar_path.name}"\npause'

    script_path.write_text(content)
    print(f"Created PocketMine-MP start script at {script_path}")
    return script_path

def open_folder_in_os(folder_path: Path):
    """Opens a given folder in Windows Explorer."""
    try:
        os.startfile(folder_path)
        print(f"Opened folder: {folder_path}")
    except Exception as e:
        print(f"Could not open folder: {str(e)}")

if __name__ == "__main__":
    app = PlayPort()
    app.mainloop()