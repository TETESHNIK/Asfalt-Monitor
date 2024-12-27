import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import cv2
import os
import datetime
from threading import Thread, Event
import logging
import subprocess

# Настройка логирования
logging.basicConfig(
    filename="app.log",  # Имя файла для логов
    level=logging.INFO,  # Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    format="%(asctime)s - %(levelname)s - %(message)s",  # Формат записи логов
    encoding="utf-8"
)


# Локализация
LANGUAGES = {
    "ru": {
        "start": "Начать работу",
        "stop": "Остановить работу",
        "connection": "Соединение",
        "settings": "Настройки",
        "help": "ПОМОЩЬ",
        "database": "Открыть базу данных",
        "logs": "Открыть логи",
        "connection_msg": "Функционал соединения в разработке",
        "settings_msg": "Функционал настроек в разработке",
        "help_msg": "Обратитесь в техническую поддержку: @Yarik_NMSK71",
        "database_msg": "Открытие базы данных в разработке",
        "logs_not_found": "Файл логов не найден.",
        "logs_error": "Не удалось открыть файл логов: {error}",
        "os_error": "Неизвестная операционная система",
        "closing": "Приложение закрывается пользователем"
    },
    "en": {
        "start": "Start Work",
        "stop": "Stop Work",
        "connection": "Connection",
        "settings": "Settings",
        "help": "HELP",
        "database": "Open Database",
        "logs": "Open Logs",
        "connection_msg": "Connection functionality is under development",
        "settings_msg": "Settings functionality is under development",
        "help_msg": "Contact technical support: @Yarik_NMSK71",
        "database_msg": "Database functionality is under development",
        "logs_not_found": "Log file not found.",
        "logs_error": "Failed to open log file: {error}",
        "os_error": "Unknown operating system",
        "closing": "Application is closing by the user"
    }
}

# FPS класс для отслеживания FPS
class FPS:
    def __init__(self):
        self._start = None
        self._numFrames = 0

    def start(self):
        self._start = datetime.datetime.now()
        return self

    def update(self):
        self._numFrames += 1

    def elapsed(self):
        return (datetime.datetime.now() - self._start).total_seconds()

    def fps(self):
        return self._numFrames / self.elapsed()


# Камера, которая захватывает и сохраняет кадры, а также записывает видео
class CameraModule:
    def __init__(self, camera_index=0, output_dir="frames", frame_rate=30, video_filename="output_video.avi"):
        self.camera_index = camera_index
        self.cap = None
        self.output_dir = output_dir
        self.frame_rate = frame_rate
        self.video_filename = video_filename
        self.running = False
        self.frames = []
        self.video_writer = None
        self.stop_event = Event()  # Событие для остановки потока
        self.fps_tracker = FPS()  # Отслеживание FPS

        # Создание директории для сохранения кадров
        os.makedirs(self.output_dir, exist_ok=True)

    def start(self):
        """Запуск камеры"""
        self.running = True
        self.fps_tracker.start()  # Старт отслеживания FPS
        self.frames = []  # Очистка кадров
        self.video_writer = None  # Переинициализация видеозаписи

        self.cap = cv2.VideoCapture(self.camera_index)  # Открытие камеры
        if not self.cap.isOpened():
            raise Exception("Не удалось открыть камеру")
        self.cap.set(cv2.CAP_PROP_FPS, self.frame_rate)  # Устанавливаем FPS

        # Запуск потока для захвата кадров
        Thread(target=self.capture_frames, daemon=True).start()

    def capture_frames(self):
        """Захват кадров и запись их в файл"""
        frame_count = 0
        while self.running and not self.stop_event.is_set():
            ret, frame = self.cap.read()
            if ret:
                self.fps_tracker.update()  # Обновляем FPS
                self.frames.append(frame)

                # Сохраняем кадр на диск с уникальным именем
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                frame_path = os.path.join(self.output_dir, f"frame_{timestamp}_{frame_count:04d}.jpg")
                success = cv2.imwrite(frame_path, frame)
                if success:
                    print(f"Сохранен кадр {frame_count:04d} в {frame_path}")
                else:
                    print(f"Ошибка при сохранении кадра {frame_count:04d}")

                # Инициализируем видеозапись, если еще не сделано
                if self.video_writer is None:
                    fourcc = cv2.VideoWriter_fourcc(*'XVID')  # Кодек для .avi файлов
                    self.video_writer = cv2.VideoWriter(
                        os.path.join(self.output_dir, f"video_{timestamp}.avi"),  # Уникальное имя видео
                        fourcc, 30, (frame.shape[1], frame.shape[0])
                    )

                # Записываем кадр в видео
                self.video_writer.write(frame)

                frame_count += 1

        # После завершения захвата, освобождаем ресурсы
        self.cap.release()
        if self.video_writer:
            self.video_writer.release()

    def stop(self):
        """Остановка камеры"""
        self.running = False
        self.stop_event.set()  # Останавливаем поток
        self.stop_event.clear()  # Сбрасываем событие для возможности повторного использования
        # Ожидаем завершения потока
        if self.cap.isOpened():
            self.cap.release()
        if self.video_writer:
            self.video_writer.release()
        logging.info("Камера остановлена.")

    def get_frame(self):
        """Получить текущий кадр с камеры"""
        if self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return None

# Основной класс для графического интерфейса
class CameraApp:

    def __init__(self, root):
        self.root = root
        self.root.title("Асфальт-Монитор")
        self.root.geometry("800x500")
        self.root.configure(bg="gray")

        # Инициализация языка (по умолчанию русский)
        self.language = "ru"

        # Камера
        self.camera = CameraModule(camera_index=0, output_dir="frames", frame_rate=30,
                                   video_filename="output_video.avi")
        self.frame = None

        # Виджет для изображения
        self.camera_label = tk.Label(self.root, bg="black")
        self.camera_label.grid(row=0, column=0, padx=10, pady=10, columnspan=3, sticky="nsew")

        # Настройка растяжения строк и столбцов
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_columnconfigure(2, weight=1)


        # Кнопка "Начать работу"
        self.start_button = tk.Button(
            self.root,
            text=self.tr("start"),
            bg="red",
            command=self.toggle_camera,
            relief="flat",  # Убирает обводку
            font=("Arial", 12, "bold")  # Меняет шрифт (название, размер, стиль)
        )
        self.start_button.grid(row=0, column=2, padx=10, pady=10)

        # Кнопки справа
        self.connection_button = tk.Button(
            self.root,
            text=self.tr("connection"),
            bg="orange",
            command=self.show_connection,
            relief="flat",  # Убирает обводку
            font=("Arial", 12, "bold")  # Меняет шрифт (название, размер, стиль)
        )
        self.connection_button.grid(row=1, column=2, padx=10, pady=5)

        # Настройки как подменю

        # Создание кнопки-меню "Настройки"
        self.settings_button = tk.Menubutton(
            self.root,
            text=self.tr("settings"),
            bg="orange",
            relief="flat",  # Убираем обводку
            font=("Arial", 12, "bold"),  # Настраиваем шрифт
            padx=10,
            pady=5
        )

        # Создание выпадающего меню
        self.settings_menu = tk.Menu(self.settings_button, tearoff=0, font=("Arial", 10))  # Настраиваем шрифт в меню

        # Добавление пунктов меню
        self.settings_menu.add_command(label="Русский", command=lambda: self.switch_language("ru"))
        self.settings_menu.add_command(label="English", command=lambda: self.switch_language("en"))

        # Привязываем меню к кнопке
        self.settings_button.config(menu=self.settings_menu)

        # Размещение кнопки-меню
        self.settings_button.grid(row=2, column=2, padx=15, pady=10)


        self.help_button = tk.Button(
            self.root,
            text=self.tr("help"),
            bg="orange",
            command=self.show_help,
            relief="flat",  # Убирает обводку
            font=("Arial", 12, "bold")  # Меняет шрифт (название, размер, стиль)
        )
        self.help_button.grid(row=3, column=2, padx=10, pady=5)


        self.database_button = tk.Button(
            self.root,
            text=self.tr("database"),
            bg="yellow",
            command=self.open_database,
            relief="flat",  # Убирает обводку
            font=("Arial", 12, "bold")  # Меняет шрифт (название, размер, стиль)
        )
        self.database_button.grid(row=2, column=1, padx=20, pady=10)


        # Пример обновления кнопки
        self.logs_button = tk.Button(
            self.root,
            text=self.tr("logs"),
            bg="yellow",
            command=self.open_logs,
            relief="flat",  # Убирает обводку
            font=("Arial", 12, "bold")  # Меняет шрифт (название, размер, стиль)
        )
        self.logs_button.grid(row=1, column=1, padx=10, pady=5)

        # Флаг работы камеры
        self.running = False

    def tr(self, key):
        """Функция перевода"""
        return LANGUAGES[self.language].get(key, key)

    def switch_language(self, lang):
        """Переключение языка"""
        self.language = lang
        self.update_ui_texts()

    def update_ui_texts(self):
        """Обновление текста всех элементов интерфейса"""
        self.start_button.configure(text=self.tr("start"))
        self.connection_button.configure(text=self.tr("connection"))
        self.settings_button.configure(text=self.tr("settings"))
        self.help_button.configure(text=self.tr("help"))
        self.database_button.configure(text=self.tr("database"))
        self.logs_button.configure(text=self.tr("logs"))

    def toggle_camera(self):
        """Переключение состояния камеры"""
        if self.camera.running:
            self.stop_camera()
            self.start_button.configure(text="Начать работу", bg="SystemButtonFace", fg="red")
        else:
            self.start_camera()
            self.start_button.configure(text="Остановить работу", bg="red", fg="white")
            logging.info(self.tr("start"))  # Запись в лог

    def start_camera(self):
        """Запуск камеры"""
        self.camera.start()
        self.update_frame()

    def update_frame(self):
        """Обновление кадра"""
        if self.camera.running:
            frame = self.camera.get_frame()
            if frame is not None:
                self.frame = Image.fromarray(frame)
                self.frame = ImageTk.PhotoImage(self.frame)
                self.camera_label.configure(image=self.frame)
                self.camera_label.image = self.frame
            self.root.after(10, self.update_frame)


    def stop_camera(self):
        """Остановка камеры"""
        self.camera.stop()

    def show_connection(self):
        logging.info(self.tr("connection"))  # Запись в лог
        messagebox.showinfo(self.tr("connection"), self.tr("connection_msg"))

    def show_settings(self):
        logging.info(self.tr("settings"))  # Запись в лог
        messagebox.showinfo(self.tr("settings"), self.tr("settings_msg"))

    def show_help(self):
        logging.info(self.tr("help"))  # Запись в лог
        messagebox.showinfo(self.tr("help"), self.tr("help_msg"))

    def open_database(self):
        logging.info(self.tr("database"))  # Запись в лог
        messagebox.showinfo(self.tr("database"), self.tr("database_msg"))

    def open_logs(self):
        logging.info(self.tr("logs"))  # Запись в лог
        log_file = "app.log"
        if not os.path.exists(log_file):
            logging.warning(self.tr("logs_not_found"))
            messagebox.showinfo(self.tr("logs"), self.tr("logs_not_found"))
            return
        try:
            if os.name == 'nt':
                os.startfile(log_file)
            elif os.name == 'posix':
                subprocess.run(["xdg-open", log_file])
            else:
                logging.error(self.tr("os_error"))
                messagebox.showinfo(self.tr("logs"), self.tr("os_error"))
        except Exception as e:
            logging.error(self.tr("logs_error").format(error=str(e)))
            messagebox.showerror(self.tr("logs"), self.tr("logs_error").format(error=str(e)))

    def on_closing(self):
        logging.info(self.tr("closing"))  # Запись в лог
        self.stop_camera()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = CameraApp(root)
    root.mainloop()