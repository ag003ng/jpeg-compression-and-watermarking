import math
import zlib
import pickle
import struct
from dahuffman import HuffmanCodec
from PIL import Image

# Atribut-atribut yang diperlukan
class dataImage :
    def __init__(self) :
        # Panjang dan lebar gambar tanpa padding (satuan pixel)
        self.R_W = 0
        self.R_H = 0

        # Panjang dan lebar gambar dengan padding (satuan pixel)
        self.N_W = 0
        self.N_H = 0

        # Informasi YCbCr (Hasil convert dari RGB) dalam satu dimensi
        self.y = []
        self.cb = []
        self.cr = []

        # Informasi sub-sampling untuk mengurangi komponen Cb dan Cr
        self.sub_width = 0
        self.sub_height = 0
        self.sub_cb = []
        self.sub_cr = []

        # Tempat menyimpan hasil array blok DCT (Masing-masing elemen berisi 64 koefisien)
        self.dct_y = []
        self.dct_cb = []
        self.dct_cr = []

        # Untuk menyimpan hasil Kuantisasi
        self.quant_y = []
        self.quant_cb = []
        self.quant_cr = []

        # Tempat menyimpan hasil Zigzag & DC Difference
        self.rle_y = []
        self.rle_cb = []
        self.rle_cr = []

        # Tempat menyimpan tabel luminance quantization dan chrominance quantization
        self.luma_q = []
        self.chroma_q = []

        # Hasil akhir file kompresi (dalam bentuk bytes)
        self.compressed_data = b""

        # Untuk menyimpan huffman tree
        self.codec = []

# INIT DCT LOOKUP TABLE
# agar komputer tidak perlu menghitung ulang rumus Cosinus jutaan kali.
COS_LOOKUP = [[0.0] * 8 for k in range(8)] # Matrix 8x8
for i in range(8):
    for j in range(8):
        COS_LOOKUP[i][j] = math.cos((2 * i + 1) * j * math.pi / 16.0)

M_SQRT1_2 = 1.0 / math.sqrt(2.0)

# TABEL KUANTISASI STANDAR JPEG (CCITT Rec. T.81)
STD_LUMA_QUANTIZER = [
    16, 11, 10, 16,  24,  40,  51,  61,
    12, 12, 14, 19,  26,  58,  60,  55,
    14, 13, 16, 24,  40,  57,  69,  56,
    14, 17, 22, 29,  51,  87,  80,  62,
    18, 22, 37, 56,  68, 109, 103,  77,
    24, 35, 55, 64,  81, 104, 113,  92,
    49, 64, 78, 87, 103, 121, 120, 101,
    72, 92, 95, 98, 112, 100, 103,  99
]

STD_CHROMA_QUANTIZER = [
    17, 18, 24, 47, 99, 99, 99, 99,
    18, 21, 26, 66, 99, 99, 99, 99,
    24, 26, 56, 99, 99, 99, 99, 99,
    47, 66, 99, 99, 99, 99, 99, 99,
    99, 99, 99, 99, 99, 99, 99, 99,
    99, 99, 99, 99, 99, 99, 99, 99,
    99, 99, 99, 99, 99, 99, 99, 99,
    99, 99, 99, 99, 99, 99, 99, 99
]

# Tabel indeks untuk membaca matriks 8x8 secara menyilang (Zig-Zag)
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

def rgb_to_ycbcr(red, green, blue) :
    """
    Mengubah warna RGB menjadi YCbCr berdasarkan standar ITU-R BT.601.
    Fungsi ini dibungkus dengan int() karena nilai warna digital harus berupa bilangan bulat (0-255).
    """
    y  =       (0.299 * red)    + (0.587 * green)    + (0.114 * blue) # Kecerahan cahaya
    cb = 128 - (0.168736 * red) - (0.331264 * green) + (0.5 * blue)   # Selisih warna biru dengan total kecerahan
    cr = 128 + (0.5 * red)      - (0.418688 * green) - (0.081312 * blue) # Selisih warna merah dengan total kecerahan

    return round(y), round(cb), round(cr)


def load_ppm_file(file_path, data : dataImage) :
    file = open(file_path, "rb") # rb = read binary
                                 # tujuan rb adalah agar python membaca file dalam bentuk byte-nya
                                 # dan tidak menerjemahkan file tersebut ke bentuk teks.

    magic_number = file.readline().decode().strip()
    # Karena dibaca dalam bentuk biner, perlu di-encode dulu
    # strip() berfungsi untuk membuang <spasi> atau '\n' di akhir kalimat

    dimention_line = file.readline().decode().strip()
    while (dimention_line.startswith("#")) :
        dimention_line = file.readline().decode().strip()
    # Untuk antisipasi karena ada converter ppm yang menyisipkan creator dari converter-nya

    dimention = dimention_line.split() # Mengubah teks string menjadi list
    data.R_W = int(dimention[0])
    data.R_H = int(dimention[1])

    file.readline().decode().strip() # Baris setelah dimensi gambar yang merupakan nilai dari warna tertinggi
                                     # Bisa disimpan atau di-skip seperti yang saya lakukan

    print(f"--- INFO HEADER FILE ---")
    print(f"Format (Magic Number) : {magic_number}")
    print(f"Dimensi foto asli     : {data.R_W} X {data.R_H}")

    data.N_W = ((data.R_W + 7) // 8) * 8
    data.N_H = ((data.R_H + 7) // 8) * 8
    # Saat proses DCT, gambar dibagi menjadi block yang lebih kecil dengan ukuran 8 x 8
    # Jika panjang atau lebarnya bukan kelipatan 8, komputer tidak akan bisa memprosesnya
    # Oleh karena itu, dilakukan padding untuk panjang atau lebar yang bukan kelipatan 8

    print(f"Dimensi foto padding  : {data.N_W} X {data.N_H}")

    bytes_data = file.read() # Membaca sisa file dalam bentuk byte-nya
    file.close()

    bytes_list = list(bytes_data) # Mengubah data biner menjadi bentuk list

    index = 0 # Mengatur posisi R, G, B untuk satu piksel

    # Loop sesuai dengan dimensi gambar setelah di tambahkan padding
    for i in range(data.N_H) :
        for j in range(data.N_W) :

            # Jika posisinya berada di dimensi gambar asli, convert byte RGB-nya ke YCbCr
            if (i < data.R_H and j < data.R_W) :
                R = bytes_list[index] 
                G = bytes_list[index + 1]
                B = bytes_list[index + 2]
                index += 3

                Y, Cb, Cr = rgb_to_ycbcr(R, G, B)

                data.y.append(Y)
                data.cb.append(Cb)
                data.cr.append(Cr)
            # Jika berada di daerah padding, isi dengan warna netral
            else :
                data.y.append(0)
                data.cb.append(128)
                data.cr.append(128)
        
    # Intinya, kode di atas berfungsi untuk mengambil warna pada satu piksel dan mengekstrak informasi cahayanya
    # Mengkalkulasikan informasi cahaya pada satu piksel dan menyimpannya di y_matrix

def chroma_subsampling(data : dataImage):
    """
    Melakukan Chroma Subsampling 4:2:0 pada komponen warna Cb dan Cr.
    Setiap blok 2x2 piksel akan dirata-rata menjadi 1 piksel.
    """
    print("\n--- MEMULAI CHROMA SUBSAMPLING 4:2:0 ---")
    
    # Karena ukuran di-subsampling dengan rasio 4:2:0, dimensi barunya dibagi 2
    data.sub_width = data.N_W // 2
    data.sub_height = data.N_H // 2
    
    """
    Jika dilihat, looping-nya seperti melompat seolah-olah ada nilai yang diabaikan.
    Padahal, ini karena piksel yang disimpan dalam list 1D.
    """
    for i in range(0, data.N_H, 2):
        for j in range(0, data.N_W, 2):
            
            # Posisi visualnya:
            # [kiri_atas]   [kanan_atas]
            # [kiri_bawah]  [kanan_bawah]
            idx_kiri_atas   = (i * data.N_W) + j
            idx_kanan_atas  = (i * data.N_W) + (j + 1)
            idx_kiri_bawah  = ((i + 1) * data.N_W) + j
            idx_kanan_bawah = ((i + 1) * data.N_W) + (j + 1)
            
            # Ambil nilai dan hitung rata-ratanya untuk komponen Cb
            avg_cb = (data.cb[idx_kiri_atas] + data.cb[idx_kanan_atas] + 
                    data.cb[idx_kiri_bawah] + data.cb[idx_kanan_bawah]) / 4.0
            
            # Lakukan hal yang sama untuk komponen Cr
            avg_cr = (data.cr[idx_kiri_atas] + data.cr[idx_kanan_atas] + 
                    data.cr[idx_kiri_bawah] + data.cr[idx_kanan_bawah]) / 4.0
            
            data.sub_cb.append(avg_cb)
            data.sub_cr.append(avg_cr)
            
    print(f"Total ukuran Y asli    : {len(data.y)} piksel")
    print(f"Total ukuran Cb/Cr sub : {len(data.sub_cb)} piksel")

# FUNGSI DCT BLOCK (Mengeksekusi 1 Blok 8x8)
def dct_block_optimized(data_in, start_idx, gap):
    """
    Melakukan 2D DCT pada 1 blok 8x8 dengan teknik Separable (1D beruntun).
    
    data_in   : List 1D data piksel (Y, sub_cb, atau sub_cr)
    start_idx : Posisi indeks piksel pertama (kiri atas) dari blok 8x8 saat ini
    gap       : Lebar dimensi gambar (N_W atau sub_W) untuk melompat antar baris
    """
    inner_lookup = [[0.0] * 8 for _ in range(8)]
    out_block = [0.0] * 64 # Menampung hasil 64 koefisien frekuensi
    
    # --- TAHAP 1: DCT Vertikal & Level Shifting (-128) ---
    for x_t in range(8):
        for y_f in range(8):
            sum_val = 0.0
            for y_t in range(8):
                idx = start_idx + (y_t * gap) + x_t
                
                # Pengurangan 128 (Level shifting) dan perkalian cosinus
                sum_val += (data_in[idx] - 128.0) * COS_LOOKUP[y_t][y_f]
            
            inner_lookup[x_t][y_f] = sum_val

    # --- TAHAP 2: DCT Horizontal & Normalisasi ---
    for y_f in range(8):
        for x_f in range(8):
            freq = 0.0
            for x_t in range(8):
                freq += inner_lookup[x_t][y_f] * COS_LOOKUP[x_t][x_f]

            # Normalisasi untuk frekuensi DC (indeks 0)
            if x_f == 0:
                freq *= M_SQRT1_2
            if y_f == 0:
                freq *= M_SQRT1_2
            freq /= 4.0 

            # Simpan hasil dalam array 1D (panjang 64 elemen)
            out_block[(y_f * 8) + x_f] = freq
            
    return out_block

def process_DCT(data : dataImage):
    """
    Menentukan titik awal setiap blok 8x8,
    lalu melemparnya ke fungsi dct_block_optimized.
    """
    print("\n--- MEMULAI PROSES DCT (OPTIMIZED) ---")
    
    # Dimensi
    w_y, h_y = data.N_W, data.N_H
    w_c, h_c = data.sub_width, data.sub_height
    
    blocks_horiz_y = w_y // 8
    blocks_vert_y  = h_y // 8
    
    blocks_horiz_c = w_c // 8
    blocks_vert_c  = h_c // 8

    # --- PROSES KOMPONEN Y ---
    for v in range(blocks_vert_y):
        for h in range(blocks_horiz_y):
            # Mencari indeks titik kiri-atas blok saat ini
            start_idx = (v * 8 * w_y) + (h * 8)
            block_result = dct_block_optimized(data.y, start_idx, w_y)
            data.dct_y.append(block_result)

    # --- PROSES KOMPONEN Cb ---
    for v in range(blocks_vert_c):
        for h in range(blocks_horiz_c):
            start_idx = (v * 8 * w_c) + (h * 8)
            block_result = dct_block_optimized(data.sub_cb, start_idx, w_c)
            data.dct_cb.append(block_result)

    # --- PROSES KOMPONEN Cr ---
    for v in range(blocks_vert_c):
        for h in range(blocks_horiz_c):
            start_idx = (v * 8 * w_c) + (h * 8)
            block_result = dct_block_optimized(data.sub_cr, start_idx, w_c)
            data.dct_cr.append(block_result)

    print("Proses DCT Selesai!")
    print(f"Total Blok DCT Y  : {len(data.dct_y)} blok")
    print(f"Total Blok DCT Cb : {len(data.dct_cb)   } blok")
    print(f"Total Blok DCT Cr : {len(data.dct_cr)} blok")

# CITRA WATERMARK VISUAL
WM_INDEX = 19 # Indeks koefisien frekuensi menengah (Mid-Band) yang aman
ALPHA = 30 # Kekuatan penyisipan (Gain Factor)

def embed_visual_binary_watermark(data: dataImage, watermark_path):
    """
    Membaca Citra Biner dari file eksternal yang ukurannya pas 
    dengan grid blok gambar wajah, lalu menyisipkannya ke ranah DCT Y.
    """
    blocks_horiz = data.N_W // 8
    blocks_vert = data.N_H // 8
    
    citra_watermark_grid = []
    
    # Buka gambar watermark menggunakan library PIL
    try:
        # Konversi ke "1" (Mode Biner murni: 1-bit pixel, hitam/putih)
        wm_img = Image.open(watermark_path).convert("L").point(lambda x: 255 if x > 127 else 0).convert("1")
    except FileNotFoundError:
        print(f"Error: File watermark '{watermark_path}' tidak ditemukan!")
        return [], []

    # Paksa ukuran gambar agar sesuai dengan jumlah blok 
    if wm_img.size != (blocks_horiz, blocks_vert):
        print(f"Peringatan: Ukuran watermark diubah paksa menjadi {blocks_horiz}x{blocks_vert}")
        wm_img = wm_img.resize((blocks_horiz, blocks_vert))
    
    # Ekstrak piksel dari gambar watermark ke dalam grid list
    for v in range(blocks_vert):
        for h in range(blocks_horiz):
            # Ambil nilai piksel pada koordinat (x=h, y=v)
            # Di mode "1", piksel putih bernilai 255, piksel hitam bernilai 0
            pixel_val = wm_img.getpixel((h, v))
            
            # Konversi: Putih -> 1 (Ada watermark), Hitam -> -1 (Background)
            if pixel_val == 255:
                citra_watermark_grid.append(1)
            else:
                citra_watermark_grid.append(-1)
                
    # Sisipkan piksel citra biner visual tersebut ke koefisien DCT gambar asli
    watermarked_dct_y = []
    for i, block in enumerate(data.dct_y):
        pixel_logo = citra_watermark_grid[i]
        new_block = list(block)
        
        # Rumus penyisipan frekuensi menengah (additive): Coeff = Coeff + (Alpha * Piksel_Watermark)
        new_block[WM_INDEX] += ALPHA * pixel_logo
        watermarked_dct_y.append(new_block)
        
    return watermarked_dct_y, citra_watermark_grid

def set_quality(std_quantizer, quality):
    """
    Mengubah nilai pada tabel kuantisasi berdasarkan target kualitas (1-100).
    Sama seperti fungsi Quality Slider di aplikasi edit foto.
    """
    # Cek agar quality berada di ambang batas

    if quality <= 0: quality = 1
    if quality > 100: quality = 100

    scaled_quantizer = []
    for q in std_quantizer:
        if quality < 50:
            scale = 5000.0 / quality
        else:
            scale = 200.0 - quality * 2.0
        val = (q * scale + 50.0) / 100.0   # pembulatan
        val = int(max(1, min(255, round(val))))
        scaled_quantizer.append(val)
    return scaled_quantizer

def quantize_block(block_in, quantizer):
    """
    Membagi 1 blok (64 koefisien DCT) dengan tabel kuantisasi.
    """
    block_out = []
    for i in range(64):
        # Bagi dengan elemen quantizer pada indeks yang sama
        val = block_in[i] / quantizer[i]
        
        val = round(val)
        
        # CLIP batas JPEG 12-bit (-2048 hingga 2047)
        val = max(-2048, min(2047, val))
        block_out.append(val)
        
    return block_out

def process_quantization(data: dataImage, quality):
    """
    Memproses kuantisasi untuk seluruh blok Y, Cb, dan Cr.
    """
    print(f"\n--- MEMULAI PROSES KUANTISASI (Kualitas: {quality}%) ---")
    
    # Siapkan tabel kuantisasi berdasarkan kualitas target
    data.luma_q = set_quality(STD_LUMA_QUANTIZER, quality)
    data.chroma_q = set_quality(STD_CHROMA_QUANTIZER, quality)
    
    # Proses semua blok Y (Luminance) dengan luma_q
    for block in data.dct_y:
        data.quant_y.append(quantize_block(block, data.luma_q))
        
    # Proses semua blok Cb dan Cr (Chrominance) dengan chroma_q
    for block in data.dct_cb:
        data.quant_cb.append(quantize_block(block, data.chroma_q))
        
    for block in data.dct_cr:
        data.quant_cr.append(quantize_block(block, data.chroma_q))
        
    print("Proses Kuantisasi Selesai!")

def apply_rle(zz_block):
    """
    Melakukan Run-Length Encoding sederhana.
    Mencari rentetan angka 0 di akhir blok dan menggantinya dengan 'EOB'.
    """
    # Cari indeks angka bukan nol yang paling terakhir di dalam blok
    last_non_zero_idx = 63
    while last_non_zero_idx > 0 and zz_block[last_non_zero_idx] == 0:
        last_non_zero_idx -= 1
        
    # Ambil data dari indeks 0 sampai indeks bukan nol terakhir
    rle_block = zz_block[:last_non_zero_idx + 1]
    
    # Jika masih ada sisa tempat di blok (artinya ujungnya adalah 0), tambahkan 'EOB'
    if last_non_zero_idx < 63:
        rle_block.append('EOB')
        
    return rle_block

def apply_zigzag(block):
    """
    Mengurutkan 64 elemen blok kuantisasi menjadi urutan Zig-Zag.
    Ini mengumpulkan angka-angka berharga di awal dan angka 0 di akhir.
    """
    zigzag_block = [0] * 64
    for i in range(64):
        # Memetakan nilai dari indeks zig-zag ke array linier
        zigzag_block[i] = block[ZIGZAG_ORDER[i]]
    return zigzag_block

def process_zigzag_and_dc(quantized_blocks):
    """
    Melakukan Zig-Zag pada setiap blok dan menghitung selisih DC (DPCM).
    Mengikuti logika fungsi 'zigzag' dan 'diff_dc' pada kode C.
    """
    if not quantized_blocks:
        return []

    processed_blocks = []
    prev_dc = 0
    
    for block in quantized_blocks:
        # Lakukan Zig-Zag
        zz_block = apply_zigzag(block)
        
        # Lakukan DC Difference (Selisih koefisien DC indeks 0)
        current_dc = zz_block[0]
        zz_block[0] = current_dc - prev_dc
        prev_dc = current_dc

        rle_result = apply_rle(zz_block)
        
        processed_blocks.append(rle_result)
        
    return processed_blocks
    
def encode_entropy_huffman(data : dataImage):
    """
    Menggunakan library 'dahuffman' untuk mengompresi data hasil kuantisasi
    secara murni menggunakan algoritma Huffman Coding.
    """
    print("\n--- MEMULAI PROSES ENTROPY CODING (HUFFMAN) ---")
    
    # Proses Zig-zag dan DC Difference (Persiapan wajib JPEG)
    data.rle_y = process_zigzag_and_dc(data.quant_y)
    data.rle_cb = process_zigzag_and_dc(data.quant_cb)
    data.rle_cr = process_zigzag_and_dc(data.quant_cr)
    
    # Gabungkan semua blok menjadi satu urutan/list panjang (1 Dimensi)
    # Ini mensimulasikan aliran data (data stream) yang akan dikodekan
    all_data_stream = []
    for b in data.rle_y: all_data_stream.extend(b)
    for b in data.rle_cb: all_data_stream.extend(b)
    for b in data.rle_cr: all_data_stream.extend(b)
    
    # --- PROSES HUFFMAN CODING ---
    
    # Biarkan library secara dinamis membuat Tabel Frekuensi & Huffman Tree 
    # (Ini menggantikan ratusan baris fungsi huff_count, huff_sort, huff_size di file .c)
    print("Membangun Huffman Tree secara dinamis...")
    codec = HuffmanCodec.from_data(all_data_stream)
    
    # Lakukan kompresi (Encode) data stream menggunakan tabel yang sudah dibuat
    data.compressed_data = codec.encode(all_data_stream)
    data.codec = codec
    
    # --- PERHITUNGAN RASIO KOMPRESI ---
    
    # Menghitung ukuran asli jika setiap angka integer disimpan dalam 2 bytes (16-bit)
    # karena standar koefisien JPEG berentang -2048 s/d 2047
    ukuran_sebelum = len(all_data_stream) * 2 
    ukuran_sesudah = len(data.compressed_data)
    
    if ukuran_sebelum > 0:
        rasio = (1 - (ukuran_sesudah / ukuran_sebelum)) * 100
    else:
        rasio = 0
        
    print(f"Ukuran Data Mentah (16-bit)  : {ukuran_sebelum / 1024:.2f} KB")
    print(f"Ukuran Terkompresi (Huffman) : {ukuran_sesudah / 1024:.2f} KB")
    print(f"Rasio Kompresi Akhir         : Menyusut {rasio:.2f}%")
    
    return data.compressed_data

if __name__ == "__main__":
    file_gambar_asli = "foto-wajah.ppm"
    file_watermark = "watermark.png"
    file_output_pkl = "compress.pkl"

    print("=== MEMULAI PROGRAM KOMPRESI & WATERMARKING (MODULAR) ===")
    
    try:
        img_data = dataImage()
        
        print("\n[1/6] Membaca file gambar dan konversi warna...")
        load_ppm_file(file_gambar_asli, img_data)
        
        print("\n[2/6] Melakukan Chroma Subsampling...")
        chroma_subsampling(img_data)
        
        print("\n[3/6] Memproses Transformasi DCT 8x8...")
        process_DCT(img_data)
        
        print("\n[4/6] Menyisipkan Watermark Biner...")
        watermarked_y, grid_wm = embed_visual_binary_watermark(img_data, watermark_path=file_watermark)
        if watermarked_y:
            img_data.dct_y = watermarked_y
            print("      [+] Watermark berhasil disisipkan!")
        else:
            print("      [-] Peringatan: Gagal menyisipkan watermark.")
        
        TARGET_KUALITAS = 80
        print(f"\n[5/6] Memproses Kuantisasi (Kualitas: {TARGET_KUALITAS}%)...")
        process_quantization(img_data, quality=TARGET_KUALITAS)
        
        print("\n[6/6] Memproses Entropy Coding (Huffman)...")
        compressed_bytes = encode_entropy_huffman(img_data)
        
        print("\n[7/7] Menyimpan Paket Kompresi (.pkl)...")
        paket_kompresi = {
            "R_W": img_data.R_W,
            "R_H": img_data.R_H,
            "N_W": img_data.N_W,
            "N_H": img_data.N_H,
            "width_sub": img_data.sub_width,
            "height_sub": img_data.sub_height,
            "len_y": sum(len(b) for b in img_data.rle_y),
            "len_cb": sum(len(b) for b in img_data.rle_cb),
            "len_cr": sum(len(b) for b in img_data.rle_cr),
            "codec": img_data.codec,
            "biner": compressed_bytes,
            "luma_q": img_data.luma_q, 
            "chroma_q": img_data.chroma_q   
        }
        
        with open(file_output_pkl, "wb") as f:
            pickle.dump(paket_kompresi, f)
            
        print(f"\n[SUKSES] File tersimpan: '{file_output_pkl}'")
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        
    print("\n=== PROGRAM SELESAI ===")