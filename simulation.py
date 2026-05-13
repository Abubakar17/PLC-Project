"""Tkinter Canvas animation for the PLC process."""

from __future__ import annotations

import tkinter as tk
from typing import Dict


class IndustrialSimulation:
    """Simple conveyor, box, gate, sensors, and alarm lamp animation."""

    ACCEPT_COLORS = {
        "top": "#f0b65f",
        "side": "#ad7130",
        "front": "#d79b45",
        "seam": "#b47a32",
        "outline": "#8a5a22",
    }
    REJECT_COLORS = {
        "top": "#7aa7d9",
        "side": "#3a78b3",
        "front": "#5b9bd5",
        "seam": "#2c5a8c",
        "outline": "#1f4e79",
    }

    def __init__(self, parent: tk.Widget) -> None:
        self.canvas = tk.Canvas(parent, width=560, height=280, bg="#f4f6f8", highlightthickness=0)
        self.box_x = 78.0
        self.box_y_offset = 0.0
        self.box_type = False  # False = accept (amber), True = reject (blue)
        self.divert_armed = False
        self.alarm_flash = False
        self._build_scene()
        self._apply_box_color()

    def grid(self, **kwargs) -> None:
        self.canvas.grid(**kwargs)

    def reset_box(self) -> None:
        self.box_x = 78.0
        self.box_y_offset = 0.0
        self.divert_armed = False
        self._set_box_coords()

    def _build_scene(self) -> None:
        c = self.canvas
        c.create_text(20, 18, text="2D Industrial Process", anchor="w", font=("Segoe UI", 12, "bold"), fill="#1f2937")
        c.create_polygon(52, 155, 508, 155, 526, 172, 70, 172, fill="#4b5563", outline="#20242a")
        c.create_rectangle(52, 172, 508, 205, fill="#30363d", outline="#20242a", width=2)
        c.create_line(70, 172, 526, 172, fill="#6b7280", width=2)
        for x in range(62, 500, 34):
            c.create_oval(x, 176, x + 22, 198, fill="#69717c", outline="#20242a")
            c.create_arc(x + 3, 179, x + 19, 195, start=20, extent=140, style="arc", outline="#9ca3af")

        self.belt_motion = [
            c.create_line(72 + i * 70, 195, 106 + i * 70, 195, fill="#cfd6df", width=3)
            for i in range(6)
        ]

        c.create_polygon(
            432, 202, 504, 202,
            534, 274, 462, 274,
            fill="#cbd5e1", outline="#475569", width=2,
        )
        c.create_text(498, 266, text="REJECT", font=("Segoe UI", 8, "bold"), fill="#7f1d1d")

        self.box_shadow = c.create_oval(76, 146, 142, 166, fill="#000000", outline="", stipple="gray50")
        self.box_top = c.create_polygon(78, 114, 130, 114, 144, 126, 92, 126, fill="#f0b65f", outline="#8a5a22")
        self.box_side = c.create_polygon(130, 114, 144, 126, 144, 154, 130, 154, fill="#ad7130", outline="#8a5a22")
        self.box_front = c.create_rectangle(78, 126, 130, 154, fill="#d79b45", outline="#8a5a22", width=2)
        self.box_seam = c.create_line(78, 136, 130, 136, fill="#b47a32")

        c.create_text(178, 224, text="SENSOR1", font=("Segoe UI", 9), fill="#374151")
        c.create_text(382, 224, text="SENSOR2", font=("Segoe UI", 9), fill="#374151")
        self.sensor1 = c.create_oval(164, 185, 192, 213, fill="#a7adb5", outline="#606975", width=2)
        self.sensor2 = c.create_oval(368, 185, 396, 213, fill="#a7adb5", outline="#606975", width=2)

        c.create_text(450, 82, text="GATE", font=("Segoe UI", 9), fill="#374151")
        self.gate_post = c.create_rectangle(438, 96, 448, 158, fill="#6b7280", outline="")
        self.gate_bar = c.create_rectangle(448, 98, 512, 112, fill="#efb846", outline="#805f10", width=2)

        c.create_text(278, 82, text="CLAMP", font=("Segoe UI", 9), fill="#374151")
        self.clamp_head = c.create_rectangle(252, 94, 304, 110, fill="#64748b", outline="#334155", width=2)
        self.clamp_rod = c.create_rectangle(274, 68, 282, 94, fill="#94a3b8", outline="")

        c.create_text(490, 232, text="DIVERTER", font=("Segoe UI", 9), fill="#374151")
        self.diverter = c.create_line(458, 210, 520, 246, fill="#2563eb", width=6)

        self.ready_label = c.create_text(278, 42, text="READY", font=("Segoe UI", 10, "bold"), fill="#6b7280")

        c.create_text(84, 82, text="ALARM", font=("Segoe UI", 9), fill="#374151")
        self.alarm = c.create_oval(62, 92, 106, 136, fill="#7f1d1d", outline="#4b1111", width=2)
        self.alarm_glow = c.create_oval(54, 84, 114, 144, outline="", fill="")

        self.motor_text = c.create_text(282, 132, text="MOTOR OFF", font=("Segoe UI", 11, "bold"), fill="#6b7280")
        self._set_box_coords()

    def update(self, signals: Dict[str, bool], dt: float) -> None:
        motor = bool(signals.get("MOTOR", False))
        gate = bool(signals.get("GATE", False))
        clamp = bool(signals.get("CLAMP", False))
        diverter = bool(signals.get("DIVERTER", False))
        ready = bool(signals.get("READY", False))
        alarm = bool(signals.get("ALARM", False))

        if diverter and 326 <= self.box_x <= 386:
            self.divert_armed = True

        gate_stop_x = 372
        divert_start_x = 410
        if self.box_y_offset > 0.0:
            self.box_x += 40 * dt
            self.box_y_offset += 80 * dt
            if self.box_y_offset > 110 or self.box_x > 540:
                self._spawn_next_box()
        elif motor:
            new_x = self.box_x + 96 * dt
            if not gate and self.box_x < gate_stop_x:
                new_x = min(new_x, gate_stop_x)
            self.box_x = new_x
            if self.divert_armed and self.box_x >= divert_start_x:
                self.box_y_offset += 60 * dt
            if self.box_x > 500:
                self._spawn_next_box()
            self._animate_belt()

        self._set_box_coords()
        self.canvas.itemconfigure(self.motor_text, text="MOTOR ON" if motor else "MOTOR OFF", fill="#15803d" if motor else "#6b7280")

        self.canvas.itemconfigure(self.sensor1, fill="#22c55e" if signals.get("SENSOR1") else "#a7adb5")
        self.canvas.itemconfigure(self.sensor2, fill="#22c55e" if signals.get("SENSOR2") else "#a7adb5")

        if gate:
            self.canvas.coords(self.gate_bar, 448, 98, 512, 112)
            self.canvas.itemconfigure(self.gate_bar, fill="#22c55e", outline="#166534")
        else:
            self.canvas.coords(self.gate_bar, 448, 98, 462, 158)
            self.canvas.itemconfigure(self.gate_bar, fill="#efb846", outline="#805f10")

        if clamp:
            self.canvas.coords(self.clamp_head, 252, 126, 304, 142)
            self.canvas.coords(self.clamp_rod, 274, 68, 282, 126)
            self.canvas.itemconfigure(self.clamp_head, fill="#22c55e", outline="#166534")
        else:
            self.canvas.coords(self.clamp_head, 252, 94, 304, 110)
            self.canvas.coords(self.clamp_rod, 274, 68, 282, 94)
            self.canvas.itemconfigure(self.clamp_head, fill="#64748b", outline="#334155")

        if diverter:
            self.canvas.coords(self.diverter, 458, 210, 522, 210)
            self.canvas.itemconfigure(self.diverter, fill="#22c55e")
        else:
            self.canvas.coords(self.diverter, 458, 210, 520, 246)
            self.canvas.itemconfigure(self.diverter, fill="#2563eb")

        self.canvas.itemconfigure(self.ready_label, fill="#15803d" if ready else "#6b7280")

        if alarm:
            self.alarm_flash = not self.alarm_flash
            self.canvas.itemconfigure(self.alarm, fill="#ef4444" if self.alarm_flash else "#991b1b")
            self.canvas.itemconfigure(self.alarm_glow, fill="#fecaca" if self.alarm_flash else "")
        else:
            self.canvas.itemconfigure(self.alarm, fill="#7f1d1d")
            self.canvas.itemconfigure(self.alarm_glow, fill="")

    def auto_sensor_states(self) -> Dict[str, bool]:
        """Photo-eye sensors and box classifier derived from the animated box."""
        on_belt = self.box_y_offset < 4.0
        box_center = self.box_x + 26
        return {
            "SENSOR1": on_belt and 152 <= box_center <= 212,
            "SENSOR2": on_belt and 352 <= box_center <= 412,
            "BOX_TYPE": self.box_type,
        }

    def _spawn_next_box(self) -> None:
        self.box_x = 58.0
        self.box_y_offset = 0.0
        self.divert_armed = False
        self.box_type = not self.box_type
        self._apply_box_color()

    def _apply_box_color(self) -> None:
        colors = self.REJECT_COLORS if self.box_type else self.ACCEPT_COLORS
        self.canvas.itemconfigure(self.box_top, fill=colors["top"], outline=colors["outline"])
        self.canvas.itemconfigure(self.box_side, fill=colors["side"], outline=colors["outline"])
        self.canvas.itemconfigure(self.box_front, fill=colors["front"], outline=colors["outline"])
        self.canvas.itemconfigure(self.box_seam, fill=colors["seam"])

    def _set_box_coords(self) -> None:
        x = self.box_x
        y = self.box_y_offset
        self.canvas.coords(self.box_shadow, x - 2, 146 + y, x + 66, 166 + y)
        self.canvas.coords(self.box_top, *self._flat((x, 114 + y), (x + 52, 114 + y), (x + 66, 126 + y), (x + 14, 126 + y)))
        self.canvas.coords(self.box_side, *self._flat((x + 52, 114 + y), (x + 66, 126 + y), (x + 66, 154 + y), (x + 52, 154 + y)))
        self.canvas.coords(self.box_front, x, 126 + y, x + 52, 154 + y)
        self.canvas.coords(self.box_seam, x, 136 + y, x + 52, 136 + y)

    def _animate_belt(self) -> None:
        for line in self.belt_motion:
            x1, y1, x2, y2 = self.canvas.coords(line)
            x1 += 4
            x2 += 4
            if x1 > 500:
                x1, x2 = 62, 96
            self.canvas.coords(line, x1, y1, x2, y2)

    @staticmethod
    def _flat(*points: tuple[float, float]) -> tuple[float, ...]:
        values: list[float] = []
        for x, y in points:
            values.extend((x, y))
        return tuple(values)
