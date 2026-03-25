import cv2
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import customtkinter as ctk
from tkinter import filedialog
from PIL import Image

class MedicalSRGApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Sistem Segmentasi Medis: SRG Baseline vs Adaptif")
        self.geometry("1200x800")

        # Variabel Data
        self.img_asli = None
        self.img_grayscale = None
        self.ground_truth = None
        self.seed_point = None  # Format: (y, x)
        
        self.setup_gui()

    def setup_gui(self):
        # --- Sidebar ---
        self.sidebar = ctk.CTkFrame(self, width=250)
        self.sidebar.pack(side="left", fill="y", padx=10, pady=10)

        ctk.CTkLabel(self.sidebar, text="KONTROL PANEL", font=("Arial", 16, "bold")).pack(pady=10)

        self.btn_img = ctk.CTkButton(self.sidebar, text="1. Upload Gambar", command=self.upload_gambar)
        self.btn_img.pack(pady=10, padx=20)

        self.btn_txt = ctk.CTkButton(self.sidebar, text="2. Upload Anotasi (.txt)", command=self.upload_anotasi)
        self.btn_txt.pack(pady=10, padx=20)

        ctk.CTkLabel(self.sidebar, text="Threshold (T):").pack(pady=(20, 0))
        self.entry_t = ctk.CTkEntry(self.sidebar)
        self.entry_t.insert(0, "15") 
        self.entry_t.pack(pady=5, padx=20)

        self.lbl_seed = ctk.CTkLabel(self.sidebar, text="Seed: Belum dipilih", text_color="yellow")
        self.lbl_seed.pack(pady=10)

        self.btn_run = ctk.CTkButton(self.sidebar, text="OK / JALANKAN", fg_color="green", 
                                     command=self.process_segmentation, state="disabled")
        self.btn_run.pack(pady=20, padx=20)

        self.lbl_iou = ctk.CTkLabel(self.sidebar, text="", font=("Arial", 14), justify="left")
        self.lbl_iou.pack(pady=20)

        # --- Main Display ---
        self.display_frame = ctk.CTkFrame(self)
        self.display_frame.pack(side="right", expand=True, fill="both", padx=10, pady=10)

        self.canvas_label = ctk.CTkLabel(self.display_frame, text="Silakan upload gambar medis")
        self.canvas_label.pack(expand=True)
        self.canvas_label.bind("<Button-1>", self.on_canvas_click)

    # --- Fungsi I/O ---
    def upload_gambar(self):
        path = filedialog.askopenfilename(filetypes=[("Images", "*.jpg *.png *.jpeg *.bmp")])
        if path:
            self.img_asli = cv2.cvtColor(cv2.imread(path), cv2.COLOR_BGR2RGB)
            self.img_grayscale = cv2.cvtColor(self.img_asli, cv2.COLOR_RGB2GRAY)
            self.refresh_display(self.img_asli)
            self.lbl_seed.configure(text="Klik gambar untuk pilih Seed")

    def upload_anotasi(self):
        path = filedialog.askopenfilename(filetypes=[("Text", "*.txt")])
        if path and self.img_asli is not None:
            h, w = self.img_grayscale.shape
            mask = np.zeros((h, w), dtype=np.uint8)
            with open(path, 'r') as f:
                for line in f:
                    data = list(map(float, line.split()))
                    pts = np.array(data[1:]).reshape(-1, 2)
                    pts[:, 0] *= w
                    pts[:, 1] *= h
                    cv2.fillPoly(mask, [pts.astype(np.int32)], 1)
            self.ground_truth = mask
            ctk.CTkLabel(self.sidebar, text="GT Berhasil Dimuat", text_color="cyan").pack()

    def on_canvas_click(self, event):
        if self.img_asli is not None:
            h_img, w_img = self.img_grayscale.shape
            h_lbl = self.canvas_label.winfo_height()
            w_lbl = self.canvas_label.winfo_width()

            # Mapping klik ke koordinat pixel asli
            x_px = int(event.x * w_img / w_lbl)
            y_px = int(event.y * h_img / h_lbl)
            self.seed_point = (y_px, x_px)

            # Gambar penanda visual (titik merah)
            img_marker = self.img_asli.copy()
            cv2.circle(img_marker, (x_px, y_px), 5, (255, 0, 0), -1)
            self.refresh_display(img_marker)

            self.lbl_seed.configure(text=f"Seed: [{x_px}, {y_px}]")
            self.btn_run.configure(state="normal")

    def refresh_display(self, img_array):
        img_pil = Image.fromarray(img_array)
        img_ctk = ctk.CTkImage(img_pil, size=(700, 500))
        self.canvas_label.configure(image=img_ctk, text="")

    # --- Logika Algoritma ---
    def process_segmentation(self):
        t = int(self.entry_t.get())
        
        # 1. Baseline SRG (Seed-Based)
        res_base = self.srg_baseline(t)
        
        # 2. Adaptive SRG (Mean-Based)
        res_adapt = self.srg_adaptive(t)

        # 3. Hitung IoU
        iou_b = self.calc_iou(res_base)
        iou_a = self.calc_iou(res_adapt)

        self.lbl_iou.configure(text=f"HASIL EVALUASI:\nIoU Baseline: {iou_b:.4f}\nIoU Adaptif: {iou_a:.4f}")
        self.show_final_window(res_base, res_adapt, iou_b, iou_a)

    def srg_baseline(self, threshold):
        h, w = self.img_grayscale.shape
        mask = np.zeros((h, w), dtype=np.uint8)
        seed_val = int(self.img_grayscale[self.seed_point]) #
        
        queue = [self.seed_point]
        mask[self.seed_point] = 1
        
        while queue:
            cy, cx = queue.pop(0)
            for dy, dx in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]: # 8-neighborhood
                ny, nx = cy + dy, cx + dx
                if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] == 0:
                    if abs(int(self.img_grayscale[ny, nx]) - seed_val) <= threshold: #
                        mask[ny, nx] = 1
                        queue.append((ny, nx))
        return mask

    def srg_adaptive(self, threshold):
        h, w = self.img_grayscale.shape
        mask = np.zeros((h, w), dtype=np.uint8)
        mean_reg = float(self.img_grayscale[self.seed_point]) #
        count = 1
        
        queue = [self.seed_point]
        mask[self.seed_point] = 1
        
        while queue:
            cy, cx = queue.pop(0)
            for dy, dx in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]:
                ny, nx = cy + dy, cx + dx
                if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] == 0:
                    if abs(int(self.img_grayscale[ny, nx]) - mean_reg) <= threshold: #
                        mask[ny, nx] = 1
                        queue.append((ny, nx))
                        count += 1
                        # Update Mean Dinamis
                        mean_reg = ((mean_reg * (count - 1)) + self.img_grayscale[ny, nx]) / count
        return mask

    def calc_iou(self, pred):
        if self.ground_truth is None: return 0.0
        inter = np.logical_and(pred, self.ground_truth).sum()
        union = np.logical_or(pred, self.ground_truth).sum()
        return inter / union if union != 0 else 0.0

    # --- Visualisasi Akhir ---
    def show_final_window(self, m_base, m_adapt, iou_b, iou_a):
        win = ctk.CTkToplevel(self)
        win.title("Perbandingan Segmentasi")
        
        fig, axes = plt.subplots(1, 4, figsize=(18, 5))
        
        # 1. Asli
        axes[0].imshow(self.img_asli)
        axes[0].set_title("Original Image")

        # 2. Ground Truth Overlay (Red)
        gt_ov = self.img_asli.copy()
        if self.ground_truth is not None:
            gt_ov[self.ground_truth == 1] = [255, 0, 0]
        axes[1].imshow(gt_ov)
        axes[1].set_title("Ground Truth (Anotasi)")

        # 3. Baseline Overlay (Green)
        b_ov = self.img_asli.copy()
        b_ov[m_base == 1] = [0, 255, 0]
        axes[2].imshow(b_ov)
        axes[2].set_title(f"SRG Baseline\nIoU: {iou_b:.4f}")

        # 4. Adaptive Overlay (Blue)
        a_ov = self.img_asli.copy()
        a_ov[m_adapt == 1] = [0, 0, 255]
        axes[3].imshow(a_ov)
        axes[3].set_title(f"SRG Adaptif\nIoU: {iou_a:.4f}")

        for ax in axes: ax.axis('off')
        
        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(expand=True, fill="both")

if __name__ == "__main__":
    app = MedicalSRGApp()
    app.mainloop()