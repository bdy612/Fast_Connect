import socket
import threading
import json
import struct
import logging

# Create a logger
logger = logging.getLogger(__name__)

class Client:
    def __init__(self, server_host, server_port):
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.connect((server_host, server_port))
        self.running = True
        self.message_callback = None
        self.disconnect_callback = None
        logger.info(f"Connected to server at {server_host}:{server_port}")
        
        # Start listening thread
        self.listen_thread = threading.Thread(target=self.listen_for_messages)
        self.listen_thread.daemon = True
        self.listen_thread.start()

    # ------------------------------------------------------------------
    # Framed message helpers (length-prefix, 4-byte big-endian header)
    # ------------------------------------------------------------------
    def _send_framed(self, message):
        """Send a message prefixed with its 4-byte length"""
        data = message.encode('utf-8')
        self.client_socket.sendall(struct.pack('>I', len(data)) + data)

    def _recv_framed(self):
        """Receive a complete length-prefixed message; returns None on disconnect"""
        def recv_exact(n):
            buf = b''
            while len(buf) < n:
                try:
                    chunk = self.client_socket.recv(n - len(buf))
                    if not chunk:
                        return None
                    buf += chunk
                except socket.timeout:
                    if not self.running:
                        return None
                    continue
            return buf

        header = recv_exact(4)
        if not header:
            return None
        length = struct.unpack('>I', header)[0]
        if length > 10 * 1024 * 1024:  # 10 MB sanity limit
            return None
        body = recv_exact(length)
        if not body:
            return None
        return body.decode('utf-8')
    
    def listen_for_messages(self):
        """Listen for incoming messages from the server"""
        self.client_socket.settimeout(1.0)

        while self.running:
            message = self._recv_framed()
            if message is None:
                if self.running:
                    logger.info("Disconnected from server")
                    if self.disconnect_callback:
                        self.disconnect_callback("Server disconnected")
                self.running = False
                break

            logger.info(f"Message from server: {message[:100]}")

            # Check if we've been kicked (JSON type)
            try:
                msg_data = json.loads(message)
                if msg_data.get('type') == 'kicked':
                    logger.info("You have been kicked from the server")
                    if self.disconnect_callback:
                        self.disconnect_callback("Kicked by server")
                    self.running = False
                    break
            except Exception:
                pass

            if self.message_callback:
                self.message_callback(message)
    
    def send(self, message):
        """Send a message to the server"""
        try:
            self._send_framed(message)
            return True
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False
    
    def send_encrypted_message(self, message, encryption_data):
        """Send a message with encryption data"""
        try:
            # Create a packet containing both the message and encryption info
            packet = {
                "encrypted_message": message,
                "encryption_data": encryption_data
            }
            
            # Convert to JSON string and send
            json_data = json.dumps(packet)
            self.client_socket.send(json_data.encode())
            return True
        except Exception as e:
            logger.error(f"Error sending encrypted message: {e}")
            return False
    
    def set_message_callback(self, callback_function):
        """Set a function to call when messages are received"""
        self.message_callback = callback_function
    
    def set_disconnect_callback(self, callback_function):
        """Set a function to call when disconnected"""
        self.disconnect_callback = callback_function
    
    def close(self):
        """Close the connection to the server"""
        self.running = False
        self.client_socket.close()