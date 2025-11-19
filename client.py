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
import time # Importation du module time
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
from kivy.properties import StringProperty, BooleanProperty, ListProperty, ColorProperty
from os.path import expanduser
import pyperclip # Importation de pyperclip
import pythoncom # Importation de pythoncom pour la gestion des threads COM

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

<ColorProgressBar>:
    canvas:
        Color:
            rgba: 0.2, 0.2, 0.2, 1 # Background color
        BorderImage:
            border: (12, 12, 12, 12)
            pos: self.x, self.center_y - 12
            size: self.width, 24
            source: 'atlas://data/images/defaulttheme/progressbar_background'
        Color:
            rgba: self.bar_color
        BorderImage:
            border: [int(min(self.width * (self.value / float(self.max)) if self.max else 0, 12))] * 4
            pos: self.x, self.center_y - 12
            size: self.width * (self.value / float(self.max)) if self.max else 0, 24
            source: 'atlas://data/images/defaulttheme/progressbar'
''')

class ColorProgressBar(ProgressBar):
    bar_color = ColorProperty([0.2, 0.6, 0.8, 1]) # Default blue

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
                if hasattr(touch, 'scroll_y'):
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
                # MODIFICATION ICI : Ajouter le préfixe MSG_TYPE_COMMAND
                self.client_socket.sendall(MSG_TYPE_COMMAND + len_info + command_bytes)
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

# Message types for the main streaming socket
MSG_TYPE_IMAGE = b'\x01'
MSG_TYPE_COMMAND = b'\x02'

class RemoteViewerApp(App):
    def build(self):
        self.sm = ScreenManager()
        self.sys_info_update_event = None
        self.current_remote_path = ""
        self.cancel_transfer_flag = threading.Event()
        self.clipboard_stop_event = threading.Event() # Event pour arrêter le monitoring du presse-papiers
        self.last_clipboard_content = "" # Pour suivre le presse-papiers local
        self.last_clipboard_content_from_server = "" # Pour éviter les boucles de synchronisation
        self.chat_history_messages = [] # Nouvelle liste pour stocker les messages de chat

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
        self.tab_panel.bind(current_tab=self.on_tab_switch)

        self.desktop_tab = TabbedPanelItem(text='Bureau')
        self.remote_widget = RemoteDesktopWidget()
        self.desktop_tab.add_widget(self.remote_widget)
        self.tab_panel.add_widget(self.desktop_tab)

        # --- Onglet Infos Système ---
        self.sys_info_tab = TabbedPanelItem(text='Infos Système')
        sys_info_layout = BoxLayout(orientation='vertical', padding=20, spacing=10)

        self.sys_info_labels_grid = GridLayout(cols=2, size_hint_y=None, height=dp(120))
        self.sys_info_labels = {
            "node_name": Label(text="Nom: -"), "user_name": Label(text="Utilisateur: -"),
            "os_version": Label(text="OS: -"), "architecture": Label(text="Arch: -")
        }
        for key in ["node_name", "user_name", "os_version", "architecture"]:
            self.sys_info_labels_grid.add_widget(Label(text=key.replace('_', ' ').title() + ':', halign='right'))
            self.sys_info_labels_grid.add_widget(self.sys_info_labels[key])

        self.sys_info_bars_grid = GridLayout(cols=1, size_hint_y=None, spacing=dp(10))
        self.sys_info_bars_grid.bind(minimum_height=self.sys_info_bars_grid.setter('height'))
        self.sys_info_widgets = {}

        scroll_view = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        scroll_view.add_widget(self.sys_info_bars_grid)
        sys_info_layout.add_widget(self.sys_info_labels_grid)
        sys_info_layout.add_widget(scroll_view)
        self.sys_info_tab.add_widget(sys_info_layout)
        self.tab_panel.add_widget(self.sys_info_tab)

        settings_tab = TabbedPanelItem(text='Paramètres')
        settings_layout = BoxLayout(orientation='vertical', padding=20, spacing=10)
        self.quality_label = Label(text='Qualité de l\'image: 70%', size_hint_y=None, height=40) # Rendu self.quality_label
        quality_slider = Slider(min=10, max=95, value=70, step=5)
        quality_slider.bind(value=lambda i, v: (self.send_quality_setting(int(v)), setattr(self.quality_label, 'text', f"Qualité de l'image: {int(v)}%"))) # Mise à jour du label
        settings_layout.add_widget(self.quality_label) # Utilisation de self.quality_label
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
        scroll_view_files = ScrollView()
        scroll_view_files.add_widget(self.file_browser_grid)

        download_layout.add_widget(button_layout)
        download_layout.add_widget(self.remote_path_label)
        download_layout.add_widget(scroll_view_files)
        download_tab.add_widget(download_layout)
        self.tab_panel.add_widget(download_tab)

        # --- NOUVEAU : Onglet Chat ---
        self.chat_tab = TabbedPanelItem(text='Chat')
        chat_layout = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(5))

        self.chat_history_label = Label(
            text='',
            halign='left',
            valign='top',
            size_hint_y=None,
            markup=True # Permet d'utiliser des balises comme [b]gras[/b] ou [color=FF0000]couleur[/color]
        )
        # Lie la taille du texte à la largeur du label pour un retour à la ligne automatique
        self.chat_history_label.bind(width=lambda instance, value: setattr(instance, 'text_size', (value, None)))
        self.chat_history_label.bind(texture_size=self.chat_history_label.setter('size'))

        chat_scroll_view = ScrollView(size_hint=(1, 1))
        chat_scroll_view.add_widget(self.chat_history_label)

        chat_input_layout = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(5))
        self.chat_input = TextInput(multiline=False, hint_text='Tapez votre message ici...')
        send_button = Button(text='Envoyer', size_hint_x=None, width=dp(80), on_press=self.send_chat_message)

        chat_input_layout.add_widget(self.chat_input)
        chat_input_layout.add_widget(send_button)

        chat_layout.add_widget(chat_scroll_view)
        chat_layout.add_widget(chat_input_layout)
        self.chat_tab.add_widget(chat_layout)
        self.tab_panel.add_widget(self.chat_tab)
        # --- FIN NOUVEL ONGLET CHAT ---

        # --- NOUVEAU : Onglet À propos ---
        about_tab = TabbedPanelItem(text='À propos')
        about_layout = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(10))

        about_layout.add_widget(Label(text='[b]Hosanna Remote Viewer[/b]', markup=True, font_size='20sp', size_hint_y=None, height=dp(40)))
        about_layout.add_widget(Label(text='Version: 1.0.0', size_hint_y=None, height=dp(30)))
        about_layout.add_widget(Label(text='Développé par: Chadrak', size_hint_y=None, height=dp(30)))
        about_layout.add_widget(Label(text='Année: 2024', size_hint_y=None, height=dp(30)))
        about_layout.add_widget(Label(text='[b]Description:[/b]', markup=True, size_hint_y=None, height=dp(30)))
        about_layout.add_widget(Label(text='Application de visualisation et de contrôle à distance sécurisée.', halign='center', valign='middle'))

        about_tab.add_widget(about_layout)
        self.tab_panel.add_widget(about_tab)
        # --- FIN NOUVEL ONGLET À PROPOS ---

        self.tab_panel.default_tab = self.desktop_tab
        remote_screen.add_widget(self.tab_panel)

        self.sm.add_widget(connect_screen)
        self.sm.add_widget(remote_screen)

        return self.sm

    def on_tab_switch(self, instance, value):
        # --- Gestion du clavier ---
        if value == self.desktop_tab:
            self.remote_widget.setup_keyboard()
            print("[*] CLIENT DEBUG: Keyboard focus given to RemoteDesktopWidget.")
        else:
            self.remote_widget.release_keyboard()
            print("[*] CLIENT DEBUG: Keyboard focus released from RemoteDesktopWidget.")

        # --- Gestion des infos système ---
        if value == self.sys_info_tab:
            self.start_sys_info_updates()
        else:
            self.stop_sys_info_updates()

    def start_sys_info_updates(self):
        if not self.sys_info_update_event:
            self._request_sys_info_thread()
            self.sys_info_update_event = Clock.schedule_interval(lambda dt: self._request_sys_info_thread(), 1)

    def stop_sys_info_updates(self):
        if self.sys_info_update_event:
            self.sys_info_update_event.cancel()
            self.sys_info_update_event = None

    def _request_sys_info_thread(self):
        threading.Thread(target=self._get_sys_info_from_server, daemon=True).start()

    def _get_sys_info_from_server(self):
        try:
            host, file_port = self.ip_input.text, int(self.port_input.text) - 1
            header_str = "GET_SYS_INFO"
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
                Clock.schedule_once(lambda dt: self._update_sys_info_ui(data))
        except Exception as e:
            print(f"Erreur de récupération des infos système: {e}")
            Clock.schedule_once(lambda dt: self.stop_sys_info_updates())

    def _update_sys_info_ui(self, data):
        if 'error' in data:
            self.sys_info_labels['node_name'].text = f"Erreur: {data['error']}"
            return

        for key, label in self.sys_info_labels.items():
            label.text = str(data.get(key, '-'))

        # Mise à jour CPU
        cpu_info = data.get('cpu', {})
        cpu_usage = cpu_info.get('usage', 0)
        freq_current = cpu_info.get('freq_current', 0)
        freq_max = cpu_info.get('freq_max', 0)

        if 'cpu' not in self.sys_info_widgets:
            box = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(70))
            box.add_widget(Label(text="CPU Usage"))
            bar = ColorProgressBar(max=100)
            percent_label = Label(text="0%")
            freq_label = Label(text="Freq: -")
            box.add_widget(bar)
            box.add_widget(percent_label)
            box.add_widget(freq_label)
            self.sys_info_bars_grid.add_widget(box)
            self.sys_info_widgets['cpu'] = {'bar': bar, 'percent': percent_label, 'freq': freq_label}

        self.sys_info_widgets['cpu']['bar'].value = cpu_usage
        self.sys_info_widgets['cpu']['percent'].text = f"{cpu_usage:.1f}%"

        # Changer la couleur de la barre de progression CPU
        if cpu_usage >= 95:
            # Rouge très vif et lumineux
            self.sys_info_widgets['cpu']['bar'].bar_color = (1, 0, 0.15, 1)


        elif cpu_usage >= 80:
            # Orange plus clair donc plus visible
            self.sys_info_widgets['cpu']['bar'].bar_color = (1, 0.65, 0, 1)

        else:
            # Bleu vif bien visible
            self.sys_info_widgets['cpu']['bar'].bar_color = (0, 0.55, 1, 1)

        freq_text = "Freq: "
        if freq_current > 0:
            freq_text += f"{freq_current / 1000:.2f} GHz"
        if freq_max > 0:
            freq_text += f" (Max: {freq_max / 1000:.2f} GHz)"
        self.sys_info_widgets['cpu']['freq'].text = freq_text


        # Mise à jour RAM
        if 'ram' not in self.sys_info_widgets:
            box = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(50))
            box.add_widget(Label(text="RAM Usage"))
            bar = ColorProgressBar(max=100)
            percent_label = Label(text="0%")
            box.add_widget(bar)
            box.add_widget(percent_label)
            self.sys_info_bars_grid.add_widget(box)
            self.sys_info_widgets['ram'] = {'bar': bar, 'percent': percent_label}

        ram_info = data.get('ram', {})
        ram_percent = ram_info.get('percent', 0)
        self.sys_info_widgets['ram']['bar'].value = ram_percent
        self.sys_info_widgets['ram']['percent'].text = f"{ram_percent:.1f}% ({sizeof_fmt(ram_info.get('used',0))} / {sizeof_fmt(ram_info.get('total',0))})"

        # Changer la couleur de la barre de progression RAM
        if ram_percent >= 95:
            # Rouge très vif et lumineux
            self.sys_info_widgets['ram']['bar'].bar_color = (1, 0, 0.15, 1)


        elif ram_percent >= 80:
            # Orange clair et très visible
            self.sys_info_widgets['ram']['bar'].bar_color = (1, 0.65, 0, 1)

        else:
            # Bleu vif bien visible
            self.sys_info_widgets['ram']['bar'].bar_color = (0, 0.55, 1, 1)

        # Mise à jour Disques
        for disk in data.get('disks', []):
            disk_id = disk['device']
            if disk_id not in self.sys_info_widgets:
                box = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(50))
                box.add_widget(Label(text=f"Disk: {disk.get('mountpoint', disk_id)}"))
                bar = ColorProgressBar(max=100)
                percent_label = Label(text="0%")
                box.add_widget(bar)
                box.add_widget(percent_label)
                self.sys_info_bars_grid.add_widget(box)
                self.sys_info_widgets[disk_id] = {'bar': bar, 'percent': percent_label}

            disk_percent = disk.get('percent', 0)
            self.sys_info_widgets[disk_id]['bar'].value = disk_percent
            self.sys_info_widgets[disk_id]['percent'].text = f"{disk_percent:.1f}% ({sizeof_fmt(disk.get('used',0))} / {sizeof_fmt(disk.get('total',0))})"

            # Changer la couleur de la barre de progression Disque
            if disk_percent >= 95:
                # Rouge très vif et lumineux
                self.sys_info_widgets[disk_id]['bar'].bar_color = (1, 0, 0.3, 1)

            elif disk_percent >= 80:
                # Orange clair et très visible
                self.sys_info_widgets[disk_id]['bar'].bar_color = (1, 0.65, 0, 1)

            else:
                # Bleu vif bien visible
                self.sys_info_widgets[disk_id]['bar'].bar_color = (0, 0.55, 1, 1)

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
            host, file_port = self.ip_input.text, int(self.port_input.text) - 1
            header_str = f"UPLOAD,{filename},{filesize}"
            header_bytes = header_str.encode('utf-8')
            len_info = struct.pack("!H", len(header_bytes))
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

    def send_clipboard_to_server(self, content):
        if self.remote_widget.client_socket:
            try:
                command_str = f"CLIPBOARD_DATA,{content}"
                command_bytes = command_str.encode('utf-8')
                len_info = struct.pack("!H", len(command_bytes))
                # Prefix with message type for command
                self.remote_widget.client_socket.sendall(MSG_TYPE_COMMAND + len_info + command_bytes)
                print(f"[*] CLIENT DEBUG: Envoi du presse-papiers au serveur: '{content}'")
            except (BrokenPipeError, ConnectionResetError):
                print("[!] CLIENT DEBUG: Serveur déconnecté lors de l'envoi du presse-papiers.")
            except Exception as e:
                print(f"[!] CLIENT DEBUG: Erreur lors de l'envoi du presse-papiers au serveur: {e}")

    # NOUVEAU : Méthode pour envoyer un message de chat au serveur
    def send_chat_message(self, instance):
        message = self.chat_input.text.strip()
        if message:
            if self.remote_widget.client_socket:
                try:
                    command_str = f"CHAT_MESSAGE,{message}"
                    command_bytes = command_str.encode('utf-8')
                    len_info = struct.pack("!H", len(command_bytes))
                    # Utilise MSG_TYPE_COMMAND pour les messages de chat
                    self.remote_widget.client_socket.sendall(MSG_TYPE_COMMAND + len_info + command_bytes)
                    print(f"[*] CLIENT DEBUG: Message chat envoyé au serveur: '{message}'")
                    # Ajoute le message à l'historique local
                    self.add_message_to_chat_history(f"[b][color=00BFFF]Moi:[/color][/b] {message}")
                    self.chat_input.text = '' # Efface le champ de saisie
                except (BrokenPipeError, ConnectionResetError):
                    print("[!] CLIENT DEBUG: Serveur déconnecté lors de l'envoi du message chat.")
                    self.add_message_to_chat_history("[b][color=FF0000]Erreur:[/color][/b] Serveur déconnecté.")
                except Exception as e:
                    print(f"[!] CLIENT DEBUG: Erreur lors de l'envoi du message chat: {e}")
                    self.add_message_to_chat_history(f"[b][color=FF0000]Erreur:[/color][/b] {e}")
            else:
                self.add_message_to_chat_history("[b][color=FF0000]Erreur:[/color][/b] Non connecté au serveur.")

    # NOUVEAU : Méthode pour ajouter un message à l'historique du chat et mettre à jour l'UI
    def add_message_to_chat_history(self, message):
        self.chat_history_messages.append(message)
        # Limite le nombre de messages pour éviter une consommation excessive de mémoire
        if len(self.chat_history_messages) > 100: # Exemple de limite
            self.chat_history_messages = self.chat_history_messages[-100:]

        # Met à jour l'UI sur le thread principal
        Clock.schedule_once(lambda dt: self._update_chat_history_ui_text())

    # NOUVEAU : Méthode interne pour mettre à jour le texte du label de l'historique du chat
    def _update_chat_history_ui_text(self):
        self.chat_history_label.text = '\n'.join(self.chat_history_messages)
        # Fait défiler vers le bas
        if self.chat_history_label.parent and isinstance(self.chat_history_label.parent, ScrollView):
            self.chat_history_label.parent.scroll_y = 0 # Fait défiler vers le bas

    def monitor_clipboard_changes(self):
        # Initialize COM for this thread
        pythoncom.CoInitialize()
        try:
            self.last_clipboard_content = pyperclip.paste()
            print(f"[*] CLIENT DEBUG: Démarrage du monitoring du presse-papiers. Contenu initial: '{self.last_clipboard_content}'")
            while not self.clipboard_stop_event.is_set():
                current_clipboard = pyperclip.paste()
                if current_clipboard != self.last_clipboard_content and \
                   current_clipboard != self.last_clipboard_content_from_server:
                    print(f"[*] CLIENT DEBUG: Changement détecté dans le presse-papiers local. Ancien: '{self.last_clipboard_content}', Nouveau: '{current_clipboard}'")
                    self.last_clipboard_content = current_clipboard
                    self.send_clipboard_to_server(current_clipboard)
                    print("[*] CLIENT DEBUG: Presse-papiers client mis à jour localement et envoyé au serveur.")
                time.sleep(0.5)
        except Exception as e:
            print(f"[!] CLIENT DEBUG: Erreur dans monitor_clipboard_changes: {e}")
        finally:
            # Uninitialize COM for this thread
            pythoncom.CoUninitialize()

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

            # Démarrer le monitoring du presse-papiers
            self.clipboard_stop_event.clear()
            threading.Thread(target=self.monitor_clipboard_changes, daemon=True).start()

        except Exception as e:
            Clock.schedule_once(lambda dt, err=str(e): self.show_connection_error(err))
        else:
            while True:
                try:
                    # Read message type (1 byte)
                    msg_type_byte = self.recv_all(self.remote_widget.client_socket, 1)
                    if not msg_type_byte:
                        print("[!] CLIENT DEBUG: Déconnexion ou fin de flux (type de message vide).")
                        break

                    if msg_type_byte == MSG_TYPE_IMAGE:
                        # Read image payload length (4 bytes)
                        len_info = self.recv_all(self.remote_widget.client_socket, 4)
                        if not len_info:
                            print("[!] CLIENT DEBUG: Déconnexion ou fin de flux (longueur image vide).")
                            break
                        payload_size = struct.unpack("!I", len_info)[0]
                        payload = self.recv_all(self.remote_widget.client_socket, payload_size)
                        if not payload:
                            print("[!] CLIENT DEBUG: Déconnexion ou fin de flux (payload image vide).")
                            break

                        width, height = struct.unpack("!II", payload[:struct.calcsize("!II")])
                        self.remote_widget.server_resolution = (width, height)
                        Clock.schedule_once(lambda dt, data=payload[struct.calcsize("!II"):]: self.update_image(data))

                    elif msg_type_byte == MSG_TYPE_COMMAND:
                        # Read command length (2 bytes)
                        len_info = self.recv_all(self.remote_widget.client_socket, 2)
                        if not len_info:
                            print("[!] CLIENT DEBUG: Déconnexion ou fin de flux (longueur commande vide).")
                            break
                        cmd_len = struct.unpack("!H", len_info)[0]
                        command_data = self.recv_all(self.remote_widget.client_socket, cmd_len)
                        if not command_data:
                            print("[!] CLIENT DEBUG: Déconnexion ou fin de flux (payload commande vide).")
                            break
                        command = command_data.decode('utf-8')

                        parts = command.split(',', 1)
                        cmd_type = parts[0]
                        value_str = parts[1] if len(parts) > 1 else ""

                        if cmd_type == 'CLIPBOARD_UPDATE':
                            content = value_str
                            try:
                                pyperclip.copy(content)
                                self.last_clipboard_content = content
                                self.last_clipboard_content_from_server = content
                                print(f"[*] CLIENT DEBUG: Presse-papiers client mis à jour par le serveur avec: '{content}'")
                            except Exception as e:
                                print(f"[!] CLIENT DEBUG: Erreur lors de la mise à jour du presse-papiers client: {e}")
                        elif cmd_type == 'CHAT_MESSAGE_FROM_SERVER': # NOUVEAU : Gérer les messages de chat du serveur
                            message = value_str
                            print(f"[*] CLIENT DEBUG: Message chat reçu du serveur: '{message}'")
                            self.add_message_to_chat_history(f"[b][color=00FF00]Serveur:[/color][/b] {message}")
                        else:
                            print(f"[!] CLIENT DEBUG: Commande inconnue reçue du serveur: '{command}'")
                    else:
                        print(f"[!] CLIENT DEBUG: Type de message inconnu reçu: {msg_type_byte}")
                        break # Or handle error appropriately

                except (ConnectionResetError, BrokenPipeError):
                    print("[!] CLIENT DEBUG: Connexion perdue avec le serveur.")
                    break
                except Exception as e:
                    print(f"[!] CLIENT DEBUG: Erreur inattendue dans receive_frames: {e}")
                    break # Break on other exceptions too

            if self.remote_widget.client_socket:
                self.remote_widget.client_socket.close(); self.remote_widget.client_socket = None
            Clock.schedule_once(self.switch_to_connect_screen)

    def switch_to_remote_screen(self, dt): self.sm.current = 'remote'; self.remote_widget.setup_keyboard()
    def switch_to_connect_screen(self, dt):
        self.remote_widget.release_keyboard()
        self.clipboard_stop_event.set() # Arrêter le monitoring du presse-papiers
        self.status_label.text = "Déconnecté."; self.sm.current = 'connect'
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