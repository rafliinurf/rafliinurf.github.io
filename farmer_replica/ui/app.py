"""Tkinter UI MVP untuk ladang dan editor script drone."""
import math
import re
import tkinter as tk
import time
from tkinter import font, messagebox

from game.accounts import AccountStore
from game.clock import Clock
from game.drone import Drone
from game.entities import load_entities
from game.inventory import Inventory
from game.progression import Progression
from game.save import load_game, save_game
from game.world import GRASSLAND, SOIL, World
from runtime.api import build_api, build_constants, build_statement_api
from runtime.interpreter import Interpreter
from ui.account_dialog import AccountDialog
from ui.tree_layout import RESEARCH_ROWS, layout_tree


class FarmerApp:
    MAX_EXECUTION_TICKS_PER_FRAME = 100

    COLORS = {
        "background": "#78868c",
        "topbar": "#46545b",
        "panel": "#30393c",
        "panel_header": "#20282b",
        "editor": "#252d30",
        "output": "#1b2326",
        "text": "#d8dfdc",
        "muted": "#93a09f",
        "green": "#94ad4d",
        "green_dark": "#627d39",
        "orange": "#d78745",
        "red": "#ba6256",
        "soil": "#806647",
        "soil_dark": "#5d4935",
        "grass": "#6f914b",
        "grass_alt": "#789b52",
    }

    AUTOSAVE_INTERVAL_MS = 10_000

    DEV_GRANT_ITEMS = (
        "hay",
        "wood",
        "carrot",
        "pumpkin",
        "cactus",
        "gold",
        "power",
        "water",
        "fertilizer",
        "weird_substance",
        "bone",
    )

    def __init__(self, root=None, username=None, save_path=None, account_tag="player"):
        self.root = root or tk.Tk()
        self.root.title("Farmer Replica")
        self.root.geometry("1440x900")
        self.root.minsize(960, 640)
        self.root.configure(bg=self.COLORS["background"])
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.world = World(1, load_entities())
        self.clock = Clock()
        self.inventory = Inventory()
        self.drone = Drone(self.world, self.clock, self.inventory)
        self.progression = Progression(self.inventory)
        self.world.tile(0, 0).age = self.world.defs["grass"].grow_ticks
        self.username = username
        self.account_tag = account_tag
        self.save_path = save_path
        self.developer_panel = None
        self._save_error = None
        self._saved_script = (
            load_game(
                self.save_path,
                self.world,
                self.inventory,
                self.progression,
                self.drone,
                self.clock,
            )
            if self.save_path is not None
            else ""
        )
        self._refresh_interpreter()
        self.steps = None
        self.running = False
        self.execution_tick_budget = 0.0
        self.execution_last_update = None
        self.idle_tick_budget = 0.0
        self.idle_last_update = time.perf_counter()
        self.harvest_animation = None
        self.current_code_span = None
        self.drag_offset = (0, 0)
        self.panel_drag_state = None
        self.panel_resize_state = None
        self.panel_maximized = {"editor": False, "output": False, "progression_dialog": False}
        self.panel_restore_geometry = {}
        self.panel_positions = {
            "editor": (790, 24),
            "output": (12, 12),
            "progression_dialog": None,
        }
        self.editor_size = (610, 690)
        self.editor_minimized = False
        self.output_minimized = False
        self.output_content = None
        self.progression_dialog_size = (560, 640)
        self.progression_dialog_position = None
        self.progression_dialog_body = None
        self.inventory_labels = {}
        self.research_window = None
        self.research_maximized = False
        self.research_restore_geometry = None
        self.research_canvas = None
        self.research_detail_frame = None
        self.research_detail_content = None
        self.progression_dialog = None
        self.progression_dialog_content = None
        self.progression_dialog_canvas = None
        self.progression_dialog_window_id = None
        self.progression_dialog_body = None
        self.progression_dialog_title = None
        self.progression_dialog_drag_offset = (0, 0)
        self.progression_dialog_minimized = False
        self.progression_dialog_mode = None
        self.selected_unlock = None
        self.tutorial_seen = set()
        self.research_zoom = 0.8
        self.research_pan_origin = None
        self.research_state_snapshot = None

        self._build_topbar()
        self._build_workspace()
        self._build_output()
        self._build_editor()
        if self._saved_script:
            self.code_text.insert("1.0", self._saved_script)
            self._update_code_decoration()
        self._update_hud()
        self._render_world()
        self._append_output("Ready. Edit the script and press Run.")
        self.root.after(80, self._show_intro_dialog)
        self.root.after(50, self._advance_idle_world)
        if self.save_path is not None:
            self.root.after(self.AUTOSAVE_INTERVAL_MS, self._autosave_progress)

    def run(self):
        self.root.mainloop()

    def close(self):
        self.running = False
        self.steps = None
        try:
            self._save_progress()
        except OSError as exc:
            messagebox.showerror(
                "Progres belum tersimpan",
                f"Progres akun {self.username} gagal disimpan:\n{exc}",
                parent=self.root,
            )
            return
        self.root.destroy()

    def _save_progress(self):
        if self.save_path is None:
            return
        save_game(
            self.save_path,
            self.world,
            self.inventory,
            self.progression,
            self.drone,
            self.clock,
            self.code_text.get("1.0", "end-1c"),
        )

    def _autosave_progress(self):
        try:
            self._save_progress()
        except OSError as exc:
            error = str(exc)
            if error != self._save_error:
                self._append_output(f"Autosave failed: {error}")
            self._save_error = error
        else:
            if self._save_error is not None:
                self._append_output("Autosave recovered.")
            self._save_error = None
        self.root.after(self.AUTOSAVE_INTERVAL_MS, self._autosave_progress)

    def _build_topbar(self):
        bar = tk.Frame(self.root, bg=self.COLORS["topbar"], height=56)
        bar.pack(side="top", fill="x")
        bar.pack_propagate(False)

        title = tk.Label(
            bar,
            text="FARMER REPLICA",
            bg=self.COLORS["topbar"],
            fg=self.COLORS["text"],
            font=("Bahnschrift SemiBold", 12),
        )
        title.pack(side="left", padx=(22, 26))

        if self.username:
            tk.Label(
                bar,
                text=f"ACCOUNT  {self.username}  [{self.account_tag.upper()}]",
                bg=self.COLORS["topbar"],
                fg=self.COLORS["muted"],
                font=("Consolas", 9),
            ).pack(side="left", padx=(0, 18))

        resources = tk.Frame(bar, bg=self.COLORS["topbar"])
        resources.pack(side="left", fill="y")
        for item in ("hay", "wood", "carrot", "water"):
            group = tk.Frame(resources, bg=self.COLORS["topbar"])
            group.pack(side="left", padx=12, pady=8)
            tk.Label(
                group,
                text=item.upper(),
                bg=self.COLORS["topbar"],
                fg=self.COLORS["muted"],
                font=("Consolas", 8, "bold"),
            ).pack(anchor="w")
            value = tk.Label(
                group,
                text=self._format_resource_count(0),
                bg=self.COLORS["topbar"],
                fg=self.COLORS["text"],
                font=("Consolas", 11, "bold"),
                width=6,
                anchor="w",
            )
            value.pack(anchor="w")
            self.inventory_labels[item] = value
            group.configure(width=64, height=40)
            group.pack_propagate(False)

        if self.account_tag == "developer":
            tk.Button(
                bar,
                text="DEV ITEMS",
                command=self._open_developer_panel,
                bg="#765b32",
                fg="#ffffff",
                activebackground="#9b7540",
                relief="flat",
                padx=10,
                pady=6,
                font=("Consolas", 8, "bold"),
            ).pack(side="left", padx=(6, 0))

        self.tick_label = tk.Label(
            bar,
            text="TICK 000000",
            bg=self.COLORS["topbar"],
            fg=self.COLORS["text"],
            font=("Consolas", 10, "bold"),
        )
        self.tick_label.pack(side="right", padx=20)

        self.code_toggle = tk.Button(
            bar,
            text="CODE",
            command=self._toggle_editor,
            bg=self.COLORS["green_dark"],
            fg="#ffffff",
            activebackground=self.COLORS["green"],
            activeforeground="#172018",
            relief="flat",
            padx=14,
            pady=7,
            font=("Consolas", 9, "bold"),
        )
        self.code_toggle.pack(side="right", padx=8)

        self.output_toggle = tk.Button(
            bar,
            text="OUTPUT",
            command=self._toggle_output,
            bg=self.COLORS["panel_header"],
            fg=self.COLORS["text"],
            activebackground=self.COLORS["panel"],
            relief="flat",
            padx=12,
            pady=7,
            font=("Consolas", 9, "bold"),
        )
        self.output_toggle.pack(side="right", padx=8)

        self.guide_button = tk.Button(
            bar,
            text="GUIDE",
            command=self._toggle_progression_dialog,
            bg=self.COLORS["green_dark"],
            fg="#ffffff",
            activebackground=self.COLORS["green"],
            activeforeground="#ffffff",
            relief="flat",
            padx=13,
            pady=7,
            font=("Consolas", 9, "bold"),
        )
        self.guide_button.pack(side="right", padx=8)

        self.research_button = tk.Button(
            bar,
            text="RESEARCH",
            command=self._open_research,
            bg="#8d9864",
            fg="#182019",
            activebackground="#aab678",
            relief="flat",
            padx=13,
            pady=7,
            font=("Consolas", 9, "bold"),
        )
        self.research_button.pack(side="right", padx=8)

        self.field_label = tk.Label(
            bar,
            text="FIELD 1x1",
            bg=self.COLORS["topbar"],
            fg=self.COLORS["muted"],
            font=("Consolas", 9),
        )
        self.field_label.pack(side="right", padx=8)

    def _build_workspace(self):
        self.workspace = tk.Frame(self.root, bg=self.COLORS["background"])
        self.workspace.pack(side="top", fill="both", expand=True)
        self.workspace.bind("<Configure>", self._resize_maximized_panels)
        self.canvas = tk.Canvas(
            self.workspace,
            bg=self.COLORS["background"],
            highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _event: self._render_world())

    def _build_output(self):
        self.output_panel = tk.Frame(
            self.workspace,
            bg=self.COLORS["panel"],
            highlightthickness=1,
            highlightbackground="#a1aa9c",
        )
        self.output_panel.place(
            x=12,
            y=12,
            width=420,
            height=106,
        )
        self.output_panel_size = (420, 106)
        header = tk.Frame(self.output_panel, bg=self.COLORS["panel_header"], height=30)
        header.pack(side="top", fill="x")
        header.pack_propagate(False)
        title = tk.Label(
            header,
            text="OUTPUT",
            bg=self.COLORS["panel_header"],
            fg=self.COLORS["muted"],
            font=("Consolas", 8, "bold"),
            anchor="w",
        )
        title.pack(side="left", fill="y", padx=12)
        for widget in (header, title):
            widget.bind("<ButtonPress-1>", lambda event: self._start_panel_drag(event, "output"))
            widget.bind("<B1-Motion>", lambda event: self._drag_panel(event, "output"))
        self.output_minimize_button = tk.Button(
            header,
            text="_",
            command=self._minimize_output,
            bg=self.COLORS["panel_header"],
            fg=self.COLORS["muted"],
            activebackground=self.COLORS["panel"],
            relief="flat",
            width=4,
        )
        self.output_minimize_button.pack(side="right", fill="y")
        self.output_maximize_button = tk.Button(
            header,
            text="MAX",
            command=lambda: self._toggle_panel_maximize("output"),
            bg=self.COLORS["panel_header"],
            fg=self.COLORS["muted"],
            activebackground=self.COLORS["panel"],
            relief="flat",
            padx=5,
        )
        self.output_maximize_button.pack(side="right", fill="y")
        tk.Button(
            header,
            text="X",
            command=self._close_output,
            bg=self.COLORS["panel_header"],
            fg=self.COLORS["muted"],
            activebackground=self.COLORS["panel"],
            relief="flat",
            width=4,
        ).pack(side="right", fill="y")
        self._add_panel_resize_grip(self.output_panel, "output")
        self.output_content = tk.Frame(self.output_panel, bg=self.COLORS["panel"])
        self.output_content.pack(fill="both", expand=True, padx=8, pady=(0, 7))
        self.output = tk.Text(
            self.output_content,
            height=3,
            bg=self.COLORS["output"],
            fg=self.COLORS["text"],
            insertbackground=self.COLORS["text"],
            font=("Consolas", 9),
            relief="flat",
            wrap="word",
            state="disabled",
        )
        self.output.pack(fill="both", expand=True)
        self.root.after(80, self._position_output_panel_initial)

    def _build_editor(self):
        self.editor = tk.Frame(
            self.workspace,
            bg=self.COLORS["panel"],
            highlightthickness=1,
            highlightbackground="#a1aa9c",
        )
        self.editor.place(
            x=790,
            y=24,
            width=self.editor_size[0],
            height=self.editor_size[1],
        )

        titlebar = tk.Frame(self.editor, bg=self.COLORS["panel_header"], height=38)
        titlebar.pack(side="top", fill="x")
        titlebar.pack_propagate(False)
        title = tk.Label(
            titlebar,
            text="DRONE CODE",
            bg=self.COLORS["panel_header"],
            fg=self.COLORS["text"],
            font=("Consolas", 9, "bold"),
            anchor="w",
        )
        title.pack(side="left", fill="y", padx=12)
        for widget in (titlebar, title):
            widget.bind("<ButtonPress-1>", lambda event: self._start_panel_drag(event, "editor"))
            widget.bind("<B1-Motion>", lambda event: self._drag_panel(event, "editor"))

        tk.Button(
            titlebar,
            text="_",
            command=self._minimize_editor,
            bg=self.COLORS["panel_header"],
            fg=self.COLORS["muted"],
            activebackground=self.COLORS["panel"],
            relief="flat",
            width=4,
        ).pack(side="right", fill="y")
        tk.Button(
            titlebar,
            text="X",
            command=self._close_editor,
            bg=self.COLORS["panel_header"],
            fg=self.COLORS["muted"],
            activebackground=self.COLORS["panel"],
            relief="flat",
            width=4,
        ).pack(side="right", fill="y")
        self.editor_maximize_button = tk.Button(
            titlebar,
            text="MAX",
            command=lambda: self._toggle_panel_maximize("editor"),
            bg=self.COLORS["panel_header"],
            fg=self.COLORS["muted"],
            activebackground=self.COLORS["panel"],
            relief="flat",
            padx=5,
        )
        self.editor_maximize_button.pack(side="right", fill="y")

        controls = tk.Frame(self.editor, bg=self.COLORS["panel"], height=44)
        controls.pack(side="top", fill="x", padx=10, pady=8)
        controls.pack_propagate(False)
        self.run_button = tk.Button(
            controls,
            text="RUN",
            command=self._run_script,
            bg=self.COLORS["green"],
            fg="#172018",
            activebackground="#abc65c",
            relief="flat",
            padx=18,
            font=("Consolas", 9, "bold"),
        )
        self.run_button.pack(side="left", padx=(0, 6), pady=3)
        self.stop_button = tk.Button(
            controls,
            text="STOP",
            command=self._stop_script,
            bg=self.COLORS["red"],
            fg="#ffffff",
            activebackground="#d27b6d",
            relief="flat",
            padx=16,
            font=("Consolas", 9, "bold"),
            state="disabled",
        )
        self.stop_button.pack(side="left", pady=3)

        editor_area = tk.Frame(self.editor, bg=self.COLORS["editor"])
        editor_area.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        self.line_numbers = tk.Text(
            editor_area,
            width=4,
            bg=self.COLORS["editor"],
            fg="#69777a",
            font=("Consolas", 10),
            relief="flat",
            padx=7,
            pady=10,
            state="disabled",
            takefocus=False,
        )
        self.line_numbers.pack(side="left", fill="y")
        self.code_text = tk.Text(
            editor_area,
            bg=self.COLORS["editor"],
            fg="#d6dedb",
            insertbackground="#f0c674",
            selectbackground="#43534f",
            font=("Consolas", 10),
            relief="flat",
            padx=5,
            pady=10,
            undo=True,
            wrap="none",
            yscrollcommand=self._sync_scroll,
        )
        self.code_text.pack(side="left", fill="both", expand=True)
        scrollbar = tk.Scrollbar(editor_area, command=self._scroll_code)
        scrollbar.pack(side="right", fill="y")
        self.code_text.configure(yscrollcommand=scrollbar.set)
        self.code_text.bind("<Return>", self._auto_indent_code)
        self.code_text.bind("<KeyPress>", self._handle_code_keypress)
        self.code_text.bind("<KeyRelease>", self._update_code_decoration)
        self._update_code_decoration()

        self.action_label = tk.Label(
            self.editor,
            text="READY",
            bg=self.COLORS["panel"],
            fg=self.COLORS["muted"],
            font=("Consolas", 8),
            anchor="w",
        )
        self.action_label.pack(side="bottom", fill="x", padx=12, pady=(0, 8))
        self._add_panel_resize_grip(self.editor, "editor")
        self.root.after(80, self._position_editor_initial)

    def _sync_scroll(self, first, last):
        self.line_numbers.yview_moveto(first)

    def _scroll_code(self, *args):
        self.code_text.yview(*args)
        self.line_numbers.yview(*args)

    def _auto_indent_code(self, _event=None):
        line_start = self.code_text.index("insert linestart")
        line = self.code_text.get(line_start, "insert")
        indent = re.match(r"[ \t]*", line).group()
        content = line[len(indent):]
        if not content.strip():
            indent = indent[:-4] if indent.endswith("    ") else ""
        elif content.rstrip().endswith(":"):
            indent += "    "
        self.code_text.insert("insert", "\n" + indent)
        self._update_code_decoration()
        return "break"

    def _handle_code_keypress(self, event):
        pairs = {"(": ")", "[": "]", "{": "}"}
        closing = set(pairs.values())
        if event.char in pairs:
            selection = self.code_text.tag_ranges("sel")
            if selection:
                selected_text = self.code_text.get(*selection)
                self.code_text.delete(*selection)
                self.code_text.insert(
                    "insert",
                    event.char + selected_text + pairs[event.char],
                )
                self.code_text.mark_set(
                    "insert",
                    f"insert - {len(selected_text) + 1} chars",
                )
            else:
                self.code_text.insert("insert", event.char + pairs[event.char])
                self.code_text.mark_set("insert", "insert - 1 chars")
            self._update_code_decoration()
            return "break"
        if event.char in closing and self.code_text.get("insert", "insert + 1 chars") == event.char:
            self.code_text.mark_set("insert", "insert + 1 chars")
            return "break"
        return None

    def _update_code_decoration(self, _event=None):
        line_count = int(self.code_text.index("end-1c").split(".")[0])
        numbers = "\n".join(str(number) for number in range(1, line_count + 1))
        self.line_numbers.configure(state="normal")
        self.line_numbers.delete("1.0", "end")
        self.line_numbers.insert("1.0", numbers)
        self.line_numbers.configure(state="disabled")

        for tag in ("keyword", "api", "comment", "constant"):
            self.code_text.tag_remove(tag, "1.0", "end")
        self.code_text.tag_configure("keyword", foreground="#c792ea")
        self.code_text.tag_configure("api", foreground="#82c7a5")
        self.code_text.tag_configure("comment", foreground="#77847f")
        self.code_text.tag_configure("constant", foreground="#e4b96a")
        content = self.code_text.get("1.0", "end-1c")
        patterns = {
            "keyword": r"\b(if|else|for|while|in|not)\b",
            "api": r"\b(clear|move|can_harvest|harvest|till|plant|get_ground_type|range|get_cost|get_time|get_tick_count|min|max|abs|random)\b(?=\s*\()",
            "constant": r"\b(Grounds|Soil|Grassland|Entities|Bush|North|East|South|West)\b",
            "comment": r"#.*",
        }
        for tag, pattern in patterns.items():
            for match in re.finditer(pattern, content):
                start = f"1.0+{match.start()}c"
                end = f"1.0+{match.end()}c"
                self.code_text.tag_add(tag, start, end)

        self.code_text.tag_configure(
            "current_code",
            background=self.COLORS["editor"],
            foreground="#ffffff",
            relief="solid",
            borderwidth=1,
        )
        if self.current_code_span is not None:
            self._highlight_code_span(*self.current_code_span, force=True)

    def _highlight_code_span(
        self,
        line_number,
        column_start=None,
        end_line=None,
        column_end=None,
        force=False,
    ):
        span = (
            None
            if line_number is None
            else (line_number, column_start, end_line, column_end)
        )
        if not force and self.current_code_span == span:
            return
        self.current_code_span = span
        self.code_text.tag_remove("current_code", "1.0", "end")
        if line_number is None:
            return
        last_line = int(self.code_text.index("end-1c").split(".")[0])
        if (
            not 1 <= line_number <= last_line
            or end_line is None
            or column_start is None
            or column_end is None
            or not line_number <= end_line <= last_line
        ):
            return
        start = f"{line_number}.{column_start}"
        end = f"{end_line}.{column_end}"
        self.code_text.tag_add("current_code", start, end)
        self.code_text.tag_raise("current_code")
        self.code_text.see(start)
        self.line_numbers.see(f"{line_number}.0")

    def _add_panel_resize_grip(self, panel, panel_name):
        grip = tk.Label(
            panel,
            text="///",
            bg=self.COLORS["panel_header"],
            fg=self.COLORS["muted"],
            cursor="size_nw_se",
            font=("Consolas", 8),
        )
        grip.place(relx=1, rely=1, anchor="se", width=30, height=18)
        grip.bind(
            "<ButtonPress-1>",
            lambda event: self._start_panel_resize(event, panel_name),
        )
        grip.bind(
            "<B1-Motion>",
            lambda event: self._resize_panel(event, panel_name),
        )
        grip.bind("<ButtonRelease-1>", lambda _event: self._stop_panel_resize())

    def _start_panel_drag(self, event, panel_name):
        if self.panel_maximized.get(panel_name, False):
            return
        panel = self._get_panel(panel_name)
        if panel is None:
            return
        self.panel_drag_state = (
            panel_name,
            event.x_root - panel.winfo_rootx(),
            event.y_root - panel.winfo_rooty(),
        )

    def _drag_panel(self, event, panel_name):
        if self.panel_drag_state is None or self.panel_drag_state[0] != panel_name:
            return
        panel = self._get_panel(panel_name)
        _, offset_x, offset_y = self.panel_drag_state
        x = event.x_root - self.workspace.winfo_rootx() - offset_x
        y = event.y_root - self.workspace.winfo_rooty() - offset_y
        max_x = max(0, self.workspace.winfo_width() - panel.winfo_width())
        max_y = max(0, self.workspace.winfo_height() - 38)
        x, y = max(0, min(x, max_x)), max(0, min(y, max_y))
        panel.place_configure(x=x, y=y)
        if panel_name == "progression_dialog":
            self.progression_dialog_position = (x, y)
        else:
            self.panel_positions[panel_name] = (x, y)

    def _start_panel_resize(self, event, panel_name):
        if self.panel_maximized[panel_name]:
            self._toggle_panel_maximize(panel_name)
        panel = self._get_panel(panel_name)
        self.panel_resize_state = (
            panel_name,
            event.x_root,
            event.y_root,
            panel.winfo_width(),
            panel.winfo_height(),
        )

    def _resize_panel(self, event, panel_name):
        if self.panel_resize_state is None or self.panel_resize_state[0] != panel_name:
            return
        panel = self._get_panel(panel_name)
        _, start_x, start_y, start_width, start_height = self.panel_resize_state
        min_width = 420 if panel_name == "progression_dialog" else 300
        min_height = 400 if panel_name == "progression_dialog" else 180
        x, y = int(panel.place_info()["x"]), int(panel.place_info()["y"])
        width = min(
            max(min_width, start_width + event.x_root - start_x),
            max(min_width, self.workspace.winfo_width() - x),
        )
        height = min(
            max(min_height, start_height + event.y_root - start_y),
            max(min_height, self.workspace.winfo_height() - y),
        )
        panel.place_configure(width=width, height=height)
        if panel_name == "editor":
            self.editor_size = (width, height)
        elif panel_name == "output":
            self.output_panel_size = (width, height)
        else:
            self.progression_dialog_size = (width, height)

    def _stop_panel_resize(self):
        self.panel_resize_state = None

    def _get_panel(self, panel_name):
        if panel_name == "editor":
            return self.editor
        if panel_name == "progression_dialog":
            return self.progression_dialog
        return self.output_panel

    def _resize_maximized_panels(self, _event=None):
        width = self.workspace.winfo_width()
        height = self.workspace.winfo_height()
        for name, panel in (
            ("editor", getattr(self, "editor", None)),
            ("output", getattr(self, "output_panel", None)),
            ("progression_dialog", getattr(self, "progression_dialog", None)),
        ):
            if (
                self.panel_maximized[name]
                and panel is not None
                and panel.winfo_exists()
                and panel.winfo_manager()
            ):
                panel.place_configure(x=0, y=0, width=width, height=height)

    def _toggle_panel_maximize(self, panel_name):
        panel = self._get_panel(panel_name)
        if not panel.winfo_manager():
            return
        if panel_name == "editor" and self.editor_minimized:
            return
        if panel_name == "output" and self.output_minimized:
            return
        if panel_name == "progression_dialog" and self.progression_dialog_minimized:
            return
        if self.panel_maximized[panel_name]:
            x, y, width, height = self.panel_restore_geometry.pop(panel_name)
            panel.place_configure(x=x, y=y, width=width, height=height)
            self.panel_maximized[panel_name] = False
        else:
            info = panel.place_info()
            self.panel_restore_geometry[panel_name] = (
                int(info["x"]),
                int(info["y"]),
                panel.winfo_width(),
                panel.winfo_height(),
            )
            panel.place_configure(
                x=0,
                y=0,
                width=self.workspace.winfo_width(),
                height=self.workspace.winfo_height(),
            )
            self.panel_maximized[panel_name] = True
        label = "REST" if self.panel_maximized[panel_name] else "MAX"
        getattr(self, f"{panel_name}_maximize_button").configure(text=label)
        panel.lift()
        if not self.panel_maximized[panel_name]:
            if panel_name == "editor":
                self.panel_positions["editor"] = (x, y)
                self.editor_size = (width, height)
            elif panel_name == "output":
                self.panel_positions["output"] = (x, y)
                self.output_panel_size = (width, height)
            else:
                self.progression_dialog_position = (x, y)
                self.progression_dialog_size = (width, height)

    def _position_output_panel_initial(self):
        if (
            self.output_panel.winfo_exists()
            and self.panel_positions["output"] == (12, 12)
        ):
            y = max(12, self.workspace.winfo_height() - self.output_panel_size[1] - 12)
            self.output_panel.place_configure(y=y)
            self.panel_positions["output"] = (12, y)

    def _position_editor_initial(self):
        if (
            self.editor.winfo_exists()
            and self.editor.winfo_manager()
            and self.panel_positions["editor"] == (790, 24)
        ):
            x = min(790, max(0, self.workspace.winfo_width() - self.editor_size[0]))
            self.editor.place_configure(x=x)
            self.panel_positions["editor"] = (x, 24)

    def _minimize_output(self):
        if self.output_minimized:
            return
        if self.panel_maximized["output"]:
            self._toggle_panel_maximize("output")
        self.output_panel_size = (self.output_panel.winfo_width(), self.output_panel.winfo_height())
        self.output_content.pack_forget()
        self.output_minimized = True
        self.output_panel.place_configure(height=30)

    def _restore_output(self):
        if self.output_minimized:
            self.output_content.pack(fill="both", expand=True, padx=8, pady=(0, 7))
            self.output_minimized = False
        if not self.output_panel.winfo_manager():
            x, y = self.panel_positions["output"]
            self.output_panel.place(x=x, y=y, width=self.output_panel_size[0], height=self.output_panel_size[1])
        else:
            self.output_panel.place_configure(width=self.output_panel_size[0], height=self.output_panel_size[1])
        self.panel_positions["output"] = (
            int(self.output_panel.place_info()["x"]),
            int(self.output_panel.place_info()["y"]),
        )
        self.output_panel.lift()

    def _toggle_output(self):
        self._restore_output()

    def _close_output(self):
        if self.panel_maximized["output"]:
            self._toggle_panel_maximize("output")
        if not self.output_minimized:
            self.output_panel_size = (self.output_panel.winfo_width(), self.output_panel.winfo_height())
        self.panel_positions["output"] = (
            int(self.output_panel.place_info()["x"]),
            int(self.output_panel.place_info()["y"]),
        )
        self.output_panel.place_forget()

    def _drag_editor(self, event):
        self._drag_panel(event, "editor")

    def _minimize_editor(self):
        if self.editor_minimized:
            return
        if self.panel_maximized["editor"]:
            self._toggle_panel_maximize("editor")
        self.editor_size = (self.editor.winfo_width(), self.editor.winfo_height())
        self.editor_minimized = True
        self.editor.place_configure(height=38)

    def _close_editor(self):
        if self.panel_maximized["editor"]:
            self._toggle_panel_maximize("editor")
        if not self.editor_minimized:
            self.editor_size = (self.editor.winfo_width(), self.editor.winfo_height())
        self.panel_positions["editor"] = (
            int(self.editor.place_info()["x"]),
            int(self.editor.place_info()["y"]),
        )
        self.editor_minimized = False
        self.editor.place_forget()

    def _toggle_editor(self):
        if not self.editor.winfo_manager():
            x, y = self.panel_positions["editor"]
            self.editor.place(
                x=min(x, max(0, self.workspace.winfo_width() - self.editor_size[0])),
                y=min(y, max(0, self.workspace.winfo_height() - 38)),
                width=self.editor_size[0],
                height=self.editor_size[1],
            )
            self.editor_minimized = False
        elif self.editor_minimized:
            self.editor.place_configure(height=self.editor_size[1], width=self.editor_size[0])
            self.editor_minimized = False
        self.editor.lift()

    def _run_script(self):
        if self.running:
            return
        self._highlight_code_span(None)
        self.clock.start_execution()
        self.steps = self.interpreter.run(self.code_text.get("1.0", "end-1c"))
        self.execution_tick_budget = 0.0
        self.execution_last_update = time.perf_counter()
        self.idle_last_update = self.execution_last_update
        self.harvest_animation = None
        self.running = True
        self.run_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.action_label.configure(text="RUNNING")
        self._append_output("Running script...")
        self._advance_execution()

    def _refresh_interpreter(self):
        self.interpreter = Interpreter(
            build_api(self.drone, self.progression),
            build_statement_api(self.drone, self.progression),
            build_constants(self.progression),
            self.progression.features(),
        )

    def _execution_steps_for_frame(self, elapsed_seconds):
        elapsed_seconds = max(0.0, elapsed_seconds)
        self.execution_tick_budget += (
            elapsed_seconds
            * 400
            * self.progression.speed_multiplier()
        )
        steps = min(
            int(self.execution_tick_budget),
            self.MAX_EXECUTION_TICKS_PER_FRAME,
        )
        self.execution_tick_budget -= steps
        return steps

    def _advance_idle_elapsed(self, elapsed_seconds):
        self.idle_tick_budget += (
            max(0.0, elapsed_seconds)
            * 400
            * self.progression.speed_multiplier()
        )
        ticks = min(
            int(self.idle_tick_budget),
            self.MAX_EXECUTION_TICKS_PER_FRAME,
        )
        self.idle_tick_budget -= ticks
        if ticks:
            self.clock.advance(ticks)
            self.drone._advance_world(ticks)
        return ticks

    def _open_research(self):
        if self.research_window is not None and self.research_window.winfo_exists():
            self.research_window.deiconify()
            self.research_window.lift()
            self.research_window.focus_force()
            self._draw_research_graph()
            return

        window = tk.Toplevel(self.root)
        self.research_window = window
        window.title("Research")
        window.configure(bg=self.COLORS["panel"])
        window.resizable(True, True)
        window.transient(self.root)
        window.geometry("1080x720+120+80")
        window.minsize(820, 560)
        window.protocol("WM_DELETE_WINDOW", self._close_research)
        window.lift()
        window.focus_force()

        titlebar = tk.Frame(window, bg=self.COLORS["panel_header"], height=38)
        titlebar.pack(fill="x")
        titlebar.pack_propagate(False)
        tk.Label(
            titlebar,
            text="RESEARCH",
            bg=self.COLORS["panel_header"],
            fg=self.COLORS["text"],
            font=("Consolas", 9, "bold"),
            anchor="w",
        ).pack(side="left", fill="y", padx=12)
        tk.Button(
            titlebar,
            text="_",
            command=window.iconify,
            bg=self.COLORS["panel_header"],
            fg=self.COLORS["muted"],
            activebackground=self.COLORS["panel"],
            relief="flat",
            width=4,
        ).pack(side="right", fill="y")
        self.research_maximize_button = tk.Button(
            titlebar,
            text="MAX",
            command=self._toggle_research_maximize,
            bg=self.COLORS["panel_header"],
            fg=self.COLORS["muted"],
            activebackground=self.COLORS["panel"],
            relief="flat",
            padx=5,
        )
        self.research_maximize_button.pack(side="right", fill="y")
        tk.Button(
            titlebar,
            text="X",
            command=self._close_research,
            bg=self.COLORS["panel_header"],
            fg=self.COLORS["muted"],
            activebackground=self.COLORS["panel"],
            relief="flat",
            width=4,
        ).pack(side="right", fill="y")

        zoom_controls = tk.Frame(window, bg=self.COLORS["panel"])
        zoom_controls.pack(fill="x", padx=12, pady=(8, 0))
        tk.Button(
            zoom_controls,
            text="FIT",
            command=self._fit_research_tree,
            bg=self.COLORS["panel_header"],
            fg=self.COLORS["text"],
            activebackground=self.COLORS["panel"],
            relief="flat",
            padx=10,
        ).pack(side="right", padx=(8, 0))
        tk.Button(
            zoom_controls,
            text="+",
            command=lambda: self._set_research_zoom(self.research_zoom * 1.2),
            bg=self.COLORS["panel_header"],
            fg=self.COLORS["text"],
            activebackground=self.COLORS["panel"],
            relief="flat",
            width=3,
        ).pack(side="right", padx=(4, 0))
        tk.Button(
            zoom_controls,
            text="-",
            command=lambda: self._set_research_zoom(self.research_zoom / 1.2),
            bg=self.COLORS["panel_header"],
            fg=self.COLORS["text"],
            activebackground=self.COLORS["panel"],
            relief="flat",
            width=3,
        ).pack(side="right")
        self.research_zoom_label = tk.Label(
            zoom_controls,
            text="80%",
            bg=self.COLORS["panel"],
            fg=self.COLORS["muted"],
            font=("Consolas", 8),
        )
        self.research_zoom_label.pack(side="right", padx=8)
        tk.Label(
            zoom_controls,
            text="ZOOM",
            bg=self.COLORS["panel"],
            fg=self.COLORS["muted"],
            font=("Consolas", 8, "bold"),
        ).pack(side="right", padx=(0, 2))

        research_body = tk.Frame(window, bg=self.COLORS["panel"])
        research_body.pack(fill="both", expand=True, padx=12, pady=12)
        graph_frame = tk.Frame(research_body, bg="#647177")
        graph_frame.pack(side="left", fill="both", expand=True)
        self.research_graph_frame = graph_frame
        self.research_canvas = tk.Canvas(
            graph_frame,
            bg="#647177",
            highlightthickness=0,
        )
        self.research_canvas.pack(fill="both", expand=True)
        self.research_canvas.bind("<Configure>", lambda _event: self._draw_research_graph())
        self.research_canvas.bind("<ButtonPress-1>", self._research_pan_start)
        self.research_canvas.bind("<B1-Motion>", self._research_pan_move)
        self.research_canvas.bind("<MouseWheel>", self._research_zoom)

        detail_panel = tk.Frame(
            research_body,
            bg=self.COLORS["panel"],
            width=330,
            highlightthickness=1,
            highlightbackground="#647177",
        )
        detail_panel.pack(side="right", fill="y", padx=(12, 0))
        detail_panel.pack_propagate(False)
        tk.Label(
            detail_panel,
            text="NODE DETAILS",
            bg=self.COLORS["panel_header"],
            fg=self.COLORS["text"],
            anchor="w",
            padx=12,
            pady=12,
            font=("Consolas", 9, "bold"),
        ).pack(fill="x")
        detail_canvas_frame = tk.Frame(detail_panel, bg=self.COLORS["panel"])
        detail_canvas_frame.pack(fill="both", expand=True)
        detail_canvas = tk.Canvas(
            detail_canvas_frame,
            bg=self.COLORS["panel"],
            highlightthickness=0,
        )
        detail_scrollbar = tk.Scrollbar(
            detail_canvas_frame,
            command=detail_canvas.yview,
        )
        detail_canvas.configure(yscrollcommand=detail_scrollbar.set)
        detail_canvas.pack(side="left", fill="both", expand=True)
        detail_scrollbar.pack(side="right", fill="y")
        detail_content = tk.Frame(detail_canvas, bg=self.COLORS["panel"])
        detail_window = detail_canvas.create_window(
            (0, 0),
            window=detail_content,
            anchor="nw",
        )
        detail_content.bind(
            "<Configure>",
            lambda _event: detail_canvas.configure(
                scrollregion=detail_canvas.bbox("all")
            ),
        )
        detail_canvas.bind(
            "<Configure>",
            lambda event: detail_canvas.itemconfigure(
                detail_window,
                width=event.width,
            ),
        )
        self.research_detail_frame = detail_panel
        self.research_detail_content = detail_content

        self._draw_research_graph()
        if self.selected_unlock is not None:
            self._render_research_inline_detail(self.selected_unlock)
        window.after_idle(self._fit_research_tree)

    def _toggle_research_maximize(self):
        window = self.research_window
        if window is None or not window.winfo_exists():
            return
        if self.research_maximized:
            window.state("normal")
            if self.research_restore_geometry:
                window.geometry(self.research_restore_geometry)
            self.research_maximize_button.configure(text="MAX")
            self.research_maximized = False
        else:
            self.research_restore_geometry = window.geometry()
            window.state("zoomed")
            self.research_maximize_button.configure(text="REST")
            self.research_maximized = True

    def _close_research(self):
        if self.research_window is not None and self.research_window.winfo_exists():
            self.research_window.withdraw()

    def _draw_research_graph(self):
        canvas = self.research_canvas
        if canvas is None or not canvas.winfo_exists():
            return
        canvas.delete("all")
        canvas.create_text(
            18,
            16,
            text="RESEARCH TREE",
            fill="#e0e6e1",
            anchor="nw",
            font=("Consolas", 9, "bold"),
        )
        nodes = self.progression.tech_tree
        node_width, node_height = 132, 64
        gap_x, gap_y = 34, 32
        positions = layout_tree(
            nodes,
            node_width=node_width,
            node_height=node_height,
            gap_x=gap_x,
            gap_y=gap_y,
            ordered_rows=RESEARCH_ROWS,
        )
        scale = self.research_zoom
        offset_x, offset_y = 16, 42

        children_by_parent = {}
        secondary_edges = []
        for child_name, data in nodes.items():
            parents = [
                parent
                for parent in data.get("visual_parents", ())
                if parent in nodes
            ]
            if parents:
                children_by_parent.setdefault(parents[0], []).append(child_name)
                secondary_edges.extend(
                    (parent, child_name) for parent in parents[1:]
                )

        for parent_name, child_names in children_by_parent.items():
            parent_x, parent_y = positions[parent_name]
            parent_center_x = offset_x + (
                parent_x + node_width / 2
            ) * scale
            parent_bottom_y = offset_y + (
                parent_y + node_height
            ) * scale
            child_centers = []
            for child_name in child_names:
                child_x, child_y = positions[child_name]
                child_centers.append(
                    (
                        offset_x + (child_x + node_width / 2) * scale,
                        offset_y + child_y * scale,
                    )
                )
            bus_y = (parent_bottom_y + min(top_y for _, top_y in child_centers)) / 2
            branch_x = [parent_center_x]
            branch_x.extend(center_x for center_x, _ in child_centers)
            canvas.create_line(
                parent_center_x,
                parent_bottom_y,
                parent_center_x,
                bus_y,
                fill="#d3b873",
                width=2,
                capstyle=tk.ROUND,
            )
            canvas.create_line(
                min(branch_x),
                bus_y,
                max(branch_x),
                bus_y,
                fill="#d3b873",
                width=2,
                capstyle=tk.ROUND,
            )
            for child_center_x, child_top_y in child_centers:
                canvas.create_line(
                    child_center_x,
                    bus_y,
                    child_center_x,
                    child_top_y,
                    fill="#d3b873",
                    width=2,
                    capstyle=tk.ROUND,
                )

        for parent_name, child_name in secondary_edges:
            parent_x, parent_y = positions[parent_name]
            child_x, child_y = positions[child_name]
            start_x = offset_x + (parent_x + node_width / 2) * scale
            start_y = offset_y + (parent_y + node_height) * scale
            end_x = offset_x + (child_x + node_width / 2) * scale
            end_y = offset_y + child_y * scale
            middle_y = (start_y + end_y) / 2
            canvas.create_line(
                start_x,
                start_y,
                start_x,
                middle_y,
                end_x,
                middle_y,
                end_x,
                end_y,
                fill="#9b9e88",
                width=1,
                dash=(3, 4),
            )

        for name, data in nodes.items():
            node_x, node_y = positions[name]
            x = offset_x + node_x * scale
            y = offset_y + node_y * scale
            status = self.progression.status(name)
            affordable = self.progression.is_affordable(name)
            if status == "unlocked":
                fill, outline = "#647f43", "#bfd17d"
            elif status == "available" and affordable:
                fill, outline = "#615a3c", "#d9b86e"
            elif status == "available":
                fill, outline = "#484b43", "#888675"
            elif status == "unknown":
                fill, outline = "#343d41", "#788388"
            else:
                fill, outline = "#343d41", "#586267"
            if name == self.selected_unlock:
                outline = "#f1d88c"
            if status == "unknown":
                state = "DATA INCOMPLETE"
            tag = f"node:{name}"
            canvas.create_rectangle(
                x,
                y,
                x + node_width * scale,
                y + node_height * scale,
                fill=fill,
                outline=outline,
                width=4 if name == self.selected_unlock else 2,
                dash=(7, 4) if status == "unknown" else (),
                tags=(tag,),
            )
            canvas.create_text(
                x + node_width * scale / 2,
                y + node_height * scale / 2,
                text=name.upper(),
                fill="#f1e7cb",
                anchor="center",
                width=max(1, (node_width - 12) * scale),
                justify="center",
                font=("Consolas", max(6, round(10 * scale)), "bold"),
                tags=(tag,),
            )
            canvas.tag_bind(tag, "<Button-1>", lambda _event, node=name: self._show_research_detail(node))

        canvas.configure(
            scrollregion=canvas.bbox("all") or (0, 0, 600, 500)
        )

    @staticmethod
    def _format_cost(cost):
        if cost is None:
            return "COST  NOT VERIFIED"
        if not cost:
            return "COST  NONE"
        return "COST  " + "  /  ".join(
            f"{amount} {item.title()}" for item, amount in cost.items()
        )

    def _ensure_progression_dialog(self):
        if self.progression_dialog is not None and self.progression_dialog.winfo_exists():
            return
        dialog = tk.Frame(
            self.workspace,
            bg=self.COLORS["panel"],
            highlightthickness=1,
            highlightbackground="#a1aa9c",
        )
        self.progression_dialog = dialog
        header = tk.Frame(dialog, bg=self.COLORS["panel_header"], height=38)
        header.pack(side="top", fill="x")
        header.pack_propagate(False)
        title = tk.Label(
            header,
            text="RESEARCH DIALOG",
            bg=self.COLORS["panel_header"],
            fg=self.COLORS["text"],
            font=("Consolas", 9, "bold"),
            anchor="w",
        )
        self.progression_dialog_title = title
        title.pack(side="left", fill="y", padx=12)
        for widget in (header, title):
            widget.bind("<ButtonPress-1>", self._start_progression_dialog_drag)
            widget.bind("<B1-Motion>", self._drag_progression_dialog)
        self.progression_dialog_tree_button = tk.Button(
            header,
            text="TREE",
            command=self._hide_research_detail,
            bg=self.COLORS["panel_header"],
            fg=self.COLORS["muted"],
            activebackground=self.COLORS["panel"],
            relief="flat",
            padx=8,
        )
        self.progression_dialog_tree_button.pack(side="right", fill="y")
        self.progression_dialog_minimize_button = tk.Button(
            header,
            text="_",
            command=self._minimize_progression_dialog,
            bg=self.COLORS["panel_header"],
            fg=self.COLORS["muted"],
            activebackground=self.COLORS["panel"],
            relief="flat",
            width=4,
        )
        self.progression_dialog_minimize_button.pack(side="right", fill="y")
        self.progression_dialog_maximize_button = tk.Button(
            header,
            text="MAX",
            command=lambda: self._toggle_panel_maximize("progression_dialog"),
            bg=self.COLORS["panel_header"],
            fg=self.COLORS["muted"],
            activebackground=self.COLORS["panel"],
            relief="flat",
            padx=5,
        )
        self.progression_dialog_maximize_button.pack(side="right", fill="y")
        tk.Button(
            header,
            text="X",
            command=self._close_progression_dialog,
            bg=self.COLORS["panel_header"],
            fg=self.COLORS["muted"],
            activebackground=self.COLORS["panel"],
            relief="flat",
            width=4,
        ).pack(side="right", fill="y")

        body = tk.Frame(dialog, bg=self.COLORS["panel"])
        body.pack(fill="both", expand=True)
        self.progression_dialog_body = body
        canvas = tk.Canvas(
            body,
            bg=self.COLORS["panel"],
            highlightthickness=0,
        )
        scrollbar = tk.Scrollbar(body, command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        content = tk.Frame(canvas, bg=self.COLORS["panel"])
        window_id = canvas.create_window((0, 0), window=content, anchor="nw")
        content.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(window_id, width=event.width),
        )
        self.progression_dialog_canvas = canvas
        self.progression_dialog_content = content
        self.progression_dialog_window_id = window_id
        self._add_panel_resize_grip(dialog, "progression_dialog")

    def _place_progression_dialog(self):
        self._ensure_progression_dialog()
        width, height = self.progression_dialog_size
        width = min(width, max(420, self.workspace.winfo_width() - 32))
        height = min(height, max(400, self.workspace.winfo_height() - 32))
        if self.progression_dialog_position is None:
            x = max(16, (self.workspace.winfo_width() - width) // 2)
            y = max(16, (self.workspace.winfo_height() - height) // 2)
        else:
            x, y = self.progression_dialog_position
            x = min(x, max(0, self.workspace.winfo_width() - width))
            y = min(y, max(0, self.workspace.winfo_height() - 38))
        if self.panel_maximized["progression_dialog"]:
            self.progression_dialog.place(
                x=0,
                y=0,
                width=self.workspace.winfo_width(),
                height=self.workspace.winfo_height(),
            )
        else:
            self.progression_dialog.place(
                x=x,
                y=y,
                width=width,
                height=height,
            )
        if self.progression_dialog_minimized:
            self.progression_dialog_body.pack(fill="both", expand=True)
        self.progression_dialog_minimized = False
        self.progression_dialog.lift()
        self.root.lift()

    def _show_intro_dialog(self):
        self.progression_dialog_mode = ("intro", None, False)
        self.selected_unlock = None
        if self.research_window is not None and self.research_window.winfo_exists():
            self.research_window.withdraw()
        self._place_progression_dialog()
        self.progression_dialog_title.configure(text="FARMING GUIDE")
        self.progression_dialog_tree_button.configure(state="disabled")
        content = self.progression_dialog_content
        for child in content.winfo_children():
            child.destroy()
        tk.Label(
            content,
            text="HARVESTING BASICS",
            bg=self.COLORS["panel"],
            fg="#ecd394",
            anchor="w",
            font=("Consolas", 15, "bold"),
        ).pack(fill="x", padx=18, pady=(18, 10))
        tk.Label(
            content,
            text=(
                "The drone works on the tile it is standing on. "
                "Use harvest() to collect a fully grown plant from that tile. "
                "The grass on your starting tile is ready to harvest."
            ),
            bg=self.COLORS["panel"],
            fg=self.COLORS["text"],
            justify="left",
            anchor="w",
            wraplength=500,
            font=("Consolas", 10),
        ).pack(fill="x", padx=18)
        tk.Label(
            content,
            text="HOW TO USE",
            bg=self.COLORS["panel"],
            fg="#d5c18d",
            anchor="w",
            font=("Consolas", 8, "bold"),
        ).pack(fill="x", padx=18, pady=(18, 4))
        tk.Label(
            content,
            text=(
                "Open CODE, type the command below yourself, then press RUN. "
                "When the plant is mature, harvesting adds its drops to your inventory."
            ),
            bg=self.COLORS["panel"],
            fg=self.COLORS["text"],
            justify="left",
            anchor="w",
            wraplength=500,
            font=("Consolas", 9),
        ).pack(fill="x", padx=18)
        tk.Label(
            content,
            text="COMMAND",
            bg=self.COLORS["panel"],
            fg="#d5c18d",
            anchor="w",
            font=("Consolas", 8, "bold"),
        ).pack(fill="x", padx=18, pady=(18, 4))
        tk.Label(
            content,
            text="harvest()",
            bg=self.COLORS["editor"],
            fg="#d6dedb",
            anchor="w",
            padx=10,
            pady=10,
            font=("Consolas", 11),
        ).pack(fill="x", padx=18)

    def _start_progression_dialog_drag(self, event):
        self._start_panel_drag(event, "progression_dialog")

    def _drag_progression_dialog(self, event):
        self._drag_panel(event, "progression_dialog")

    def _show_research_detail(
        self,
        unlock,
        show_tutorial=False,
        show_dialog=False,
    ):
        self.selected_unlock = unlock
        self.progression_dialog_mode = (
            ("unlock", unlock, show_tutorial) if show_dialog else None
        )
        self._render_research_inline_detail(unlock)
        self._draw_research_graph()
        if not show_dialog:
            return
        if self.research_window is not None and self.research_window.winfo_exists():
            self.research_window.lower()
        self._place_progression_dialog()
        self.progression_dialog_title.configure(text="RESEARCH DIALOG")
        self.progression_dialog_tree_button.configure(state="normal")

        content = self.progression_dialog_content
        for child in content.winfo_children():
            child.destroy()
        data = self.progression.tech_tree[unlock]
        status = self.progression.status(unlock)
        affordable = self.progression.is_affordable(unlock)
        status_text = status.upper()
        if status == "available" and not affordable:
            status_text = "AVAILABLE  /  NEEDS RESOURCES"
        max_level = self.progression.max_upgrade_level(unlock)
        if max_level is not None:
            status_text += (
                f"  /  LEVEL {self.progression.upgrade_level(unlock)}/{max_level}"
            )

        tk.Label(
            content,
            text=unlock.upper(),
            bg=self.COLORS["panel"],
            fg="#ecd394",
            anchor="w",
            font=("Consolas", 15, "bold"),
        ).pack(fill="x", padx=18, pady=(16, 5))
        tk.Label(
            content,
            text=status_text,
            bg=self.COLORS["panel"],
            fg=self.COLORS["muted"],
            anchor="w",
            font=("Consolas", 8, "bold"),
        ).pack(fill="x", padx=18, pady=(0, 10))
        category = data.get("category")
        if category:
            tk.Label(
                content,
                text=category.upper(),
                bg=self.COLORS["panel"],
                fg="#d5c18d",
                anchor="w",
                font=("Consolas", 8, "bold"),
            ).pack(fill="x", padx=18, pady=(0, 8))
        tk.Label(
            content,
            text=data.get("description", "No verified description."),
            bg=self.COLORS["panel"],
            fg=self.COLORS["text"],
            justify="left",
            anchor="w",
            wraplength=500,
            font=("Consolas", 9),
        ).pack(fill="x", padx=18)
        tutorial = self.progression.tutorial(unlock)
        if show_tutorial and tutorial:
            tk.Label(
                content,
                text="TUTORIAL",
                bg=self.COLORS["panel"],
                fg="#d5c18d",
                anchor="w",
                font=("Consolas", 8, "bold"),
            ).pack(fill="x", padx=18, pady=(10, 3))
            tk.Label(
                content,
                text=tutorial["body"],
                bg=self.COLORS["panel"],
                fg=self.COLORS["text"],
                justify="left",
                anchor="w",
                wraplength=500,
                font=("Consolas", 9),
            ).pack(fill="x", padx=18)
        usage = data.get("usage")
        if usage:
            tk.Label(
                content,
                text="HOW TO USE",
                bg=self.COLORS["panel"],
                fg="#d5c18d",
                anchor="w",
                font=("Consolas", 8, "bold"),
            ).pack(fill="x", padx=18, pady=(10, 3))
            tk.Label(
                content,
                text=usage,
                bg=self.COLORS["panel"],
                fg=self.COLORS["text"],
                justify="left",
                anchor="w",
                wraplength=500,
                font=("Consolas", 9),
            ).pack(fill="x", padx=18)
        source_code = data.get("source_code")
        if unlock == "Loops":
            source_code = (tutorial or {}).get("example", source_code)
        if source_code:
            tk.Label(
                content,
                text="SOURCE CODE",
                bg=self.COLORS["panel"],
                fg="#d5c18d",
                anchor="w",
                font=("Consolas", 8, "bold"),
            ).pack(fill="x", padx=18, pady=(10, 3))
            code = tk.Text(
                content,
                height=max(2, min(4, source_code.count("\n") + 2)),
                bg=self.COLORS["editor"],
                fg="#d6dedb",
                font=("Consolas", 9),
                relief="flat",
                wrap="word",
                padx=8,
                pady=6,
            )
            code.pack(fill="x", padx=18)
            code.insert("1.0", source_code)
            code.configure(state="disabled")
        next_cost = self.progression.current_cost(unlock)
        cost_text = (
            "MAX LEVEL"
            if max_level is not None and self.progression.upgrade_level(unlock) >= max_level
            else self._format_cost(next_cost)
        )
        tk.Label(
            content,
            text=cost_text,
            bg=self.COLORS["panel"],
            fg="#e4c77f",
            anchor="w",
            font=("Consolas", 9),
        ).pack(fill="x", padx=18, pady=(12, 5))

        if "prerequisites" in data:
            prereqs = data["prerequisites"]
            prereq_text = "PREREQUISITES  " + (", ".join(prereqs) if prereqs else "none")
        else:
            prereq_text = "PREREQUISITES  NOT VERIFIED"
        tk.Label(
            content,
            text=prereq_text,
            bg=self.COLORS["panel"],
            fg=self.COLORS["muted"],
            anchor="w",
            font=("Consolas", 8),
        ).pack(fill="x", padx=18, pady=(0, 10))

        if status == "unknown":
            action = tk.Button(
                content,
                text="DATA INCOMPLETE",
                state="disabled",
                bg=self.COLORS["panel_header"],
                fg=self.COLORS["muted"],
                relief="flat",
                padx=10,
                pady=7,
                font=("Consolas", 8, "bold"),
            )
        elif status == "unlocked" and max_level is not None:
            action = tk.Button(
                content,
                text="MAX LEVEL",
                state="disabled",
                bg=self.COLORS["panel_header"],
                fg=self.COLORS["muted"],
                relief="flat",
                padx=10,
                pady=7,
                font=("Consolas", 8, "bold"),
            )
        elif status == "unlocked" and self.progression.tutorial(unlock):
            action = tk.Button(
                content,
                text="VIEW TUTORIAL",
                command=lambda: self._show_tutorial(unlock),
                bg=self.COLORS["green_dark"],
                fg="#ffffff",
                relief="flat",
                padx=10,
                pady=7,
                font=("Consolas", 8, "bold"),
            )
        elif status == "unlocked":
            action = tk.Button(
                content,
                text="UNLOCKED",
                state="disabled",
                bg=self.COLORS["panel_header"],
                fg=self.COLORS["muted"],
                relief="flat",
                padx=10,
                pady=7,
                font=("Consolas", 8, "bold"),
            )
        else:
            level_text = (
                f"UPGRADE {self.progression.upgrade_level(unlock) + 1}/{max_level}"
                if max_level is not None
                else "UNLOCK"
            )
            action = tk.Button(
                content,
                text=level_text,
                command=lambda: self._purchase_unlock(unlock),
                bg=self.COLORS["green"],
                fg="#172018",
                relief="flat",
                padx=12,
                pady=7,
                font=("Consolas", 8, "bold"),
                state="normal" if self.progression.can_unlock(unlock) else "disabled",
            )
        action.pack(anchor="w", padx=18, pady=(0, 18))
        self.unlock_button = action
        self._draw_research_graph()

    def _render_research_inline_detail(self, unlock):
        content = self.research_detail_content
        if content is None or not content.winfo_exists():
            return
        for child in content.winfo_children():
            child.destroy()

        data = self.progression.tech_tree[unlock]
        status = self.progression.status(unlock)
        affordable = self.progression.is_affordable(unlock)
        status_text = status.upper()
        if status == "available" and not affordable:
            status_text = "AVAILABLE / NEEDS RESOURCES"
        max_level = self.progression.max_upgrade_level(unlock)
        if max_level is not None:
            status_text += (
                f" / LEVEL {self.progression.upgrade_level(unlock)}/{max_level}"
            )

        tk.Label(
            content,
            text=unlock.upper(),
            bg=self.COLORS["panel"],
            fg="#ecd394",
            anchor="w",
            justify="left",
            wraplength=280,
            font=("Consolas", 14, "bold"),
        ).pack(fill="x", padx=14, pady=(14, 4))
        tk.Label(
            content,
            text=status_text,
            bg=self.COLORS["panel"],
            fg=self.COLORS["muted"],
            anchor="w",
            justify="left",
            wraplength=280,
            font=("Consolas", 8, "bold"),
        ).pack(fill="x", padx=14, pady=(0, 10))
        category = data.get("category")
        if category:
            tk.Label(
                content,
                text=category.upper(),
                bg=self.COLORS["panel"],
                fg="#d5c18d",
                anchor="w",
                font=("Consolas", 8, "bold"),
            ).pack(fill="x", padx=14, pady=(0, 6))
        tk.Label(
            content,
            text=data.get("description", "No verified description."),
            bg=self.COLORS["panel"],
            fg=self.COLORS["text"],
            justify="left",
            anchor="w",
            wraplength=280,
            font=("Consolas", 9),
        ).pack(fill="x", padx=14)

        usage = data.get("usage")
        if usage:
            tk.Label(
                content,
                text="HOW TO USE",
                bg=self.COLORS["panel"],
                fg="#d5c18d",
                anchor="w",
                font=("Consolas", 8, "bold"),
            ).pack(fill="x", padx=14, pady=(12, 4))
            tk.Label(
                content,
                text=usage,
                bg=self.COLORS["panel"],
                fg=self.COLORS["text"],
                justify="left",
                anchor="w",
                wraplength=280,
                font=("Consolas", 9),
            ).pack(fill="x", padx=14)
        source_code = data.get("source_code")
        if unlock == "Loops":
            source_code = (
                self.progression.tutorial(unlock) or {}
            ).get("example", source_code)
        if source_code:
            tk.Label(
                content,
                text="SOURCE CODE",
                bg=self.COLORS["panel"],
                fg="#d5c18d",
                anchor="w",
                font=("Consolas", 8, "bold"),
            ).pack(fill="x", padx=14, pady=(12, 4))
            code = tk.Text(
                content,
                height=max(2, min(5, source_code.count("\n") + 2)),
                bg=self.COLORS["editor"],
                fg="#d6dedb",
                font=("Consolas", 9),
                relief="flat",
                wrap="word",
                padx=8,
                pady=6,
            )
            code.pack(fill="x", padx=14)
            code.insert("1.0", source_code)
            code.configure(state="disabled")

        next_cost = self.progression.current_cost(unlock)
        cost_text = (
            "MAX LEVEL"
            if max_level is not None
            and self.progression.upgrade_level(unlock) >= max_level
            else self._format_cost(next_cost)
        )
        tk.Label(
            content,
            text=cost_text,
            bg=self.COLORS["panel"],
            fg="#e4c77f",
            anchor="w",
            font=("Consolas", 9),
        ).pack(fill="x", padx=14, pady=(12, 5))

        prereqs = data.get("prerequisites")
        prereq_text = (
            "PREREQUISITES  " + (", ".join(prereqs) if prereqs else "none")
            if prereqs is not None
            else "PREREQUISITES  NOT VERIFIED"
        )
        tk.Label(
            content,
            text=prereq_text,
            bg=self.COLORS["panel"],
            fg=self.COLORS["muted"],
            anchor="w",
            justify="left",
            wraplength=280,
            font=("Consolas", 8),
        ).pack(fill="x", padx=14, pady=(0, 10))

        if status == "unknown":
            action = tk.Button(
                content,
                text="DATA INCOMPLETE",
                state="disabled",
                bg=self.COLORS["panel_header"],
                fg=self.COLORS["muted"],
                relief="flat",
                padx=10,
                pady=7,
                font=("Consolas", 8, "bold"),
            )
        elif status == "unlocked" and max_level is not None:
            action = tk.Button(
                content,
                text="MAX LEVEL",
                state="disabled",
                bg=self.COLORS["panel_header"],
                fg=self.COLORS["muted"],
                relief="flat",
                padx=10,
                pady=7,
                font=("Consolas", 8, "bold"),
            )
        elif status == "unlocked" and self.progression.tutorial(unlock):
            action = tk.Button(
                content,
                text="VIEW TUTORIAL",
                command=lambda: self._show_tutorial(unlock),
                bg=self.COLORS["green_dark"],
                fg="#ffffff",
                relief="flat",
                padx=10,
                pady=7,
                font=("Consolas", 8, "bold"),
            )
        elif status == "unlocked":
            action = tk.Button(
                content,
                text="UNLOCKED",
                state="disabled",
                bg=self.COLORS["panel_header"],
                fg=self.COLORS["muted"],
                relief="flat",
                padx=10,
                pady=7,
                font=("Consolas", 8, "bold"),
            )
        else:
            level_text = (
                f"UPGRADE {self.progression.upgrade_level(unlock) + 1}/{max_level}"
                if max_level is not None
                else "UNLOCK"
            )
            action = tk.Button(
                content,
                text=level_text,
                command=lambda: self._purchase_unlock(unlock),
                bg=self.COLORS["green"],
                fg="#172018",
                relief="flat",
                padx=12,
                pady=7,
                font=("Consolas", 8, "bold"),
                state="normal" if self.progression.can_unlock(unlock) else "disabled",
            )
        action.pack(anchor="w", padx=14, pady=(0, 18))
        self.research_unlock_button = action

    def _hide_research_detail(self):
        if self.progression_dialog is not None and self.progression_dialog.winfo_exists():
            self.progression_dialog.place_forget()
        self.progression_dialog_minimized = False
        self.progression_dialog_mode = None
        if self.research_window is not None and self.research_window.winfo_exists():
            self.research_window.deiconify()
            self.research_window.lift()
            self.research_window.focus_force()
            self._draw_research_graph()

    def _minimize_progression_dialog(self):
        if self.progression_dialog is None or not self.progression_dialog.winfo_exists():
            return
        if self.progression_dialog_minimized:
            return
        if self.panel_maximized["progression_dialog"]:
            self._toggle_panel_maximize("progression_dialog")
        self.progression_dialog_size = (
            self.progression_dialog.winfo_width(),
            self.progression_dialog.winfo_height(),
        )
        self.progression_dialog_body.pack_forget()
        self.progression_dialog_minimized = True
        self.progression_dialog.place_configure(height=38)

    def _close_progression_dialog(self):
        if self.progression_dialog is not None and self.progression_dialog.winfo_exists():
            if self.panel_maximized["progression_dialog"]:
                self._toggle_panel_maximize("progression_dialog")
            if self.progression_dialog.winfo_manager():
                self.progression_dialog_position = (
                    int(self.progression_dialog.place_info()["x"]),
                    int(self.progression_dialog.place_info()["y"]),
                )
            self.progression_dialog.place_forget()
        self.progression_dialog_minimized = False
        if self.research_window is not None and self.research_window.winfo_exists():
            self.research_window.deiconify()
            self.research_window.lift()
            self.research_window.focus_force()
            self._draw_research_graph()

    def _toggle_progression_dialog(self):
        if (
            self.progression_dialog is not None
            and self.progression_dialog.winfo_exists()
            and self.progression_dialog.winfo_manager()
        ):
            if self.progression_dialog_minimized:
                self._place_progression_dialog()
            else:
                self.progression_dialog.lift()
            return
        mode = self.progression_dialog_mode
        if mode is not None and mode[0] == "unlock":
            self._show_research_detail(
                mode[1],
                show_tutorial=mode[2],
                show_dialog=True,
            )
        else:
            self._show_intro_dialog()

    def _purchase_unlock(self, unlock):
        old_level = self.progression.upgrade_level(unlock)
        if not self.progression.unlock(unlock):
            return
        self.drone.grass_yield_multiplier = self.progression.grass_yield_multiplier()
        if self.progression.upgrade_level(unlock) > old_level:
            effects = self.progression.current_level_effects(unlock)
            self.drone.speed_multiplier = self.progression.speed_multiplier()
            self.drone.watering_tanks_per_10_seconds = (
                self.progression.watering_tanks_per_10_seconds()
            )
            if "width" in effects and "height" in effects:
                resize_world = (
                    self.world.resize
                    if unlock == "Expand"
                    else self.world.expand_and_clear
                )
                resize_world(effects["width"], effects["height"])
                self.drone.x, self.drone.y = self.world.wrap(self.drone.x, self.drone.y)
        self._refresh_interpreter()
        self._update_hud()
        self._draw_research_graph()
        show_tutorial = (
            bool(self.progression.tutorial(unlock))
            and unlock not in self.tutorial_seen
        )
        if show_tutorial:
            self.tutorial_seen.add(unlock)
        self._show_research_detail(
            unlock,
            show_tutorial=show_tutorial,
            show_dialog=True,
        )
        try:
            self._save_progress()
        except OSError as exc:
            messagebox.showerror(
                "Progres belum tersimpan",
                f"Pembelian berhasil, tetapi progres akun {self.username} gagal disimpan:\n{exc}",
                parent=self.root,
            )
        level = self.progression.upgrade_level(unlock)
        max_level = self.progression.max_upgrade_level(unlock)
        if max_level is not None and old_level:
            message = f"Research upgraded: {unlock} to level {level}/{max_level}."
        elif max_level is not None:
            message = f"Research complete: {unlock} unlocked at level {level}/{max_level}."
        else:
            message = f"Research complete: {unlock} unlocked."
        self._append_output(message)

    def _show_tutorial(self, unlock):
        tutorial = self.progression.tutorial(unlock)
        if not tutorial:
            return
        self._show_research_detail(
            unlock,
            show_tutorial=True,
            show_dialog=True,
        )

    def _research_pan_start(self, event):
        self.research_pan_origin = (event.x, event.y)
        self.research_canvas.scan_mark(event.x, event.y)

    def _research_pan_move(self, event):
        if self.research_pan_origin is None:
            return
        self.research_canvas.scan_dragto(event.x, event.y, gain=1)

    def _research_zoom(self, event):
        factor = 1.1 if event.delta > 0 else 1 / 1.1
        self._set_research_zoom(self.research_zoom * factor)

    def _set_research_zoom(self, zoom):
        self.research_zoom = min(1.7, max(0.2, zoom))
        if hasattr(self, "research_zoom_label"):
            self.research_zoom_label.configure(text=f"{self.research_zoom:.0%}")
        self._draw_research_graph()

    def _fit_research_tree(self):
        canvas = self.research_canvas
        if canvas is None or not canvas.winfo_exists():
            return
        nodes = self.progression.tech_tree
        positions = layout_tree(
            nodes,
            node_width=132,
            node_height=64,
            gap_x=34,
            gap_y=32,
            ordered_rows=RESEARCH_ROWS,
        )
        max_x = max(x for x, _ in positions.values()) + 132
        max_y = max(y for _, y in positions.values()) + 64
        available_width = max(1, canvas.winfo_width() - 32)
        available_height = max(1, canvas.winfo_height() - 58)
        self._set_research_zoom(
            min(available_width / max_x, available_height / max_y)
        )

    def _stop_script(self):
        if not self.running:
            return
        self.running = False
        self.steps = None
        self.idle_last_update = time.perf_counter()
        self.harvest_animation = None
        self._highlight_code_span(None)
        self.run_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.action_label.configure(text="STOPPED")
        self._append_output("Execution stopped.")

    def _advance_idle_world(self):
        now = time.perf_counter()
        elapsed = now - self.idle_last_update
        self.idle_last_update = now
        if not self.running:
            ticks = self._advance_idle_elapsed(elapsed)
            if ticks:
                self._update_hud()
                self._render_world()
        self.root.after(50, self._advance_idle_world)

    def _advance_execution(self):
        if not self.running or self.steps is None:
            return
        now = time.perf_counter()
        elapsed = now - self.execution_last_update
        self.execution_last_update = now
        steps_this_frame = self._execution_steps_for_frame(elapsed)
        if steps_this_frame == 0:
            self.root.after(1, self._advance_execution)
            return
        should_render_world = False
        for _ in range(steps_this_frame):
            try:
                step = next(self.steps)
            except StopIteration:
                self._finish_execution()
                return
            except Exception as exc:
                self.running = False
                self.steps = None
                self.idle_last_update = time.perf_counter()
                self.harvest_animation = None
                self._highlight_code_span(None)
                self.run_button.configure(state="normal")
                self.stop_button.configure(state="disabled")
                self.action_label.configure(text="ERROR")
                self._append_output(f"{type(exc).__name__}: {exc}")
                return

            progress = step.result
            if step.function == "harvest":
                if progress.completed_ticks == 1:
                    event = self.drone.last_harvest_event
                    self.harvest_animation = (
                        {**event, "completed_ticks": 0, "total_ticks": progress.total_ticks}
                        if event is not None
                        else None
                    )
                if self.harvest_animation is not None:
                    self.harvest_animation["completed_ticks"] = (
                        progress.completed_ticks
                    )
            should_render_world |= (
                progress.completed_ticks == 1
                or progress.completed_ticks == progress.total_ticks
                or (
                    step.function == "harvest"
                    and progress.completed_ticks % 8 == 0
                )
            )

        self._highlight_code_span(
            step.line,
            step.column_start,
            step.end_line,
            step.column_end,
        )
        self.tick_label.configure(text=f"TICK {self.clock.tick_count:06d}")
        self.action_label.configure(
            text=f"{step.function.upper()}  {progress.completed_ticks}/{progress.total_ticks}"
        )
        self._update_hud()
        if should_render_world:
            self._render_world()
        if (
            self.harvest_animation is not None
            and self.harvest_animation["completed_ticks"]
            >= self.harvest_animation["total_ticks"]
        ):
            self.harvest_animation = None
        self.root.after(1, self._advance_execution)

    def _finish_execution(self):
        self.running = False
        self.steps = None
        self.idle_last_update = time.perf_counter()
        self.harvest_animation = None
        self._highlight_code_span(None)
        self.run_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.action_label.configure(text="COMPLETE")
        self._render_world()
        self._append_output(f"Finished at tick {self.clock.tick_count}.")

    def _update_hud(self):
        for item, label in self.inventory_labels.items():
            label.configure(
                text=self._format_resource_count(self.inventory.count(item))
            )
        self.tick_label.configure(text=f"TICK {self.clock.tick_count:06d}")
        if hasattr(self, "field_label"):
            self.field_label.configure(
                text=f"FIELD {self.world.height}x{self.world.width}"
            )
        if hasattr(self, "unlock_button") and self.unlock_button.winfo_exists():
            selected = self.selected_unlock
            if selected is not None:
                status = self.progression.status(selected)
                can_view_tutorial = bool(self.progression.tutorial(selected))
                self.unlock_button.configure(
                    state=(
                        "normal"
                        if self.progression.can_unlock(selected)
                        or (status == "unlocked" and can_view_tutorial)
                        else "disabled"
                    )
                )
        canvas = getattr(self, "research_canvas", None)
        if canvas is not None and canvas.winfo_exists():
            snapshot = tuple(
                (name, self.progression.status(name), self.progression.is_affordable(name))
                for name in self.progression.tech_tree
            )
            if snapshot != self.research_state_snapshot:
                self.research_state_snapshot = snapshot
                self._draw_research_graph()
                if self.selected_unlock is not None:
                    self._render_research_inline_detail(self.selected_unlock)
                if (
                    self.selected_unlock is not None
                    and not self.progression_dialog_minimized
                    and self.progression_dialog is not None
                    and self.progression_dialog.winfo_manager()
                ):
                    mode = self.progression_dialog_mode
                    if mode is not None and mode[0] == "unlock":
                        self._show_research_detail(
                            self.selected_unlock,
                            show_tutorial=bool(mode[2]),
                            show_dialog=True,
                        )

    def _open_developer_panel(self):
        if self.account_tag != "developer":
            raise PermissionError("Developer items hanya tersedia untuk akun developer.")
        if self.developer_panel is not None and self.developer_panel.winfo_exists():
            self.developer_panel.lift()
            return

        window = tk.Toplevel(self.root)
        self.developer_panel = window
        window.title("Developer — Tambah Item")
        window.geometry("360x260")
        window.resizable(False, False)
        window.transient(self.root)
        window.configure(bg=self.COLORS["panel"])
        window.protocol("WM_DELETE_WINDOW", window.destroy)
        frame = tk.Frame(window, bg=self.COLORS["panel"], padx=22, pady=18)
        frame.pack(fill="both", expand=True)

        tk.Label(
            frame,
            text="TAMBAH RESOURCE / ITEM",
            bg=self.COLORS["panel"],
            fg=self.COLORS["text"],
            font=("Consolas", 11, "bold"),
        ).pack(anchor="w", pady=(0, 14))
        tk.Label(
            frame,
            text="Item",
            bg=self.COLORS["panel"],
            fg=self.COLORS["muted"],
            font=("Consolas", 9),
        ).pack(anchor="w")
        selected_item = tk.StringVar(value=self.DEV_GRANT_ITEMS[0])
        tk.OptionMenu(frame, selected_item, *self.DEV_GRANT_ITEMS).pack(
            fill="x",
            pady=(3, 10),
        )
        tk.Label(
            frame,
            text="Jumlah yang ditambahkan",
            bg=self.COLORS["panel"],
            fg=self.COLORS["muted"],
            font=("Consolas", 9),
        ).pack(anchor="w")
        amount_entry = tk.Entry(frame, bg="#252d30", fg=self.COLORS["text"])
        amount_entry.pack(fill="x", pady=(3, 12), ipady=5)
        amount_entry.insert(0, "1")

        def apply_grant():
            try:
                amount = int(amount_entry.get())
                self._grant_developer_item(selected_item.get(), amount)
            except (ValueError, OSError, PermissionError) as exc:
                messagebox.showerror(
                    "Developer items",
                    str(exc),
                    parent=window,
                )
                return
            messagebox.showinfo(
                "Developer items",
                f"Berhasil menambahkan {amount} {selected_item.get()}.",
                parent=window,
            )

        tk.Button(
            frame,
            text="TAMBAHKAN",
            command=apply_grant,
            bg=self.COLORS["green"],
            fg="#172018",
            activebackground="#abc65c",
            relief="flat",
            padx=14,
            pady=8,
            font=("Consolas", 9, "bold"),
        ).pack(fill="x")
        window.grab_set()
        amount_entry.focus_set()

    def _grant_developer_item(self, item, amount):
        if self.account_tag != "developer":
            raise PermissionError("Developer items hanya tersedia untuk akun developer.")
        if item not in self.DEV_GRANT_ITEMS:
            raise ValueError("Item tidak tersedia.")
        if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
            raise ValueError("Jumlah harus berupa bilangan bulat positif.")

        previous_inventory = self.inventory.as_dict()
        self.inventory.add(item, amount)
        try:
            self._save_progress()
        except (OSError, ValueError):
            self.inventory.replace(previous_inventory)
            raise
        self._update_hud()

    @staticmethod
    def _format_resource_count(amount):
        if amount < 1_000:
            return str(amount)
        for divisor, suffix in (
            (1_000_000_000_000, "T"),
            (1_000_000_000, "B"),
            (1_000_000, "M"),
            (1_000, "K"),
        ):
            if amount >= divisor:
                if amount < divisor * 10:
                    tenths = amount * 10 // divisor
                    return f"{tenths // 10}.{tenths % 10}{suffix}"
                return f"{amount // divisor}{suffix}"
        return str(amount)

    def _append_output(self, message):
        self.output.configure(state="normal")
        self.output.insert("end", message + "\n")
        self.output.see("end")
        self.output.configure(state="disabled")

    def _render_world(self):
        if not hasattr(self, "canvas"):
            return
        canvas = self.canvas
        width = max(1, canvas.winfo_width())
        height = max(1, canvas.winfo_height())
        canvas.delete("all")
        canvas.create_text(
            26,
            24,
            text="FARM / 01",
            fill="#e2e6df",
            anchor="nw",
            font=("Consolas", 10, "bold"),
        )
        canvas.create_text(
            26,
            44,
            text=f"FIELD  {self.world.height} x {self.world.width}",
            fill="#c3cdc5",
            anchor="nw",
            font=("Consolas", 8),
        )
        crop_status = self._current_crop_status()
        if crop_status is not None:
            status_text, is_ready = crop_status
            canvas.create_text(
                26,
                62,
                text=status_text,
                fill="#e7dc85" if is_ready else "#b7d879",
                anchor="nw",
                font=("Consolas", 8, "bold"),
            )

        tile_width = 94
        tile_height = 48
        center_x = width / 2
        center_y = max(170, height * 0.36)
        origin_x = center_x - (
            (self.world.width - self.world.height) * tile_width / 4
        )
        origin_y = center_y - (
            (self.world.width + self.world.height - 2) * tile_height / 4
        )
        ordered_tiles = sorted(
            (
                (x, y, self.world.tile(x, y))
                for x in range(self.world.width)
                for y in range(self.world.height)
            ),
            key=lambda entry: entry[0] + entry[1],
        )
        for x, y, tile in ordered_tiles:
            center_x = origin_x + (x - y) * tile_width / 2
            center_y = origin_y + (x + y) * tile_height / 2
            self._draw_tile(center_x, center_y, tile_width, tile_height, tile.ground)
            harvest = self.harvest_animation
            is_harvesting = (
                harvest is not None
                and (harvest["x"], harvest["y"]) == (x, y)
            )
            entity = harvest["entity"] if is_harvesting else tile.entity
            if entity:
                definition = self.world.defs[entity]
                if is_harvesting:
                    progress = harvest["progress"]
                    animation_progress = min(
                        1.0,
                        harvest["completed_ticks"] / harvest["total_ticks"],
                    )
                    scale = max(0.18, 1.0 - animation_progress * 0.82)
                else:
                    progress = min(1.0, tile.age / definition.grow_ticks)
                    scale = 0.55 + 0.45 * progress
                    animation_progress = 0.0
                entity_x = center_x
                entity_y = center_y - 8
                self._draw_entity(
                    entity_x,
                    entity_y,
                    entity,
                    scale=scale,
                    growth_progress=progress,
                    ready=not is_harvesting and progress >= 1.0,
                )
                if is_harvesting and harvest["mature"] and animation_progress >= 0.4:
                    rewards = "  ".join(
                        f"+{amount} {item.upper()}"
                        for item, amount in harvest["yields"].items()
                    )
                    self.canvas.create_text(
                        center_x,
                        center_y - 34 - animation_progress * 16,
                        text=rewards,
                        fill="#f3e58a",
                        font=("Consolas", 8, "bold"),
                    )

        drone_x = origin_x + (self.drone.x - self.drone.y) * tile_width / 2
        drone_y = origin_y + (self.drone.x + self.drone.y) * tile_height / 2
        harvest = self.harvest_animation
        if harvest is not None and (harvest["x"], harvest["y"]) == (
            self.drone.x,
            self.drone.y,
        ):
            animation_progress = min(
                1.0,
                harvest["completed_ticks"] / harvest["total_ticks"],
            )
            drone_offset = math.sin(animation_progress * math.pi) * 5
            self.canvas.create_line(
                drone_x,
                drone_y - 19 + drone_offset,
                drone_x,
                drone_y + 4,
                fill="#f5f1d6",
                width=2,
            )
        else:
            drone_offset = 0
        self._draw_drone(drone_x, drone_y - 20 + drone_offset)

    def _current_crop_status(self):
        tile = self.drone.tile
        if tile.entity is None:
            if tile.ground == SOIL:
                return "SOIL  READY TO PLANT", False
            return "GRASSLAND  TILL TO PREPARE", False
        definition = self.world.defs[tile.entity]
        progress = min(1.0, tile.age / definition.grow_ticks)
        if progress >= 1:
            return f"{tile.entity.upper()}  READY TO HARVEST", True
        return f"{tile.entity.upper()}  GROWING  {int(progress * 100)}%", False

    def _draw_tile(self, x, y, width, height, ground):
        half_w, half_h = width / 2, height / 2
        top = (x, y - half_h)
        right = (x + half_w, y)
        bottom = (x, y + half_h)
        left = (x - half_w, y)
        depth = 13
        if ground == SOIL:
            top_color, side_color = self.COLORS["soil"], self.COLORS["soil_dark"]
        else:
            variation = (round(x + y) // 30) % 2
            top_color = self.COLORS["grass_alt"] if variation else self.COLORS["grass"]
            side_color = self.COLORS["green_dark"]
        self.canvas.create_polygon(
            left[0], left[1], bottom[0], bottom[1], bottom[0], bottom[1] + depth,
            left[0], left[1] + depth, fill=side_color, outline="",
        )
        self.canvas.create_polygon(
            bottom[0], bottom[1], right[0], right[1], right[0], right[1] + depth,
            bottom[0], bottom[1] + depth, fill=side_color, outline="",
        )
        self.canvas.create_polygon(
            top[0], top[1], right[0], right[1], bottom[0], bottom[1], left[0], left[1],
            fill=top_color, outline="#354b38", width=2,
        )

    def _draw_entity(
        self,
        x,
        y,
        entity,
        *,
        scale=1.0,
        growth_progress=1.0,
        ready=False,
    ):
        def point(px, py):
            return x + px * scale, y + py * scale

        if entity == "grass":
            for offset, color in ((-8, "#b6d76a"), (0, "#d2df77"), (8, "#a5c85b")):
                start = point(0, 9)
                end = point(offset, -10)
                self.canvas.create_line(
                    *start,
                    *end,
                    fill=color,
                    width=max(1, 3 * scale),
                )
        elif entity == "bush":
            self.canvas.create_oval(
                *point(-15, -8),
                *point(15, 12),
                fill="#477442",
                outline="#385c38",
            )
            self.canvas.create_oval(
                *point(-9, -12),
                *point(7, 5),
                fill="#689b4f",
                outline="",
            )
        elif entity == "carrot":
            self.canvas.create_polygon(
                *point(-8, -5),
                *point(8, -5),
                *point(0, 17),
                fill="#ff8a24", outline="#ffe074", width=2,
            )
            self.canvas.create_line(
                *point(0, -5),
                *point(-8, -18),
                fill="#b6ee4b",
                width=max(2, 5 * scale),
            )
            self.canvas.create_line(
                *point(0, -5),
                *point(8, -19),
                fill="#8cda39",
                width=max(2, 5 * scale),
            )
            self.canvas.create_line(
                *point(0, -5),
                *point(0, -21),
                fill="#d1f45d",
                width=max(2, 4 * scale),
            )
        else:
            self.canvas.create_oval(
                *point(-13, -12),
                *point(13, 12),
                fill="#d89245",
                outline="#835c35",
            )
        if ready:
            self.canvas.create_oval(
                x - 19,
                y - 20,
                x + 19,
                y + 15,
                outline="#e7dc85",
                width=2,
            )
        else:
            bar_left = x - 19
            bar_top = y - 29
            self.canvas.create_rectangle(
                bar_left,
                bar_top,
                bar_left + 38,
                bar_top + 5,
                fill="#26312d",
                outline="",
            )
            self.canvas.create_rectangle(
                bar_left,
                bar_top,
                bar_left + 38 * max(0.0, min(1.0, growth_progress)),
                bar_top + 5,
                fill="#b7d879",
                outline="",
            )
            self.canvas.create_text(
                x,
                bar_top - 5,
                text=f"{max(0, min(100, int(growth_progress * 100)))}%",
                fill="#e2e6df",
                font=("Consolas", 7, "bold"),
            )

    def _draw_drone(self, x, y):
        self.canvas.create_oval(x - 25, y + 9, x + 25, y + 19, fill="#465342", outline="")
        self.canvas.create_line(x - 20, y - 12, x + 20, y - 12, fill="#303a3c", width=3)
        self.canvas.create_line(x, y - 12, x, y + 2, fill="#303a3c", width=3)
        self.canvas.create_polygon(
            x - 17, y - 12, x - 11, y - 22, x + 12, y - 22,
            x + 18, y - 12, x + 11, y + 1, x - 11, y + 1,
            fill=self.COLORS["orange"], outline="#694e36", width=2,
        )
        self.canvas.create_rectangle(x - 5, y - 18, x + 5, y - 11, fill="#d4e4dc", outline="")
        for offset in (-22, 22):
            self.canvas.create_oval(x + offset - 5, y - 16, x + offset + 5, y - 8, fill="#293336", outline="#b8c0b7")


def main():
    root = tk.Tk()
    root.withdraw()
    account_store = AccountStore()
    username = AccountDialog(root, account_store).show()
    if username is None:
        root.destroy()
        return
    try:
        account_tag = account_store.tag_for(username)
        app = FarmerApp(
            root,
            username,
            account_store.profile_path(username),
            account_tag,
        )
    except (OSError, ValueError) as exc:
        messagebox.showerror("Progres gagal dimuat", str(exc), parent=root)
        root.destroy()
        return
    root.deiconify()
    app.run()