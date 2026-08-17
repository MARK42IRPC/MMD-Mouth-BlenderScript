"""Bundle Sudachi's API without its optional 207 MB core dictionary."""

from PyInstaller.utils.hooks import collect_data_files


datas = collect_data_files("sudachipy")
hiddenimports = ["sudachipy.config", "sudachipy.errors"]
