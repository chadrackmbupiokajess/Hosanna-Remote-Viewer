# Configurer Kivy pour gérer le clic droit
from kivy.config import Config
Config.set('input', 'mouse', 'mouse,multitouch_on_demand')
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.utils import get_color_from_hex

import socket
import struct
import io
import threading
import ssl
import os
import json
import time
from tkinter import Tk, filedialog
from kivy.app import App
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.uix.image import Image
from kivy.graphics.texture import Texture
from kivy.clock import Clock
from kivy.core.image import Image as CoreImage
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
from kivy.uix.popup import Popup
from kivy.properties import StringProperty, BooleanProperty, ListProperty, ColorProperty, NumericProperty
from os.path import expanduser
import pyperclip
import pythoncom
from kivy.uix.spinner import Spinner # Import Spinner
import sys
from kivy.resources import resource_add_path

# Add this block to handle resource paths for PyInstaller
if hasattr(sys, '_MEIPASS'):
    resource_add_path(os.path.join(sys._MEIPASS))
else:
    # If running from source, add the script's directory
    resource_add_path(os.path.dirname(os.path.abspath(__file__)))


# --- NOUVEAU : Design amélioré avec KV String ---
Builder.load_string('''
#:import get_color_from_hex kivy.utils.get_color_from_hex
#:import RoundedRectangle kivy.graphics.RoundedRectangle

<SpinnerOption@SpinnerOption>: # Custom styling for spinner options
    background_color: get_color_from_hex('#2C2F33')
    color: get_color_from_hex('#FFFFFF')
    background_normal: ''
    background_down: ''
    canvas.before:
        Color:
            rgba: self.background_color
        Rectangle:
            pos: self.pos
            size: self.size

<FileEntryWidget>:
    orientation: 'horizontal'
    padding: dp(10)
    spacing: dp(10)
    size_hint_y: None
    height: dp(40)
    canvas.before:
        Color:
            rgba: get_color_from_hex('#5865F2') if self.is_selected else (0,0,0,0)
        Rectangle:
            pos: self.pos[0], self.pos[1] + self.height - dp(2)
            size: self.width, dp(1) if self.is_selected else 0
        Color:
            rgba: get_color_from_hex('#2A2D31') if self.is_selected else (0.15, 0.15, 0.15, 0.5 if self.parent and self.parent.children.index(self) % 2 == 0 else 0)
        Rectangle:
            pos: self.pos
            size: self.size
    Label:
        id: icon_label
        text: "📁" if root.is_dir else "📄"
        font_name: 'seguisym.ttf'
        font_size: '18sp'
        size_hint_x: None
        width: dp(30)
        color: get_color_from_hex('#FFFFFF')
    Label:
        text: root.name
        halign: 'left'
        valign: 'middle'
        text_size: self.width, None
        shorten: True
        shorten_from: 'right'
        color: get_color_from_hex('#FFFFFF')
    Label:
        text: root.file_size
        size_hint_x: None
        width: dp(80)
        halign: 'right'
        valign: 'middle'
        text_size: self.width, None
        font_size: '12sp'
        color: get_color_from_hex('#99AAB5')

<ColorProgressBar>:
    canvas:
        Color:
            rgba: 0.2, 0.2, 0.2, 1
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

<ConnectScreen>:
    canvas.before:
        Color:
            rgba: get_color_from_hex('#1A1A1A')
        Rectangle:
            pos: self.pos
            size: self.size

    BoxLayout:
        orientation: 'vertical'
        size_hint: None, None
        size: dp(400), dp(550)
        pos_hint: {'center_x': 0.5, 'center_y': 0.5}
        padding: dp(30)
        spacing: dp(15)
        canvas.before:
            Color:
                rgba: get_color_from_hex('#2C2F33')
            RoundedRectangle:
                pos: self.pos
                size: self.size
                radius: [dp(15),]

        Image:
            source: 'logo.ico'
            size_hint_y: None
            height: dp(80)
            allow_stretch: True
            padding: dp(10)

        Label:
            text: 'Hosanna Remote'
            font_size: '32sp'
            bold: True
            size_hint_y: None
            height: self.texture_size[1]
            color: get_color_from_hex('#FFFFFF')

        Label:
            text: 'Connexion sécurisée'
            font_size: '16sp'
            size_hint_y: None
            height: self.texture_size[1]
            color: get_color_from_hex('#99AAB5')
            padding: 0, dp(10)

        TabbedPanel:
            id: connection_tabs
            do_default_tab: False
            tab_pos: 'top_mid'
            tab_width: self.width / 2
            background_color: get_color_from_hex('#2C2F33')

            TabbedPanelItem:
                text: 'Connexion Locale'
                id: local_tab
                font_size: '14sp'
                background_color: get_color_from_hex('#23272A')
                
                GridLayout:
                    cols: 1
                    spacing: dp(15)
                    padding: dp(20)
                    
                    BoxLayout:
                        size_hint_y: None
                        height: dp(50)
                        canvas.before:
                            Color:
                                rgba: get_color_from_hex('#23272A')
                            RoundedRectangle:
                                pos: self.pos
                                size: self.size
                                radius: [dp(8),]
                        TextInput:
                            id: ip_input
                            hint_text: 'Adresse IP du serveur'
                            multiline: False
                            background_color: 0,0,0,0
                            foreground_color: get_color_from_hex('#FFFFFF')
                            hint_text_color: get_color_from_hex('#99AAB5')
                            font_size: '15sp'
                            padding: [dp(15), (self.height - self.line_height) / 2, dp(15), (self.height - self.line_height) / 2]

                    BoxLayout:
                        size_hint_y: None
                        height: dp(50)
                        canvas.before:
                            Color:
                                rgba: get_color_from_hex('#23272A')
                            RoundedRectangle:
                                pos: self.pos
                                size: self.size
                                radius: [dp(8),]
                        TextInput:
                            id: port_input
                            hint_text: 'Port (ex: 5000)'
                            text: '1981'
                            multiline: False
                            background_color: 0,0,0,0
                            foreground_color: get_color_from_hex('#FFFFFF')
                            hint_text_color: get_color_from_hex('#99AAB5')
                            font_size: '15sp'
                            padding: [dp(15), (self.height - self.line_height) / 2, dp(15), (self.height - self.line_height) / 2]

            TabbedPanelItem:
                text: 'Connexion Distante'
                id: remote_tab
                font_size: '14sp'
                background_color: get_color_from_hex('#23272A')

                GridLayout:
                    cols: 1
                    spacing: dp(15)
                    padding: dp(20)

                    BoxLayout:
                        size_hint_y: None
                        height: dp(50)
                        canvas.before:
                            Color:
                                rgba: get_color_from_hex('#23272A')
                            RoundedRectangle:
                                pos: self.pos
                                size: self.size
                                radius: [dp(8),]
                        TextInput:
                            id: remote_address_input
                            hint_text: 'Adresse publique'
                            multiline: False
                            background_color: 0,0,0,0
                            foreground_color: get_color_from_hex('#FFFFFF')
                            hint_text_color: get_color_from_hex('#99AAB5')
                            font_size: '15sp'
                            padding: [dp(15), (self.height - self.line_height) / 2, dp(15), (self.height - self.line_height) / 2]
                    
                    BoxLayout:
                        size_hint_y: None
                        height: dp(50)
                        canvas.before:
                            Color:
                                rgba: get_color_from_hex('#23272A')
                            RoundedRectangle:
                                pos: self.pos
                                size: self.size
                                radius: [dp(8),]
                        TextInput:
                            id: remote_port_input
                            hint_text: 'Port public'
                            multiline: False
                            background_color: 0,0,0,0
                            foreground_color: get_color_from_hex('#FFFFFF')
                            hint_text_color: get_color_from_hex('#99AAB5')
                            font_size: '15sp'
                            padding: [dp(15), (self.height - self.line_height) / 2, dp(15), (self.height - self.line_height) / 2]
        
        BoxLayout:
            size_hint_y: None
            height: dp(50)
            spacing: dp(15)

            Button:
                id: discover_button
                text: 'Rechercher'
                font_size: '16sp'
                background_color: 0,0,0,0
                canvas.before:
                    Color:
                        rgba: get_color_from_hex('#40444B')
                    RoundedRectangle:
                        pos: self.pos
                        size: self.size
                        radius: [dp(8),]
                on_press: app.discover_server(self)

            Button:
                id: connect_button
                text: 'Se connecter'
                font_size: '16sp'
                background_color: 0,0,0,0
                canvas.before:
                    Color:
                        rgba: get_color_from_hex('#5865F2')
                    RoundedRectangle:
                        pos: self.pos
                        size: self.size
                        radius: [dp(8),]
                on_press: app.connect_to_server(self)

        Label:
            id: status_label
            text: ''
            size_hint_y: None
            height: self.texture_size[1]
            text_size: self.width, None
            halign: 'center'
            color: get_color_from_hex('#FFFFFF')

<RemoteScreen>:
    canvas.before:
        Color:
            rgba: get_color_from_hex('#1A1A1A')
        Rectangle:
            pos: self.pos
            size: self.size

<TabbedPanel>:
    do_default_tab: False
    tab_width: 150
    tab_height: 40
    background_color: get_color_from_hex('#2C2F33')
    canvas.before:
        Color:
            rgba: get_color_from_hex('#1A1A1A')
        Rectangle:
            pos: self.pos
            size: self.size

<TabbedPanelItem>:
    background_color: get_color_from_hex('#2C2F33')
    background_disabled_normal: ''
    background_normal: ''
    color: get_color_from_hex('#99AAB5')
    font_size: '14sp'
    
<TabbedPanelHeader>:
    background_color: get_color_from_hex('#2C2F33')

<TabbedPanelItem.background_normal>:
    background_color: get_color_from_hex('#2C2F33')

<TabbedPanelItem.background_disabled_normal>:
    background_color: get_color_from_hex('#2C2F33')

<TabbedPanelItem.background_down>:
    background_color: get_color_from_hex('#5865F2')
''')

# --- CORRECTION : Remise en place des variables globales ---
MSG_TYPE_IMAGE = b'\x01'
MSG_TYPE_COMMAND = b'\x02'
MSG_TYPE_CAMERA = b'\x03' # Nouveau type de message pour la caméra

class ColorProgressBar(ProgressBar):
    bar_color = ColorProperty([0.2, 0.6, 0.8, 1])

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
        if not hasattr(app, 'tab_panel') or not hasattr(app, 'desktop_tab'): return -1, -1
        if app.tab_panel.current_tab != app.desktop_tab: return -1, -1
        if not self.texture or self.norm_image_size[0] == 0: return -1, -1
        img_x = self.center_x - self.norm_image_size[0] / 2
        img_y = self.center_y - self.norm_image_size[1] / 2
        if not (img_x <= touch.x < img_x + self.norm_image_size[0] and img_y <= touch.y < img_y + self.norm_image_size[1]): return -1, -1
        relative_x = (touch.x - img_x) / self.norm_image_size[0]
        relative_y = (touch.y - img_y) / self.norm_image_size[1]
        server_x = int(relative_x * self.server_resolution[0])
        server_y = int((1 - relative_y) * self.server_resolution[1])
        return server_x, server_y

    def _get_mapped_button_name(self, kivy_button_name): return kivy_button_name

    def on_touch_down(self, touch):
        x, y = self._get_scaled_coords(touch)
        if x != -1:
            if touch.is_mouse_scrolling:
                if hasattr(touch, 'scroll_y'): self.send_command(f"SCROLL,0,{int(touch.scroll_y)}")
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
                self.client_socket.sendall(MSG_TYPE_COMMAND + len_info + command_bytes)
            except (BrokenPipeError, ConnectionResetError): pass

class RemoteCameraWidget(Image):
    def __init__(self, **kwargs):
        super(RemoteCameraWidget, self).__init__(**kwargs)
        self.client_socket = None
        self.camera_resolution = (1, 1)

    def send_command(self, command_str):
        if self.client_socket:
            try:
                command_bytes = command_str.encode('utf-8')
                len_info = struct.pack("!H", len(command_bytes))
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
                for widget in self.parent.children: widget.is_selected = False
                self.is_selected = True
            return True
        return super().on_touch_down(touch)

class ConnectScreen(Screen):
    pass

class RemoteScreen(Screen):
    pass

class RemoteViewerApp(App):
    available_cameras = ListProperty([])
    selected_camera_index = NumericProperty(0)

    def build(self):
        self.title = 'HosannaRemote'
        self.icon = 'logo.ico'
        self.sm = ScreenManager()
        self.sys_info_update_event = None
        self.current_remote_path = ""
        self.current_dir_entries = []
        self.cancel_transfer_flag = threading.Event()
        self.clipboard_stop_event = threading.Event()
        self.last_clipboard_content = ""
        self.last_clipboard_content_from_server = ""
        self.chat_history_messages = []
        self.is_camera_streaming = False
        self.main_server_address = None # (host, port) for main connection
        self.file_server_address = None # (host, port) for file transfer connection
        
        self.camera_placeholder_image = CoreImage('Hosanna Cameralogo.png')

        connect_screen = ConnectScreen(name='connect')
        self.connection_tabs = connect_screen.ids.connection_tabs
        self.local_tab = connect_screen.ids.local_tab
        self.remote_tab = connect_screen.ids.remote_tab
        self.ip_input = connect_screen.ids.ip_input
        self.port_input = connect_screen.ids.port_input
        self.remote_address_input = connect_screen.ids.remote_address_input
        self.remote_port_input = connect_screen.ids.remote_port_input
        self.status_label = connect_screen.ids.status_label
        
        self.connection_tabs.default_tab = self.local_tab

        remote_screen = RemoteScreen(name='remote')
        self.tab_panel = TabbedPanel(do_default_tab=False)
        self.tab_panel.bind(current_tab=self.on_tab_switch)

        self.desktop_tab = TabbedPanelItem(text='Bureau')
        self.remote_widget = RemoteDesktopWidget()
        self.desktop_tab.add_widget(self.remote_widget)
        self.tab_panel.add_widget(self.desktop_tab)

        self.camera_tab = TabbedPanelItem(text='Caméra')
        camera_layout = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))

        camera_selector_layout = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(10))
        camera_selector_layout.add_widget(Label(text="Sélectionner la caméra:", size_hint_x=None, width=dp(150), color=get_color_from_hex('#FFFFFF')))
        self.camera_selector = Spinner(
            text="Caméra 0",
            values=[],
            size_hint_x=None,
            width=dp(150),
            background_color=get_color_from_hex('#23272A'),
            color=get_color_from_hex('#FFFFFF'),
            option_cls='SpinnerOption'
        )
        self.camera_selector.bind(text=self.on_camera_selection_text)
        camera_selector_layout.add_widget(self.camera_selector)
        camera_layout.add_widget(camera_selector_layout)

        self.remote_camera_widget = RemoteCameraWidget(
            texture=self.camera_placeholder_image.texture,
            fit_mode="contain"
        )
        camera_layout.add_widget(self.remote_camera_widget)

        camera_controls = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        self.start_camera_button = Button(text='Démarrer Caméra', on_press=self.start_camera_stream)
        self.stop_camera_button = Button(text='Arrêter Caméra', on_press=self.stop_camera_stream, disabled=True)
        camera_controls.add_widget(self.start_camera_button)
        camera_controls.add_widget(self.stop_camera_button)
        camera_layout.add_widget(camera_controls)

        self.camera_tab.add_widget(camera_layout)
        self.tab_panel.add_widget(self.camera_tab)

        self.sys_info_tab = TabbedPanelItem(text='Infos Système')
        sys_info_layout = BoxLayout(orientation='vertical', padding=[dp(20), dp(15), dp(20), dp(120)], spacing=dp(15))
        self.sys_info_labels = {}
        self.sys_info_widgets = {}
        info_card = self._create_info_card()
        info_card.size_hint_y = None
        info_card.height = dp(120)
        sys_info_layout.add_widget(info_card)
        resources_card, self.resources_layout = self._create_resources_card()
        sys_info_layout.add_widget(resources_card)
        self.sys_info_tab.add_widget(sys_info_layout)
        self.tab_panel.add_widget(self.sys_info_tab)

        settings_tab = TabbedPanelItem(text='Paramètres')
        root_layout = BoxLayout(padding=dp(30), orientation='vertical')
        quality_card = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(180), padding=dp(20), spacing=dp(10))
        with quality_card.canvas.before:
            Color(rgba=get_color_from_hex('#2C2F33'))
            self.quality_card_rect = RoundedRectangle(size=quality_card.size, pos=quality_card.pos, radius=[dp(15)])
        quality_card.bind(pos=lambda i, v: setattr(self.quality_card_rect, 'pos', v), size=lambda i, v: setattr(self.quality_card_rect, 'size', v))
        title_label = Label(text='Qualité de l\'image', font_size='18sp', bold=True, size_hint_y=None, height=dp(30), halign='left', color=get_color_from_hex('#FFFFFF'))
        title_label.bind(width=lambda i, v: setattr(i, 'text_size', (v, None)))
        quality_card.add_widget(title_label)
        description_label = Label(text='Ajuste la qualité pour équilibrer performance et bande passante.', font_size='12sp', size_hint_y=None, height=dp(20), halign='left', color=get_color_from_hex('#99AAB5'))
        description_label.bind(width=lambda i, v: setattr(i, 'text_size', (v, None)))
        quality_card.add_widget(description_label)
        slider_layout = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(10))
        quality_slider = Slider(min=10, max=95, value=70, step=5, value_track=True, value_track_color=get_color_from_hex('#5865F2'), cursor_size=(dp(20), dp(20)))
        self.quality_label = Label(text='70%', size_hint_x=None, width=dp(50), color=get_color_from_hex('#FFFFFF'))
        def update_quality(instance, value):
            v = int(value)
            self.send_quality_setting(v)
            self.quality_label.text = f"{v}%"
        quality_slider.bind(value=update_quality)
        slider_layout.add_widget(quality_slider)
        slider_layout.add_widget(self.quality_label)
        quality_card.add_widget(slider_layout)
        
        share_button = Button(text='Partager l\'accès à distance', on_press=self.generate_share_code, size_hint_y=None, height=dp(50))
        quality_card.add_widget(share_button)

        root_layout.add_widget(quality_card)
        root_layout.add_widget(BoxLayout())
        settings_tab.add_widget(root_layout)
        self.tab_panel.add_widget(settings_tab)

        self.transfer_tab = TabbedPanelItem(text='Transferts')
        main_transfer_layout = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        remote_files_card = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(5))
        with remote_files_card.canvas.before:
            Color(rgba=get_color_from_hex('#2C2F33'))
            remote_files_card.rect = RoundedRectangle(size=remote_files_card.size, pos=remote_files_card.pos, radius=[dp(15)])
        remote_files_card.bind(pos=lambda i, v: setattr(remote_files_card.rect, 'pos', v), size=lambda i, v: setattr(remote_files_card.rect, 'size', v))
        toolbar = BoxLayout(size_hint_y=None, height=dp(40), padding=(dp(5), 0), spacing=dp(10))
        up_button = Button(text='⬆', font_name='seguisym.ttf', font_size='20sp', on_press=self.go_up_dir, size_hint_x=None, width=dp(40))
        self.remote_path_label = Label(text='/', halign='left', valign='middle', color=get_color_from_hex('#FFFFFF'))
        self.remote_path_label.bind(size=self.remote_path_label.setter('text_size'))
        refresh_button = Button(text='⟳', font_name='seguisym.ttf', font_size='20sp', on_press=lambda i: self.list_remote_dir(self.current_remote_path), size_hint_x=None, width=dp(40))
        toolbar.add_widget(up_button)
        toolbar.add_widget(self.remote_path_label)
        toolbar.add_widget(refresh_button)
        remote_files_card.add_widget(toolbar)
        self.file_search_input = TextInput(hint_text="Rechercher...", multiline=False, size_hint_y=None, height=dp(35))
        self.file_search_input.bind(text=self.filter_remote_files)
        remote_files_card.add_widget(self.file_search_input)
        header = BoxLayout(size_hint_y=None, height=dp(30), padding=(dp(10), 0))
        header.add_widget(Label(text='', size_hint_x=None, width=dp(30)))
        header.add_widget(Label(text='Nom', bold=True, halign='left', color=get_color_from_hex('#99AAB5')))
        header.add_widget(Label(text='Taille', bold=True, size_hint_x=None, width=dp(80), halign='right', color=get_color_from_hex('#99AAB5')))
        remote_files_card.add_widget(header)
        self.file_browser_grid = GridLayout(cols=1, size_hint_y=None)
        self.file_browser_grid.bind(minimum_height=self.file_browser_grid.setter('height'))
        scroll_view_files = ScrollView()
        scroll_view_files.add_widget(self.file_browser_grid)
        remote_files_card.add_widget(scroll_view_files)
        transfer_controls_card = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(180), padding=dp(20), spacing=dp(10))
        with transfer_controls_card.canvas.before:
            Color(rgba=get_color_from_hex('#23272A'))
            transfer_controls_card.rect = RoundedRectangle(size=transfer_controls_card.size, pos=transfer_controls_card.pos, radius=[dp(15)])
        transfer_controls_card.bind(pos=lambda i, v: setattr(transfer_controls_card.rect, 'pos', v), size=lambda i, v: setattr(transfer_controls_card.rect, 'size', v))
        transfer_controls_card.add_widget(Label(text='Contrôle des Transferts', font_size='16sp', bold=True, size_hint_y=None, height=dp(30), color=get_color_from_hex('#FFFFFF')))
        self.transfer_status_label = Label(text='Prêt.', size_hint_y=None, height=dp(25), color=get_color_from_hex('#99AAB5'), font_size='12sp')
        transfer_controls_card.add_widget(self.transfer_status_label)
        self.transfer_progress_bar = ColorProgressBar(max=100, size_hint_y=None, height=dp(15))
        transfer_controls_card.add_widget(self.transfer_progress_bar)
        buttons_layout = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(15), padding=(0, dp(10), 0, 0))
        send_file_button = Button(text='Envoyer un fichier...', on_press=self.choose_and_upload_file, font_size='16sp', background_color=(0,0,0,0))
        with send_file_button.canvas.before:
            Color(rgba=get_color_from_hex('#5865F2'))
            send_file_button.rect = RoundedRectangle(size=send_file_button.size, pos=send_file_button.pos, radius=[dp(8)])
        send_file_button.bind(pos=lambda i, v: setattr(send_file_button.rect, 'pos', v), size=lambda i, v: setattr(send_file_button.rect, 'size', v))
        self.cancel_button = Button(text='Annuler', on_press=self.cancel_transfer, disabled=True, font_size='16sp', background_color=(0,0,0,0), size_hint_x=0.5)
        with self.cancel_button.canvas.before:
            Color(rgba=get_color_from_hex('#40444B'))
            self.cancel_button.rect = RoundedRectangle(size=self.cancel_button.size, pos=self.cancel_button.pos, radius=[dp(8)])
        self.cancel_button.bind(pos=lambda i, v: setattr(self.cancel_button.rect, 'pos', v), size=lambda i, v: setattr(self.cancel_button.rect, 'size', v))
        buttons_layout.add_widget(send_file_button)
        buttons_layout.add_widget(self.cancel_button)
        transfer_controls_card.add_widget(buttons_layout)
        main_transfer_layout.add_widget(remote_files_card)
        main_transfer_layout.add_widget(transfer_controls_card)
        self.transfer_tab.add_widget(main_transfer_layout)
        self.tab_panel.add_widget(self.transfer_tab)

        self.chat_tab = TabbedPanelItem(text='Chat')
        chat_layout = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(5))
        self.chat_history_label = Label(text='', halign='left', valign='top', size_hint_y=None, markup=True)
        self.chat_history_label.bind(width=lambda instance, value: setattr(instance, 'text_size', (value, None)), texture_size=self.chat_history_label.setter('size'))
        chat_scroll_view = ScrollView(size_hint=(1, 1))
        chat_scroll_view.add_widget(self.chat_history_label)
        chat_input_layout = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(5))
        self.chat_input = TextInput(multiline=False, hint_text='Tapez votre message ici...')
        send_button = Button(text='Envoyer', size_hint_x=None, width=dp(80), on_press=self.send_chat_message)
        chat_input_layout.add_widget(self.chat_input)
        chat_input_layout.add_widget(send_button)
        for widget in [chat_scroll_view, chat_input_layout]:
            chat_layout.add_widget(widget)
        self.chat_tab.add_widget(chat_layout)
        self.tab_panel.add_widget(self.chat_tab)

        about_tab = TabbedPanelItem(text='À propos')
        about_layout = BoxLayout(orientation='vertical', padding=dp(30), spacing=dp(20))
        title_card = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(220), padding=dp(20), spacing=dp(15))
        with title_card.canvas.before:
            Color(rgba=get_color_from_hex('#2C2F33'))
            title_card.rect = RoundedRectangle(size=title_card.size, pos=title_card.pos, radius=[dp(15)])
        title_card.bind(pos=lambda i, v: setattr(title_card.rect, 'pos', v), size=lambda i, v: setattr(title_card.rect, 'size', v))
        logo = Image(source='logo.ico', size_hint_y=None, height=dp(80), allow_stretch=True)
        title_label = Label(text='[b]Hosanna Remote Viewer[/b]', markup=True, font_size='24sp', size_hint_y=None, height=dp(40), color=get_color_from_hex('#FFFFFF'))
        version_label = Label(text='Version 1.0.0', font_size='14sp', size_hint_y=None, height=dp(20), color=get_color_from_hex('#99AAB5'))
        title_card.add_widget(logo)
        title_card.add_widget(title_label)
        title_card.add_widget(version_label)
        about_layout.add_widget(title_card)
        info_card = BoxLayout(orientation='vertical', size_hint_y=None, padding=dp(20), spacing=dp(10))
        info_card.bind(minimum_height=info_card.setter('height'))
        with info_card.canvas.before:
            Color(rgba=get_color_from_hex('#2C2F33'))
            info_card.rect = RoundedRectangle(size=info_card.size, pos=info_card.pos, radius=[dp(15)])
        info_card.bind(pos=lambda i, v: setattr(info_card.rect, 'pos', v), size=lambda i, v: setattr(info_card.rect, 'size', v))
        info_card.add_widget(Label(text='[b]Développé par :[/b] Chadrack Mbu Jess', markup=True, font_size='16sp', size_hint_y=None, height=dp(30), color=get_color_from_hex('#FFFFFF')))
        info_card.add_widget(Label(text='© 2025', markup=True, font_size='16sp', size_hint_y=None, height=dp(30), color=get_color_from_hex('#99AAB5')))
        desc_title = Label(text='[b]Description :[/b]', markup=True, font_size='16sp', size_hint_y=None, height=dp(40), color=get_color_from_hex('#FFFFFF'), halign='left')
        desc_title.bind(width=lambda i, v: setattr(i, 'text_size', (v, None)))
        info_card.add_widget(desc_title)
        description = Label(text='Une application de bureau à distance sécurisée et performante, conçue pour offrir un contrôle fluide et un accès facile à vos fichiers et informations système.', font_size='14sp', color=get_color_from_hex('#99AAB5'), halign='left', valign='top')
        description.bind(width=lambda i, v: setattr(i, 'text_size', (v, None)))
        info_card.add_widget(description)
        about_layout.add_widget(info_card)
        about_layout.add_widget(BoxLayout())
        about_tab.add_widget(about_layout)
        self.tab_panel.add_widget(about_tab)

        self.tab_panel.default_tab = self.desktop_tab
        remote_screen.add_widget(self.tab_panel)
        self.sm.add_widget(connect_screen)
        self.sm.add_widget(remote_screen)
        return self.sm

    def _create_info_card(self):
        card = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(2))
        with card.canvas.before:
            Color(rgba=get_color_from_hex('#2C2F33'))
            card.rect = RoundedRectangle(size=card.size, pos=card.pos, radius=[dp(15)])
        card.bind(pos=lambda i, v: setattr(card.rect, 'pos', v), size=lambda i, v: setattr(card.rect, 'size', v))
        card.add_widget(Label(text='Informations Générales', font_size='18sp', bold=True, size_hint_y=None, height=dp(30), color=get_color_from_hex('#FFFFFF')))
        grid = GridLayout(cols=2, spacing=dp(2))
        info_keys = {"node_name": "Nom", "user_name": "Utilisateur", "os_version": "OS", "architecture": "Arch"}
        for key, name in info_keys.items():
            grid.add_widget(Label(text=f"{name}:", halign='right', font_size='12sp', color=get_color_from_hex('#99AAB5')))
            self.sys_info_labels[key] = Label(text="-", halign='left', font_size='12sp', color=get_color_from_hex('#FFFFFF'))
            grid.add_widget(self.sys_info_labels[key])
        card.add_widget(grid)
        return card

    def _create_resources_card(self):
        card = BoxLayout(orientation='vertical', size_hint_y=None, padding=dp(15), spacing=dp(5))
        card.bind(minimum_height=card.setter('height'))
        with card.canvas.before:
            Color(rgba=get_color_from_hex('#2C2F33'))
            card.rect = RoundedRectangle(size=card.size, pos=card.pos, radius=[dp(15)])
        card.bind(pos=lambda i, v: setattr(card.rect, 'pos', v), size=lambda i, v: setattr(card.rect, 'size', v))
        card.add_widget(Label(text='Ressources Système', font_size='18sp', bold=True, size_hint_y=None, height=dp(30), color=get_color_from_hex('#FFFFFF')))
        resources_layout = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(10))
        resources_layout.bind(minimum_height=resources_layout.setter('height'))
        cpu_layout = self._create_resource_section('cpu', 'Utilisation CPU')
        resources_layout.add_widget(cpu_layout)
        ram_layout = self._create_resource_section('ram', 'Utilisation RAM')
        resources_layout.add_widget(ram_layout)
        self.disk_grid = GridLayout(cols=2, size_hint_y=None, spacing=dp(10))
        self.disk_grid.bind(minimum_height=self.disk_grid.setter('height'))
        resources_layout.add_widget(self.disk_grid)
        card.add_widget(resources_layout)
        return card, resources_layout

    def _create_resource_section(self, key, title):
        section = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(65), spacing=dp(2))
        title_layout = BoxLayout(size_hint_y=None, height=dp(20))
        title_label = Label(text=title, font_size='14sp', halign='left', color=get_color_from_hex('#FFFFFF'))
        title_label.bind(text_size=lambda i, ts: setattr(i, 'width', ts[0]))
        title_layout.add_widget(title_label)
        if key == 'cpu':
            freq_label = Label(text="Freq: -", size_hint_x=None, width=dp(150), font_size='12sp', halign='right', color=get_color_from_hex('#99AAB5'))
            self.sys_info_widgets['cpu_freq'] = freq_label
            title_layout.add_widget(freq_label)
        section.add_widget(title_layout)
        bar = ColorProgressBar(max=100, size_hint_y=None, height=dp(10))
        percent_label = Label(text="0%", size_hint_y=None, height=dp(20), font_size='12sp', halign='left', color=get_color_from_hex('#FFFFFF'))
        percent_label.bind(text_size=lambda i, ts: setattr(i, 'width', ts[0]))
        self.sys_info_widgets[key] = {'bar': bar, 'percent': percent_label}
        section.add_widget(bar)
        section.add_widget(percent_label)
        return section

    def on_tab_switch(self, instance, value):
        if value == self.desktop_tab:
            self.remote_widget.setup_keyboard()
            self.stop_camera_stream()
        else:
            self.remote_widget.release_keyboard()
        if value == self.camera_tab:
            pass
        else:
            self.stop_camera_stream()
        if value == self.sys_info_tab: self.start_sys_info_updates()
        else: self.stop_sys_info_updates()

    def on_camera_selection_text(self, spinner, text):
        try:
            index = int(text.split(' ')[1])
            self.select_camera(index)
        except (ValueError, IndexError):
            print(f"Invalid camera selection text: {text}")

    def select_camera(self, index):
        if self.selected_camera_index != index:
            self.selected_camera_index = index
            print(f"Client selected camera index: {index}")
            if self.remote_widget.client_socket:
                self.remote_widget.send_command(f"SELECT_CAMERA,{index}")
            if self.is_camera_streaming:
                self.stop_camera_stream()
                self.start_camera_stream(None)

    def start_camera_stream(self, instance):
        if not self.is_camera_streaming and self.selected_camera_index != -1:
            self.remote_camera_widget.send_command("START_CAMERA")
            self.remote_camera_widget.send_command(f"SELECT_CAMERA,{self.selected_camera_index}")
            self.is_camera_streaming = True
            self.start_camera_button.disabled = True
            self.stop_camera_button.disabled = True
            self.remote_widget.send_command("STOP_SCREEN")
        elif self.selected_camera_index == -1:
            print("[!] Impossible de démarrer le streaming: aucune caméra disponible.")

    def stop_camera_stream(self, instance=None):
        if self.is_camera_streaming:
            self.remote_camera_widget.send_command("STOP_CAMERA")
        self.is_camera_streaming = False
        self.start_camera_button.disabled = False
        self.stop_camera_button.disabled = True
        self.remote_camera_widget.texture = self.camera_placeholder_image.texture
        if self.remote_widget.client_socket:
            self.remote_widget.send_command("START_SCREEN")

    def start_sys_info_updates(self):
        if not self.sys_info_update_event:
            self._request_sys_info_thread()
            self.sys_info_update_event = Clock.schedule_interval(lambda dt: self._request_sys_info_thread(), 1)

    def stop_sys_info_updates(self):
        if self.sys_info_update_event:
            self.sys_info_update_event.cancel()
            self.sys_info_update_event = None

    def _get_file_transfer_address(self):
        # If file_server_address is set (remote connection), use it
        if self.file_server_address:
            return self.file_server_address[0], self.file_server_address[1]
        # Otherwise, use the local IP/Port from the input fields
        if self.main_server_address: # If main_server_address is set (local connection)
            return self.main_server_address[0], self.main_server_address[1] - 1
        # Fallback if no connection info is available (shouldn't happen if connected)
        return self.ip_input.text, int(self.port_input.text) - 1

    def _request_sys_info_thread(self): threading.Thread(target=self._get_sys_info_from_server, daemon=True).start()

    def _get_sys_info_from_server(self):
        try:
            host, file_port = self._get_file_transfer_address()
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
        except Exception: Clock.schedule_once(lambda dt: self.stop_sys_info_updates())

    def _update_sys_info_ui(self, data):
        if 'error' in data:
            self.sys_info_labels['node_name'].text = f"Erreur: {data['error']}"
            return
        for key, label in self.sys_info_labels.items():
            label.text = str(data.get(key, '-'))
        cpu_info = data.get('cpu', {})
        cpu_usage = cpu_info.get('usage', 0)
        self.sys_info_widgets['cpu']['bar'].value = cpu_usage
        self.sys_info_widgets['cpu']['percent'].text = f"{cpu_usage:.1f}%"
        if cpu_usage >= 95: self.sys_info_widgets['cpu']['bar'].bar_color = (1, 0, 0.15, 1)
        elif cpu_usage >= 80: self.sys_info_widgets['cpu']['bar'].bar_color = (1, 0.65, 0, 1)
        else: self.sys_info_widgets['cpu']['bar'].bar_color = (0, 0.55, 1, 1)
        freq_current = cpu_info.get('freq_current', 0)
        freq_max = cpu_info.get('freq_max', 0)
        freq_text = "Freq: "
        if freq_current > 0: freq_text += f"{freq_current / 1000:.2f} GHz"
        if freq_max > 0: freq_text += f" (Max: {freq_max / 1000:.2f} GHz)"
        self.sys_info_widgets['cpu_freq'].text = freq_text
        ram_info = data.get('ram', {})
        ram_percent = ram_info.get('percent', 0)
        self.sys_info_widgets['ram']['bar'].value = ram_percent
        self.sys_info_widgets['ram']['percent'].text = f"{ram_percent:.1f}% ({sizeof_fmt(ram_info.get('used',0))} / {sizeof_fmt(ram_info.get('total',0))})"
        if ram_percent >= 95: self.sys_info_widgets['ram']['bar'].bar_color = (1, 0, 0.15, 1)
        elif ram_percent >= 80: self.sys_info_widgets['ram']['bar'].bar_color = (1, 0.65, 0, 1)
        else: self.sys_info_widgets['ram']['bar'].bar_color = (0, 0.55, 1, 1)
        for disk in data.get('disks', []):
            disk_id = disk['device']
            if disk_id not in self.sys_info_widgets:
                disk_section = self._create_resource_section(disk_id, f"Disque: {disk.get('mountpoint', disk_id)}")
                self.disk_grid.add_widget(disk_section)
            disk_percent = disk.get('percent', 0)
            self.sys_info_widgets[disk_id]['bar'].value = disk_percent
            self.sys_info_widgets[disk_id]['percent'].text = f"{disk_percent:.1f}% ({sizeof_fmt(disk.get('used',0))} / {sizeof_fmt(disk.get('total',0))})"
            if disk_percent >= 95: self.sys_info_widgets[disk_id]['bar'].bar_color = (1, 0, 0.3, 1)
            elif disk_percent >= 80: self.sys_info_widgets[disk_id]['bar'].bar_color = (1, 0.65, 0, 1)
            else: self.sys_info_widgets[disk_id]['bar'].bar_color = (0, 0.55, 1, 1)

    def cancel_transfer(self, instance): self.cancel_transfer_flag.set()

    def on_file_selection(self, filename, is_dir):
        if self.current_remote_path == "" and not filename.endswith(':\\'):
             full_path = os.path.join(self.current_remote_path, filename).replace('\\', '/')
        else:
             full_path = filename if self.current_remote_path == "" else os.path.join(self.current_remote_path, filename).replace('\\', '/')
        if is_dir: self.list_remote_dir(full_path)
        else: self.choose_and_download_file(full_path, filename)

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
            host, file_port = self._get_file_transfer_address()
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
            Clock.schedule_once(lambda dt, err=e: setattr(self.transfer_status_label, 'text', f"Erreur: {err}"))

    def update_file_browser(self, data):
        if 'error' in data and data['error']: self.transfer_status_label.text = f"Erreur distante: {data['error']}"
        else: self.transfer_status_label.text = "Prêt."
        self.current_remote_path = data.get('path', self.current_remote_path)
        self.remote_path_label.text = f"/{self.current_remote_path}"
        self.current_dir_entries = data.get('entries', [])
        self.file_search_input.text = ""
        self.filter_remote_files(self.file_search_input, "")

    def filter_remote_files(self, instance, search_text=""):
        search_text = instance.text.lower()
        self.file_browser_grid.clear_widgets()
        for entry in self.current_dir_entries:
            if search_text in entry['name'].lower():
                widget = FileEntryWidget(name=entry['name'], is_dir=entry['is_dir'], file_size="" if entry['is_dir'] else sizeof_fmt(entry.get('size', 0)))
                self.file_browser_grid.add_widget(widget)

    def choose_and_upload_file(self, instance):
        Tk().withdraw()
        file_path = filedialog.askopenfilename(title="Choisir un fichier à envoyer", initialdir=expanduser("~"))
        if file_path:
            self.cancel_transfer_flag.clear()
            threading.Thread(target=self._upload_file_thread, args=(file_path,), daemon=True).start()

    def _upload_file_thread(self, file_path):
        def update_status(text): Clock.schedule_once(lambda dt: setattr(self.transfer_status_label, 'text', text))
        def update_progress(value): Clock.schedule_once(lambda dt: setattr(self.transfer_progress_bar, 'value', value))
        Clock.schedule_once(lambda dt: setattr(self.cancel_button, 'disabled', False))
        try:
            filename, filesize = os.path.basename(file_path), os.path.getsize(file_path)
            update_status(f"Envoi de {filename}..."); update_progress(0)
            host, file_port = self._get_file_transfer_address()
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
            if not self.cancel_transfer_flag.is_set(): update_status(f"Erreur: {e}"); update_progress(0)
        finally:
            Clock.schedule_once(lambda dt: setattr(self.cancel_button, 'disabled', True))
            self.cancel_transfer_flag.clear()

    def choose_and_download_file(self, remote_path, filename):
        Tk().withdraw()
        save_path = filedialog.asksaveasfilename(title="Enregistrer le fichier sous...", initialdir=expanduser("~"), initialfile=filename)
        if save_path:
            self.cancel_transfer_flag.clear()
            threading.Thread(target=self._download_file_thread, args=(remote_path, save_path), daemon=True).start()

    def _download_file_thread(self, remote_path, save_path):
        def update_status(text): Clock.schedule_once(lambda dt: setattr(self.transfer_status_label, 'text', text))
        def update_progress(value): Clock.schedule_once(lambda dt: setattr(self.transfer_progress_bar, 'value', value))
        Clock.schedule_once(lambda dt: setattr(self.cancel_button, 'disabled', False))
        try:
            update_status(f"Téléchargement de {os.path.basename(remote_path)}..."); update_progress(0)
            host, file_port = self._get_file_transfer_address()
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
                            update_status("Téléchargement annulé."); update_progress(0)
                            return
                        chunk_size = min(65536, filesize - bytes_received)
                        chunk = secure_sock.recv(chunk_size)
                        if not chunk:
                            if bytes_received < filesize: update_status("Erreur: Connexion perdue pendant le téléchargement.")
                            break
                        f.write(chunk)
                        bytes_received += len(chunk)
                        update_progress((bytes_received / filesize) * 100)
                if self.cancel_transfer_flag.is_set():
                    if os.path.exists(save_path): os.remove(save_path)
                elif bytes_received == filesize:
                    update_status(f"Téléchargé: {os.path.basename(save_path)}"); update_progress(100)
                else:
                    update_status("Erreur de téléchargement inattendue."); update_progress(0)
                    if os.path.exists(save_path): os.remove(save_path)
        except Exception as e:
            if not self.cancel_transfer_flag.is_set(): update_status(f"Erreur: {e}"); update_progress(0)
        finally:
            Clock.schedule_once(lambda dt: setattr(self.cancel_button, 'disabled', True))
            self.cancel_transfer_flag.clear()

    def send_quality_setting(self, quality_value):
        if self.remote_widget.client_socket:
            try:
                self.remote_widget.send_command(f"QUALITY,{quality_value}")
            except Exception as e:
                print(f"[!] Erreur lors de l'envoi de la qualité: {e}")

    def send_clipboard_to_server(self, content):
        if self.remote_widget.client_socket:
            try:
                command_str = f"CLIPBOARD_DATA,{content}"
                command_bytes = command_str.encode('utf-8')
                len_info = struct.pack("!H", len(command_bytes))
                self.remote_widget.client_socket.sendall(MSG_TYPE_COMMAND + len_info + command_bytes)
            except (BrokenPipeError, ConnectionResetError): pass
            except Exception as e: print(f"[!] Erreur lors de l'envoi du presse-papiers au serveur: {e}")

    def send_chat_message(self, instance):
        message = self.chat_input.text.strip()
        if message:
            if self.remote_widget.client_socket:
                try:
                    command_str = f"CHAT_MESSAGE,{message}"
                    command_bytes = command_str.encode('utf-8')
                    len_info = struct.pack("!H", len(command_bytes))
                    self.remote_widget.client_socket.sendall(MSG_TYPE_COMMAND + len_info + command_bytes)
                    self.add_message_to_chat_history(f"[b][color=00BFFF]Moi:[/color][/b] {message}")
                    self.chat_input.text = ''
                except (BrokenPipeError, ConnectionResetError): self.add_message_to_chat_history("[b][color=FF0000]Erreur:[/color][/b] Serveur déconnecté.")
                except Exception as e: print(f"[!] Erreur lors de l'envoi du presse-papiers au serveur: {e}")
            else: self.add_message_to_chat_history("[b][color=FF0000]Erreur:[/color][/b] Non connecté au serveur.")

    def add_message_to_chat_history(self, message):
        self.chat_history_messages.append(message)
        if len(self.chat_history_messages) > 100: self.chat_history_messages = self.chat_history_messages[-100:]
        Clock.schedule_once(lambda dt: self._update_chat_history_ui_text())

    def _update_chat_history_ui_text(self):
        self.chat_history_label.text = '\n'.join(self.chat_history_messages)
        if self.chat_history_label.parent and isinstance(self.chat_history_label.parent, ScrollView):
            self.chat_history_label.parent.scroll_y = 0

    def monitor_clipboard_changes(self):
        pythoncom.CoInitialize()
        try:
            self.last_clipboard_content = pyperclip.paste()
            while not self.clipboard_stop_event.is_set():
                current_clipboard = pyperclip.paste()
                if current_clipboard != self.last_clipboard_content and current_clipboard != self.last_clipboard_content_from_server:
                    self.last_clipboard_content = current_clipboard
                    self.send_clipboard_to_server(current_clipboard)
                time.sleep(0.5)
        except Exception as e: print(f"[!] Erreur dans monitor_clipboard_changes: {e}")
        finally: pythoncom.CoUninitialize()

    def discover_server(self, instance):
        self.status_label.text = "Recherche d'un serveur..."
        threading.Thread(target=self._discover_server_thread, daemon=True).start()

    def _discover_server_thread(self):
        discovery_port = 9998
        broadcast_address = '<broadcast>'
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        client_socket.settimeout(3.0)
        try:
            message = "HOSANNA_REMOTE_DISCOVERY_REQUEST".encode('utf-8')
            client_socket.sendto(message, (broadcast_address, discovery_port))
            data, server_address = client_socket.recvfrom(1024)
            response = data.decode('utf-8')
            if response == "HOSANNA_REMOTE_DISCOVERY_RESPONSE":
                server_ip = server_address[0]
                Clock.schedule_once(lambda dt: self.update_ip_address(server_ip))
            else: Clock.schedule_once(lambda dt: setattr(self.status_label, 'text', "Réponse inattendue du serveur."))
        except socket.timeout: Clock.schedule_once(lambda dt: setattr(self.status_label, 'text', "Aucun serveur trouvé sur le réseau."))
        except Exception as e:
            Clock.schedule_once(lambda dt, err=e: setattr(self.status_label, 'text', f"Erreur: {err}"))
        finally: client_socket.close()

    def update_ip_address(self, ip):
        self.ip_input.text = ip
        self.status_label.text = f"Serveur trouvé à l'adresse {ip} !"

    def connect_to_server(self, instance):
        active_tab = self.connection_tabs.current_tab
        if active_tab == self.local_tab:
            host = self.ip_input.text.strip()
            port_str = self.port_input.text.strip()
            if not host or not port_str:
                self.status_label.text = "L'adresse IP et le port sont requis."
                return
            try:
                port = int(port_str)
            except ValueError:
                self.status_label.text = "Le port doit être un nombre valide."
                return
            self.main_server_address = (host, port)
            self.file_server_address = (host, port - 1) # For local, file port is main_port - 1
            self.status_label.text = f"Connexion à {host}:{port}..."
            threading.Thread(target=self.receive_frames, args=(host, port), daemon=True).start()
        
        elif active_tab == self.remote_tab:
            host = self.remote_address_input.text.strip()
            port_str = self.remote_port_input.text.strip()
            if not host or not port_str:
                self.status_label.text = "L'adresse et le port publics sont requis."
                return
            try:
                port = int(port_str)
            except ValueError:
                self.status_label.text = "Le port public doit être un nombre valide."
                return
            # For remote, main_server_address and file_server_address will be set by SHARE_INFO_GENERATED
            # We connect to the main port first, and the server will send us the file port info
            self.main_server_address = (host, port)
            self.file_server_address = None # Will be updated by server
            self.status_label.text = f"Connexion à {host}:{port}..."
            threading.Thread(target=self.receive_frames, args=(host, port), daemon=True).start()

    def generate_share_code(self, instance):
        if self.remote_widget.client_socket:
            self.remote_widget.send_command("GENERATE_SHARE_CODE")
            self.status_label.text = "Génération des informations de partage..."

    def show_share_code_popup(self, main_address, main_port): # Simplified to show only main info
        content = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        title = 'Informations de Partage'
        
        main_addr_label = Label(text=f"[b]Adresse:[/b] {main_address}", markup=True, font_size='20sp')
        main_port_label = Label(text=f"[b]Port:[/b] {main_port}", markup=True, font_size='20sp')
        info_label = Label(text="Communiquez ces informations à l'utilisateur distant.", text_size=(dp(350), None), halign='center')
        
        content.add_widget(main_addr_label)
        content.add_widget(main_port_label)
        content.add_widget(info_label)
        
        popup = Popup(title=title, content=content, size_hint=(None, None), size=(dp(400), dp(220)))
        popup.open()

    def receive_frames(self, host, port):
        context = ssl.create_default_context(); context.check_hostname = False; context.verify_mode = ssl.CERT_NONE
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            client_socket = context.wrap_socket(sock, server_hostname=host)
            client_socket.connect((host, port))
            client_socket.settimeout(None)
            self.remote_widget.client_socket = client_socket
            self.remote_camera_widget.client_socket = client_socket
            self.send_quality_setting(70)
            Clock.schedule_once(self.switch_to_remote_screen)
            self.clipboard_stop_event.clear()
            threading.Thread(target=self.monitor_clipboard_changes, daemon=True).start()
        except ConnectionRefusedError:
            Clock.schedule_once(lambda dt: self.show_connection_error("Connexion refusée. Vérifiez l'IP, le port et le statut du serveur."))
        except socket.timeout:
            Clock.schedule_once(lambda dt: self.show_connection_error("Délai de connexion dépassé. Le serveur ne répond pas."))
        except socket.gaierror:
            Clock.schedule_once(lambda dt: self.show_connection_error("Adresse IP ou nom d'hôte invalide."))
        except Exception as e:
            Clock.schedule_once(lambda dt, err=str(e): self.show_connection_error(f"Erreur inattendue: {err}"))
        else:
            while True:
                try:
                    msg_type_byte = self.recv_all(self.remote_widget.client_socket, 1)
                    if not msg_type_byte: break
                    if msg_type_byte == MSG_TYPE_IMAGE:
                        len_info = self.recv_all(self.remote_widget.client_socket, 4)
                        if not len_info: break
                        payload_size = struct.unpack("!I", len_info)[0]
                        payload = self.recv_all(self.remote_widget.client_socket, payload_size)
                        if not payload: break
                        width, height = struct.unpack("!II", payload[:struct.calcsize("!II")])
                        self.remote_widget.server_resolution = (width, height)
                        Clock.schedule_once(lambda dt, data=payload[struct.calcsize("!II"):]: self.update_image(data))
                    elif msg_type_byte == MSG_TYPE_CAMERA:
                        len_info = self.recv_all(self.remote_camera_widget.client_socket, 4)
                        if not len_info: break
                        payload_size = struct.unpack("!I", len_info)[0]
                        payload = self.recv_all(self.remote_camera_widget.client_socket, payload_size)
                        if not payload: break
                        width, height = struct.unpack("!II", payload[:struct.calcsize("!II")])
                        self.remote_camera_widget.camera_resolution = (width, height)
                        Clock.schedule_once(lambda dt, data=payload[struct.calcsize("!II"):]: self.update_camera_feed(data))
                    elif msg_type_byte == MSG_TYPE_COMMAND:
                        len_info = self.recv_all(self.remote_widget.client_socket, 2)
                        if not len_info: break
                        cmd_len = struct.unpack("!H", len_info)[0]
                        command_data = self.recv_all(self.remote_widget.client_socket, cmd_len)
                        if not command_data: break
                        command = command_data.decode('utf-8')
                        parts = command.split(',', 1)
                        cmd_type = parts[0]
                        value_str = parts[1] if len(parts) > 1 else ""
                        
                        if cmd_type == 'SHARE_INFO_GENERATED':
                            # Split value_str into main_address, main_port, file_address, file_port
                            share_parts = value_str.split(',')
                            if len(share_parts) == 4:
                                main_addr, main_p, file_addr, file_p = share_parts
                                self.main_server_address = (main_addr, int(main_p))
                                self.file_server_address = (file_addr, int(file_p)) # Store file tunnel info
                                Clock.schedule_once(lambda dt: self.show_share_code_popup(main_addr, main_p)) # Only show main info
                            else:
                                print(f"[!] Erreur: Format SHARE_INFO_GENERATED inattendu: {value_str}")
                                Clock.schedule_once(lambda dt: self.show_connection_error("Erreur de partage: Format de données invalide."))
                        elif cmd_type == 'SHARE_INFO_ERROR':
                            self.show_connection_error(f"Erreur de partage: {value_str}")
                        elif cmd_type == 'FILE_TUNNEL_INFO': # New command to receive file tunnel info
                            file_addr, file_p = value_str.split(',')
                            self.file_server_address = (file_addr, int(file_p))
                            print(f"[*] Reçu les infos du tunnel de fichiers: {self.file_server_address}")
                            # If we are already on the remote screen, we might need to refresh file browser
                            if self.sm.current == 'remote':
                                Clock.schedule_once(lambda dt: self.list_remote_dir(self.current_remote_path))
                        elif cmd_type == 'CLIPBOARD_UPDATE':
                            content = value_str
                            try:
                                pyperclip.copy(content)
                                self.last_clipboard_content = content
                                self.last_clipboard_content_from_server = content
                            except Exception as e: print(f"[!] Erreur lors de la mise à jour du presse-papiers client: {e}")
                        elif cmd_type == 'CHAT_MESSAGE_FROM_SERVER':
                            message = value_str
                            self.add_message_to_chat_history(f"[b][color=00FF00]Serveur:[/color][/b] {message}")
                        elif cmd_type == 'CAMERA_LIST':
                            try:
                                camera_indices = json.loads(value_str)
                                Clock.schedule_once(lambda dt: self.update_available_cameras(camera_indices))
                            except json.JSONDecodeError as e:
                                print(f"[!] Erreur de décodage de la liste des caméras: {e}")
                        else: pass
                    else: break
                except (ConnectionResetError, BrokenPipeError, ssl.SSLEOFError) as e:
                    print(f"[!] Connexion interrompue: {e}")
                    break
                except Exception as e: print(f"[!] Erreur inattendue dans receive_frames: {e}"); break
            if self.remote_widget.client_socket:
                self.remote_widget.client_socket.close()
                self.remote_widget.client_socket = None
                self.remote_camera_widget.client_socket = None
            Clock.schedule_once(self.switch_to_connect_screen)

    def update_available_cameras(self, camera_indices):
        self.available_cameras = [f"Caméra {i}" for i in camera_indices]
        if self.available_cameras:
            self.camera_selector.values = self.available_cameras
            if not self.camera_selector.text or self.camera_selector.text not in self.available_cameras:
                self.camera_selector.text = self.available_cameras[0]
                self.selected_camera_index = int(self.available_cameras[0].split(' ')[1])
                if self.remote_widget.client_socket:
                    self.remote_widget.send_command(f"SELECT_CAMERA,{self.selected_camera_index}")
        else:
            self.camera_selector.values = ["Aucune caméra"]
            self.camera_selector.text = "Aucune caméra"
            self.selected_camera_index = -1
            self.start_camera_button.disabled = True
            self.stop_camera_button.disabled = True
            print("[!] Aucune caméra détectée sur le serveur.")

    def switch_to_remote_screen(self, dt):
        self.sm.current = 'remote'
        self.remote_widget.setup_keyboard()
        self.list_remote_dir("")
        self.stop_camera_stream()

    def switch_to_connect_screen(self, dt):
        self.remote_widget.release_keyboard()
        self.clipboard_stop_event.set()
        if self.sm.current == 'remote':
            self.stop_camera_stream()
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
            except (socket.error, AttributeError, ssl.SSLEOFError) as e:
                print(f"[!] Erreur lors de la réception des données: {e}")
                return None
        return data

    def update_image(self, jpeg_bytes):
        try:
            buf = io.BytesIO(jpeg_bytes)
            core_image = CoreImage(buf, ext='jpg')
            self.remote_widget.texture = core_image.texture
        except Exception as e:
            print(f"[!] Erreur de décodage d'image (trame ignorée): {e}")

    def update_camera_feed(self, jpeg_bytes):
        if not self.is_camera_streaming:
            return
        try:
            buf = io.BytesIO(jpeg_bytes)
            core_image = CoreImage(buf, ext='jpg')
            self.remote_camera_widget.texture = core_image.texture
        except Exception as e:
            print(f"[!] Erreur de décodage de flux caméra (trame ignorée): {e}")

if __name__ == '__main__':
    RemoteViewerApp().run()
