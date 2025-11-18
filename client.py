# Configurer Kivy pour gérer le clic droit
from kivy.config import Config
Config.set('input', 'mouse', 'mouse,multitouch_on_demand')

import socket
import struct
import io
import threading
import ssl
import os
import json
from tkinter import Tk, filedialog
from kivy.app import App
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.uix.image import Image
from kivy.graphics.texture import Texture
from kivy.clock import Clock
from kivy.core.image import Image as CoreImage
from kivy.core.window import Window
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.uix.slider import Slider
from kivy.uix.progressbar import ProgressBar
from kivy.uix.scrollview import ScrollView
from kivy.properties import StringProperty, BooleanProperty
from os.path import expanduser

# --- KV String for the file browser row ---
Builder.load_string('''
<FileEntryWidget>:
    orientation: 'horizontal'
    padding: dp(5)
    spacing: dp(10)
    size_hint_y: None
    height: dp(40)
    canvas.before:
        Color:
            rgba: (0.2, 0.6, 0.8, 0.5) if self.is_selected else (0.15, 0.15, 0.15, 1)
        Rectangle:
            pos: self.pos
            size: self.size
    Label:
        text: '[D]' if root.is_dir else '[F]'
        size_hint_x: None
        width: dp(30)
    Label:
        text: root.name
        halign: 'left'
        valign: 'middle'
        text_size: self.width, None
        shorten: True
        shorten_from: 'right'
    Label:
        text: root.file_size
        size_hint_x: None
        width: dp(80)
        halign: 'right'
        valign: 'middle'
        text_size: self.width, None
''')

# --- Fonctions utilitaires pour la taille des fichiers ---
def sizeof_fmt(num, suffix="B"):
    for unit in ["", "K", "M", "G", "T", "P", "E", "Z"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Y{suffix}"

class RemoteDesktopWidget(Image):
    def __init__(self, **kwargs):
        super(RemoteDesktopWidget, self).__init__(**kwargs)
        self.client_socket = None
        self.pressed_keys = set()
        self._keyboard = None
        self.server_resolution = (1, 1)

    def setup_keyboard(self):
        if not self._keyboard:
            self._keyboard = Window.request_keyboard(self._keyboard_closed, self)
            self._keyboard.bind(on_key_down=self._on_key_down)
            self._keyboard.bind(on_key_up=self._on_key_up)

    def release_keyboard(self):
        if self._keyboard:
            self._keyboard.unbind(on_key_down=self._on_key_down)
            self._keyboard.unbind(on_key_up=self._on_key_up)
            self._keyboard.release()
            self._keyboard = None

    def _keyboard_closed(self): self.release_keyboard()
    def _on_key_down(self, k, kc, t, m):
        if kc[1] and kc[1] not in self.pressed_keys:
            self.pressed_keys.add(kc[1]); self.send_command(f"KP,{kc[1]}")
        return True
    def _on_key_up(self, k, kc):
        if kc[1] and kc[1] in self.pressed_keys:
            self.pressed_keys.remove(kc[1]); self.send_command(f"KR,{kc[1]}")
        return True

    def _get_scaled_coords(self, touch):
        app = App.get_running_app()
        if not hasattr(app, 'tab_panel') or not hasattr(app, 'desktop_tab'):
            return -1, -1
        if app.tab_panel.current_tab != app.desktop_tab:
            return -1, -1

        if not self.texture or self.norm_image_size[0] == 0: return -1, -1
        img_x = self.center_x - self.norm_image_size[0] / 2
        img_y = self.center_y - self.norm_image_size[1] / 2
        if not (img_x <= touch.x < img_x + self.norm_image_size[0] and \
                img_y <= touch.y < img_y + self.norm_image_size[1]):
            return -1, -1
        relative_x = (touch.x - img_x) / self.norm_image_size[0]
        relative_y = (touch.y - img_y) / self.norm_image_size[1]
        server_x = int(relative_x * self.server_resolution[0])
        server_y = int((1 - relative_y) * self.server_resolution[1])
        return server_x, server_y

    def _get_mapped_button_name(self, kivy_button_name):
        return kivy_button_name

    def on_touch_down(self, touch):
        x, y = self._get_scaled_coords(touch)
        if x != -1:
            if touch.is_mouse_scrolling:
                self.send_command(f"SCROLL,0,{int(touch.scroll_y)}")
                return True
            self.send_command(f"MV,{x},{y}")
            touch.ud['initial_pos'] = touch.pos
            mapped_button = self._get_mapped_button_name(touch.button)
            self.send_command(f"MC,{mapped_button},1")
            return True
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        x, y = self._get_scaled_coords(touch)
        if x != -1:
            mapped_button = self._get_mapped_button_name(touch.button)
            if mapped_button == 'left' and touch.is_double_tap:
                self.send_command(f"DBLCLICK,{x},{y},{mapped_button}")
            else:
                self.send_command(f"MC,{mapped_button},0")
            return True
        return super().on_touch_up(touch)

    def on_touch_move(self, touch):
        x, y = self._get_scaled_coords(touch)
        if x != -1:
            self.send_command(f"MV,{x},{y}")
            return True
        return super().on_touch_move(touch)

    def send_command(self, command_str):
        if self.client_socket:
            try:
                command_bytes = command_str.encode('utf-8')
                len_info = struct.pack("!H", len(command_bytes))
                self.client_socket.sendall(len_info + command_bytes)
            except (BrokenPipeError, ConnectionResetError): pass

class FileEntryWidget(BoxLayout):
    name = StringProperty('')
    file_size = StringProperty('')
    is_dir = BooleanProperty(False)
    is_selected = BooleanProperty(False)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            if touch.is_double_tap:
                App.get_running_app().on_file_selection(self.name, self.is_dir)
            else:
                for widget in self.parent.children:
                    widget.is_selected = False
                self.is_selected = True
            return True
        return super().on_touch_down(touch)

class RemoteViewerApp(App):
    def build(self):
        self.sm = ScreenManager()
        connect_screen = Screen(name='connect')
        layout = BoxLayout(orientation='vertical', padding=30, spacing=10)
        grid = GridLayout(cols=2, spacing=10, size_hint_y=None, height=100)
        grid.add_widget(Label(text='Adresse IP:'))
        self.ip_input = TextInput(text='127.0.0.1', multiline=False)
        grid.add_widget(self.ip_input)
        grid.add_widget(Label(text='Port:'))
        self.port_input = TextInput(text='9999', multiline=False)
        grid.add_widget(self.port_input)
        self.status_label = Label(text='', size_hint_y=None, height=40)
        connect_button = Button(text='Se connecter', on_press=self.connect_to_server)
        layout.add_widget(grid)
        layout.add_widget(connect_button)
        layout.add_widget(self.status_label)
        connect_screen.add_widget(layout)

        remote_screen = Screen(name='remote')
        self.tab_panel = TabbedPanel(do_default_tab=False)
        
        self.desktop_tab = TabbedPanelItem(text='Bureau')
        self.remote_widget = RemoteDesktopWidget()
        self.desktop_tab.add_widget(self.remote_widget)
        self.tab_panel.add_widget(self.desktop_tab)

        settings_tab = TabbedPanelItem(text='Paramètres')
        settings_layout = BoxLayout(orientation='vertical', padding=20, spacing=10)
        quality_label = Label(text='Qualité de l\'image: 70%', size_hint_y=None, height=40)
        quality_slider = Slider(min=10, max=95, value=70, step=5)
        quality_slider.bind(value=lambda i, v: self.send_quality_setting(int(v)))
        settings_layout.add_widget(quality_label)
        settings_layout.add_widget(quality_slider)
        settings_tab.add_widget(settings_layout)
        self.tab_panel.add_widget(settings_tab)

        self.transfer_tab = TabbedPanelItem(text='Transferts')
        transfer_layout = BoxLayout(orientation='vertical', padding=20, spacing=10)
        self.transfer_status_label = Label(text='Prêt.', size_hint_y=None, height=40)
        self.transfer_progress_bar = ProgressBar(max=100, size_hint_y=None, height=20)
        
        transfer_buttons = BoxLayout(size_hint_y=None, height=40, spacing=5)
        send_file_button = Button(text='Envoyer un fichier...', on_press=self.choose_and_upload_file)
        self.cancel_button = Button(text='Annuler', on_press=self.cancel_transfer)
        self.cancel_button.disabled = True
        transfer_buttons.add_widget(send_file_button)
        transfer_buttons.add_widget(self.cancel_button)

        transfer_layout.add_widget(self.transfer_status_label)
        transfer_layout.add_widget(self.transfer_progress_bar)
        transfer_layout.add_widget(transfer_buttons)
        self.transfer_tab.add_widget(transfer_layout)
        self.tab_panel.add_widget(self.transfer_tab)

        download_tab = TabbedPanelItem(text='Fichiers Distants')
        download_layout = BoxLayout(orientation='vertical', padding=10, spacing=5)
        self.remote_path_label = Label(text='/', size_hint_y=None, height=30)
        
        button_layout = BoxLayout(size_hint_y=None, height=40, spacing=5)
        up_button = Button(text='..', on_press=self.go_up_dir)
        refresh_button = Button(text='Actualiser', on_press=lambda i: self.list_remote_dir(self.current_remote_path))
        button_layout.add_widget(up_button)
        button_layout.add_widget(refresh_button)

        self.file_browser_grid = GridLayout(cols=1, size_hint_y=None)
        self.file_browser_grid.bind(minimum_height=self.file_browser_grid.setter('height'))
        scroll_view = ScrollView()
        scroll_view.add_widget(self.file_browser_grid)
        
        download_layout.add_widget(button_layout)
        download_layout.add_widget(self.remote_path_label)
        download_layout.add_widget(scroll_view)
        download_tab.add_widget(download_layout)
        self.tab_panel.add_widget(download_tab)
        
        self.tab_panel.default_tab = self.desktop_tab
        remote_screen.add_widget(self.tab_panel)

        self.sm.add_widget(connect_screen)
        self.sm.add_widget(remote_screen)
        
        self.current_remote_path = ""
        self.cancel_transfer_flag = threading.Event()
        return self.sm

    def cancel_transfer(self, instance):
        self.cancel_transfer_flag.set()

    def on_file_selection(self, filename, is_dir):
        if self.current_remote_path == "" and not filename.endswith(':\\'):
             full_path = os.path.join(self.current_remote_path, filename).replace('\\', '/')
        else:
             full_path = filename if self.current_remote_path == "" else os.path.join(self.current_remote_path, filename).replace('\\', '/')

        if is_dir:
            self.list_remote_dir(full_path)
        else:
            self.choose_and_download_file(full_path, filename)

    def go_up_dir(self, instance):
        if not self.current_remote_path or not os.path.dirname(self.current_remote_path) == self.current_remote_path:
            parent_path = os.path.dirname(self.current_remote_path).replace('\\', '/')
        else:
            parent_path = ""
        self.list_remote_dir(parent_path)

    def list_remote_dir(self, path):
        self.transfer_status_label.text = f"Chargement de /{path}..."
        threading.Thread(target=self._list_remote_dir_thread, args=(path,), daemon=True).start()

    def _list_remote_dir_thread(self, path):
        try:
            host, file_port = self.ip_input.text, int(self.port_input.text) - 1
            header_str = f"LIST_DIR,{path}"
            header_bytes = header_str.encode('utf-8')
            len_info = struct.pack("!H", len(header_bytes))
            context = ssl.create_default_context(); context.check_hostname = False; context.verify_mode = ssl.CERT_NONE
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                secure_sock = context.wrap_socket(sock, server_hostname=host)
                secure_sock.connect((host, file_port))
                secure_sock.sendall(len_info + header_bytes)
                len_info = self.recv_all(secure_sock, 4)
                if not len_info: return
                payload_size = struct.unpack("!I", len_info)[0]
                payload = self.recv_all(secure_sock, payload_size)
                data = json.loads(payload.decode('utf-8'))
                Clock.schedule_once(lambda dt: self.update_file_browser(data))
        except Exception as e: 
            print(f"Erreur listage: {e}")
            Clock.schedule_once(lambda dt: setattr(self.transfer_status_label, 'text', f"Erreur: {e}"))

    def update_file_browser(self, data):
        if 'error' in data and data['error']:
            self.transfer_status_label.text = f"Erreur distante: {data['error']}"
        else:
            self.transfer_status_label.text = "Prêt."
        
        self.current_remote_path = data.get('path', self.current_remote_path)
        self.remote_path_label.text = f"/{self.current_remote_path}"
        
        self.file_browser_grid.clear_widgets()
        for entry in data.get('entries', []):
            widget = FileEntryWidget(
                name=entry['name'],
                is_dir=entry['is_dir'],
                file_size="" if entry['is_dir'] else sizeof_fmt(entry.get('size', 0))
            )
            self.file_browser_grid.add_widget(widget)

    def choose_and_upload_file(self, instance):
        Tk().withdraw() 
        file_path = filedialog.askopenfilename(title="Choisir un fichier à envoyer", initialdir=expanduser("~"))
        if file_path:
            self.tab_panel.switch_to(self.transfer_tab)
            self.cancel_transfer_flag.clear()
            threading.Thread(target=self._upload_file_thread, args=(file_path,), daemon=True).start()

    def _upload_file_thread(self, file_path):
        def update_status(text): Clock.schedule_once(lambda dt: setattr(self.transfer_status_label, 'text', text))
        def update_progress(value): Clock.schedule_once(lambda dt: setattr(self.transfer_progress_bar, 'value', value))
        
        Clock.schedule_once(lambda dt: setattr(self.cancel_button, 'disabled', False))
        try:
            filename, filesize = os.path.basename(file_path), os.path.getsize(file_path)
            update_status(f"Envoi de {filename}..."); update_progress(0)
            header_str = f"UPLOAD,{filename},{filesize}"
            header_bytes = header_str.encode('utf-8')
            len_info = struct.pack("!H", len(header_bytes))
            host, file_port = self.ip_input.text, int(self.port_input.text) - 1
            context = ssl.create_default_context(); context.check_hostname = False; context.verify_mode = ssl.CERT_NONE
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                secure_sock = context.wrap_socket(sock, server_hostname=host)
                secure_sock.connect((host, file_port))
                secure_sock.sendall(len_info + header_bytes)
                with open(file_path, 'rb') as f:
                    bytes_sent = 0
                    while True:
                        if self.cancel_transfer_flag.is_set():
                            update_status("Envoi annulé."); update_progress(0)
                            return
                        chunk = f.read(65536)
                        if not chunk: break
                        secure_sock.sendall(chunk)
                        bytes_sent += len(chunk)
                        update_progress((bytes_sent / filesize) * 100)
                secure_sock.settimeout(10)
                response = secure_sock.recv(1024)
                if response == b"OK": update_status(f"'{filename}' envoyé!"); update_progress(100)
                else: update_status(f"Erreur: {response.decode('utf-8', 'ignore')}"); update_progress(0)
        except Exception as e:
            if not self.cancel_transfer_flag.is_set():
                update_status(f"Erreur: {e}"); update_progress(0)
        finally:
            Clock.schedule_once(lambda dt: setattr(self.cancel_button, 'disabled', True))
            self.cancel_transfer_flag.clear()

    def choose_and_download_file(self, remote_path, filename):
        Tk().withdraw()
        save_path = filedialog.asksaveasfilename(title="Enregistrer le fichier sous...", initialdir=expanduser("~"), initialfile=filename)
        if save_path:
            self.tab_panel.switch_to(self.transfer_tab)
            self.cancel_transfer_flag.clear()
            threading.Thread(target=self._download_file_thread, args=(remote_path, save_path), daemon=True).start()

    def _download_file_thread(self, remote_path, save_path):
        def update_status(text): Clock.schedule_once(lambda dt: setattr(self.transfer_status_label, 'text', text))
        def update_progress(value): Clock.schedule_once(lambda dt: setattr(self.transfer_progress_bar, 'value', value))

        Clock.schedule_once(lambda dt: setattr(self.cancel_button, 'disabled', False))
        try:
            update_status(f"Téléchargement de {os.path.basename(remote_path)}..."); update_progress(0)
            host, file_port = self.ip_input.text, int(self.port_input.text) - 1
            header_str = f"DOWNLOAD,{remote_path}"
            header_bytes = header_str.encode('utf-8')
            len_info = struct.pack("!H", len(header_bytes))
            context = ssl.create_default_context(); context.check_hostname = False; context.verify_mode = ssl.CERT_NONE
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                secure_sock = context.wrap_socket(sock, server_hostname=host)
                secure_sock.connect((host, file_port))
                secure_sock.sendall(len_info + header_bytes)
                
                response_header = self.recv_all(secure_sock, 8)
                if not response_header:
                    update_status("Erreur: Pas de réponse du serveur."); update_progress(0)
                    return

                try:
                    filesize = struct.unpack("!Q", response_header)[0]
                except struct.error:
                    error_msg = response_header.decode('utf-8', 'ignore')
                    update_status(f"Erreur du serveur: {error_msg}"); update_progress(0)
                    return

                if filesize == 0:
                    update_status("Erreur: Fichier non trouvé ou vide."); update_progress(0)
                    return
                    
                bytes_received = 0
                with open(save_path, 'wb') as f:
                    while bytes_received < filesize:
                        if self.cancel_transfer_flag.is_set():
                            update_status("Téléchargement annulé.")
                            update_progress(0)
                            return
                        
                        chunk_size = min(65536, filesize - bytes_received)
                        chunk = secure_sock.recv(chunk_size)
                        if not chunk:
                            if bytes_received < filesize:
                                update_status("Erreur: Connexion perdue pendant le téléchargement.")
                            break
                        f.write(chunk)
                        bytes_received += len(chunk)
                        update_progress((bytes_received / filesize) * 100)

                if self.cancel_transfer_flag.is_set():
                    if os.path.exists(save_path):
                        os.remove(save_path)
                elif bytes_received == filesize:
                    update_status(f"Téléchargé: {os.path.basename(save_path)}"); update_progress(100)
                else:
                    update_status("Erreur de téléchargement inattendue."); update_progress(0)
                    if os.path.exists(save_path):
                        os.remove(save_path)

        except Exception as e:
            if not self.cancel_transfer_flag.is_set():
                update_status(f"Erreur: {e}"); update_progress(0)
        finally:
            Clock.schedule_once(lambda dt: setattr(self.cancel_button, 'disabled', True))
            self.cancel_transfer_flag.clear()

    def send_quality_setting(self, quality_value): self.remote_widget.send_command(f"QUALITY,{quality_value}")

    def connect_to_server(self, instance):
        host, port = self.ip_input.text, int(self.port_input.text)
        self.status_label.text = f"Connexion à {host}:{port}..."
        threading.Thread(target=self.receive_frames, args=(host, port), daemon=True).start()
        Clock.schedule_once(lambda dt: self.list_remote_dir(""), 2)

    def receive_frames(self, host, port):
        context = ssl.create_default_context(); context.check_hostname = False; context.verify_mode = ssl.CERT_NONE
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket = context.wrap_socket(sock, server_hostname=host)
            client_socket.connect((host, port))
            self.remote_widget.client_socket = client_socket
            self.send_quality_setting(70)
            Clock.schedule_once(self.switch_to_remote_screen)
        except Exception as e: Clock.schedule_once(lambda dt, err=str(e): self.show_connection_error(err))
        else:
            while True:
                try:
                    len_info = self.recv_all(self.remote_widget.client_socket, 4)
                    if not len_info: break
                    payload_size = struct.unpack("!I", len_info)[0]
                    payload = self.recv_all(self.remote_widget.client_socket, payload_size)
                    if not payload: break
                    width, height = struct.unpack("!II", payload[:struct.calcsize("!II")])
                    self.remote_widget.server_resolution = (width, height)
                    Clock.schedule_once(lambda dt, data=payload[struct.calcsize("!II"):]: self.update_image(data))
                except (ConnectionResetError, BrokenPipeError): break
            if self.remote_widget.client_socket:
                self.remote_widget.client_socket.close(); self.remote_widget.client_socket = None
            Clock.schedule_once(self.switch_to_connect_screen)

    def switch_to_remote_screen(self, dt): self.sm.current = 'remote'; self.remote_widget.setup_keyboard()
    def switch_to_connect_screen(self, dt): self.remote_widget.release_keyboard(); self.status_label.text = "Déconnecté."; self.sm.current = 'connect'
    def show_connection_error(self, error_msg): self.status_label.text = f"Échec: {error_msg}"

    def recv_all(self, sock, n):
        data = bytearray()
        while len(data) < n:
            if sock is None: return None
            try:
                packet = sock.recv(n - len(data))
                if not packet: return None
                data.extend(packet)
            except (socket.error, AttributeError): return None
        return data

    def update_image(self, jpeg_bytes):
        buf = io.BytesIO(jpeg_bytes)
        core_image = CoreImage(buf, ext='jpg')
        self.remote_widget.texture = core_image.texture

if __name__ == '__main__':
    RemoteViewerApp().run()
