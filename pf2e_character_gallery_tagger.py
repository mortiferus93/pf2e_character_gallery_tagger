#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PF2e Character Gallery Tagger

Kurzbeschreibung:
Dieses Programm ist ein grafisches Werkzeug (Tkinter) zum Durchsehen und Taggen
von Charakterbildern zur Verwendung der Bilder im Foudnrymodul Character Gallery. Es erlaubt, pro Bild ein Label
einzugeben, eine Skalierung festzulegen, optional ein zweites Bild anzugeben
(z. B. Token oder Subject) und aus vordefinierten Tag-Gruppen mehrere Tags
auszuwählen. Die Ergebnisse werden in einer JSON-Datei (datasheet.json)
gespeichert. Bereits verarbeitete Bildpfade werden in einer Logdatei
(processed_log.txt) protokolliert.

"""

import json
import os
import re
from pathlib import Path
from tkinter import (
    Tk, Label, Entry, Button, Checkbutton, IntVar,
    filedialog, messagebox, Frame, LabelFrame, Spinbox, StringVar, Toplevel
)
from PIL import Image, ImageTk

# Basisverzeichnis des Skripts; dort werden die JSON- und Logdatei angelegt.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Dateiname für die gesammelten Tagging-Daten (als Liste von Einträgen).
JSON_FILE = os.path.join(BASE_DIR, "datasheet.json")

# Logdatei, die relative Pfade bereits verarbeiteter Bilder enthält.
LOG_FILE = os.path.join(BASE_DIR, "processed_log.txt")


def normalize_path(path: str) -> str:
    """
    Normalisiere einen Pfad in POSIX-Form.
    Diese Funktion sorgt dafür, dass Pfade plattformübergreifend konsistent
    mit Vorwärtsschrägstrichen gespeichert werden.
    """
    return Path(path).as_posix()


def make_relative(path: str) -> str:
    """
    Erzeuge einen Pfad relativ zum Skript-Ordner und normalisiere ihn.

    Das erleichtert portables Speichern von Bildpfaden in der JSON-Datei,
    da beim Verschieben des Projektordners relative Pfade erhalten bleiben.
    """
    return normalize_path(os.path.relpath(path, BASE_DIR))


class ModuleIDDialog:
    """
    Erstes Eingabefenster beim Programmstart.

    Dient zur Eingabe der Foundry-Modul-ID.
    Die ID darf nur Kleinbuchstaben und Bindestriche enthalten.
    """

    def __init__(self, parent):
        # Erzeuge ein modales Toplevel-Fenster
        self.top = Toplevel(parent)
        self.top.title("Foundry Modul-ID")
        self.top.geometry("420x150")
        self.top.resizable(False, False)
        # grab_set macht das Fenster modal
        self.top.grab_set()

        # Standardwert (Default)
        self.result = StringVar(value="token-sammlung")

        Label(self.top, text="Foundry Modul-ID:", anchor="w").pack(pady=(10, 0), padx=10, anchor="w")
        self.entry = Entry(self.top, textvariable=self.result, width=40)
        self.entry.pack(pady=(2, 5), padx=10)
        self.entry.focus_set()

        # Hinweistext unterhalb des Eingabefeldes
        Label(
            self.top,
            text="Bitte Foundry-ID des Moduls angeben",
            fg="gray"
        ).pack(pady=(0, 10))

        # OK / Abbrechen Buttons
        btn_frame = Frame(self.top)
        btn_frame.pack(pady=5)
        Button(btn_frame, text="OK", command=self.on_ok).pack(side="left", padx=10)
        Button(btn_frame, text="Abbrechen", command=self.on_cancel).pack(side="left", padx=10)

        # Wenn das Fenster geschlossen wird, wie Abbrechen behandeln
        self.top.protocol("WM_DELETE_WINDOW", self.on_cancel)

        # Warte, bis das Dialogfenster geschlossen wurde
        self.top.wait_window()

    def on_ok(self):
        """
        Validiert die Eingabe: nur a-z und '-' sind erlaubt.
        Schließt das Fenster bei gültiger Eingabe.
        """
        value = self.result.get().strip()
        if not re.fullmatch(r"[a-z-]+", value):
            messagebox.showerror(
                "Ungültige Eingabe",
                "Die Modul-ID darf nur Kleinbuchstaben und Bindestriche enthalten."
            )
            return
        self.top.destroy()

    def on_cancel(self):
        """
        Setzt das Ergebnis auf leer und schließt das Fenster.
        Ein leerer Wert signalisiert dem Aufrufer, dass abgebrochen wurde.
        """
        self.result.set("")
        self.top.destroy()


class ImageTagger:
    """
    Hauptklasse für die grafische Anwendung.

    Verantwortlichkeiten:
    - Aufbau und Verwaltung der Tkinter-Oberfläche
    - Laden und Anzeigen von Bildvorschauen
    - Erfassen der Benutzereingaben (Label, Scale, Tags)
    - Speichern der Ergebnisse in die JSON-Datei
    - Protokollieren verarbeiteter Bilder in der Logdatei
    """

    def __init__(self, root):
        # Zuerst die Foundry Modul-ID abfragen; bei Abbruch Anwendung beenden
        dialog = ModuleIDDialog(root)
        self.module_id = dialog.result.get().strip()
        if not self.module_id:
            # Benutzer hat abgebrochen; Hauptfenster schließen
            root.destroy()
            return

        self.root = root
        self.root.title("PF2e Character Gallery Tagger")
        self.root.geometry("1260x1000")
        self.root.minsize(1260, 1000)

        # Interner Zustand für die Bildersammlung und Vorschaubilder
        self.current_folder = None        # Ordner, aus dem Bilder geladen werden
        self.image_files = []             # Liste aller Bildpfade im aktuellen Ordner
        self.current_index = -1           # Index des aktuell geladenen Bilds in image_files
        self.saved_count = 0              # Anzahl gespeicherter Einträge (aus JSON)
        self.image1_preview = None        # Referenz auf PhotoImage für Vorschaubild 1
        self.image2_preview = None        # Referenz auf PhotoImage für Vorschaubild 2

        # Gelernte/verarbeitete Pfade aus der Logdatei laden
        self.processed_paths = self._load_processed_paths()

        # Aufbau der Benutzeroberfläche und Konfiguration des Wurzel-Layouts
        self._setup_ui()
        self.root.rowconfigure(4, weight=1)
        self.root.columnconfigure(0, weight=1)

        # Anzahl der bereits gespeicherten Einträge ermitteln (für Statusanzeige)
        self.update_saved_count()

    # ------------------------------------------------------------------
    # GUI-Aufbau und Hilfsmethoden
    # ------------------------------------------------------------------
    def _setup_ui(self):
        """
        Erzeugt die komplette Benutzeroberfläche.

        Bereichsaufteilung:
        - top_frame: Pfad-Eingaben, Label und Scale
        - preview_frame: Bildvorschauen (zwei Spalten)
        - button_frame: Steuerungsbuttons (Speichern / Überspringen)
        - tags_frame: Tag-Gruppen mit Checkbuttons und pro-Gruppe Toggle
        """
        # Oberes Panel für Pfade / Label / Scale
        top_frame = Frame(self.root)
        top_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        top_frame.columnconfigure(1, weight=1)  # Entry-Felder sollen wachsen

        # Zeile: Bildpfad 1 (Pflichtfeld)
        self._add_path_row(
            top_frame, 0,
            "Bildpfad 1 (Portrait/Thumb):",
            entry_var='path_entry1',
            button_cb=lambda: self.choose_file(1)
        )

        # Zeile: Bildpfad 2 (optional, Token/Subject)
        self._add_path_row(
            top_frame, 1,
            "Bildpfad 2 (Token/Subject, optional):",
            entry_var='path_entry2',
            button_cb=lambda: self.choose_file(2)
        )

        # Label-Eingabe (für das spätere JSON-Feld "label")
        label_lbl = Label(top_frame, text="Label:")
        label_lbl.grid(row=2, column=0, sticky="w", pady=(5, 0))
        self.label_entry = Entry(top_frame, width=40)
        self.label_entry.grid(row=2, column=1, sticky="ew", pady=(5, 0))

        # Scale-Eingabe als Spinbox (ganzzahlig, 1..10)
        scale_lbl = Label(top_frame, text="Scale:")
        scale_lbl.grid(row=3, column=0, sticky="w")
        self.scale_var = IntVar(value=1)
        self.scale_entry = Spinbox(
            top_frame, from_=1, to=10, width=5,
            textvariable=self.scale_var, state='readonly'
        )
        self.scale_entry.grid(row=3, column=1, sticky="w")

        # Vorschau-Bereich: zwei Spalten für Portrait/Thumb und Token/Subject
        preview_frame = Frame(self.root)
        preview_frame.grid(row=1, column=0, pady=5, padx=10, sticky="ew")
        preview_frame.columnconfigure((0, 1), weight=1)

        self.preview_label1 = Label(preview_frame, bd=2, relief="sunken")
        self.preview_label1.grid(row=0, column=0, padx=10)
        self.preview_label2 = Label(preview_frame, bd=2, relief="sunken")
        self.preview_label2.grid(row=0, column=1, padx=10)

        # Buttons: Speichern & Überspringen
        button_frame = Frame(self.root)
        button_frame.grid(row=2, column=0, pady=10, sticky="ew")
        button_frame.columnconfigure((0, 1), weight=1)

        Button(
            button_frame,
            text="Speichern & nächstes Bild",
            command=self.save_and_next
        ).grid(row=0, column=0, padx=10, sticky="e")

        Button(
            button_frame,
            text="Überspringen",
            command=self.skip_image
        ).grid(row=0, column=1, padx=10, sticky="w")

        # Statuslabel für Anzahl gespeicherter Bilder / Anzahl Bilder im Ordner
        self.info_label = Label(self.root, text="Bilder: 0 / 0")
        self.info_label.grid(row=3, column=0, pady=5)

        # Tags-Bereich: wird mit LabelFrames für jede Tag-Gruppe gefüllt
        self.tags_frame = Frame(self.root)
        self.tags_frame.grid(row=4, column=0, sticky="nsew", padx=10, pady=10)
        self.tags_inner = Frame(self.tags_frame)
        self.tags_inner.pack(fill="both", expand=True)

        # Tag-Struktur definieren, Variablencontainer vorbereiten und UI bauen
        self.tags = self.create_tags_structure()
        self.tag_vars = {}         # dict: gruppe -> {tag_name: IntVar}
        self.keep_group_vars = {}  # dict: gruppe -> IntVar (Toggle "Tags behalten")
        self._build_tag_checkbuttons()

    def _add_path_row(self, parent, row, label_text, entry_var, button_cb):
        """
        Hilfsfunktion zum Erzeugen einer Zeile mit:
        - Label
        - Entry (für Pfad)
        - Button "Datei wählen"
        - Button "Clear"

        Parameter:
        - parent: übergeordnetes Frame
        - row: Zeilenindex im Grid des parent
        - label_text: sichtbarer Text links
        - entry_var: Attributname (als String), z.B. 'path_entry1'
        - button_cb: Callback-Funktion für den "Datei wählen"-Button
        """
        lbl = Label(parent, text=label_text)
        lbl.grid(row=row, column=0, sticky="w")

        entry = Entry(parent, width=50)
        entry.grid(row=row, column=1, sticky="ew", padx=(5, 0))
        setattr(self, entry_var, entry)  # z.B. self.path_entry1 = entry

        btn_file = Button(parent, text="Datei wählen", command=button_cb)
        btn_file.grid(row=row, column=2, padx=5)

        btn_clear = Button(parent, text="Löschen", command=lambda: self.clear_input(entry))
        btn_clear.grid(row=row, column=3)

    # ------------------------------------------------------------------
    # Aufbau der Tag-Checkboxen inklusive per-Gruppe Toggle
    # ------------------------------------------------------------------
    def _build_tag_checkbuttons(self):
        """
        Erzeugt pro Tag-Gruppe ein LabelFrame, füllt es mit Checkbuttons für
        die einzelnen Tags und fügt unter jeder Gruppe einen Checkbutton
        hinzu, mit dem das Beibehalten der Tags (für die Gruppe) gesteuert wird.

        Intern werden zwei Mappings gepflegt:
        - self.tag_vars[group][tag] -> IntVar für jeden Tag
        - self.keep_group_vars[group] -> IntVar für den "Tags behalten"-Toggle
        """
        col = 0  # Spaltenindex für die Gruppen anordnen
        for cat, options in self.tags.items():
            # LabelFrame für die Gruppe (z.B. "Category", "Ancestry")
            lf = LabelFrame(
                self.tags_inner,
                text=cat.capitalize(),
                padx=5, pady=5, bd=2, relief="groove"
            )
            lf.grid(row=0, column=col, padx=5, sticky="n")

            # Positionierung der Tag-Checkbuttons innerhalb der Gruppe
            row_idx = 0
            col_idx = 0
            self.tag_vars[cat] = {}

            # Anzahl Spalten innerhalb der Gruppe festlegen, um Layout zu glätten
            max_cols = 2 if cat in ("category", "features", "family", "special", "equipment") else 3

            for opt in options:
                var = IntVar()
                self.tag_vars[cat][opt] = var
                cb = Checkbutton(lf, text=opt, variable=var)
                cb.grid(row=row_idx, column=col_idx, sticky="w", padx=2, pady=1)

                col_idx += 1
                if col_idx >= max_cols:
                    col_idx = 0
                    row_idx += 1

            # Nach den Tag-Checkboxen ein zusätzlicher Checkbutton:
            # "Tags behalten" für diese Gruppe (default: aus)
            keep_var = IntVar(value=0)
            self.keep_group_vars[cat] = keep_var
            keep_cb = Checkbutton(lf, text="Tags behalten", variable=keep_var)
            # Platzierung unterhalb der letzten Tag-Zeile; es wird die komplette
            # Spaltenbreite der Gruppe eingenommen
            keep_cb.grid(row=row_idx + 1, column=0, columnspan=max_cols, sticky="w", pady=(5, 0))

            col += 1

    # ------------------------------------------------------------------
    # Dateiauswahl und Vorschauladen
    # ------------------------------------------------------------------
    def choose_file(self, entry_number):
        """
        Öffnet einen Dateidialog zur Auswahl einer Bilddatei und lädt die
        Datei in das entsprechende Entry-Feld und die Vorschau.

        Verhalten:
        - entry_number == 1: Bildpfad 1 (Portrait) auswählen; zusätzlich
          werden alle Bilddateien im Ordner gesammelt und als "image_files"
          gespeichert, damit 'nächste Bild'-Funktion funktioniert.
        - entry_number == 2: Bildpfad 2 (Token) wählen; lediglich Vorschau laden.

        Zusätzlich wird geprüft, ob das Bild bereits in der Logdatei auftaucht.
        """
        file_path = filedialog.askopenfilename(
            title="Bilddatei wählen",
            filetypes=[("Bilddateien", "*.png;*.jpg;*.jpeg;*.bmp;*.gif;*.webp")]
        )
        if not file_path:
            return

        # Relativer Pfad für Logvergleich
        rel_path = make_relative(file_path)
        if rel_path in self.processed_paths:
            messagebox.showwarning(
                "Hinweis",
                f"Dieses Bild wurde bereits bearbeitet:\n{file_path}"
            )

        if entry_number == 1:
            # Pfad in Entry 1 eintragen und Vorschaubild laden
            self.path_entry1.delete(0, "end")
            self.path_entry1.insert(0, file_path)
            self.load_preview(file_path, 1)

            # Sammle alle Bilddateien aus dem Ordner für Vor-/Zurück-Navigation
            self.current_folder = os.path.dirname(os.path.abspath(file_path))
            all_files = os.listdir(self.current_folder)
            self.image_files = [
                os.path.abspath(os.path.join(self.current_folder, f))
                for f in all_files
                if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"))
            ]
            self.image_files.sort()

            # Versuche, den aktuellen Index auf das ausgewählte Bild zu setzen.
            abs_file_path = os.path.abspath(file_path)
            try:
                self.current_index = self.image_files.index(abs_file_path)
            except ValueError:
                # Fallback: vergleiche aufgelöste Pfade (resolve)
                self.current_index = next((i for i, p in enumerate(self.image_files)
                                           if Path(p).resolve() == Path(abs_file_path).resolve()), 0)

            self.update_saved_count()
            self.update_info_label()
        else:
            # Für Entry 2 nur das Feld füllen und die Vorschau anzeigen
            self.path_entry2.delete(0, "end")
            self.path_entry2.insert(0, file_path)
            self.load_preview(file_path, 2)

    def load_preview(self, path, number):
        """
        Lädt ein Bild, erzeugt ein Thumbnail und zeigt es in einem Label an.

        Parameter:
        - path: Pfad zur Bilddatei
        - number: 1 oder 2 (entsprechendes Vorschau-Label)

        Hinweise:
        - Es wird PIL.Image verwendet; bei Ladefehler wird eine Fehlermeldung angezeigt.
        - Für das erste Bild (number == 1) wird außerdem automatisch ein
          Vorschlags-Label aus dem Dateinamen erzeugt (Unterstriche / Bindestriche
          werden durch Leerzeichen ersetzt).
        """
        try:
            img = Image.open(path)
            img.thumbnail((250, 250))  # Thumbnail-Größe beschränkt Auflösung und Speicher
            photo = ImageTk.PhotoImage(img)

            if number == 1:
                # Referenz speichern, sonst wird das Bild vom Garbage Collector entfernt
                self.image1_preview = photo
                self.preview_label1.config(image=self.image1_preview)

                # Generiere einen sinnvollen Label-Vorschlag aus dem Dateinamen
                basename = os.path.splitext(os.path.basename(path))[0]
                label_text = basename.replace("_", " ").replace("-", " ")
                self.label_entry.delete(0, "end")
                self.label_entry.insert(0, label_text)
            else:
                self.image2_preview = photo
                self.preview_label2.config(image=self.image2_preview)
        except Exception as e:
            # Fehlermeldung bei Problemen mit dem Dateiformat oder Dateizugriff
            messagebox.showerror("Fehler", f"Bild konnte nicht geladen werden:\n{e}")

    def clear_input(self, entry):
        """
        Löscht den Inhalt eines Entry-Feldes und entfernt die zugehörige Vorschau.

        Wird verwendet von den "Clear"-Buttons neben den Pfad-Entries.
        """
        if entry == self.path_entry1:
            self.preview_label1.config(image="")
            self.image1_preview = None
        else:
            self.preview_label2.config(image="")
            self.image2_preview = None

        entry.delete(0, "end")

    # ------------------------------------------------------------------
    # Speichern, Loggen und Weiterschalten
    # ------------------------------------------------------------------
    def save_and_next(self):
        """
        Validiert Eingaben, erzeugt den JSON-Eintrag und speichert ihn.

        Ablauf:
        1. Pfad 1 und Label prüfen.
        2. Scale einlesen und prüfen.
        3. Tags aus allen Gruppen sammeln.
        4. JSON-Datei laden (falls vorhanden), neuen Eintrag anhängen und speichern.
        5. Relativen Pfad des Bildes in die Logdatei schreiben (falls noch nicht vorhanden).
        6. Tags für jede Gruppe zurücksetzen, wenn der zugehörige Keep-Toggle deaktiviert ist.
        7. Vorschau und Felder für Bild 2 zurücksetzen und zum nächsten Bild wechseln.
        """
        path1 = self.path_entry1.get()
        if not path1:
            messagebox.showwarning("Fehler", "Bitte Bildpfad 1 wählen!")
            return

        # Bild 2 ist optional; Standard ist Bild 1
        path2 = self.path_entry2.get() or path1

        # Label einlesen und prüfen
        label = self.label_entry.get().strip()
        if not label:
            messagebox.showwarning("Fehler", "Bitte ein Label eingeben!")
            return

        # Scale validieren (ganzzahlig)
        try:
            scale = int(self.scale_var.get())
        except ValueError:
            messagebox.showwarning("Fehler", "Scale muss eine ganze Zahl sein!")
            return

        # Erzeuge den 'key' aus dem Label: Leerzeichen -> Bindestrich
        key_value = label.replace(" ", "-")

        # Sammle ausgewählte Tags je Gruppe
        tag_data = {}
        for cat, options in self.tag_vars.items():
            selected = [opt for opt, var in options.items() if var.get()]
            if selected:
                tag_data[cat] = selected

        # Hilfsfunktion: prepend module path to relative path
        def make_foundry_path(p):
            """
            Erzeugt einen Foundry-kompatiblen Pfad, indem der relative Pfad
            mit /modules/<module_id>/ vorangestellt wird.
            """
            return f"/modules/{self.module_id}/{make_relative(p)}"

        # Zusammensetzen des Eintrags für die JSON-Datei.
        # Das Feld "source" ist fest auf "Token Sammlung" gesetzt.
        entry = {
            "label": label,
            "key": key_value,
            "source": "Token Sammlung",
            "art": {
                "portrait": make_foundry_path(path1),
                "thumb": make_foundry_path(path1),
                "token": make_foundry_path(path2),
                "subject": make_foundry_path(path2),
                "scale": scale
            },
            "tags": tag_data
        }

        # Vorhandene JSON-Datei laden (falls lesbar), sonst mit leerer Liste starten.
        data = []
        if os.path.exists(JSON_FILE):
            try:
                with open(JSON_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except json.JSONDecodeError:
                # Wenn die Datei beschädigt ist, vermeiden wir Absturz; es wird
                # mit einer neuen Liste weitergearbeitet. Bestehende Datei bleibt unangetastet.
                data = []

        # Neuen Eintrag anhängen und Datei schreiben.
        data.append(entry)
        try:
            with open(JSON_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except PermissionError:
            messagebox.showerror("Fehler", f"Keine Schreibrechte für:\n{JSON_FILE}")
            return
        except Exception as e:
            messagebox.showerror("Fehler", f"Beim Schreiben der JSON-Datei ist ein Fehler aufgetreten:\n{e}")
            return

        # Relativen Pfad in die Logdatei hinzufügen (nur wenn noch nicht vorhanden)
        rel_path = make_relative(path1)
        if rel_path not in self.processed_paths:
            self.processed_paths.add(rel_path)
            self._append_to_log(rel_path)

        # Anzahl gespeicherter Einträge aktualisieren und Info-Label setzen
        self.saved_count += 1
        self.update_info_label()

        # Nur die Gruppen zurücksetzen, deren "Tags behalten"-Toggle deaktiviert ist.
        # Die Keep-Flags werden in self.keep_group_vars geführt.
        for cat, options in self.tag_vars.items():
            keep_flag = self.keep_group_vars.get(cat)
            if not keep_flag or not keep_flag.get():
                # Toggle nicht gesetzt: Checkboxen dieser Gruppe zurücksetzen
                for var in options.values():
                    var.set(0)

        # Bild 2 und seine Vorschau zurücksetzen
        self.path_entry2.delete(0, "end")
        self.preview_label2.config(image="")
        self.image2_preview = None

        # Zum nächsten Bild navigieren (falls vorhanden)
        self.load_next_image()

    def skip_image(self):
        """
        Überspringt das aktuelle Bild ohne zu speichern und lädt das nächste Bild.
        """
        self.load_next_image()

    def load_next_image(self):
        """
        Lädt das nächste Bild aus self.image_files, falls vorhanden.

        Verhalten:
        - Index erhöhen und die Vorschau (Portrait) des nächsten Bilds laden.
        - Felder für Bild 2 wieder zurücksetzen.
        - Wenn kein weiteres Bild vorhanden ist, wird eine Informationsbox angezeigt
          und das UI wird in einen leeren Zustand zurückgesetzt.
        """
        if self.image_files and self.current_index < len(self.image_files) - 1:
            self.current_index += 1
            next_path = self.image_files[self.current_index]
            self.path_entry1.delete(0, "end")
            self.path_entry1.insert(0, next_path)
            self.load_preview(next_path, 1)

            # Bild 2 und Vorschau zurücksetzen
            self.path_entry2.delete(0, "end")
            self.preview_label2.config(image="")
            self.image2_preview = None
        else:
            # Kein weiteres Bild im Ordner
            messagebox.showinfo("Fertig", "Keine weiteren Bilder im Ordner.")
            self.path_entry1.delete(0, "end")
            self.path_entry2.delete(0, "end")
            self.preview_label1.config(image="")
            self.preview_label2.config(image="")
            self.image1_preview = None
            self.image2_preview = None
            self.label_entry.delete(0, "end")

    # ------------------------------------------------------------------
    # Hilfsfunktionen: Statusaktualisierung & Logverwaltung
    # ------------------------------------------------------------------
    def update_info_label(self):
        """
        Aktualisiert das Status-Label mit Anzahl gespeicherter Einträge und
        Anzahl der gefundenen Bilder im aktuellen Ordner.
        """
        total = len(self.image_files)
        self.info_label.config(text=f"Bilder: {self.saved_count} / {total}")

    def update_saved_count(self):
        """
        Liest die JSON-Datei ein und setzt self.saved_count auf die Anzahl
        der vorhandenen Einträge. Bei Lesefehlern wird saved_count auf 0 gesetzt.
        """
        self.saved_count = 0
        if os.path.exists(JSON_FILE):
            try:
                with open(JSON_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Erwartung: data ist eine Liste von Einträgen
                    if isinstance(data, list):
                        self.saved_count = len(data)
            except Exception:
                # Bei Problemen (z. B. beschädigter JSON) verbleibt saved_count bei 0
                self.saved_count = 0

    def _load_processed_paths(self):
        """
        Lädt bereits verarbeitete (relative) Pfade aus der Logdatei und gibt
        sie als Set zurück. Bei Lesefehlern wird ein leeres Set zurückgegeben.

        Rückgabe:
        - Set von Strings (relativer Pfade)
        """
        if os.path.exists(LOG_FILE):
            try:
                with open(LOG_FILE, "r", encoding="utf-8") as f:
                    return set(line.strip() for line in f if line.strip())
            except Exception as e:
                messagebox.showerror(
                    "Fehler beim Laden des Log-Speichers",
                    f"Die Logdatei konnte nicht gelesen werden:\n{e}"
                )
        return set()

    def _append_to_log(self, rel_path: str):
        """
        Hängt einen relativen Pfad an die Logdatei an. Bei Fehlern wird eine
        Fehlermeldung angezeigt, die Anwendung aber nicht zwangsweise beendet.
        """
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(rel_path + "\n")
        except Exception as e:
            messagebox.showerror(
                "Fehler beim Loggen",
                f"Die Logdatei konnte nicht geschrieben werden:\n{e}"
            )

    # ------------------------------------------------------------------
    # Tag-Struktur
    # ------------------------------------------------------------------
    def create_tags_structure(self):
        """
        Definiert die verfügbaren Tag-Gruppen und die jeweiligen Tag-Optionen.

        Rückgabe:
        - Dictionary: gruppenname -> Liste von Tag-Strings

        Hinweis:
        - Diese Struktur ist aktuell fest kodiert. Bei Bedarf kann sie aus
          einer externen Datei geladen werden, um Anpassungen ohne Codeänderung
          zu ermöglichen.
        """
        return {
            "category": [
                "humanoid", "aberrant", "aquatic", "bestial", "constructed", "divine",
                "draconic", "elemental", "fey", "fiendish", "fungal", "monitor",
                "planar", "plant", "undead"
            ],
            "ancestry": [
                "dwarf", "elf", "gnome", "goblin", "halfling", "human", "leshy", "orc",
                "amurrun", "azarketi", "fetchling", "hobgoblin", "iruxi", "kholo",
                "kitsune", "kobold", "nagaji", "tengu", "tripkee", "vanara", "ysoki",
                "anadi", "android", "automaton", "conrasu", "fleshwarp", "ghoran",
                "goloma", "kashrishi", "poppet", "shisk", "shoony", "skeleton",
                "sprite", "strix", "vishkanya", "aiuvarin", "beastkin", "changeling",
                "dhampir", "dromaar", "geniekin", "nephilim"
            ],
            "equipment": [
                "axe", "bludgeon", "bomb", "bow", "brawling", "crossbow", "dart",
                "firearm", "flail", "knife", "pick", "polearm", "shield", "sling",
                "sword", "tome", "scroll", "focus", "unarmored", "clothing",
                "light", "medium", "heavy"
            ],
            "features": [
                "magic", "music", "alchemy", "companion", "dual-wielding",
                "prosthetic", "nature", "tech", "winged"
            ],
            "family": [
                "civilian", "warrior", "sage", "seafarer", "officer", "outcast",
                "worker", "artisan", "affluent"
            ],
            "special": ["bust", "unique", "iconic", "deity"]
        }


if __name__ == "__main__":
    root = Tk()
    app = ImageTagger(root)
    # Falls der Benutzer beim Modul-ID Dialog abgebrochen hat, ist app ggf. None oder root zerstört.
    try:
        root.mainloop()
    except Exception:
        # Bei unerwarteten Fehlern das Programm sauber beenden
        try:
            root.destroy()
        except Exception:
            pass
