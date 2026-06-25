import customtkinter as ctk
import json
import os
import psutil
import shutil
import tempfile
import threading
import time
import urllib.request
from pathlib import Path
from tkinter import filedialog, messagebox

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")

COLORS = {
    "bg": "#0f0f0f",
    "surface": "#1a1a1a",
    "surface2": "#242424",
    "border": "#2e2e2e",
    "accent": "#3b82f6",
    "accent_hover": "#2563eb",
    "text": "#f0f0f0",
    "text_muted": "#6b7280",
    "text_dim": "#9ca3af",
    "success": "#22c55e",
    "danger": "#ef4444",
    "tag_bg": "#1d2d44",
    "tag_border": "#2d4a70",
}


def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    return {}


def save_settings(data):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def find_multimc_instances(multimc_root):
    instances_path = os.path.join(multimc_root, "instances")
    if not os.path.isdir(instances_path):
        return []
    return [
        d for d in os.listdir(instances_path)
        if os.path.isdir(os.path.join(instances_path, d)) and not d.startswith("_")
    ]


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("MultiMC Manager")
        self.geometry("540x560")
        self.minsize(540, 560)
        self.configure(fg_color=COLORS["bg"])
        self.resizable(False, False)

        self.settings = load_settings()
        self._clean_missing_instances()
        self._current_frame = None
        self._show_startup()

    def _clean_missing_instances(self):
        multimc_path = self.settings.get("multimc_path")
        instances = self.settings.get("instances", [])
        if multimc_path and instances:
            existing = find_multimc_instances(multimc_path)
            cleaned = [i for i in instances if i in existing]
            if cleaned != instances:
                self.settings["instances"] = cleaned
                save_settings(self.settings)

    def _switch_frame(self, frame_cls, **kwargs):
        if self._current_frame:
            self._current_frame.destroy()
        self._current_frame = frame_cls(self, **kwargs)
        self._current_frame.pack(fill="both", expand=True)

    def _show_startup(self):
        self._switch_frame(StartupFrame)

    def _show_multimc_select(self, on_done, back_to=None, found_paths=None):
        self._switch_frame(MultimcSelectFrame, on_done=on_done, back_to=back_to, found_paths=found_paths)

    def _show_instance_select(self, back_to=None):
        self._switch_frame(InstanceSelectFrame, back_to=back_to)

    def _show_main(self):
        self._switch_frame(MainFrame)

    def _show_settings(self):
        self._switch_frame(SettingsFrame)


class StartupFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=COLORS["bg"], corner_radius=0)
        self._label = ctk.CTkLabel(
            self, text="Démarrage...",
            font=ctk.CTkFont(family="SF Pro Display", size=22, weight="bold"),
            text_color=COLORS["text"]
        )
        self._label.place(relx=0.5, rely=0.5, anchor="center")

        self._sub = ctk.CTkLabel(
            self, text="",
            font=ctk.CTkFont(size=13),
            text_color=COLORS["text_muted"]
        )
        self._sub.place(relx=0.5, rely=0.62, anchor="center")

        self._dot_label = ctk.CTkLabel(
            self, text="",
            font=ctk.CTkFont(size=13),
            text_color=COLORS["accent"]
        )
        self._dot_label.place(relx=0.5, rely=0.72, anchor="center")

        threading.Thread(target=self._run_sequence, daemon=True).start()

    def _run_sequence(self):
        time.sleep(2)
        self.after(0, lambda: self._sub.configure(text="Recherche de MultiMC..."))
        self.after(0, lambda: self._animate_dots())
        found_paths = self._find_multimc()
        time.sleep(1.2)
        self.after(0, lambda: self._on_found(found_paths))

    def _animate_dots(self, count=0):
        if not self.winfo_exists():
            return
        dots = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self._dot_label.configure(text=dots[count % len(dots)])
        self._anim_id = self.after(80, lambda: self._animate_dots(count + 1))

    def _find_multimc(self):
        found = []
        try:
            for proc in psutil.process_iter(['name', 'exe']):
                if proc.info['name'] and proc.info['name'].lower() == "multimc.exe":
                    exe = proc.info['exe']
                    if exe:
                        found.append(exe)
        except Exception:
            pass
        return list(set(found))

    def _on_found(self, found_paths):
        if hasattr(self, '_anim_id'):
            self.after_cancel(self._anim_id)
        self._dot_label.configure(text="")

        settings = self.master.settings
        if settings.get("multimc_path") and settings.get("instances"):
            self.master._show_main()
            return

        def on_done():
            self.master._show_instance_select()

        if settings.get("multimc_path"):
            self.master._show_instance_select()
        else:
            self.master._show_multimc_select(on_done=on_done, found_paths=found_paths)


class MultimcSelectFrame(ctk.CTkFrame):
    def __init__(self, master, on_done, back_to=None, found_paths=None):
        super().__init__(master, fg_color=COLORS["bg"], corner_radius=0)
        self._on_done = on_done
        self._back_to = back_to
        self._found_paths = found_paths or []
        self._selected_path = ctk.StringVar()
        self._build_ui()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color=COLORS["surface"], corner_radius=0, height=56)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text="Sélectionnez MultiMC",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=COLORS["text"]
        ).place(relx=0.5, rely=0.5, anchor="center")

        if self._back_to:
            back_btn = ctk.CTkButton(
                header, text="←", width=36, height=36,
                fg_color="transparent", hover_color=COLORS["surface2"],
                text_color=COLORS["text_muted"], font=ctk.CTkFont(size=16),
                command=self._back_to
            )
            back_btn.place(x=10, rely=0.5, anchor="w")

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=32, pady=24)

        ctk.CTkLabel(
            content, text="Sélectionnez votre instance MultiMC",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLORS["text_dim"], anchor="w"
        ).pack(fill="x", pady=(0, 10))

        options = self._found_paths + ["Autre..."]
        display_options = [
            os.path.dirname(p) if p != "Autre..." else "Autre — choisir manuellement"
            for p in options
        ]
        self._option_map = dict(zip(display_options, options))

        if not self._found_paths:
            default = "Autre — choisir manuellement"
        else:
            default = display_options[0]
            self._selected_path.set(self._found_paths[0])

        self._combo = ctk.CTkOptionMenu(
            content,
            values=display_options,
            variable=ctk.StringVar(value=default),
            command=self._on_option_change,
            fg_color=COLORS["surface2"],
            button_color=COLORS["accent"],
            button_hover_color=COLORS["accent_hover"],
            dropdown_fg_color=COLORS["surface"],
            text_color=COLORS["text"],
            font=ctk.CTkFont(size=13),
            height=40,
            anchor="w"
        )
        self._combo.pack(fill="x", pady=(0, 16))

        self._browse_frame = ctk.CTkFrame(content, fg_color="transparent")
        self._browse_frame.pack(fill="x")

        self._browse_btn = ctk.CTkButton(
            self._browse_frame,
            text="📂  Choisir MultiMC.exe",
            font=ctk.CTkFont(size=13),
            height=40,
            fg_color=COLORS["surface2"],
            hover_color=COLORS["border"],
            text_color=COLORS["text_dim"],
            border_width=1,
            border_color=COLORS["border"],
            command=self._browse
        )
        self._browse_btn.pack(fill="x")

        self._path_label = ctk.CTkLabel(
            self._browse_frame, text="",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_muted"], anchor="w", wraplength=440
        )
        self._path_label.pack(fill="x", pady=(6, 0))

        if self._found_paths:
            self._browse_frame.pack_forget()

        footer = ctk.CTkFrame(self, fg_color=COLORS["surface"], corner_radius=0, height=60)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        self._next_btn = ctk.CTkButton(
            footer, text="Suivant →",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            text_color="white", width=120, height=36,
            command=self._save_and_next
        )
        self._next_btn.place(relx=0.97, rely=0.5, anchor="e", x=-12)

        if not self._found_paths and not self._selected_path.get():
            self._next_btn.configure(state="disabled")

    def _on_option_change(self, display_val):
        raw = self._option_map.get(display_val, "")
        if raw == "Autre...":
            self._browse_frame.pack(fill="x")
            self._selected_path.set("")
            self._next_btn.configure(state="disabled")
        else:
            self._browse_frame.pack_forget()
            self._selected_path.set(os.path.dirname(raw))
            self._next_btn.configure(state="normal")

    def _browse(self):
        path = filedialog.askopenfilename(
            title="Sélectionnez MultiMC.exe",
            filetypes=[("Exécutable", "MultiMC.exe"), ("Tous les fichiers", "*.*")]
        )
        if not path:
            return
        if os.path.basename(path).lower() != "multimc.exe":
            messagebox.showerror("Fichier invalide", "Veuillez sélectionner MultiMC.exe")
            return
        root = os.path.dirname(path)
        self._selected_path.set(root)
        self._path_label.configure(text=f"✓  {root}", text_color=COLORS["success"])
        self._next_btn.configure(state="normal")

    def _save_and_next(self):
        path = self._selected_path.get()
        if not path:
            return
        self.master.settings["multimc_path"] = path
        save_settings(self.master.settings)
        self._on_done()


class InstanceSelectFrame(ctk.CTkFrame):
    def __init__(self, master, back_to=None):
        super().__init__(master, fg_color=COLORS["bg"], corner_radius=0)
        self._back_to = back_to
        self._selected = list(master.settings.get("instances", []))
        self._build_ui()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color=COLORS["surface"], corner_radius=0, height=56)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text="Choix des instances",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=COLORS["text"]
        ).place(relx=0.5, rely=0.5, anchor="center")

        if self._back_to:
            ctk.CTkButton(
                header, text="←", width=36, height=36,
                fg_color="transparent", hover_color=COLORS["surface2"],
                text_color=COLORS["text_muted"], font=ctk.CTkFont(size=16),
                command=self._back_to
            ).place(x=10, rely=0.5, anchor="w")

        footer = ctk.CTkFrame(self, fg_color=COLORS["surface"], corner_radius=0, height=60)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        self._next_btn = ctk.CTkButton(
            footer, text="Suivant →",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            text_color="white", width=120, height=36,
            corner_radius=8,
            state="disabled" if not self._selected else "normal",
            command=self._save_and_next
        )
        self._next_btn.pack(side="right", padx=16, pady=12)

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=32, pady=20)

        self._tags_outer = ctk.CTkFrame(content, fg_color="transparent", height=36)
        self._tags_outer.pack(fill="x", pady=(0, 12))
        self._tags_outer.pack_propagate(False)
        self._tags_frame = ctk.CTkFrame(self._tags_outer, fg_color="transparent")
        self._tags_frame.pack(fill="x")
        self._refresh_tags()

        label_row = ctk.CTkFrame(content, fg_color="transparent")
        label_row.pack(fill="x", pady=(0, 6))

        ctk.CTkLabel(
            label_row, text="Instances disponibles",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_muted"], anchor="w"
        ).pack(side="left")

        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._filter_list())
        search_entry = ctk.CTkEntry(
            label_row,
            textvariable=self._search_var,
            placeholder_text="🔍  Rechercher...",
            font=ctk.CTkFont(size=12),
            fg_color=COLORS["surface2"],
            border_color=COLORS["border"],
            text_color=COLORS["text"],
            placeholder_text_color=COLORS["text_muted"],
            height=28, corner_radius=8, width=180
        )
        search_entry.pack(side="right")

        self._list_frame = ctk.CTkScrollableFrame(
            content, fg_color=COLORS["surface"],
            scrollbar_button_color=COLORS["border"],
            corner_radius=10
        )
        self._list_frame.pack(fill="both", expand=True)
        self._btn_widgets = {}
        self._build_list()

    def _refresh_tags(self):
        for w in self._tags_frame.winfo_children():
            w.destroy()

        if not self._selected:
            ctk.CTkLabel(
                self._tags_frame, text="Aucune instance sélectionnée",
                font=ctk.CTkFont(size=12), text_color=COLORS["text_muted"]
            ).pack(side="left")
            return

        for inst in self._selected:
            tag = ctk.CTkFrame(
                self._tags_frame, fg_color=COLORS["tag_bg"], corner_radius=14,
                border_width=1, border_color=COLORS["tag_border"]
            )
            tag.pack(side="left", padx=(0, 6), pady=2)

            ctk.CTkLabel(
                tag, text=inst,
                font=ctk.CTkFont(size=12), text_color=COLORS["accent"]
            ).pack(side="left", padx=(10, 4), pady=4)

            ctk.CTkButton(
                tag, text="✕", width=18, height=18,
                fg_color=COLORS["tag_border"], hover_color=COLORS["danger"],
                text_color=COLORS["text"], font=ctk.CTkFont(size=9),
                corner_radius=9,
                command=lambda i=inst: self._remove(i)
            ).pack(side="left", padx=(0, 6), pady=4)

    def _build_list(self):
        self._btn_widgets.clear()
        for w in self._list_frame.winfo_children():
            w.destroy()

        multimc_path = self.master.settings.get("multimc_path", "")
        self._all_instances = sorted(find_multimc_instances(multimc_path))

        if not self._all_instances:
            ctk.CTkLabel(
                self._list_frame, text="Aucune instance trouvée dans ce dossier.",
                font=ctk.CTkFont(size=12), text_color=COLORS["text_muted"]
            ).pack(pady=20)
            return

        for inst in self._all_instances:
            is_sel = inst in self._selected
            btn = ctk.CTkButton(
                self._list_frame,
                text=f"{'✓  ' if is_sel else '   '}{inst}",
                font=ctk.CTkFont(size=13),
                anchor="w",
                fg_color=COLORS["tag_bg"] if is_sel else COLORS["surface2"],
                hover_color=COLORS["border"],
                text_color=COLORS["accent"] if is_sel else COLORS["text"],
                border_width=1,
                border_color=COLORS["tag_border"] if is_sel else COLORS["border"],
                height=38, corner_radius=8,
                command=lambda i=inst: self._toggle(i)
            )
            btn.pack(fill="x", padx=8, pady=2)
            self._btn_widgets[inst] = btn

    def _update_btn(self, inst):
        btn = self._btn_widgets.get(inst)
        if not btn:
            return
        is_sel = inst in self._selected
        btn.configure(
            text=f"{'✓  ' if is_sel else '   '}{inst}",
            fg_color=COLORS["tag_bg"] if is_sel else COLORS["surface2"],
            text_color=COLORS["accent"] if is_sel else COLORS["text"],
            border_color=COLORS["tag_border"] if is_sel else COLORS["border"],
        )

    def _filter_list(self):
        query = self._search_var.get().lower().strip()
        for inst, btn in self._btn_widgets.items():
            if query in inst.lower():
                btn.pack(fill="x", padx=8, pady=2)
            else:
                btn.pack_forget()

    def _toggle(self, inst):
        if inst in self._selected:
            self._selected.remove(inst)
        else:
            self._selected.append(inst)
        self._update_btn(inst)
        self._refresh_tags()
        self._next_btn.configure(state="normal" if self._selected else "disabled")

    def _remove(self, inst):
        self._selected.remove(inst)
        self._update_btn(inst)
        self._refresh_tags()
        self._next_btn.configure(state="normal" if self._selected else "disabled")

    def _save_and_next(self):
        self.master.settings["instances"] = self._selected
        save_settings(self.master.settings)
        self.master._show_main()


class ConfirmModal(ctk.CTkToplevel):
    def __init__(self, master, on_confirm):
        super().__init__(master)
        self.title("")
        self.geometry("340x160")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["bg"])
        self.grab_set()
        self.focus_force()
        self.transient(master)

        x = master.winfo_x() + (master.winfo_width() - 340) // 2
        y = master.winfo_y() + (master.winfo_height() - 160) // 2
        self.geometry(f"+{x}+{y}")

        self._on_confirm = on_confirm
        self._build_ui()

    def _build_ui(self):
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=28, pady=24)

        ctk.CTkLabel(
            content, text="Avez-vous fermé votre jeu ?",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["text"], anchor="center"
        ).pack(fill="x", pady=(0, 6))

        ctk.CTkLabel(
            content, text="Le fichier mod sera remplacé sur le disque.",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_muted"], anchor="center"
        ).pack(fill="x")

        footer = ctk.CTkFrame(self, fg_color=COLORS["surface"], corner_radius=0, height=52)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        btn_row = ctk.CTkFrame(footer, fg_color="transparent")
        btn_row.place(relx=0.5, rely=0.5, anchor="center")

        non_btn = ctk.CTkButton(
            btn_row, text="Non",
            font=ctk.CTkFont(size=13),
            fg_color="transparent", hover_color=COLORS["surface2"],
            text_color=COLORS["text_muted"],
            width=80, height=34, corner_radius=8,
            border_width=0,
            command=self.destroy
        )
        non_btn.pack(side="left", padx=(0, 8))

        non_btn.configure(font=ctk.CTkFont(size=13, underline=True))

        ctk.CTkButton(
            btn_row, text="Oui",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            text_color="white", width=80, height=34, corner_radius=8,
            command=self._confirm
        ).pack(side="left")

    def _confirm(self):
        self.destroy()
        self._on_confirm()


class ResultModal(ctk.CTkToplevel):
    def __init__(self, master, success, failures):
        super().__init__(master)
        self.title("")
        self.geometry("360x300")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["bg"])
        self.grab_set()
        self.focus_force()
        self.transient(master)

        x = master.winfo_x() + (master.winfo_width() - 360) // 2
        y = master.winfo_y() + (master.winfo_height() - 300) // 2
        self.geometry(f"+{x}+{y}")

        self._build_ui(success, failures)

    def _build_ui(self, success, failures):
        header = ctk.CTkFrame(self, fg_color=COLORS["surface"], corner_radius=0, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        ctk.CTkLabel(
            header, text="Exécution terminée",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["text"]
        ).place(relx=0.5, rely=0.5, anchor="center")

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=16)

        if success:
            ctk.CTkLabel(
                content, text="Installation réussie :",
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=COLORS["success"], anchor="w"
            ).pack(fill="x", pady=(0, 4))
            for inst in success:
                ctk.CTkLabel(
                    content, text=f"  — {inst}",
                    font=ctk.CTkFont(size=12),
                    text_color=COLORS["text_dim"], anchor="w"
                ).pack(fill="x")

        if success and failures:
            ctk.CTkFrame(content, fg_color=COLORS["border"], height=1).pack(fill="x", pady=12)

        if failures:
            ctk.CTkLabel(
                content, text="Installation échec :",
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=COLORS["danger"], anchor="w"
            ).pack(fill="x", pady=(0, 4))
            for inst in failures:
                ctk.CTkLabel(
                    content, text=f"  — {inst}",
                    font=ctk.CTkFont(size=12),
                    text_color=COLORS["text_dim"], anchor="w"
                ).pack(fill="x")

        footer = ctk.CTkFrame(self, fg_color=COLORS["surface"], corner_radius=0, height=52)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        ctk.CTkButton(
            footer, text="Fermer",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            text_color="white", width=100, height=34, corner_radius=8,
            command=self.destroy
        ).pack(side="right", padx=16, pady=9)


class MainFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=COLORS["bg"], corner_radius=0)
        self._build_ui()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color=COLORS["surface"], corner_radius=0, height=56)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text="Action sur les instances",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=COLORS["text"]
        ).place(relx=0.5, rely=0.5, anchor="center")

        gear_btn = ctk.CTkButton(
            header, text="⚙", width=36, height=36,
            fg_color="transparent", hover_color=COLORS["surface2"],
            text_color=COLORS["text_muted"], font=ctk.CTkFont(size=18),
            command=self.master._show_settings
        )
        gear_btn.place(relx=1.0, x=-10, rely=0.5, anchor="e")

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=32, pady=24)

        instances = self.master.settings.get("instances", [])
        ctk.CTkLabel(
            content,
            text=f"Instances actives : {', '.join(instances) if instances else 'aucune'}",
            font=ctk.CTkFont(size=12), text_color=COLORS["text_muted"], anchor="w", wraplength=460
        ).pack(fill="x", pady=(0, 24))

        actions = [
            ("🔄  Réinstaller FSPatches", "#1a2a1a", "#22c55e", "#16a34a", "#1e3d1e", self._action_fspatches),
            ("📦  Installer Loki Client", "#1a1a2e", "#6366f1", "#4f46e5", "#25254a", self._action_loki),
        ]

        self._btn_fspatches = None
        self._btn_loki = None

        for i, (label, bg, color, hover, border, cmd) in enumerate(actions):
            card = ctk.CTkFrame(
                content, fg_color=bg, corner_radius=12,
                border_width=1,
                border_color=border
            )
            card.pack(fill="x", pady=8)

            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="x", padx=20, pady=14)

            ctk.CTkLabel(
                inner, text=label,
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color=color, anchor="w"
            ).pack(side="left")

            btn = ctk.CTkButton(
                inner, text="Lancer",
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color=color, hover_color=hover,
                text_color="white", width=80, height=30,
                corner_radius=8,
                command=cmd
            )
            btn.pack(side="right")
            if i == 0:
                self._btn_fspatches = btn
            else:
                self._btn_loki = btn

    def _spin(self, btn_ref, count=0):
        if getattr(btn_ref, "_spinning", False):
            dots = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
            btn_ref.configure(text=dots[count % len(dots)])
            btn_ref._spin_id = self.after(80, lambda: self._spin(btn_ref, count + 1))

    def _stop_spin(self, btn_ref):
        btn_ref._spinning = False
        if hasattr(btn_ref, "_spin_id"):
            self.after_cancel(btn_ref._spin_id)
        btn_ref.configure(state="normal", text="Lancer")

    def _install_file(self, url, filename, label_key, btn_ref):
        instances = self.master.settings.get("instances", [])
        multimc_path = self.master.settings.get("multimc_path", "")

        if not instances or not multimc_path:
            messagebox.showerror("Erreur", "Aucune instance configurée.")
            return

        btn_ref._spinning = True
        btn_ref.configure(state="disabled", text="⠋")
        self._spin(btn_ref)

        def run():
            errors = []
            for inst in instances:
                mods_dir = os.path.join(multimc_path, "instances", inst, ".minecraft", "mods")
                os.makedirs(mods_dir, exist_ok=True)
                dest = os.path.join(mods_dir, filename)

                try:
                    tmp_fd, tmp_path = tempfile.mkstemp(dir=mods_dir, suffix=".tmp")
                    os.close(tmp_fd)
                    urllib.request.urlretrieve(url, tmp_path)

                    if os.path.exists(dest):
                        try:
                            os.replace(dest, dest + ".bak")
                        except PermissionError:
                            pass

                    try:
                        os.replace(tmp_path, dest)
                    except PermissionError:
                        backup = dest + ".bak"
                        if os.path.exists(backup):
                            os.replace(backup, dest)
                        if os.path.exists(tmp_path):
                            os.remove(tmp_path)
                        errors.append(f"{inst}: fichier verrouillé, impossible de remplacer.")
                        continue

                    backup = dest + ".bak"
                    if os.path.exists(backup):
                        try:
                            os.remove(backup)
                        except Exception:
                            pass

                except Exception as e:
                    if os.path.exists(tmp_path):
                        try:
                            os.remove(tmp_path)
                        except Exception:
                            pass
                    errors.append(f"{inst}: {e}")

            failed_instances = [e.split(":")[0] for e in errors]
            success_instances = [i for i in instances if i not in failed_instances]

            def done():
                self._stop_spin(btn_ref)
                ResultModal(self.master, success_instances, failed_instances)

            self.after(0, done)

        threading.Thread(target=run, daemon=True).start()

    def _action_fspatches(self):
        ConfirmModal(self.master, lambda: self._install_file(
            "https://cdn.46anarchy.fr/files/mods/fspatches.jar",
            "fspatches.jar",
            "FSPatches",
            self._btn_fspatches
        ))

    def _action_loki(self):
        ConfirmModal(self.master, lambda: self._install_file(
            "https://cdn.46anarchy.fr/files/loki.jar",
            "loki.jar",
            "Loki Client",
            self._btn_loki
        ))


class SettingsFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=COLORS["bg"], corner_radius=0)
        self._build_ui()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color=COLORS["surface"], corner_radius=0, height=56)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text="Réglages",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=COLORS["text"]
        ).place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkButton(
            header, text="←", width=36, height=36,
            fg_color="transparent", hover_color=COLORS["surface2"],
            text_color=COLORS["text_muted"], font=ctk.CTkFont(size=16),
            command=self.master._show_main
        ).place(x=10, rely=0.5, anchor="w")

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=32, pady=24)

        self._build_section(
            content,
            title="Chemin MultiMC",
            value=self.master.settings.get("multimc_path", "Non défini"),
            btn_text="Modifier",
            btn_cmd=self._change_multimc
        )

        ctk.CTkFrame(content, fg_color=COLORS["border"], height=1).pack(fill="x", pady=16)

        self._build_section(
            content,
            title="Instances sélectionnées",
            value=", ".join(self.master.settings.get("instances", [])) or "Aucune",
            btn_text="Modifier",
            btn_cmd=self._change_instances
        )

    def _build_section(self, parent, title, value, btn_text, btn_cmd):
        row = ctk.CTkFrame(parent, fg_color=COLORS["surface"], corner_radius=10)
        row.pack(fill="x", pady=4)

        inner = ctk.CTkFrame(row, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=14)

        left = ctk.CTkFrame(inner, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            left, text=title,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLORS["text"], anchor="w"
        ).pack(fill="x")

        ctk.CTkLabel(
            left, text=value,
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_muted"], anchor="w", wraplength=330
        ).pack(fill="x")

        ctk.CTkButton(
            inner, text=btn_text,
            font=ctk.CTkFont(size=12),
            fg_color=COLORS["surface2"], hover_color=COLORS["border"],
            text_color=COLORS["text_dim"],
            border_width=1, border_color=COLORS["border"],
            width=80, height=32,
            command=btn_cmd
        ).pack(side="right")

    def _change_multimc(self):
        def on_done():
            settings = self.master.settings
            multimc_path = settings.get("multimc_path", "")
            existing = find_multimc_instances(multimc_path)
            instances = settings.get("instances", [])
            cleaned = [i for i in instances if i in existing]
            if cleaned != instances:
                settings["instances"] = cleaned
                save_settings(settings)
            self.master._show_settings()

        self.master._show_multimc_select(on_done=on_done, back_to=self.master._show_settings)

    def _change_instances(self):
        self.master._show_instance_select(back_to=self.master._show_settings)


if __name__ == "__main__":
    app = App()
    app.mainloop()