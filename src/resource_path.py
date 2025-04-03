import os
import sys
import platform

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS  # PyInstaller temp folder
    else:
        if platform.system() == "Windows":
            base_path = os.path.abspath(".") # Use current directory on Windows
        else:
            base_path = os.path.dirname(os.path.abspath(sys.argv[0])) # Use executable's directory on Linux

    return os.path.join(base_path, relative_path)