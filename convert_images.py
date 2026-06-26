import os
from PyQt6.QtGui import QImage

def force_to_8bit_bmp() -> None:
    """Находит JPG и 24-битные BMP файлы в папке и сохраняет их как честные 8-bit BMP."""
    # Перебираем все файлы в текущей директории
    for file_name in os.listdir("."):
        if file_name.endswith((".jpg", ".jpeg", ".bmp")) and not file_name.endswith("_ready.bmp"):
            print(f"Обработка файла: {file_name}...")
            
            img: QImage = QImage(file_name)
            if img.isNull():
                continue
                
            # Принудительно конвертируем структуру пикселей в 8-битный индексированный формат (256 градаций серого)
            grayscale_img: QImage = img.convertToFormat(QImage.Format.Format_Indexed8)
            
            # Формируем новое имя
            base_name: str = os.path.splitext(file_name)[0]
            output_name: str = f"{base_name}_ready.bmp"
            
            # Сохраняем в честный BMP
            grayscale_img.save(output_name, "BMP")
            print(f"-> Успешно создан 8-битный файл: {output_name}")

if __name__ == "__main__":
    force_to_8bit_bmp()