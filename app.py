import os
import sys
import json
import socket
import subprocess
import time
import threading
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import winreg
import pystray
from PIL import Image, ImageTk

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.abspath(os.path.dirname(sys.executable))
else:
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "WinPHP"

def set_startup(enabled=True):
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_SET_VALUE)
    try:
        if enabled:
            if getattr(sys, 'frozen', False):
                app_path = f'"{sys.executable}"'
            else:
                exe_path = os.path.join(BASE_DIR, 'WinPHP.exe')
                if os.path.exists(exe_path):
                    app_path = f'"{exe_path}"'
                else:
                    app_path = f'"{sys.executable}" "{os.path.join(BASE_DIR, "app.py")}"'
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, app_path)
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
    finally:
        winreg.CloseKey(key)

def is_startup_enabled():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_READ)
        try:
            winreg.QueryValueEx(key, APP_NAME)
            return True
        except FileNotFoundError:
            return False
        finally:
            winreg.CloseKey(key)
    except Exception:
        return False

BIN_DIR = os.path.join(BASE_DIR, 'bin')
TOOLS_DIR = os.path.join(BASE_DIR, 'tools')
WWW_DIR = os.path.join(BASE_DIR, 'www')
PID_FILE = os.path.join(BASE_DIR, 'bin', 'services_pids.json')
DB_CONFIG_FILE = os.path.join(BASE_DIR, 'bin', 'db_config.json')
PORTS_CONFIG_FILE = os.path.join(BASE_DIR, 'bin', 'ports_config.json')

# Detach processes from parent job/console so they survive app.py restarts
DETACHED_FLAGS = subprocess.DETACHED_PROCESS | 0x02000000  # DETACHED_PROCESS | CREATE_NO_WINDOW

DEFAULT_PORTS = {
    'nginx': 80,
    'apache': 8080,
    'mysql': 3306,
    'php': 9000
}

def load_ports():
    if os.path.exists(PORTS_CONFIG_FILE):
        try:
            with open(PORTS_CONFIG_FILE, 'r') as f:
                loaded = json.load(f)
                ports = {}
                for k, v in DEFAULT_PORTS.items():
                    ports[k] = int(loaded.get(k, v))
                return ports
        except Exception:
            pass
    return DEFAULT_PORTS.copy()

def save_ports(ports):
    os.makedirs(os.path.dirname(PORTS_CONFIG_FILE), exist_ok=True)
    try:
        with open(PORTS_CONFIG_FILE, 'w') as f:
            json.dump(ports, f, indent=4)
    except Exception as e:
        print("Error saving ports:", e)

PORTS = load_ports()

def update_service_port_in_config(name, old_port, new_port):
    if name == 'nginx':
        nginx_conf = os.path.join(BIN_DIR, 'nginx', 'conf', 'nginx.conf')
        if os.path.exists(nginx_conf):
            try:
                with open(nginx_conf, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                import re
                content = re.sub(rf'listen\s+{old_port}\b', f'listen       {new_port}', content)
                with open(nginx_conf, 'w', encoding='utf-8') as f:
                    f.write(content)
            except Exception as e:
                print(f"Error updating Nginx port: {e}")
                
    elif name == 'apache':
        apache_conf = os.path.join(BIN_DIR, 'apache', 'conf', 'httpd.conf')
        if os.path.exists(apache_conf):
            try:
                with open(apache_conf, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                import re
                content = re.sub(rf'Listen\s+{old_port}\b', f'Listen {new_port}', content)
                with open(apache_conf, 'w', encoding='utf-8') as f:
                    f.write(content)
            except Exception as e:
                print(f"Error updating Apache port: {e}")
                
    elif name == 'mysql':
        mysql_conf = os.path.join(BIN_DIR, 'mysql', 'my.ini')
        if os.path.exists(mysql_conf):
            try:
                with open(mysql_conf, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                import re
                content = re.sub(rf'port={old_port}\b', f'port={new_port}', content)
                with open(mysql_conf, 'w', encoding='utf-8') as f:
                    f.write(content)
            except Exception as e:
                print(f"Error updating MySQL port: {e}")
                
    elif name == 'php':
        nginx_conf = os.path.join(BIN_DIR, 'nginx', 'conf', 'nginx.conf')
        if os.path.exists(nginx_conf):
            try:
                with open(nginx_conf, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                import re
                content = re.sub(rf'127\.0\.0\.1:{old_port}\b', f'127.0.0.1:{new_port}', content)
                with open(nginx_conf, 'w', encoding='utf-8') as f:
                    f.write(content)
            except Exception as e:
                print(f"Error updating Nginx PHP port: {e}")
                
        apache_conf = os.path.join(BIN_DIR, 'apache', 'conf', 'httpd.conf')
        if os.path.exists(apache_conf):
            try:
                with open(apache_conf, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                import re
                content = re.sub(rf'127\.0\.0\.1:{old_port}\b', f'127.0.0.1:{new_port}', content)
                with open(apache_conf, 'w', encoding='utf-8') as f:
                    f.write(content)
            except Exception as e:
                print(f"Error updating Apache PHP port: {e}")

CONFIG_FILES = {
    'nginx': os.path.join(BIN_DIR, 'nginx', 'conf', 'nginx.conf'),
    'apache': os.path.join(BIN_DIR, 'apache', 'conf', 'httpd.conf'),
    'mysql': os.path.join(BIN_DIR, 'mysql', 'my.ini'),
    'php': lambda: os.path.join(BIN_DIR, 'php', get_current_php_version(), 'php.ini')
}

# Helper to load pids
def load_pids():
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

# Helper to save pids
def save_pids(pids):
    os.makedirs(os.path.dirname(PID_FILE), exist_ok=True)
    try:
        with open(PID_FILE, 'w') as f:
            json.dump(pids, f, indent=4)
    except Exception as e:
        print("Error saving pids:", e)

# Helper to check if PID is running on Windows
def is_pid_running(pid):
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

# Helper to check if port is open
def is_port_open(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        return s.connect_ex(('127.0.0.1', port)) == 0

# Helper to get active PHP version
def get_current_php_version():
    pids = load_pids()
    if 'php_version' in pids and pids['php_version']:
        return pids['php_version']
    versions = get_php_versions()
    if versions:
        return versions[0]
    return 'php-8.2.31-nts'

# Helper to get PHP version folders
def get_php_versions():
    php_dir = os.path.join(BIN_DIR, 'php')
    if not os.path.exists(php_dir):
        return []
    versions = []
    try:
        for d in os.listdir(php_dir):
            if os.path.isdir(os.path.join(php_dir, d)) and d.startswith('php-'):
                versions.append(d)
    except Exception:
        pass
    return sorted(versions, reverse=True)

# Helper to kill process tree
def kill_process_tree(pid):
    if not pid:
        return
    try:
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(pid)], 
                       creationflags=subprocess.CREATE_NO_WINDOW,
                       stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"Error killing process {pid}: {e}")

# Helper to get process RAM usage on Windows
def get_pid_memory(pid):
    if not pid:
        return 0
    try:
        out = subprocess.check_output(
            ["powershell", "-Command", f"Get-Process -Id {pid} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty WorkingSet"],
            creationflags=subprocess.CREATE_NO_WINDOW,
            text=True
        )
        val = out.strip()
        if val:
            return round(int(val) / (1024 * 1024), 1)  # MB
    except Exception:
        pass
    return 0

def get_service_status(name):
    pids = load_pids()
    pid = pids.get(name)
    
    port = PORTS.get(name)
    port_active = is_port_open(port) if port else False
    
    is_running = port_active or (is_pid_running(pid) if pid else False)
    
    if is_running:
        if not pid and name == 'nginx':
            nginx_pid_file = os.path.join(BIN_DIR, 'nginx', 'logs', 'nginx.pid')
            if os.path.exists(nginx_pid_file):
                try:
                    with open(nginx_pid_file, 'r') as f:
                        pid = int(f.read().strip())
                except:
                    pass
        
        memory_mb = get_pid_memory(pid) if pid else 0
        return 'running', pid, memory_mb
    else:
        return 'stopped', None, 0

def stop_service_internal(name):
    status, pid, _ = get_service_status(name)
    if status == 'stopped':
        return
        
    try:
        if name == 'nginx':
            nginx_exe = os.path.join(BIN_DIR, 'nginx', 'nginx.exe')
            if os.path.exists(nginx_exe):
                subprocess.run(
                    [nginx_exe, '-s', 'stop'],
                    cwd=os.path.join(BIN_DIR, 'nginx'),
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            time.sleep(0.5)
            if pid:
                kill_process_tree(pid)
            subprocess.run(['taskkill', '/F', '/IM', 'nginx.exe'], 
                           creationflags=subprocess.CREATE_NO_WINDOW,
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
            
        elif name == 'mysql':
            mysqladmin_exe = os.path.join(BIN_DIR, 'mysql', 'bin', 'mysqladmin.exe')
            shutdown_success = False
            if os.path.exists(mysqladmin_exe):
                res = subprocess.run(
                    [mysqladmin_exe, '-u', 'root', 'shutdown'],
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                if res.returncode == 0:
                    shutdown_success = True
            
            if not shutdown_success and pid:
                kill_process_tree(pid)
                
        elif name == 'apache':
            if pid:
                kill_process_tree(pid)
            subprocess.run(['taskkill', '/F', '/IM', 'httpd.exe'], 
                           creationflags=subprocess.CREATE_NO_WINDOW,
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
            
        elif name == 'php':
            if pid:
                kill_process_tree(pid)
            subprocess.run(['taskkill', '/F', '/IM', 'php-cgi.exe'], 
                           creationflags=subprocess.CREATE_NO_WINDOW,
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
            
    except Exception as e:
        print(f"Error stopping service {name} internally: {e}")
        
    pids = load_pids()
    pids[name] = None
    save_pids(pids)

def start_php_internal(version=None):
    php_status, _, _ = get_service_status('php')
    if php_status == 'running':
        return True
        
    selected_version = version or get_current_php_version()
    php_exe = os.path.join(BIN_DIR, 'php', selected_version, 'php-cgi.exe')
    if not os.path.exists(php_exe):
        return False
        
    try:
        proc = subprocess.Popen(
            [php_exe, '-b', f'127.0.0.1:{PORTS["php"]}'],
            creationflags=DETACHED_FLAGS,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        success = False
        for _ in range(15):
            time.sleep(0.2)
            if is_port_open(PORTS['php']):
                success = True
                break
                
        if success:
            pids = load_pids()
            pids['php'] = proc.pid
            pids['php_version'] = selected_version
            save_pids(pids)
            return True
        else:
            try:
                subprocess.run(['taskkill', '/F', '/PID', str(proc.pid)], 
                               creationflags=subprocess.CREATE_NO_WINDOW,
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
            except:
                pass
            return False
    except Exception as e:
        print(f"Error starting PHP internally: {e}")
        return False

def start_service_internal(name, php_version=None):
    status, current_pid, _ = get_service_status(name)
    if status == 'running':
        return True, current_pid
        
    pids = load_pids()
    
    # Enforce web server mutual exclusion
    if name == 'nginx':
        stop_service_internal('apache')
        start_php_internal(php_version)
    elif name == 'apache':
        stop_service_internal('nginx')
        start_php_internal(php_version)
        
    success = False
    pid = None
    
    try:
        if name == 'php':
            version = php_version or get_current_php_version()
            php_exe = os.path.join(BIN_DIR, 'php', version, 'php-cgi.exe')
            if not os.path.exists(php_exe):
                return False, f"PHP executable not found for version {version}"
            
            proc = subprocess.Popen(
                [php_exe, '-b', f'127.0.0.1:{PORTS["php"]}'],
                creationflags=DETACHED_FLAGS,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            pid = proc.pid
            pids['php_version'] = version
            
        elif name == 'nginx':
            nginx_exe = os.path.join(BIN_DIR, 'nginx', 'nginx.exe')
            if not os.path.exists(nginx_exe):
                return False, "Nginx executable not found"
                
            proc = subprocess.Popen(
                [nginx_exe],
                cwd=os.path.join(BIN_DIR, 'nginx'),
                creationflags=DETACHED_FLAGS,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            pid = proc.pid
            
        elif name == 'apache':
            httpd_exe = os.path.join(BIN_DIR, 'apache', 'bin', 'httpd.exe')
            if not os.path.exists(httpd_exe):
                return False, "Apache executable not found"
                
            proc = subprocess.Popen(
                [httpd_exe],
                cwd=os.path.join(BIN_DIR, 'apache'),
                creationflags=DETACHED_FLAGS,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            pid = proc.pid
            
        elif name == 'mysql':
            mysqld_exe = os.path.join(BIN_DIR, 'mysql', 'bin', 'mysqld.exe')
            if not os.path.exists(mysqld_exe):
                return False, "MySQL/MariaDB executable not found"
                
            my_ini = os.path.join(BIN_DIR, 'mysql', 'my.ini')
            cmd = [mysqld_exe]
            if os.path.exists(my_ini):
                cmd.append(f'--defaults-file={my_ini}')
                
            proc = subprocess.Popen(
                cmd,
                cwd=os.path.join(BIN_DIR, 'mysql'),
                creationflags=DETACHED_FLAGS,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            pid = proc.pid
        
        # Wait up to 5 seconds for port bind
        for _ in range(25):
            time.sleep(0.2)
            if is_port_open(PORTS[name]):
                success = True
                break
                
        if name == 'nginx' and success:
            nginx_pid_file = os.path.join(BIN_DIR, 'nginx', 'logs', 'nginx.pid')
            if os.path.exists(nginx_pid_file):
                try:
                    with open(nginx_pid_file, 'r') as f:
                        pid = int(f.read().strip())
                except:
                    pass
            
    except Exception as e:
        return False, str(e)
        
    if success and pid:
        pids[name] = pid
        save_pids(pids)
        return True, pid
    else:
        if pid:
            kill_process_tree(pid)
        return False, f"Service {name} failed to start or port {PORTS[name]} not binding."

def load_db_config():
    if os.path.exists(DB_CONFIG_FILE):
        try:
            with open(DB_CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return {"root_password": ""}
    return {"root_password": ""}

def save_db_config(config):
    os.makedirs(os.path.dirname(DB_CONFIG_FILE), exist_ok=True)
    try:
        with open(DB_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
    except Exception:
        pass

def run_mysql_query(sql_query):
    mysql_exe = os.path.join(BIN_DIR, 'mysql', 'bin', 'mysql.exe')
    if not os.path.exists(mysql_exe):
        return False, "mysql.exe executable not found"
        
    config = load_db_config()
    root_password = config.get('root_password', '')
    
    cmd = [mysql_exe, '-h', '127.0.0.1', '-u', 'root']
    if root_password:
        cmd.append(f'-p{root_password}')
    cmd.extend(['-e', sql_query])
    
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return True, result.stdout
        else:
            return False, result.stderr
    except subprocess.TimeoutExpired:
        return False, "Query timed out"
    except Exception as e:
        return False, str(e)

def update_phpmyadmin_password(new_password):
    pma_config = os.path.join(TOOLS_DIR, 'phpmyadmin', 'config.inc.php')
    if not os.path.exists(pma_config):
        return
        
    with open(pma_config, 'r', encoding='utf-8') as f:
        content = f.read()
        
    import re
    pattern = r"(\$cfg\['Servers'\]\[\$i\]\['password'\]\s*=\s*['\"]).*?(['\"];)"
    replacement = rf"\1{new_password}\2"
    
    new_content, count = re.subn(pattern, replacement, content)
    if count > 0:
        with open(pma_config, 'w', encoding='utf-8') as f:
            f.write(new_content)

def get_php_extensions_list():
    php_ini = CONFIG_FILES['php']
    if callable(php_ini):
        php_ini = php_ini()
    if not os.path.exists(php_ini):
        return []
    
    extensions = []
    import re
    ext_pattern = re.compile(r'^\s*(;)?\s*(extension|zend_extension)\s*=\s*([\w\.\-]+)\s*(;.*)?$')
    
    try:
        with open(php_ini, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                match = ext_pattern.match(line)
                if match:
                    is_commented = match.group(1) is not None
                    ext_type = match.group(2)
                    name = match.group(3)
                    extensions.append({
                        'name': name,
                        'type': ext_type,
                        'enabled': not is_commented
                    })
    except Exception as e:
        print(f"Error reading php extensions: {e}")
        
    return extensions

def toggle_php_extension_in_ini(name, enable):
    php_ini = CONFIG_FILES['php']
    if callable(php_ini):
        php_ini = php_ini()
    if not os.path.exists(php_ini):
        return False, "php.ini not found"
        
    import re
    pattern = re.compile(rf'^(\s*)(;)?(\s*)(extension|zend_extension)(\s*=\s*{re.escape(name)})(\s*)(;.*)?$')
    
    modified = False
    new_lines = []
    try:
        with open(php_ini, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                match = pattern.match(line)
                if match:
                    indent = match.group(1) or ""
                    ext_type = match.group(4)
                    eq_name = match.group(5)
                    tail = match.group(7) or ""
                    if tail:
                        tail = " " + tail
                        
                    if enable:
                        new_line = f"{indent}{ext_type}{eq_name}{tail}\n"
                    else:
                        new_line = f"{indent};{ext_type}{eq_name}{tail}\n"
                    
                    new_lines.append(new_line)
                    modified = True
                else:
                    new_lines.append(line)
                    
        if modified:
            with open(php_ini, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
            return True, None
        else:
            return False, f"Extension {name} not found in php.ini"
    except Exception as e:
        return False, str(e)

# Beautified Scrollable Canvas Helper with Wheel Binding
class ScrollableFrame(tk.Frame):
    def __init__(self, parent, bg="#1e293b", *args, **kwargs):
        super().__init__(parent, bg=bg, *args, **kwargs)
        
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        
        # Modern Styled Scrollbar
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollbar.pack(side="right", fill="y")
        
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.bind('<Configure>', lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        
        self.scroll_window = tk.Frame(self.canvas, bg=bg)
        self.canvas.create_window((0, 0), window=self.scroll_window, anchor="nw")
        
        # Fit inner frame width to canvas width automatically
        self.canvas.bind('<Configure>', self._on_canvas_configure)
        
        # Mouse Wheel Event Bindings
        self.canvas.bind("<Enter>", self._bind_mousewheel)
        self.canvas.bind("<Leave>", self._unbind_mousewheel)
        
    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas.find_withtag("all")[0], width=event.width)
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _bind_mousewheel(self, event):
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _unbind_mousewheel(self, event):
        self.canvas.unbind_all("<MouseWheel>")

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

# Main Premium Application
class WinPHPApp(tk.Tk):
    def __init__(self):
        super().__init__()
        
        self.title("WinPHP Control Center")
        
        # Calculate DPI scaling factor
        try:
            self.dpi_factor = self.winfo_fpixels('1i') / 96.0
        except Exception:
            self.dpi_factor = 1.0
            
        # Scale default and minimum window dimensions by the DPI factor
        width = int(1000 * self.dpi_factor)
        height = int(720 * self.dpi_factor)
        self.geometry(f"{width}x{height}")
        
        min_w = int(950 * self.dpi_factor)
        min_h = int(640 * self.dpi_factor)
        self.minsize(min_w, min_h)
        self.resizable(True, True)
        self.configure(bg="#0f172a") # Slate 900
        
        # Set Window Icon
        icon_path = os.path.join(BASE_DIR, 'icon.ico')
        icon_loaded = False
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
                icon_loaded = True
            except Exception as e:
                try:
                    img = Image.open(icon_path)
                    self.icon_photo_img = ImageTk.PhotoImage(img)
                    self.iconphoto(True, self.icon_photo_img)
                    icon_loaded = True
                except Exception as e2:
                    print("Error loading icon via PIL:", e2)
        
        # Set custom Combobox Styling
        self.configure_combobox_style()
        
        self.active_php_version = get_current_php_version()
        self.php_versions = get_php_versions()
        self.active_web_server = "nginx"
        self.detect_active_web_server()
        
        # Main Layout
        self.create_layout()
        
        # Stats & status loops
        self.stats_thread_active = True
        self.stats_thread = threading.Thread(target=self.system_stats_loop, daemon=True)
        self.stats_thread.start()
        
        self.status_thread_active = True
        self.status_thread = threading.Thread(target=self.services_status_loop, daemon=True)
        self.status_thread.start()
        
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # System Tray initialization
        self.tray_icon = None
        self.setup_tray()
        self.bind("<Unmap>", self.on_minimize)
        
    def configure_combobox_style(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        # Combobox customization to match dark mode theme
        style.configure('TCombobox',
                        fieldbackground='#0f172a',
                        background='#1e293b',
                        foreground='#f8fafc',
                        bordercolor='#334155',
                        arrowcolor='#3b82f6')
        
        style.map('TCombobox',
                  fieldbackground=[('readonly', '#0f172a')],
                  foreground=[('readonly', '#f8fafc')])
                  
        # Scrollbar customization
        style.configure('Vertical.TScrollbar',
                        background='#1e293b',
                        troughcolor='#0f172a',
                        bordercolor='#334155',
                        arrowcolor='#3b82f6')

    def detect_active_web_server(self):
        a_status, _, _ = get_service_status('apache')
        n_status, _, _ = get_service_status('nginx')
        if a_status == 'running':
            self.active_web_server = 'apache'
        elif n_status == 'running':
            self.active_web_server = 'nginx'

    def create_layout(self):
        # Left Sidebar (Slate 800)
        sidebar_width = int(225 * self.dpi_factor)
        self.sidebar = tk.Frame(self, bg="#1e293b", width=sidebar_width)
        self.sidebar.pack(fill="y", side="left")
        self.sidebar.pack_propagate(False)
        
        # Brand Logo in Sidebar
        brand_frame = tk.Frame(self.sidebar, bg="#1e293b")
        brand_frame.pack(fill="x", pady=(int(15 * self.dpi_factor), int(10 * self.dpi_factor)), padx=int(20 * self.dpi_factor))
        
        logo_path = os.path.join(BASE_DIR, 'logo.png')
        logo_loaded = False
        if os.path.exists(logo_path):
            try:
                # Load and scale logo using PIL for high-quality resizing
                img = Image.open(logo_path)
                target_w = int(170 * self.dpi_factor)
                orig_w, orig_h = img.size
                aspect = orig_h / orig_w
                target_h = int(target_w * aspect)
                
                img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
                self.logo_img = ImageTk.PhotoImage(img)
                
                logo_lbl = tk.Label(brand_frame, image=self.logo_img, bg="#1e293b")
                logo_lbl.pack(anchor="w", pady=(0, 10))
                logo_loaded = True
            except Exception as e:
                print("Error loading sidebar logo image:", e)
                
        if not logo_loaded:
            tk.Label(brand_frame, text="⚡ WinPHP", bg="#1e293b", fg="#3b82f6", font=("Segoe UI", 18, "bold")).pack(anchor="w")
            
        tk.Label(brand_frame, text="v1.2 Premium Console", bg="#1e293b", fg="#64748b", font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(2, 0))
        
        # Sidebar Menu Buttons
        self.menu_buttons = {}
        menu_items = [
            ("Dashboard", "dashboard"),
            ("Config Editor", "config"),
            ("Logs Viewer", "logs"),
            ("PHP Extensions", "extensions"),
            ("DB Manager", "db"),
            ("Projects", "projects"),
            ("Settings", "settings")
        ]
        
        for label, tab_id in menu_items:
            # Menu button frame for left active indicator stripe
            btn_frame = tk.Frame(self.sidebar, bg="#1e293b")
            btn_frame.pack(fill="x", pady=1)
            
            stripe = tk.Frame(btn_frame, bg="#1e293b", width=4)
            stripe.pack(side="left", fill="y")
            
            btn = tk.Button(
                btn_frame, 
                text=label, 
                bg="#1e293b", 
                fg="#94a3b8", 
                activebackground="#1e293b",
                activeforeground="#3b82f6",
                relief="flat", 
                font=("Segoe UI", 10, "bold"),
                anchor="w",
                padx=15,
                pady=6,
                borderwidth=0,
                command=lambda tid=tab_id: self.show_tab(tid)
            )
            btn.pack(fill="x", side="right")
            self.menu_buttons[tab_id] = (btn, stripe, btn_frame)
            
            # Hover Bindings
            btn.bind("<Enter>", lambda e, bid=tab_id: self.on_menu_hover(bid, True))
            btn.bind("<Leave>", lambda e, bid=tab_id: self.on_menu_hover(bid, False))
            
        # Add system stats label at the bottom of sidebar
        stats_frame = tk.Frame(self.sidebar, bg="#1e293b")
        stats_frame.pack(side="bottom", fill="x", padx=20, pady=(10, 15))
        
        tk.Label(stats_frame, text="SYSTEM METRICS", bg="#1e293b", fg="#64748b", font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 8))
        
        self.create_flat_progressbar(stats_frame, "CPU", "cpu_fill", "cpu_lbl")
        self.create_flat_progressbar(stats_frame, "RAM", "ram_fill", "ram_lbl")
        self.create_flat_progressbar(stats_frame, "DISK", "disk_fill", "disk_lbl")
        
        # Main Work Area
        self.work_area = tk.Frame(self, bg="#0f172a")
        self.work_area.pack(fill="both", expand=True, side="right", padx=25, pady=25)
        
        # Create tabs
        self.tabs = {}
        self.create_dashboard_tab()
        self.create_config_tab()
        self.create_logs_tab()
        self.create_extensions_tab()
        self.create_db_tab()
        self.create_projects_tab()
        self.create_settings_tab()
        
        # Show default tab
        self.show_tab("dashboard")
        
    def create_flat_progressbar(self, parent, name, fill_attr, lbl_attr):
        frame = tk.Frame(parent, bg="#1e293b", pady=2)
        frame.pack(fill="x")
        
        lbl_frame = tk.Frame(frame, bg="#1e293b")
        lbl_frame.pack(fill="x")
        
        tk.Label(lbl_frame, text=name, bg="#1e293b", fg="#94a3b8", font=("Segoe UI", 9, "bold")).pack(side="left")
        val_lbl = tk.Label(lbl_frame, text="0%", bg="#1e293b", fg="#64748b", font=("Segoe UI", 9, "bold"))
        val_lbl.pack(side="right")
        setattr(self, lbl_attr, val_lbl)
        
        # Progress Bar base track
        track_width = int(170 * self.dpi_factor)
        track = tk.Frame(frame, bg="#334155", height=6, width=track_width)
        track.pack(anchor="w", pady=(3, 5))
        track.pack_propagate(False)
        
        bar_color = {"CPU": "#3b82f6", "RAM": "#8b5cf6", "DISK": "#f59e0b"}.get(name, "#3b82f6")
        fill_bar = tk.Frame(track, bg=bar_color, width=0)
        fill_bar.pack(side="left", fill="y")
        setattr(self, fill_attr, fill_bar)

    def on_menu_hover(self, tab_id, is_enter):
        btn, stripe, _ = self.menu_buttons[tab_id]
        if tab_id == self.current_tab:
            return
        if is_enter:
            btn.config(fg="#f8fafc")
        else:
            btn.config(fg="#94a3b8")

    def show_tab(self, tab_id):
        self.current_tab = tab_id
        
        # Hide all tabs
        for tab in self.tabs.values():
            tab.pack_forget()
            
        # Reset menu styling
        for tid, (btn, stripe, frame) in self.menu_buttons.items():
            if tid == tab_id:
                btn.config(fg="#3b82f6", bg="#0f172a")
                stripe.config(bg="#3b82f6")
                frame.config(bg="#0f172a")
            else:
                btn.config(fg="#94a3b8", bg="#1e293b")
                stripe.config(bg="#1e293b")
                frame.config(bg="#1e293b")
                
        # Show selected tab
        self.tabs[tab_id].pack(fill="both", expand=True)
        
        # Tab specific loads
        if tab_id == "extensions":
            self.load_extensions_list()
        elif tab_id == "projects":
            self.load_projects_list()

    # ==================== DASHBOARD TAB ====================
    def create_dashboard_tab(self):
        tab = tk.Frame(self.work_area, bg="#0f172a")
        self.tabs["dashboard"] = tab
        
        # Header Row
        hdr_frame = tk.Frame(tab, bg="#0f172a")
        hdr_frame.pack(fill="x", pady=(0, int(12 * self.dpi_factor)))
        
        tk.Label(hdr_frame, text="Dashboard", bg="#0f172a", fg="#f8fafc", font=("Segoe UI", 20, "bold")).pack(side="left")
        
        # Web server segmented switch
        ws_frame = tk.Frame(hdr_frame, bg="#1e293b", padx=3, pady=3, highlightbackground="#334155", highlightthickness=1)
        ws_frame.pack(side="right")
        
        self.btn_nginx_toggle = tk.Button(
            ws_frame, text="Nginx Server", bg="#3b82f6", fg="#ffffff", font=("Segoe UI", 9, "bold"),
            relief="flat", padx=15, pady=5, borderwidth=0, cursor="hand2", command=lambda: self.switch_active_server('nginx')
        )
        self.btn_nginx_toggle.pack(side="left")
        
        self.btn_apache_toggle = tk.Button(
            ws_frame, text="Apache Server", bg="#1e293b", fg="#94a3b8", font=("Segoe UI", 9, "bold"),
            relief="flat", padx=15, pady=5, borderwidth=0, cursor="hand2", command=lambda: self.switch_active_server('apache')
        )
        self.btn_apache_toggle.pack(side="left")
        
        # Quick Actions Row
        btn_grp = tk.Frame(tab, bg="#0f172a")
        btn_grp.pack(fill="x", pady=(0, int(12 * self.dpi_factor)))
        
        tk.Button(
            btn_grp, text="▶  Start All Services", bg="#10b981", fg="#ffffff", font=("Segoe UI", 10, "bold"),
            relief="flat", padx=18, pady=8, borderwidth=0, cursor="hand2", command=self.start_all_services
        ).pack(side="left", padx=(0, 12))
                  
        tk.Button(
            btn_grp, text="■  Stop All Services", bg="#ef4444", fg="#ffffff", font=("Segoe UI", 10, "bold"),
            relief="flat", padx=18, pady=8, borderwidth=0, cursor="hand2", command=self.stop_all_services
        ).pack(side="left")
        
        # Status Message Info Bar
        self.status_bar = tk.Label(btn_grp, text="Status: Server operational", bg="#0f172a", fg="#64748b", font=("Segoe UI", 9, "bold"))
        self.status_bar.pack(side="right", pady=8)

        # Grid of Cards
        cards_frame = tk.Frame(tab, bg="#0f172a")
        cards_frame.pack(fill="both", expand=True)
        cards_frame.columnconfigure(0, weight=1, uniform="group1")
        cards_frame.columnconfigure(1, weight=1, uniform="group1")
        cards_frame.rowconfigure(0, weight=1, uniform="group2")
        cards_frame.rowconfigure(1, weight=1, uniform="group2")
        
        # Cards Initialization
        self.service_cards = {}
        self.create_service_card(cards_frame, "nginx", "Nginx Server", f"Web Server · Port {PORTS['nginx']}", 0, 0)
        self.create_service_card(cards_frame, "apache", "Apache Server", f"Web Server · Port {PORTS['apache']}", 0, 1)
        self.create_service_card(cards_frame, "mysql", "MariaDB Server", f"Database Engine · Port {PORTS['mysql']}", 1, 0)
        self.create_service_card(cards_frame, "php", "PHP FastCGI", f"Processor · Port {PORTS['php']}", 1, 1, has_select=True)
        
        self.update_webserver_ui()

    def create_service_card(self, parent, svc_id, title, desc, row, col, has_select=False):
        card = tk.Frame(parent, bg="#1e293b", highlightbackground="#334155", highlightthickness=1)
        card.grid(row=row, column=col, padx=int(8 * self.dpi_factor), pady=int(8 * self.dpi_factor), sticky="nsew")
        
        # Colored Left Edge Stripe
        stripe_color = {"nginx": "#10b981", "apache": "#f59e0b", "mysql": "#3b82f6", "php": "#8b5cf6"}.get(svc_id, "#64748b")
        stripe = tk.Frame(card, bg=stripe_color, width=4)
        stripe.pack(side="left", fill="y")
        
        content = tk.Frame(card, bg="#1e293b", padx=int(15 * self.dpi_factor), pady=int(10 * self.dpi_factor))
        content.pack(fill="both", expand=True, side="right")
        
        # Title and Description Labels
        tk.Label(content, text=title, bg="#1e293b", fg="#f8fafc", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        desc_lbl = tk.Label(content, text=desc, bg="#1e293b", fg="#64748b", font=("Segoe UI", 9))
        desc_lbl.pack(anchor="w", pady=(2, int(6 * self.dpi_factor)))
        
        # Status Bar Row
        status_frame = tk.Frame(content, bg="#1e293b")
        status_frame.pack(fill="x", pady=(0, int(8 * self.dpi_factor)))
        
        status_dot = tk.Canvas(status_frame, width=12, height=12, bg="#1e293b", highlightthickness=0)
        status_dot.pack(side="left", padx=(0, 8))
        status_dot.create_oval(1, 1, 11, 11, fill="#ef4444", outline="#ef4444")
        
        status_lbl = tk.Label(status_frame, text="Stopped", bg="#1e293b", fg="#ef4444", font=("Segoe UI", 9, "bold"))
        status_lbl.pack(side="left")
        
        mem_lbl = tk.Label(status_frame, text="", bg="#1e293b", fg="#94a3b8", font=("Segoe UI", 9, "bold"))
        mem_lbl.pack(side="right")
        
        # Controls Footer Row
        ctrl_frame = tk.Frame(content, bg="#1e293b")
        ctrl_frame.pack(fill="x", side="bottom")
        
        action_btn = tk.Button(
            ctrl_frame, text="Start", bg="#10b981", fg="#ffffff", font=("Segoe UI", 9, "bold"),
            relief="flat", padx=15, pady=5, borderwidth=0, cursor="hand2", command=lambda: self.toggle_service(svc_id)
        )
        action_btn.pack(side="left")
        
        if has_select:
            php_sel = ttk.Combobox(ctrl_frame, values=self.php_versions, width=15, state="readonly")
            if self.active_php_version in self.php_versions:
                php_sel.set(self.active_php_version)
            else:
                php_sel.set(self.php_versions[0] if self.php_versions else "")
            php_sel.pack(side="right", pady=2)
            php_sel.bind("<<ComboboxSelected>>", self.change_php_version)
            self.php_combobox = php_sel
            
        # Store Reference Dictionary
        self.service_cards[svc_id] = {
            'canvas': status_dot,
            'label': status_lbl,
            'mem': mem_lbl,
            'btn': action_btn,
            'desc_lbl': desc_lbl
        }

    def update_webserver_ui(self):
        if self.active_web_server == "nginx":
            self.btn_nginx_toggle.config(bg="#3b82f6", fg="#ffffff")
            self.btn_apache_toggle.config(bg="#1e293b", fg="#94a3b8")
        else:
            self.btn_nginx_toggle.config(bg="#1e293b", fg="#94a3b8")
            self.btn_apache_toggle.config(bg="#3b82f6", fg="#ffffff")

    def switch_active_server(self, server_type):
        if self.active_web_server == server_type:
            return
        
        self.active_web_server = server_type
        self.update_webserver_ui()
        
        def transition():
            self.set_status_bar(f"Switching web server to {server_type.upper()}...")
            if server_type == "nginx":
                stop_service_internal("apache")
                start_service_internal("nginx", self.active_php_version)
            else:
                stop_service_internal("nginx")
                start_service_internal("apache", self.active_php_version)
            self.set_status_bar("Web server switched.")
            
        threading.Thread(target=transition, daemon=True).start()

    def toggle_service(self, svc_id):
        status, _, _ = get_service_status(svc_id)
        
        def run_toggle():
            self.set_status_bar(f"Toggling {svc_id.upper()}...")
            if status == "running":
                stop_service_internal(svc_id)
                self.set_status_bar(f"{svc_id.upper()} stopped.")
            else:
                ok, err = start_service_internal(svc_id, self.active_php_version)
                if ok:
                    self.set_status_bar(f"{svc_id.upper()} started.")
                else:
                    messagebox.showerror("Service Error", f"Failed to start {svc_id}: {err}")
                    self.set_status_bar(f"Failed to start {svc_id.upper()}.")
                    
        threading.Thread(target=run_toggle, daemon=True).start()

    def change_php_version(self, event):
        new_version = self.php_combobox.get()
        if new_version == self.active_php_version:
            return
            
        self.active_php_version = new_version
        
        def perform_version_change():
            self.set_status_bar(f"Switching PHP version to {new_version}...")
            pids = load_pids()
            pids['php_version'] = new_version
            save_pids(pids)
            
            php_status, _, _ = get_service_status('php')
            if php_status == 'running':
                stop_service_internal('php')
                start_php_internal(new_version)
                
            self.set_status_bar(f"PHP version switched to {new_version}.")
            
        threading.Thread(target=perform_version_change, daemon=True).start()

    def start_all_services(self):
        def action():
            self.set_status_bar("Starting all configured services...")
            start_service_internal("mysql")
            start_service_internal(self.active_web_server, self.active_php_version)
            self.set_status_bar("All services running.")
            
        threading.Thread(target=action, daemon=True).start()

    def stop_all_services(self):
        def action():
            self.set_status_bar("Stopping all configured services...")
            for s in ['nginx', 'apache', 'mysql', 'php']:
                stop_service_internal(s)
            self.set_status_bar("All services stopped.")
            
        threading.Thread(target=action, daemon=True).start()

    def set_status_bar(self, msg):
        try:
            self.status_bar.config(text=f"Status: {msg}")
        except:
            pass

    # ==================== CONFIG EDITOR TAB ====================
    def create_config_tab(self):
        tab = tk.Frame(self.work_area, bg="#0f172a")
        self.tabs["config"] = tab
        
        # Header Row
        hdr_frame = tk.Frame(tab, bg="#0f172a")
        hdr_frame.pack(fill="x", pady=(0, 15))
        
        tk.Label(hdr_frame, text="Config Editor", bg="#0f172a", fg="#f8fafc", font=("Segoe UI", 18, "bold")).pack(side="left")
        
        # Selector Combobox
        self.config_svc_var = tk.StringVar(value="php")
        choices = ["php", "nginx", "apache", "mysql"]
        
        opt_menu = ttk.Combobox(hdr_frame, values=choices, textvar=self.config_svc_var, state="readonly", width=12)
        opt_menu.pack(side="right")
        opt_menu.bind("<<ComboboxSelected>>", lambda e: self.load_config_content())
        
        # Scrollable Text Editor with rounded boundary representation
        self.config_editor = scrolledtext.ScrolledText(
            tab, bg="#1e293b", fg="#f8fafc", insertbackground="#ffffff", 
            font=("Consolas", 10), wrap="none", relief="flat", highlightbackground="#334155", highlightthickness=1
        )
        self.config_editor.pack(fill="both", expand=True, pady=(0, 15))
        
        # Save Button
        save_btn = tk.Button(
            tab, text="✔  Save Configuration", bg="#3b82f6", fg="#ffffff", font=("Segoe UI", 10, "bold"),
            relief="flat", padx=20, pady=8, borderwidth=0, cursor="hand2", command=self.save_config_content
        )
        save_btn.pack(anchor="e")
        
        self.load_config_content()

    def load_config_content(self):
        svc = self.config_svc_var.get()
        path = CONFIG_FILES[svc]
        if callable(path):
            path = path()
            
        self.config_editor.delete("1.0", tk.END)
        
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                self.config_editor.insert(tk.END, content)
                self.set_status_bar(f"Config loaded: {os.path.basename(path)}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not read config file: {e}")
        else:
            self.config_editor.insert(tk.END, f"# Config file not found at: {path}")

    def save_config_content(self):
        svc = self.config_svc_var.get()
        path = CONFIG_FILES[svc]
        if callable(path):
            path = path()
            
        content = self.config_editor.get("1.0", tk.END)
        
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            messagebox.showinfo("Success", f"Config file saved successfully.")
            self.set_status_bar(f"Config updated: {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not write config file: {e}")

    # ==================== LOGS VIEWER TAB ====================
    def create_logs_tab(self):
        tab = tk.Frame(self.work_area, bg="#0f172a")
        self.tabs["logs"] = tab
        
        # Header Row
        hdr_frame = tk.Frame(tab, bg="#0f172a")
        hdr_frame.pack(fill="x", pady=(0, 15))
        
        tk.Label(hdr_frame, text="Logs Viewer", bg="#0f172a", fg="#f8fafc", font=("Segoe UI", 18, "bold")).pack(side="left")
        
        ctrls = tk.Frame(hdr_frame, bg="#0f172a")
        ctrls.pack(side="right")
        
        self.log_svc_var = tk.StringVar(value="nginx")
        choices = ["nginx", "apache", "mysql", "php"]
        
        opt_menu = ttk.Combobox(ctrls, values=choices, textvar=self.log_svc_var, state="readonly", width=12)
        opt_menu.pack(side="left", padx=(0, 12))
        opt_menu.bind("<<ComboboxSelected>>", lambda e: self.load_log_content())
        
        tk.Button(
            ctrls, text="🔄  Refresh Logs", bg="#1e293b", fg="#f8fafc", font=("Segoe UI", 9, "bold"),
            relief="flat", padx=12, pady=4, borderwidth=0, cursor="hand2", command=self.load_log_content
        ).pack(side="left")
        
        # Log Text Box
        self.log_viewer = scrolledtext.ScrolledText(
            tab, bg="#1e293b", fg="#94a3b8", font=("Consolas", 9), wrap="none", relief="flat", highlightbackground="#334155", highlightthickness=1
        )
        self.log_viewer.pack(fill="both", expand=True)
        
        self.load_log_content()

    def load_log_content(self):
        svc = self.log_svc_var.get()
        
        LOG_PATHS = {
            'nginx': [
                os.path.join(BIN_DIR, 'nginx', 'logs', 'error.log'),
                os.path.join(BIN_DIR, 'nginx', 'logs', 'access.log')
            ],
            'apache': [
                os.path.join(BIN_DIR, 'apache', 'logs', 'error.log')
            ],
            'mysql': [
                lambda: next((os.path.join(BIN_DIR, 'mysql', 'data', f) 
                              for f in os.listdir(os.path.join(BIN_DIR, 'mysql', 'data')) 
                              if f.endswith('.err')), None) if os.path.exists(os.path.join(BIN_DIR, 'mysql', 'data')) else None
            ],
            'php': [
                os.path.join(BIN_DIR, 'php', get_current_php_version(), 'php_errors.log'),
                os.path.join(BASE_DIR, 'php_errors.log')
            ]
        }
        
        paths = LOG_PATHS[svc]
        if isinstance(paths, list) and callable(paths[0]):
            paths = [paths[0]()]
        elif callable(paths):
            paths = [paths()]
            
        logs_content = ""
        found_path = None
        
        for path in paths:
            if path and os.path.exists(path):
                found_path = path
                try:
                    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                        logs_content = "".join(lines[-100:])
                    break
                except Exception as e:
                    logs_content = f"Error reading log: {e}"
                    
        self.log_viewer.config(state="normal")
        self.log_viewer.delete("1.0", tk.END)
        
        if found_path:
            self.log_viewer.insert(tk.END, logs_content)
            self.set_status_bar(f"Loaded logs: {os.path.basename(found_path)}")
        else:
            self.log_viewer.insert(tk.END, "No log records found for this service.")
            self.set_status_bar("No logs found.")
            
        self.log_viewer.config(state="disabled")

    # ==================== EXTENSIONS TAB ====================
    def create_extensions_tab(self):
        tab = tk.Frame(self.work_area, bg="#0f172a")
        self.tabs["extensions"] = tab
        
        # Header text
        tk.Label(tab, text="PHP Extensions Manager", bg="#0f172a", fg="#f8fafc", font=("Segoe UI", 18, "bold")).pack(anchor="w", pady=(0, 5))
        tk.Label(tab, text="Toggling extensions modifies your active php.ini. Services will automatically reload.", bg="#0f172a", fg="#64748b", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 20))
        
        # Scrollable Frame with Wheel Binding
        self.ext_scroll = ScrollableFrame(tab, bg="#1e293b")
        self.ext_scroll.pack(fill="both", expand=True)
        
        self.ext_checkbox_vars = {}

    def load_extensions_list(self):
        inner_frame = self.ext_scroll.scroll_window
        
        # Clear previous elements
        for widget in inner_frame.winfo_children():
            widget.destroy()
            
        self.ext_checkbox_vars.clear()
        
        extensions = get_php_extensions_list()
        
        if not extensions:
            tk.Label(inner_frame, text="No extensions parsed from php.ini", bg="#1e293b", fg="#64748b", font=("Segoe UI", 10, "bold")).pack(pady=40)
            return
            
        # Multi-column grid representation
        col1 = tk.Frame(inner_frame, bg="#1e293b")
        col1.pack(side="left", fill="both", expand=True, padx=20, pady=10)
        col2 = tk.Frame(inner_frame, bg="#1e293b")
        col2.pack(side="left", fill="both", expand=True, padx=20, pady=10)
        
        for i, ext in enumerate(extensions):
            target_col = col1 if i % 2 == 0 else col2
            
            var = tk.BooleanVar(value=ext['enabled'])
            name = ext['name']
            
            # Stylized Checkbutton element matching dark mode UI
            cb = tk.Checkbutton(
                target_col, text=f"  {name} ({ext['type']})", variable=var,
                bg="#1e293b", fg="#f8fafc", selectcolor="#0f172a",
                activebackground="#1e293b", activeforeground="#f8fafc",
                font=("Segoe UI", 10), anchor="w", cursor="hand2",
                command=lambda n=name, v=var: self.toggle_extension(n, v)
            )
            cb.pack(fill="x", pady=5)
            self.ext_checkbox_vars[name] = var

    def toggle_extension(self, name, var):
        enable = var.get()
        
        def run_toggle():
            self.set_status_bar(f"Toggling extension {name}...")
            ok, err = toggle_php_extension_in_ini(name, enable)
            if ok:
                php_status, _, _ = get_service_status('php')
                if php_status == 'running':
                    stop_service_internal('php')
                    start_php_internal(self.active_php_version)
                self.set_status_bar(f"Extension {name} updated.")
            else:
                messagebox.showerror("Error", f"Failed to modify php.ini: {err}")
                self.set_status_bar("Failed to update extension.")
                
        threading.Thread(target=run_toggle, daemon=True).start()

    # ==================== DB MANAGER TAB ====================
    def create_db_tab(self):
        tab = tk.Frame(self.work_area, bg="#0f172a")
        self.tabs["db"] = tab
        
        # Header Row
        hdr = tk.Frame(tab, bg="#0f172a")
        hdr.pack(fill="x", pady=(0, 20))
        
        tk.Label(hdr, text="Database Manager", bg="#0f172a", fg="#f8fafc", font=("Segoe UI", 18, "bold")).pack(side="left")
        
        tk.Button(
            hdr, text="🌐  Open phpMyAdmin", bg="#10b981", fg="#ffffff", font=("Segoe UI", 9, "bold"),
            relief="flat", padx=15, pady=5, borderwidth=0, cursor="hand2", command=self.open_phpmyadmin
        ).pack(side="right")
        
        panel_container = tk.Frame(tab, bg="#0f172a")
        panel_container.pack(fill="both", expand=True)
        panel_container.columnconfigure(0, weight=1, uniform="db_panel")
        panel_container.columnconfigure(1, weight=1, uniform="db_panel")
        
        # Left Panel (Password Updates)
        p1 = tk.Frame(panel_container, bg="#1e293b", highlightbackground="#334155", highlightthickness=1, padx=25, pady=25)
        p1.grid(row=0, column=0, padx=(0, 12), sticky="nsew")
        
        tk.Label(p1, text="Set root Password", bg="#1e293b", fg="#f8fafc", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 8))
        tk.Label(p1, text="Direct password manipulation for the DB administrator account.", 
                 bg="#1e293b", fg="#64748b", font=("Segoe UI", 9), justify="left", wrap=250).pack(anchor="w", pady=(0, 20))
                 
        tk.Label(p1, text="New Password", bg="#1e293b", fg="#94a3b8", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 5))
        self.db_root_pass_entry = tk.Entry(
            p1, bg="#0f172a", fg="#f8fafc", show="*", insertbackground="#ffffff", 
            relief="flat", highlightbackground="#334155", highlightthickness=1, font=("Segoe UI", 10)
        )
        self.db_root_pass_entry.pack(fill="x", pady=(0, 25), ipady=5)
        
        tk.Button(
            p1, text="🔑  Update Root Password", bg="#3b82f6", fg="#ffffff", font=("Segoe UI", 10, "bold"),
            relief="flat", padx=15, pady=8, borderwidth=0, cursor="hand2", command=self.update_root_db_pass
        ).pack(anchor="w")
        
        # Right Panel (User Generation)
        p2 = tk.Frame(panel_container, bg="#1e293b", highlightbackground="#334155", highlightthickness=1, padx=25, pady=25)
        p2.grid(row=0, column=1, padx=(12, 0), sticky="nsew")
        
        tk.Label(p2, text="Create DB & User", bg="#1e293b", fg="#f8fafc", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 8))
        tk.Label(p2, text="Generates a user role and schema databases in a single command.", 
                 bg="#1e293b", fg="#64748b", font=("Segoe UI", 9), justify="left", wrap=250).pack(anchor="w", pady=(0, 20))
                 
        tk.Label(p2, text="Username", bg="#1e293b", fg="#94a3b8", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 4))
        self.db_new_user_entry = tk.Entry(
            p2, bg="#0f172a", fg="#f8fafc", insertbackground="#ffffff", 
            relief="flat", highlightbackground="#334155", highlightthickness=1, font=("Segoe UI", 10)
        )
        self.db_new_user_entry.pack(fill="x", pady=(0, 12), ipady=5)
        
        tk.Label(p2, text="Password", bg="#1e293b", fg="#94a3b8", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 4))
        self.db_new_pass_entry = tk.Entry(
            p2, bg="#0f172a", fg="#f8fafc", insertbackground="#ffffff", 
            relief="flat", highlightbackground="#334155", highlightthickness=1, font=("Segoe UI", 10)
        )
        self.db_new_pass_entry.pack(fill="x", pady=(0, 12), ipady=5)
        
        tk.Label(p2, text="Database Name (optional)", bg="#1e293b", fg="#94a3b8", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 4))
        self.db_new_name_entry = tk.Entry(
            p2, bg="#0f172a", fg="#f8fafc", insertbackground="#ffffff", 
            relief="flat", highlightbackground="#334155", highlightthickness=1, font=("Segoe UI", 10)
        )
        self.db_new_name_entry.pack(fill="x", pady=(0, 25), ipady=5)
        
        tk.Button(
            p2, text="➕  Create Schema & User", bg="#10b981", fg="#ffffff", font=("Segoe UI", 10, "bold"),
            relief="flat", padx=15, pady=8, borderwidth=0, cursor="hand2", command=self.create_db_and_user
        ).pack(anchor="w")

    def open_phpmyadmin(self):
        port = PORTS[self.active_web_server]
        url = f"http://localhost:{port}/phpmyadmin" if port != 80 else "http://localhost/phpmyadmin"
        webbrowser.open(url)

    def update_root_db_pass(self):
        new_pass = self.db_root_pass_entry.get()
        if not new_pass:
            messagebox.showwarning("Warning", "Password cannot be empty!")
            return
            
        status, _, _ = get_service_status('mysql')
        if status != 'running':
            messagebox.showerror("Error", "MariaDB service must be active to modify credentials.")
            return
            
        def perform():
            self.set_status_bar("Updating MariaDB root credentials...")
            queries = [
                f"ALTER USER 'root'@'localhost' IDENTIFIED BY '{new_pass}';",
                f"ALTER USER 'root'@'127.0.0.1' IDENTIFIED BY '{new_pass}';",
                "FLUSH PRIVILEGES;"
            ]
            
            success = True
            error_msg = ""
            for q in queries:
                ok, out = run_mysql_query(q)
                if not ok:
                    success = False
                    error_msg = out
                    break
                    
            if success:
                config = load_db_config()
                config['root_password'] = new_pass
                save_db_config(config)
                
                try:
                    update_phpmyadmin_password(new_pass)
                except Exception as e:
                    print(f"Error updating config: {e}")
                    
                messagebox.showinfo("Success", "MariaDB root credentials updated successfully.")
                self.set_status_bar("Root password changed.")
                self.db_root_pass_entry.delete(0, tk.END)
            else:
                messagebox.showerror("SQL Error", f"Query failed: {error_msg}")
                self.set_status_bar("Failed root pass alteration.")
                
        threading.Thread(target=perform, daemon=True).start()

    def create_db_and_user(self):
        user = self.db_new_user_entry.get().strip()
        pwd = self.db_new_pass_entry.get().strip()
        dbname = self.db_new_name_entry.get().strip()
        
        if not user or not pwd:
            messagebox.showwarning("Warning", "Username and Password fields are mandatory.")
            return
            
        status, _, _ = get_service_status('mysql')
        if status != 'running':
            messagebox.showerror("Error", "MariaDB service must be active to create schemas.")
            return
            
        def perform():
            self.set_status_bar("Generating SQL privileges...")
            queries = []
            if dbname:
                queries.append(f"CREATE DATABASE IF NOT EXISTS `{dbname}`;")
            queries.append(f"CREATE USER IF NOT EXISTS '{user}'@'localhost' IDENTIFIED BY '{pwd}';")
            queries.append(f"CREATE USER IF NOT EXISTS '{user}'@'127.0.0.1' IDENTIFIED BY '{pwd}';")
            if dbname:
                queries.append(f"GRANT ALL PRIVILEGES ON `{dbname}`.* TO '{user}'@'localhost';")
                queries.append(f"GRANT ALL PRIVILEGES ON `{dbname}`.* TO '{user}'@'127.0.0.1';")
            else:
                queries.append(f"GRANT ALL PRIVILEGES ON *.* TO '{user}'@'localhost';")
                queries.append(f"GRANT ALL PRIVILEGES ON *.* TO '{user}'@'127.0.0.1';")
            queries.append("FLUSH PRIVILEGES;")
            
            success = True
            error_msg = ""
            for q in queries:
                ok, out = run_mysql_query(q)
                if not ok:
                    success = False
                    error_msg = out
                    break
                    
            if success:
                messagebox.showinfo("Success", f"Database + User '{user}' initialized.")
                self.set_status_bar(f"Created Database user '{user}'.")
                self.db_new_user_entry.delete(0, tk.END)
                self.db_new_pass_entry.delete(0, tk.END)
                self.db_new_name_entry.delete(0, tk.END)
            else:
                messagebox.showerror("SQL Execution Error", f"Query failed: {error_msg}")
                self.set_status_bar("Failed schema generation.")
                
        threading.Thread(target=perform, daemon=True).start()

    # ==================== PROJECTS TAB ====================
    def create_projects_tab(self):
        tab = tk.Frame(self.work_area, bg="#0f172a")
        self.tabs["projects"] = tab
        
        # Header Row
        hdr = tk.Frame(tab, bg="#0f172a")
        hdr.pack(fill="x", pady=(0, 15))
        
        tk.Label(hdr, text="Local Projects", bg="#0f172a", fg="#f8fafc", font=("Segoe UI", 18, "bold")).pack(side="left")
        
        tk.Button(
            hdr, text="📁  Open www/ directory", bg="#1e293b", fg="#f8fafc", font=("Segoe UI", 9, "bold"),
            relief="flat", padx=12, pady=5, borderwidth=0, cursor="hand2", command=lambda: os.startfile(WWW_DIR)
        ).pack(side="right")
        
        # Search Filter bar
        search_frame = tk.Frame(tab, bg="#1e293b", highlightbackground="#334155", highlightthickness=1)
        search_frame.pack(fill="x", pady=(0, 15))
        
        tk.Label(search_frame, text="🔍", bg="#1e293b", fg="#64748b", font=("Segoe UI", 11)).pack(side="left", padx=10)
        self.project_search_var = tk.StringVar()
        self.project_search_var.trace_add("write", lambda name, index, mode: self.filter_projects())
        
        search_entry = tk.Entry(
            search_frame, textvariable=self.project_search_var, bg="#1e293b", fg="#f8fafc", 
            insertbackground="#ffffff", relief="flat", font=("Segoe UI", 10)
        )
        search_entry.pack(fill="both", expand=True, side="left", pady=10)
        
        # Scrollable container using custom mouse wheel binder
        self.proj_scroll = ScrollableFrame(tab, bg="#1e293b")
        self.proj_scroll.pack(fill="both", expand=True)
        
        self.all_projects = []

    def load_projects_list(self):
        self.all_projects.clear()
        if os.path.exists(WWW_DIR):
            try:
                for item in os.listdir(WWW_DIR):
                    if os.path.isdir(os.path.join(WWW_DIR, item)):
                        self.all_projects.append(item)
            except Exception:
                pass
        self.filter_projects()

    def filter_projects(self):
        inner_frame = self.proj_scroll.scroll_window
        
        # Clear existing elements
        for widget in inner_frame.winfo_children():
            widget.destroy()
            
        query = self.project_search_var.get().lower()
        filtered = [p for p in self.all_projects if query in p.lower()]
        
        if not filtered:
            tk.Label(inner_frame, text="No local project folders inside www/.", bg="#1e293b", fg="#64748b", font=("Segoe UI", 10, "bold")).pack(pady=40)
            return
            
        for project in filtered:
            row = tk.Frame(inner_frame, bg="#1e293b", pady=8)
            row.pack(fill="x", anchor="w", expand=True, padx=15)
            
            # Project label
            tk.Label(row, text=f"📁  {project}", bg="#1e293b", fg="#f8fafc", font=("Segoe UI", 10, "bold"), anchor="w").pack(side="left", padx=(0, 20))
            
            # Action buttons
            actions = tk.Frame(row, bg="#1e293b")
            actions.pack(side="right")
            
            tk.Button(
                actions, text="Open Browser", bg="#3b82f6", fg="#ffffff", font=("Segoe UI", 8, "bold"),
                relief="flat", padx=12, pady=4, borderwidth=0, cursor="hand2", command=lambda p=project: self.open_project_in_browser(p)
            ).pack(side="left", padx=5)
            
            tk.Button(
                actions, text="Open Folder", bg="#0f172a", fg="#94a3b8", font=("Segoe UI", 8, "bold"),
                relief="flat", padx=12, pady=4, borderwidth=0, cursor="hand2", command=lambda p=project: os.startfile(os.path.join(WWW_DIR, p))
            ).pack(side="left")
            
            # Thin divider
            tk.Frame(inner_frame, bg="#334155", height=1).pack(fill="x", padx=15, pady=4)

    def open_project_in_browser(self, project):
        port = PORTS[self.active_web_server]
        url = f"http://localhost:{port}/{project}" if port != 80 else f"http://localhost/{project}"
        webbrowser.open(url)

    # ==================== SETTINGS TAB ====================
    def create_settings_tab(self):
        tab = tk.Frame(self.work_area, bg="#0f172a")
        self.tabs["settings"] = tab
        
        # Header Row
        hdr = tk.Frame(tab, bg="#0f172a")
        hdr.pack(fill="x", pady=(0, 20))
        
        tk.Label(hdr, text="Settings", bg="#0f172a", fg="#f8fafc", font=("Segoe UI", 18, "bold")).pack(side="left")
        
        # Container for Settings Card
        p = tk.Frame(tab, bg="#1e293b", highlightbackground="#334155", highlightthickness=1, padx=25, pady=25)
        p.pack(fill="both", expand=True)
        
        tk.Label(p, text="Service Ports Configuration", bg="#1e293b", fg="#f8fafc", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 8))
        tk.Label(p, text="Customize the network ports for each service. Port changes will modify configuration files automatically.", 
                 bg="#1e293b", fg="#64748b", font=("Segoe UI", 9), justify="left").pack(anchor="w", pady=(0, 20))
        
        # Port Form
        form_frame = tk.Frame(p, bg="#1e293b")
        form_frame.pack(fill="x", pady=(0, 25))
        form_frame.columnconfigure(0, weight=1)
        form_frame.columnconfigure(1, weight=1)
        
        # Row 1: Nginx & Apache Ports
        # Nginx
        f_nginx = tk.Frame(form_frame, bg="#1e293b")
        f_nginx.grid(row=0, column=0, padx=(0, 10), pady=10, sticky="ew")
        tk.Label(f_nginx, text="Nginx Server Port", bg="#1e293b", fg="#94a3b8", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 5))
        self.entry_port_nginx = tk.Entry(
            f_nginx, bg="#0f172a", fg="#f8fafc", insertbackground="#ffffff", 
            relief="flat", highlightbackground="#334155", highlightthickness=1, font=("Segoe UI", 10)
        )
        self.entry_port_nginx.pack(fill="x", ipady=5)
        self.entry_port_nginx.insert(0, str(PORTS['nginx']))
        
        # Apache
        f_apache = tk.Frame(form_frame, bg="#1e293b")
        f_apache.grid(row=0, column=1, padx=(10, 0), pady=10, sticky="ew")
        tk.Label(f_apache, text="Apache Server Port", bg="#1e293b", fg="#94a3b8", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 5))
        self.entry_port_apache = tk.Entry(
            f_apache, bg="#0f172a", fg="#f8fafc", insertbackground="#ffffff", 
            relief="flat", highlightbackground="#334155", highlightthickness=1, font=("Segoe UI", 10)
        )
        self.entry_port_apache.pack(fill="x", ipady=5)
        self.entry_port_apache.insert(0, str(PORTS['apache']))
        
        # Row 2: MySQL & PHP Ports
        # MySQL
        f_mysql = tk.Frame(form_frame, bg="#1e293b")
        f_mysql.grid(row=1, column=0, padx=(0, 10), pady=10, sticky="ew")
        tk.Label(f_mysql, text="MariaDB Port", bg="#1e293b", fg="#94a3b8", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 5))
        self.entry_port_mysql = tk.Entry(
            f_mysql, bg="#0f172a", fg="#f8fafc", insertbackground="#ffffff", 
            relief="flat", highlightbackground="#334155", highlightthickness=1, font=("Segoe UI", 10)
        )
        self.entry_port_mysql.pack(fill="x", ipady=5)
        self.entry_port_mysql.insert(0, str(PORTS['mysql']))
        
        # PHP
        f_php = tk.Frame(form_frame, bg="#1e293b")
        f_php.grid(row=1, column=1, padx=(10, 0), pady=10, sticky="ew")
        tk.Label(f_php, text="PHP FastCGI Port", bg="#1e293b", fg="#94a3b8", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 5))
        self.entry_port_php = tk.Entry(
            f_php, bg="#0f172a", fg="#f8fafc", insertbackground="#ffffff", 
            relief="flat", highlightbackground="#334155", highlightthickness=1, font=("Segoe UI", 10)
        )
        self.entry_port_php.pack(fill="x", ipady=5)
        self.entry_port_php.insert(0, str(PORTS['php']))
        
        # Save Button
        tk.Button(
            p, text="💾  Save Port Settings", bg="#3b82f6", fg="#ffffff", font=("Segoe UI", 10, "bold"),
            relief="flat", padx=20, pady=10, borderwidth=0, cursor="hand2", command=self.save_port_settings
        ).pack(anchor="w")
        
        # Divider line
        tk.Frame(p, bg="#334155", height=1).pack(fill="x", pady=25)
        
        tk.Label(p, text="System Integration", bg="#1e293b", fg="#f8fafc", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 8))
        tk.Label(p, text="Enable Windows integration features like running automatically on system startup.", 
                 bg="#1e293b", fg="#64748b", font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 15))
        
        self.var_startup = tk.BooleanVar(value=is_startup_enabled())
        cb_startup = tk.Checkbutton(
            p, text="🚀  Start WinPHP on Windows Startup", variable=self.var_startup,
            bg="#1e293b", fg="#f8fafc", activebackground="#1e293b", activeforeground="#f8fafc",
            selectcolor="#0f172a", font=("Segoe UI", 10), command=self.toggle_startup,
            relief="flat", bd=0, highlightthickness=0
        )
        cb_startup.pack(anchor="w", pady=(0, 10))

    def save_port_settings(self):
        try:
            new_ports = {
                'nginx': int(self.entry_port_nginx.get().strip()),
                'apache': int(self.entry_port_apache.get().strip()),
                'mysql': int(self.entry_port_mysql.get().strip()),
                'php': int(self.entry_port_php.get().strip())
            }
        except ValueError:
            messagebox.showerror("Validation Error", "All port numbers must be valid integers.")
            return
            
        for name, port in new_ports.items():
            if port < 1 or port > 65535:
                messagebox.showerror("Validation Error", f"Port for {name.upper()} must be between 1 and 65535.")
                return
                
        ports_list = list(new_ports.values())
        if len(ports_list) != len(set(ports_list)):
            messagebox.showwarning("Warning", "Assigning the same port to multiple services might cause conflicts.")
            
        global PORTS
        old_ports = PORTS.copy()
        PORTS.update(new_ports)
        save_ports(PORTS)
        
        def apply_changes():
            self.set_status_bar("Applying port configurations...")
            for name, port in new_ports.items():
                if port != old_ports.get(name):
                    update_service_port_in_config(name, old_ports.get(name), port)
            
            # Update descriptions in the UI cards
            self.update_service_descriptions()
            self.set_status_bar("Port configuration saved successfully.")
            messagebox.showinfo("Success", "Ports updated and configuration files written!\n\nPlease restart any running services for the changes to take effect.")
            
        threading.Thread(target=apply_changes, daemon=True).start()

    def update_service_descriptions(self):
        descriptions = {
            "nginx": f"Web Server · Port {PORTS['nginx']}",
            "apache": f"Web Server · Port {PORTS['apache']}",
            "mysql": f"Database Engine · Port {PORTS['mysql']}",
            "php": f"Processor · Port {PORTS['php']}"
        }
        for svc_id, desc in descriptions.items():
            if svc_id in self.service_cards and 'desc_lbl' in self.service_cards[svc_id]:
                try:
                    self.service_cards[svc_id]['desc_lbl'].config(text=desc)
                except:
                    pass

    # ==================== SYSTEM METRICS LOOPS ====================
    def system_stats_loop(self):
        while self.stats_thread_active:
            # Memory load calculation
            mem_pct = 0
            try:
                mem_out = subprocess.check_output(
                    ["powershell", "-Command", "Get-CimInstance Win32_OperatingSystem | Select-Object TotalVisibleMemorySize,FreePhysicalMemory | ConvertTo-Json"],
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    text=True
                )
                mem_data = json.loads(mem_out)
                total_mem = mem_data['TotalVisibleMemorySize']
                free_mem = mem_data['FreePhysicalMemory']
                mem_pct = round(((total_mem - free_mem) / total_mem) * 100)
            except:
                pass

            # CPU load calculation
            cpu_pct = 0
            try:
                cpu_out = subprocess.check_output(
                    ["powershell", "-Command", "Get-CimInstance Win32_Processor | Select-Object -ExpandProperty LoadPercentage"],
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    text=True
                )
                cpu_pct = int(cpu_out.strip())
            except:
                pass

            # Disk load calculation
            disk_pct = 0
            try:
                disk_out = subprocess.check_output(
                    ["powershell", "-Command", "Get-CimInstance Win32_LogicalDisk | Where-Object DeviceID -eq 'C:' | Select-Object Size,FreeSpace | ConvertTo-Json"],
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    text=True
                )
                disk_data = json.loads(disk_out)
                size = disk_data['Size']
                free = disk_data['FreeSpace']
                disk_pct = round(((size - free) / size) * 100)
            except:
                pass

            # Update Custom Flat Progress Bars
            self.update_progressbar(cpu_pct, "cpu_fill", "cpu_lbl")
            self.update_progressbar(mem_pct, "ram_fill", "ram_lbl")
            self.update_progressbar(disk_pct, "disk_fill", "disk_lbl")
                
            time.sleep(3)

    def update_progressbar(self, pct, fill_attr, lbl_attr):
        try:
            # Max width in sidebar is scaled by DPI factor
            max_width = int(170 * self.dpi_factor)
            target_width = int(max_width * (pct / 100))
            
            fill_bar = getattr(self, fill_attr)
            val_lbl = getattr(self, lbl_attr)
            
            # Safely configure width and label values on main thread
            fill_bar.config(width=target_width)
            val_lbl.config(text=f"{pct}%")
        except:
            pass

    def services_status_loop(self):
        while self.status_thread_active:
            for name in PORTS.keys():
                status, pid, memory = get_service_status(name)
                
                try:
                    card = self.service_cards[name]
                    if status == "running":
                        card['canvas'].itemconfig(1, fill="#10b981", outline="#10b981") # Green dot
                        card['label'].config(text="Running", fg="#10b981")
                        card['mem'].config(text=f"{memory} MB")
                        card['btn'].config(text="Stop", bg="#ef4444")
                    else:
                        card['canvas'].itemconfig(1, fill="#ef4444", outline="#ef4444") # Red dot
                        card['label'].config(text="Stopped", fg="#ef4444")
                        card['mem'].config(text="")
                        card['btn'].config(text="Start", bg="#10b981")
                except:
                    pass
            time.sleep(1)

    def on_close(self):
        self.real_exit()
        
    def real_exit(self):
        if hasattr(self, 'tray_icon') and self.tray_icon:
            try:
                self.tray_icon.stop()
            except:
                pass
                
        self.stats_thread_active = False
        self.status_thread_active = False
        
        progress = tk.Toplevel(self)
        progress.title("Exiting")
        progress.geometry("320x110")
        progress.resizable(False, False)
        progress.configure(bg="#1e293b")
        
        # Center progress box
        progress.update_idletasks()
        width = progress.winfo_width()
        height = progress.winfo_height()
        x = (progress.winfo_screenwidth() // 2) - (width // 2)
        y = (progress.winfo_screenheight() // 2) - (height // 2)
        progress.geometry(f'+{x}+{y}')
        
        lbl = tk.Label(progress, text="Shutting down background services...", bg="#1e293b", fg="#ffffff", font=("Segoe UI", 10, "bold"))
        lbl.pack(pady=40)
        self.update()
        
        for service in ['nginx', 'apache', 'mysql', 'php']:
            try:
                stop_service_internal(service)
            except:
                pass
                
        progress.destroy()
        self.destroy()
        os._exit(0)

    def setup_tray(self):
        icon_path = os.path.join(BASE_DIR, 'icon.ico')
        if not os.path.exists(icon_path):
            from PIL import ImageDraw
            img = Image.new('RGB', (64, 64), color = (59, 130, 246))
            d = ImageDraw.Draw(img)
            d.text((10, 10), "PHP", fill=(255, 255, 255))
        else:
            try:
                img = Image.open(icon_path)
            except Exception:
                from PIL import ImageDraw
                img = Image.new('RGB', (64, 64), color = (59, 130, 246))
                d = ImageDraw.Draw(img)
                d.text((10, 10), "PHP", fill=(255, 255, 255))

        def on_tray_click(icon, item):
            name = str(item)
            if name == 'Show Control Center':
                self.after(0, self.restore_window)
            elif name == 'Start All Services':
                self.after(0, self.start_all_services)
            elif name == 'Stop All Services':
                self.after(0, self.stop_all_services)
            elif name == 'Exit':
                self.after(0, self.real_exit)

        menu = pystray.Menu(
            pystray.MenuItem('Show Control Center', on_tray_click, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('Start All Services', on_tray_click),
            pystray.MenuItem('Stop All Services', on_tray_click),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('Exit', on_tray_click)
        )
        
        self.tray_icon = pystray.Icon("WinPHP", img, "WinPHP Server Manager", menu)
        self.tray_icon.run_detached()

    def restore_window(self):
        self.deiconify()
        self.state('normal')
        self.lift()
        self.focus_force()

    def on_minimize(self, event):
        if self.state() == 'iconic':
            self.withdraw()

    def toggle_startup(self):
        enabled = self.var_startup.get()
        try:
            set_startup(enabled)
            self.set_status_bar(f"Startup {'enabled' if enabled else 'disabled'}.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not change startup settings: {e}")

if __name__ == '__main__':
    # Enable High DPI awareness for sharp text and proper layout scaling on high-resolution monitors
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
        
    pids = load_pids()
    cleaned = False
    for name, port in PORTS.items():
        if not is_port_open(port) and pids.get(name):
            pids[name] = None
            cleaned = True
    if cleaned:
        save_pids(pids)
        
    app = WinPHPApp()
    app.mainloop()
