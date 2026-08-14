# -*- coding: utf-8 -*-
"""文件名翻译器 - 入口。"""

import sys


def main():
    if "--selftest" in sys.argv:
        from app.selftest import run_selftest

        raise SystemExit(run_selftest())
    import tkinter as tk

    from app.gui import FileTranslatorApp

    root = tk.Tk()
    FileTranslatorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
