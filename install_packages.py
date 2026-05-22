import os
import sys
import urllib.request
import zipfile
import shutil
import subprocess

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
BIN_DIR = os.path.join(BASE_DIR, 'bin')
TOOLS_DIR = os.path.join(BASE_DIR, 'tools')
WWW_DIR = os.path.join(BASE_DIR, 'www')
DOWNLOADS_DIR = os.path.join(BASE_DIR, 'downloads')

# URLs to download
PACKAGES = {
    'php': {
        'url': 'https://windows.php.net/downloads/releases/php-8.2.31-nts-Win32-vs16-x64.zip',
        'dest': os.path.join(BIN_DIR, 'php', 'php-8.2.31-nts'),
        'type': 'zip',
        'strip_root': False
    },
    'nginx': {
        'url': 'https://nginx.org/download/nginx-1.26.3.zip',
        'dest': os.path.join(BIN_DIR, 'nginx'),
        'type': 'zip',
        'strip_root': True
    },
    'apache': {
        'url': 'https://www.apachelounge.com/download/VS18/binaries/httpd-2.4.67-260504-Win64-VS18.zip',
        'dest': os.path.join(BIN_DIR, 'apache'),
        'type': 'zip',
        'strip_root': True,
        'nested_folder': 'Apache24'
    },
    'mysql': {
        'url': 'https://downloads.mariadb.com/MariaDB/mariadb-10.11.8/winx64-packages/mariadb-10.11.8-winx64.zip',
        'dest': os.path.join(BIN_DIR, 'mysql'),
        'type': 'zip',
        'strip_root': True
    },
    'phpmyadmin': {
        'url': 'https://files.phpmyadmin.net/phpMyAdmin/5.2.3/phpMyAdmin-5.2.3-all-languages.zip',
        'dest': os.path.join(TOOLS_DIR, 'phpmyadmin'),
        'type': 'zip',
        'strip_root': True
    }
}

def report_progress(block_num, block_size, total_size):
    read_so_far = block_num * block_size
    if total_size > 0:
        percent = min(100, read_so_far * 100 / total_size)
        sys.stdout.write(f"\rDownloading... {percent:.1f}% ({read_so_far / (1024*1024):.2f}MB / {total_size / (1024*1024):.2f}MB)")
    else:
        sys.stdout.write(f"\rDownloading... ({read_so_far / (1024*1024):.2f}MB)")
    sys.stdout.flush()

def download_file(url, filepath):
    print(f"Downloading {url} to {filepath}...")
    opener = urllib.request.build_opener()
    opener.addheaders = [('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)')]
    urllib.request.install_opener(opener)
    urllib.request.urlretrieve(url, filepath, report_progress)
    print("\nDownload complete.")

def extract_zip(zip_path, dest_dir, strip_root=False, nested_folder=None):
    print(f"Extracting {zip_path} to {dest_dir}...")
    os.makedirs(dest_dir, exist_ok=True)
    
    # Extract to a temp directory first
    temp_extract = os.path.join(DOWNLOADS_DIR, 'temp_extract')
    if os.path.exists(temp_extract):
        shutil.rmtree(temp_extract)
    os.makedirs(temp_extract, exist_ok=True)
    
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(temp_extract)
        
    if strip_root:
        # Find the root folder inside zip
        contents = os.listdir(temp_extract)
        if nested_folder and nested_folder in contents:
            root_src = os.path.join(temp_extract, nested_folder)
        elif len(contents) == 1 and os.path.isdir(os.path.join(temp_extract, contents[0])):
            root_src = os.path.join(temp_extract, contents[0])
        else:
            root_src = temp_extract
            
        for item in os.listdir(root_src):
            s = os.path.join(root_src, item)
            d = os.path.join(dest_dir, item)
            if os.path.exists(d):
                if os.path.isdir(d):
                    shutil.rmtree(d)
                else:
                    os.remove(d)
            shutil.move(s, d)
    else:
        for item in os.listdir(temp_extract):
            s = os.path.join(temp_extract, item)
            d = os.path.join(dest_dir, item)
            if os.path.exists(d):
                if os.path.isdir(d):
                    shutil.rmtree(d)
                else:
                    os.remove(d)
            shutil.move(s, d)
            
    shutil.rmtree(temp_extract)
    print("Extraction complete.")

def setup_php(php_dir):
    print("Setting up PHP...")
    php_ini_dev = os.path.join(php_dir, 'php.ini-development')
    php_ini = os.path.join(php_dir, 'php.ini')
    
    if os.path.exists(php_ini_dev) and not os.path.exists(php_ini):
        with open(php_ini_dev, 'r') as f:
            content = f.read()
            
        # Enable extensions
        content = content.replace(';extension_dir = "ext"', 'extension_dir = "ext"')
        extensions = ['curl', 'mbstring', 'mysqli', 'openssl', 'pdo_mysql', 'sockets']
        for ext in extensions:
            content = content.replace(f';extension={ext}', f'extension={ext}')
            
        with open(php_ini, 'w') as f:
            f.write(content)
        print("PHP php.ini generated successfully.")

def setup_nginx():
    print("Setting up Nginx...")
    nginx_conf = os.path.join(BIN_DIR, 'nginx', 'conf', 'nginx.conf')
    
    # Use forward slashes for Nginx paths
    www_path = WWW_DIR.replace('\\', '/')
    phpmyadmin_path = os.path.join(TOOLS_DIR, 'phpmyadmin').replace('\\', '/')
    
    conf_content = f"""
worker_processes  1;

events {{
    worker_connections  1024;
}}

http {{
    include       mime.types;
    default_type  application/octet-stream;
    sendfile        on;
    keepalive_timeout  65;

    server {{
        listen       80;
        server_name  localhost;

        root         "{www_path}";
        index        index.php index.html index.htm;

        location / {{
            try_files $uri $uri/ =404;
        }}

        location ~ \\.php$ {{
            fastcgi_pass   127.0.0.1:9000;
            fastcgi_index  index.php;
            fastcgi_param  SCRIPT_FILENAME  $document_root$fastcgi_script_name;
            include        fastcgi_params;
        }}

        location /phpmyadmin {{
            alias "{phpmyadmin_path}/";
            index index.php index.html;
            
            location ~ \\.php$ {{
                fastcgi_pass   127.0.0.1:9000;
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
    print("Nginx configuration written.")

def setup_apache():
    print("Setting up Apache...")
    apache_dir = os.path.join(BIN_DIR, 'apache')
    httpd_conf = os.path.join(apache_dir, 'conf', 'httpd.conf')
    
    if os.path.exists(httpd_conf):
        with open(httpd_conf, 'r') as f:
            content = f.read()
            
        # Replace SRVROOT (handling drive letter case variations)
        apache_path_esc = apache_dir.replace('\\', '/')
        content = content.replace('Define SRVROOT "C:/Apache24"', f'Define SRVROOT "{apache_path_esc}"')
        content = content.replace('Define SRVROOT "c:/Apache24"', f'Define SRVROOT "{apache_path_esc}"')
        
        # Change listen port from 80 to 8080 (or keep 80 if wanted, let's use 8080 to avoid Nginx conflicts)
        content = content.replace('Listen 80', 'Listen 8080')
        
        # Change DocumentRoot
        www_path_esc = WWW_DIR.replace('\\', '/')
        old_docroot = 'DocumentRoot "${SRVROOT}/htdocs"'
        new_docroot = f'DocumentRoot "{www_path_esc}"'
        content = content.replace(old_docroot, new_docroot)
        
        old_dir = '<Directory "${SRVROOT}/htdocs">'
        new_dir = f'<Directory "{www_path_esc}">'
        content = content.replace(old_dir, new_dir)
        
        # Add index.php to DirectoryIndex
        content = content.replace('DirectoryIndex index.html', 'DirectoryIndex index.php index.html')
        
        # Add proxy fcgi modules and PHP proxy handler if not present
        if 'proxy_fcgi_module' not in content:
            # Enable proxy modules
            content = content.replace('#LoadModule proxy_module modules/mod_proxy.so', 'LoadModule proxy_module modules/mod_proxy.so')
            content = content.replace('#LoadModule proxy_fcgi_module modules/mod_proxy_fcgi.so', 'LoadModule proxy_fcgi_module modules/mod_proxy_fcgi.so')
            
            phpmyadmin_path_esc = os.path.join(TOOLS_DIR, 'phpmyadmin').replace('\\', '/')
            php_proxy_setup = f"""
# PHP FastCGI proxy setup
<FilesMatch \\.php$>
    SetHandler "proxy:fcgi://127.0.0.1:9000"
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
        print("Apache configuration updated.")

def setup_mysql():
    print("Setting up MariaDB...")
    mysql_dir = os.path.join(BIN_DIR, 'mysql')
    my_ini = os.path.join(mysql_dir, 'my.ini')
    
    mysql_dir_esc = mysql_dir.replace('\\', '/')
    data_dir_esc = os.path.join(mysql_dir, 'data').replace('\\', '/')
    
    ini_content = f"""[mysqld]
port=3306
basedir="{mysql_dir_esc}"
datadir="{data_dir_esc}"
bind-address=127.0.0.1
sql_mode=NO_ENGINE_SUBSTITUTION
max_allowed_packet=64M
default-storage-engine=INNODB
"""
    with open(my_ini, 'w') as f:
        f.write(ini_content)
    print("MariaDB my.ini written.")
    
    # Initialize MariaDB Data Directory
    data_dir = os.path.join(mysql_dir, 'data')
    if not os.path.exists(data_dir):
        print("Initializing MariaDB database...")
        install_db_exe = os.path.join(mysql_dir, 'bin', 'mysql_install_db.exe')
        if os.path.exists(install_db_exe):
            cmd = [install_db_exe, f'--datadir={data_dir}']
            print(f"Running: {' '.join(cmd)}")
            subprocess.run(cmd, shell=True)
            print("Database initialized.")
        else:
            print("Warning: mysql_install_db.exe not found. Database initialization skipped.")

def setup_phpmyadmin():
    print("Setting up phpMyAdmin...")
    pma_dir = os.path.join(TOOLS_DIR, 'phpmyadmin')
    config_sample = os.path.join(pma_dir, 'config.sample.inc.php')
    config_inc = os.path.join(pma_dir, 'config.inc.php')
    
    if os.path.exists(config_sample) and not os.path.exists(config_inc):
        with open(config_sample, 'r') as f:
            content = f.read()
            
        # Quick configuration for password-less root access on localhost
        content = content.replace("['AllowNoPassword'] = false;", "['AllowNoPassword'] = true;")
        content = content.replace("['auth_type'] = 'cookie';", "['auth_type'] = 'config';")
        content = content.replace("['host'] = 'localhost';", "['host'] = '127.0.0.1';")
        
        # Add root user config directly
        content = content.replace("/* Server parameters */", "/* Server parameters */\n$cfg['Servers'][$i]['user'] = 'root';\n$cfg['Servers'][$i]['password'] = '';")
        
        # Set a random blowfish secret (required by phpMyAdmin)
        content = re.sub(r"\['blowfish_secret'\] = '';", "['blowfish_secret'] = 'winphpservermanagersecretblowfish32chars';", content)
        
        with open(config_inc, 'w') as f:
            f.write(content)
        print("phpMyAdmin config.inc.php configured.")

def main():
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    os.makedirs(WWW_DIR, exist_ok=True)
    
    # Write a default index.php file
    default_index = os.path.join(WWW_DIR, 'index.php')
    if not os.path.exists(default_index):
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
            
    for name, pkg in PACKAGES.items():
        print("="*40)
        print(f"Processing Package: {name.upper()}")
        print("="*40)
        
        dest = pkg['dest']
        if os.path.exists(dest) and len(os.listdir(dest)) > 3:
            print(f"Package {name} is already installed in {dest}.")
            continue
            
        zip_filename = os.path.basename(pkg['url'])
        zip_path = os.path.join(DOWNLOADS_DIR, zip_filename)
        
        if not os.path.exists(zip_path):
            try:
                download_file(pkg['url'], zip_path)
            except Exception as e:
                print(f"Error downloading {name}: {e}")
                continue
                
        try:
            nested = pkg.get('nested_folder')
            extract_zip(zip_path, dest, strip_root=pkg['strip_root'], nested_folder=nested)
        except Exception as e:
            print(f"Error extracting {name}: {e}")
            continue
            
        # Clean up zip
        try:
            os.remove(zip_path)
        except:
            pass

    # Configurations
    print("="*40)
    print("CONFIGURING ALL PACKAGES")
    print("="*40)
    
    setup_php(PACKAGES['php']['dest'])
    setup_nginx()
    setup_apache()
    setup_mysql()
    setup_phpmyadmin()
    
    # Cleanup downloads dir
    if os.path.exists(DOWNLOADS_DIR):
        try:
            shutil.rmtree(DOWNLOADS_DIR)
        except:
            pass
            
    print("\n" + "="*40)
    print("ALL SERVER PACKAGES BUILT AND CONFIGURED!")
    print("="*40)

if __name__ == '__main__':
    import re
    main()
