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

# --- Widget du bureau distant (avec la logique de votre ancien code) ---
class RemoteDesktopWidget(Image):
    def __init__(self, **kwargs):
        super(RemoteDesktopWidget, self).__init__(**kwargs)
        self.client_socket = None
        self.pressed_keys = set()
        self._keyboard = None

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

    def _keyboard_closed(self):
        self.release_keyboard()

    def _on_key_down(self, keyboard, keycode, text, modifiers):
        key_name = keycode[1]
        if not key_name: return True
        if key_name not in self.pressed_keys:
            self.pressed_keys.add(key_name)
            self.send_command(f"KP,{key_name}")
        return True

    def _on_key_up(self, keyboard, keycode):
        key_name = keycode[1]
        if not key_name: return True
        if key_name in self.pressed_keys:
            self.pressed_keys.remove(key_name)
            self.send_command(f"KR,{key_name}")
        return True

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos) and self.texture:
            btn = "left" if touch.button == 'left' else "right"
            self.send_command(f"MC,{btn},1") # Press
            return True
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if self.collide_point(*touch.pos) and self.texture:
            btn = "left" if touch.button == 'left' else "right"
            self.send_command(f"MC,{btn},0") # Release
            return True
        return super().on_touch_up(touch)

    def on_touch_move(self, touch):
        if self.collide_point(*touch.pos) and self.texture:
            remote_x = int(touch.x * (self.texture.width / self.width))
            remote_y = int((self.height - touch.y) * (self.texture.height / self.height))
            self.send_command(f"MV,{remote_x},{remote_y}")
            return True
        return super().on_touch_move(touch)

    def send_command(self, command_str):
        if self.client_socket:
            try:
                command_bytes = command_str.encode('utf-8')
                len_info = struct.pack("!H", len(command_bytes))
                self.client_socket.sendall(len_info + command_bytes)
            except (BrokenPipeError, ConnectionResetError):
                pass

# --- Application principale (avec SSL) ---
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
        # Configuration SSL
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE # Pas de vérification du certificat serveur pour ce test

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
                img_size = struct.unpack("!I", len_info)[0]
                img_bytes = self.recv_all(client_socket, img_size)
                if not img_bytes: break
                Clock.schedule_once(lambda dt, data=img_bytes: self.update_image(data))
            except (ConnectionResetError, BrokenPipeError):
                break
        
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
