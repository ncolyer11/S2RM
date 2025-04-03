import os
import sys

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS  # PyInstaller temp folder
    else:
        # base_path = os.path.abspath(".")
        base_path = os.path.dirname(os.path.abspath(sys.argv[0]))  # Use the executable's directory

    return os.path.join(base_path, relative_path)
