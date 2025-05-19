# ui/components.py
import tkinter as tk
from tkinter import ttk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import pandas as pd

class DarkTheme:
    """Tema ayarları için renk paleti"""
    BG = "#2d2d2d"
    FG = "#e8e8e8"
    ACCENT = "#568af2"
    WARNING = "#ff6b6b"
    FRAME_BG = "#3d3d3d"
    TREEVIEW = {
        'bg': FRAME_BG,
        'fg': FG,
        'fieldbackground': FRAME_BG,
        'selected_bg': ACCENT,
        'selected_fg': FG
    }

class GrafikBileseni(ttk.Frame):
    """Matplotlib tabanlı interaktif grafik bileşeni"""
    def __init__(self, parent, width=800, height=400):
        super().__init__(parent)
        self.configure(style='Dark.TFrame')
        
        # Matplotlib figür ve canvas
        self.fig = Figure(figsize=(width/100, height/100), dpi=100, facecolor=DarkTheme.BG)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor(DarkTheme.BG)
        self.ax.tick_params(colors=DarkTheme.FG)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
    def update_grafik(self, df: pd.DataFrame, title: str):
        """Yeni verilerle grafiği güncelle"""
        self.ax.clear()
        
        # Grafik çizimleri
        self.ax.plot(df.index, df['close'], color=DarkTheme.ACCENT, linewidth=1)
        self.ax.fill_between(df.index, df['upper_band'], df['lower_band'], 
                           color=DarkTheme.ACCENT, alpha=0.2)
        self.ax.set_title(title, color=DarkTheme.FG)
        self.ax.grid(color=DarkTheme.FG, alpha=0.1)
        
        # Renk ayarları
        for spine in self.ax.spines.values():
            spine.set_color(DarkTheme.FG)
            
        self.canvas.draw()

class HaberPaneli(ttk.Frame):
    """Finansal haberleri gösteren interaktif tablo"""
    def __init__(self, parent):
        super().__init__(parent)
        self.configure(style='Dark.TFrame')
        
        # Treeview ve scrollbar
        self.tree = ttk.Treeview(self, columns=('Time', 'Title', 'Sentiment'), 
                               show='headings', height=8)
        
        # Sütun ayarları
        self.tree.heading('Time', text='Zaman')
        self.tree.heading('Title', text='Başlık')
        self.tree.heading('Sentiment', text='Duygu')
        
        self.tree.column('Time', width=100, anchor='center')
        self.tree.column('Title', width=400)
        self.tree.column('Sentiment', width=80, anchor='center')
        
        # Stil ayarları
        style = ttk.Style()
        style.configure('Treeview', **DarkTheme.TREEVIEW)
        style.map('Treeview', **{
            'background': [('selected', DarkTheme.ACCENT)],
            'foreground': [('selected', DarkTheme.FG)]
        })
        
        scroll = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        
        # Yerleşim
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def haber_ekle(self, haberler: list):
        """Yeni haberleri tabloya ekle"""
        self.tree.delete(*self.tree.get_children())
        for haber in haberler:
            sentiment = "🟢" if haber['sentiment'] == 'positive' else "🔴" if haber['sentiment'] == 'negative' else "⚪"
            self.tree.insert('', tk.END, values=(
                haber['timestamp'].strftime("%H:%M"),
                haber['title'][:70] + "..." if len(haber['title']) > 70 else haber['title'],
                sentiment
            ))

class APISayac(ttk.Frame):
    """API kullanım sayacı bileşeni"""
    def __init__(self, parent, api_name: str):
        super().__init__(parent)
        self.api_name = api_name
        self.configure(style='Dark.TFrame')
        
        # UI elemanları
        self.label = ttk.Label(self, text=f"{api_name}:", style='Dark.TLabel')
        self.progress = ttk.Progressbar(self, orient=tk.HORIZONTAL, length=150, mode='determinate')
        self.count_label = ttk.Label(self, text="0/0", style='Dark.TLabel')
        
        # Yerleşim
        self.label.pack(side=tk.LEFT, padx=5)
        self.progress.pack(side=tk.LEFT, padx=5)
        self.count_label.pack(side=tk.LEFT, padx=5)
        
    def update_sayac(self, kullanilan: int, limit: int):
        """Sayacı güncelle"""
        self.progress['value'] = (kullanilan / limit) * 100
        self.count_label.config(text=f"{kullanilan}/{limit}")
        self.progress['style'] = 'Warning.Horizontal.TProgressbar' if kullanilan >= limit else 'Dark.Horizontal.TProgressbar'

class SinyalGostergesi(tk.Canvas):
    """Anlık sinyal göstergesi (LED efekti)"""
    def __init__(self, parent, width=100, height=30):
        super().__init__(parent, width=width, height=height, 
                        bg=DarkTheme.BG, highlightthickness=0)
        self.current_signal = None
        self.led_id = None
        
    def update_sinyal(self, signal: str):
        """Göstergeyi güncelle"""
        colors = {
            'Long': ('#2ecc71', 'LONG'),
            'Short': ('#e74c3c', 'SHORT'),
            'Hold': ('#f1c40f', 'HOLD')
        }
        color, text = colors.get(signal, ('#95a5a6', 'N/A'))
        
        # LED efekti
        if self.led_id:
            self.delete(self.led_id)
            
        self.led_id = self.create_oval(10, 5, 25, 20, fill=color, outline='')
        self.create_text(50, 13, text=text, fill=DarkTheme.FG, 
                        font=('Helvetica', 10, 'bold'))

# Tema ve stilleri uygula
style = ttk.Style()
style.theme_create('dark', parent='alt', settings={
    'TFrame': {'configure': {'background': DarkTheme.BG}},
    'TLabel': {'configure': {'background': DarkTheme.BG, 'foreground': DarkTheme.FG}},
    'TButton': {'configure': {'background': DarkTheme.ACCENT, 'foreground': DarkTheme.FG}},
    'Horizontal.TProgressbar': {
        'configure': {'background': DarkTheme.ACCENT, 'troughcolor': DarkTheme.FRAME_BG}},
    'Warning.Horizontal.TProgressbar': {
        'configure': {'background': DarkTheme.WARNING}}
})
style.theme_use('dark')