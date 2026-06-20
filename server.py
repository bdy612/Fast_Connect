import socket
import threading
import time
import struct
import logging

class Server:
    def __init__(self, host, port):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((host, port))
        self.server_socket.listen(5)  # Allow up to 5 connections
        self.running = True
        self.clients = []  # List to store connected clients
        self.message_handler = None
        self.client_kicked_handler = None  # Callback for when a client is kicked
        self.log = []
        
        # Start the listener in a separate thread
        self.listener_thread = threading.Thread(target=self.listen_for_clients)
        self.listener_thread.daemon = True
        self.listener_thread.start()

    # ------------------------------------------------------------------
    # Framed message helpers (length-prefix, 4-byte big-endian header)
    # ------------------------------------------------------------------
    def _send_framed(self, sock, message):
        """Send a message prefixed with its 4-byte length"""
        data = message.encode('utf-8')
        sock.sendall(struct.pack('>I', len(data)) + data)

    def _recv_framed(self, sock):
        """Receive a complete length-prefixed message; returns None on disconnect"""
        def recv_exact(n):
            buf = b''
            while len(buf) < n:
                try:
                    chunk = sock.recv(n - len(buf))
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
    
    def listen_for_clients(self):
        """Listen for incoming client connections"""
        self.server_socket.settimeout(1.0)  # Add timeout to allow checking running flag
        
        while self.running:
            try:
                client_socket, client_address = self.server_socket.accept()
                self.log.append(f"Connection from {client_address}")
                
                # Add client to the list
                self.clients.append((client_socket, client_address))
                
                # Start a thread to handle this client
                client_thread = threading.Thread(target=self.handle_client, 
                                               args=(client_socket, client_address))
                client_thread.daemon = True
                client_thread.start()
                
            except socket.timeout:
                # This allows the server to check if it should continue running
                continue
            except Exception as e:
                if self.running:  # Only log if still supposed to be running
                    self.log.append(f"Error accepting connection: {e}")
    
    def handle_client(self, client_socket, client_address):
        """Handle communication with a connected client"""
        client_socket.settimeout(1.0)
        try:
            while self.running:
                data = self._recv_framed(client_socket)
                if data is None:
                    self.log.append(f"Client {client_address} disconnected")
                    break

                self.log.append(f"Received from {client_address}: {data[:120]}")

                if self.message_handler:
                    self.message_handler(client_address, data)

        except Exception as e:
            if self.running:
                self.log.append(f"Error communicating with {client_address}: {e}")
        finally:
            # Notify about disconnect then clean up
            if self.client_kicked_handler:
                self.client_kicked_handler(client_address, "Disconnected")
            self.remove_client(client_socket, client_address)
    
    def kick_client(self, client_address):
        """Forcibly disconnect a client"""
        for client_socket, addr in self.clients:
            if addr == client_address:
                try:
                    # Send a kick message to the client
                    try:
                        self._send_framed(client_socket, '{"type": "kicked"}')
                    except:
                        pass  # Client might already be unresponsive

                    # Close the socket (handle_client finally block will clean up)
                    client_socket.close()
                    
                    # Call the kicked handler if set
                    if self.client_kicked_handler:
                        self.client_kicked_handler(addr, "Kicked by server")
                    
                    self.log.append(f"Client {addr} has been kicked")
                    return True
                except Exception as e:
                    self.log.append(f"Error kicking client {addr}: {e}")
                    return False
        
        self.log.append(f"Client {client_address} not found")
        return False
    
    def remove_client(self, client_socket, client_address):
        """Remove a client from the list and close their socket"""
        if (client_socket, client_address) in self.clients:
            self.clients.remove((client_socket, client_address))
            
            try:
                client_socket.close()
            except:
                pass  # Socket might already be closed
    
    def broadcast(self, message):
        """Send a message to all connected clients"""
        disconnected_clients = []

        for client_socket, client_address in list(self.clients):
            try:
                self._send_framed(client_socket, message)
                self.log.append(f"Broadcast message sent to {client_address}")
            except Exception:
                disconnected_clients.append((client_socket, client_address))

        for client in disconnected_clients:
            if client in self.clients:
                self.clients.remove(client)
    
    def send_to_client(self, client_address, message):
        """Send a message to a specific client by address"""
        for client_socket, addr in self.clients:
            if addr == client_address:
                try:
                    self._send_framed(client_socket, message)
                    self.log.append(f"Message sent to {client_address}")
                    return True
                except Exception as e:
                    self.log.append(f"Error sending to {client_address}: {e}")
                    return False

        self.log.append(f"Client {client_address} not found")
        return False
    
    def set_message_handler(self, handler_function):
        """Set a function to handle incoming messages"""
        self.message_handler = handler_function
    
    def set_client_kicked_handler(self, handler_function):
        """Set a function to handle client kick events"""
        self.client_kicked_handler = handler_function
    
    def close(self):
        """Close the server and all client connections"""
        self.running = False
        
        # Close all client connections
        for client_socket, _ in self.clients:
            try:
                client_socket.close()
            except:
                pass
        self.clients = []
        
        # Close server socket
        try:
            self.server_socket.close()
        except:
            pass