import pickle
import numpy as np
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

def start_decompress(file_pkl):
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
    luma_q_1d   = paket["luma_q"]      # list 64 integer
    chroma_q_1d = paket["chroma_q"]    # list 64 integer

    # Ubah tabel kuantisasi 1D ke 8x8
    Q_Y   = np.array(luma_q_1d).reshape(8, 8)
    Q_Cb  = np.array(chroma_q_1d).reshape(8, 8)
    Q_Cr  = Q_Cb  # sama

    # 2. Decode Huffman
    print("[2/6] Mengekstrak Huffman...")
    data_stream = codec.decode(data_biner)

    # 3. Pisahkan stream menjadi Y, Cb, Cr dan bentuk blok
    print("[3/6] Membentuk ulang blok dan membalikkan DPCM+Zigzag...")
    stream_y  = data_stream[:len_y]
    stream_cb = data_stream[len_y : len_y+len_cb]
    stream_cr = data_stream[len_y+len_cb : len_y+len_cb+len_cr]

    def stream_to_blocks(stream, total_blocks):
        """Mengubah stream 1D menjadi list blok 64, lalu inverse zig‑zag dan inverse DPCM."""
        blok_flat = [list(stream[i:i+64]) for i in range(0, len(stream), 64)]
        inverse_dpcm(blok_flat)
        blok_normal = [inverse_zigzag(b) for b in blok_flat]
        return blok_normal

    blocks_y  = stream_to_blocks(stream_y,  len_y // 64)
    blocks_cb = stream_to_blocks(stream_cb, len_cb // 64)
    blocks_cr = stream_to_blocks(stream_cr, len_cr // 64)

    # 4. Dekuantisasi dan Inverse DCT
    print("[4/6] Dekuantisasi dan Inverse DCT...")
    def dequant_idct(blocks, Q):
        spatial_blocks = []
        for blk in blocks:
            mat = np.array(blk).reshape(8, 8)   # nilai hasil dequantisasi? Belum!
            # Dekuantisasi (kalikan dengan tabel)
            mat_deq = mat * Q
            # Inverse DCT
            spatial = inverse_dct_2d(mat_deq)
            spatial_blocks.append(spatial)
        return spatial_blocks

    spatial_y  = dequant_idct(blocks_y,  Q_Y)
    spatial_cb = dequant_idct(blocks_cb, Q_Cb)
    spatial_cr = dequant_idct(blocks_cr, Q_Cr)

    # 5. Rekonstruksi kanvas penuh (Y, Cb, Cr)
    print("[5/6] Menyusun ulang gambar...")
    def blocks_to_image(spatial_blocks, img_w, img_h):
        """Menyusun blok 8x8 menjadi gambar grayscale (2D array)."""
        img = np.zeros((img_h, img_w), dtype=np.float32)
        idx = 0
        for v in range(0, img_h, 8):
            for u in range(0, img_w, 8):
                blk = spatial_blocks[idx]
                img[v:v+8, u:u+8] = blk + 128.0   # level shift
                idx += 1
        return np.clip(img, 0, 255).astype(np.uint8)

    Y_img  = blocks_to_image(spatial_y,  N_W, N_H)
    Cb_sub = blocks_to_image(spatial_cb, width_sub, height_sub)
    Cr_sub = blocks_to_image(spatial_cr, width_sub, height_sub)

    # Upsampling Cb/Cr ke ukuran penuh (replikasi 2x2)
    Cb_full = np.kron(Cb_sub, np.ones((2, 2)))[:N_H, :N_W]
    Cr_full = np.kron(Cr_sub, np.ones((2, 2)))[:N_H, :N_W]

    # 6. Ekstrak Watermark (dari blok Y yang masih terkuantisasi?)
    # Catatan: watermark aslinya disisipkan di DCT sebelum kuantisasi.
    # Kita ekstrak dari nilai terkuantisasi yang sudah di‑inverse zigzag dan DPCM.
    # Untuk akurasi lebih baik, kita bisa menggunakan blok hasil dequantisasi? 
    # Di sini saya pakai nilai dari `blocks_y` (nilai integer terkuantisasi).
    print("[6/6] Ekstrak Watermark...")
    WM_INDEX = 19
    watermark_pixels = []
    for blk in blocks_y:   # blk adalah list 64 integer (sudah inverse zigzag)
        val = blk[WM_INDEX]
        if val > 0:
            watermark_pixels.append(255)
        else:
            watermark_pixels.append(0)

    # Buat gambar watermark biner
    wm_w = N_W // 8
    wm_h = N_H // 8
    wm_img = Image.new("1", (wm_w, wm_h))
    idx = 0
    for v in range(wm_h):
        for h in range(wm_w):
            if idx < len(watermark_pixels):
                wm_img.putpixel((h, v), watermark_pixels[idx])
                idx += 1
    wm_img.save("hasil_ekstrak_watermark.png")

    # Konversi YCbCr ke RGB
    # Rumus invers dari BT.601 yang Anda pakai di encoder
    def ycbcr2rgb(Y, Cb, Cr):
        R = Y + 1.402 * (Cr - 128)
        G = Y - 0.344136 * (Cb - 128) - 0.714136 * (Cr - 128)
        B = Y + 1.772 * (Cb - 128)
        return np.stack([
            np.clip(R, 0, 255),
            np.clip(G, 0, 255),
            np.clip(B, 0, 255)
        ], axis=-1).astype(np.uint8)

    rgb_img = ycbcr2rgb(Y_img, Cb_full, Cr_full)

    # Potong ke ukuran asli (tanpa padding)
    R_W, R_H = paket["R_W"], paket["R_H"]
    final_img = rgb_img[:R_H, :R_W, :]

    # Simpan gambar hasil
    result = Image.fromarray(final_img)
    result.save("hasil_rekonstruksi_gambar.png")

    print("\n=== PROSES SELESAI ===")
    print("File yang dihasilkan:")
    print("- hasil_ekstrak_watermark.png")
    print("- hasil_rekonstruksi_gambar.png (warna penuh)")

    # Di decoder, setelah ekstraksi:
    values_at_wm_index = [blk[WM_INDEX] for blk in blocks_y]
    print(f"\nDebug - Statistik koefisien di indeks {WM_INDEX}:")
    print(f"  Min    : {min(values_at_wm_index)}")
    print(f"  Max    : {max(values_at_wm_index)}")
    print(f"  Mean   : {np.mean(values_at_wm_index):.2f}")
    print(f"  Median : {np.median(values_at_wm_index):.2f}")
    print(f"  > 0    : {sum(1 for v in values_at_wm_index if v > 0)}")
    print(f"  <= 0   : {sum(1 for v in values_at_wm_index if v <= 0)}")
    print(f"  == 0   : {sum(1 for v in values_at_wm_index if v == 0)}")

if __name__ == "__main__":
    start_decompress("compress.pkl")