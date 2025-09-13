import os
import tkinter as tk
from tkinter import filedialog, messagebox
import tarfile
import gzip
import io
import shutil
import tempfile
import time

def resource_path(relative_path):
    """Получает абсолютный путь к ресурсу, работает и в .exe"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath(os.path.dirname(__file__)), relative_path)
    
class IPKEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("IPK Editor by roma21515")
        self.extract_dir = None
        self.ipk_file = None
        self.is_tar_format = False

        # GUI elements
        self.label = tk.Label(root, text="Выберите IPK файл для распаковки")
        self.label.pack(pady=10)

        self.select_button = tk.Button(root, text="Выбрать IPK", command=self.select_ipk)
        self.select_button.pack(pady=5)

        self.extract_button = tk.Button(root, text="Распаковать", command=self.extract_ipk, state=tk.DISABLED)
        self.extract_button.pack(pady=5)

        self.pack_button = tk.Button(root, text="Собрать IPK", command=self.pack_ipk, state=tk.DISABLED)
        self.pack_button.pack(pady=5)

        self.status_label = tk.Label(root, text="")
        self.status_label.pack(pady=10)

    def is_gzip_file(self, filepath):
        with open(filepath, 'rb') as f:
            return f.read(2) == b'\x1f\x8b'

    def decompress_gzip(self, filepath, output_path):
        with gzip.open(filepath, 'rb') as f_in:
            with open(output_path, 'wb') as f_out:
                f_out.write(f_in.read())
        return output_path

    def is_ar_archive(self, filepath):
        with open(filepath, 'rb') as f:
            magic = f.read(8)
            return magic == b'!<arch>\n'

    def extract_ar(self, ar_path, extract_dir):
        with open(ar_path, 'rb') as f:
            magic = f.read(8)
            if magic != b'!<arch>\n':
                raise ValueError(f"Not a valid ar archive. First 8 bytes: {magic}")
            while True:
                header = f.read(60)
                if len(header) < 60:
                    break
                name = header[:16].decode('ascii').rstrip(' /')
                timestamp = int(header[16:28].decode('ascii').strip())
                owner = int(header[28:34].decode('ascii').strip())
                group = int(header[34:40].decode('ascii').strip())
                mode = int(header[40:48].decode('ascii').strip(), 8)
                size = int(header[48:58].decode('ascii').strip())
                end = header[58:60]
                if end != b'`\n':
                    raise ValueError("Invalid ar header")
                data = f.read(size)
                if size % 2 == 1:
                    f.read(1)  # padding
                file_path = os.path.join(extract_dir, name)
                with open(file_path, 'wb') as outf:
                    outf.write(data)
                os.chmod(file_path, mode)

    def extract_tar(self, tar_path, extract_dir):
        with tarfile.open(tar_path, 'r:*') as tar:
            tar.extractall(path=extract_dir)

    def create_ar(self, ar_path, file_paths):
        with open(ar_path, 'wb') as f:
            f.write(b'!<arch>\n')
            for file_path in file_paths:
                name = os.path.basename(file_path)
                if len(name) > 15:
                    raise ValueError(f"Filename too long: {name}")
                stat = os.stat(file_path)
                timestamp = int(stat.st_mtime)
                owner_id = 0
                group_id = 0
                mode = stat.st_mode & 0o777
                with open(file_path, 'rb') as inf:
                    data = inf.read()
                size = len(data)
                header = (
                    f"{name:<16}"
                    f"{timestamp:12}"
                    f"{owner_id:6}"
                    f"{group_id:6}"
                    f"{mode:8o}"
                    f"{size:10}"
                    f"`\n"
                ).encode('ascii')
                f.write(header)
                f.write(data)
                if size % 2 == 1:
                    f.write(b'\n')

    def create_tar(self, tar_path, file_paths):
        with tarfile.open(tar_path, 'w') as tar:
            for file_path in file_paths:
                tar.add(file_path, arcname=os.path.basename(file_path))

    def create_tar_gz(self, src_dir, tar_path):
        with tarfile.open(tar_path, 'w:gz') as tar:
            for item in os.listdir(src_dir):
                tar.add(os.path.join(src_dir, item), arcname=item)

    def compress_gzip(self, input_path, output_path):
        with open(input_path, 'rb') as f_in:
            with gzip.open(output_path, 'wb') as f_out:
                f_out.write(f_in.read())

    def select_ipk(self):
        self.ipk_file = filedialog.askopenfilename(filetypes=[("IPK files", "*.ipk")])
        if self.ipk_file:
            self.extract_button.config(state=tk.NORMAL)
            self.status_label.config(text=f"Выбран файл: {os.path.basename(self.ipk_file)}")
        else:
            self.extract_button.config(state=tk.DISABLED)
            self.status_label.config(text="Файл не выбран")

    def extract_ipk(self):
        if not self.ipk_file:
            messagebox.showerror("Ошибка", "Сначала выберите IPK файл")
            return

        self.extract_dir = os.path.splitext(os.path.basename(self.ipk_file))[0]
        os.makedirs(self.extract_dir, exist_ok=True)

        temp_ipk = self.ipk_file
        if self.is_gzip_file(self.ipk_file):
            temp_ipk = os.path.join(self.extract_dir, 'temp_ipk')
            self.decompress_gzip(self.ipk_file, temp_ipk)
            self.status_label.config(text=f"GZIP распакован в {temp_ipk}")

        try:
            if self.is_ar_archive(temp_ipk):
                self.is_tar_format = False
                self.extract_ar(temp_ipk, self.extract_dir)
            else:
                self.is_tar_format = True
                self.status_label.config(text="Не ar-архив, обрабатываем как tar...")
                self.extract_tar(temp_ipk, self.extract_dir)

            # Распаковка .tar.gz файлов
            for filename in list(os.listdir(self.extract_dir)):
                if filename.endswith('.tar.gz'):
                    tar_path = os.path.join(self.extract_dir, filename)
                    sub_dir_name = filename[:-7]
                    sub_dir = os.path.join(self.extract_dir, sub_dir_name)
                    os.makedirs(sub_dir, exist_ok=True)
                    self.extract_tar(tar_path, sub_dir)
                    os.remove(tar_path)

            if temp_ipk != self.ipk_file and os.path.exists(temp_ipk):
                os.remove(temp_ipk)
            self.pack_button.config(state=tk.NORMAL)
            self.status_label.config(text=f"Распаковано в {self.extract_dir}. Отредактируйте файлы и нажмите 'Собрать IPK'.")
            os.startfile(self.extract_dir)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось распаковать IPK: {str(e)}")
            self.status_label.config(text=f"Ошибка при распаковке: {str(e)}")

    def pack_ipk(self):
        if not self.extract_dir:
            messagebox.showerror("Ошибка", "Сначала распакуйте IPK файл")
            return

        # Формируем имена файлов
        base_name = os.path.splitext(os.path.basename(self.ipk_file))[0]
        new_ipk = os.path.join(os.path.dirname(self.ipk_file), base_name)
        final_ipk = os.path.join(os.path.dirname(self.ipk_file), f"{base_name}_mod.ipk")

        try:
            # Создаем .tar.gz для папок control, data, debian (если есть)
            sub_dirs = ['control', 'data']
            if os.path.exists(os.path.join(self.extract_dir, 'debian')):
                sub_dirs.append('debian')
            tar_files = []
            for sub in sub_dirs:
                src_dir = os.path.join(self.extract_dir, sub)
                if not os.path.exists(src_dir):
                    os.makedirs(src_dir)
                tar_path = os.path.join(self.extract_dir, f'{sub}.tar.gz')
                self.create_tar_gz(src_dir, tar_path)
                tar_files.append(tar_path)
                self.status_label.config(text=f"Создан {tar_path}")

            # Создаем debian-binary
            debian_binary = os.path.join(self.extract_dir, 'debian-binary')
            if not os.path.exists(debian_binary):
                with open(debian_binary, 'w') as f:
                    f.write('2.0\n')
                self.status_label.config(text=f"Создан {debian_binary}")

            # Собираем файлы для архива
            ar_files = [debian_binary] + tar_files
            self.status_label.config(text=f"Собираемые файлы: {', '.join(os.path.basename(f) for f in ar_files)}")

            # Создаем IPK во временной папке, чтобы избежать блокировок на оригинальной директории
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_ipk = os.path.join(temp_dir, f"{base_name}")  # Временный файл без расширения
                
                temp_output = os.path.join(temp_dir, 'temp_output')
                if self.is_tar_format:
                    self.create_tar(temp_output, ar_files)
                    self.compress_gzip(temp_output, temp_ipk)
                    if os.path.exists(temp_output):
                        os.remove(temp_output)
                else:
                    self.create_ar(temp_ipk, sorted(ar_files))

                # Теперь копируем из временной папки в финальное место
                time.sleep(0.5)  # Больше задержки
                if os.path.exists(final_ipk):
                    os.remove(final_ipk)
                shutil.copy2(temp_ipk, final_ipk)
                self.status_label.config(text=f"Файл скопирован в {final_ipk}")

                if os.path.exists(self.extract_dir):
                    shutil.rmtree(self.extract_dir)
            
            self.status_label.config(text=f"IPK собран: {final_ipk}")
            messagebox.showinfo("Успех", f"IPK успешно собран: {final_ipk}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось собрать IPK: {str(e)}")
            self.status_label.config(text=f"Ошибка при сборке: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = IPKEditor(root)
    root.geometry("400x200")
    root.mainloop()