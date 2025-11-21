import socket
import struct
import time
import io
import threading
import ssl
import sys
import os
import json
import ctypes
import platform
import psutil
from queue import Queue, Empty
from PIL import Image
import mss
from pynput.mouse import Button, Controller as MouseController
from pynput.keyboard import Key, Controller as KeyboardController
import pyperclip
import tkinter as tk
from tkinter import scrolledtext
import cv2
import subprocess
import re

# --- Fonction pour trouver les ressources (pour PyInstaller) ---
def resource_path(relative_path):
    """ Obtenir le chemin absolu de la ressource, fonctionne pour le dev et pour PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# --- Dictionnaire de touches (inchangé) ---
KEY_MAP = {
    'enter': Key.enter, 'shift': Key.shift, 'ctrl': Key.ctrl, 'alt': Key.alt,
    'esc': Key.esc, 'escape': Key.esc, 'space': Key.space, 'spacebar': Key.space,
    'backspace': Key.backspace, 'tab': Key.tab, 'delete': Key.delete,
    'up': Key.up, 'down': Key.down, 'left': Key.left, 'right': Key.right,
    'capslock': Key.caps_lock, 'numlock': Key.num_lock,
    'printscreen': Key.print_screen, 'scrolllock': Key.scroll_lock,
    'ctrl_l': Key.ctrl_l, 'ctrl_r': Key.ctrl_r, 'lctrl': Key.ctrl_l, 'rctrl': Key.ctrl_r,
    'shift_l': Key.shift_l, 'shift_r': Key.shift_r,
    'alt_l': Key.alt_l, 'alt_r': Key.alt_r, 'alt-gr': Key.alt_gr,
    'super': Key.cmd, 'win': Key.cmd,
    'f1': Key.f1, 'f2': Key.f2, 'f3': Key.f3, 'f4': Key.f4, 'f5': Key.f5,
    'f6': Key.f6, 'f7': Key.f7, 'f8': Key.f8, 'f9': Key.f9, 'f10': Key.f10,
    'f11': Key.f11, 'f12': Key.f12,
    'home': Key.home, 'end': Key.end, 'pageup': Key.page_up,
    'pagedown': Key.page_down, 'insert': Key.insert,
}

command_queue = Queue()
# Global storage for active bore tunnel info
active_bore_tunnels_info = {
    'main': {'process': None, 'address': None, 'port': None},
    'file': {'process': None, 'address': None, 'port': None}
}

def command_processor(stop_event):
    mouse_ctrl = MouseController()
    keyboard_ctrl = KeyboardController()
    while not stop_event.is_set():
        try:
            commands = [command_queue.get(timeout=0.02)]
            while not command_queue.empty():
                commands.append(command_queue.get_nowait())
            last_move = None
            other_commands = []
            for cmd in commands:
                if cmd[0] == 'MV':
                    last_move = cmd
                else:
                    other_commands.append(cmd)
            if last_move:
                mouse_ctrl.position = last_move[1]
            for cmd_type, value in other_commands:
                if cmd_type == 'MC':
                    btn_name, pressed = value
                    button = Button.left if btn_name == 'left' else Button.right
                    if pressed: mouse_ctrl.press(button)
                    else: mouse_ctrl.release(button)
                elif cmd_type == 'CLICK' or cmd_type == 'DBLCLICK':
                    x, y, btn_name = value
                    mouse_ctrl.position = (x, y)
                    button = Button.left if btn_name == 'left' else Button.right
                    click_count = 2 if cmd_type == 'DBLCLICK' else 1
                    mouse_ctrl.click(button, click_count)
                elif cmd_type == 'SCROLL':
                    x_offset, y_offset = value
                    mouse_ctrl.scroll(x_offset, y_offset)
                elif cmd_type == 'KP':
                    key = KEY_MAP.get(value, value)
                    keyboard_ctrl.press(key)
                elif cmd_type == 'KR':
                    key = KEY_MAP.get(value, value)
                    keyboard_ctrl.release(key)
        except Empty:
            continue
        except Exception as e:
            print(f"[!] Erreur dans command_processor: {e}")

def recv_all(sock, n):
    data = bytearray()
    while len(data) < n:
        try:
            packet = sock.recv(n - len(data))
            if not packet: return None
            data.extend(packet)
        except (ssl.SSLWantReadError, ssl.SSLWantWriteError, ssl.SSLEOFError, ConnectionResetError, BrokenPipeError):
            return None # Indicate connection error or closure
        except Exception as e:
            print(f"[!] Erreur inattendue lors de la réception: {e}")
            return None
    return data

MSG_TYPE_IMAGE = b'\x01'
MSG_TYPE_COMMAND = b'\x02'
MSG_TYPE_CAMERA = b'\x03'
active_chat_windows = {}

def send_command_to_client(client_socket, command_str):
    try:
        command_bytes = command_str.encode('utf-8')
        len_info = struct.pack("!H", len(command_bytes))
        client_socket.sendall(MSG_TYPE_COMMAND + len_info + command_bytes)
    except (ssl.SSLWantReadError, ssl.SSLWantWriteError, ssl.SSLEOFError, ConnectionResetError, BrokenPipeError) as e:
        print(f"[!] Client déconnecté ou erreur SSL lors de l'envoi de la commande: {e}")
        return False
    except Exception as e:
        print(f"[!] Erreur inattendue lors de l'envoi de la commande au client: {e}")
        return False
    return True

def send_chat_message_to_client(client_socket, message):
    send_command_to_client(client_socket, f"CHAT_MESSAGE_FROM_SERVER,{message}")

def send_clipboard_to_client(client_socket, content):
    send_command_to_client(client_socket, f"CLIPBOARD_UPDATE,{content}")

def monitor_and_sync_clipboard(client_socket, stop_event, session_data):
    try:
        current_server_clipboard = pyperclip.paste()
        session_data['last_server_clipboard'] = current_server_clipboard
        session_data['last_client_clipboard_received'] = current_server_clipboard
        if current_server_clipboard:
            send_clipboard_to_client(client_socket, current_server_clipboard)
            session_data['last_clipboard_sent_to_client'] = current_server_clipboard
        while not stop_event.is_set():
            current_clipboard = pyperclip.paste()
            if current_clipboard != session_data['last_server_clipboard'] and \
                    current_clipboard != session_data['last_client_clipboard_received']:
                send_clipboard_to_client(client_socket, current_clipboard)
                session_data['last_server_clipboard'] = current_clipboard
                session_data['last_clipboard_sent_to_client'] = current_clipboard
            time.sleep(0.5)
    except Exception as e:
        print(f"[!] Erreur dans monitor_and_sync_clipboard: {e}")

class ServerChatWindow:
    def __init__(self, client_socket, client_address, stop_event_client_handler, on_window_closed_callback):
        self.client_socket = client_socket
        self.client_address = client_address
        self.stop_event_client_handler = stop_event_client_handler
        self.on_window_closed_callback = on_window_closed_callback
        self.root = tk.Tk()
        self.root.withdraw() # Hide the main Tkinter window
        self.chat_window = tk.Toplevel(self.root) # Create a Toplevel window instead
        self.chat_window.overrideredirect(True)
        self.chat_window.protocol("WM_DELETE_WINDOW", self._on_closing) # Handle closing

        window_width, window_height = 1000, 800
        screen_width, screen_height = self.chat_window.winfo_screenwidth(), self.chat_window.winfo_screenheight()
        center_x, center_y = int(screen_width/2 - window_width / 2), int(screen_height/2 - window_height / 2)
        self.chat_window.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')
        self.chat_window.attributes("-topmost", True)

        main_frame = tk.Frame(self.chat_window, highlightbackground="gray", highlightcolor="gray", highlightthickness=1)
        main_frame.pack(fill=tk.BOTH, expand=True)
        title_bar = tk.Frame(main_frame, bg='gray', relief='raised', bd=0)
        title_bar.pack(expand=False, fill='x')
        title_label = tk.Label(title_bar, text=f"Chat avec {self.client_address[0]}", bg='gray', fg='white')
        title_label.pack(side=tk.LEFT, padx=10)
        title_bar.bind("<ButtonPress-1>", self._on_press)
        title_bar.bind("<B1-Motion>", self._on_drag)
        title_label.bind("<ButtonPress-1>", self._on_press)
        title_label.bind("<B1-Motion>", self._on_drag)
        try:
            self.chat_window.iconbitmap(resource_path("logo_-hosanna-tv-copie.ico"))
        except Exception as e:
            print(f"[!] Erreur lors du chargement de l'icône: {e}")
        self.chat_history = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, state='disabled', font=("Arial", 10))
        self.chat_history.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        self.chat_history.tag_config("me", foreground="blue")
        self.chat_history.tag_config("client", foreground="green")
        self.chat_history.tag_config("system", foreground="red")
        input_frame = tk.Frame(main_frame)
        input_frame.pack(padx=10, pady=5, fill=tk.X)
        self.message_var = tk.StringVar()
        self.message_var.trace_add("write", self._update_send_button_state)
        self.message_input = tk.Entry(input_frame, font=("Arial", 10), textvariable=self.message_var)
        self.message_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.message_input.bind("<Return>", self._send_message_from_gui)
        close_button = tk.Button(input_frame, text="Fermer", command=self._on_closing, font=("Arial", 10))
        close_button.pack(side=tk.RIGHT, padx=(5, 0))
        self.send_button = tk.Button(input_frame, text="Envoyer", command=self._send_message_from_gui, font=("Arial", 10), state='disabled')
        self.send_button.pack(side=tk.RIGHT, padx=(5, 5))
        self.chat_window.grab_set_global()
        self.chat_window.after(100, self._check_message_queue)

    def _on_press(self, event): self._offset_x, self._offset_y = event.x, event.y
    def _on_drag(self, event): self.chat_window.geometry(f"+{self.chat_window.winfo_pointerx() - self._offset_x}+{self.chat_window.winfo_pointery() - self._offset_y}")
    def _update_send_button_state(self, *args): self.send_button.config(state='normal' if self.message_var.get().strip() else 'disabled')
    def _check_message_queue(self):
        try:
            while True:
                sender, message = self.message_queue.get_nowait()
                self._add_message_to_history(sender, message)
        except Empty: pass
        finally:
            if self.chat_window and self.chat_window.winfo_exists(): self.chat_window.after(100, self._check_message_queue)
    def _add_message_to_history(self, sender, message):
        self.chat_history.config(state='normal')
        self.chat_history.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {sender}: {message}\n", sender.lower())
        self.chat_history.config(state='disabled')
        self.chat_history.see(tk.END)
    def add_message(self, sender, message):
        if self.chat_window and self.chat_window.winfo_exists(): self.message_queue.put((sender, message))
    def _send_message_from_gui(self, event=None):
        message = self.message_input.get().strip()
        if message:
            send_chat_message_to_client(self.client_socket, message)
            self._add_message_to_history("Moi", message)
            self.message_input.delete(0, tk.END)
    def _on_closing(self):
        send_chat_message_to_client(self.client_socket, "L'utilisateur a fermé la fenêtre de chat. Envoyez un nouveau message pour la rouvrir.")
        self.chat_window.grab_release()
        self.chat_window.destroy()
        self.root.destroy() # Destroy the hidden root window as well
        if self.on_window_closed_callback: self.on_window_closed_callback(self.client_address)
    def close_window_from_other_thread(self):
        if self.chat_window and self.chat_window.winfo_exists(): self.chat_window.after_idle(self.chat_window.destroy)
        if self.root and self.root.winfo_exists(): self.root.after_idle(self.root.destroy)
    def start_loop(self):
        self.root.mainloop()

def stream_frames(client_socket, stop_event, session_settings):
    try:
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            while not stop_event.is_set():
                if not session_settings['screen_streaming_active']:
                    time.sleep(0.1)
                    continue
                sct_img = sct.grab(monitor)
                header = struct.pack("!II", sct_img.width, sct_img.height)
                img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                buffer = io.BytesIO()
                quality = session_settings['jpeg_quality']
                img.save(buffer, format='JPEG', quality=quality)
                jpeg_bytes = buffer.getvalue()
                payload = header + jpeg_bytes
                len_info = struct.pack("!I", len(payload))
                try:
                    client_socket.sendall(MSG_TYPE_IMAGE + len_info + payload)
                except (ssl.SSLWantReadError, ssl.SSLWantWriteError, ssl.SSLEOFError, ConnectionResetError, BrokenPipeError) as e:
                    print(f"[!] Client déconnecté ou erreur SSL lors de l'envoi de l'image: {e}")
                    break # Break if send fails
                time.sleep(0.03)
    except (BrokenPipeError, ConnectionResetError): pass
    finally: stop_event.set()

def get_available_cameras():
    available_cameras = []
    for i in range(10):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if cap.isOpened():
            ret, _ = cap.read()
            if ret: available_cameras.append(i)
            cap.release()
    return available_cameras

def stream_camera_frames(client_socket, stop_event, session_settings, camera_index_ref):
    cap = None
    current_camera_index = -1
    try:
        while not stop_event.is_set():
            selected_camera_index = camera_index_ref[0]
            if session_settings['camera_streaming_active'] and current_camera_index != selected_camera_index:
                if cap: cap.release()
                current_camera_index = selected_camera_index
                print(f"[*] Initialisation de la caméra {current_camera_index}...")
                cap = cv2.VideoCapture(current_camera_index, cv2.CAP_DSHOW)
                if not cap.isOpened():
                    print(f"[!] Erreur: Impossible d'ouvrir la caméra {current_camera_index}.")
                    cap = None; current_camera_index = -1; time.sleep(1); continue
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            elif not session_settings['camera_streaming_active'] and cap:
                cap.release(); cap = None; current_camera_index = -1; time.sleep(0.1); continue
            elif not session_settings['camera_streaming_active']: time.sleep(0.1); continue
            if cap:
                ret, frame = cap.read()
                if not ret:
                    print(f"[!] Erreur: Impossible de lire la trame de la caméra {current_camera_index}.")
                    cap.release(); cap = None; current_camera_index = -1; time.sleep(1); continue
                _, jpeg_bytes = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), session_settings['jpeg_quality']])
                header = struct.pack("!II", frame.shape[1], frame.shape[0])
                payload = header + jpeg_bytes.tobytes()
                len_info = struct.pack("!I", len(payload))
                try:
                    client_socket.sendall(MSG_TYPE_CAMERA + len_info + payload)
                except (ssl.SSLWantReadError, ssl.SSLWantWriteError, ssl.SSLEOFError, ConnectionResetError, BrokenPipeError) as e:
                    print(f"[!] Client déconnecté ou erreur SSL lors de l'envoi de la caméra: {e}")
                    break # Break if send fails
                time.sleep(0.05)
    except (BrokenPipeError, ConnectionResetError): pass
    except Exception as e: print(f"[!] Erreur dans stream_camera_frames: {e}")
    finally:
        if cap: cap.release()
        stop_event.set()

def start_bore_tunnel(local_port, tunnel_type, result_queue):
    """
    Démarre un tunnel bore pour un port local donné.
    Place le résultat (adresse, port) ou une erreur dans la queue.
    """
    bore_path = resource_path("bore.exe")
    if not os.path.exists(bore_path):
        result_queue.put((None, f"bore.exe non trouvé à {bore_path}"))
        return

    command = [bore_path, "local", str(local_port), "--to", "bore.pub"]
    process = None
    try:
        # Use subprocess.Popen with PIPE for stdout/stderr to capture output
        # and CREATE_NO_WINDOW to hide the console window on Windows
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        
        # Read output line by line to find the public address and port
        public_address = None
        public_port = None
        for line in iter(process.stdout.readline, ''):
            print(f"[BORE {local_port}] {line.strip()}") # For debugging
            match = re.search(r'listening at (.*):(\d+)', line)
            if match:
                public_address = match.group(1)
                public_port = match.group(2)
                break # Found the info, stop reading output for this tunnel
        
        if public_address and public_port:
            result_queue.put((public_address, public_port))
        else:
            # If process exited or didn't provide expected output
            stderr_output = process.communicate(timeout=5)[0] # Try to get any remaining output
            result_queue.put((None, f"bore tunnel failed to start for port {local_port}. Output: {stderr_output}"))

    except FileNotFoundError:
        result_queue.put((None, f"bore.exe non trouvé à {bore_path}"))
    except subprocess.TimeoutExpired:
        if process: process.kill(); process.wait()
        result_queue.put((None, f"Timeout lors du démarrage du tunnel bore pour le port {local_port}"))
    except Exception as e:
        result_queue.put((None, str(e)))
    finally:
        # Store the process globally so it can be killed later
        if process:
            global active_bore_tunnels_info
            active_bore_tunnels_info[tunnel_type]['process'] = process
            active_bore_tunnels_info[tunnel_type]['address'] = public_address
            active_bore_tunnels_info[tunnel_type]['port'] = public_port

def handle_client(client_socket, client_address):
    stop_event = threading.Event()
    session_settings = {'jpeg_quality': 70, 'screen_streaming_active': True, 'camera_streaming_active': False, 'selected_camera_index': [0]}
    session_data = {'jpeg_quality': 70, 'last_server_clipboard': "", 'last_client_clipboard_received': "", 'last_clipboard_sent_to_client': ""}
    server_chat_window = None
    
    # Send camera list
    if not send_command_to_client(client_socket, f"CAMERA_LIST,{json.dumps(get_available_cameras())}"):
        stop_event.set()
        return

    # Send file tunnel info immediately after connection if available
    global active_bore_tunnels_info
    if active_bore_tunnels_info['file']['address'] and active_bore_tunnels_info['file']['port']:
        if not send_command_to_client(client_socket, f"FILE_TUNNEL_INFO,{active_bore_tunnels_info['file']['address']},{active_bore_tunnels_info['file']['port']}"):
            stop_event.set()
            return


    def _notify_chat_window_closed(address):
        nonlocal server_chat_window
        server_chat_window = None
        if address in active_chat_windows: del active_chat_windows[address]

    processor_thread = threading.Thread(target=command_processor, args=(stop_event,), daemon=True)
    processor_thread.start()
    clipboard_monitor = threading.Thread(target=monitor_and_sync_clipboard, args=(client_socket, stop_event, session_data), daemon=True)
    clipboard_monitor.start()
    camera_streamer_thread, camera_streamer_stop_event = None, threading.Event()

    def start_camera_streamer():
        nonlocal camera_streamer_thread, camera_streamer_stop_event
        if camera_streamer_thread and camera_streamer_thread.is_alive():
            camera_streamer_stop_event.set(); camera_streamer_thread.join(timeout=1)
        camera_streamer_stop_event = threading.Event()
        camera_streamer_thread = threading.Thread(target=stream_camera_frames, args=(client_socket, camera_streamer_stop_event, session_settings, session_settings['selected_camera_index']), daemon=True)
        camera_streamer_thread.start()
    start_camera_streamer()

    def _receive_and_process_client_messages():
        nonlocal server_chat_window
        try:
            while not stop_event.is_set():
                msg_type_byte = recv_all(client_socket, 1)
                if not msg_type_byte: break
                if msg_type_byte == MSG_TYPE_COMMAND:
                    len_info = recv_all(client_socket, 2)
                    if not len_info: break
                    cmd_len = struct.unpack("!H", len_info)[0]
                    command_data = recv_all(client_socket, cmd_len)
                    if not command_data: break
                    command = command_data.decode('utf-8')
                    parts = command.split(',', 1)
                    cmd_type, value_str = parts[0], parts[1] if len(parts) > 1 else ""
                    
                    if cmd_type == 'GENERATE_SHARE_CODE':
                        main_q, file_q = Queue(), Queue()
                        
                        # Check if tunnels are already active
                        if active_bore_tunnels_info['main']['address'] and active_bore_tunnels_info['file']['address']:
                            main_address = active_bore_tunnels_info['main']['address']
                            main_port = active_bore_tunnels_info['main']['port']
                            file_address = active_bore_tunnels_info['file']['address']
                            file_port = active_bore_tunnels_info['file']['port']
                            send_command_to_client(client_socket, f"SHARE_INFO_GENERATED,{main_address},{main_port},{file_address},{file_port}")
                            continue

                        # Start tunnels for both main and file transfer ports
                        main_tunnel_thread = threading.Thread(target=start_bore_tunnel, args=(1981, "main", main_q), daemon=True)
                        file_tunnel_thread = threading.Thread(target=start_bore_tunnel, args=(1980, "file", file_q), daemon=True)
                        
                        main_tunnel_thread.start()
                        file_tunnel_thread.start()

                        main_info, file_info = None, None
                        try:
                            main_info = main_q.get(timeout=20) # Increased timeout
                            file_info = file_q.get(timeout=20) # Increased timeout
                        except Empty:
                            send_command_to_client(client_socket, "SHARE_INFO_ERROR,Timeout lors de la création des tunnels.")
                            continue

                        main_address, main_port = main_info
                        file_address, file_port = file_info

                        if main_address and file_address:
                            # Send all tunnel info to the client
                            send_command_to_client(client_socket, f"SHARE_INFO_GENERATED,{main_address},{main_port},{file_address},{file_port}")
                        else:
                            error_msg = main_port if not main_address else file_port
                            send_command_to_client(client_socket, f"SHARE_INFO_ERROR,{error_msg}")
                        continue

                    if cmd_type == 'QUALITY': session_settings['jpeg_quality'] = int(value_str)
                    elif cmd_type == 'MV': x, y = value_str.split(','); command_queue.put(('MV', (int(x), int(y))))
                    elif cmd_type == 'MC': btn, pressed = value_str.split(','); command_queue.put(('MC', (btn, int(pressed))))
                    elif cmd_type in ('CLICK', 'DBLCLICK'): x, y, btn = value_str.split(','); command_queue.put((cmd_type, (int(x), int(y), btn)))
                    elif cmd_type == 'SCROLL': x_offset, y_offset = value_str.split(','); command_queue.put((cmd_type, (int(x_offset), int(y_offset))))
                    elif cmd_type in ('KP', 'KR'): command_queue.put((cmd_type, value_str))
                    elif cmd_type == 'CLIPBOARD_DATA':
                        try:
                            pyperclip.copy(value_str)
                            session_data['last_server_clipboard'] = value_str
                            session_data['last_client_clipboard_received'] = value_str
                        except Exception as e: print(f"[!] Erreur presse-papiers: {e}")
                    elif cmd_type == 'CHAT_MESSAGE':
                        if server_chat_window is None:
                            server_chat_window = ServerChatWindow(client_socket, client_address, stop_event, _notify_chat_window_closed)
                            active_chat_windows[client_address] = server_chat_window
                            threading.Thread(target=server_chat_window.start_loop, daemon=True).start()
                            time.sleep(0.2)
                        server_chat_window.add_message("Client", value_str)
                    elif cmd_type == 'START_CAMERA': session_settings['camera_streaming_active'] = True
                    elif cmd_type == 'STOP_CAMERA': session_settings['camera_streaming_active'] = False
                    elif cmd_type == 'SELECT_CAMERA':
                        try:
                            new_idx = int(value_str)
                            if new_idx != session_settings['selected_camera_index'][0]:
                                session_settings['selected_camera_index'][0] = new_idx
                                start_camera_streamer()
                        except ValueError: print(f"[!] Commande SELECT_CAMERA invalide: {value_str}")
                    elif cmd_type == 'START_SCREEN': session_settings['screen_streaming_active'] = True
                    elif cmd_type == 'STOP_SCREEN': session_settings['screen_streaming_active'] = False
                else: break
        finally:
            stop_event.set()
            camera_streamer_stop_event.set()
            if server_chat_window:
                server_chat_window.add_message("Système", "Client déconnecté.")
                server_chat_window.close_window_from_other_thread()
            if client_address in active_chat_windows: del active_chat_windows[client_address]

    receiver = threading.Thread(target=_receive_and_process_client_messages, daemon=True)
    streamer = threading.Thread(target=stream_frames, args=(client_socket, stop_event, session_settings), daemon=True)
    receiver.start()
    streamer.start()
    stop_event.wait()
    print(f"[-] Client {client_address} déconnecté.")
    client_socket.close()

def get_system_info():
    try:
        uname = platform.uname()
        sys_info = {"node_name": uname.node, "user_name": psutil.users()[0].name if psutil.users() else "N/A", "os_version": platform.platform(), "architecture": uname.machine}
        cpu_usage = psutil.cpu_percent(interval=0.1)
        cpu_freq = psutil.cpu_freq()
        sys_info["cpu"] = {"usage": cpu_usage, "freq_current": cpu_freq.current if cpu_freq else 0, "freq_max": cpu_freq.max if cpu_freq else 0}
        ram = psutil.virtual_memory()
        sys_info["ram"] = {"total": ram.total, "used": ram.used, "percent": ram.percent}
        partitions_info = []
        for p in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(p.mountpoint)
                partitions_info.append({"device": p.device, "mountpoint": p.mountpoint, "total": usage.total, "used": usage.used, "percent": usage.percent})
            except (PermissionError, FileNotFoundError): continue
        sys_info["disks"] = partitions_info
        return sys_info
    except Exception as e:
        print(f"[*] Erreur dans get_system_info: {e}", file=sys.stderr)
        return {"error": str(e)}

def get_downloads_folder():
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders')
        downloads_folder, _ = winreg.QueryValueEx(key, '{374DE290-123F-4565-9164-39C4925E467B}')
        winreg.CloseKey(key)
        return downloads_folder
    except Exception:
        return os.path.join(os.path.expanduser("~"), "Downloads")

def get_available_drives():
    drives = []
    bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
        if bitmask & 1: drives.append(f"{letter}:\\")
        bitmask >>= 1
    return drives

def handle_file_transfer(client_socket):
    try:
        len_info = recv_all(client_socket, 2)
        if not len_info: return
        header_len = struct.unpack("!H", len_info)[0]
        header_data = recv_all(client_socket, header_len)
        if not header_data: return
        header_str = header_data.decode('utf-8')
        parts = header_str.split(',', 1)
        command = parts[0]
        if command == 'UPLOAD':
            _, filename, filesize_str = header_str.split(',')
            filesize = int(filesize_str)
            filename = os.path.basename(filename)
            downloads_path = get_downloads_folder()
            reception_path = os.path.join(downloads_path, "Hosanna Tv Reception")
            if not os.path.exists(reception_path): os.makedirs(reception_path)
            save_path = os.path.join(reception_path, filename)
            print(f"[*] Réception de '{filename}'...")
            bytes_received = 0
            interrupted = False
            try:
                with open(save_path, 'wb') as f:
                    while bytes_received < filesize:
                        chunk_size = min(65536, filesize - bytes_received)
                        chunk = recv_all(client_socket, chunk_size)
                        if not chunk: interrupted = True; break
                        f.write(chunk)
                        bytes_received += len(chunk)
            except Exception as e: interrupted = True; print(f"[!] Erreur écriture fichier: {e}")
            if interrupted:
                print(f"[!] Transfert de '{filename}' interrompu.")
                if os.path.exists(save_path): os.remove(save_path)
            elif bytes_received == filesize:
                print(f"[*] Fichier '{filename}' reçu.")
                client_socket.sendall(b"OK")
        elif command == 'LIST_DIR':
            req_path = parts[1]
            response_data = None
            if not req_path:
                entries = [{'name': d, 'is_dir': True, 'size': 0} for d in get_available_drives()]
                response_data = json.dumps({'path': '', 'entries': entries}).encode('utf-8')
            else:
                entries, error_msg = [], None
                try:
                    for entry in os.scandir(req_path):
                        try:
                            is_dir = entry.is_dir()
                            size = 0 if is_dir else entry.stat().st_size
                            entries.append({'name': entry.name, 'is_dir': is_dir, 'size': size})
                        except (OSError, PermissionError): continue
                except (OSError, PermissionError): error_msg = "Accès refusé"
                entries.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
                response_dict = {'path': req_path, 'entries': entries, 'error': error_msg}
                response_data = json.dumps(response_dict).encode('utf-8')
            if response_data:
                len_prefix = struct.pack("!I", len(response_data))
                client_socket.sendall(len_prefix + response_data)
        elif command == 'DOWNLOAD':
            req_path = parts[1]
            if not os.path.isfile(req_path): client_socket.sendall(struct.pack("!Q", 0))
            else:
                try:
                    filesize = os.path.getsize(req_path)
                    client_socket.sendall(struct.pack("!Q", filesize))
                    print(f"[*] Envoi de '{req_path}'...")
                    with open(req_path, 'rb') as f:
                        while True:
                            chunk = f.read(65536)
                            if not chunk: break
                            client_socket.sendall(chunk)
                    print(f"[*] Envoi de '{req_path}' terminé.")
                except (BrokenPipeError, ConnectionResetError): pass
                except Exception as e: print(f"[!] Erreur envoi fichier: {e}")
        elif command == 'GET_SYS_INFO':
            info = get_system_info()
            response_data = json.dumps(info).encode('utf-8')
            len_prefix = struct.pack("!I", len(response_data))
            client_socket.sendall(len_prefix + response_data)
    except Exception as e: print(f"[!!!] ERREUR CRITIQUE transfert: {e}", file=sys.stderr)
    finally: client_socket.close()

def file_server(host, port, context):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((host, port))
    server_socket.listen(5)
    print(f"[*] Serveur de fichiers en écoute sur le port {port}...")
    while True:
        try:
            client, addr = server_socket.accept()
            ssl_socket = context.wrap_socket(client, server_side=True)
            threading.Thread(target=handle_file_transfer, args=(ssl_socket,), daemon=True).start()
        except Exception as e: print(f"[!] Erreur serveur de fichiers: {e}"); break

def discovery_service(discovery_port):
    discovery_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    discovery_socket.bind(('', discovery_port))
    print(f"[*] Service de découverte en écoute sur le port UDP {discovery_port}...")
    while True:
        try:
            message, client_address = discovery_socket.recvfrom(1024)
            if message.decode('utf-8') == "HOSANNA_REMOTE_DISCOVERY_REQUEST":
                discovery_socket.sendto(b"HOSANNA_REMOTE_DISCOVERY_RESPONSE", client_address)
        except Exception as e: print(f"[!] Erreur découverte: {e}"); break

def main():
    base_path = sys._MEIPASS if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
    cert_path, key_path = os.path.join(base_path, "cert.pem"), os.path.join(base_path, "key.pem")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    try:
        context.load_cert_chain(certfile=cert_path, keyfile=key_path)
    except FileNotFoundError:
        print("[ERREUR] cert.pem ou key.pem non trouvé."); input("Appuyez sur Entrée..."); return

    main_port, file_port, discovery_port = 1981, 1980, 9998
    threading.Thread(target=discovery_service, args=(discovery_port,), daemon=True).start()
    threading.Thread(target=file_server, args=('0.0.0.0', file_port, context), daemon=True).start()

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(('0.0.0.0', main_port))
    server_socket.listen(5)
    print(f"[*] Serveur sécurisé en écoute sur le port {main_port}...")
    try:
        while True:
            client, addr = server_socket.accept()
            print(f"[*] Connexion acceptée de {addr[0]}:{addr[1]}")
            ssl_socket = context.wrap_socket(client, server_side=True)
            threading.Thread(target=handle_client, args=(ssl_socket, addr), daemon=True).start()
    except KeyboardInterrupt: print("\n[*] Serveur arrêté.")
    finally:
        global active_bore_tunnels_info
        for tunnel_type in active_bore_tunnels_info:
            process = active_bore_tunnels_info[tunnel_type]['process']
            if process and process.poll() is None: # If process is still running
                print(f"[*] Arrêt du tunnel bore ({tunnel_type})...")
                process.kill()
                process.wait()
        server_socket.close()

if __name__ == '__main__':
    main()
