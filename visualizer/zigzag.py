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
    if not quantized_blocks:
        return []

    # --- TAMBAHKAN PENGECEKAN INI ---
    # Jika inputnya cuma 1 matriks 2D langsung (bukan kumpulan blok), bungkus jadi list
    if isinstance(quantized_blocks[0], list) and len(quantized_blocks) == 8 and len(quantized_blocks[0]) == 8:
        # Otomatis meratakan matriks 8x8 menjadi 64 elemen
        quantized_blocks = [sum(quantized_blocks, [])]
    # ---------------------------------

    processed_blocks = []
    prev_dc = 0
    
    for block in quantized_blocks:
        zz_block = apply_zigzag(block)
        
        current_dc = zz_block[0]
        zz_block[0] = current_dc - prev_dc
        prev_dc = current_dc
        
        processed_blocks.append(zz_block)
        
    return processed_blocks

block_input_2d_textur = [
    [ 120,   15,   -4,    2,    0,    0,    0,    0],
    [  -8,    6,    1,    0,    0,    0,    0,    0],
    [   5,   -3,    0,    0,    0,    0,    0,    0],
    [   0,    2,    0,    0,    0,    0,    0,    0],
    [  -1,    0,  -15,    0,    0,    0,    0,    0], # -15 adalah contoh watermark di koordinat spasial berbeda
    [   0,    0,    0,    0,    0,    0,    0,    0],
    [   0,    0,    0,    0,    0,    0,    0,    0],
    [   0,    0,    0,    0,    0,    0,    0,    0]
]

print(process_zigzag_and_dc(block_input_2d_textur))