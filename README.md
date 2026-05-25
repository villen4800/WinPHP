# ⚡ WinPHP Control Center
<img width="1774" height="887" alt="image" src="https://github.com/user-attachments/assets/02aaf55e-b775-41f5-a8ef-acc3f5bdfe32" />

WinPHP Control Center is a premium, modern, and high-DPI aware desktop administration console for managing your local WAMP (Windows, Apache/Nginx, MariaDB/MySQL, PHP) development stack. Built using Python and PySide6 (Qt), it features a sleek dark-mode user interface designed for high-resolution displays.

[![Download Windows App](https://img.shields.io/badge/Download-Windows%20App%20(v1.2)-3b82f6?style=for-the-badge&logo=windows)](https://github.com/villen4800/WinPHP-Lightweight-Php-server-for-windows/releases/download/1.2/WinPHP.WINDOWS.zip)

---

## ✨ Features

- **🌐 Dual Web Server Switcher:** Seamlessly toggle between **Nginx** and **Apache** with a single click.
- **🛠️ Integrated Service Controls:** Start, stop, and monitor **Nginx**, **Apache**, **MariaDB/MySQL**, and **PHP FastCGI** independently or all at once.
- **🔄 PHP Version Switcher:** Change active PHP versions instantly with automated service restarts.
- **🔌 Extensions Manager:** Toggle PHP extensions directly from the UI with real-time `php.ini` modification.
- **📝 Built-in Configuration Editor:** Inspect and modify server config files (`php.ini`, `nginx.conf`, `httpd.conf`, `my.ini`) inside a built-in text editor.
- **📊 Real-time System Metrics:** Track local **CPU**, **RAM**, and **Disk space** utilization with custom, thread-safe progress indicators.
- **🔍 Log Viewer:** Monitor real-time logs for all servers directly within the console.
- **📁 Projects Manager:** Register and quickly launch local website directories.
- **📥 System Tray Integration:** Minimizes to the Windows system tray with a right-click context menu for quick commands (Start, Stop, Restore, Exit).
- **🚀 Windows Startup Support:** Option to automatically run the application on Windows logon.
- **📐 High-DPI Auto-Scaling:** Automatically detects display scaling factor (125%, 150%, 200%, etc.) to scale layouts, fonts, and resource assets, preventing clipping.

---
## 📦 Supported Stack Versions

- **Apache:** 2.4.67
- **Nginx:** 1.24.0, 1.26.3
- **MariaDB:** 11.4.11 - 12.3.1
- **PHP:** 7.4.33-nts - 8.5.6-nts
- **phpMyAdmin:** 4.9.11 - 5.2.3


## 🚀 Getting Started

### Prerequisites

To run you need:

1. **Python 3.10+** (tested on Python 3.14)
2. Python dependencies:
   ```bash
   pip install PySide6 pillow
   ```

### Running Locally

To run the application from source:

```bash
python app.py
```
## Screenshots
CLI Interface 
<img width="1532" height="1205" alt="{2AE0D67F-2949-43BE-9BA2-DEAC5780BAF7}" src="https://github.com/user-attachments/assets/82624d19-f259-4e9f-8488-abeaf4cf2810" />

App Interface
<img width="1982" height="1491" alt="{E38703BC-C20C-469F-88E9-509473617694}" src="https://github.com/user-attachments/assets/afa940fe-a18f-4792-b597-479e1bd08626" />


## 🔧 Customization

All service settings (such as custom port allocations, system status loop timings, and active server preferences) are stored dynamically within the local configuration schema to maintain persistence across sessions.
