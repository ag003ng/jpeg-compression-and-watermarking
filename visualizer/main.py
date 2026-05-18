import pickle
import numpy as np
from PIL import Image
from scipy.fftpack import idct
from dahuffman import HuffmanCodec

# ==========================================
# KONFIGURASI WATERMARK (Sesuaikan dengan Encoder)
# ==========================================
ALPHA = 10      # Kekuatan Watermark (Gain Factor)
WM_INDEX = 19   # Posisi frekuensi menengah untuk penyisipan

# ==========================================
# KONFIGURASI JPEG
# ==========================================
ZIGZAG_ORDER = [
     0,  1,  5,  6, 14, 15, 27, 28,
     2,  4,  7, 13, 16, 26, 29, 42,
     3,  8, 12, 17, 25, 30, 41, 43,
     9, 11, 18, 24, 31, 40, 44, 53,
    10, 19, 23, 32, 39, 45, 52, 54,
    20, 22, 33, 38, 46, 51, 55, 60,
    21, 34, 37, 47, 50, 56, 59, 61,
    35, 36, 48, 49, 57, 58, 62, 63
]

def inverse_zigzag(zz_block):
    """Mengembalikan urutan zig‑zag ke urutan normal 8x8."""
    block = [0] * 64
    for i in range(64):
        block[ZIGZAG_ORDER[i]] = zz_block[i]
    return block

def inverse_dpcm(blocks):
    """Mengembalikan selisih DC menjadi nilai DC asli."""
    prev_dc = 0
    for blk in blocks:
        blk[0] = blk[0] + prev_dc
        prev_dc = blk[0]

def inverse_dct_2d(block):
    """Inverse DCT 2D ortonormal."""
    return idct(idct(block.T, norm='ortho').T, norm='ortho')

def start_decompress(file_pkl):
    print("=== MEMULAI PROSES DEKOMPRESI & EKSTRAKSI ===")
    
    # ---------------------------------------------------------
    # 1. BACA PAKET DATA KOMPRESI
    # ---------------------------------------------------------
    print("[1/6] Membaca file paket kompresi...")
    with open(file_pkl, "rb") as f:
        paket = pickle.load(f)
    
    codec       = paket["codec"]
    data_biner  = paket["biner"]
    N_W         = paket["N_W"]
    N_H         = paket["N_H"]
    width_sub   = paket["width_sub"]
    height_sub  = paket["height_sub"]
    len_y       = paket["len_y"]
    len_cb      = paket["len_cb"]
    len_cr      = paket["len_cr"]
    luma_q_1d   = paket["luma_q"]      
    chroma_q_1d = paket["chroma_q"]    

    Q_Y   = np.array(luma_q_1d).reshape(8, 8)
    Q_Cb  = np.array(chroma_q_1d).reshape(8, 8)
    Q_Cr  = Q_Cb  

    # ---------------------------------------------------------
    # 2. DECODE HUFFMAN
    # ---------------------------------------------------------
    print("[2/6] Mengekstrak Huffman...")
    data_stream = codec.decode(data_biner)

    # ---------------------------------------------------------
    # 3. PISAHKAN STREAM & REKONSTRUKSI BLOK (Inverse DPCM + Zigzag)
    # ---------------------------------------------------------
    print("[3/6] Membentuk ulang blok...")
    stream_y  = data_stream[:len_y]
    stream_cb = data_stream[len_y : len_y+len_cb]
    stream_cr = data_stream[len_y+len_cb : len_y+len_cb+len_cr]

    def stream_to_blocks(stream, total_blocks):
        blok_flat = [list(stream[i:i+64]) for i in range(0, len(stream), 64)]
        inverse_dpcm(blok_flat)
        blok_normal = [inverse_zigzag(b) for b in blok_flat]
        return blok_normal

    blocks_y  = stream_to_blocks(stream_y,  len_y // 64)
    blocks_cb = stream_to_blocks(stream_cb, len_cb // 64)
    blocks_cr = stream_to_blocks(stream_cr, len_cr // 64)

    # ---------------------------------------------------------
    # 4. DEKUANTISASI & PEMISAHAN JALUR FOTO (Dengan vs Tanpa Watermark)
    # ---------------------------------------------------------
    print("[4/6] Dekuantisasi dan Pemisahan Jalur Foto...")
    
    dct_y_dequantized = [] 
    spatial_y_with_wm = []  # Untuk foto asli yang disisipi
    spatial_y_clean = []    # Untuk foto hasil restorasi (dibersihkan)

    # Pemrosesan Blok Luma (Y)
    for blk in blocks_y:
        mat = np.array(blk).reshape(8, 8)
        mat_deq = mat * Q_Y  # Nilai DCT asli pasca-dekuantisasi
        
        # Simpan nilai mentahnya untuk diekstrak jadi citra watermark nanti
        dct_y_dequantized.append(mat_deq.flatten()) 
        
        # --- JALUR 1: Watermark Tetap Menempel ---
        spatial_with_wm = inverse_dct_2d(mat_deq)
        spatial_y_with_wm.append(spatial_with_wm)
        
        # --- JALUR 2: Bersihkan Efek ALPHA ---
        mat_clean = mat_deq.copy().flatten()
        val_wm = mat_clean[WM_INDEX]
        
        if val_wm > 0:
            mat_clean[WM_INDEX] -= ALPHA  # Netralkan bit putih
        else:
            mat_clean[WM_INDEX] += ALPHA  # Netralkan bit hitam
            
        spatial_clean = inverse_dct_2d(mat_clean.reshape(8, 8))
        spatial_y_clean.append(spatial_clean)

    # Pemrosesan Blok Chroma (Cb, Cr)
    def dequant_idct_chroma(blocks, Q):
        spatial_blocks = []
        for blk in blocks:
            mat = np.array(blk).reshape(8, 8)
            mat_deq = mat * Q
            spatial = inverse_dct_2d(mat_deq)
            spatial_blocks.append(spatial)
        return spatial_blocks

    spatial_cb = dequant_idct_chroma(blocks_cb, Q_Cb)
    spatial_cr = dequant_idct_chroma(blocks_cr, Q_Cr)

    # ---------------------------------------------------------
    # 5. SUSUN ULANG GAMBAR KANVAS PENUH
    # ---------------------------------------------------------
    print("[5/6] Menyusun ulang gambar (Dengan vs Tanpa Watermark)...")
    def blocks_to_image(spatial_blocks, img_w, img_h):
        img = np.zeros((img_h, img_w), dtype=np.float32)
        idx = 0
        for v in range(0, img_h, 8):
            for u in range(0, img_w, 8):
                blk = spatial_blocks[idx]
                img[v:v+8, u:u+8] = blk + 128.0   
                idx += 1
        return np.clip(img, 0, 255).astype(np.uint8)

    # Buat komponen Y untuk kedua versi
    Y_img_with_wm = blocks_to_image(spatial_y_with_wm, N_W, N_H)
    Y_img_clean   = blocks_to_image(spatial_y_clean, N_W, N_H)
    
    # Komponen warna tetap sama
    Cb_sub = blocks_to_image(spatial_cb, width_sub, height_sub)
    Cr_sub = blocks_to_image(spatial_cr, width_sub, height_sub)
    Cb_full = np.kron(Cb_sub, np.ones((2, 2)))[:N_H, :N_W]
    Cr_full = np.kron(Cr_sub, np.ones((2, 2)))[:N_H, :N_W]

    def ycbcr2rgb(Y, Cb, Cr):
        R = Y + 1.402 * (Cr - 128)
        G = Y - 0.344136 * (Cb - 128) - 0.714136 * (Cr - 128)
        B = Y + 1.772 * (Cb - 128)
        return np.stack([np.clip(R, 0, 255), np.clip(G, 0, 255), np.clip(B, 0, 255)], axis=-1).astype(np.uint8)

    # Konversi ke RGB dan Potong Padding (Crop)
    R_W, R_H = paket["R_W"], paket["R_H"]
    
    final_img_with_wm = ycbcr2rgb(Y_img_with_wm, Cb_full, Cr_full)[:R_H, :R_W, :]
    final_img_clean   = ycbcr2rgb(Y_img_clean, Cb_full, Cr_full)[:R_H, :R_W, :]

    # Simpan Output Foto 1 & 2
    Image.fromarray(final_img_with_wm).save("hasil_foto_dengan_watermark.png")
    Image.fromarray(final_img_clean).save("hasil_foto_dibersihkan.png")

    # ---------------------------------------------------------
    # 6. EKSTRAK CITRA WATERMARK BINER
    # ---------------------------------------------------------
    print("[6/6] Mengekstrak Citra Watermark Biner...")
    watermark_pixels = []
    
    # Ekstrak bit dari koefisien yang sudah didekuantisasi
    for blk in dct_y_dequantized:   
        val = blk[WM_INDEX]
        if val > 0:
            watermark_pixels.append(255) # Putih (1)
        else:
            watermark_pixels.append(0)   # Hitam (-1)

    # Bentuk kembali menjadi gambar
    wm_w = N_W // 8
    wm_h = N_H // 8
    wm_img = Image.new("1", (wm_w, wm_h))
    idx = 0
    for v in range(wm_h):
        for h in range(wm_w):
            if idx < len(watermark_pixels):
                wm_img.putpixel((h, v), watermark_pixels[idx])
                idx += 1
                
    # Simpan Output ke-3
    wm_img.save("hasil_ekstrak_watermark.png")

    # ---------------------------------------------------------
    # SUMMARY & DEBUGGING
    # ---------------------------------------------------------
    print("\n=== PROSES DEKOMPRESI & PEMISAHAN BERHASIL ===")
    print("Berhasil menghasilkan 3 buah file:")
    print("1. [FOTO WATERMARKED] -> hasil_foto_dengan_watermark.png")
    print("2. [FOTO BERSIH]      -> hasil_foto_dibersihkan.png")
    print("3. [LOGO WATERMARK]   -> hasil_ekstrak_watermark.png")

    # Debug Statistik Koefisien
    values_at_wm_index = [blk[WM_INDEX] for blk in dct_y_dequantized]
    print(f"\n[Debug] Statistik Koefisien pada Indeks {WM_INDEX}:")
    print(f"  Mean Value : {np.mean(values_at_wm_index):.2f}")
    print(f"  Bit Putih  : {sum(1 for v in values_at_wm_index if v > 0)} piksel")
    print(f"  Bit Hitam  : {sum(1 for v in values_at_wm_index if v <= 0)} piksel")

# ==========================================
# EKSEKUSI UTAMA
# ==========================================
if __name__ == "__main__":
    # Ganti dengan nama file .pkl Anda
    start_decompress("hasil_kompresi_lengkap.pkl")