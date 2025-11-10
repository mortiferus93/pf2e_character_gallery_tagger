#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
from tkinter import (
    Tk, Label, Entry, Button, Checkbutton, IntVar,
    filedialog, messagebox, Frame, LabelFrame,
    VERTICAL, HORIZONTAL, Spinbox
)
from PIL import Image, ImageTk

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_FILE = os.path.join(BASE_DIR, "datasheet.json")


def normalize_path(path: str) -> str:
    """Ersetzt Backslashes durch Slashes – sorgt für konsistente Pfade."""
    return path.replace("\\", "/")


def make_relative(path: str) -> str:
    """Gibt einen relativen Pfad zum Skript‑Ordner zurück."""
    return normalize_path(os.path.relpath(path, BASE_DIR))


class ImageTagger:
    def __init__(self, root):
        self.root = root
        self.root.title("Custom Token Creator")
        # Startgröße – kann später verkleinert werden, aber nicht unter die Mindestgröße.
        self.root.geometry("1100x800")
        self.root.minsize(900, 600)          # **Mindestgröße für ein scroll‑freies Tags‑Panel**

        # ---------- Daten‑Container ----------
        self.current_folder = None
        self.image_files = []
        self.current_index = -1
        self.saved_count = 0
        self.image1_preview = None
        self.image2_preview = None

        # ---------- UI Aufbau ----------
        self._setup_ui()

        # Root‑Grid konfigurieren (Tags‑Frame soll wachsen)
        self.root.rowconfigure(4, weight=1)      # Zeile 4 = tags_frame
        self.root.columnconfigure(0, weight=1)

        # Aktuelle gespeicherte Einträge zählen
        self.update_saved_count()

    # ------------------------------------------------------------------
    # --------------------------- GUI Setup ---------------------------------
    # ------------------------------------------------------------------
    def _setup_ui(self):
        """Erzeugt das komplette Interface – in modularen Unter‑Methoden."""
        # 1. Oberes Eingabe‑Panel
        top_frame = Frame(self.root)
        top_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        top_frame.columnconfigure(1, weight=1)          # Entry soll wachsen

        self._add_path_row(top_frame, 0,
                           "Bildpfad 1 (Portrait/Thumb):",
                           entry_var='path_entry1',
                           button_cb=lambda: self.choose_file(1))

        self._add_path_row(top_frame, 1,
                           "Bildpfad 2 (Token/Subject, optional):",
                           entry_var='path_entry2',
                           button_cb=lambda: self.choose_file(2))

        # Label & Scale
        label_lbl = Label(top_frame, text="Label:")
        label_lbl.grid(row=2, column=0, sticky="w", pady=(5, 0))
        self.label_entry = Entry(top_frame, width=40)
        self.label_entry.grid(row=2, column=1, sticky="ew", pady=(5, 0))

        scale_lbl = Label(top_frame, text="Scale:")
        scale_lbl.grid(row=3, column=0, sticky="w")
        # Spinbox statt normaler Entry
        self.scale_var = IntVar(value=1)
        self.scale_entry = Spinbox(
            top_frame, from_=1, to=10, width=5,
            textvariable=self.scale_var, state='readonly'
        )
        self.scale_entry.grid(row=3, column=1, sticky="w")

        # 2. Vorschauelemente
        preview_frame = Frame(self.root)
        preview_frame.grid(row=1, column=0, pady=5, padx=10, sticky="ew")
        preview_frame.columnconfigure((0, 1), weight=1)

        self.preview_label1 = Label(preview_frame, bd=2, relief="sunken")
        self.preview_label1.grid(row=0, column=0, padx=10)
        self.preview_label2 = Label(preview_frame, bd=2, relief="sunken")
        self.preview_label2.grid(row=0, column=1, padx=10)

        # 3. Buttons Speichern / Überspringen
        button_frame = Frame(self.root)
        button_frame.grid(row=2, column=0, pady=10, sticky="ew")
        button_frame.columnconfigure((0, 1), weight=1)

        Button(button_frame, text="Speichern & nächstes Bild",
               command=self.save_and_next).grid(row=0, column=0, padx=10, sticky="e")
        Button(button_frame, text="Überspringen",
               command=self.skip_image).grid(row=0, column=1, padx=10, sticky="w")

        # 4. Info Label
        self.info_label = Label(self.root, text="Bilder: 0 / 0")
        self.info_label.grid(row=3, column=0, pady=5)

        # 5. Tags Panel (ohne Scrollbar)
        self.tags_frame = Frame(self.root)
        self.tags_frame.grid(row=4, column=0, sticky="nsew", padx=10, pady=10)

        # Inhalt des Panels – ein einfacher Frame
        self.tags_inner = Frame(self.tags_frame)
        self.tags_inner.pack(fill="both", expand=True)

        # Tags‑Struktur erzeugen und Checkbuttons bauen
        self.tags = self.create_tags_structure()
        self.tag_vars = {}
        self._build_tag_checkbuttons()

    def _add_path_row(self, parent, row, label_text, entry_var, button_cb):
        """Hilfsmethode zum Erstellen einer Zeile mit Pfad‑Entry + Buttons."""
        lbl = Label(parent, text=label_text)
        lbl.grid(row=row, column=0, sticky="w")
        entry = Entry(parent, width=50)
        entry.grid(row=row, column=1, sticky="ew", padx=(5, 0))
        setattr(self, entry_var, entry)

        btn_file = Button(parent, text="Datei wählen",
                          command=button_cb)
        btn_file.grid(row=row, column=2, padx=5)

        btn_clear = Button(parent, text="Clear",
                           command=lambda: self.clear_input(entry))
        btn_clear.grid(row=row, column=3)

    # ------------------------------------------------------------------
    # --------------------------- Tags UI --------------------------------
    # ------------------------------------------------------------------
    def _build_tag_checkbuttons(self):
        """Erzeugt für jede Kategorie ein LabelFrame mit Checkbuttons."""
        col = 0
        for cat, options in self.tags.items():
            lf = LabelFrame(
                self.tags_inner,
                text=cat.capitalize(),
                padx=5, pady=5,
                fg="white", bg="#333333",
                bd=2, relief="groove"
            )
            lf.grid(row=0, column=col, padx=5, sticky="n")
            row_idx = 0
            col_idx = 0
            self.tag_vars[cat] = {}
            for opt in options:
                var = IntVar()
                self.tag_vars[cat][opt] = var
                cb = Checkbutton(
                    lf,
                    text=opt,
                    variable=var,
                    bg="#444444",
                    fg="white",
                    selectcolor="#666666"
                )
                cb.grid(row=row_idx, column=col_idx, sticky="w", padx=2, pady=1)
                col_idx += 1
                if col_idx >= 3:
                    col_idx = 0
                    row_idx += 1

            # Die "Alle auswählen / Alle abwählen" Buttons wurden entfernt.
            col += 1

    # ------------------------------------------------------------------
    # --------------------------- Core Functionality --------------------
    # ------------------------------------------------------------------
    def choose_file(self, entry_number):
        file_path = filedialog.askopenfilename(
            title="Bilddatei wählen",
            filetypes=[("Bilddateien", "*.png;*.jpg;*.jpeg;*.bmp;*.gif;*.webp")]
        )
        if not file_path:
            return

        # Pfad in Entry eintragen
        if entry_number == 1:
            self.path_entry1.delete(0, "end")
            self.path_entry1.insert(0, file_path)
            self.load_preview(file_path, 1)

            # Alle Bilder im Ordner sammeln
            self.current_folder = os.path.dirname(file_path)
            all_files = os.listdir(self.current_folder)
            self.image_files = [
                os.path.join(self.current_folder, f)
                for f in all_files
                if f.lower().endswith(
                    (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp")
                )
            ]
            self.image_files.sort()
            self.current_index = self.image_files.index(file_path)

            self.update_saved_count()
            self.update_info_label()

        else:  # entry_number == 2
            self.path_entry2.delete(0, "end")
            self.path_entry2.insert(0, file_path)
            self.load_preview(file_path, 2)

    def load_preview(self, path, number):
        try:
            img = Image.open(path)
            img.thumbnail((250, 250))
            photo = ImageTk.PhotoImage(img)
            if number == 1:
                self.image1_preview = photo
                self.preview_label1.config(image=self.image1_preview)
                basename = os.path.splitext(os.path.basename(path))[0]
                label_text = basename.replace("_", " ").replace("-", " ")
                self.label_entry.delete(0, "end")
                self.label_entry.insert(0, label_text)
            else:
                self.image2_preview = photo
                self.preview_label2.config(image=self.image2_preview)
        except Exception as e:
            messagebox.showerror("Fehler", f"Bild konnte nicht geladen werden:\n{e}")

    def clear_input(self, entry):
        """Clear‑Button für einen Entry – löscht auch die Vorschau."""
        if entry == self.path_entry1:
            self.preview_label1.config(image="")
            self.image1_preview = None
        else:
            self.preview_label2.config(image="")
            self.image2_preview = None

        entry.delete(0, "end")

    def save_and_next(self):
        path1 = self.path_entry1.get()
        if not path1:
            messagebox.showwarning("Fehler", "Bitte Bildpfad 1 wählen!")
            return
        path2 = self.path_entry2.get() or path1

        label = self.label_entry.get().strip()
        if not label:
            messagebox.showwarning("Fehler", "Bitte ein Label eingeben!")
            return

        try:
            scale = int(self.scale_var.get())
        except ValueError:
            messagebox.showwarning("Fehler", "Scale muss eine ganze Zahl sein!")
            return

        tag_data = {}
        for cat, options in self.tag_vars.items():
            selected = [opt for opt, var in options.items() if var.get()]
            if selected:
                tag_data[cat] = selected

        entry = {
            "label": label,
            "key": "custom_token",
            "source": "custom_token",
            "art": {
                "portrait": make_relative(path1),
                "thumb": make_relative(path1),
                "token": make_relative(path2),
                "subject": make_relative(path2),
                "scale": scale
            },
            "tags": tag_data
        }

        data = []
        if os.path.exists(JSON_FILE):
            try:
                with open(JSON_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except json.JSONDecodeError:
                data = []

        data.append(entry)

        try:
            with open(JSON_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except PermissionError:
            messagebox.showerror("Fehler", f"Keine Schreibrechte für:\n{JSON_FILE}")
            return

        self.saved_count += 1
        self.update_info_label()

        # Reset UI
        self.path_entry2.delete(0, "end")
        self.preview_label2.config(image="")
        self.image2_preview = None

        for cat in self.tag_vars.values():
            for var in cat.values():
                var.set(0)

        self.load_next_image()

    def skip_image(self):
        self.load_next_image()

    def load_next_image(self):
        if self.image_files and self.current_index < len(self.image_files) - 1:
            self.current_index += 1
            next_path = self.image_files[self.current_index]
            self.path_entry1.delete(0, "end")
            self.path_entry1.insert(0, next_path)
            self.load_preview(next_path, 1)

            # Bild 2 zurücksetzen
            self.path_entry2.delete(0, "end")
            self.preview_label2.config(image="")
            self.image2_preview = None
        else:
            messagebox.showinfo("Fertig", "Keine weiteren Bilder im Ordner.")
            self.path_entry1.delete(0, "end")
            self.path_entry2.delete(0, "end")
            self.preview_label1.config(image="")
            self.preview_label2.config(image="")
            self.image1_preview = None
            self.image2_preview = None
            self.label_entry.delete(0, "end")

    def update_info_label(self):
        total = len(self.image_files)
        self.info_label.config(text=f"Bilder: {self.saved_count} / {total}")

    def update_saved_count(self):
        """Liest die aktuelle Anzahl gespeicherter Einträge aus der JSON‑Datei."""
        self.saved_count = 0
        if os.path.exists(JSON_FILE):
            try:
                with open(JSON_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.saved_count = len(data)
            except Exception:
                self.saved_count = 0

    # ------------------------------------------------------------------
    # --------------------------- Tag‑Struktur --------------------------------
    # ------------------------------------------------------------------
    def create_tags_structure(self):
        return {
            "category": [
                "humanoid","aberrant","aquatic","bestial","constructed","divine",
                "draconic","elemental","fey","fiendish","fungal","monitor",
                "planar","plant","undead"
            ],
            "ancestry": [
                "dwarf","elf","gnome","goblin","halfling","human","leshy","orc",
                "amurrun","azarketi","fetchling","hobgoblin","iruxi","kholo",
                "kitsune","kobold","nagaji","tengu","tripkee","vanara","ysoki",
                "anadi","android","automaton","conrasu","fleshwarp","ghoran",
                "goloma","kashrishi","kesi","poppet","shisk","shoony","skeleton",
                "sprite","strix","vishkanya","aiuvarin","beastkin","changeling",
                "dhampir","dromaar","geniekin","nephilim"
            ],
            "equipment": [
                "axe","bludgeon","bomb","bow","brawling","crossbow","dart","firearm",
                "flail","knife","pick","polearm","shield","sling","sword",
                "tome","scroll","focus","unarmored","clothing","light","medium","heavy"
            ],
            "features": [
                "magic","music","alchemy","companion","dual-wielding","prosthetic",
                "nature","tech","winged"
            ],
            "family": [
                "civilian","warrior","sage","seafarer","officer","outcast","worker",
                "artisan","affluent"
            ],
            "special": ["bust","unique","iconic","deity"]
        }


# ------------------------------------------------------------------
# --------------------------- Main ------------------------------------
# ------------------------------------------------------------------
if __name__ == "__main__":
    root = Tk()
    app = ImageTagger(root)
    root.mainloop()
