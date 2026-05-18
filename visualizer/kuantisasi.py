import cv2
import numpy as np
from scipy.fftpack import dct

# 1. Matriks Kuantisasi Standar JPEG (Quality 50)
LUMA_Q = np.array([
    [16,  11,  10,  16,  24,  40,  51,  61],
    [12,  12,  14,  19,  26,  58,  60,  55],
    [14,  13,  16,  24,  40,  57,  69,  56],
    [14,  17,  22,  29,  51,  87,  80,  62],
    [18,  22,  37,  56,  68, 109, 103,  77],
    [24,  35,  55,  64,  81, 104, 113,  92],
    [49,  64,  78,  87, 103, 121, 120, 101],
    [72,  92,  95,  98, 112, 100, 103,  99]
], dtype=np.float32)

CHROMA_Q = np.array([
    [17,  18,  24,  47,  99,  99,  99,  99],
    [18,  21,  26,  66,  99,  99,  99,  99],
    [24,  26,  56,  99,  99,  99,  99,  99],
    [47,  66,  99,  99,  99,  99,  99,  99],
    [99,  99,  99,  99,  99,  99,  99,  99],
    [99,  99,  99,  99,  99,  99,  99,  99],
    [99,  99,  99,  99,  99,  99,  99,  99],
    [99,  99,  99,  99,  99,  99,  99,  99]
], dtype=np.float32)

def dct_2d(block):
    """Melakukan proses 2D DCT ortonormal."""
    return dct(dct(block.T, norm='ortho').T, norm='ortho')

def konversi_ke_gambar_visual_3channel(kanvas_y, kanvas_cb, kanvas_cr):
    """
    Mengubah nilai frekuensi Y, Cb, Cr menjadi visualisasi RGB.
    Menggunakan log-scale dan normalisasi per komponen.
    """
    def log_normalize(matriks):
        abs_mat = np.abs(matriks)
        log_mat = np.log(1 + abs_mat)
        # Normalisasi ke rentang piksel 0-255
        return cv2.normalize(log_mat, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

    # Visualisasikan frekuensi masing-masing channel
    vis_y  = log_normalize(kanvas_y)
    vis_cb = log_normalize(kanvas_cb)
    vis_cr = log_normalize(kanvas_cr)
    
    # Gabungkan kembali menjadi gambar YCrCb lalu balikkan ke RGB (untuk disimpan)
    ycrcb_img = cv2.merge([vis_y, vis_cr, vis_cb])
    rgb_img = cv2.cvtColor(ycrcb_img, cv2.COLOR_YCrCb2BGR)
    return rgb_img

def proses_visualisasi_kompresi_warna(img_path):
    # 1. Baca gambar asli dalam format Warna BGR (OpenCV standard)
    img_bgr = cv2.imread(img_path)
    if img_bgr is None:
        raise FileNotFoundError(f"Gambar tidak ditemukan: {img_path}")
        
    h, w, _ = img_bgr.shape
    h_new = (h // 8) * 8
    w_new = (w // 8) * 8
    img_bgr_cropped = img_bgr[:h_new, :w_new]
    
    # Simpan File 0: Gambar Original Berwarna (Sudah di-crop kelipatan 8)
    cv2.imwrite("visual_0_original_color.png", img_bgr_cropped)
    
    # Konversi Gambar ke YCrCb (Ingat: OpenCV urutannya Y, Cr, Cb)
    img_ycrcb = cv2.cvtColor(img_bgr_cropped, cv2.COLOR_BGR2YCrCb)
    Y, Cr, Cb = cv2.split(img_ycrcb)
    
    # Siapkan kanvas kosong untuk menyimpan frekuensi masing-masing channel
    kanvas_dct_y  = np.zeros_like(Y, dtype=np.float32)
    kanvas_dct_cb = np.zeros_like(Cb, dtype=np.float32)
    kanvas_dct_cr = np.zeros_like(Cr, dtype=np.float32)
    
    kanvas_kuan_y  = np.zeros_like(Y, dtype=np.float32)
    kanvas_kuan_cb = np.zeros_like(Cb, dtype=np.float32)
    kanvas_kuan_cr = np.zeros_like(Cr, dtype=np.float32)
    
    print("Memproses DCT & Kuantisasi untuk channel Y, Cb, dan Cr...")
    
    # 2. Iterasi per blok 8x8
    for v in range(0, h_new, 8):
        for h_idx in range(0, w_new, 8):
            
            # --- SEBELUM DCT: Level Shifting (-128) ---
            blk_y  = Y[v:v+8, h_idx:h_idx+8].astype(np.float32) - 128.0
            blk_cb = Cb[v:v+8, h_idx:h_idx+8].astype(np.float32) - 128.0
            blk_cr = Cr[v:v+8, h_idx:h_idx+8].astype(np.float32) - 128.0
            
            # --- TAHAP 1: BERIKAN DCT ---
            dct_y  = dct_2d(blk_y)
            dct_cb = dct_2d(blk_cb)
            dct_cr = dct_2d(blk_cr)
            
            kanvas_dct_y[v:v+8, h_idx:h_idx+8]  = dct_y
            kanvas_dct_cb[v:v+8, h_idx:h_idx+8] = dct_cb
            kanvas_dct_cr[v:v+8, h_idx:h_idx+8] = dct_cr
            
            # --- TAHAP 2: BERIKAN KUANTISASI ---
            # Saluran Y menggunakan LUMA_Q, Saluran Cb & Cr menggunakan CHROMA_Q
            kanvas_kuan_y[v:v+8, h_idx:h_idx+8]  = np.round(dct_y / LUMA_Q)
            kanvas_kuan_cb[v:v+8, h_idx:h_idx+8] = np.round(dct_cb / CHROMA_Q)
            kanvas_kuan_cr[v:v+8, h_idx:h_idx+8] = np.round(dct_cr / CHROMA_Q)

    print("Menyusun peta spektrum frekuensi berwarna...")
    
    # 3. Konversi data matriks frekuensi gabungan menjadi gambar berwarna (RGB)
    gambar_visual_dct  = konversi_ke_gambar_visual_3channel(kanvas_dct_y, kanvas_dct_cb, kanvas_dct_cr)
    gambar_visual_kuan = konversi_ke_gambar_visual_3channel(kanvas_kuan_y, kanvas_kuan_cb, kanvas_kuan_cr)
    
    # 4. Simpan output berwarna
    cv2.imwrite("visual_1_pasca_dct_warna.png", gambar_visual_dct)
    cv2.imwrite("visual_2_pasca_kuantisasi_warna.png", gambar_visual_kuan)
    
    print("\n=== PROSES BERWARNA SELESAI ===")
    print("Berhasil mengekstrak 3 file representasi warna penuh:")
    print("1. visual_0_original_color.png         -> Foto Asli")
    print("2. visual_1_pasca_dct_warna.png        -> Spektrum Frekuensi Gabungan Y, Cb, Cr")
    print("3. visual_2_pasca_kuantisasi_warna.png -> Spektrum Terkuantisasi (Banyak warna redup/padam)")

if __name__ == "__main__":
    proses_visualisasi_kompresi_warna("foto-wajah-padded.jpeg")