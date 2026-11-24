import os
import sys
import uuid
import json
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import minecraft_launcher_lib

APP_DIR = os.path.join(os.path.expanduser("~"), ".fishlauncher")
INSTANCES_DIR = os.path.join(APP_DIR, "instances")
CONFIG_FILE = os.path.join(APP_DIR, "config.json")


class MinecraftLauncherApp:
    def __init__(self, root):
        self.root = root
        self.root.title("FishLauncher")
        self.root.geometry("820x520")
        self.root.minsize(750, 480)
        self.root.configure(bg="#1e1e2e")

        os.makedirs(INSTANCES_DIR, exist_ok=True)
        self.config = self.load_config()
        self.versions_cache = []
        self.is_running = False

        self.setup_styles()
        self.build_ui()
        self.refresh_instances()
        self.fetch_versions_async()

    def load_config(self):
        default_cfg = {
            "username": "Player",
            "ram_mb": 4096,
            "java_path": "",
            "last_instance": ""
        }
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    default_cfg.update(data)
            except Exception:
                pass
        return default_cfg

    def save_config(self):
        self.config["username"] = self.username_var.get().strip() or "Player"
        try:
            self.config["ram_mb"] = int(self.ram_var.get())
        except ValueError:
            self.config["ram_mb"] = 4096
        self.config["java_path"] = self.java_var.get().strip()
        selected = self.get_selected_instance()
        if selected:
            self.config["last_instance"] = selected
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2)

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        bg_dark = "#1e1e2e"
        bg_panel = "#252536"
        fg_text = "#cdd6f4"
        accent = "#89b4fa"
        btn_bg = "#313244"

        style.configure("TFrame", background=bg_dark)
        style.configure("Panel.TFrame", background=bg_panel)
        style.configure("TLabel", background=bg_dark, foreground=fg_text, font=("Segoe UI", 10))
        style.configure("Panel.TLabel", background=bg_panel, foreground=fg_text, font=("Segoe UI", 10))
        style.configure("Title.TLabel", background=bg_dark, foreground=accent, font=("Segoe UI", 15, "bold"))
        style.configure("TButton", background=btn_bg, foreground=fg_text, borderwidth=0, padding=6, font=("Segoe UI", 10))
        style.map("TButton", background=[("active", "#45475a")])

        style.configure("Play.TButton", background="#a6e3a1", foreground="#11111b", font=("Segoe UI", 11, "bold"), padding=10)
        style.map("Play.TButton", background=[("active", "#94e2d5"), ("disabled", "#585b70")])

        style.configure("TEntry", fieldbackground="#313244", foreground=fg_text, insertcolor=fg_text, borderwidth=0)
        style.configure("TCombobox", fieldbackground="#313244", background=btn_bg, foreground=fg_text, arrowcolor=fg_text)
        style.configure("TCheckbutton", background=bg_dark, foreground=fg_text, font=("Segoe UI", 9))
        style.map("TCheckbutton", background=[("active", bg_dark)])
        style.configure("Horizontal.TProgressbar", troughcolor="#313244", background=accent, thickness=14)

    def build_ui(self):
        # Top Header Bar
        header = ttk.Frame(self.root, padding=(15, 10))
        header.pack(fill=tk.X)

        ttk.Label(header, text="FishLauncher", style="Title.TLabel").pack(side=tk.LEFT)

        acc_frame = ttk.Frame(header)
        acc_frame.pack(side=tk.RIGHT)
        ttk.Label(acc_frame, text="Account (Offline):").pack(side=tk.LEFT, padx=(0, 6))
        self.username_var = tk.StringVar(value=self.config["username"])
        ttk.Entry(acc_frame, textvariable=self.username_var, width=18).pack(side=tk.LEFT)

        # Main Split Content
        main = ttk.Frame(self.root, padding=(15, 5))
        main.pack(fill=tk.BOTH, expand=True)

        # Left: Instances List
        left_panel = ttk.Frame(main, style="Panel.TFrame", padding=10)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        inst_header = ttk.Frame(left_panel, style="Panel.TFrame")
        inst_header.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(inst_header, text="Instances", style="Panel.TLabel", font=("Segoe UI", 11, "bold")).pack(side=tk.LEFT)
        ttk.Button(inst_header, text="Delete", command=self.delete_instance).pack(side=tk.RIGHT, padx=(4, 0))
        ttk.Button(inst_header, text="Open Folder", command=self.open_instance_folder).pack(side=tk.RIGHT)

        self.instance_listbox = tk.Listbox(
            left_panel,
            bg="#181825",
            fg="#cdd6f4",
            selectbackground="#89b4fa",
            selectforeground="#11111b",
            font=("Segoe UI", 11),
            borderwidth=0,
            highlightthickness=0,
            activestyle="none"
        )
        self.instance_listbox.pack(fill=tk.BOTH, expand=True)
        self.instance_listbox.bind("<<ListboxSelect>>", self.on_instance_select)

        # Right: Create Instance & Settings
        right_panel = ttk.Frame(main, style="Panel.TFrame", padding=12, width=290)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y)
        right_panel.pack_propagate(False)

        ttk.Label(right_panel, text="New Instance", style="Panel.TLabel", font=("Segoe UI", 11, "bold")).pack(anchor=tk.W, pady=(0, 8))

        ttk.Label(right_panel, text="Instance Name:", style="Panel.TLabel").pack(anchor=tk.W)
        self.new_name_var = tk.StringVar()
        ttk.Entry(right_panel, textvariable=self.new_name_var).pack(fill=tk.X, pady=(2, 8))

        ttk.Label(right_panel, text="Minecraft Version:", style="Panel.TLabel").pack(anchor=tk.W)
        self.version_var = tk.StringVar()
        self.version_combo = ttk.Combobox(right_panel, textvariable=self.version_var, state="readonly")
        self.version_combo.pack(fill=tk.X, pady=(2, 4))

        self.show_snapshots_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            right_panel,
            text="Show Snapshots / Old Versions",
            variable=self.show_snapshots_var,
            command=self.update_version_dropdown
        ).pack(anchor=tk.W, pady=(0, 8))

        ttk.Label(right_panel, text="Mod Loader:", style="Panel.TLabel").pack(anchor=tk.W)
        self.loader_var = tk.StringVar(value="Vanilla")
        ttk.Combobox(
            right_panel,
            textvariable=self.loader_var,
            values=["Vanilla", "Fabric", "Forge", "NeoForge", "Quilt"],
            state="readonly"
        ).pack(fill=tk.X, pady=(2, 10))

        ttk.Button(right_panel, text="+ Create Instance", command=self.create_instance).pack(fill=tk.X, pady=(0, 15))

        ttk.Separator(right_panel, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=6)

        ttk.Label(right_panel, text="JVM Settings", style="Panel.TLabel", font=("Segoe UI", 11, "bold")).pack(anchor=tk.W, pady=(4, 8))

        ram_row = ttk.Frame(right_panel, style="Panel.TFrame")
        ram_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(ram_row, text="Max RAM (MB):", style="Panel.TLabel").pack(side=tk.LEFT)
        self.ram_var = tk.StringVar(value=str(self.config["ram_mb"]))
        ttk.Entry(ram_row, textvariable=self.ram_var, width=10).pack(side=tk.RIGHT)

        ttk.Label(right_panel, text="Java Executable (optional):", style="Panel.TLabel").pack(anchor=tk.W)
        java_row = ttk.Frame(right_panel, style="Panel.TFrame")
        java_row.pack(fill=tk.X, pady=(2, 0))
        self.java_var = tk.StringVar(value=self.config["java_path"])
        ttk.Entry(java_row, textvariable=self.java_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        ttk.Button(java_row, text="...", width=3, command=self.browse_java).pack(side=tk.RIGHT)

        # Bottom Bar: Progress & Launch
        footer = ttk.Frame(self.root, padding=(15, 10))
        footer.pack(fill=tk.X, side=tk.BOTTOM)

        progress_frame = ttk.Frame(footer)
        progress_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 15))

        self.status_var = tk.StringVar(value="Ready.")
        ttk.Label(progress_frame, textvariable=self.status_var).pack(anchor=tk.W, pady=(0, 4))

        self.progress = ttk.Progressbar(progress_frame, mode="determinate")
        self.progress.pack(fill=tk.X)

        self.play_btn = ttk.Button(footer, text="PLAY", style="Play.TButton", width=16, command=self.launch_selected)
        self.play_btn.pack(side=tk.RIGHT)

    def browse_java(self):
        path = filedialog.askopenfilename(title="Select java.exe / javaw.exe")
        if path:
            self.java_var.set(path)

    def fetch_versions_async(self):
        self.status_var.set("Fetching Minecraft version manifest...")
        def worker():
            try:
                versions = minecraft_launcher_lib.utils.get_version_list()
                self.versions_cache = versions
                self.root.after(0, self.update_version_dropdown)
                self.root.after(0, lambda: self.status_var.set("Ready."))
            except Exception as e:
                self.root.after(0, lambda: self.status_var.set(f"Offline / Version fetch failed: {e}"))
        threading.Thread(target=worker, daemon=True).start()

    def update_version_dropdown(self):
        show_all = self.show_snapshots_var.get()
        filtered = [
            v["id"] for v in self.versions_cache
            if show_all or v["type"] == "release"
        ]
        self.version_combo["values"] = filtered
        if filtered:
            self.version_var.set(filtered[0])

    def refresh_instances(self):
        self.instance_listbox.delete(0, tk.END)
        if not os.path.exists(INSTANCES_DIR):
            return
        names = sorted(os.listdir(INSTANCES_DIR))
        select_idx = 0
        for i, name in enumerate(names):
            meta_path = os.path.join(INSTANCES_DIR, name, "instance.json")
            if os.path.isfile(meta_path):
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                label = f"{name}   [{meta.get('version', '?')} • {meta.get('loader', 'Vanilla')}]"
                self.instance_listbox.insert(tk.END, label)
                if name == self.config.get("last_instance"):
                    select_idx = self.instance_listbox.size() - 1
        if self.instance_listbox.size() > 0:
            self.instance_listbox.selection_set(select_idx)

    def get_selected_instance(self):
        sel = self.instance_listbox.curselection()
        if not sel:
            return None
        text = self.instance_listbox.get(sel[0])
        return text.split("   [")[0].strip()

    def on_instance_select(self, _event=None):
        self.save_config()

    def create_instance(self):
        name = self.new_name_var.get().strip()
        version = self.version_var.get().strip()
        loader = self.loader_var.get().strip()

        if not name:
            name = f"{version}-{loader}"
        if not version:
            messagebox.showwarning("Missing Version", "Select a Minecraft version first.")
            return

        inst_path = os.path.join(INSTANCES_DIR, name)
        if os.path.exists(inst_path):
            messagebox.showerror("Exists", f"Instance '{name}' already exists.")
            return

        os.makedirs(os.path.join(inst_path, ".minecraft"), exist_ok=True)
        meta = {"name": name, "version": version, "loader": loader}
        with open(os.path.join(inst_path, "instance.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        self.new_name_var.set("")
        self.config["last_instance"] = name
        self.refresh_instances()
        self.status_var.set(f"Created instance '{name}'.")

    def delete_instance(self):
        name = self.get_selected_instance()
        if not name:
            return
        if messagebox.askyesno("Delete Instance", f"Delete '{name}' and all its saves/mods?"):
            import shutil
            shutil.rmtree(os.path.join(INSTANCES_DIR, name), ignore_errors=True)
            self.refresh_instances()
            self.status_var.set(f"Deleted '{name}'.")

    def open_instance_folder(self):
        name = self.get_selected_instance()
        if not name:
            return
        mc_dir = os.path.join(INSTANCES_DIR, name, ".minecraft")
        os.makedirs(mc_dir, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(mc_dir)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", mc_dir])
        else:
            subprocess.Popen(["xdg-open", mc_dir])

    def set_progress_max(self, maximum):
        self.root.after(0, lambda: self.progress.configure(maximum=max(1, maximum)))

    def set_progress(self, value):
        self.root.after(0, lambda: self.progress.configure(value=value))

    def set_status(self, text):
        self.root.after(0, lambda: self.status_var.set(text))

    def launch_selected(self):
        if self.is_running:
            return
        name = self.get_selected_instance()
        if not name:
            messagebox.showinfo("No Instance", "Create and select an instance first.")
            return

        self.save_config()
        inst_path = os.path.join(INSTANCES_DIR, name)
        with open(os.path.join(inst_path, "instance.json"), "r", encoding="utf-8") as f:
            meta = json.load(f)

        self.is_running = True
        self.play_btn.configure(state=tk.DISABLED)

        threading.Thread(
            target=self._install_and_run_worker,
            args=(inst_path, meta),
            daemon=True
        ).start()

    def _install_and_run_worker(self, inst_path, meta):
        mc_dir = os.path.join(inst_path, ".minecraft")
        mc_version = meta["version"]
        loader = meta.get("loader", "Vanilla")

        callback = {
            "setStatus": self.set_status,
            "setProgress": self.set_progress,
            "setMax": self.set_progress_max
        }

        try:
            self.set_status(f"Installing/verifying Minecraft {mc_version}...")
            minecraft_launcher_lib.install.install_minecraft_version(mc_version, mc_dir, callback=callback)

            launch_version_id = mc_version

            if loader != "Vanilla":
                self.set_status(f"Installing {loader} for {mc_version}...")
                loader_id = loader.lower()
                mod_loader = minecraft_launcher_lib.mod_loader.get_mod_loader(loader_id)
                loader_versions = mod_loader.get_loader_versions(mc_version, stable_only=False)
                if not loader_versions:
                    raise RuntimeError(f"No {loader} version found for Minecraft {mc_version}.")
                launch_version_id = mod_loader.install(mc_version, mc_dir, loader_version=loader_versions[0], callback=callback)

            username = self.config["username"]
            offline_uuid = str(uuid.uuid3(uuid.NAMESPACE_DNS, f"OfflinePlayer:{username}"))

            options = {
                "username": username,
                "uuid": offline_uuid,
                "token": "0",
                "jvmArguments": [f"-Xmx{self.config['ram_mb']}M", f"-Xms512M"]
            }
            if self.config["java_path"]:
                options["executablePath"] = self.config["java_path"]

            self.set_status("Building launch command...")
            cmd = minecraft_launcher_lib.command.get_minecraft_command(launch_version_id, mc_dir, options)

            self.set_status(f"Running {meta['name']}...")
            subprocess.Popen(cmd, cwd=mc_dir)
            self.set_status("Game launched!")
        except Exception as e:
            self.set_status("Launch failed.")
            self.root.after(0, lambda err=str(e): messagebox.showerror("Launch Error", err))
        finally:
            self.is_running = False
            self.root.after(0, lambda: self.play_btn.configure(state=tk.NORMAL))


if __name__ == "__main__":
    root = tk.Tk()
    app = MinecraftLauncherApp(root)
    root.mainloop()
