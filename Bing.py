import os
import random
import re
import shutil
import subprocess
import threading
import time
import tkinter as tk
from tkinter import ttk
from urllib.parse import quote_plus
import pyperclip
import pyautogui

DEFAULT_TOTAL_SEARCHES = 20
POINTS_PER_SEARCH = 3
DEFAULT_WAIT_MINUTES = 1
DEFAULT_WAIT_MAXUTES = 3

def normalize_query(text: str) -> str:
    text = str(text or "").strip()
    text = re.sub(r"^(assistant|ai|bot)\s*[:\-]?\s*", "", text, flags=re.IGNORECASE)
    text = text.strip('"').strip("'")
    text = re.sub(r"[\n\r]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = text.lower()
    return text

def get_ai_query(language: str = "tr") -> str:
    lang = (language or "tr").lower()
    if lang.startswith("de"):
        system_prompt = "Du bist ein Internetnutzer. Erstelle eine kurze, natürliche und interessante Suchanfrage für eine Suchmaschine. Schreibe nur die Suchanfrage, keine Erklärung."
        user_prompt = "Erstelle eine kurze, natürliche und realistische Suchanfrage."
        fallback_topics = ["Technik-Nachrichten", "Weltraumforschung", "neue Kunstbewegungen", "gesundes Essen"]
    elif lang.startswith("fr"):
        system_prompt = "Tu es un utilisateur d'internet. Génère une seule requête de recherche courte, naturelle et intrigante pour un moteur de recherche. Écris seulement la requête, pas d'explication."
        user_prompt = "Génère une requête de recherche courte, naturelle et réaliste."
        fallback_topics = ["actualités tech", "exploration spatiale", "nouveaux mouvements artistiques", "alimentation saine"]
    elif lang.startswith("es"):
        system_prompt = "Eres un usuario de internet. Genera una sola consulta de búsqueda corta, natural e intrigante para un motor de búsqueda. Solo escribe la consulta, sin explicación."
        user_prompt = "Genera una consulta de búsqueda corta, natural y realista."
        fallback_topics = ["noticias de tecnología", "exploración espacial", "nuevos movimientos artísticos", "alimentación saludable"]
    elif lang.startswith("en"):
        system_prompt = "You are an internet user. Generate one short, natural, and intriguing search query for a search engine. Only write the query, no explanation."
        user_prompt = "Generate a short, natural, and realistic search query."
        fallback_topics = ["tech news", "space exploration", "new art movements", "healthy eating"]
    else:
        system_prompt = "Sen bir internet kullanıcısısın. Arama motorunda aratılacak, kısa, doğal ve merak uyandırıcı tek bir konu başlığı üret. Sadece sorguyu yaz, açıklama yapma."
        user_prompt = "kısa, doğal ve gerçekçi bir arama sorgusu üret."
        fallback_topics = ["teknoloji haberleri", "uzay araştırmaları", "yeni sanat akımları", "sağlıklı beslenme"]

    try:
        import ollama
        response = ollama.chat(
            model="llama3.1",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        if isinstance(response, dict):
            message = response.get("message", {})
            content = message.get("content", "") if isinstance(message, dict) else getattr(message, "content", "")
        else:
            content = getattr(getattr(response, "message", None), "content", "")
        cleaned = normalize_query(content)
        if cleaned:
            return cleaned
    except Exception:
        pass
    return random.choice(fallback_topics)

class BingSearchGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Bing Automation")
        self.root.geometry("240x350")
        self.root.attributes("-topmost", True)
        self.root.resizable(False, False)

        self.total_searches = DEFAULT_TOTAL_SEARCHES
        self.wait_min_minutes = DEFAULT_WAIT_MINUTES
        self.wait_max_minutes = DEFAULT_WAIT_MAXUTES
        self.completed = 0
        self.points = 0
        self.is_running = False
        self.stop_event = threading.Event()
        self.ollama_process = None
        self.theme = "Light"
        self.language = "en"

        style = ttk.Style()
        style.theme_use("clam")

        main_frame = ttk.Frame(root, padding=10, style="Card.TFrame")
        main_frame.pack(fill="both", expand=True)

        ttk.Label(main_frame, text="Bing Search Automation", style="Title.TLabel").pack(anchor="w")
        ttk.Label(main_frame, text="Number of searches:", style="Label.TLabel").pack(anchor="w", pady=(6, 2))

        self.spin = ttk.Spinbox(main_frame, from_=1, to=100, width=8, style="TSpinbox")
        self.spin.set(str(DEFAULT_TOTAL_SEARCHES))
        self.spin.pack(anchor="w")

        ttk.Label(main_frame, text="Wait time (minutes):", style="Label.TLabel").pack(anchor="w", pady=(6, 2))
        wait_frame = ttk.Frame(main_frame, style="Card.TFrame")
        wait_frame.pack(anchor="w")
        
        ttk.Label(wait_frame, text="Min:", style="Label.TLabel").pack(side="left")
        self.wait_min_spin = ttk.Spinbox(wait_frame, from_=1, to=60, width=6, style="TSpinbox")
        self.wait_min_spin.set(str(DEFAULT_WAIT_MINUTES))
        self.wait_min_spin.pack(side="left", padx=(4, 8))
        
        ttk.Label(wait_frame, text="Max:", style="Label.TLabel").pack(side="left")
        self.wait_max_spin = ttk.Spinbox(wait_frame, from_=1, to=60, width=6, style="TSpinbox")
        self.wait_max_spin.set(str(DEFAULT_WAIT_MAXUTES))
        self.wait_max_spin.pack(side="left", padx=(4, 0))

        self.status_var = tk.StringVar(value="Ready")
        self.status_label = ttk.Label(main_frame, textvariable=self.status_var, style="Label.TLabel")
        self.status_label.pack(anchor="w", pady=(6, 2))

        self.score_var = tk.StringVar(value="Score: 0")
        self.score_label = ttk.Label(main_frame, textvariable=self.score_var, font=("Segoe UI", 10, "bold"), style="Label.TLabel")
        self.score_label.pack(anchor="w")

        self.progress_var = tk.StringVar(value=f"0/{DEFAULT_TOTAL_SEARCHES} completed")
        ttk.Label(main_frame, textvariable=self.progress_var, style="Label.TLabel").pack(anchor="w", pady=(2, 6))

        settings_frame = ttk.LabelFrame(main_frame, text="Settings", style="Settings.TLabelframe")
        settings_frame.pack(anchor="w", pady=(6, 0), fill="x")
        settings_frame.configure(padding=(8, 6))

        ttk.Label(settings_frame, text="Theme:", style="Label.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.theme_var = tk.StringVar(value="Light")
        self.theme_combo = ttk.Combobox(settings_frame, textvariable=self.theme_var, state="readonly", width=10, style="TCombobox")
        self.theme_combo["values"] = ("Light", "Dark")
        self.theme_combo.grid(row=0, column=1, sticky="w")
        self.theme_combo.bind("<<ComboboxSelected>>", self.apply_theme)

        ttk.Label(settings_frame, text="Language:", style="Label.TLabel").grid(row=1, column=0, sticky="w", padx=(0, 6), pady=(6, 0))
        self.language_var = tk.StringVar(value="English")
        self.language_combo = ttk.Combobox(settings_frame, textvariable=self.language_var, state="readonly", width=12, style="TCombobox")
        self.language_combo["values"] = ("Turkish", "English", "German", "French", "Spanish")
        self.language_combo.grid(row=1, column=1, sticky="w", pady=(6, 0))
        self.language_combo.bind("<<ComboboxSelected>>", self.apply_theme)

        button_frame = ttk.Frame(main_frame, style="Card.TFrame")
        button_frame.pack(anchor="w", pady=(8, 0))
        
        self.start_btn = ttk.Button(button_frame, text="Start", command=self.start_thread, style="Accent.TButton")
        self.start_btn.pack(side="left", padx=(0, 6))
        self.stop_btn = ttk.Button(button_frame, text="Stop", command=self.stop_thread, style="Danger.TButton", state="disabled")
        self.stop_btn.pack(side="left")

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.apply_theme()
        self.start_ollama()

    def start_ollama(self):
        if self.ollama_process and self.ollama_process.poll() is None:
            return
        if shutil.which("ollama") is None:
            self.status_var.set("Ollama not found!")
            return
        try:
            self.status_var.set("Starting Ollama...")
            self.ollama_process = subprocess.Popen('start "Ollama" /min cmd /c ollama serve', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(3)
            self.status_var.set("Ollama is ready in the background!")
        except Exception:
            self.status_var.set("Failed to start Ollama!")

    def stop_ollama(self):
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/F", "/IM", "ollama.exe", "/T"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.run(["pkill", "-f", "ollama serve"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
        finally:
            self.ollama_process = None

    def start_thread(self):
        try:
            self.total_searches = int(self.spin.get())
        except ValueError:
            self.total_searches = DEFAULT_TOTAL_SEARCHES
        if self.total_searches < 1:
            self.total_searches = 1

        try:
            self.wait_min_minutes = float(self.wait_min_spin.get())
        except ValueError:
            self.wait_min_minutes = DEFAULT_WAIT_MINUTES
        try:
            self.wait_max_minutes = float(self.wait_max_spin.get())
        except ValueError:
            self.wait_max_minutes = DEFAULT_WAIT_MAXUTES

        if self.wait_min_minutes < 1:
            self.wait_min_minutes = 1.0
        if self.wait_max_minutes < self.wait_min_minutes:
            self.wait_max_minutes = self.wait_min_minutes

        self.completed = 0
        self.points = 0
        self.is_running = True
        self.stop_event.clear()
        self.status_var.set("Started...")
        self.score_var.set("Score: 0")
        self.progress_var.set(f"0/{self.total_searches} completed")
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        threading.Thread(target=self.run_automation, daemon=True).start()

    def apply_theme(self, event=None):
        self.theme = self.theme_var.get().lower()
        lang_value = self.language_var.get().lower()
        
        # Dil algılama mantığı düzeltildi
        if lang_value.startswith("en"):
            self.language = "en"
        elif lang_value.startswith("de"):
            self.language = "de"
        elif lang_value.startswith("fr"):
            self.language = "fr"
        elif lang_value.startswith("es"):
            self.language = "es"
        else:
            self.language = "tr"

        if self.theme == "dark":
            bg = "#1f2329"
            fg = "#f5f7fa"
            accent = "#5b8cff"
            danger = "#ff5d73"
            field_bg = "#2d333b"
            field_fg = "#f5f7fa"
        else:
            bg = "#f4f7fb"
            fg = "#355070"
            accent = "#2f6fed"
            danger = "#e63946"
            field_bg = "#ffffff"
            field_fg = "#1f2937"

        self.root.configure(bg=bg)

        style = ttk.Style()
        style.configure("Card.TFrame", background=bg)
        style.configure("Title.TLabel", background=bg, foreground=accent if self.theme == "dark" else "#1f3b5b", font=("Segoe UI", 11, "bold"))
        style.configure("Label.TLabel", background=bg, foreground=fg)
        style.configure("Settings.TLabelframe", background=bg, foreground=fg)
        style.configure("Settings.TLabelframe.Label", background=bg, foreground=fg)
        
        style.configure("Accent.TButton", padding=6, foreground="white", background=accent)
        style.configure("Danger.TButton", padding=6, foreground="white", background=danger)
        style.map("Accent.TButton", background=[("active", accent), ("disabled", "#7fa8f4")])
        style.map("Danger.TButton", background=[("active", danger), ("disabled", "#f08b95")])

        # Spinbox renk düzeltmeleri
        style.configure("TSpinbox", fieldbackground=field_bg, background=field_bg, foreground=field_fg, arrowcolor=fg)
        style.map("TSpinbox", fieldbackground=[("readonly", field_bg), ("disabled", bg)])
        
        # Combobox kutusunun readonly durumundaki renk haritalaması düzeltildi
        style.configure("TCombobox", fieldbackground=field_bg, background=field_bg, foreground=field_fg, arrowcolor=fg)
        style.map("TCombobox", 
                  fieldbackground=[("readonly", field_bg), ("disabled", bg)],
                  foreground=[("readonly", field_fg)],
                  selectbackground=[("readonly", accent)],
                  selectforeground=[("readonly", "white")])

        # Açılır liste açıldığında listenin içindeki arka plan ve yazı renkleri ayarlandı
        self.root.option_add("*TCombobox*Listbox.background", field_bg)
        self.root.option_add("*TCombobox*Listbox.foreground", field_fg)
        self.root.option_add("*TCombobox*Listbox.selectBackground", accent)
        self.root.option_add("*TCombobox*Listbox.selectForeground", "white")

    def stop_thread(self):
        self.is_running = False
        self.stop_event.set()
        self.status_var.set("Stopped")
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")

    def open_new_tab(self):
        pyautogui.hotkey("ctrl", "t")
        time.sleep(0.6)

    def close_entire_browser(self):
        pyautogui.hotkey("alt", "f4")
        time.sleep(0.5)

    def navigate_to_url(self, url: str):
        pyautogui.hotkey("ctrl", "l")
        time.sleep(0.2)
        pyperclip.copy(url)
        time.sleep(0.2)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.2)
        pyautogui.press("enter")
        time.sleep(2.5)

    def click_relevant_search_result(self):
        time.sleep(2.0)
        steps = random.randint(8, 15)
        for _ in range(steps):
            pyautogui.press("tab")
            time.sleep(0.15)
        pyautogui.press("enter")
        time.sleep(2.5)

    def perform_search_cycle(self, query: str, open_tab: bool):
        if open_tab:
            self.open_new_tab()
        bing_url = f"https://www.bing.com/search?q={quote_plus(query)}"
        self.navigate_to_url(bing_url)
        time.sleep(1.2)
        for _ in range(random.randint(2, 5)):
            pyautogui.scroll(random.randint(-400, 400))
            time.sleep(0.3)
        time.sleep(1.0)
        self.click_relevant_search_result()
        time.sleep(1.5)

    def run_automation(self):
        subprocess.Popen("start msedge", shell=True)
        time.sleep(6)

        for i in range(self.total_searches):
            if not self.is_running or self.stop_event.is_set():
                break

            query = get_ai_query(self.language)
            self.perform_search_cycle(query, open_tab=(i > 0))

            self.completed = i + 1
            self.points += POINTS_PER_SEARCH
            self.progress_var.set(f"{self.completed}/{self.total_searches} completed")
            self.score_var.set(f"Score: {self.points}")
            self.status_var.set(f"Searched: {query}")

            if self.completed >= self.total_searches:
                break

            wait_time = random.uniform(self.wait_min_minutes * 60, self.wait_max_minutes * 60)
            remaining_seconds = int(wait_time)
            while remaining_seconds > 0 and self.is_running and not self.stop_event.is_set():
                self.status_var.set(f"Waiting for next search: {remaining_seconds // 60} min {remaining_seconds % 60} sec")
                time.sleep(1)
                remaining_seconds -= 1

        if not self.stop_event.is_set() and self.completed == self.total_searches:
            self.close_entire_browser()
            self.status_var.set("Completed!")
        else:
            self.status_var.set("Stopped")

        self.is_running = False
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")

    def on_close(self):
        self.stop_thread()
        self.stop_ollama()
        self.root.destroy()

def main():
    root = tk.Tk()
    BingSearchGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
