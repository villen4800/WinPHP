import os
import sys
import json
import socket
import subprocess
import time
import threading
import webbrowser
import winreg
import zipfile
import urllib.request
import shutil

from PySide6.QtCore import Qt, QSize, QThread, Signal, Slot, QTimer, QMetaObject, QEvent
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QComboBox, QLineEdit, QPlainTextEdit,
    QCheckBox, QScrollArea, QFrame, QStackedWidget, QDialog, 
    QMessageBox, QSystemTrayIcon, QMenu, QGridLayout, QProgressBar,
    QSizePolicy
)
from PySide6.QtGui import QIcon, QPixmap, QColor, QFont, QAction, QFontMetrics, QFontMetricsF

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
    'apache': 80,
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

PROCESS_NAMES = {
    'nginx': 'nginx.exe',
    'apache': 'httpd.exe',
    'mysql': 'mysqld.exe',
    'php': 'php-cgi.exe'
}

def is_process_running_by_name(image_name):
    if not image_name:
        return False
    try:
        out = subprocess.check_output(
            ["tasklist", "/NH", "/FI", f"IMAGENAME eq {image_name}"],
            creationflags=subprocess.CREATE_NO_WINDOW,
            text=True
        )
        return image_name.lower() in out.lower()
    except Exception:
        return False

def get_service_status(name):
    pids = load_pids()
    pid = pids.get(name)
    
    port = PORTS.get(name)
    port_active = is_port_open(port) if port else False
    
    img_name = PROCESS_NAMES.get(name)
    is_running = (is_pid_running(pid) if pid else False) or (is_process_running_by_name(img_name) and port_active)
    
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


# Package Manager definitions
AVAILABLE_VERSIONS = {
    'php': {
        'php-8.3.15-nts': 'https://windows.php.net/downloads/releases/php-8.3.15-nts-Win32-vs16-x64.zip',
        'php-8.2.31-nts': 'https://windows.php.net/downloads/releases/php-8.2.31-nts-Win32-vs16-x64.zip',
        'php-8.1.30-nts': 'https://windows.php.net/downloads/releases/php-8.1.30-nts-Win32-vs16-x64.zip',
        'php-8.0.30-nts': 'https://windows.php.net/downloads/releases/php-8.0.30-nts-Win32-vs16-x64.zip',
        'php-7.4.33-nts': 'https://windows.php.net/downloads/releases/archives/php-7.4.33-nts-Win32-vc15-x64.zip'
    },
    'nginx': {
        'nginx-1.26.3': 'https://nginx.org/download/nginx-1.26.3.zip',
        'nginx-1.24.0': 'https://nginx.org/download/nginx-1.24.0.zip'
    },
    'apache': {
        'apache-2.4.62': 'https://www.apachelounge.com/download/VS17/binaries/httpd-2.4.62-win64-VS17.zip',
        'apache-2.4.58': 'https://www.apachelounge.com/download/VS17/binaries/httpd-2.4.58-win64-VS17.zip'
    },
    'mysql': {
        'mariadb-10.11.8': 'https://downloads.mariadb.com/MariaDB/mariadb-10.11.8/winx64-packages/mariadb-10.11.8-winx64.zip',
        'mariadb-11.4.2': 'https://downloads.mariadb.com/MariaDB/mariadb-11.4.2/winx64-packages/mariadb-11.4.2-winx64.zip'
    },
    'phpmyadmin': {
        'phpmyadmin-5.2.3': 'https://files.phpmyadmin.net/phpMyAdmin/5.2.3/phpMyAdmin-5.2.3-all-languages.zip'
    }
}

INSTALLED_PACKAGES_FILE = os.path.join(BIN_DIR, 'installed_packages.json')

def load_installed_packages():
    if os.path.exists(INSTALLED_PACKAGES_FILE):
        try:
            with open(INSTALLED_PACKAGES_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    # Detect what is physically installed
    installed = {}
    if os.path.exists(os.path.join(BIN_DIR, 'nginx', 'nginx.exe')):
        installed['nginx'] = 'nginx-1.26.3'
    if os.path.exists(os.path.join(BIN_DIR, 'apache', 'bin', 'httpd.exe')):
        installed['apache'] = 'apache-2.4.62'
    if os.path.exists(os.path.join(BIN_DIR, 'mysql', 'bin', 'mysqld.exe')):
        installed['mysql'] = 'mariadb-10.11.8'
    if os.path.exists(os.path.join(TOOLS_DIR, 'phpmyadmin', 'index.php')):
        installed['phpmyadmin'] = 'phpmyadmin-5.2.3'
    return installed

def save_installed_packages(installed):
    try:
        with open(INSTALLED_PACKAGES_FILE, 'w') as f:
            json.dump(installed, f, indent=4)
    except Exception:
        pass


class PackageInstallWorker(QThread):
    progress_updated = Signal(str, int)  # task, percentage
    finished = Signal(bool, str)        # success, message
    
    def __init__(self, service_name, version_name, url, dest_dir, strip_root=False, nested_folder=None):
        super().__init__()
        self.service_name = service_name
        self.version_name = version_name
        self.url = url
        self.dest_dir = dest_dir
        self.strip_root = strip_root
        self.nested_folder = nested_folder
        self.downloads_dir = os.path.join(BASE_DIR, 'downloads')
        
    def run(self):
        try:
            # 1. Create downloads folder
            os.makedirs(self.downloads_dir, exist_ok=True)
            
            # 2. Set download filename
            zip_filename = os.path.basename(self.url)
            zip_path = os.path.join(self.downloads_dir, zip_filename)
            
            # 3. Stop service if running
            self.progress_updated.emit("Stopping service...", 5)
            stop_service_internal(self.service_name)
            time.sleep(0.5)
            
            # 4. Download file
            self.progress_updated.emit("Downloading zip file...", 10)
            req = urllib.request.Request(
                self.url,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            
            with urllib.request.urlopen(req) as response:
                total_size = int(response.info().get('Content-Length', 0))
                downloaded = 0
                block_size = 512 * 1024  # 512KB chunks
                
                with open(zip_path, 'wb') as f:
                    while True:
                        chunk = response.read(block_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = int((downloaded / total_size) * 70)  # scale download to 10%-80%
                            self.progress_updated.emit("Downloading...", 10 + percent)
                        else:
                            self.progress_updated.emit("Downloading (unknown size)...", 40)
            
            # 5. Extract file
            self.progress_updated.emit("Extracting files...", 80)
            os.makedirs(self.dest_dir, exist_ok=True)
            
            # Extract to temp first
            temp_extract = os.path.join(self.downloads_dir, 'temp_extract')
            if os.path.exists(temp_extract):
                shutil.rmtree(temp_extract)
            os.makedirs(temp_extract, exist_ok=True)
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_extract)
                
            if self.strip_root:
                contents = os.listdir(temp_extract)
                if self.nested_folder and self.nested_folder in contents:
                    root_src = os.path.join(temp_extract, self.nested_folder)
                elif len(contents) == 1 and os.path.isdir(os.path.join(temp_extract, contents[0])):
                    root_src = os.path.join(temp_extract, contents[0])
                else:
                    root_src = temp_extract
                    
                for item in os.listdir(root_src):
                    s = os.path.join(root_src, item)
                    d = os.path.join(self.dest_dir, item)
                    if os.path.exists(d):
                        if os.path.isdir(d):
                            shutil.rmtree(d)
                        else:
                            os.remove(d)
                    shutil.move(s, d)
            else:
                for item in os.listdir(temp_extract):
                    s = os.path.join(temp_extract, item)
                    d = os.path.join(self.dest_dir, item)
                    if os.path.exists(d):
                        if os.path.isdir(d):
                            shutil.rmtree(d)
                        else:
                            os.remove(d)
                    shutil.move(s, d)
                    
            shutil.rmtree(temp_extract)
            try:
                os.remove(zip_path)
            except:
                pass
                
            # 6. Post-install setups
            self.progress_updated.emit("Configuring package...", 90)
            if self.service_name == 'php':
                self.setup_php(self.dest_dir)
            elif self.service_name == 'nginx':
                self.setup_nginx(self.dest_dir)
            elif self.service_name == 'apache':
                self.setup_apache(self.dest_dir)
            elif self.service_name == 'mysql':
                self.setup_mysql(self.dest_dir)
            elif self.service_name == 'phpmyadmin':
                self.setup_phpmyadmin(self.dest_dir)
                
            # Create a default index.php if not exists
            default_index = os.path.join(WWW_DIR, 'index.php')
            if not os.path.exists(default_index):
                os.makedirs(WWW_DIR, exist_ok=True)
                with open(default_index, 'w') as f:
                    f.write("""<!DOCTYPE html>
<html>
<head>
    <title>Welcome to WinPHP</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #0f172a; color: #f8fafc; text-align: center; padding-top: 100px; }
        h1 { color: #3b82f6; }
        .info { background: #1e293b; display: inline-block; padding: 20px; border-radius: 8px; border: 1px solid #334155; }
    </style>
</head>
<body>
    <h1>WinPHP Server is Running Successfully!</h1>
    <div class="info">
        <p>PHP Version: <?php echo phpversion(); ?></p>
        <p>Document Root: <code><?php echo $_SERVER['DOCUMENT_ROOT']; ?></code></p>
        <p><a href="/phpmyadmin" style="color: #10b981;">Open phpMyAdmin</a></p>
    </div>
</body>
</html>""")
            
            # Clean up downloads dir
            if os.path.exists(self.downloads_dir):
                try:
                    shutil.rmtree(self.downloads_dir)
                except:
                    pass
                    
            self.progress_updated.emit("Done!", 100)
            self.finished.emit(True, f"{self.service_name.upper()} {self.version_name} successfully installed!")
        except Exception as e:
            self.finished.emit(False, str(e))
            
    def setup_php(self, php_dir):
        php_ini_dev = os.path.join(php_dir, 'php.ini-development')
        php_ini = os.path.join(php_dir, 'php.ini')
        if os.path.exists(php_ini_dev) and not os.path.exists(php_ini):
            with open(php_ini_dev, 'r') as f:
                content = f.read()
            content = content.replace(';extension_dir = "ext"', 'extension_dir = "ext"')
            extensions = ['curl', 'mbstring', 'mysqli', 'openssl', 'pdo_mysql', 'sockets']
            for ext in extensions:
                content = content.replace(f';extension={ext}', f'extension={ext}')
            with open(php_ini, 'w') as f:
                f.write(content)

    def setup_nginx(self, nginx_dir):
        nginx_conf = os.path.join(nginx_dir, 'conf', 'nginx.conf')
        if os.path.exists(nginx_conf):
            return
            
        www_path = WWW_DIR.replace('\\', '/')
        phpmyadmin_path = os.path.join(TOOLS_DIR, 'phpmyadmin').replace('\\', '/')
        
        conf_content = f"""worker_processes  1;
events {{
    worker_connections  1024;
}}
http {{
    include       mime.types;
    default_type  application/octet-stream;
    sendfile        on;
    keepalive_timeout  65;

    server {{
        listen       {PORTS['nginx']};
        server_name  localhost;

        root         "{www_path}";
        index        index.php index.html index.htm;

        location / {{
            try_files $uri $uri/ =404;
        }}

        location ~ \\.php$ {{
            fastcgi_pass   127.0.0.1:{PORTS['php']};
            fastcgi_index  index.php;
            fastcgi_param  SCRIPT_FILENAME  $document_root$fastcgi_script_name;
            include        fastcgi_params;
        }}

        location /phpmyadmin {{
            alias "{phpmyadmin_path}/";
            index index.php index.html;
            
            location ~ \\.php$ {{
                fastcgi_pass   127.0.0.1:{PORTS['php']};
                fastcgi_index  index.php;
                fastcgi_param  SCRIPT_FILENAME  $request_filename;
                include        fastcgi_params;
            }}
        }}
    }}
}}
"""
        with open(nginx_conf, 'w') as f:
            f.write(conf_content)

    def setup_apache(self, apache_dir):
        httpd_conf = os.path.join(apache_dir, 'conf', 'httpd.conf')
        if os.path.exists(httpd_conf):
            try:
                with open(httpd_conf, 'r') as f:
                    content = f.read()
                
                apache_path_esc = apache_dir.replace('\\', '/')
                content = content.replace('Define SRVROOT "C:/Apache24"', f'Define SRVROOT "{apache_path_esc}"')
                content = content.replace('Define SRVROOT "c:/Apache24"', f'Define SRVROOT "{apache_path_esc}"')
                import re
                content = re.sub(r'\bListen\s+80\b', f'Listen {PORTS["apache"]}', content)
                
                www_path_esc = WWW_DIR.replace('\\', '/')
                content = content.replace('DocumentRoot "${SRVROOT}/htdocs"', f'DocumentRoot "{www_path_esc}"')
                content = content.replace('<Directory "${SRVROOT}/htdocs">', f'<Directory "{www_path_esc}">')
                content = content.replace('DirectoryIndex index.html', 'DirectoryIndex index.php index.html')
                
                if 'proxy_fcgi_module' not in content:
                    content = content.replace('#LoadModule proxy_module modules/mod_proxy.so', 'LoadModule proxy_module modules/mod_proxy.so')
                    content = content.replace('#LoadModule proxy_fcgi_module modules/mod_proxy_fcgi.so', 'LoadModule proxy_fcgi_module modules/mod_proxy_fcgi.so')
                    
                    phpmyadmin_path_esc = os.path.join(TOOLS_DIR, 'phpmyadmin').replace('\\', '/')
                    php_proxy_setup = f"""
# PHP FastCGI proxy setup
<FilesMatch \\.php$>
    ProxyFCGIBackendType GENERIC
    SetHandler "proxy:fcgi://127.0.0.1:{PORTS['php']}//./"
</FilesMatch>

Alias /phpmyadmin "{phpmyadmin_path_esc}"
<Directory "{phpmyadmin_path_esc}">
    Options Indexes FollowSymLinks
    AllowOverride All
    Require all granted
</Directory>
"""
                    content += php_proxy_setup
                    
                with open(httpd_conf, 'w') as f:
                    f.write(content)
            except Exception as e:
                print(f"Error configuring Apache: {e}")

    def setup_mysql(self, mysql_dir):
        my_ini = os.path.join(mysql_dir, 'my.ini')
        if not os.path.exists(my_ini):
            mysql_dir_esc = mysql_dir.replace('\\', '/')
            data_dir_esc = os.path.join(mysql_dir, 'data').replace('\\', '/')
            ini_content = f"""[mysqld]
port={PORTS['mysql']}
basedir="{mysql_dir_esc}"
datadir="{data_dir_esc}"
bind-address=127.0.0.1
sql_mode=NO_ENGINE_SUBSTITUTION
max_allowed_packet=64M
default-storage-engine=INNODB
"""
            with open(my_ini, 'w') as f:
                f.write(ini_content)
                
        data_dir = os.path.join(mysql_dir, 'data')
        if not os.path.exists(data_dir):
            install_db_exe = os.path.join(mysql_dir, 'bin', 'mysql_install_db.exe')
            if os.path.exists(install_db_exe):
                cmd = [install_db_exe, f'--datadir={data_dir}']
                subprocess.run(cmd, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)

    def setup_phpmyadmin(self, pma_dir):
        config_sample = os.path.join(pma_dir, 'config.sample.inc.php')
        config_inc = os.path.join(pma_dir, 'config.inc.php')
        if os.path.exists(config_sample) and not os.path.exists(config_inc):
            with open(config_sample, 'r') as f:
                content = f.read()
            content = content.replace("['AllowNoPassword'] = false;", "['AllowNoPassword'] = true;")
            content = content.replace("['auth_type'] = 'cookie';", "['auth_type'] = 'config';")
            content = content.replace("['host'] = 'localhost';", "['host'] = '127.0.0.1';")
            content = content.replace("/* Server parameters */", "/* Server parameters */\n$cfg['Servers'][$i]['user'] = 'root';\n$cfg['Servers'][$i]['password'] = '';")
            
            import re
            content = re.sub(r"\['blowfish_secret'\] = '';", "['blowfish_secret'] = 'winphpservermanagersecretblowfish32chars';", content)
            
            with open(config_inc, 'w') as f:
                f.write(content)


class PackageCard(QFrame):
    def __init__(self, svc_id, title, desc, versions_dict, stripe_color, parent_app):
        super().__init__()
        self.svc_id = svc_id
        self.title = title
        self.desc = desc
        self.versions_dict = versions_dict
        self.stripe_color = stripe_color
        self.parent_app = parent_app
        
        self.setObjectName("PackageCard")
        self.setStyleSheet("""
            QFrame#PackageCard {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 8px;
            }
            QFrame#PackageCard:hover {
                border: 1px solid #3b82f6;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Left accent stripe
        self.stripe = QFrame()
        self.stripe.setFixedWidth(4)
        self.stripe.setStyleSheet(f"background-color: {stripe_color}; border-top-left-radius: 8px; border-bottom-left-radius: 8px;")
        layout.addWidget(self.stripe)
        
        # Content frame
        content = QWidget()
        content.setObjectName("CardContent")
        content.setStyleSheet("QWidget#CardContent { background-color: transparent; border: none; }")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 12, 16, 12)
        content_layout.setSpacing(6)
        
        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #f8fafc; background-color: transparent;")
        content_layout.addWidget(self.title_lbl)
        
        self.desc_lbl = QLabel(desc)
        self.desc_lbl.setStyleSheet("font-size: 12px; color: #64748b; background-color: transparent;")
        content_layout.addWidget(self.desc_lbl)
        
        # Current status label
        self.status_lbl = QLabel("Installed Version: Checking...")
        self.status_lbl.setStyleSheet("font-size: 12px; font-weight: bold; color: #94a3b8; background-color: transparent;")
        content_layout.addWidget(self.status_lbl)
        
        content_layout.addStretch()
        
        # Controls Row
        ctrl_layout = QHBoxLayout()
        ctrl_layout.setSpacing(10)
        
        self.version_combo = QComboBox()
        self.version_combo.addItems(list(versions_dict.keys()))
        self.version_combo.setFixedWidth(180)
        ctrl_layout.addWidget(self.version_combo)
        
        self.btn = QPushButton("Install / Switch")
        self.btn.setCursor(Qt.PointingHandCursor)
        self.btn.setFixedSize(130, 30)
        self.btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                font-weight: bold;
                font-size: 12px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
            QPushButton:disabled {
                background-color: #334155;
                color: #64748b;
            }
        """)
        self.btn.clicked.connect(self.start_installation)
        ctrl_layout.addWidget(self.btn)
        
        ctrl_layout.addStretch()
        content_layout.addLayout(ctrl_layout)
        
        # Progress Row (initially hidden)
        self.progress_row = QWidget()
        self.progress_row.setStyleSheet("border: none; background-color: transparent;")
        prog_layout = QVBoxLayout(self.progress_row)
        prog_layout.setContentsMargins(0, 5, 0, 0)
        prog_layout.setSpacing(4)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #334155;
                border-radius: 4px;
                border: none;
            }
            QProgressBar::chunk {
                background-color: #10b981;
                border-radius: 4px;
            }
        """)
        prog_layout.addWidget(self.progress_bar)
        
        self.progress_lbl = QLabel("")
        self.progress_lbl.setStyleSheet("font-size: 11px; color: #10b981; font-weight: bold;")
        prog_layout.addWidget(self.progress_lbl)
        
        self.progress_row.setVisible(False)
        content_layout.addWidget(self.progress_row)
        
        layout.addWidget(content)
        
        self.refresh_status()
        
    def refresh_status(self):
        installed = load_installed_packages()
        current = installed.get(self.svc_id)
        if self.svc_id == 'php':
            active = get_current_php_version()
            installed_list = get_php_versions()
            if active in installed_list:
                self.status_lbl.setText(f"Active Version: {active}  (Installed: {len(installed_list)} versions)")
                self.status_lbl.setStyleSheet("font-size: 12px; font-weight: bold; color: #10b981; background-color: transparent;")
            else:
                self.status_lbl.setText("Status: No PHP versions installed")
                self.status_lbl.setStyleSheet("font-size: 12px; font-weight: bold; color: #ef4444; background-color: transparent;")
        else:
            if current:
                self.status_lbl.setText(f"Installed Version: {current}")
                self.status_lbl.setStyleSheet("font-size: 12px; font-weight: bold; color: #10b981; background-color: transparent;")
            else:
                self.status_lbl.setText("Status: Not Installed")
                self.status_lbl.setStyleSheet("font-size: 12px; font-weight: bold; color: #ef4444; background-color: transparent;")
                
    def start_installation(self):
        selected_version = self.version_combo.currentText()
        url = self.versions_dict[selected_version]
        
        strip_root = True
        nested_folder = None
        
        if self.svc_id == 'php':
            dest = os.path.join(BIN_DIR, 'php', selected_version)
            strip_root = False
        elif self.svc_id == 'nginx':
            dest = os.path.join(BIN_DIR, 'nginx')
        elif self.svc_id == 'apache':
            dest = os.path.join(BIN_DIR, 'apache')
            nested_folder = 'Apache24'
        elif self.svc_id == 'mysql':
            dest = os.path.join(BIN_DIR, 'mysql')
        elif self.svc_id == 'phpmyadmin':
            dest = os.path.join(TOOLS_DIR, 'phpmyadmin')
            
        self.btn.setEnabled(False)
        self.version_combo.setEnabled(False)
        self.progress_row.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_lbl.setText("Initializing installation...")
        
        self.worker = PackageInstallWorker(self.svc_id, selected_version, url, dest, strip_root, nested_folder)
        self.worker.progress_updated.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()
        
    def on_progress(self, task, pct):
        self.progress_bar.setValue(pct)
        self.progress_lbl.setText(f"{task} ({pct}%)")
        
    def on_finished(self, success, message):
        self.progress_row.setVisible(False)
        self.btn.setEnabled(True)
        self.version_combo.setEnabled(True)
        
        if success:
            QMessageBox.information(self, "Installation Complete", message)
            
            installed = load_installed_packages()
            installed[self.svc_id] = self.version_combo.currentText()
            save_installed_packages(installed)
            
            self.refresh_status()
            self.parent_app.on_package_installed(self.svc_id)
        else:
            QMessageBox.critical(self, "Installation Error", f"Installation failed:\n{message}")


# Background thread worker for checking statuses and system metrics
class StatusAndMetricsWorker(QThread):
    status_updated = Signal(dict)
    metrics_updated = Signal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.active = True
        self.window_active = True
        
    def run(self):
        counter = 0
        while self.active:
            # 1. Services Status Check (every 1 second)
            statuses = {}
            for name in ['nginx', 'apache', 'mysql', 'php']:
                status, pid, memory = get_service_status(name)
                statuses[name] = (status, pid, memory)
            self.status_updated.emit(statuses)
            
            # 2. System Metrics Check (every 3 seconds)
            if counter % 3 == 0 and self.window_active:
                metrics = {}
                
                # RAM
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
                metrics['ram'] = mem_pct

                # CPU
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
                metrics['cpu'] = cpu_pct

                # Disk
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
                metrics['disk'] = disk_pct
                
                self.metrics_updated.emit(metrics)
                
            counter += 1
            self.msleep(1000)
            
    def stop(self):
        self.active = False


# Premium stylized custom card for services
class ServiceCard(QFrame):
    def __init__(self, svc_id, title, desc, stripe_color, has_select=False, parent=None):
        super().__init__(parent)
        self.svc_id = svc_id
        self.title = title
        self.desc = desc
        self.stripe_color = stripe_color
        self.has_select = has_select
        
        self.setObjectName("ServiceCard")
        self.setStyleSheet(f"""
            QFrame#ServiceCard {{
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 8px;
            }}
            QFrame#ServiceCard:hover {{
                border: 1px solid #3b82f6;
            }}
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Left accent stripe
        self.stripe = QFrame()
        self.stripe.setFixedWidth(4)
        self.stripe.setStyleSheet(f"background-color: {stripe_color}; border-top-left-radius: 8px; border-bottom-left-radius: 8px;")
        layout.addWidget(self.stripe)
        
        # Content frame
        content = QWidget()
        content.setObjectName("CardContent")
        content.setStyleSheet("QWidget#CardContent { background-color: transparent; border: none; }")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 12, 16, 12)
        content_layout.setSpacing(6)
        
        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #f8fafc; background-color: transparent;")
        content_layout.addWidget(self.title_lbl)
        
        self.desc_lbl = QLabel(desc)
        self.desc_lbl.setStyleSheet("font-size: 12px; color: #64748b; background-color: transparent;")
        content_layout.addWidget(self.desc_lbl)
        
        # Status Row
        status_row = QHBoxLayout()
        status_row.setSpacing(8)
        
        self.status_dot = QFrame()
        self.status_dot.setFixedSize(10, 10)
        self.status_dot.setStyleSheet("background-color: #ef4444; border-radius: 5px;")
        status_row.addWidget(self.status_dot)
        
        self.status_lbl = QLabel("Stopped")
        self.status_lbl.setStyleSheet("font-size: 12px; font-weight: bold; color: #ef4444; background-color: transparent;")
        status_row.addWidget(self.status_lbl)
        
        status_row.addStretch()
        
        self.mem_lbl = QLabel("")
        self.mem_lbl.setStyleSheet("font-size: 12px; font-weight: bold; color: #94a3b8; background-color: transparent;")
        status_row.addWidget(self.mem_lbl)
        
        content_layout.addLayout(status_row)
        content_layout.addStretch()
        
        # Controls Row
        ctrl_row = QHBoxLayout()
        self.btn = QPushButton("Start")
        self.btn.setCursor(Qt.PointingHandCursor)
        self.btn.setFixedSize(85, 30)
        self.btn.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                font-weight: bold;
                font-size: 12px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        ctrl_row.addWidget(self.btn)
        
        ctrl_row.addStretch()
        
        if has_select:
            self.combobox = QComboBox()
            self.combobox.setFixedWidth(145)
            self.combobox.setStyleSheet("""
                QComboBox {
                    background-color: #0f172a;
                    border: 1px solid #334155;
                    border-radius: 6px;
                    padding: 4px 8px;
                    font-size: 12px;
                    color: #f8fafc;
                }
            """)
            ctrl_row.addWidget(self.combobox)
            
        content_layout.addLayout(ctrl_row)
        
        layout.addWidget(content)


# Main WinPHP Control Center Application Window
class WinPHPApp(QMainWindow):
    status_bar_msg = Signal(str)
    message_box = Signal(str, str, str)
    extensions_loaded = Signal(list)
    projects_loaded = Signal(list)
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WinPHP Control Center")
        self.setMinimumSize(1000, 720)
        
        self.active_php_version = get_current_php_version()
        self.php_versions = get_php_versions()
        self.active_web_server = "nginx"
        self.detect_active_web_server()
        
        # Thread signals connection
        self.status_bar_msg.connect(self.set_status_bar)
        self.message_box.connect(self.show_message_box_slot)
        self.extensions_loaded.connect(self.display_extensions_list)
        self.projects_loaded.connect(self.display_projects_list)
        
        # Style sheet setup
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0f172a;
            }
            QWidget {
                font-family: 'Segoe UI', sans-serif;
                color: #f8fafc;
            }
            QLabel {
                background-color: transparent;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QComboBox {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 12px;
                color: #f8fafc;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox QAbstractItemView {
                background-color: #1e293b;
                border: 1px solid #334155;
                color: #f8fafc;
                selection-background-color: #3b82f6;
                selection-color: #ffffff;
                outline: 0px;
                padding: 6px;
            }
            QLineEdit {
                background-color: #0f172a;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 8px 12px;
                color: #f8fafc;
            }
            QLineEdit:focus {
                border: 1px solid #3b82f6;
            }
            QPlainTextEdit {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 10px;
                color: #f8fafc;
            }
            QCheckBox {
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 1px solid #334155;
                border-radius: 4px;
                background-color: #0f172a;
            }
            QCheckBox::indicator:unchecked:hover {
                border: 1px solid #3b82f6;
            }
            QCheckBox::indicator:checked {
                background-color: #3b82f6;
                border: 1px solid #3b82f6;
                image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='white' width='16px' height='16px'><path d='M0 0h24v24H0V0z' fill='none'/><path d='M9 16.2L4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4L9 16.2z'/></svg>");
            }
            QScrollBar:vertical {
                border: none;
                background: #0f172a;
                width: 8px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #334155;
                min-height: 20px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #475569;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar:horizontal {
                border: none;
                background: #0f172a;
                height: 8px;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background: #334155;
                min-width: 20px;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #475569;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
        """)
        
        icon_path = os.path.join(BASE_DIR, 'icon.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            
        self.create_layout()
        
        # Start background worker
        self.worker = StatusAndMetricsWorker(self)
        self.worker.status_updated.connect(self.on_status_updated)
        self.worker.metrics_updated.connect(self.on_metrics_updated)
        self.worker.start()
        
        # System Tray setup
        self.setup_tray()
        
    def detect_active_web_server(self):
        a_status, _, _ = get_service_status('apache')
        n_status, _, _ = get_service_status('nginx')
        if a_status == 'running':
            self.active_web_server = 'apache'
        elif n_status == 'running':
            self.active_web_server = 'nginx'

    def create_layout(self):
        # Central Widget & Main horizontal layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Sidebar Frame (Slate 800)
        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(230)
        self.sidebar.setStyleSheet("background-color: #1e293b; border: none;")
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(0, 20, 0, 20)
        sidebar_layout.setSpacing(5)
        
        # Brand Logo in Sidebar
        brand_container = QWidget()
        brand_layout = QVBoxLayout(brand_container)
        brand_layout.setContentsMargins(20, 0, 20, 10)
        brand_layout.setSpacing(2)
        
        self.logo_lbl = QLabel()
        logo_path = os.path.join(BASE_DIR, 'logo.png')
        logo_loaded = False
        if os.path.exists(logo_path):
            try:
                pixmap = QPixmap(logo_path)
                scaled_pixmap = pixmap.scaled(170, 50, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.logo_lbl.setPixmap(scaled_pixmap)
                logo_loaded = True
            except Exception:
                pass
        if not logo_loaded:
            self.logo_lbl.setText("⚡ WinPHP")
            self.logo_lbl.setStyleSheet("font-size: 22px; font-weight: bold; color: #3b82f6; padding: 10px 0px;")
            
        brand_layout.addWidget(self.logo_lbl)
        
        version_lbl = QLabel("v1.2 Premium Console")
        version_lbl.setStyleSheet("font-size: 11px; font-weight: bold; color: #64748b;")
        brand_layout.addWidget(version_lbl)
        
        sidebar_layout.addWidget(brand_container)
        sidebar_layout.addSpacing(10)
        
        # Sidebar Menu Items
        self.menu_buttons = {}
        menu_items = [
            ("Dashboard", "dashboard"),
            ("Config Editor", "config"),
            ("Logs Viewer", "logs"),
            ("PHP Extensions", "extensions"),
            ("DB Manager", "db"),
            ("Projects", "projects"),
            ("Packages", "packages"),
            ("Settings", "settings")
        ]
        
        for label, tab_id in menu_items:
            container, stripe, btn = self.create_sidebar_button(label, tab_id)
            sidebar_layout.addWidget(container)
            self.menu_buttons[tab_id] = (container, stripe, btn)
            
        sidebar_layout.addStretch()
        
        # System Stats bottom panel
        stats_container = QWidget()
        stats_layout = QVBoxLayout(stats_container)
        stats_layout.setContentsMargins(20, 10, 20, 10)
        stats_layout.setSpacing(8)
        
        title_stats = QLabel("SYSTEM METRICS")
        title_stats.setStyleSheet("font-size: 11px; font-weight: bold; color: #64748b;")
        stats_layout.addWidget(title_stats)
        
        self.cpu_widget, self.cpu_bar, self.cpu_val = self.create_flat_progressbar("CPU", "#3b82f6")
        stats_layout.addWidget(self.cpu_widget)
        
        self.ram_widget, self.ram_bar, self.ram_val = self.create_flat_progressbar("RAM", "#8b5cf6")
        stats_layout.addWidget(self.ram_widget)
        
        self.disk_widget, self.disk_bar, self.disk_val = self.create_flat_progressbar("DISK", "#f59e0b")
        stats_layout.addWidget(self.disk_widget)
        
        sidebar_layout.addWidget(stats_container)
        
        main_layout.addWidget(self.sidebar)
        
        # Main stacked work area
        self.work_area = QStackedWidget()
        self.work_area.setStyleSheet("background-color: #0f172a; border: none;")
        
        self.tabs = {}
        self.create_dashboard_tab()
        self.create_config_tab()
        self.create_logs_tab()
        self.create_extensions_tab()
        self.create_db_tab()
        self.create_projects_tab()
        self.create_packages_tab()
        self.create_settings_tab()
        
        main_layout.addWidget(self.work_area, 1)
        
        # Show default tab
        self.show_tab("dashboard")

    def create_sidebar_button(self, label, tab_id):
        container = QWidget()
        container.setObjectName("MenuBtnContainer")
        container.setStyleSheet("QWidget#MenuBtnContainer { background-color: transparent; }")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        stripe = QFrame()
        stripe.setFixedWidth(4)
        stripe.setStyleSheet("background-color: transparent;")
        layout.addWidget(stripe)
        
        btn = QPushButton(label)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setCheckable(True)
        btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #94a3b8;
                font-weight: bold;
                font-size: 13px;
                text-align: left;
                padding: 10px 15px 10px 20px;
                border: none;
            }
            QPushButton:hover {
                color: #f8fafc;
            }
        """)
        btn.clicked.connect(lambda: self.show_tab(tab_id))
        layout.addWidget(btn)
        
        return container, stripe, btn

    def create_flat_progressbar(self, name, progress_color):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(3)
        
        lbl_layout = QHBoxLayout()
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet("font-size: 12px; font-weight: bold; color: #94a3b8;")
        lbl_layout.addWidget(name_lbl)
        
        val_lbl = QLabel("0%")
        val_lbl.setStyleSheet("font-size: 12px; font-weight: bold; color: #64748b;")
        lbl_layout.addWidget(val_lbl)
        
        layout.addLayout(lbl_layout)
        
        pbar = QProgressBar()
        pbar.setRange(0, 100)
        pbar.setValue(0)
        pbar.setTextVisible(False)
        pbar.setFixedHeight(6)
        pbar.setStyleSheet(f"""
            QProgressBar {{
                background-color: #334155;
                border-radius: 3px;
                border: none;
            }}
            QProgressBar::chunk {{
                background-color: {progress_color};
                border-radius: 3px;
            }}
        """)
        layout.addWidget(pbar)
        
        return widget, pbar, val_lbl

    def show_tab(self, tab_id):
        self.current_tab = tab_id
        
        # Reset all menu styling
        for tid, (container, stripe, btn) in self.menu_buttons.items():
            if tid == tab_id:
                btn.setChecked(True)
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #0f172a;
                        color: #3b82f6;
                        font-weight: bold;
                        font-size: 13px;
                        text-align: left;
                        padding: 10px 15px 10px 20px;
                        border: none;
                    }
                """)
                stripe.setStyleSheet("background-color: #3b82f6;")
                container.setStyleSheet("background-color: #0f172a;")
            else:
                btn.setChecked(False)
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: transparent;
                        color: #94a3b8;
                        font-weight: bold;
                        font-size: 13px;
                        text-align: left;
                        padding: 10px 15px 10px 20px;
                        border: none;
                    }
                    QPushButton:hover {
                        color: #f8fafc;
                    }
                """)
                stripe.setStyleSheet("background-color: transparent;")
                container.setStyleSheet("background-color: transparent;")
                
        # Show selected tab
        self.work_area.setCurrentWidget(self.tabs[tab_id])
        
        # Tab specific updates
        if tab_id == "extensions":
            self.load_extensions_list()
        elif tab_id == "projects":
            self.load_projects_list()

    # ==================== DASHBOARD TAB ====================
    def create_dashboard_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(20)
        
        # Header Row
        hdr_row = QHBoxLayout()
        title_lbl = QLabel("Dashboard")
        title_lbl.setStyleSheet("font-size: 24px; font-weight: bold; color: #f8fafc;")
        hdr_row.addWidget(title_lbl)
        
        hdr_row.addStretch()
        
        # Web server segmented switch
        self.switch_frame = QFrame()
        self.switch_frame.setStyleSheet("""
            QFrame {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
            }
        """)
        switch_layout = QHBoxLayout(self.switch_frame)
        switch_layout.setContentsMargins(3, 3, 3, 3)
        switch_layout.setSpacing(2)
        
        self.btn_nginx_toggle = QPushButton("Nginx Server")
        self.btn_nginx_toggle.setCursor(Qt.PointingHandCursor)
        self.btn_nginx_toggle.setFixedSize(110, 30)
        
        self.btn_apache_toggle = QPushButton("Apache Server")
        self.btn_apache_toggle.setCursor(Qt.PointingHandCursor)
        self.btn_apache_toggle.setFixedSize(110, 30)
        
        self.btn_nginx_toggle.clicked.connect(lambda: self.switch_active_server('nginx'))
        self.btn_apache_toggle.clicked.connect(lambda: self.switch_active_server('apache'))
        
        switch_layout.addWidget(self.btn_nginx_toggle)
        switch_layout.addWidget(self.btn_apache_toggle)
        
        hdr_row.addWidget(self.switch_frame)
        layout.addLayout(hdr_row)
        
        # Quick Actions Row
        actions_row = QHBoxLayout()
        btn_start_all = QPushButton("▶  Start All Services")
        btn_start_all.setCursor(Qt.PointingHandCursor)
        btn_start_all.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                font-weight: bold;
                font-size: 13px;
                padding: 8px 18px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        btn_start_all.clicked.connect(self.start_all_services)
        actions_row.addWidget(btn_start_all)
        
        btn_stop_all = QPushButton("■  Stop All Services")
        btn_stop_all.setCursor(Qt.PointingHandCursor)
        btn_stop_all.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                color: white;
                font-weight: bold;
                font-size: 13px;
                padding: 8px 18px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #dc2626;
            }
        """)
        btn_stop_all.clicked.connect(self.stop_all_services)
        actions_row.addWidget(btn_stop_all)
        
        actions_row.addStretch()
        
        self.status_bar = QLabel("Status: Server operational")
        self.status_bar.setStyleSheet("font-size: 12px; font-weight: bold; color: #64748b; padding-right: 5px;")
        actions_row.addWidget(self.status_bar)
        
        layout.addLayout(actions_row)
        
        # Grid of Cards
        grid_widget = QWidget()
        grid_layout = QGridLayout(grid_widget)
        grid_layout.setContentsMargins(0, 5, 0, 0)
        grid_layout.setSpacing(15)
        
        self.service_cards = {}
        self.service_cards['nginx'] = ServiceCard('nginx', "Nginx Server", f"Web Server · Port {PORTS['nginx']}", "#10b981", parent=self)
        self.service_cards['apache'] = ServiceCard('apache', "Apache Server", f"Web Server · Port {PORTS['apache']}", "#f59e0b", parent=self)
        self.service_cards['mysql'] = ServiceCard('mysql', "MariaDB Server", f"Database Engine · Port {PORTS['mysql']}", "#3b82f6", parent=self)
        self.service_cards['php'] = ServiceCard('php', "PHP FastCGI", f"Processor · Port {PORTS['php']}", "#8b5cf6", has_select=True, parent=self)
        
        grid_layout.addWidget(self.service_cards['nginx'], 0, 0)
        grid_layout.addWidget(self.service_cards['apache'], 0, 1)
        grid_layout.addWidget(self.service_cards['mysql'], 1, 0)
        grid_layout.addWidget(self.service_cards['php'], 1, 1)
        
        layout.addWidget(grid_widget, 1)
        
        # Initialize switch UI state
        self.update_webserver_ui()
        
        # Connect service cards buttons
        for name, card in self.service_cards.items():
            card.btn.clicked.connect(lambda checked, n=name: self.toggle_service(n))
            if name == 'php':
                card.combobox.addItems(self.php_versions)
                if self.active_php_version in self.php_versions:
                    card.combobox.setCurrentText(self.active_php_version)
                else:
                    if self.php_versions:
                        card.combobox.setCurrentText(self.php_versions[0])
                card.combobox.currentTextChanged.connect(self.change_php_version)
                
        self.tabs["dashboard"] = page
        self.work_area.addWidget(page)

    def update_webserver_ui(self):
        if self.active_web_server == "nginx":
            self.btn_nginx_toggle.setStyleSheet("""
                QPushButton {
                    background-color: #3b82f6;
                    color: #ffffff;
                    font-weight: bold;
                    font-size: 12px;
                    border-radius: 4px;
                    border: none;
                }
            """)
            self.btn_apache_toggle.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #94a3b8;
                    font-weight: bold;
                    font-size: 12px;
                    border-radius: 4px;
                    border: none;
                }
                QPushButton:hover {
                    color: #f8fafc;
                }
            """)
        else:
            self.btn_nginx_toggle.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #94a3b8;
                    font-weight: bold;
                    font-size: 12px;
                    border-radius: 4px;
                    border: none;
                }
                QPushButton:hover {
                    color: #f8fafc;
                }
            """)
            self.btn_apache_toggle.setStyleSheet("""
                QPushButton {
                    background-color: #3b82f6;
                    color: #ffffff;
                    font-weight: bold;
                    font-size: 12px;
                    border-radius: 4px;
                    border: none;
                }
            """)

    def switch_active_server(self, server_type):
        if self.active_web_server == server_type:
            return
        
        self.active_web_server = server_type
        self.update_webserver_ui()
        
        def transition():
            self.status_bar_msg.emit(f"Switching web server to {server_type.upper()}...")
            if server_type == "nginx":
                stop_service_internal("apache")
                start_service_internal("nginx", self.active_php_version)
            else:
                stop_service_internal("nginx")
                start_service_internal("apache", self.active_php_version)
            self.status_bar_msg.emit("Web server switched.")
            
        threading.Thread(target=transition, daemon=True).start()

    def toggle_service(self, svc_id):
        status, _, _ = get_service_status(svc_id)
        
        def run_toggle():
            self.status_bar_msg.emit(f"Toggling {svc_id.upper()}...")
            if status == "running":
                stop_service_internal(svc_id)
                self.status_bar_msg.emit(f"{svc_id.upper()} stopped.")
            else:
                ok, err = start_service_internal(svc_id, self.active_php_version)
                if ok:
                    self.status_bar_msg.emit(f"{svc_id.upper()} started.")
                else:
                    self.message_box.emit("error", "Service Error", f"Failed to start {svc_id}: {err}")
                    self.status_bar_msg.emit(f"Failed to start {svc_id.upper()}.")
                    
        threading.Thread(target=run_toggle, daemon=True).start()

    def change_php_version(self, new_version):
        if new_version == self.active_php_version:
            return
            
        self.active_php_version = new_version
        
        def perform_version_change():
            self.status_bar_msg.emit(f"Switching PHP version to {new_version}...")
            pids = load_pids()
            pids['php_version'] = new_version
            save_pids(pids)
            
            php_status, _, _ = get_service_status('php')
            if php_status == 'running':
                stop_service_internal('php')
                start_php_internal(new_version)
                
            self.status_bar_msg.emit(f"PHP version switched to {new_version}.")
            
        threading.Thread(target=perform_version_change, daemon=True).start()

    def start_all_services(self):
        def action():
            self.status_bar_msg.emit("Starting all configured services...")
            start_service_internal("mysql")
            start_service_internal(self.active_web_server, self.active_php_version)
            self.status_bar_msg.emit("All services running.")
            
        threading.Thread(target=action, daemon=True).start()

    def stop_all_services(self):
        def action():
            self.status_bar_msg.emit("Stopping all configured services...")
            for s in ['nginx', 'apache', 'mysql', 'php']:
                stop_service_internal(s)
            self.status_bar_msg.emit("All services stopped.")
            
        threading.Thread(target=action, daemon=True).start()

    def set_status_bar(self, msg):
        self.status_bar.setText(f"Status: {msg}")

    # ==================== CONFIG EDITOR TAB ====================
    def create_config_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(15)
        
        # Header Row
        hdr_row = QHBoxLayout()
        title_lbl = QLabel("Config Editor")
        title_lbl.setStyleSheet("font-size: 22px; font-weight: bold; color: #f8fafc;")
        hdr_row.addWidget(title_lbl)
        
        hdr_row.addStretch()
        
        self.config_svc_combo = QComboBox()
        self.config_svc_combo.addItems(["php", "nginx", "apache", "mysql"])
        self.config_svc_combo.setFixedWidth(120)
        self.config_svc_combo.currentTextChanged.connect(self.load_config_content)
        hdr_row.addWidget(self.config_svc_combo)
        
        layout.addLayout(hdr_row)
        
        # Editor Text Box
        self.config_editor = QPlainTextEdit()
        self.config_editor.setFont(QFont("Consolas", 10))
        self.config_editor.setLineWrapMode(QPlainTextEdit.NoWrap)
        # Tab size setup
        self.config_editor.setTabStopDistance(QFontMetricsF(self.config_editor.font()).horizontalAdvance(' ') * 4)
        layout.addWidget(self.config_editor, 1)
        
        # Footer Action Button
        footer_row = QHBoxLayout()
        footer_row.addStretch()
        
        save_btn = QPushButton("✔  Save Configuration")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                font-weight: bold;
                font-size: 13px;
                padding: 8px 20px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        save_btn.clicked.connect(self.save_config_content)
        footer_row.addWidget(save_btn)
        
        layout.addLayout(footer_row)
        
        self.load_config_content()
        
        self.tabs["config"] = page
        self.work_area.addWidget(page)

    def load_config_content(self):
        svc = self.config_svc_combo.currentText()
        path = CONFIG_FILES[svc]
        if callable(path):
            path = path()
            
        self.config_editor.clear()
        
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                self.config_editor.setPlainText(content)
                self.set_status_bar(f"Config loaded: {os.path.basename(path)}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not read config file: {e}")
        else:
            self.config_editor.setPlainText(f"# Config file not found at: {path}")

    def save_config_content(self):
        svc = self.config_svc_combo.currentText()
        path = CONFIG_FILES[svc]
        if callable(path):
            path = path()
            
        content = self.config_editor.toPlainText()
        
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            QMessageBox.information(self, "Success", "Config file saved successfully.")
            self.set_status_bar(f"Config updated: {os.path.basename(path)}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not write config file: {e}")

    # ==================== LOGS VIEWER TAB ====================
    def create_logs_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(15)
        
        # Header Row
        hdr_row = QHBoxLayout()
        title_lbl = QLabel("Logs Viewer")
        title_lbl.setStyleSheet("font-size: 22px; font-weight: bold; color: #f8fafc;")
        hdr_row.addWidget(title_lbl)
        
        hdr_row.addStretch()
        
        self.log_svc_combo = QComboBox()
        self.log_svc_combo.addItems(["nginx", "apache", "mysql", "php"])
        self.log_svc_combo.setFixedWidth(120)
        self.log_svc_combo.currentTextChanged.connect(self.load_log_content)
        hdr_row.addWidget(self.log_svc_combo)
        
        refresh_btn = QPushButton("🔄  Refresh Logs")
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #f8fafc;
                font-weight: bold;
                font-size: 12px;
                padding: 6px 14px;
                border-radius: 6px;
                border: 1px solid #334155;
            }
            QPushButton:hover {
                background-color: #334155;
            }
        """)
        refresh_btn.clicked.connect(self.load_log_content)
        hdr_row.addWidget(refresh_btn)
        
        layout.addLayout(hdr_row)
        
        # Viewer Text box
        self.log_viewer = QPlainTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setFont(QFont("Consolas", 10))
        self.log_viewer.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.log_viewer.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e293b;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 6px;
            }
        """)
        layout.addWidget(self.log_viewer, 1)
        
        self.load_log_content()
        
        self.tabs["logs"] = page
        self.work_area.addWidget(page)

    def load_log_content(self):
        svc = self.log_svc_combo.currentText()
        
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
                    
        self.log_viewer.setPlainText(logs_content if found_path else "No log records found for this service.")
        if found_path:
            self.set_status_bar(f"Loaded logs: {os.path.basename(found_path)}")
        else:
            self.set_status_bar("No logs found.")

    # ==================== PHP EXTENSIONS TAB ====================
    def create_extensions_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(5)
        
        title_lbl = QLabel("PHP Extensions Manager")
        title_lbl.setStyleSheet("font-size: 22px; font-weight: bold; color: #f8fafc;")
        layout.addWidget(title_lbl)
        
        desc_lbl = QLabel("Toggling extensions modifies your active php.ini. Services will automatically reload.")
        desc_lbl.setStyleSheet("font-size: 12px; font-weight: bold; color: #64748b; padding-bottom: 15px;")
        layout.addWidget(desc_lbl)
        
        # Scroll Area for Extensions
        self.ext_scroll = QScrollArea()
        self.ext_scroll.setWidgetResizable(True)
        self.ext_scroll.setStyleSheet("""
            QScrollArea {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 8px;
            }
        """)
        
        self.ext_scroll_content = QWidget()
        self.ext_scroll_content.setStyleSheet("background-color: transparent;")
        self.ext_layout = QVBoxLayout(self.ext_scroll_content)
        self.ext_layout.setContentsMargins(15, 15, 15, 15)
        self.ext_layout.setSpacing(10)
        
        self.ext_scroll.setWidget(self.ext_scroll_content)
        layout.addWidget(self.ext_scroll, 1)
        
        self.tabs["extensions"] = page
        self.work_area.addWidget(page)

    def load_extensions_list(self):
        # Show loading message
        for i in reversed(range(self.ext_layout.count())):
            widget = self.ext_layout.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()
                
        loading = QLabel("Loading php extensions...")
        loading.setStyleSheet("font-size: 13px; color: #64748b; font-weight: bold; margin: 20px;")
        self.ext_layout.addWidget(loading)
        
        def run_load():
            exts = get_php_extensions_list()
            self.extensions_loaded.emit(exts)
            
        threading.Thread(target=run_load, daemon=True).start()

    def display_extensions_list(self, extensions):
        # Clear loading label
        for i in reversed(range(self.ext_layout.count())):
            widget = self.ext_layout.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()
                
        if not extensions:
            no_ext = QLabel("No extensions parsed from php.ini")
            no_ext.setStyleSheet("font-size: 13px; color: #64748b; font-weight: bold; margin: 20px;")
            self.ext_layout.addWidget(no_ext)
            return
            
        grid = QWidget()
        grid.setStyleSheet("background-color: transparent;")
        grid_layout = QGridLayout(grid)
        grid_layout.setContentsMargins(10, 10, 10, 10)
        grid_layout.setSpacing(15)
        
        self.ext_checkboxes = {}
        for idx, ext in enumerate(extensions):
            row = idx // 2
            col = idx % 2
            
            cb = QCheckBox(f"  {ext['name']} ({ext['type']})")
            cb.setChecked(ext['enabled'])
            cb.setStyleSheet("QCheckBox { font-size: 13px; color: #f8fafc; } QCheckBox:hover { color: white; }")
            # Bind event click AFTER setting checked state
            cb.toggled.connect(lambda checked, name=ext['name']: self.toggle_extension(name, checked))
            grid_layout.addWidget(cb, row, col)
            self.ext_checkboxes[ext['name']] = cb
            
        self.ext_layout.addWidget(grid)
        self.ext_layout.addStretch()

    def toggle_extension(self, name, enable):
        def run_toggle():
            self.status_bar_msg.emit(f"Toggling extension {name}...")
            ok, err = toggle_php_extension_in_ini(name, enable)
            if ok:
                php_status, _, _ = get_service_status('php')
                if php_status == 'running':
                    stop_service_internal('php')
                    start_php_internal(self.active_php_version)
                self.status_bar_msg.emit(f"Extension {name} updated.")
            else:
                self.message_box.emit("error", "Error", f"Failed to modify php.ini: {err}")
                self.status_bar_msg.emit("Failed to update extension.")
                
        threading.Thread(target=run_toggle, daemon=True).start()

    # ==================== DB MANAGER TAB ====================
    def create_db_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(20)
        
        # Header Row
        hdr_row = QHBoxLayout()
        title_lbl = QLabel("Database Manager")
        title_lbl.setStyleSheet("font-size: 22px; font-weight: bold; color: #f8fafc;")
        hdr_row.addWidget(title_lbl)
        
        hdr_row.addStretch()
        
        pma_btn = QPushButton("🌐  Open phpMyAdmin")
        pma_btn.setCursor(Qt.PointingHandCursor)
        pma_btn.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                font-weight: bold;
                font-size: 12px;
                padding: 6px 14px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        pma_btn.clicked.connect(self.open_phpmyadmin)
        hdr_row.addWidget(pma_btn)
        
        layout.addLayout(hdr_row)
        
        # Columns Layout
        cols_layout = QHBoxLayout()
        cols_layout.setSpacing(20)
        
        # Left Panel (Update Passwords)
        p1 = QFrame()
        p1.setStyleSheet("QFrame { background-color: #1e293b; border: 1px solid #334155; border-radius: 8px; }")
        p1_layout = QVBoxLayout(p1)
        p1_layout.setContentsMargins(25, 25, 25, 25)
        p1_layout.setSpacing(12)
        
        p1_title = QLabel("Set root Password")
        p1_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #f8fafc; border: none; background-color: transparent;")
        p1_layout.addWidget(p1_title)
        
        p1_desc = QLabel("Direct password manipulation for the DB administrator account.")
        p1_desc.setWordWrap(True)
        p1_desc.setStyleSheet("font-size: 12px; color: #64748b; border: none; background-color: transparent; padding-bottom: 10px;")
        p1_layout.addWidget(p1_desc)
        
        lbl_pass = QLabel("New Password")
        lbl_pass.setStyleSheet("font-size: 13px; font-weight: bold; color: #94a3b8; border: none; background-color: transparent;")
        p1_layout.addWidget(lbl_pass)
        
        self.db_root_pass = QLineEdit()
        self.db_root_pass.setEchoMode(QLineEdit.Password)
        self.db_root_pass.setStyleSheet("background-color: #0f172a; padding: 8px;")
        p1_layout.addWidget(self.db_root_pass)
        
        p1_layout.addSpacing(10)
        
        btn_update_pass = QPushButton("🔑  Update Root Password")
        btn_update_pass.setCursor(Qt.PointingHandCursor)
        btn_update_pass.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                font-weight: bold;
                font-size: 13px;
                padding: 8px 16px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        btn_update_pass.clicked.connect(self.update_root_db_pass)
        p1_layout.addWidget(btn_update_pass)
        p1_layout.addStretch()
        
        cols_layout.addWidget(p1, 1)
        
        # Right Panel (Create DB and User)
        p2 = QFrame()
        p2.setStyleSheet("QFrame { background-color: #1e293b; border: 1px solid #334155; border-radius: 8px; }")
        p2_layout = QVBoxLayout(p2)
        p2_layout.setContentsMargins(25, 25, 25, 25)
        p2_layout.setSpacing(10)
        
        p2_title = QLabel("Create DB & User")
        p2_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #f8fafc; border: none; background-color: transparent;")
        p2_layout.addWidget(p2_title)
        
        p2_desc = QLabel("Generates a user role and schema databases in a single command.")
        p2_desc.setWordWrap(True)
        p2_desc.setStyleSheet("font-size: 12px; color: #64748b; border: none; background-color: transparent; padding-bottom: 5px;")
        p2_layout.addWidget(p2_desc)
        
        lbl_new_user = QLabel("Username")
        lbl_new_user.setStyleSheet("font-size: 12px; font-weight: bold; color: #94a3b8; border: none; background-color: transparent;")
        p2_layout.addWidget(lbl_new_user)
        
        self.db_new_user = QLineEdit()
        self.db_new_user.setStyleSheet("background-color: #0f172a; padding: 7px;")
        p2_layout.addWidget(self.db_new_user)
        
        lbl_new_pass = QLabel("Password")
        lbl_new_pass.setStyleSheet("font-size: 12px; font-weight: bold; color: #94a3b8; border: none; background-color: transparent;")
        p2_layout.addWidget(lbl_new_pass)
        
        self.db_new_pass = QLineEdit()
        self.db_new_pass.setStyleSheet("background-color: #0f172a; padding: 7px;")
        p2_layout.addWidget(self.db_new_pass)
        
        lbl_new_name = QLabel("Database Name (optional)")
        lbl_new_name.setStyleSheet("font-size: 12px; font-weight: bold; color: #94a3b8; border: none; background-color: transparent;")
        p2_layout.addWidget(lbl_new_name)
        
        self.db_new_name = QLineEdit()
        self.db_new_name.setStyleSheet("background-color: #0f172a; padding: 7px;")
        p2_layout.addWidget(self.db_new_name)
        
        p2_layout.addSpacing(10)
        
        btn_create_schema = QPushButton("➕  Create Schema & User")
        btn_create_schema.setCursor(Qt.PointingHandCursor)
        btn_create_schema.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                font-weight: bold;
                font-size: 13px;
                padding: 8px 16px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        btn_create_schema.clicked.connect(self.create_db_and_user)
        p2_layout.addWidget(btn_create_schema)
        
        cols_layout.addWidget(p2, 1)
        
        layout.addLayout(cols_layout, 1)
        
        self.tabs["db"] = page
        self.work_area.addWidget(page)

    def open_phpmyadmin(self):
        port = PORTS[self.active_web_server]
        url = f"http://localhost:{port}/phpmyadmin" if port != 80 else "http://localhost/phpmyadmin"
        webbrowser.open(url)

    def update_root_db_pass(self):
        new_pass = self.db_root_pass.text().strip()
        if not new_pass:
            QMessageBox.warning(self, "Warning", "Password cannot be empty!")
            return
            
        status, _, _ = get_service_status('mysql')
        if status != 'running':
            QMessageBox.critical(self, "Error", "MariaDB service must be active to modify credentials.")
            return
            
        def perform():
            self.status_bar_msg.emit("Updating MariaDB root credentials...")
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
                    
                self.message_box.emit("info", "Success", "MariaDB root credentials updated successfully.")
                self.status_bar_msg.emit("Root password changed.")
                QMetaObject.invokeMethod(self.db_root_pass, "clear", Qt.QueuedConnection)
            else:
                self.message_box.emit("error", "SQL Error", f"Query failed: {error_msg}")
                self.status_bar_msg.emit("Failed root pass alteration.")
                
        threading.Thread(target=perform, daemon=True).start()

    def create_db_and_user(self):
        user = self.db_new_user.text().strip()
        pwd = self.db_new_pass.text().strip()
        dbname = self.db_new_name.text().strip()
        
        if not user or not pwd:
            QMessageBox.warning(self, "Warning", "Username and Password fields are mandatory.")
            return
            
        status, _, _ = get_service_status('mysql')
        if status != 'running':
            QMessageBox.critical(self, "Error", "MariaDB service must be active to create schemas.")
            return
            
        def perform():
            self.status_bar_msg.emit("Generating SQL privileges...")
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
                self.message_box.emit("info", "Success", f"Database + User '{user}' initialized.")
                self.status_bar_msg.emit(f"Created Database user '{user}'.")
                QMetaObject.invokeMethod(self.db_new_user, "clear", Qt.QueuedConnection)
                QMetaObject.invokeMethod(self.db_new_pass, "clear", Qt.QueuedConnection)
                QMetaObject.invokeMethod(self.db_new_name, "clear", Qt.QueuedConnection)
            else:
                self.message_box.emit("error", "SQL Execution Error", f"Query failed: {error_msg}")
                self.status_bar_msg.emit("Failed schema generation.")
                
        threading.Thread(target=perform, daemon=True).start()

    # ==================== PROJECTS TAB ====================
    def create_projects_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(15)
        
        # Header Row
        hdr_row = QHBoxLayout()
        title_lbl = QLabel("Local Projects")
        title_lbl.setStyleSheet("font-size: 22px; font-weight: bold; color: #f8fafc;")
        hdr_row.addWidget(title_lbl)
        
        hdr_row.addStretch()
        
        open_dir_btn = QPushButton("📁  Open www/ directory")
        open_dir_btn.setCursor(Qt.PointingHandCursor)
        open_dir_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #f8fafc;
                font-weight: bold;
                font-size: 12px;
                padding: 6px 14px;
                border-radius: 6px;
                border: 1px solid #334155;
            }
            QPushButton:hover {
                background-color: #334155;
            }
        """)
        open_dir_btn.clicked.connect(lambda: os.startfile(WWW_DIR))
        hdr_row.addWidget(open_dir_btn)
        
        layout.addLayout(hdr_row)
        
        # Search Filter Bar
        search_frame = QFrame()
        search_frame.setStyleSheet("""
            QFrame {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
            }
        """)
        search_layout = QHBoxLayout(search_frame)
        search_layout.setContentsMargins(10, 2, 10, 2)
        search_layout.setSpacing(8)
        
        search_icon = QLabel("🔍")
        search_icon.setStyleSheet("font-size: 14px; border: none; background-color: transparent;")
        search_layout.addWidget(search_icon)
        
        self.project_search = QLineEdit()
        self.project_search.setPlaceholderText("Search local projects...")
        self.project_search.setStyleSheet("background-color: transparent; border: none; padding: 8px 0px;")
        self.project_search.textChanged.connect(self.filter_projects)
        search_layout.addWidget(self.project_search)
        
        layout.addWidget(search_frame)
        
        # Scroll Area for Projects List
        self.proj_scroll = QScrollArea()
        self.proj_scroll.setWidgetResizable(True)
        self.proj_scroll.setStyleSheet("""
            QScrollArea {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 8px;
            }
        """)
        
        self.proj_scroll_content = QWidget()
        self.proj_scroll_content.setStyleSheet("background-color: transparent;")
        self.proj_layout = QVBoxLayout(self.proj_scroll_content)
        self.proj_layout.setContentsMargins(10, 10, 10, 10)
        self.proj_layout.setSpacing(5)
        
        self.proj_scroll.setWidget(self.proj_scroll_content)
        layout.addWidget(self.proj_scroll, 1)
        
        self.all_projects = []
        
        self.tabs["projects"] = page
        self.work_area.addWidget(page)

    def load_projects_list(self):
        for i in reversed(range(self.proj_layout.count())):
            widget = self.proj_layout.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()
                
        loading = QLabel("Loading projects...")
        loading.setStyleSheet("font-size: 13px; color: #64748b; font-weight: bold; margin: 20px;")
        self.proj_layout.addWidget(loading)
        
        def run_load():
            all_projects = []
            if os.path.exists(WWW_DIR):
                try:
                    for item in os.listdir(WWW_DIR):
                        if os.path.isdir(os.path.join(WWW_DIR, item)):
                            all_projects.append(item)
                except Exception:
                    pass
            self.all_projects = all_projects
            self.projects_loaded.emit(self.all_projects)
            
        threading.Thread(target=run_load, daemon=True).start()

    def display_projects_list(self, all_projects):
        self.filter_projects()

    def filter_projects(self):
        query = self.project_search.text().lower()
        filtered = [p for p in self.all_projects if query in p.lower()]
        
        # Clear layout
        for i in reversed(range(self.proj_layout.count())):
            widget = self.proj_layout.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()
                
        if not filtered:
            no_proj = QLabel("No local project folders inside www/.")
            no_proj.setStyleSheet("font-size: 13px; color: #64748b; font-weight: bold; margin: 40px;")
            no_proj.setAlignment(Qt.AlignCenter)
            self.proj_layout.addWidget(no_proj)
            return
            
        for project in filtered:
            row = QFrame()
            row.setStyleSheet("background-color: transparent; border: none;")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(15, 8, 15, 8)
            
            proj_lbl = QLabel(f"📁  {project}")
            proj_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #f8fafc;")
            row_layout.addWidget(proj_lbl)
            
            row_layout.addStretch()
            
            # Action Buttons
            btn_browser = QPushButton("Open Browser")
            btn_browser.setCursor(Qt.PointingHandCursor)
            btn_browser.setStyleSheet("""
                QPushButton {
                    background-color: #3b82f6;
                    color: white;
                    font-weight: bold;
                    font-size: 11px;
                    padding: 5px 12px;
                    border-radius: 4px;
                    border: none;
                }
                QPushButton:hover {
                    background-color: #2563eb;
                }
            """)
            btn_browser.clicked.connect(lambda checked, p=project: self.open_project_in_browser(p))
            row_layout.addWidget(btn_browser)
            
            btn_folder = QPushButton("Open Folder")
            btn_folder.setCursor(Qt.PointingHandCursor)
            btn_folder.setStyleSheet("""
                QPushButton {
                    background-color: #0f172a;
                    color: #94a3b8;
                    font-weight: bold;
                    font-size: 11px;
                    padding: 5px 12px;
                    border-radius: 4px;
                    border: 1px solid #334155;
                }
                QPushButton:hover {
                    color: #f8fafc;
                    background-color: #1e293b;
                }
            """)
            btn_folder.clicked.connect(lambda checked, p=project: os.startfile(os.path.join(WWW_DIR, p)))
            row_layout.addWidget(btn_folder)
            
            self.proj_layout.addWidget(row)
            
            # Thin divider
            divider = QFrame()
            divider.setFixedHeight(1)
            divider.setStyleSheet("background-color: #334155;")
            self.proj_layout.addWidget(divider)
            
        self.proj_layout.addStretch()

    def open_project_in_browser(self, project):
        port = PORTS[self.active_web_server]
        url = f"http://localhost:{port}/{project}" if port != 80 else f"http://localhost/{project}"
        webbrowser.open(url)

    # ==================== SETTINGS TAB ====================
    def create_settings_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(15)
        
        # Header Row
        title_lbl = QLabel("Settings")
        title_lbl.setStyleSheet("font-size: 22px; font-weight: bold; color: #f8fafc;")
        layout.addWidget(title_lbl)
        
        # Scroll Area for Form (so it scales gracefully)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background-color: transparent;")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(20)
        
        # Settings Panel Card
        panel = QFrame()
        panel.setStyleSheet("QFrame { background-color: #1e293b; border: 1px solid #334155; border-radius: 8px; }")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(25, 25, 25, 25)
        panel_layout.setSpacing(12)
        
        lbl_ports_title = QLabel("Service Ports Configuration")
        lbl_ports_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #f8fafc; border: none; background-color: transparent;")
        panel_layout.addWidget(lbl_ports_title)
        
        lbl_ports_desc = QLabel("Customize the network ports for each service. Port changes will modify configuration files automatically.")
        lbl_ports_desc.setWordWrap(True)
        lbl_ports_desc.setStyleSheet("font-size: 12px; color: #64748b; border: none; background-color: transparent; padding-bottom: 10px;")
        panel_layout.addWidget(lbl_ports_desc)
        
        # Form Layout of inputs
        form_grid = QGridLayout()
        form_grid.setSpacing(15)
        
        # Row 0: Nginx / Apache
        # Nginx
        f_nginx = QWidget()
        f_nginx.setStyleSheet("border: none; background-color: transparent;")
        fn_lay = QVBoxLayout(f_nginx)
        fn_lay.setContentsMargins(0, 0, 0, 0)
        fn_lay.setSpacing(4)
        lbl_n = QLabel("Nginx Server Port")
        lbl_n.setStyleSheet("font-size: 12px; font-weight: bold; color: #94a3b8;")
        fn_lay.addWidget(lbl_n)
        self.entry_port_nginx = QLineEdit()
        self.entry_port_nginx.setText(str(PORTS['nginx']))
        fn_lay.addWidget(self.entry_port_nginx)
        form_grid.addWidget(f_nginx, 0, 0)
        
        # Apache
        f_apache = QWidget()
        f_apache.setStyleSheet("border: none; background-color: transparent;")
        fa_lay = QVBoxLayout(f_apache)
        fa_lay.setContentsMargins(0, 0, 0, 0)
        fa_lay.setSpacing(4)
        lbl_a = QLabel("Apache Server Port")
        lbl_a.setStyleSheet("font-size: 12px; font-weight: bold; color: #94a3b8;")
        fa_lay.addWidget(lbl_a)
        self.entry_port_apache = QLineEdit()
        self.entry_port_apache.setText(str(PORTS['apache']))
        fa_lay.addWidget(self.entry_port_apache)
        form_grid.addWidget(f_apache, 0, 1)
        
        # Row 1: MySQL / PHP
        # MySQL
        f_mysql = QWidget()
        f_mysql.setStyleSheet("border: none; background-color: transparent;")
        fm_lay = QVBoxLayout(f_mysql)
        fm_lay.setContentsMargins(0, 0, 0, 0)
        fm_lay.setSpacing(4)
        lbl_m = QLabel("MariaDB Port")
        lbl_m.setStyleSheet("font-size: 12px; font-weight: bold; color: #94a3b8;")
        fm_lay.addWidget(lbl_m)
        self.entry_port_mysql = QLineEdit()
        self.entry_port_mysql.setText(str(PORTS['mysql']))
        fm_lay.addWidget(self.entry_port_mysql)
        form_grid.addWidget(f_mysql, 1, 0)
        
        # PHP
        f_php = QWidget()
        f_php.setStyleSheet("border: none; background-color: transparent;")
        fp_lay = QVBoxLayout(f_php)
        fp_lay.setContentsMargins(0, 0, 0, 0)
        fp_lay.setSpacing(4)
        lbl_p = QLabel("PHP FastCGI Port")
        lbl_p.setStyleSheet("font-size: 12px; font-weight: bold; color: #94a3b8;")
        fp_lay.addWidget(lbl_p)
        self.entry_port_php = QLineEdit()
        self.entry_port_php.setText(str(PORTS['php']))
        fp_lay.addWidget(self.entry_port_php)
        form_grid.addWidget(f_php, 1, 1)
        
        panel_layout.addLayout(form_grid)
        panel_layout.addSpacing(10)
        
        # Save button
        btn_save_ports = QPushButton("💾  Save Port Settings")
        btn_save_ports.setCursor(Qt.PointingHandCursor)
        btn_save_ports.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                font-weight: bold;
                font-size: 13px;
                padding: 8px 20px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        btn_save_ports.clicked.connect(self.save_port_settings)
        panel_layout.addWidget(btn_save_ports)
        
        # Divider Line
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background-color: #334155; border: none;")
        panel_layout.addWidget(divider)
        
        # System Integration Section
        lbl_integ_title = QLabel("System Integration")
        lbl_integ_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #f8fafc; border: none; background-color: transparent;")
        panel_layout.addWidget(lbl_integ_title)
        
        lbl_integ_desc = QLabel("Enable Windows integration features like running automatically on system startup.")
        lbl_integ_desc.setStyleSheet("font-size: 12px; color: #64748b; border: none; background-color: transparent;")
        panel_layout.addWidget(lbl_integ_desc)
        
        self.startup_checkbox = QCheckBox("🚀  Start WinPHP on Windows Startup")
        self.startup_checkbox.setChecked(is_startup_enabled())
        self.startup_checkbox.setStyleSheet("QCheckBox { font-size: 13px; color: #f8fafc; border: none; background-color: transparent; }")
        self.startup_checkbox.toggled.connect(self.toggle_startup)
        panel_layout.addWidget(self.startup_checkbox)
        
        panel_layout.addStretch()
        
        scroll_layout.addWidget(panel)
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        
        layout.addWidget(scroll, 1)
        
        self.tabs["settings"] = page
        self.work_area.addWidget(page)

    def save_port_settings(self):
        try:
            new_ports = {
                'nginx': int(self.entry_port_nginx.text().strip()),
                'apache': int(self.entry_port_apache.text().strip()),
                'mysql': int(self.entry_port_mysql.text().strip()),
                'php': int(self.entry_port_php.text().strip())
            }
        except ValueError:
            QMessageBox.critical(self, "Validation Error", "All port numbers must be valid integers.")
            return
            
        for name, port in new_ports.items():
            if port < 1 or port > 65535:
                QMessageBox.critical(self, "Validation Error", f"Port for {name.upper()} must be between 1 and 65535.")
                return
                
        # Check for real conflicts (non-mutually-exclusive services sharing ports)
        conflict_detected = False
        non_web_ports = [new_ports['mysql'], new_ports['php']]
        web_ports = [new_ports['nginx'], new_ports['apache']]
        
        if len(non_web_ports) != len(set(non_web_ports)):
            conflict_detected = True
        elif any(p in web_ports for p in non_web_ports):
            conflict_detected = True
            
        if conflict_detected:
            QMessageBox.warning(self, "Warning", "Assigning the same port to non-compatible services (like Web Server and Database/PHP) will cause conflicts.")
            
        global PORTS
        old_ports = PORTS.copy()
        PORTS.update(new_ports)
        save_ports(PORTS)
        
        def apply_changes():
            self.status_bar_msg.emit("Applying port configurations...")
            for name, port in new_ports.items():
                if port != old_ports.get(name):
                    update_service_port_in_config(name, old_ports.get(name), port)
            
            QMetaObject.invokeMethod(self, "update_service_descriptions", Qt.QueuedConnection)
            self.status_bar_msg.emit("Port configuration saved successfully.")
            self.message_box.emit("info", "Success", "Ports updated and configuration files written!\n\nPlease restart any running services for the changes to take effect.")
            
        threading.Thread(target=apply_changes, daemon=True).start()

    @Slot()
    def update_service_descriptions(self):
        descriptions = {
            "nginx": f"Web Server · Port {PORTS['nginx']}",
            "apache": f"Web Server · Port {PORTS['apache']}",
            "mysql": f"Database Engine · Port {PORTS['mysql']}",
            "php": f"Processor · Port {PORTS['php']}"
        }
        for svc_id, desc in descriptions.items():
            if svc_id in self.service_cards:
                self.service_cards[svc_id].desc_lbl.setText(desc)

    def toggle_startup(self, checked):
        try:
            set_startup(checked)
            self.set_status_bar(f"Startup {'enabled' if checked else 'disabled'}.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not change startup settings: {e}")

    # ==================== PACKAGES TAB ====================
    def create_packages_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(15)
        
        # Header Row
        title_lbl = QLabel("Package Manager")
        title_lbl.setStyleSheet("font-size: 22px; font-weight: bold; color: #f8fafc;")
        layout.addWidget(title_lbl)
        
        # Scroll Area for Cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background-color: transparent;")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(15)
        
        # Add a card for each package type
        self.package_cards = {}
        
        # PHP Card
        self.package_cards['php'] = PackageCard(
            'php',
            "PHP FastCGI Processor",
            "FastCGI process manager for running PHP scripts.",
            AVAILABLE_VERSIONS['php'],
            "#8b5cf6",
            self
        )
        scroll_layout.addWidget(self.package_cards['php'])
        
        # Nginx Card
        self.package_cards['nginx'] = PackageCard(
            'nginx',
            "Nginx Web Server",
            "Lightweight, high-performance HTTP web server.",
            AVAILABLE_VERSIONS['nginx'],
            "#10b981",
            self
        )
        scroll_layout.addWidget(self.package_cards['nginx'])
        
        # Apache Card
        self.package_cards['apache'] = PackageCard(
            'apache',
            "Apache HTTP Server",
            "Robust and modular open-source web server.",
            AVAILABLE_VERSIONS['apache'],
            "#ef4444",
            self
        )
        scroll_layout.addWidget(self.package_cards['apache'])
        
        # MariaDB Card
        self.package_cards['mysql'] = PackageCard(
            'mysql',
            "MariaDB Database Server",
            "Community-developed MySQL relational database fork.",
            AVAILABLE_VERSIONS['mysql'],
            "#0284c7",
            self
        )
        scroll_layout.addWidget(self.package_cards['mysql'])
        
        # phpMyAdmin Card
        self.package_cards['phpmyadmin'] = PackageCard(
            'phpmyadmin',
            "phpMyAdmin Database Console",
            "Web-based graphical administration tool for MariaDB/MySQL databases.",
            AVAILABLE_VERSIONS['phpmyadmin'],
            "#f59e0b",
            self
        )
        scroll_layout.addWidget(self.package_cards['phpmyadmin'])
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)
        
        self.tabs["packages"] = page
        self.work_area.addWidget(page)
        
    def on_package_installed(self, svc_id):
        if svc_id == 'php':
            # Refresh PHP versions list
            self.php_versions = get_php_versions()
            
            # Find the card and recreate combobox items in Dashboard
            if 'php' in self.service_cards:
                php_card = self.service_cards['php']
                php_card.combobox.blockSignals(True)
                php_card.combobox.clear()
                php_card.combobox.addItems(self.php_versions)
                
                # Make the newly installed version active if we don't have one active
                active = get_current_php_version()
                if active in self.php_versions:
                    php_card.combobox.setCurrentText(active)
                else:
                    if self.php_versions:
                        php_card.combobox.setCurrentText(self.php_versions[0])
                        pids = load_pids()
                        pids['php_version'] = self.php_versions[0]
                        save_pids(pids)
                        self.active_php_version = self.php_versions[0]
                php_card.combobox.blockSignals(False)
                
        # Refresh status of all package cards
        for card in self.package_cards.values():
            card.refresh_status()

    # ==================== WORKER EMISSION SLOTS ====================
    @Slot(dict)
    def on_status_updated(self, statuses):
        for name, (status, pid, memory) in statuses.items():
            if name not in self.service_cards:
                continue
            card = self.service_cards[name]
            if status == "running":
                card.status_dot.setStyleSheet("background-color: #10b981; border-radius: 5px;")
                card.status_lbl.setText("Running")
                card.status_lbl.setStyleSheet("font-size: 12px; font-weight: bold; color: #10b981; background-color: transparent;")
                card.mem_lbl.setText(f"{memory} MB")
                card.btn.setText("Stop")
                card.btn.setStyleSheet("""
                    QPushButton {
                        background-color: #ef4444;
                        color: white;
                        font-weight: bold;
                        font-size: 12px;
                        border-radius: 6px;
                        border: none;
                    }
                    QPushButton:hover {
                        background-color: #dc2626;
                    }
                """)
            else:
                card.status_dot.setStyleSheet("background-color: #ef4444; border-radius: 5px;")
                card.status_lbl.setText("Stopped")
                card.status_lbl.setStyleSheet("font-size: 12px; font-weight: bold; color: #ef4444; background-color: transparent;")
                card.mem_lbl.setText("")
                card.btn.setText("Start")
                card.btn.setStyleSheet("""
                    QPushButton {
                        background-color: #10b981;
                        color: white;
                        font-weight: bold;
                        font-size: 12px;
                        border-radius: 6px;
                        border: none;
                    }
                    QPushButton:hover {
                        background-color: #059669;
                    }
                """)

    @Slot(dict)
    def on_metrics_updated(self, metrics):
        cpu = metrics.get('cpu', 0)
        ram = metrics.get('ram', 0)
        disk = metrics.get('disk', 0)
        
        self.cpu_bar.setValue(cpu)
        self.cpu_val.setText(f"{cpu}%")
        
        self.ram_bar.setValue(ram)
        self.ram_val.setText(f"{ram}%")
        
        self.disk_bar.setValue(disk)
        self.disk_val.setText(f"{disk}%")

    @Slot(str, str, str)
    def show_message_box_slot(self, msg_type, title, text):
        if msg_type == 'error':
            QMessageBox.critical(self, title, text)
        elif msg_type == 'warning':
            QMessageBox.warning(self, title, text)
        else:
            QMessageBox.information(self, title, text)

    # ==================== WINDOW STATE / TRAY ACTIONS ====================
    def setup_tray(self):
        icon_path = os.path.join(BASE_DIR, 'icon.ico')
        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
        else:
            # Fallback blank blue icon
            pix = QPixmap(32, 32)
            pix.fill(QColor("#3b82f6"))
            icon = QIcon(pix)
            
        self.tray_icon = QSystemTrayIcon(icon, self)
        self.tray_icon.setToolTip("WinPHP Server Manager")
        
        tray_menu = QMenu(self)
        tray_menu.setStyleSheet("""
            QMenu {
                background-color: #1e293b;
                color: #f8fafc;
                border: 1px solid #334155;
            }
            QMenu::item:selected {
                background-color: #3b82f6;
                color: #ffffff;
            }
        """)
        
        show_action = QAction("Show Control Center", self)
        show_action.triggered.connect(self.restore_window)
        tray_menu.addAction(show_action)
        
        tray_menu.addSeparator()
        
        start_action = QAction("Start All Services", self)
        start_action.triggered.connect(self.start_all_services)
        tray_menu.addAction(start_action)
        
        stop_action = QAction("Stop All Services", self)
        stop_action.triggered.connect(self.stop_all_services)
        tray_menu.addAction(stop_action)
        
        tray_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.real_exit)
        tray_menu.addAction(exit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.restore_window()

    def restore_window(self):
        self.show()
        self.setWindowState(Qt.WindowNoState)
        self.raise_()
        self.activateWindow()
        if hasattr(self, 'worker') and self.worker:
            self.worker.window_active = True

    def changeEvent(self, event):
        if event.type() == QEvent.WindowStateChange:
            if self.isMinimized():
                # Minimize to system tray
                self.hide()
                if hasattr(self, 'worker') and self.worker:
                    self.worker.window_active = False
                event.accept()
                return
            else:
                if hasattr(self, 'worker') and self.worker:
                    self.worker.window_active = True
        elif event.type() == QEvent.WindowActivate:
            if hasattr(self, 'worker') and self.worker:
                self.worker.window_active = True
        elif event.type() == QEvent.WindowDeactivate:
            if hasattr(self, 'worker') and self.worker:
                self.worker.window_active = False
        super().changeEvent(event)

    def closeEvent(self, event):
        self.real_exit()
        event.accept()

    def real_exit(self):
        # Hide tray icon
        if hasattr(self, 'tray_icon') and self.tray_icon:
            self.tray_icon.hide()
            
        # Stop worker thread
        if hasattr(self, 'worker') and self.worker:
            self.worker.stop()
            self.worker.wait()
            
        # Exiting dialog to stop services
        progress = QDialog(self)
        progress.setWindowTitle("Exiting")
        progress.setFixedSize(320, 110)
        progress.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        progress.setStyleSheet("background-color: #1e293b; color: white;")
        
        lay = QVBoxLayout(progress)
        lbl = QLabel("Shutting down background services...", progress)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("font-size: 12px; font-weight: bold; border: none; background-color: transparent;")
        lay.addWidget(lbl)
        
        progress.show()
        QApplication.processEvents()
        
        for service in ['nginx', 'apache', 'mysql', 'php']:
            try:
                stop_service_internal(service)
            except:
                pass
                
        progress.close()
        QApplication.quit()
        os._exit(0)


if __name__ == '__main__':
    pids = load_pids()
    cleaned = False
    for name, port in PORTS.items():
        if not is_port_open(port) and pids.get(name):
            pids[name] = None
            cleaned = True
    if cleaned:
        save_pids(pids)
        
    app = QApplication(sys.argv)
    
    # Custom font setup to check for Segoe UI or Outfit
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    window = WinPHPApp()
    window.show()
    
    sys.exit(app.exec())
