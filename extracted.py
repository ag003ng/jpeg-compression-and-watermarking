import pickle
import numpy as np
import copy
from PIL import Image
from scipy.fftpack import idct
from dahuffman import HuffmanCodec

# Indeks zig‑zag yang sama dengan encoder
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
    """Mengembalikan urutan zig‑zag ke urutan normal 8x8 (baris per baris)."""
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
    """Inverse DCT 2D ortonormal (cocok dengan encoder Anda)."""
    return idct(idct(block.T, norm='ortho').T, norm='ortho')

def start_decompress(file_pkl, output_wm_png="ekstrak_watermark.png",
                     output_wm_jpeg="gambar_watermark.jpeg",
                     output_clean_jpeg="gambar_tanpa_watermark.jpeg"):
    print("=== MEMULAI PROSES DEKOMPRESI ===")
    
    # 1. Baca Paket Data
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

    # Ubah tabel kuantisasi 1D ke 8x8
    Q_Y   = np.array(luma_q_1d).reshape(8, 8)
    Q_Cb  = np.array(chroma_q_1d).reshape(8, 8)
    Q_Cr  = Q_Cb  

    # 2. Decode Huffman
    print("[2/6] Mengekstrak Huffman...")
    data_stream = codec.decode(data_biner)

    # 3. Pisahkan stream menjadi Y, Cb, Cr dan bentuk blok
    print("[3/6] Membentuk ulang blok dan membalikkan DPCM+Zigzag...")
    stream_y  = data_stream[:len_y]
    stream_cb = data_stream[len_y : len_y+len_cb]
    stream_cr = data_stream[len_y+len_cb : len_y+len_cb+len_cr]

    def stream_to_blocks(stream):
        blok_flat = []
        current_block = []
        
        for item in stream:
            if item == 'EOB':
                sisa_tempat = 64 - len(current_block)
                current_block.extend([0] * sisa_tempat)
                blok_flat.append(current_block)
                current_block = []
            else:
                current_block.append(item)
                if len(current_block) == 64:
                    blok_flat.append(current_block)
                    current_block = []
                    
        inverse_dpcm(blok_flat)
        blok_normal = [inverse_zigzag(b) for b in blok_flat]
        return blok_normal

    blocks_y  = stream_to_blocks(stream_y)
    blocks_cb = stream_to_blocks(stream_cb)
    blocks_cr = stream_to_blocks(stream_cr)
    
    # Siapkan dua versi blok Y: Satu dibiarkan (untuk gambar ber-watermark), 
    # satu dibersihkan (untuk gambar ori tanpa watermark)
    blocks_y_wm = copy.deepcopy(blocks_y)
    blocks_y_clean = copy.deepcopy(blocks_y)
    
    WM_INDEX = 19

    # Ekstrak Watermark & Bersihkan blok Y untuk gambar original
    print("[4/6] Mengekstrak Watermark & Menyiapkan Gambar Original...")
    watermark_pixels = []
    for blk in blocks_y_clean:   
        val = blk[WM_INDEX]
        # Proses ekstraksi
        if val > 0:
            watermark_pixels.append(255)
        else:
            watermark_pixels.append(0)
        # Hapus watermark dengan me-reset koefisien DCT di index WM menjadi 0
        blk[WM_INDEX] = 0

    # Buat dan simpan gambar watermark biner
    wm_w = N_W // 8
    wm_h = N_H // 8
    wm_img = Image.new("1", (wm_w, wm_h))
    idx = 0
    for v in range(wm_h):
        for h in range(wm_w):
            if idx < len(watermark_pixels):
                wm_img.putpixel((h, v), watermark_pixels[idx])
                idx += 1
    wm_img.save(output_wm_png)

    # 4. Dekuantisasi dan Inverse DCT
    print("[5/6] Dekuantisasi dan Inverse DCT...")
    def dequant_idct(blocks, Q):
        spatial_blocks = []
        for blk in blocks:
            mat = np.array(blk).reshape(8, 8)
            mat_deq = mat * Q
            spatial = inverse_dct_2d(mat_deq)
            spatial_blocks.append(spatial)
        return spatial_blocks

    # Proses Inverse DCT untuk dua versi blok Y
    spatial_y_wm    = dequant_idct(blocks_y_wm, Q_Y)
    spatial_y_clean = dequant_idct(blocks_y_clean, Q_Y)
    spatial_cb      = dequant_idct(blocks_cb, Q_Cb)
    spatial_cr      = dequant_idct(blocks_cr, Q_Cr)

    # 5. Rekonstruksi kanvas penuh
    print("[6/6] Menyusun ulang gambar dan konversi warna...")
    def blocks_to_image(spatial_blocks, img_w, img_h):
        img = np.zeros((img_h, img_w), dtype=np.float32)
        idx = 0
        for v in range(0, img_h, 8):
            for u in range(0, img_w, 8):
                blk = spatial_blocks[idx]
                img[v:v+8, u:u+8] = blk + 128.0 
                idx += 1
        return np.clip(img, 0, 255).astype(np.uint8)

    # Susun ulang dua versi Y_img
    Y_img_wm    = blocks_to_image(spatial_y_wm,  N_W, N_H)
    Y_img_clean = blocks_to_image(spatial_y_clean, N_W, N_H)
    Cb_sub      = blocks_to_image(spatial_cb, width_sub, height_sub)
    Cr_sub      = blocks_to_image(spatial_cr, width_sub, height_sub)

    # Upsampling Cb/Cr
    Cb_full = np.kron(Cb_sub, np.ones((2, 2)))[:N_H, :N_W]
    Cr_full = np.kron(Cr_sub, np.ones((2, 2)))[:N_H, :N_W]

    # Konversi YCbCr ke RGB
    def ycbcr2rgb(Y, Cb, Cr):
        R = Y + 1.402 * (Cr - 128)
        G = Y - 0.344136 * (Cb - 128) - 0.714136 * (Cr - 128)
        B = Y + 1.772 * (Cb - 128)
        return np.stack([
            np.clip(R, 0, 255),
            np.clip(G, 0, 255),
            np.clip(B, 0, 255)
        ], axis=-1).astype(np.uint8)

    rgb_img_wm    = ycbcr2rgb(Y_img_wm, Cb_full, Cr_full)
    rgb_img_clean = ycbcr2rgb(Y_img_clean, Cb_full, Cr_full)

    # Potong ke ukuran asli (tanpa padding)
    R_W, R_H = paket["R_W"], paket["R_H"]
    final_img_wm    = rgb_img_wm[:R_H, :R_W, :]
    final_img_clean = rgb_img_clean[:R_H, :R_W, :]

    # Simpan kedua gambar hasil
    Image.fromarray(final_img_wm).save(output_wm_jpeg)
    Image.fromarray(final_img_clean).save(output_clean_jpeg)

    print("\n=== PROSES SELESAI ===")
    print("File yang berhasil dihasilkan:")
    print(f"1. {output_wm_png}       (Gambar Watermark Biner)")
    print(f"2. {output_wm_jpeg}       (Gambar dengan Watermark tersisip)")
    print(f"3. {output_clean_jpeg}       (Gambar bersih)")
    
if __name__ == "__main__":
    start_decompress("compress.pkl")