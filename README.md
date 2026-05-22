# ⚡ WinPHP Control Center

WinPHP Control Center is a premium, modern, and high-DPI aware desktop administration console for managing your local WAMP (Windows, Apache/Nginx, MariaDB/MySQL, PHP) development stack. Built using Python and PySide6 (Qt), it features a sleek dark-mode user interface designed for high-resolution displays.

[![Download Standalone App](https://img.shields.io/badge/Download-Standalone%20App%20(v1.2)-3b82f6?style=for-the-badge&logo=windows)](https://github.com/villen4800/WinPHP/releases/download/1.2/WinPHP.exe)

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

## 🚀 Getting Started

### Prerequisites

To run or build the application from source, you need:

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


## 🔧 Customization

All service settings (such as custom port allocations, system status loop timings, and active server preferences) are stored dynamically within the local configuration schema to maintain persistence across sessions.

---
