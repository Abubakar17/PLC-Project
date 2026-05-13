"""Entry point for the Mini PLC Logic Simulator."""

from __future__ import annotations

import tkinter as tk

from gui import PlcSimulatorApp


def main() -> None:
    root = tk.Tk()
    PlcSimulatorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

