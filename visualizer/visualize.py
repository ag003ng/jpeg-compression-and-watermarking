import os
from PIL import Image

def buat_visualisasi_warna_asli(image_path):
    if not os.path.exists(image_path):
        print(f"Error: File '{image_path}' tidak ditemukan!")
        return

    # 1. Buka gambar asli dalam mode RGB
    img_rgb = Image.open(image_path).convert("RGB")
    w, h = img_rgb.size
    
    # Buat folder untuk menyimpan hasil gambar
    os.makedirs("visualisasi_warna_asli", exist_ok=True)
    
    # Menyiapkan saluran kosong (berisi angka 0) untuk bantuan manipulasi RGB
    r_channel, g_channel, b_channel = img_rgb.split()
    hitam = r_channel.point(lambda x: 0)

    print("--- Memproses Saluran RGB ---")
    # Saluran R Asli (R, 0, 0) -> Hanya memancarkan cahaya merah
    img_r_warna = Image.merge("RGB", (r_channel, hitam, hitam))
    img_r_warna.save("visualisasi_warna_asli/1_RGB_Saluran_Red_Warna.png")
    
    # Saluran G Asli (0, G, 0) -> Hanya memancarkan cahaya hijau
    img_g_warna = Image.merge("RGB", (hitam, g_channel, hitam))
    img_g_warna.save("visualisasi_warna_asli/2_RGB_Saluran_Green_Warna.png")
    
    # Saluran B Asli (0, 0, B) -> Hanya memancarkan cahaya biru
    img_b_warna = Image.merge("RGB", (hitam, hitam, b_channel))
    img_b_warna.save("visualisasi_warna_asli/3_RGB_Saluran_Blue_Warna.png")


    print("--- Memproses Saluran YCbCr ---")
    # Konversi gambar ke format YCbCr
    img_ycbcr = img_rgb.convert("YCbCr")
    y_data, cb_data, cr_data = img_ycbcr.split()

    # A. Saluran Y (Luminance) -> Warna aslinya memang grayscale/hitam-putih murni
    y_data.save("visualisasi_warna_asli/4_YCbCr_Saluran_Y_Warna.png")

    # B. Mewarnai Saluran Cb (Chroma Blue) 
    # Kita kunci nilai Y (Kecerahan) di angka 128 (tengah-tengah) dan Cr di angka 128 (netral)
    # Ini akan memunculkan warna transisi asli Cb dari Kuning ke Biru
    y_netral = y_data.point(lambda x: 128)
    cr_netral = cr_data.point(lambda x: 128)
    img_cb_warna = Image.merge("YCbCr", (y_netral, cb_data, cr_netral)).convert("RGB")
    img_cb_warna.save("visualisasi_warna_asli/5_YCbCr_Saluran_Cb_Warna.png")

    # C. Mewarnai Saluran Cr (Chroma Red)
    # Kita kunci nilai Y di angka 128 dan Cb di angka 128 (netral)
    # Ini akan memunculkan warna transisi asli Cr dari Sian (Hijau Toska) ke Merah
    cb_netral = cb_data.point(lambda x: 128)
    img_cr_warna = Image.merge("YCbCr", (y_netral, cb_netral, cr_data)).convert("RGB")
    img_cr_warna.save("visualisasi_warna_asli/6_YCbCr_Saluran_Cr_Warna.png")

    print("\n[SUKSES] Semua file warna asli berhasil dibuat!")
    print("Silakan cek folder 'visualisasi_warna_asli' di komputer Anda.")

if __name__ == "__main__":
    # Pastikan file "foto-muka.png" ada di folder yang sama
    buat_visualisasi_warna_asli("foto-wajah.jpeg")