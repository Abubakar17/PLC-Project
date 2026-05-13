# Mini PLC Logic Simulator

A Tkinter-based PLC training app inspired by FX-TRN concepts. It simulates a scan cycle, boolean logic, TON timers, output lamps, an event log, and a 2D conveyor cell with a gate, clamp, diverter, sensors, and alarm beacon.

## Run

```powershell
python main.py
```

## How To Proceed

1. Start the app with `python main.py`.
2. Choose an example from the drop-down list and press `LOAD EXAMPLE`.
3. Press `RUN`.
4. Turn `START` on.
5. In `AUTO` mode, the animated box triggers `SENSOR1` and `SENSOR2` as it moves.
6. Switch to `MANUAL` mode when you want to toggle sensors yourself.
7. Edit the program, press `RUN` again, and watch the output lamps and animation update.
8. Use `Reset Box` if you want to restart the physical animation from the beginning of the conveyor.

The bottom scan monitor shows whether the PLC is running, how many scans have executed, the most recent scan time, and the current Auto/Manual mode. The right-side timer monitor shows `T1` and `T2` accumulated time, preset time, enable state, and done state.

The editor includes line numbers and syntax highlighting for comments, assignment targets, operators, timers, literals, and signal names.

The Signal Watch table shows common internal bits such as `INSPECT_DONE`, `SORT_DONE`, `JAM`, `CELL_OK`, and timer done/enabled bits.

Force output mode lets you override output signals for teaching and debugging. Enable `Force outputs`, then use each output's force button. Forced outputs are applied after the logic scan, so they behave like a trainer/debug layer on top of the PLC program.

## What Each Sensor Does

`START`: operator start command. Most examples use it to permit the motor.

`STOP`: normal stop input. Most examples write `NOT STOP` so the conveyor stops when this input is on.

`ESTOP`: emergency stop/fault input. Use it to force motion outputs off and `ALARM` on.

`SENSOR1`: entry or inspection photo-eye near the clamp station. In Auto mode it turns on when the box reaches the left/middle station.

`SENSOR2`: exit or sorting photo-eye near the gate/diverter. In Auto mode it turns on when the box reaches the right station.

## Outputs

`MOTOR`: moves the conveyor and the box.

`GATE`: opens the exit gate.

`CLAMP`: lowers the inspection clamp onto the box.

`DIVERTER`: changes the sorting chute position.

`READY`: general OK/running lamp for user logic.

`ALARM`: flashes the red beacon.

`TIMER1_DONE`, `TIMER2_DONE`: visible timer done bits used by the example programs.

## Logic Examples

### Starter Conveyor

```text
MOTOR = START AND NOT STOP AND NOT ESTOP
T1 = TIMER(SENSOR1, 0.3)
TIMER1_DONE = T1_DONE
GATE = MOTOR AND NOT ESTOP
READY = MOTOR AND NOT ALARM
ALARM = ESTOP
```

This shows a basic conveyor permissive, a sensor proof timer, a gate that opens while the motor is permitted, and a simple emergency-stop alarm.

### Inspection Clamp

```text
T1 = TIMER(SENSOR1, 2.5)
TIMER1_DONE = T1_DONE
INSPECT_DONE = T1_DONE OR (INSPECT_DONE AND NOT STOP AND NOT ESTOP)
CLAMP = SENSOR1 AND NOT INSPECT_DONE AND NOT ESTOP
MOTOR = START AND NOT STOP AND NOT ESTOP AND NOT CLAMP
GATE = INSPECT_DONE AND NOT ESTOP
READY = START AND NOT ESTOP AND NOT CLAMP
ALARM = ESTOP OR (SENSOR2 AND NOT GATE)
```

This is a more complex sequence: the box reaches `SENSOR1`, the clamp holds it for an inspection dwell, `INSPECT_DONE` latches the completed state, the motor restarts, and the gate stays open.

### Sorting Diverter

```text
T2 = TIMER(SENSOR2, 1.5)
TIMER2_DONE = T2_DONE
SORT_DONE = T2_DONE OR (SORT_DONE AND SENSOR2)
MOTOR = START AND NOT STOP AND NOT ESTOP AND NOT (SENSOR2 AND NOT SORT_DONE)
DIVERTER = SORT_DONE AND NOT ESTOP
GATE = SENSOR2 OR DIVERTER
READY = MOTOR AND NOT DIVERTER AND NOT ALARM
ALARM = ESTOP
```

This demonstrates a second timer, a short motor pause at the sorting station, a latched sorting decision while the sensor is active, and the diverter output.

### NAND NOR Practice

```text
MOTOR = START NAND STOP
ALARM = SENSOR1 NOR SENSOR2
GATE = START AND NOT ESTOP
READY = NOT ALARM AND NOT ESTOP
DIVERTER = SENSOR2 AND READY
```

This is a small truth-table style program for experimenting with `NAND` and `NOR`.

### Jam Watchdog

```text
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
```

This uses two timers: one for normal inspection time and one as a longer watchdog. If inspection never completes while the box remains at `SENSOR1`, `JAM` turns on and raises `ALARM`.

### Safe Gate Interlock

```text
CELL_OK = START AND NOT STOP AND NOT ESTOP
EXIT_CLEAR = NOT SENSOR2
MOTOR = CELL_OK AND EXIT_CLEAR
GATE = CELL_OK AND EXIT_CLEAR
CLAMP = SENSOR1 AND CELL_OK
DIVERTER = SENSOR2 AND CELL_OK
READY = CELL_OK AND EXIT_CLEAR
ALARM = ESTOP OR (SENSOR2 AND GATE)
```

This demonstrates intermediate variables. `CELL_OK` and `EXIT_CLEAR` make the later output rules easier to read.

### Try It Yourself

The app includes a commented exercise where every logic line starts with `#`, so it does not execute yet. Remove one `#` at a time, press `RUN`, and watch how each output joins the process.

## Supported Logic

Supported operators: `AND`, `OR`, `NOT`, `NAND`, `NOR`.

Timer syntax:

```text
T1 = TIMER(SENSOR1, 3)
```

This exports `T1_EN`, `T1_DONE`, and `T1_ACC` internally. Dots are accepted in expressions too, so `T1.DONE` is normalized to `T1_DONE`.

## PLC Scan Cycle

Each scan does this:

```text
1. Read inputs
2. In AUTO mode, update SENSOR1 and SENSOR2 from the animated box position
3. Evaluate timers
4. Evaluate logic assignments
5. Write outputs
6. Update lamps, log entries, and the 2D animation
```

The app repeats this roughly every 75 ms using Tkinter's `after()` loop.

## Code Map

`main.py`: starts Tkinter and creates the simulator app.

`gui.py`: builds the input panel, logic editor, example loader, output lamps, guide text, event log, and scan loop.

`logic_engine.py`: parses lines like `MOTOR = START AND NOT ESTOP`, evaluates boolean expressions, and runs timer assignments before normal output assignments.

`timer.py`: implements a TON on-delay timer with `EN`, `DONE`, and `ACC`.

`simulation.py`: draws and animates the conveyor, moving box, clamp, gate, diverter, sensors, and alarm.

`signals.py`: owns the shared signal dictionary for inputs, outputs, timers, and internal bits.
