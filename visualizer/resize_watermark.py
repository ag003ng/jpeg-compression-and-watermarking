import os
from PIL import Image

def siapkan_watermark(input_path, output_path, target_width, target_height):
    """
    Fungsi untuk mengubah ukuran gambar menjadi spesifik (122x162)
    dan mengonversinya menjadi citra biner (Hitam-Putih murni).
    """
    # 1. Cek apakah file gambar asli ada
    if not os.path.exists(input_path):
        print(f"Error: File '{input_path}' tidak ditemukan!")
        print("Pastikan nama file dan foldernya sudah benar.")
        return

    # 2. Buka gambar watermark yang Anda siapkan (bisa dari ukuran berapa saja)
    img = Image.open(input_path)
    print(f"Ukuran gambar asli: {img.width} x {img.height} piksel")

    # 3. Ubah Ukuran (Resize)
    # Sangat Penting: Kita gunakan Image.Resampling.NEAREST
    # Ini mencegah Pillow membuat warna abu-abu (anti-aliasing) di tepian logo saat dikecilkan/dibesarkan.
    # Kita hanya butuh warna hitam atau putih tegas!
    img_resized = img.resize((target_width, target_height), Image.Resampling.NEAREST)

    # 4. Konversi ke mode "1" (Biner / 1-bit pixel)
    # Nilai piksel akan dipaksa menjadi 0 (Hitam murni) atau 255 (Putih murni)
    img_binary = img_resized.convert("L").point(lambda x: 255 if x > 127 else 0).convert("1")
    
    # 5. Simpan hasilnya
    img_binary.save(output_path)
    
    print("\n[SUKSES] Gambar watermark siap digunakan!")
    print(f"Disimpan sebagai: {output_path}")
    print(f"Ukuran akhir    : {img_binary.width} x {img_binary.height} piksel")


# =====================================================================
# BLOK EKSEKUSI
# =====================================================================
if __name__ == "__main__":
    # Ganti "logo_kampus_asli.png" dengan nama file gambar Anda saat ini
    # (Bisa gambar berukuran besar hasil download atau editan sendiri)
    file_input = "watermark.png" 
    
    # Nama file output yang ukurannya sudah pas (Ini yang nanti dimasukkan ke main.py)
    file_output = "watermark_padding.png"
    
    # Target ukuran (Lebar x Tinggi)
    LEBAR_TARGET = 122
    TINGGI_TARGET = 162
    
    print("=== Aplikasi Penyesuai Ukuran Watermark ===")
    siapkan_watermark(file_input, file_output, LEBAR_TARGET, TINGGI_TARGET)