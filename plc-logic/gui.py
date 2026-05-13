"""Tkinter GUI for the mini PLC logic simulator."""

from __future__ import annotations

import re
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from logic_engine import LogicEngine, LogicSyntaxError
from signals import DEFAULT_INPUTS, DEFAULT_OUTPUTS, SignalStore
from simulation import IndustrialSimulation


SCAN_MS = 75
MONITORED_TIMERS = ("T1", "T2")
WATCH_SIGNALS = (
    "INSPECT_DONE",
    "SORT_DONE",
    "JAM",
    "CELL_OK",
    "EXIT_CLEAR",
    "T1_EN",
    "T1_DONE",
    "T2_EN",
    "T2_DONE",
)
OPERATORS = {"AND", "OR", "NOT", "NAND", "NOR"}
LITERALS = {"TRUE", "FALSE"}


EXAMPLES = {
    "Starter Conveyor": {
        "description": "Basic motor, entry delay, gate open, and alarm interlock.",
        "program": """# Starter Conveyor
# START runs the motor unless STOP or ESTOP is on.
# SENSOR1 proves the box reached the entry station.
MOTOR = START AND NOT STOP AND NOT ESTOP
T1 = TIMER(SENSOR1, 0.3)
TIMER1_DONE = T1_DONE
GATE = MOTOR AND NOT ESTOP
READY = MOTOR AND NOT ALARM
ALARM = ESTOP
""",
    },
    "Inspection Clamp": {
        "description": "Stops the box at SENSOR1, clamps it for inspection, then releases through the gate.",
        "program": """# Inspection Clamp
# SENSOR1 means the box is at the inspection station.
# T1 is the inspection dwell. The clamp stays down until T1_DONE.
T1 = TIMER(SENSOR1, 2.5)
TIMER1_DONE = T1_DONE
INSPECT_DONE = T1_DONE OR (INSPECT_DONE AND NOT STOP AND NOT ESTOP)
CLAMP = SENSOR1 AND NOT INSPECT_DONE AND NOT ESTOP
MOTOR = START AND NOT STOP AND NOT ESTOP AND NOT CLAMP
GATE = INSPECT_DONE AND NOT ESTOP
READY = START AND NOT ESTOP AND NOT CLAMP
ALARM = ESTOP OR (SENSOR2 AND NOT GATE)
""",
    },
    "Sorting Diverter": {
        "description": "Uses SENSOR2 as a quality/photo-eye station and diverts after a short confirmation delay.",
        "program": """# Sorting Diverter
# SENSOR2 confirms the box reached the sorting station.
# The motor pauses at SENSOR2 until the sorting timer is done.
T2 = TIMER(SENSOR2, 1.2)
TIMER2_DONE = T2_DONE
SORT_DONE = T2_DONE OR (SORT_DONE AND SENSOR2)
MOTOR = START AND NOT STOP AND NOT ESTOP AND NOT (SENSOR2 AND NOT SORT_DONE)
DIVERTER = SORT_DONE AND NOT ESTOP
GATE = SENSOR2 OR DIVERTER
READY = MOTOR AND NOT DIVERTER AND NOT ALARM
ALARM = ESTOP
""",
    },
    "NAND NOR Practice": {
        "description": "Small truth-table style example for NAND and NOR operators.",
        "program": """# NAND NOR Practice
# MOTOR is off only when START and STOP are both on.
# ALARM turns on when both sensors are off, using NOR.
MOTOR = START NAND STOP
ALARM = SENSOR1 NOR SENSOR2
GATE = START AND NOT ESTOP
READY = NOT ALARM AND NOT ESTOP
DIVERTER = SENSOR2 AND READY
""",
    },
    "Jam Watchdog": {
        "description": "Raises ALARM if the box stays at SENSOR1 too long before inspection completes.",
        "program": """# Jam Watchdog
# T1 is normal inspection time. T2 is the longer fault watchdog.
T1 = TIMER(SENSOR1, 0.9)
TIMER1_DONE = T1_DONE
INSPECT_DONE = T1_DONE OR (INSPECT_DONE AND NOT STOP AND NOT ESTOP)
T2 = TIMER(SENSOR1 AND NOT INSPECT_DONE, 2.8)
TIMER2_DONE = T2_DONE
JAM = T2_DONE
MOTOR = START AND NOT STOP AND NOT ESTOP AND NOT JAM
CLAMP = SENSOR1 AND NOT INSPECT_DONE AND NOT ESTOP
GATE = INSPECT_DONE AND NOT JAM AND NOT ESTOP
READY = MOTOR AND NOT ALARM
ALARM = ESTOP OR JAM
""",
    },
    "Safe Gate Interlock": {
        "description": "Requires START, no faults, and a clear exit before opening the gate.",
        "program": """# Safe Gate Interlock
# Gate opens only when the cell is ready and SENSOR2 is clear.
CELL_OK = START AND NOT STOP AND NOT ESTOP
EXIT_CLEAR = NOT SENSOR2
MOTOR = CELL_OK AND EXIT_CLEAR
GATE = CELL_OK AND EXIT_CLEAR
CLAMP = SENSOR1 AND CELL_OK
DIVERTER = SENSOR2 AND CELL_OK
READY = CELL_OK AND EXIT_CLEAR
ALARM = ESTOP OR (SENSOR2 AND GATE)
""",
    },
    "Try It Yourself": {
        "description": "Commented exercise: read the hints, then uncomment lines one by one.",
        "program": """# Try It Yourself - commented exercise
# Nothing below executes yet because every logic line starts with '#'.
# Remove the '#' at the start of a line to activate it, then press RUN.

# Step 1: make START run the conveyor, unless STOP or ESTOP is active.
# MOTOR = START AND NOT STOP AND NOT ESTOP

# Step 2: make SENSOR1 start a 1 second inspection timer.
# T1 = TIMER(SENSOR1, 1)
# TIMER1_DONE = T1_DONE

# Step 3: lower the clamp while SENSOR1 is on and the timer is not done.
# CLAMP = SENSOR1 AND NOT T1_DONE AND NOT ESTOP

# Step 4: open the gate after the timer is done.
# GATE = T1_DONE AND NOT ESTOP

# Step 5: add normal status and alarm lamps.
# READY = MOTOR AND NOT CLAMP AND NOT ESTOP
# ALARM = ESTOP OR (SENSOR2 AND NOT GATE)
""",
    },
}

EXAMPLE_PROGRAM = EXAMPLES["Inspection Clamp"]["program"]

GUIDE_TEXT = """How to proceed:
1. Pick an example, press LOAD EXAMPLE, then RUN.
2. Turn START on. In AUTO mode the moving box triggers SENSOR1 and SENSOR2.
3. Switch to MANUAL mode when you want to toggle sensors yourself.
4. Edit the logic, press RUN again, and watch the scan cycle update outputs.

Inputs:
START: operator start command.
STOP: normal stop command, usually used as NOT STOP.
ESTOP: emergency stop/fault input. Use it to force MOTOR/GATE off and ALARM on.
SENSOR1: entry/inspection photo-eye near the clamp station.
SENSOR2: exit/sorting photo-eye near the gate and diverter.

Outputs:
MOTOR moves the conveyor box.
GATE opens the exit gate.
CLAMP lowers the inspection clamp.
DIVERTER changes the sorting chute.
READY is a general OK/running lamp.
ALARM flashes the red beacon.

Timers:
T1 = TIMER(SENSOR1, 3) creates T1_EN, T1_DONE, and T1_ACC.
You can write either T1_DONE or T1.DONE in logic.

Debugging:
Signal Watch shows useful internal bits.
Force outputs lets you override output lamps and animation for teaching."""


class PlcSimulatorApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Mini PLC Logic Simulator with 2D Industrial Animation (FX-TRN Inspired)")
        self.root.geometry("1180x760")
        self.root.minsize(980, 650)

        self.signals = SignalStore()
        self.engine = LogicEngine()
        self.running = False
        self.paused = False
        self.last_scan = time.monotonic()
        self.scan_count = 0
        self.last_scan_ms = 0.0
        self.last_snapshot = self.signals.snapshot()

        self.input_buttons: dict[str, ttk.Button] = {}
        self.input_lamps: dict[str, tk.Canvas] = {}
        self.output_lamps: dict[str, tk.Canvas] = {}
        self.output_labels: dict[str, ttk.Label] = {}
        self.force_buttons: dict[str, ttk.Button] = {}
        self.force_values: dict[str, tk.BooleanVar] = {}
        self.timer_labels: dict[str, ttk.Label] = {}
        self.timer_bars: dict[str, ttk.Progressbar] = {}
        self.watch_rows: dict[str, str] = {}
        self.force_mode_var = tk.BooleanVar(value=False)
        self.example_var = tk.StringVar(value="Inspection Clamp")
        self.highlight_after_id: str | None = None

        self._configure_style()
        self._build_layout()
        self._load_selected_example()
        self._refresh_inputs()
        self._refresh_outputs()
        self._refresh_watch_table()
        self._refresh_scan_monitor()
        self._schedule_scan()

    def _configure_style(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#eef2f6")
        style.configure("Panel.TFrame", background="#ffffff", relief="flat")
        style.configure("TLabel", background="#ffffff", foreground="#1f2937", font=("Segoe UI", 10))
        style.configure("Title.TLabel", background="#ffffff", foreground="#111827", font=("Segoe UI", 12, "bold"))
        style.configure("Status.TLabel", background="#f8fafc", foreground="#334155", font=("Segoe UI", 9))
        style.configure("Run.TButton", font=("Segoe UI", 10, "bold"))
        style.configure("On.TButton", background="#22c55e", foreground="#052e16")
        style.configure("Off.TButton", background="#e5e7eb", foreground="#1f2937")
        style.configure("Fault.TButton", background="#ef4444", foreground="#ffffff")

    def _build_layout(self) -> None:
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=0)

        left = ttk.Frame(self.root, style="Panel.TFrame", padding=14)
        center = ttk.Frame(self.root, style="Panel.TFrame", padding=14)
        right = ttk.Frame(self.root, style="Panel.TFrame", padding=14)
        bottom = ttk.Frame(self.root, style="Panel.TFrame", padding=10)

        left.grid(row=0, column=0, sticky="ns", padx=(10, 6), pady=10)
        center.grid(row=0, column=1, sticky="nsew", padx=6, pady=10)
        right.grid(row=0, column=2, sticky="ns", padx=(6, 10), pady=10)
        bottom.grid(row=1, column=0, columnspan=3, sticky="ew", padx=10, pady=(0, 10))
        center.columnconfigure(0, weight=1)
        center.rowconfigure(1, weight=1)
        bottom.columnconfigure(0, weight=1)

        self._build_left_panel(left)
        self._build_center_panel(center)
        self._build_right_panel(right)
        self._build_log(bottom)

    def _build_left_panel(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(1, weight=1)
        ttk.Label(parent, text="Inputs", style="Title.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        for row, name in enumerate(DEFAULT_INPUTS, start=1):
            lamp = tk.Canvas(parent, width=24, height=24, bg="#ffffff", highlightthickness=0)
            lamp.grid(row=row, column=0, padx=(0, 6), pady=4)
            lamp.create_oval(4, 4, 20, 20, fill="#9ca3af", outline="#6b7280", width=2, tags=("bulb",))
            button = ttk.Button(parent, text=f"{name}: OFF", command=lambda n=name: self._toggle_input(n), width=16)
            button.grid(row=row, column=1, sticky="ew", pady=4)
            self.input_lamps[name] = lamp
            self.input_buttons[name] = button

        ttk.Separator(parent).grid(row=7, column=0, columnspan=2, sticky="ew", pady=14)
        self.mode_var = tk.StringVar(value="AUTO")
        ttk.Label(parent, text="Mode", style="Title.TLabel").grid(row=8, column=0, columnspan=2, sticky="w")
        ttk.Radiobutton(parent, text="Auto", variable=self.mode_var, value="AUTO", command=self._mode_changed).grid(row=9, column=0, columnspan=2, sticky="w")
        ttk.Radiobutton(parent, text="Manual", variable=self.mode_var, value="MANUAL", command=self._mode_changed).grid(row=10, column=0, columnspan=2, sticky="w")

        ttk.Separator(parent).grid(row=11, column=0, columnspan=2, sticky="ew", pady=14)
        ttk.Button(parent, text="Single Step", command=self._single_step).grid(row=12, column=0, columnspan=2, sticky="ew", pady=4)
        ttk.Button(parent, text="Pause / Resume", command=self._toggle_pause).grid(row=13, column=0, columnspan=2, sticky="ew", pady=4)
        ttk.Button(parent, text="Reset Box", command=self._reset_box).grid(row=14, column=0, columnspan=2, sticky="ew", pady=4)

        ttk.Separator(parent).grid(row=15, column=0, columnspan=2, sticky="ew", pady=14)
        ttk.Checkbutton(
            parent,
            text="Force outputs",
            variable=self.force_mode_var,
            command=self._force_mode_changed,
        ).grid(row=16, column=0, columnspan=2, sticky="w")

    def _build_center_panel(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Logic Editor", style="Title.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
        editor_frame = ttk.Frame(parent)
        editor_frame.grid(row=1, column=0, sticky="nsew")
        editor_frame.columnconfigure(1, weight=1)
        editor_frame.rowconfigure(0, weight=1)

        self.line_numbers = tk.Canvas(editor_frame, width=42, bg="#edf2f7", highlightthickness=0)
        self.line_numbers.grid(row=0, column=0, sticky="ns")
        self.editor = tk.Text(editor_frame, height=16, wrap="none", undo=True, font=("Consolas", 11), bg="#fbfdff", fg="#111827")
        self.editor.grid(row=0, column=1, sticky="nsew")
        yscroll = ttk.Scrollbar(editor_frame, orient="vertical", command=self._on_editor_scroll)
        yscroll.grid(row=0, column=2, sticky="ns")
        self.editor.configure(yscrollcommand=lambda first, last: self._on_editor_yscroll(yscroll, first, last))
        self.editor.tag_configure("error", background="#fecaca")
        self.editor.tag_configure("comment", foreground="#64748b")
        self.editor.tag_configure("operator", foreground="#7c3aed", font=("Consolas", 11, "bold"))
        self.editor.tag_configure("timer", foreground="#b45309", font=("Consolas", 11, "bold"))
        self.editor.tag_configure("literal", foreground="#0f766e", font=("Consolas", 11, "bold"))
        self.editor.tag_configure("target", foreground="#1d4ed8", font=("Consolas", 11, "bold"))
        self.editor.tag_configure("signal", foreground="#334155")
        self.editor.bind("<KeyRelease>", self._editor_changed)
        self.editor.bind("<ButtonRelease-1>", self._editor_changed)
        self.editor.bind("<MouseWheel>", self._editor_changed)
        self.editor.bind("<Configure>", self._editor_changed)

        controls = ttk.Frame(parent, style="Panel.TFrame")
        controls.grid(row=2, column=0, sticky="ew", pady=10)
        for col in range(7):
            controls.columnconfigure(col, weight=1)

        ttk.Button(controls, text="RUN", style="Run.TButton", command=self._run).grid(row=0, column=0, sticky="ew", padx=3)
        ttk.Button(controls, text="STOP", command=self._stop).grid(row=0, column=1, sticky="ew", padx=3)
        ttk.Button(controls, text="CLEAR LOGIC", command=self._clear_logic).grid(row=0, column=2, sticky="ew", padx=3)
        example_box = ttk.Combobox(controls, textvariable=self.example_var, values=list(EXAMPLES), state="readonly", width=18)
        example_box.grid(row=0, column=3, sticky="ew", padx=3)
        ttk.Button(controls, text="LOAD EXAMPLE", command=self._load_selected_example).grid(row=0, column=4, sticky="ew", padx=3)
        ttk.Button(controls, text="SAVE", command=self._save_logic).grid(row=0, column=5, sticky="ew", padx=3)
        ttk.Button(controls, text="LOAD", command=self._load_logic).grid(row=0, column=6, sticky="ew", padx=3)

        sim_frame = ttk.Frame(parent, style="Panel.TFrame")
        sim_frame.grid(row=3, column=0, sticky="ew", pady=(6, 0))
        self.simulation = IndustrialSimulation(sim_frame)
        self.simulation.grid(row=0, column=0, sticky="ew")

    def _build_right_panel(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(1, weight=1)
        ttk.Label(parent, text="Outputs", style="Title.TLabel").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))
        for row, name in enumerate(DEFAULT_OUTPUTS, start=1):
            lamp = tk.Canvas(parent, width=34, height=34, bg="#ffffff", highlightthickness=0)
            lamp.grid(row=row, column=0, padx=(0, 8), pady=6)
            lamp.create_oval(5, 5, 29, 29, fill="#9ca3af", outline="#6b7280", width=2, tags=("bulb",))
            label = ttk.Label(parent, text=f"{name}: OFF", width=18)
            label.grid(row=row, column=1, sticky="w")
            force_var = tk.BooleanVar(value=False)
            force_button = ttk.Button(parent, text="Force OFF", command=lambda n=name: self._toggle_force(n), width=10)
            force_button.grid(row=row, column=2, sticky="ew", padx=(6, 0))
            self.output_lamps[name] = lamp
            self.output_labels[name] = label
            self.force_values[name] = force_var
            self.force_buttons[name] = force_button

        sep_row = len(DEFAULT_OUTPUTS) + 1
        ttk.Separator(parent).grid(row=sep_row, column=0, columnspan=3, sticky="ew", pady=14)
        self.status_label = ttk.Label(parent, text="Stopped", style="Title.TLabel")
        self.status_label.grid(row=sep_row + 1, column=0, columnspan=3, sticky="w")

        ttk.Separator(parent).grid(row=sep_row + 2, column=0, columnspan=3, sticky="ew", pady=14)
        ttk.Label(parent, text="Timers", style="Title.TLabel").grid(row=sep_row + 3, column=0, columnspan=3, sticky="w")
        timer_row = sep_row + 4
        for index, timer_name in enumerate(MONITORED_TIMERS):
            label = ttk.Label(parent, text=f"{timer_name}: 0.0 / 0.0s", width=18)
            label.grid(row=timer_row + index * 2, column=0, columnspan=3, sticky="w", pady=(6, 0))
            bar = ttk.Progressbar(parent, maximum=1.0, value=0.0)
            bar.grid(row=timer_row + index * 2 + 1, column=0, columnspan=3, sticky="ew")
            self.timer_labels[timer_name] = label
            self.timer_bars[timer_name] = bar

        watch_row = timer_row + len(MONITORED_TIMERS) * 2
        ttk.Separator(parent).grid(row=watch_row, column=0, columnspan=3, sticky="ew", pady=14)
        ttk.Label(parent, text="Signal Watch", style="Title.TLabel").grid(row=watch_row + 1, column=0, columnspan=3, sticky="w")
        self.watch_table = ttk.Treeview(parent, columns=("value",), show="tree headings", height=7)
        self.watch_table.heading("#0", text="Signal")
        self.watch_table.heading("value", text="Value")
        self.watch_table.column("#0", width=130, stretch=True)
        self.watch_table.column("value", width=70, stretch=False, anchor="center")
        self.watch_table.grid(row=watch_row + 2, column=0, columnspan=3, sticky="ew", pady=(6, 0))
        for signal_name in WATCH_SIGNALS:
            row_id = self.watch_table.insert("", "end", text=signal_name, values=("OFF",))
            self.watch_rows[signal_name] = row_id

        guide_row = watch_row + 3
        ttk.Separator(parent).grid(row=guide_row, column=0, columnspan=3, sticky="ew", pady=14)
        ttk.Label(parent, text="Guide", style="Title.TLabel").grid(row=guide_row + 1, column=0, columnspan=3, sticky="w")
        self.guide_text = tk.Text(parent, width=34, height=15, wrap="word", bg="#f8fafc", fg="#1f2937", relief="flat", font=("Segoe UI", 9))
        self.guide_text.grid(row=guide_row + 2, column=0, columnspan=2, sticky="nsew", pady=(6, 0))
        guide_scrollbar = ttk.Scrollbar(parent, orient="vertical", command=self.guide_text.yview)
        guide_scrollbar.grid(row=guide_row + 2, column=2, sticky="ns", pady=(6, 0))
        self.guide_text.configure(yscrollcommand=guide_scrollbar.set)
        self.guide_text.insert("1.0", GUIDE_TEXT)
        self.guide_text.configure(state="disabled")

    def _build_log(self, parent: ttk.Frame) -> None:
        monitor = ttk.Frame(parent, style="Panel.TFrame")
        monitor.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        for column in range(4):
            monitor.columnconfigure(column, weight=1)
        self.scan_state_label = ttk.Label(monitor, text="State: Stopped", style="Status.TLabel")
        self.scan_count_label = ttk.Label(monitor, text="Scans: 0", style="Status.TLabel")
        self.scan_time_label = ttk.Label(monitor, text="Scan: 0.0 ms", style="Status.TLabel")
        self.scan_mode_label = ttk.Label(monitor, text="Mode: AUTO", style="Status.TLabel")
        self.scan_state_label.grid(row=0, column=0, sticky="w")
        self.scan_count_label.grid(row=0, column=1, sticky="w")
        self.scan_time_label.grid(row=0, column=2, sticky="w")
        self.scan_mode_label.grid(row=0, column=3, sticky="w")

        ttk.Label(parent, text="Event Log", style="Title.TLabel").grid(row=1, column=0, sticky="w", pady=(0, 6))
        log_frame = ttk.Frame(parent)
        log_frame.grid(row=2, column=0, sticky="ew")
        log_frame.columnconfigure(0, weight=1)
        self.log_text = tk.Text(log_frame, height=7, state="disabled", wrap="word", font=("Consolas", 10), bg="#111827", fg="#d1d5db")
        self.log_text.grid(row=0, column=0, sticky="ew")
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scrollbar.set)

    def _schedule_scan(self) -> None:
        now = time.monotonic()
        dt = now - self.last_scan
        self.last_scan = now
        if self.running and not self.paused:
            self._apply_auto_sensors()
            self._scan_once(dt)
        else:
            self._apply_auto_sensors()
            self.simulation.update(self.signals.snapshot(), 0.0)
        self.root.after(SCAN_MS, self._schedule_scan)

    def _scan_once(self, dt: float | None = None) -> None:
        if dt is None:
            now = time.monotonic()
            dt = now - self.last_scan
            self.last_scan = now
        try:
            next_values = self.engine.scan(self.signals.snapshot(), dt)
        except Exception as exc:
            self.running = False
            self.status_label.configure(text="Logic error")
            self._log(f"Runtime error: {exc}")
            messagebox.showerror("Logic runtime error", str(exc))
            return

        for name, value in next_values.items():
            self.signals.set(name, value)
        self._apply_forced_outputs()
        self.scan_count += 1
        self.last_scan_ms = dt * 1000
        self._refresh_outputs()
        self._refresh_timers()
        self._refresh_watch_table()
        self._refresh_scan_monitor()
        self.simulation.update(self.signals.snapshot(), dt)
        self._apply_auto_sensors()
        self._log_signal_changes()

    def _compile_editor_logic(self) -> bool:
        self.editor.tag_remove("error", "1.0", "end")
        try:
            self.engine.compile(self.editor.get("1.0", "end"))
        except LogicSyntaxError as exc:
            self.running = False
            self.status_label.configure(text="Syntax error")
            self._highlight_error(exc.line_no)
            self._log(f"Syntax error on line {exc.line_no}: {exc}")
            messagebox.showerror("Logic syntax error", f"Line {exc.line_no}: {exc}")
            return False
        self._log("Logic compiled")
        return True

    def _run(self) -> None:
        if not self._compile_editor_logic():
            return
        self.engine.reset()
        self.signals.reset_runtime()
        self.signals.update_many(self.engine.reset_program_signals())
        self._apply_forced_outputs()
        self._refresh_outputs()
        self._refresh_timers()
        self._refresh_watch_table()
        self._refresh_inputs()
        self.running = True
        self.paused = False
        self.scan_count = 0
        self.last_scan_ms = 0.0
        self.last_scan = time.monotonic()
        self.status_label.configure(text="Running")
        self._refresh_scan_monitor()

    def _stop(self) -> None:
        self.running = False
        self.paused = False
        self.engine.reset()
        self.signals.reset_runtime()
        self.signals.update_many(self.engine.reset_program_signals())
        self._apply_forced_outputs()
        self._refresh_inputs()
        self._refresh_outputs()
        self._refresh_timers()
        self._refresh_watch_table()
        self.simulation.update(self.signals.snapshot(), 0.0)
        self.status_label.configure(text="Stopped")
        self._refresh_scan_monitor()
        self._log("PLC stopped")

    def _single_step(self) -> None:
        if not self._compile_editor_logic():
            return
        self._apply_auto_sensors()
        self._scan_once(SCAN_MS / 1000)
        self.running = False
        self.status_label.configure(text="Single step")
        self._refresh_scan_monitor()

    def _toggle_pause(self) -> None:
        if not self.running:
            return
        self.paused = not self.paused
        self.status_label.configure(text="Paused" if self.paused else "Running")
        self._refresh_scan_monitor()
        self._log("Simulation paused" if self.paused else "Simulation resumed")

    def _toggle_input(self, name: str) -> None:
        if self.mode_var.get() == "AUTO" and name in {"SENSOR1", "SENSOR2"}:
            self._log(f"{name} is controlled by box position in AUTO mode")
            return
        self.signals.set(name, not self.signals.get(name))
        self._refresh_inputs()
        self._log(f"{name} {'ON' if self.signals.get(name) else 'OFF'}")

    def _refresh_inputs(self) -> None:
        for name, button in self.input_buttons.items():
            value = self.signals.get(name)
            suffix = f"AUTO {'ON' if value else 'OFF'}" if self.mode_var.get() == "AUTO" and name in {"SENSOR1", "SENSOR2"} else ("ON" if value else "OFF")
            style = "Fault.TButton" if name == "ESTOP" and value else "On.TButton" if value else "Off.TButton"
            button.configure(text=f"{name}: {suffix}", style=style)
            fill, outline = ("#ef4444", "#991b1b") if name == "ESTOP" and value else (("#22c55e", "#15803d") if value else ("#9ca3af", "#6b7280"))
            self.input_lamps[name].itemconfigure("bulb", fill=fill, outline=outline)

    def _refresh_outputs(self) -> None:
        snapshot = self.signals.snapshot()
        for name in DEFAULT_OUTPUTS:
            value = bool(snapshot.get(name, False))
            lamp = self.output_lamps[name]
            if name == "ALARM" and value:
                fill, outline = "#ef4444", "#991b1b"
            elif self.force_mode_var.get() and name in self.force_values:
                fill, outline = ("#f59e0b", "#92400e") if value else ("#9ca3af", "#6b7280")
            else:
                fill, outline = ("#22c55e", "#15803d") if value else ("#9ca3af", "#6b7280")
            lamp.itemconfigure("bulb", fill=fill, outline=outline)
            suffix = "FORCED ON" if self.force_mode_var.get() and self.force_values[name].get() else ("FORCED OFF" if self.force_mode_var.get() else ("ON" if value else "OFF"))
            self.output_labels[name].configure(text=f"{name}: {suffix}")
            self.force_buttons[name].configure(text="Force ON" if self.force_values[name].get() else "Force OFF")
            self.force_buttons[name].configure(state="normal" if self.force_mode_var.get() else "disabled")

    def _refresh_timers(self) -> None:
        snapshot = self.signals.snapshot()
        for timer_name in MONITORED_TIMERS:
            timer = self.engine.timers.get(timer_name)
            preset = timer.delay_seconds if timer else 0.0
            acc = float(snapshot.get(f"{timer_name}_ACC", 0.0) or 0.0)
            done = bool(snapshot.get(f"{timer_name}_DONE", False))
            ratio = min(acc / preset, 1.0) if preset > 0 else 0.0
            state = "DONE" if done else ("EN" if snapshot.get(f"{timer_name}_EN", False) else "IDLE")
            self.timer_labels[timer_name].configure(text=f"{timer_name}: {acc:.1f} / {preset:.1f}s {state}")
            self.timer_bars[timer_name].configure(value=ratio)

    def _refresh_watch_table(self) -> None:
        snapshot = self.signals.snapshot()
        for signal_name, row_id in self.watch_rows.items():
            raw_value = snapshot.get(signal_name, False)
            value = f"{raw_value:.1f}" if isinstance(raw_value, float) else ("ON" if bool(raw_value) else "OFF")
            self.watch_table.item(row_id, values=(value,))

    def _refresh_scan_monitor(self) -> None:
        if self.running and self.paused:
            state = "Paused"
        elif self.running:
            state = "Running"
        elif self.status_label.cget("text") == "Single step":
            state = "Single step"
        else:
            state = "Stopped"
        self.scan_state_label.configure(text=f"State: {state}")
        self.scan_count_label.configure(text=f"Scans: {self.scan_count}")
        self.scan_time_label.configure(text=f"Scan: {self.last_scan_ms:.1f} ms")
        self.scan_mode_label.configure(text=f"Mode: {self.mode_var.get()}")

    def _on_editor_scroll(self, *args: str) -> None:
        self.editor.yview(*args)
        self._draw_line_numbers()

    def _on_editor_yscroll(self, scrollbar: ttk.Scrollbar, first: str, last: str) -> None:
        scrollbar.set(first, last)
        self._draw_line_numbers()

    def _editor_changed(self, event: tk.Event | None = None) -> None:
        self._draw_line_numbers()
        if self.highlight_after_id is not None:
            self.root.after_cancel(self.highlight_after_id)
        self.highlight_after_id = self.root.after(120, self._highlight_syntax)

    def _draw_line_numbers(self) -> None:
        self.line_numbers.delete("all")
        index = self.editor.index("@0,0")
        while True:
            line_info = self.editor.dlineinfo(index)
            if line_info is None:
                break
            y = line_info[1]
            line_no = index.split(".")[0]
            self.line_numbers.create_text(36, y, anchor="ne", text=line_no, fill="#64748b", font=("Consolas", 10))
            index = self.editor.index(f"{index}+1line")

    def _highlight_syntax(self) -> None:
        self.highlight_after_id = None
        for tag in ("comment", "operator", "timer", "literal", "target", "signal"):
            self.editor.tag_remove(tag, "1.0", "end")

        line_count = int(self.editor.index("end-1c").split(".")[0])
        for line_no in range(1, line_count + 1):
            line = self.editor.get(f"{line_no}.0", f"{line_no}.end")
            comment_start = line.find("#")
            code_end = len(line) if comment_start < 0 else comment_start
            if comment_start >= 0:
                self.editor.tag_add("comment", f"{line_no}.{comment_start}", f"{line_no}.end")

            code = line[:code_end]
            if "=" in code:
                target = code.split("=", 1)[0]
                match = re.search(r"[A-Za-z_][A-Za-z0-9_\.]*", target)
                if match:
                    self.editor.tag_add("target", f"{line_no}.{match.start()}", f"{line_no}.{match.end()}")

            for match in re.finditer(r"\b[A-Za-z_][A-Za-z0-9_\.]*\b", code):
                word = match.group(0).upper().replace(".", "_")
                start = f"{line_no}.{match.start()}"
                end = f"{line_no}.{match.end()}"
                if word in OPERATORS:
                    self.editor.tag_add("operator", start, end)
                elif word == "TIMER":
                    self.editor.tag_add("timer", start, end)
                elif word in LITERALS:
                    self.editor.tag_add("literal", start, end)
                else:
                    self.editor.tag_add("signal", start, end)

        for tag in ("signal", "literal", "timer", "operator", "target", "comment", "error"):
            self.editor.tag_raise(tag)
        self._draw_line_numbers()

    def _apply_forced_outputs(self) -> None:
        if not self.force_mode_var.get():
            return
        for name, value_var in self.force_values.items():
            self.signals.set(name, value_var.get())

    def _toggle_force(self, name: str) -> None:
        self.force_values[name].set(not self.force_values[name].get())
        self._apply_forced_outputs()
        self._refresh_outputs()
        self.simulation.update(self.signals.snapshot(), 0.0)
        self._log(f"{name} forced {'ON' if self.force_values[name].get() else 'OFF'}")

    def _force_mode_changed(self) -> None:
        if not self.force_mode_var.get():
            for value_var in self.force_values.values():
                value_var.set(False)
            if not (self.running and not self.paused):
                self.signals.reset_runtime()
                self.signals.update_many(self.engine.reset_program_signals())
        self._apply_forced_outputs()
        self._refresh_outputs()
        self._refresh_watch_table()
        self.simulation.update(self.signals.snapshot(), 0.0)
        self._log(f"Force output mode {'enabled' if self.force_mode_var.get() else 'disabled'}")

    def _log_signal_changes(self) -> None:
        current = self.signals.snapshot()
        watched = set(DEFAULT_OUTPUTS) | {"T1_DONE", "T1_EN", "T2_DONE", "T2_EN"}
        for name in sorted(watched):
            if current.get(name) != self.last_snapshot.get(name):
                self._log(f"{name} {'ON' if current.get(name) else 'OFF'}")
        self.last_snapshot = current

    def _apply_auto_sensors(self) -> None:
        if self.mode_var.get() != "AUTO":
            return
        self.signals.update_many(self.simulation.auto_sensor_states())
        self._refresh_inputs()

    def _mode_changed(self) -> None:
        if self.mode_var.get() == "AUTO":
            self._apply_auto_sensors()
        self._refresh_inputs()
        self._refresh_scan_monitor()
        self._log(f"Mode changed to {self.mode_var.get()}")

    def _reset_box(self) -> None:
        self.simulation.reset_box()
        self._apply_auto_sensors()
        self.simulation.update(self.signals.snapshot(), 0.0)
        self._log("Box reset to start position")

    def _highlight_error(self, line_no: int | None) -> None:
        if line_no is None:
            return
        self.editor.tag_add("error", f"{line_no}.0", f"{line_no}.end")
        self.editor.see(f"{line_no}.0")

    def _load_selected_example(self) -> None:
        example_name = self.example_var.get()
        example = EXAMPLES.get(example_name, EXAMPLES["Inspection Clamp"])
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", example["program"])
        self._editor_changed()
        self._log(f"Example loaded: {example_name} - {example['description']}")

    def _clear_logic(self) -> None:
        self.editor.delete("1.0", "end")
        self.editor.tag_remove("error", "1.0", "end")
        self._editor_changed()
        self._log("Logic editor cleared")

    def _save_logic(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save logic program",
            defaultextension=".plc",
            filetypes=[("PLC logic", "*.plc"), ("Text files", "*.txt"), ("All files", "*.*")],
        )
        if path:
            Path(path).write_text(self.editor.get("1.0", "end-1c"), encoding="utf-8")
            self._log(f"Saved {Path(path).name}")

    def _load_logic(self) -> None:
        path = filedialog.askopenfilename(
            title="Load logic program",
            filetypes=[("PLC logic", "*.plc"), ("Text files", "*.txt"), ("All files", "*.*")],
        )
        if path:
            self.editor.delete("1.0", "end")
            self.editor.insert("1.0", Path(path).read_text(encoding="utf-8"))
            self._editor_changed()
            self._log(f"Loaded {Path(path).name}")

    def _log(self, message: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{timestamp}] {message}\n")
        self.log_text.configure(state="disabled")
        self.log_text.see("end")
