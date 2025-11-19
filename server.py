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
from tkinter import scrolledtext  # Pour une zone de texte avec scroll

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
                    if pressed:
                        mouse_ctrl.press(button)
                    else:
                        mouse_ctrl.release(button)
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
        except (ssl.SSLWantReadError, ssl.SSLWantWriteError):
            continue
        except (ConnectionResetError, BrokenPipeError):
            return None
    return data


# Message types for the main streaming socket
MSG_TYPE_IMAGE = b'\x01'
MSG_TYPE_COMMAND = b'\x02'

# Global dictionary to hold active chat windows, keyed by client_address
active_chat_windows = {}


# NOUVEAU : Fonction pour envoyer un message de chat au client
def send_chat_message_to_client(client_socket, message):
    try:
        command_str = f"CHAT_MESSAGE_FROM_SERVER,{message}"
        command_bytes = command_str.encode('utf-8')
        len_info = struct.pack("!H", len(command_bytes))
        client_socket.sendall(MSG_TYPE_COMMAND + len_info + command_bytes)
        print(f"[*] SERVER DEBUG: Message chat envoyé au client: '{message}'")
    except (BrokenPipeError, ConnectionResetError):
        print("[!] SERVER DEBUG: Client déconnecté lors de l'envoi du message chat.")
    except Exception as e:
        print(f"[!] SERVER DEBUG: Erreur lors de l'envoi du message chat au client: {e}")


def send_clipboard_to_client(client_socket, content):
    try:
        command_str = f"CLIPBOARD_UPDATE,{content}"
        command_bytes = command_str.encode('utf-8')
        len_info = struct.pack("!H", len(command_bytes))
        client_socket.sendall(MSG_TYPE_COMMAND + len_info + command_bytes)
        print(f"[*] SERVER DEBUG: Envoi du presse-papiers au client: '{content}'")
    except (BrokenPipeError, ConnectionResetError):
        print("[!] SERVER DEBUG: Client déconnecté lors de l'envoi du presse-papiers.")
    except Exception as e:
        print(f"[!] SERVER DEBUG: Erreur lors de l'envoi du presse-papiers au client: {e}")


def monitor_and_sync_clipboard(client_socket, stop_event, session_data):
    try:
        current_server_clipboard = pyperclip.paste()
        session_data['last_server_clipboard'] = current_server_clipboard
        session_data['last_client_clipboard_received'] = current_server_clipboard

        print(
            f"[*] SERVER DEBUG: Démarrage du monitoring du presse-papiers. Contenu initial serveur: '{current_server_clipboard}'")

        if current_server_clipboard:
            send_clipboard_to_client(client_socket, current_server_clipboard)
            session_data['last_clipboard_sent_to_client'] = current_server_clipboard
            print(f"[*] SERVER DEBUG: Presse-papiers initial du serveur envoyé au client: '{current_server_clipboard}'")

        while not stop_event.is_set():
            current_clipboard = pyperclip.paste()
            if current_clipboard != session_data['last_server_clipboard'] and \
                    current_clipboard != session_data['last_client_clipboard_received']:
                print(
                    f"[*] SERVER DEBUG: Changement détecté dans le presse-papiers local du serveur. Ancien: '{session_data['last_server_clipboard']}', Nouveau: '{current_clipboard}'")
                send_clipboard_to_client(client_socket, current_clipboard)
                session_data['last_server_clipboard'] = current_clipboard
                session_data['last_clipboard_sent_to_client'] = current_clipboard
                print(f"[*] SERVER DEBUG: Presse-papiers serveur mis à jour localement et envoyé au client.")
            time.sleep(0.5)
    except Exception as e:
        print(f"[!] SERVER DEBUG: Erreur dans monitor_and_sync_clipboard: {e}")


# NOUVEAU : Classe pour la fenêtre de chat du serveur
class ServerChatWindow:
    def __init__(self, client_socket, client_address, stop_event_client_handler, on_window_closed_callback):
        self.client_socket = client_socket
        self.client_address = client_address
        self.stop_event_client_handler = stop_event_client_handler  # Pour signaler au gestionnaire client de s'arrêter si la GUI se ferme
        self.on_window_closed_callback = on_window_closed_callback  # Callback pour notifier la fermeture

        self.root = None
        self.chat_history = None
        self.message_input = None

        # Queue pour les messages venant *vers* cette fenêtre de chat depuis d'autres threads
        self.message_queue = Queue()

    def _create_gui(self):
        self.root = tk.Tk()
        self.root.title(f"Chat avec Client {self.client_address[0]}:{self.client_address[1]}")
        self.root.geometry("900x700")  # MODIFICATION : Taille de fenêtre encore agrandie
        self.root.attributes("-topmost", True)

        self.chat_history = scrolledtext.ScrolledText(self.root, wrap=tk.WORD, state='disabled', font=("Arial", 10))
        self.chat_history.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)  # expand=True assure l'agrandissement

        self.chat_history.tag_config("me", foreground="blue")
        self.chat_history.tag_config("client", foreground="green")
        self.chat_history.tag_config("system", foreground="red")

        input_frame = tk.Frame(self.root)
        input_frame.pack(padx=10, pady=5, fill=tk.X)

        self.message_input = tk.Entry(input_frame, font=("Arial", 10))
        # MODIFICATION : Le champ de saisie prend le reste de l'espace à gauche
        self.message_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.message_input.bind("<Return>", self._send_message_from_gui)

        # MODIFICATION : Boutons empaquetés à droite pour une meilleure visibilité
        close_button = tk.Button(input_frame, text="Fermer", command=self._on_closing, font=("Arial", 10))
        close_button.pack(side=tk.RIGHT, padx=(5, 0))  # Le bouton Fermer est le plus à droite

        send_button = tk.Button(input_frame, text="Envoyer", command=self._send_message_from_gui, font=("Arial", 10))
        send_button.pack(side=tk.RIGHT, padx=(5, 5))  # Le bouton Envoyer est à gauche du bouton Fermer

        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

        # Commencer à vérifier la queue de messages périodiquement
        self.root.after(100, self._check_message_queue)

    def _check_message_queue(self):
        try:
            while True:
                sender, message = self.message_queue.get_nowait()
                self._add_message_to_history(sender, message)
        except Empty:
            pass
        finally:
            if self.root and self.root.winfo_exists():  # Vérifier si la fenêtre existe toujours
                self.root.after(100, self._check_message_queue)  # Planifier la prochaine vérification

    def _add_message_to_history(self, sender, message):
        self.chat_history.config(state='normal')
        if sender == "Moi":
            self.chat_history.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] Moi: {message}\n", "me")
        elif sender == "Client":
            self.chat_history.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] Client: {message}\n", "client")
        elif sender == "Système":
            self.chat_history.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] Système: {message}\n", "system")
        self.chat_history.config(state='disabled')
        self.chat_history.see(tk.END)

    def add_message(self, sender, message):
        # Cette méthode est appelée depuis d'autres threads, elle met les messages dans la queue
        if self.root and self.root.winfo_exists():  # S'assurer que la fenêtre existe avant d'ajouter à la queue
            self.message_queue.put((sender, message))

    def _send_message_from_gui(self, event=None):
        # Cette méthode est appelée depuis le thread GUI
        message = self.message_input.get().strip()
        if message:
            send_chat_message_to_client(self.client_socket, message)  # Envoie au client
            self._add_message_to_history("Moi", message)  # Ajoute à l'historique local
            self.message_input.delete(0, tk.END)

    def _on_closing(self):
        # Cette méthode est appelée depuis le thread GUI lorsque la fenêtre est fermée
        print(f"[*] SERVER DEBUG: Fenêtre de chat pour {self.client_address} fermée par l'utilisateur.")
        self.root.destroy()
        if self.on_window_closed_callback:
            self.on_window_closed_callback(self.client_address)  # Notifier handle_client

    def close_window_from_other_thread(self):
        # Cette méthode est appelée depuis d'autres threads (e.g., quand le client se déconnecte)
        if self.root and self.root.winfo_exists():
            self.root.after_idle(self.root.destroy)  # Planifie la destruction sur le thread GUI

    def start_loop(self):
        # Cette méthode est appelée dans un thread dédié
        self._create_gui()
        self.root.mainloop()


# NOUVEAU : Fonction globale stream_frames
def stream_frames(client_socket, stop_event, session_settings):
    try:
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            while not stop_event.is_set():
                sct_img = sct.grab(monitor)
                header = struct.pack("!II", sct_img.width, sct_img.height)
                img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                buffer = io.BytesIO()
                quality = session_settings['jpeg_quality']
                img.save(buffer, format='JPEG', quality=quality)
                jpeg_bytes = buffer.getvalue()
                payload = header + jpeg_bytes
                len_info = struct.pack("!I", len(payload))
                client_socket.sendall(MSG_TYPE_IMAGE + len_info + payload)
                time.sleep(0.03)
    except (BrokenPipeError, ConnectionResetError):
        print("[-] Le client de bureau a fermé la connexion.")
    finally:
        stop_event.set()


def handle_client(client_socket, client_address):
    stop_event = threading.Event()
    session_settings = {'jpeg_quality': 70}
    session_data = {
        'jpeg_quality': 70,
        'last_server_clipboard': "",
        'last_client_clipboard_received': "",
        'last_clipboard_sent_to_client': ""
    }

    server_chat_window = None  # Initialiser à None

    # NOUVEAU : Callback pour gérer la fermeture de la fenêtre de chat par l'utilisateur
    def _notify_chat_window_closed(address):
        nonlocal server_chat_window
        print(f"[*] SERVER DEBUG: Callback: Fenêtre de chat pour {address} fermée. Réinitialisation de la référence.")
        server_chat_window = None  # Permet de recréer la fenêtre si un nouveau message arrive
        if address in active_chat_windows:
            del active_chat_windows[address]

    processor_thread = threading.Thread(target=command_processor, args=(stop_event,), daemon=True)
    processor_thread.start()

    clipboard_monitor = threading.Thread(target=monitor_and_sync_clipboard,
                                         args=(client_socket, stop_event, session_data), daemon=True)
    clipboard_monitor.start()

    # Renommée et refactorisée pour gérer tous les messages entrants du client
    def _receive_and_process_client_messages():
        nonlocal server_chat_window  # Permet de modifier server_chat_window de la portée englobante
        try:
            while not stop_event.is_set():
                msg_type_byte = recv_all(client_socket, 1)
                if not msg_type_byte:
                    print(f"[!] SERVER DEBUG: Client {client_address} déconnecté (type de message vide).")
                    break

                if msg_type_byte == MSG_TYPE_COMMAND:
                    len_info = recv_all(client_socket, 2)
                    if not len_info:
                        print(f"[!] SERVER DEBUG: Client {client_address} déconnecté (longueur commande vide).")
                        break
                    cmd_len = struct.unpack("!H", len_info)[0]
                    command_data = recv_all(client_socket, cmd_len)
                    if not command_data:
                        print(f"[!] SERVER DEBUG: Client {client_address} déconnecté (payload commande vide).")
                        break
                    command = command_data.decode('utf-8')

                    parts = command.split(',', 1)
                    cmd_type = parts[0]
                    value_str = parts[1] if len(parts) > 1 else ""

                    if cmd_type == 'QUALITY':
                        session_settings['jpeg_quality'] = int(value_str)
                        print(f"[*] Qualité d'image réglée à {value_str} pour le client {client_address}.")
                    elif cmd_type == 'MV':
                        x, y = value_str.split(',')
                        command_queue.put(('MV', (int(x), int(y))))
                    elif cmd_type == 'MC':
                        btn, pressed = value_str.split(',')
                        command_queue.put(('MC', (btn, int(pressed))))
                    elif cmd_type == 'CLICK' or cmd_type == 'DBLCLICK':
                        x, y, btn = value_str.split(',')
                        command_queue.put((cmd_type, (int(x), int(y), btn)))
                    elif cmd_type == 'SCROLL':
                        x_offset, y_offset = value_str.split(',')
                        command_queue.put((cmd_type, (int(x_offset), int(y_offset))))
                    elif cmd_type in ('KP', 'KR'):
                        command_queue.put((cmd_type, value_str))
                    elif cmd_type == 'CLIPBOARD_DATA':
                        content = value_str
                        try:
                            pyperclip.copy(content)
                            session_data['last_server_clipboard'] = content
                            session_data['last_client_clipboard_received'] = content
                            print(
                                f"[*] SERVER DEBUG: Presse-papiers serveur mis à jour par le client {client_address} avec: '{content}'")
                        except Exception as e:
                            print(
                                f"[!] SERVER DEBUG: Erreur lors de la mise à jour du presse-papiers serveur pour {client_address}: {e}")
                    elif cmd_type == 'CHAT_MESSAGE':
                        print(f"[CHAT] Message du client {client_address}: {value_str}")
                        # NOUVEAU : Créer la fenêtre de chat si elle n'existe pas encore
                        if server_chat_window is None:
                            print(f"[*] SERVER DEBUG: Recréation de la fenêtre de chat pour {client_address}.")
                            server_chat_window = ServerChatWindow(client_socket, client_address, stop_event,
                                                                  _notify_chat_window_closed)
                            active_chat_windows[client_address] = server_chat_window
                            chat_window_thread = threading.Thread(target=server_chat_window.start_loop, daemon=True)
                            chat_window_thread.start()
                            time.sleep(0.1)  # Laisser le temps à Tkinter de s'initialiser
                            server_chat_window.add_message("Système", "Chat démarré avec le client.")
                            send_chat_message_to_client(client_socket,
                                                        "Chat démarré avec le serveur.")  # Informer le client

                        # Ensure server_chat_window is not None before adding message
                        if server_chat_window:  # Check again in case it was closed immediately after creation
                            server_chat_window.add_message("Client", value_str)
                        else:
                            print(
                                f"[!] SERVER DEBUG: Fenêtre de chat pour {client_address} non disponible pour afficher le message: {value_str}")
                            # Optionally, log to console or re-open window automatically
                    else:
                        print(f"[!] SERVER DEBUG: Commande inconnue reçue du client {client_address}: '{command}'")
                elif msg_type_byte == MSG_TYPE_IMAGE:
                    print(f"[!] SERVER DEBUG: Reçu MSG_TYPE_IMAGE inattendu du client {client_address}. Ignoré.")
                    len_info = recv_all(client_socket, 4)
                    if len_info:
                        payload_size = struct.unpack("!I", len_info)[0]
                        recv_all(client_socket, payload_size)
                    else:
                        print(
                            f"[!] SERVER DEBUG: Erreur de lecture de la taille de l'image inattendue pour {client_address}.")
                        break
                else:
                    print(
                        f"[!] SERVER DEBUG: Type de message inconnu reçu de {client_address}: {msg_type_byte}. Déconnexion.")
                    break

        finally:
            stop_event.set()
            if server_chat_window:  # If the window still exists (wasn't closed by user)
                server_chat_window.add_message("Système", "Client déconnecté.")
                server_chat_window.close_window_from_other_thread()
            # The active_chat_windows entry is removed by the _notify_chat_window_closed callback
            # or by the finally block if the window was never created or handle_client stops before window closes.
            if client_address in active_chat_windows:  # Ensure cleanup if window was never created or closed by handle_client
                del active_chat_windows[client_address]

    receiver = threading.Thread(target=_receive_and_process_client_messages, daemon=True)
    streamer = threading.Thread(target=stream_frames, args=(client_socket, stop_event, session_settings), daemon=True)
    receiver.start()
    streamer.start()
    stop_event.wait()
    print(f"[-] Un thread client pour {client_address} s'est arrêté, fermeture de la connexion.")
    client_socket.close()


def get_system_info():
    try:
        uname = platform.uname()
        sys_info = {
            "node_name": uname.node,
            "user_name": psutil.users()[0].name if psutil.users() else "N/A",
            "os_version": platform.platform(),
            "architecture": uname.machine,
        }

        cpu_usage = psutil.cpu_percent(interval=0.1)
        cpu_freq = psutil.cpu_freq()
        sys_info["cpu"] = {
            "usage": cpu_usage,
            "freq_current": cpu_freq.current if cpu_freq else 0,
            "freq_max": cpu_freq.max if cpu_freq else 0,
        }

        ram = psutil.virtual_memory()
        sys_info["ram"] = {
            "total": ram.total,
            "used": ram.used,
            "percent": ram.percent
        }

        partitions_info = []
        partitions = psutil.disk_partitions()
        for p in partitions:
            try:
                usage = psutil.disk_usage(p.mountpoint)
                partitions_info.append({
                    "device": p.device,
                    "mountpoint": p.mountpoint,
                    "total": usage.total,
                    "used": usage.used,
                    "percent": usage.percent
                })
            except (PermissionError, FileNotFoundError):
                continue
        sys_info["disks"] = partitions_info

        print(f"[*] Infos système collectées: {sys_info}")
        return sys_info
    except Exception as e:
        print(f"[*] Erreur dans get_system_info: {e}", file=sys.stderr)
        return {"error": str(e)}


def get_downloads_folder():
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r'Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders')
        downloads_folder, _ = winreg.QueryValueEx(key, '{374DE290-123F-4565-9164-39C4925E467B}')
        winreg.CloseKey(key)
        return downloads_folder
    except Exception:
        return os.path.join(os.path.expanduser("~"), "Downloads")


def get_available_drives():
    drives = []
    bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
        if bitmask & 1:
            drives.append(f"{letter}:\\")
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
            if not os.path.exists(reception_path):
                os.makedirs(reception_path)

            save_path = os.path.join(reception_path, filename)
            print(f"[*] Réception de '{filename}' ({filesize} octets) vers '{save_path}'")

            bytes_received = 0
            interrupted = False
            try:
                with open(save_path, 'wb') as f:
                    while bytes_received < filesize:
                        chunk_size = min(65536, filesize - bytes_received)
                        chunk = recv_all(client_socket, chunk_size)
                        if not chunk:
                            interrupted = True
                            break
                        f.write(chunk)
                        bytes_received += len(chunk)
            except Exception as e:
                interrupted = True
                print(f"[!] Erreur pendant l'écriture du fichier {filename}: {e}")

            if interrupted:
                print(f"[!] Transfert de '{filename}' interrompu. Nettoyage.")
                if os.path.exists(save_path):
                    os.remove(save_path)
            elif bytes_received == filesize:
                print(f"[*] Fichier '{filename}' reçu avec succès.")
                client_socket.sendall(b"OK")

        elif command == 'LIST_DIR':
            req_path = parts[1]
            response_data = None

            if not req_path:
                entries = [{'name': d, 'is_dir': True, 'size': 0} for d in get_available_drives()]
                response_data = json.dumps({'path': '', 'entries': entries}).encode('utf-8')
            else:
                entries = []
                error_msg = None
                try:
                    for entry in os.scandir(req_path):
                        try:
                            is_dir = entry.is_dir()
                            size = 0 if is_dir else entry.stat().st_size
                            entries.append({'name': entry.name, 'is_dir': is_dir, 'size': size})
                        except (OSError, PermissionError):
                            continue
                except (OSError, PermissionError):
                    error_msg = "Accès refusé"

                entries.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
                response_dict = {'path': req_path, 'entries': entries, 'error': error_msg}
                response_data = json.dumps(response_dict).encode('utf-8')

            if response_data:
                len_prefix = struct.pack("!I", len(response_data))
                client_socket.sendall(len_prefix + response_data)

        elif command == 'DOWNLOAD':
            req_path = parts[1]
            if not os.path.isfile(req_path):
                client_socket.sendall(struct.pack("!Q", 0))
                print(f"[!] Tentative de téléchargement de fichier inexistant: {req_path}")
            else:
                try:
                    filesize = os.path.getsize(req_path)
                    client_socket.sendall(struct.pack("!Q", filesize))
                    print(f"[*] Envoi de '{req_path}' ({filesize} octets)")
                    with open(req_path, 'rb') as f:
                        while True:
                            chunk = f.read(65536)
                            if not chunk: break
                            client_socket.sendall(chunk)
                    print(f"[*] Envoi de '{req_path}' terminé.")
                except (BrokenPipeError, ConnectionResetError):
                    print(f"[*] Connexion fermée par le client pendant l'envoi de '{req_path}'. Annulé.")
                except Exception as e:
                    print(f"[!] Erreur pendant l'envoi du fichier '{req_path}': {e}")

        elif command == 'GET_SYS_INFO':
            info = get_system_info()
            response_data = json.dumps(info).encode('utf-8')
            len_prefix = struct.pack("!I", len(response_data))
            client_socket.sendall(len_prefix + response_data)

    except Exception as e:
        print(f"[!!!] ERREUR CRITIQUE transfert: {e}", file=sys.stderr)
    finally:
        client_socket.close()


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
        except Exception as e:
            print(f"[!] Erreur sur le serveur de fichiers: {e}")
            break


def main():
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    cert_path = os.path.join(base_path, "cert.pem")
    key_path = os.path.join(base_path, "key.pem")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    try:
        context.load_cert_chain(certfile=cert_path, keyfile=key_path)
    except FileNotFoundError:
        print(f"[ERREUR] cert.pem ou key.pem non trouvé.")
        input("Appuyez sur Entrée pour quitter...")
        return

    main_port = 9999
    file_port = main_port - 1
    file_server_thread = threading.Thread(target=file_server, args=('0.0.0.0', file_port, context), daemon=True)
    file_server_thread.start()

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
    except KeyboardInterrupt:
        print("\n[*] Serveur arrêté.")
    finally:
        server_socket.close()


if __name__ == '__main__':
    main()