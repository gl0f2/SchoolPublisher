"""Eingabemaske für Gewichtungen und tatsächliche Leistungserhebungen."""
from __future__ import annotations
import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox
from config import MATRIX_FILE
from importer import MatrixImporter

ROOT = Path(__file__).resolve().parent.parent
DATEI = ROOT / "data" / "bewertungen.json"
STANDARD_ERHEBUNGEN = ["Klassenarbeiten", "Tests", "Projekte", "Praktische Arbeiten", "Sonstige"]

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SchoolPublisher – Bewertungen bearbeiten")
        self.geometry("840x650")
        self.minsize(760, 560)
        self.daten = self._laden()
        self.faecher = sorted({e.anzeigename for e in MatrixImporter(MATRIX_FILE).load()}, key=str.casefold)
        self.zeilen = []
        self._ui()
        if self.faecher:
            self.fach.set(self.faecher[0]); self._fach_laden()

    def _laden(self):
        if DATEI.is_file():
            try: return json.loads(DATEI.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError): pass
        return {"faecher": {}}

    def _ui(self):
        kopf=ttk.Frame(self,padding=16); kopf.pack(fill="x")
        ttk.Label(kopf,text="Fach:").pack(side="left")
        self.fach=tk.StringVar()
        cb=ttk.Combobox(kopf,textvariable=self.fach,values=self.faecher,state="readonly",width=35)
        cb.pack(side="left",padx=8); cb.bind("<<ComboboxSelected>>",lambda _e:self._fach_laden())
        ttk.Button(kopf,text="Speichern",command=self._speichern).pack(side="right")

        haupt=ttk.Frame(self,padding=(16,0,16,16)); haupt.pack(fill="both",expand=True)
        rahmen=ttk.LabelFrame(haupt,text="Gesamtbewertung",padding=12); rahmen.pack(fill="x")
        self.links=tk.StringVar(value="Mündlich"); self.rechts=tk.StringVar(value="Schriftlich")
        self.gl=tk.StringVar(value="2"); self.gr=tk.StringVar(value="1")
        for c,(label,var,w) in enumerate((("Bereich 1",self.links,22),("Gewicht",self.gl,8),("Bereich 2",self.rechts,22),("Gewicht",self.gr,8))):
            ttk.Label(rahmen,text=label).grid(row=0,column=c,padx=4,sticky="w")
            ttk.Entry(rahmen,textvariable=var,width=w).grid(row=1,column=c,padx=4,sticky="ew")

        er=ttk.LabelFrame(haupt,text="Tatsächliche Leistungserhebungen",padding=12); er.pack(fill="both",expand=True,pady=(14,0))
        ttk.Label(er,text="Bezeichnung").grid(row=0,column=0,sticky="w")
        ttk.Label(er,text="Anzahl").grid(row=0,column=1,sticky="w")
        ttk.Label(er,text="Gewicht").grid(row=0,column=2,sticky="w")
        self.zeilenrahmen=er
        for name in STANDARD_ERHEBUNGEN: self._zeile_hinzufuegen(name)
        ttk.Button(er,text="+ weitere Art",command=lambda:self._zeile_hinzufuegen("")).grid(row=99,column=0,pady=12,sticky="w")
        ttk.Label(haupt,text="Nur Erhebungen mit Anzahl größer 0 erscheinen auf der Karte. Eine Gewichtungszeile erscheint erst bei mindestens zwei vorhandenen Arten mit Gewicht.",wraplength=760).pack(fill="x",pady=10)

    def _zeile_hinzufuegen(self,name="",anzahl="",gewicht=""):
        r=len(self.zeilen)+1
        vars_=(tk.StringVar(value=name),tk.StringVar(value=str(anzahl)),tk.StringVar(value=str(gewicht)))
        ttk.Entry(self.zeilenrahmen,textvariable=vars_[0],width=35).grid(row=r,column=0,padx=(0,8),pady=3,sticky="ew")
        ttk.Entry(self.zeilenrahmen,textvariable=vars_[1],width=10).grid(row=r,column=1,padx=8,pady=3)
        ttk.Entry(self.zeilenrahmen,textvariable=vars_[2],width=10).grid(row=r,column=2,padx=8,pady=3)
        self.zeilen.append(vars_)

    def _fach_laden(self):
        d=self.daten.get("faecher",{}).get(self.fach.get(),{})
        self.links.set(d.get("bereich_links","Mündlich")); self.rechts.set(d.get("bereich_rechts","Schriftlich"))
        self.gl.set(str(d.get("gewicht_links",2))); self.gr.set(str(d.get("gewicht_rechts",1)))
        vorhand={e.get("bezeichnung",""):e for e in d.get("leistungserhebungen",[])}
        for name,anz,gew in self.zeilen:
            e=vorhand.get(name.get(),{})
            anz.set(str(e.get("anzahl",""))); gew.set(str(e.get("gewicht","")))

    def _zahl(self,text,pflicht=False):
        text=text.strip().replace(",", ".")
        if not text and not pflicht: return None
        z=float(text)
        if z <= 0: raise ValueError
        return int(z) if z.is_integer() else z

    def _speichern(self):
        try:
            eintraege=[]
            for name,anz,gew in self.zeilen:
                bez=name.get().strip(); a=anz.get().strip(); g=gew.get().strip()
                if not bez or not a: continue
                anzahl=int(a)
                if anzahl < 0: raise ValueError
                eintraege.append({"bezeichnung":bez,"anzahl":anzahl,"gewicht":self._zahl(g)})
            self.daten.setdefault("faecher",{})[self.fach.get()]={
                "bereich_links":self.links.get().strip() or "Mündlich",
                "bereich_rechts":self.rechts.get().strip() or "Schriftlich",
                "gewicht_links":self._zahl(self.gl.get(),True),
                "gewicht_rechts":self._zahl(self.gr.get(),True),
                "leistungserhebungen":eintraege,
            }
            DATEI.parent.mkdir(parents=True,exist_ok=True)
            DATEI.write_text(json.dumps(self.daten,ensure_ascii=False,indent=2),encoding="utf-8")
            messagebox.showinfo("Gespeichert",f"Bewertung für {self.fach.get()} wurde gespeichert.")
        except (ValueError,TypeError):
            messagebox.showerror("Ungültige Eingabe","Anzahl muss eine ganze Zahl ab 0 sein; Gewichte müssen positive Zahlen sein.")

if __name__ == "__main__": App().mainloop()
