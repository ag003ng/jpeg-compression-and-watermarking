import os
from PIL import Image, ImageOps

def pad_image_to_tile8_pillow(image_path, output_path):
    """
    Fungsi mandiri untuk mendeteksi ukuran gambar .png dan memberikan padding
    di sisi kanan dan bawah agar dimensinya menjadi kelipatan 8.
    """
    # 1. Pastikan file gambar yang dituju ada
    if not os.path.exists(image_path):
        print(f"Error: File '{image_path}' tidak ditemukan!")
        print("Pastikan file gambar berada di folder yang sama dengan skrip ini.")
        return False

    # 2. Buka gambar menggunakan Pillow
    img = Image.open(image_path)
    w_asli, h_asli = img.size
    
    # 3. Hitung berapa piksel yang kurang agar genap kelipatan 8
    # Menggunakan modulus 8. Jika sudah kelipatan 8, hasilnya otomatis 0
    pad_bawah = (8 - (h_asli % 8)) % 8
    pad_kanan = (8 - (w_asli % 8)) % 8
    
    # Jika gambar sudah kelipatan 8, langsung simpan/salin tanpa diubah
    if pad_bawah == 0 and pad_kanan == 0:
        print(f"\nGambar '{image_path}' sudah kelipatan 8 ({w_asli}x{h_asli}).")
        print("Tidak memerlukan padding tambahan.")
        img.save(output_path)
        return True
    
    # 4. Atur konfigurasi padding (kiri, atas, kanan, bawah)
    # Kita hanya ingin menambahkan di kanan dan bawah agar koordinat (0,0) tidak bergeser
    padding_config = (0, 0, pad_kanan, pad_bawah)
    
    # 5. Eksekusi padding dengan warna abu-abu netral (R=128, G=128, B=128)
    padded_img = ImageOps.expand(img, padding_config, fill=(128, 128, 128))
    
    # 6. Simpan hasil akhirnya
    padded_img.save(output_path)
    
    # Tampilkan informasi visual di terminal
    print(f"\n[PROSES PADDING SELESAI]")
    print(f"Nama File Asli      : {image_path}")
    print(f"Dimensi Awal        : {w_asli} x {h_asli} piksel")
    print(f"Piksel yang Ditambah: Kanan (+{pad_kanan}), Bawah (+{pad_bawah})")
    print(f"Dimensi Akhir       : {padded_img.size[0]} x {padded_img.size[1]} piksel (Kelipatan 8)")
    print(f"File Berhasil Disimpan: {output_path}")
    return True


# =====================================================================
# BLOK EKSEKUSI OTOMATIS
# =====================================================================
if __name__ == "__main__":
    # Tentukan nama file .png input dan output Anda di sini
    # Silakan ganti "foto-muka.png" dengan nama file asli Anda
    file_input = "foto-wajah.jpeg" 
    file_output = "foto-wajah-padded.jpeg"
    
    print("=== Aplikasi Pembungkus Gambar (Padding Kelipatan 8) ===")
    
    # Jalankan fungsi
    pad_image_to_tile8_pillow(file_input, file_output)