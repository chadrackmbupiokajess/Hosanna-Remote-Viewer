# Configurer Kivy pour gérer le clic droit
from kivy.config import Config
Config.set('input', 'mouse', 'mouse,multitouch_on_demand')

import socket
import struct
import io
import threading
import ssl
import os
from tkinter import Tk
from tkinter.filedialog import askopenfilename
from kivy.app import App
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
from os.path import expanduser

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
        
        def on_quality_change(instance, value):
            quality_label.text = f"Qualité de l'image: {int(value)}%"
            self.send_quality_setting(int(value))

        quality_slider.bind(value=on_quality_change)
        settings_layout.add_widget(quality_label)
        settings_layout.add_widget(quality_slider)
        settings_tab.add_widget(settings_layout)
        self.tab_panel.add_widget(settings_tab)

        file_tab = TabbedPanelItem(text='Fichiers')
        file_layout = BoxLayout(orientation='vertical', padding=20, spacing=10)
        self.file_status_label = Label(text='Prêt pour le transfert.', size_hint_y=None, height=40)
        
        # --- NOUVEAU: Barre de progression ---
        self.progress_bar = ProgressBar(max=100, size_hint_y=None, height=20)
        
        open_explorer_button = Button(text="Ouvrir l'explorateur distant", on_press=self.open_remote_explorer)
        send_file_button = Button(text='Envoyer un fichier au serveur', on_press=self.open_file_chooser)
        
        file_layout.add_widget(self.file_status_label)
        file_layout.add_widget(self.progress_bar) # Ajout de la barre
        file_layout.add_widget(open_explorer_button)
        file_layout.add_widget(send_file_button)
        file_tab.add_widget(file_layout)
        self.tab_panel.add_widget(file_tab)

        self.tab_panel.default_tab = self.desktop_tab
        remote_screen.add_widget(self.tab_panel)

        self.sm.add_widget(connect_screen)
        self.sm.add_widget(remote_screen)
        return self.sm

    def open_remote_explorer(self, instance):
        self.remote_widget.send_command("OPEN_EXPLORER,")
        self.tab_panel.switch_to(self.desktop_tab)

    def open_file_chooser(self, instance):
        Tk().withdraw() 
        file_path = askopenfilename(
            title="Choisissez un fichier à envoyer",
            initialdir=expanduser("~")
        )
        if file_path:
            threading.Thread(target=self._send_file_thread, args=(file_path,), daemon=True).start()

    def _send_file_thread(self, file_path):
        def update_status(text):
            Clock.schedule_once(lambda dt: setattr(self.file_status_label, 'text', text))
        
        # --- NOUVEAU: Fonction pour mettre à jour la barre de progression ---
        def update_progress(value):
            Clock.schedule_once(lambda dt: setattr(self.progress_bar, 'value', value))

        try:
            filename = os.path.basename(file_path)
            filesize = os.path.getsize(file_path)
            
            update_status(f"Envoi de {filename}...")
            update_progress(0)

            header_str = f"FILE_TRANSFER,{filename},{filesize}"
            header_bytes = header_str.encode('utf-8')
            len_info = struct.pack("!H", len(header_bytes))
            
            host = self.ip_input.text
            file_port = int(self.port_input.text) - 1 

            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as file_socket:
                secure_file_socket = context.wrap_socket(file_socket, server_hostname=host)
                secure_file_socket.connect((host, file_port))
                
                secure_file_socket.sendall(len_info + header_bytes)

                with open(file_path, 'rb') as f:
                    bytes_sent = 0
                    while True:
                        chunk = f.read(4096)
                        if not chunk:
                            break
                        secure_file_socket.sendall(chunk)
                        # --- NOUVEAU: Mise à jour de la progression ---
                        bytes_sent += len(chunk)
                        progress = (bytes_sent / filesize) * 100
                        update_progress(progress)
                
                secure_file_socket.settimeout(10)
                response = secure_file_socket.recv(1024)
                if response == b"OK":
                    update_status(f"'{filename}' envoyé avec succès!")
                    update_progress(100)
                else:
                    update_status(f"Erreur du serveur: {response.decode('utf-8', 'ignore')}")
                    update_progress(0)

        except socket.timeout:
            update_status("Erreur: Le serveur n'a pas répondu.")
            update_progress(0)
        except Exception as e:
            update_status(f"Erreur: {e}")
            update_progress(0)

    def send_quality_setting(self, quality_value):
        self.remote_widget.send_command(f"QUALITY,{quality_value}")

    def connect_to_server(self, instance):
        host = self.ip_input.text
        port = int(self.port_input.text)
        self.status_label.text = f"Connexion sécurisée à {host}:{port}..."
        threading.Thread(target=self.receive_frames, args=(host, port), daemon=True).start()

    def receive_frames(self, host, port):
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket = context.wrap_socket(sock, server_hostname=host)
            client_socket.connect((host, port))
            self.remote_widget.client_socket = client_socket
            self.send_quality_setting(70)
            Clock.schedule_once(self.switch_to_remote_screen)
        except Exception as e:
            Clock.schedule_once(lambda dt, err=str(e): self.show_connection_error(err))
            return
        
        while True:
            try:
                len_info = self.recv_all(self.remote_widget.client_socket, 4)
                if not len_info: break
                payload_size = struct.unpack("!I", len_info)[0]
                payload = self.recv_all(self.remote_widget.client_socket, payload_size)
                if not payload: break
                header_size = struct.calcsize("!II")
                width, height = struct.unpack("!II", payload[:header_size])
                self.remote_widget.server_resolution = (width, height)
                img_bytes = payload[header_size:]
                Clock.schedule_once(lambda dt, data=img_bytes: self.update_image(data))
            except (ConnectionResetError, BrokenPipeError): break
        
        if self.remote_widget.client_socket:
            self.remote_widget.client_socket.close()
            self.remote_widget.client_socket = None
        Clock.schedule_once(self.switch_to_connect_screen)

    def switch_to_remote_screen(self, dt):
        self.sm.current = 'remote'
        self.remote_widget.setup_keyboard()

    def switch_to_connect_screen(self, dt):
        self.remote_widget.release_keyboard()
        self.status_label.text = "Déconnecté du serveur."
        self.sm.current = 'connect'

    def show_connection_error(self, error_msg):
        self.status_label.text = f"Échec: {error_msg}"

    def recv_all(self, sock, n):
        data = bytearray()
        while len(data) < n:
            if sock is None: return None
            try:
                packet = sock.recv(n - len(data))
                if not packet: return None
                data.extend(packet)
            except (socket.error, AttributeError):
                return None
        return data

    def update_image(self, jpeg_bytes):
        buf = io.BytesIO(jpeg_bytes)
        core_image = CoreImage(buf, ext='jpg')
        self.remote_widget.texture = core_image.texture

if __name__ == '__main__':
    RemoteViewerApp().run()
