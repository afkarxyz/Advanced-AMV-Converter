import sys
import os
import subprocess
from pathlib import Path

if sys.platform == 'win32':
    import ctypes
    from ctypes import wintypes
    
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    
    SW_HIDE = 0
    hWnd = kernel32.GetConsoleWindow()
    if hWnd:
        user32.ShowWindow(hWnd, SW_HIDE)

def get_resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(__file__)
    
    return os.path.join(base_path, relative_path)

def get_ffmpeg_path():
    if getattr(sys, 'frozen', False):
        ffmpeg_path = get_resource_path('ffmpeg.exe')
        ffprobe_path = get_resource_path('ffprobe.exe')
    else:
        ffmpeg_path = 'ffmpeg'
        ffprobe_path = 'ffprobe'
    
    return ffmpeg_path, ffprobe_path

FFMPEG_PATH, FFPROBE_PATH = get_ffmpeg_path()

def run_subprocess(cmd, **kwargs):
    """Helper function to run subprocess with proper Windows flags"""
    default_kwargs = {
        'creationflags': subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
    }
    default_kwargs.update(kwargs)
    return subprocess.Popen(cmd, **default_kwargs)

def run_subprocess_simple(cmd, **kwargs):
    """Helper function to run subprocess.run with proper Windows flags"""
    default_kwargs = {
        'creationflags': subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
    }
    default_kwargs.update(kwargs)
    return subprocess.run(cmd, **default_kwargs)
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QPushButton, QComboBox, 
                            QProgressBar, QTextEdit, QFileDialog, QListWidget,
                            QTabWidget, QRadioButton, QButtonGroup, QMessageBox, QGridLayout, QMenu)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap, QAction, QDragEnterEvent, QDropEvent

class BlackBarWorker(QThread):
    progress_updated = pyqtSignal(int)
    status_updated = pyqtSignal(str)
    conversion_finished = pyqtSignal(bool, str)
    
    def __init__(self, input_files):
        super().__init__()
        self.input_files = input_files
        self.is_running = True
        
    def detect_crop(self, input_file):
        try:
            cmd = [
                FFMPEG_PATH, '-ss', '00:00:01', '-t', '5', '-i', str(input_file),
                '-vf', 'cropdetect', '-an', '-f', 'null', '-'
            ]
            
            process = run_subprocess(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = process.communicate()
            
            crop_lines = [line for line in stderr.split('\n') if 'crop=' in line]
            if crop_lines:
                last_line = crop_lines[-1]
                crop_start = last_line.find('crop=') + 5
                crop_end = last_line.find(' ', crop_start)
                if crop_end == -1:
                    crop_end = len(last_line)
                crop_params = last_line[crop_start:crop_end]
                return crop_params
            
            return None
            
        except Exception as e:
            self.status_updated.emit(f"❌ Crop detection error: {str(e)}")
            return None
    
    def run(self):
        total_files = len(self.input_files)
        
        for i, input_file in enumerate(self.input_files):
            if not self.is_running:
                break
                
            try:
                input_path = Path(input_file)
                self.status_updated.emit(f"Detecting black bars: {input_path.name}")
                
                crop_params = self.detect_crop(input_file)
                
                if crop_params:
                    self.status_updated.emit(f"Detected crop: {crop_params}")
                    
                    cropped_folder = input_path.parent / "Cropped"
                    cropped_folder.mkdir(exist_ok=True)
                    
                    output_file = cropped_folder / input_path.name
                    
                    self.status_updated.emit(f"Removing black bars: {input_path.name}")
                    
                    cmd = [
                        FFMPEG_PATH, '-i', str(input_file),
                        '-vf', f'crop={crop_params}',
                        '-c:a', 'copy',
                        '-y',
                        str(output_file)
                    ]
                    
                    process = run_subprocess(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    
                    stdout, stderr = process.communicate()
                    
                    if process.returncode == 0:
                        self.status_updated.emit(f"✅ Completed: {output_file.name}")
                    else:
                        self.status_updated.emit(f"❌ Failed: {input_path.name}")
                else:
                    self.status_updated.emit(f"⚠️ No black bars detected: {input_path.name}")
                
                progress = int((i + 1) / total_files * 100)
                self.progress_updated.emit(progress)
                
            except Exception as e:
                self.status_updated.emit(f"❌ Error: {str(e)}")
        
        if self.is_running:
            self.conversion_finished.emit(True, "Black bar removal completed!")
        else:
            self.conversion_finished.emit(False, "Black bar removal cancelled")
    
    def stop(self):
        self.is_running = False

class DragDropListWidget(QListWidget):
    files_dropped = pyqtSignal(list)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.original_style = self.styleSheet()
        
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm'}
            has_video = False
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    file_path = url.toLocalFile()
                    if any(file_path.lower().endswith(ext) for ext in video_extensions):
                        has_video = True
                        break
            
            if has_video:
                self.setStyleSheet(self.original_style + """
                    QListWidget {
                        border: 2px dashed #4CAF50;
                        background-color: #E8F5E8;
                    }
                """)
                event.acceptProposedAction()
            else:
                self.setStyleSheet(self.original_style + """
                    QListWidget {
                        border: 2px dashed #F44336;
                        background-color: #FFEBEE;
                    }
                """)
                event.ignore()
        else:
            event.ignore()
        
    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm'}
            has_video = False
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    file_path = url.toLocalFile()
                    if any(file_path.lower().endswith(ext) for ext in video_extensions):
                        has_video = True
                        break
            
            if has_video:
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()
    
    def dragLeaveEvent(self, event):
        self.setStyleSheet(self.original_style)
        super().dragLeaveEvent(event)
            
    def dropEvent(self, event: QDropEvent):
        self.setStyleSheet(self.original_style)
        
        if event.mimeData().hasUrls():
            video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm'}
            video_files = []
            
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    file_path = url.toLocalFile()
                    if any(file_path.lower().endswith(ext) for ext in video_extensions):
                        video_files.append(file_path)
            
            if video_files:
                self.files_dropped.emit(video_files)
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()

class ConversionWorker(QThread):
    progress_updated = pyqtSignal(int)
    ffmpeg_progress_updated = pyqtSignal(int)
    status_updated = pyqtSignal(str)
    conversion_finished = pyqtSignal(bool, str)
    
    def __init__(self, input_files, resolution_filter, fps, block_size):
        super().__init__()
        self.input_files = input_files
        self.resolution_filter = resolution_filter
        self.fps = fps
        self.block_size = block_size
        self.is_running = True
        
    def parse_ffmpeg_progress(self, line):
        if 'time=' in line:
            try:
                time_part = line.split('time=')[1].split()[0]
                time_parts = time_part.split(':')
                if len(time_parts) == 3:
                    hours = float(time_parts[0])
                    minutes = float(time_parts[1])
                    seconds = float(time_parts[2])
                    total_seconds = hours * 3600 + minutes * 60 + seconds
                    return total_seconds
            except:
                pass
        return None
        
    def run(self):
        total_files = len(self.input_files)
        
        for i, input_file in enumerate(self.input_files):
            if not self.is_running:
                break
                
            try:
                input_path = Path(input_file)
                
                amv_folder = input_path.parent / "AMV Converted"
                amv_folder.mkdir(exist_ok=True)
                
                output_file = amv_folder / input_path.with_suffix('.amv').name
                
                self.status_updated.emit(f"Converting: {input_path.name}")
                self.ffmpeg_progress_updated.emit(0)
                
                duration_cmd = [
                    FFPROBE_PATH, '-v', 'quiet', '-show_entries', 'format=duration',
                    '-of', 'csv=p=0', str(input_file)
                ]
                
                try:
                    duration_result = run_subprocess_simple(
                        duration_cmd, 
                        capture_output=True, 
                        text=True
                    )
                    video_duration = float(duration_result.stdout.strip()) if duration_result.stdout.strip() else 0
                except:
                    video_duration = 0
                
                cmd = [
                    FFMPEG_PATH, '-i', str(input_file),
                    '-vf', self.resolution_filter,
                    '-r', str(self.fps),
                    '-b:v', '300k',
                    '-pix_fmt', 'yuvj420p',
                    '-c:v', 'amv',
                    '-ac', '1',
                    '-ar', '22050',
                    '-c:a', 'adpcm_ima_amv',
                    '-block_size', str(self.block_size),
                    '-progress', 'pipe:2',
                    '-y',
                    str(output_file)
                ]
                
                process = run_subprocess(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE, 
                    text=True
                )
                
                while True:
                    if not self.is_running:
                        process.terminate()
                        break
                        
                    line = process.stderr.readline()
                    if not line:
                        break
                        
                    current_time = self.parse_ffmpeg_progress(line)
                    if current_time and video_duration > 0:
                        progress = min(int((current_time / video_duration) * 100), 100)
                        self.ffmpeg_progress_updated.emit(progress)
                
                process.wait()
                
                if process.returncode == 0:
                    self.status_updated.emit(f"✅ Completed: {input_path.name}")
                    self.ffmpeg_progress_updated.emit(100)
                else:
                    self.status_updated.emit(f"❌ Failed: {input_path.name}")
                
                progress = int((i + 1) / total_files * 100)
                self.progress_updated.emit(progress)
                
            except Exception as e:
                self.status_updated.emit(f"❌ Error: {str(e)}")
        
        if self.is_running:
            self.conversion_finished.emit(True, "All conversions completed!")
        else:
            self.conversion_finished.emit(False, "Conversion cancelled")
    
    def stop(self):
        self.is_running = False

class AdvancedAMVConverter(QMainWindow):
    def __init__(self):
        super().__init__()
        self.conversion_worker = None
        self.blackbar_worker = None
        self.input_files = []
        
        self.fps_block_mapping = {
            10: 2205, 11: 2005, 12: 1838, 13: 1696, 14: 1575, 15: 1470,
            16: 1378, 17: 1297, 18: 1225, 19: 1161, 20: 1103, 21: 1050,
            22: 1002, 23: 959, 24: 919, 25: 882, 26: 848, 27: 817,
            28: 788, 29: 760, 30: 735
        }
        
        self.init_ui()
        self.center_window()
        
    def init_ui(self):
        self.setWindowTitle("Advanced AMV Converter")
        self.setFixedSize(400, 300)
        
        icon_path = get_resource_path("icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        self.create_file_selection_tab()
        self.create_settings_tab()
        self.create_progress_tab()
        self.create_about_tab()
        
    def create_file_selection_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(5)
        
        button_layout = QHBoxLayout()
        self.add_files_btn = QPushButton("Add Files")
        self.add_files_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_files_btn.clicked.connect(self.add_files)
        self.clear_files_btn = QPushButton("Clear All")
        self.clear_files_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_files_btn.clicked.connect(self.clear_files)
        
        button_layout.addWidget(self.add_files_btn)
        button_layout.addWidget(self.clear_files_btn)
        layout.addLayout(button_layout)
        
        self.file_list = DragDropListWidget()
        self.file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self.show_context_menu)
        self.file_list.files_dropped.connect(self.handle_dropped_files)
        
        self.update_file_list_placeholder()
        
        layout.addWidget(self.file_list)
        
        control_layout = QHBoxLayout()
        
        self.convert_btn = QPushButton("Convert AMV")
        self.convert_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.convert_btn.clicked.connect(self.start_conversion)
        control_layout.addWidget(self.convert_btn)
        
        self.blackbar_btn = QPushButton("Remove Black Bars")
        self.blackbar_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.blackbar_btn.clicked.connect(self.start_blackbar_removal)
        control_layout.addWidget(self.blackbar_btn)
        
        layout.addLayout(control_layout)
        
        self.tab_widget.addTab(tab, "File Selection")
        
    def create_settings_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)
        
        amv_settings_label = QLabel("<b>AMV Settings</b>")
        amv_settings_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(amv_settings_label)
        
        res_label = QLabel("<b>Resolution</b>")
        layout.addWidget(res_label)
        
        res_layout = QGridLayout()
        self.resolution_group = QButtonGroup()
        self.resolution_radios = {}
        
        resolutions = ["240p", "180p", "176p", "160p", "144p", "128p", "120p", "96p"]
        for i, res in enumerate(resolutions):
            radio = QRadioButton(res)
            radio.setCursor(Qt.CursorShape.PointingHandCursor)
            self.resolution_radios[res] = radio
            self.resolution_group.addButton(radio, i)
            
            row = i // 4
            col = i % 4
            res_layout.addWidget(radio, row, col)
        
        self.resolution_radios["240p"].setChecked(True)
        layout.addLayout(res_layout)
        
        scale_label = QLabel("<b>Scale Type</b>")
        layout.addWidget(scale_label)
        
        scale_layout = QHBoxLayout()
        self.scale_group = QButtonGroup()
        
        self.preserved_radio = QRadioButton("Preserved")
        self.preserved_radio.setToolTip("Width auto-calculated based on aspect ratio")
        self.preserved_radio.setChecked(True)
        self.preserved_radio.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.forced_radio = QRadioButton("Forced")
        self.forced_radio.setToolTip("Direct resize to exact resolution")
        self.forced_radio.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.crop_radio = QRadioButton("Crop")
        self.crop_radio.setToolTip("Resize then crop to exact resolution")
        self.crop_radio.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.scale_group.addButton(self.preserved_radio, 0)
        self.scale_group.addButton(self.forced_radio, 1)
        self.scale_group.addButton(self.crop_radio, 2)
        
        scale_layout.addWidget(self.preserved_radio)
        scale_layout.addWidget(self.forced_radio)
        scale_layout.addWidget(self.crop_radio)
        layout.addLayout(scale_layout)
        
        fps_label = QLabel("<b>Frame Rate (FPS)</b>")
        layout.addWidget(fps_label)
        
        self.fps_combo = QComboBox()
        self.fps_combo.setMaximumWidth(80)
        self.fps_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        fps_values = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30]
        for fps in fps_values:
            self.fps_combo.addItem(str(fps))
        
        self.fps_combo.setCurrentText("15")
        layout.addWidget(self.fps_combo)
        
        layout.addStretch()
        
        self.tab_widget.addTab(tab, "Settings")
        
    def create_progress_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(5)
        
        self.file_progress_label = QLabel("File Progress:")
        self.file_progress_label.setVisible(False)
        layout.addWidget(self.file_progress_label)
        
        self.file_progress_bar = QProgressBar()
        self.file_progress_bar.setVisible(False)
        layout.addWidget(self.file_progress_bar)
        
        self.ffmpeg_progress_label = QLabel("Current File Progress:")
        self.ffmpeg_progress_label.setVisible(False)
        layout.addWidget(self.ffmpeg_progress_label)
        
        self.ffmpeg_progress_bar = QProgressBar()
        self.ffmpeg_progress_bar.setVisible(False)
        layout.addWidget(self.ffmpeg_progress_bar)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)
        
        stop_layout = QHBoxLayout()
        stop_layout.addStretch()
        
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_btn.setFixedWidth(150)
        self.stop_btn.clicked.connect(self.stop_conversion)
        self.stop_btn.setEnabled(False)
        stop_layout.addWidget(self.stop_btn)
        
        stop_layout.addStretch()
        layout.addLayout(stop_layout)
        
        self.tab_widget.addTab(tab, "Progress")
        
    def create_about_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)
        
        icon_png_path = get_resource_path("icon.png")
        if os.path.exists(icon_png_path):
            icon_label = QLabel()
            pixmap = QPixmap(icon_png_path)
            scaled_pixmap = pixmap.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            icon_label.setPixmap(scaled_pixmap)
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(icon_label)
        
        about_text = QLabel("""
<h3>Advanced AMV Converter</h3>
<p><b>Version:</b> 1.0</p>

<p><b>Supported Input Formats:</b><br>
MP4, AVI, MOV, MKV, FLV, WMV, WEBM</p>

<p><b>GitHub:</b><br>
<a href="https://github.com/afkarxyz/Advanced-AMV-Converter">https://github.com/afkarxyz/Advanced-AMV-Converter</a></p>
        """)
        about_text.setWordWrap(True)
        about_text.setAlignment(Qt.AlignmentFlag.AlignTop)
        about_text.setOpenExternalLinks(True)
        layout.addWidget(about_text)
        
        layout.addStretch()
        
        self.tab_widget.addTab(tab, "About")
        
    def center_window(self):
        screen = QApplication.primaryScreen().geometry()
        window = self.geometry()
        x = (screen.width() - window.width()) // 2
        y = (screen.height() - window.height()) // 2
        self.move(x, y)
        
    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Video Files",
            "",
            "Video Files (*.mp4 *.avi *.mov *.mkv *.flv *.wmv *.webm);;All Files (*)"
        )
        
        if files:
            for file in files:
                if file not in self.input_files:
                    self.input_files.append(file)
                    if (self.file_list.count() > 0 and 
                        self.file_list.item(0) and 
                        self.file_list.item(0).text().startswith("📁")):
                        self.file_list.takeItem(0)
                    self.file_list.addItem(Path(file).name)
                    
            self.log_text.append(f"Added {len(files)} file(s)")
            self.update_file_list_placeholder()
    
    def handle_dropped_files(self, files):
        added_count = 0
        for file in files:
            if file not in self.input_files:
                self.input_files.append(file)
                self.file_list.addItem(Path(file).name)
                added_count += 1
        
        if added_count > 0:
            self.log_text.append(f"Dropped {added_count} file(s)")
        else:
            self.log_text.append("No new files added (duplicates ignored)")
        
        self.update_file_list_placeholder()
    
    def update_file_list_placeholder(self):
        if self.file_list.count() == 0:
            placeholder_item = self.file_list.addItem("📁 Drag & drop video files here or click 'Add Files'")
            item = self.file_list.item(0)
            if item:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        else:
            if (self.file_list.count() > 0 and 
                self.file_list.item(0) and 
                self.file_list.item(0).text().startswith("📁")):
                self.file_list.takeItem(0)
        
    def clear_files(self):
        self.input_files.clear()
        self.file_list.clear()
        self.log_text.append("Cleared all files")
        self.update_file_list_placeholder()
    
    def show_context_menu(self, position):
        item = self.file_list.itemAt(position)
        if item is not None and not item.text().startswith("📁"):
            context_menu = QMenu(self)
            delete_action = QAction("Delete", self)
            delete_action.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_TrashIcon))
            delete_action.triggered.connect(self.delete_selected_file)
            context_menu.addAction(delete_action)
            context_menu.exec(self.file_list.mapToGlobal(position))
    
    def delete_selected_file(self):
        current_row = self.file_list.currentRow()
        if current_row >= 0:
            item = self.file_list.item(current_row)
            if item and item.text().startswith("📁"):
                return
            
            item = self.file_list.takeItem(current_row)
            if current_row < len(self.input_files):
                removed_file = self.input_files.pop(current_row)
                self.log_text.append(f"Removed: {Path(removed_file).name}")
                self.update_file_list_placeholder()
        
    def start_conversion(self):
        if not self.input_files:
            QMessageBox.warning(self, "Warning", "Please add video files first!")
            return
            
        selected_resolution = None
        for res, radio in self.resolution_radios.items():
            if radio.isChecked():
                selected_resolution = res.replace('p', '')
                break
        
        scale_type = None
        if self.preserved_radio.isChecked():
            scale_type = "Preserved"
        elif self.forced_radio.isChecked():
            scale_type = "Forced"
        elif self.crop_radio.isChecked():
            scale_type = "Crop"
        
        selected_fps = int(self.fps_combo.currentText())
        
        resolution_filter = self.build_resolution_filter(selected_resolution, scale_type)
        block_size = self.fps_block_mapping.get(selected_fps, 1470)
        
        self.tab_widget.setCurrentIndex(2)
        
        self.convert_btn.setEnabled(False)
        self.blackbar_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        
        if len(self.input_files) == 1:
            self.file_progress_label.setVisible(False)
            self.file_progress_bar.setVisible(False)
            self.ffmpeg_progress_label.setVisible(True)
            self.ffmpeg_progress_bar.setVisible(True)
            self.ffmpeg_progress_bar.setValue(0)
        else:
            self.file_progress_label.setVisible(True)
            self.file_progress_bar.setVisible(True)
            self.file_progress_bar.setValue(0)
            self.ffmpeg_progress_label.setVisible(True)
            self.ffmpeg_progress_bar.setVisible(True)
            self.ffmpeg_progress_bar.setValue(0)
        
        self.log_text.clear()
        self.log_text.append(f"Starting conversion of {len(self.input_files)} file(s)")
        self.log_text.append(f"Resolution: {selected_resolution}p ({scale_type})")
        self.log_text.append(f"FPS: {selected_fps}")
        self.log_text.append("-" * 50)
        
        self.conversion_worker = ConversionWorker(
            self.input_files, resolution_filter, selected_fps, block_size
        )
        self.conversion_worker.progress_updated.connect(self.update_progress)
        self.conversion_worker.ffmpeg_progress_updated.connect(self.update_ffmpeg_progress)
        self.conversion_worker.status_updated.connect(self.update_status)
        self.conversion_worker.conversion_finished.connect(self.conversion_finished)
        self.conversion_worker.start()
    
    def build_resolution_filter(self, resolution, scale_type):
        height = resolution
        
        if scale_type == "Preserved":
            return f"scale=-2:{height}"
        elif scale_type == "Forced":
            width_mapping = {
                "240": "320", "180": "240", "176": "208", "160": "208", 
                "144": "176", "128": "176", "120": "160", "96": "128"
            }
            width = width_mapping.get(height, "320")
            return f"scale={width}:{height}"
        elif scale_type == "Crop":
            width_mapping = {
                "240": "320", "180": "240", "176": "208", "160": "208", 
                "144": "176", "128": "176", "120": "160", "96": "128"
            }
            width = width_mapping.get(height, "320")
            return f"scale=-2:{height},crop={width}:{height}"
        
        return f"scale=-2:{height}"
        
    def start_blackbar_removal(self):
        if not self.input_files:
            QMessageBox.warning(self, "Warning", "Please add video files first!")
            return
            
        self.tab_widget.setCurrentIndex(2)
        
        self.convert_btn.setEnabled(False)
        self.blackbar_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        
        self.file_progress_label.setVisible(True)
        self.file_progress_bar.setVisible(True)
        self.file_progress_bar.setValue(0)
        
        self.ffmpeg_progress_label.setVisible(False)
        self.ffmpeg_progress_bar.setVisible(False)
        
        self.log_text.clear()
        self.log_text.append(f"Starting black bar removal for {len(self.input_files)} file(s)")
        self.log_text.append("-" * 50)
        
        self.blackbar_worker = BlackBarWorker(self.input_files)
        self.blackbar_worker.progress_updated.connect(self.update_progress)
        self.blackbar_worker.status_updated.connect(self.update_status)
        self.blackbar_worker.conversion_finished.connect(self.conversion_finished)
        self.blackbar_worker.start()
    
    def stop_conversion(self):
        if self.conversion_worker:
            self.conversion_worker.stop()
            self.conversion_worker.wait()
        
        if self.blackbar_worker:
            self.blackbar_worker.stop()
            self.blackbar_worker.wait()
            
        self.conversion_finished(False, "Process stopped by user")
        
    def update_progress(self, value):
        self.file_progress_bar.setValue(value)
        
        if len(self.input_files) == 1 and value > 0 and self.conversion_worker:
            if not self.ffmpeg_progress_bar.isVisible():
                self.ffmpeg_progress_label.setVisible(True)
                self.ffmpeg_progress_bar.setVisible(True)
        
    def update_ffmpeg_progress(self, value):
        self.ffmpeg_progress_bar.setValue(value)
        
    def update_status(self, message):
        self.log_text.append(message)
        
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
    def conversion_finished(self, success, message):
        self.convert_btn.setEnabled(True)
        self.blackbar_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        
        if success:
            self.file_progress_bar.setValue(100)
            if self.ffmpeg_progress_bar.isVisible():
                self.ffmpeg_progress_bar.setValue(100)
            
        self.log_text.append("-" * 50)
        self.log_text.append(message)
        
        self.file_progress_label.setVisible(False)
        self.file_progress_bar.setVisible(False)
        self.ffmpeg_progress_label.setVisible(False)
        self.ffmpeg_progress_bar.setVisible(False)

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    window = AdvancedAMVConverter()
    window.show()
    
    sys.exit(app.exec())

if __name__ == '__main__':
    main()