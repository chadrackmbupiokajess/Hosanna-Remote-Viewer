import socket
import struct
import time
import io
import threading
import ssl
import sys
import os
from queue import Queue, Empty
from PIL import Image
import mss
from pynput.mouse import Button, Controller as MouseController
from pynput.keyboard import Key, Controller as KeyboardController

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
                if cmd[0] == 'MV': last_move = cmd
                else: other_commands.append(cmd)
            
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
        packet = sock.recv(n - len(data))
        if not packet: return None
        data.extend(packet)
    return data

def handle_client(client_socket):
    stop_event = threading.Event()
    # --- NOUVEAU: Utiliser un dictionnaire partagé pour les paramètres de session
    session_settings = {'jpeg_quality': 70} 

    processor_thread = threading.Thread(target=command_processor, args=(stop_event,))
    processor_thread.daemon = True
    processor_thread.start()

    def receive_commands():
        try:
            while not stop_event.is_set():
                len_info = recv_all(client_socket, 2)
                if not len_info: break
                cmd_len = struct.unpack("!H", len_info)[0]
                command_data = recv_all(client_socket, cmd_len)
                if not command_data: break
                command = command_data.decode('utf-8')
                parts = command.split(',', 1)
                if len(parts) < 2: continue
                cmd_type, value_str = parts[0], parts[1]

                # --- NOUVEAU: Gérer la commande de qualité
                if cmd_type == 'QUALITY':
                    session_settings['jpeg_quality'] = int(value_str)
                    print(f"[*] Qualité d'image réglée à {value_str} pour ce client.")
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
        finally: stop_event.set()

    def stream_frames():
        try:
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                while not stop_event.is_set():
                    sct_img = sct.grab(monitor)
                    header = struct.pack("!II", sct_img.width, sct_img.height)
                    img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                    buffer = io.BytesIO()
                    # --- NOUVEAU: Utiliser la qualité de la session
                    quality = session_settings['jpeg_quality']
                    img.save(buffer, format='JPEG', quality=quality)
                    jpeg_bytes = buffer.getvalue()
                    payload = header + jpeg_bytes
                    len_info = struct.pack("!I", len(payload))
                    client_socket.sendall(len_info + payload)
                    time.sleep(0.03) # Garder une petite pause pour ne pas surcharger le CPU
        finally: stop_event.set()

    receiver = threading.Thread(target=receive_commands)
    streamer = threading.Thread(target=stream_frames)
    receiver.daemon = True
    streamer.daemon = True
    receiver.start()
    streamer.start()
    stop_event.wait()
    print("[-] Un thread client s'est arrêté, fermeture de la connexion.")
    client_socket.close()

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
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(('0.0.0.0', 9999))
    server_socket.listen(5)
    print("[*] Serveur sécurisé en écoute sur le port 9999...")
    try:
        while True:
            client, addr = server_socket.accept()
            print(f"[*] Connexion acceptée de {addr[0]}:{addr[1]}")
            ssl_socket = context.wrap_socket(client, server_side=True)
            threading.Thread(target=handle_client, args=(ssl_socket,), daemon=True).start()
    except KeyboardInterrupt:
        print("\n[*] Serveur arrêté.")
    finally:
        server_socket.close()

if __name__ == '__main__':
    main()
