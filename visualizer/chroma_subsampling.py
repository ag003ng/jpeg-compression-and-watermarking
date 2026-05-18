import os
from PIL import Image

def buat_ilustrasi_subsampling(input_png_path, folder_output):
    """
    Fungsi untuk mengisolasi proses Chroma Subsampling 4:2:0.
    Menghasilkan visualisasi efek subsampling pada warna untuk ilustrasi dokumen.
    """
    # Validasi apakah file foto yang dimasukkan ada atau tidak
    if not os.path.exists(input_png_path):
        print(f"[-] Error: File '{input_png_path}' tidak ditemukan!")
        print("Silakan periksa kembali penulisan nama file atau folder Anda.")
        return

    if not os.path.exists(folder_output):
        os.makedirs(folder_output)
        
    print(f"[1/4] Membuka foto: {input_png_path}")
    img = Image.open(input_png_path).convert("RGB")
    width, height = img.size
    
    # Pastikan dimensi kelipatan 2 agar bisa dibagi rata saat subsampling 4:2:0
    pad_w = (width // 2) * 2
    pad_h = (height // 2) * 2
    img = img.resize((pad_w, pad_h))
    img.save(os.path.join(folder_output, "1_original.png"))
    
    print("[2/4] Mengonversi ruang warna RGB ke YCbCr...")
    ycbcr_img = img.convert("YCbCr")
    Y, Cb, Cr = ycbcr_img.split()
    
    print("[3/4] Memproses Chroma Subsampling 4:2:0 (Pengecilan matriks warna)...")
    sub_w, sub_h = pad_w // 2, pad_h // 2
    Cb_subsampled = Cb.resize((sub_w, sub_h), Image.Resampling.BOX)
    Cr_subsampled = Cr.resize((sub_w, sub_h), Image.Resampling.BOX)
    
    # --- PROSES VISUALISASI WARNA MURNI ---
    # Memperbesar kembali komponen warna yang menyusut menggunakan mode NEAREST (tanpa penghalusan)
    # Ini dilakukan agar piksel warna yang pecah/blur terlihat jelas secara visual
    Cb_visual = Cb_subsampled.resize((pad_w, pad_h), Image.Resampling.NEAREST)
    Cr_visual = Cr_subsampled.resize((pad_w, pad_h), Image.Resampling.NEAREST)
    
    # Membuat gambar rekonstruksi warna tiruan tanpa komponen Kecerahan (Y diset abu-abu konstan / 128)
    warna_saja_subsampled = Image.merge("YCbCr", (Image.new("L", (pad_w, pad_h), 128), Cb_visual, Cr_visual)).convert("RGB")
    warna_saja_subsampled.save(os.path.join(folder_output, "2_efek_warna_subsampled.png"))
    
    print("[4/4] Melakukan Upsampling & merekonstruksi gambar akhir...")
    # Menggunakan metode BILINEAR untuk mensimulasikan bagaimana image viewer bawaan komputer
    # menghaluskan kembali data warna yang hilang saat gambar JPEG dibuka
    Cb_upsampled = Cb_subsampled.resize((pad_w, pad_h), Image.Resampling.BILINEAR)
    Cr_upsampled = Cr_subsampled.resize((pad_w, pad_h), Image.Resampling.BILINEAR)
    
    # Satukan kembali Kecerahan (Y) asli yang tajam dengan warna (Cb, Cr) hasil subsampling
    img_reconstructed = Image.merge("YCbCr", (Y, Cb_upsampled, Cr_upsampled)).convert("RGB")
    
    # Simpan hasil akhir dalam format .jpg (Kualitas 100 agar murni hanya memperlihatkan efek subsampling)
    output_path = os.path.join(folder_output, "3_hasil_akhir_subsampling.jpg")
    img_reconstructed.save(output_path, "JPEG", quality=100)
    
    print(f"\n[+] Sukses! Silakan periksa folder '{folder_output}' untuk mengambil gambar.")


# --- EKSEKUSI OTOMATIS ---
if __name__ == "__main__":
    FOTO_INPUT = "example.jpg"
    OUTPUT_ILUSTRASI = "example-subsampling.jpg"
    buat_ilustrasi_subsampling(FOTO_INPUT, OUTPUT_ILUSTRASI)