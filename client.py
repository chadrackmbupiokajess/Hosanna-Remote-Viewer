# Configurer Kivy pour gérer le clic droit
from kivy.config import Config
Config.set('input', 'mouse', 'mouse,multitouch_on_demand')

import socket
import struct
import io
import threading
import ssl
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
        return kivy_button_name # On fait confiance à Kivy pour rapporter le bon bouton

    def on_touch_down(self, touch):
        # print(f"[CLIENT DEBUG] on_touch_down - button: {touch.button}, pos: {touch.pos}") # <-- DEBUG
        x, y = self._get_scaled_coords(touch)
        if x != -1:
            # Gérer le défilement de la molette
            if touch.is_mouse_scrolling:
                # Kivy's scroll_y est 1 pour haut, -1 pour bas.
                # pynput's scroll attend (x_offset, y_offset)
                # Pour le défilement vertical, x_offset est 0, y_offset est touch.scroll_y
                self.send_command(f"SCROLL,0,{int(touch.scroll_y)}")
                print(f"[CLIENT DEBUG] Envoi: SCROLL,0,{int(touch.scroll_y)}")
                return True # Consommer l'événement

            # CORRIGÉ: Envoyer la position avant d'envoyer l'événement de clic
            self.send_command(f"MV,{x},{y}")
            
            # Envoyer la commande "press"
            touch.ud['initial_pos'] = touch.pos
            mapped_button = self._get_mapped_button_name(touch.button)
            self.send_command(f"MC,{mapped_button},1")
            print(f"[CLIENT DEBUG] Envoi: MV,{x},{y} puis MC,{mapped_button},1 (down)")
            return True
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        # print(f"[CLIENT DEBUG] on_touch_up - button: {touch.button}, pos: {touch.pos}") # <-- DEBUG
        x, y = self._get_scaled_coords(touch)
        if x != -1:
            mapped_button = self._get_mapped_button_name(touch.button)

            # CORRIGÉ: La logique de clic est simplifiée pour envoyer un relâchement simple,
            # sauf pour le double-clic qui reste un cas spécial.
            if mapped_button == 'left' and touch.is_double_tap:
                self.send_command(f"DBLCLICK,{x},{y},{mapped_button}")
                print(f"[CLIENT DEBUG] Envoi: DBLCLICK,{x},{y},{mapped_button}")
            else:
                # Pour un clic simple (gauche/droit) ou la fin d'un glisser,
                # on envoie seulement la commande "release".
                self.send_command(f"MC,{mapped_button},0")
                print(f"[CLIENT DEBUG] Envoi: MC,{mapped_button},0 (up)")

            return True
        return super().on_touch_up(touch)

    def on_touch_move(self, touch):
        # print(f"[CLIENT DEBUG] on_touch_move - button: {touch.button}, pos: {touch.pos}") # <-- DEBUG (peut être très verbeux)
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
        self.remote_widget = RemoteDesktopWidget()
        remote_screen.add_widget(self.remote_widget)
        self.sm.add_widget(connect_screen)
        self.sm.add_widget(remote_screen)
        return self.sm

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
            Clock.schedule_once(self.switch_to_remote_screen)
        except Exception as e:
            Clock.schedule_once(lambda dt, err=str(e): self.show_connection_error(err))
            return
        
        while True:
            try:
                len_info = self.recv_all(client_socket, 4)
                if not len_info: break
                payload_size = struct.unpack("!I", len_info)[0]
                payload = self.recv_all(client_socket, payload_size)
                if not payload: break
                header_size = struct.calcsize("!II")
                width, height = struct.unpack("!II", payload[:header_size])
                self.remote_widget.server_resolution = (width, height)
                img_bytes = payload[header_size:]
                Clock.schedule_once(lambda dt, data=img_bytes: self.update_image(data))
            except (ConnectionResetError, BrokenPipeError): break
        
        client_socket.close()
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
            packet = sock.recv(n - len(data))
            if not packet: return None
            data.extend(packet)
        return data

    def update_image(self, jpeg_bytes):
        buf = io.BytesIO(jpeg_bytes)
        core_image = CoreImage(buf, ext='jpg')
        self.remote_widget.texture = core_image.texture

if __name__ == '__main__':
    RemoteViewerApp().run()
