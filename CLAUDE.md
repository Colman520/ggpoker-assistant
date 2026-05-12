# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GGPoker 助手 v1.0 — a Windows-only real-time poker odds calculator that runs alongside the GGPoker client. Captures the poker table screen, recognizes cards via OpenCV, and computes win rates through Monte Carlo simulation. UI is in Simplified Chinese.

## Running and Testing

```bash
# Install dependencies
pip install -r requirements.txt

# GUI mode (default, falls back to CLI if PyQt6 unavailable)
python main.py

# CLI mode (no GUI required)
python main.py --cli

# Screen region calibration tool (requires GGPoker window open)
python calibration.py

# Card template extraction tool (requires GGPoker window open)
python template_generator.py

# Run all tests (8 stages: deps, imports, config, card parsing, odds, screen capture, recognizer, GUI)
python test_all.py

# Run preflop logic tests (13 assertions covering position, hand strength, table size)
python test_preflop.py
```

No pytest/unittest framework — tests use a custom `test(name, func)` helper with manual pass/fail tracking.

## Architecture

Flat module layout at the repo root. No subdirectories for source. No inheritance hierarchies — modules compose each other via `Config` object injection.

### Module Dependency Graph

```
main.py → config.py, screen_capture.py, card_recognition.py, odds_calculator.py, gui.py
gui.py  → config.py, screen_capture.py, card_recognition.py, odds_calculator.py,
           calibration.py (lazy), template_generator.py (lazy)
calibration.py, template_generator.py → config.py, screen_capture.py
```

### Key Modules

- **`config.py`** — `Config` class: dict-like wrapper around `config.json` with `DEFAULT_CONFIG` fallback and deep-merge loading. Access via `config["key"]`.
- **`main.py`** — Entry point. `main()` dispatches to `main_gui()` or `main_cli()` based on `--cli` flag. GUI falls back to CLI on import failure. Also provides `create_odds_calculator()` and `create_hand_evaluator()` factory functions.
- **`screen_capture.py`** — `ScreenCapture`: uses `mss` for screenshots + `win32gui` to find GGPoker window by title. Regions are relative fractions `[x, y, w, h]` of the window rect.
- **`card_recognition.py`** — `CardRecognizer` (template matching via OpenCV, HSV color detection for suits) and `ManualCardInput` (parses strings like `"Ah Kh"`).
- **`odds_calculator.py`** — `HandEvaluator` (5-card hand ranking with kickers) and `OddsCalculator` (Monte Carlo engine with range-aware opponent sampling, position-based ranges, board texture analysis, outs, pot odds, SPR, MDF, fold equity, bluff EV).
- **`hand_evaluator_two_plus_two.py`** — `HandEvaluatorTwoPlusTwo`: Two Plus Two algorithm for fast hand evaluation. Supports 5/6/7 card evaluation with precomputed lookup tables.
- **`odds_calculator_hybrid.py`** — `OddsCalculatorHybrid`: Hybrid odds calculator combining exact calculation and Monte Carlo simulation. Dynamically selects the best method based on scenario.
- **`generate_tables.py`** — `TableGenerator`: Generates lookup tables for Two Plus Two hand evaluator.
- **`gui.py`** — `PokerAssistantGUI`: PyQt6 frameless always-on-top overlay. Visual card selector dialogs (`CardSelectorDialog`). Calculation runs in `QThread` (`CalcWorker`). Auto-capture via `QTimer` (currently disabled — UI section is commented out).
- **`calibration.py`** — `RegionCalibrator`: interactive OpenCV tool to define screen capture regions.
- **`template_generator.py`** — `TemplateGenerator`: extracts rank/suit template images from GGPoker screenshots into `templates/ranks/` and `templates/suits/`.

### Data Flow (GUI)

1. User picks cards via `CardSelectorDialog` or auto-capture recognizes them from screen
2. User sets table parameters (size, position, opponents, pot/call amounts, opponent action)
3. "Calculate" → `OddsCalculator.calculate_odds()` runs Monte Carlo simulation (default 20,000 iterations)
4. Results displayed: win rate, equity, outs, pot odds, SPR, fold equity, EV, suggestion

### Data Flow (CLI)

Interactive REPL: prompts for hand, community cards, opponent count → runs calculation → prints formatted results.

## Configuration

`config.json` is the runtime config file (created on first save). `Config` class in `config.py` deep-merges saved values over `DEFAULT_CONFIG`. Key sections:

- **`regions`** — screen capture regions as `[x, y, w, h]` fractions (use `calibration.py` to set)
- **`recognition`** — template matching threshold, aspect ratios, color detection params
- **`gui`** — opacity, window position/dimensions, table size, position, stack sizes
- **`simulation_count`** — Monte Carlo iterations (default 20,000)
- **`algorithm`** — algorithm selection:
  - `hand_evaluator`: "two_plus_two" (default) or "cactus_kev"
  - `odds_calculator`: "hybrid" (default), "exact", or "monte_carlo"
  - `exact_calculation_threshold`: max combinations for exact calculation (default 1,000,000)
  - `monte_carlo_simulations`: default Monte Carlo iterations (default 10,000)
  - `table_path`: path to lookup tables directory (default "tables/")

### Algorithm Selection

The system supports two hand evaluators and three odds calculation methods:

**Hand Evaluators:**
- **Two Plus Two** (default): Uses precomputed lookup tables for fast 7-card evaluation. ~10x faster than Cactus Kev.
- **Cactus Kev**: Original algorithm using prime number encoding. Good compatibility.

**Odds Calculators:**
- **Hybrid** (default): Dynamically selects between exact calculation and Monte Carlo simulation based on scenario complexity.
- **Exact**: Enumerates all possible outcomes. 100% accurate but slow for complex scenarios.
- **Monte Carlo**: Random sampling simulation. Fast but has variance.

To switch algorithms, modify the `algorithm` section in `config.json`.

## Platform Constraints

- **Windows-only**: `screen_capture.py` depends on `pywin32` (`win32gui`, `win32con`) for window enumeration
- Template images (`templates/ranks/`, `templates/suits/`) are not in the repo — generate them with `template_generator.py` before using auto-capture
- Auto-capture feature is disabled in the current GUI (commented out in `gui.py`)
