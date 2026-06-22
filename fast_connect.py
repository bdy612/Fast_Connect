import json
import os
import threading
import random
import string
from client import Client
from server import Server
from main import Encription
import gdrive_storage

_USERS_DB_FILENAME = 'users_db.json'
_USERS_DB_DEFAULT = {'users': {}, 'friendships': {}, 'next_user_number': 1}


def _load_db():
    """Load users_db.json from Google Drive, returning an empty template if missing."""
    try:
        data = gdrive_storage.load_json(_USERS_DB_FILENAME, default=None)
        if data is not None:
            return data
    except Exception:
        pass
    return dict(_USERS_DB_DEFAULT)


def _save_db(db):
    """Write db dict back to users_db.json on Google Drive."""
    gdrive_storage.save_json(_USERS_DB_FILENAME, db)


class FastConnectServer:
    """Server-side FastConnect with multi-layer encryption"""
    
    def __init__(self, host='0.0.0.0', port=9999):
        self.host = host
        self.port = port
        self.server = None
        self.users = {}  # username -> {'address': addr, 'real_name': name}
        self.friend_requests = {}  # username -> [list of pending requests]
        self.friendships = {}  # username -> [list of accepted friends]
        self.muted_from_broadcast = set()  # usernames who cannot send broadcasts
        self.server_master_key = None    # the 16th key, set by the server admin
        self.encryption_key = self._generate_multi_layer_key()
        self.encryption_type = Encription.VIGENERE  # Vigenère: reversible with key only
        self.callbacks = {}
        
    def _generate_multi_layer_key(self, iterations=15):
        """Generate multi-layer randomized encryption key (15 iterations)"""
        key = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
        for _ in range(iterations - 1):
            sub_key = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
            key = f"{key}|{sub_key}"
        return key
    
    def start(self):
        """Start the server"""
        try:
            self.server = Server(self.host, self.port)
            self.server.set_message_handler(self._handle_message)
            self.server.set_client_kicked_handler(self._handle_client_kicked)
            self._trigger_callback('server_started', {'host': self.host, 'port': self.port})
            return True
        except Exception as e:
            print(f"Error starting server: {e}")
            self._trigger_callback('server_error', {'error': str(e)})
            return False
    
    def stop(self):
        """Stop the server"""
        if self.server:
            self.server.close()
            self.server = None
            self._trigger_callback('server_stopped', {})
            return True
        return False
    
    def _handle_message(self, client_address, message):
        """Handle incoming messages on the server"""
        try:
            data = json.loads(message)
            msg_type = data.get('type')
            
            if msg_type == 'register':
                self._handle_register(client_address, data)
            elif msg_type == 'friend_request':
                self._handle_friend_request(client_address, data)
            elif msg_type == 'friend_response':
                self._handle_friend_response(client_address, data)
            elif msg_type == 'private_message':
                self._handle_private_message(client_address, data)
            elif msg_type == 'broadcast':
                self._handle_broadcast(client_address, data)
            elif msg_type == 'list_users':
                self._handle_list_users(client_address)
            
        except Exception as e:
            print(f"Error handling message: {e}")
    
    def _handle_register(self, client_address, data):
        """Handle user registration"""
        username = data.get('username')
        real_name = data.get('real_name', '')

        if username not in self.users:
            self.users[username] = {
                'address': client_address,
                'real_name': real_name
            }
            self.friend_requests[username] = []

            # Load persisted friendships so they survive reconnects
            db = _load_db()
            stored = db.get('friendships', {}).get(username, [])
            self.friendships[username] = list(stored)

            # Build a name-map of existing friends to send back
            friends_details = {}
            for fname in stored:
                friends_details[fname] = {
                    'real_name': db.get('users', {}).get(fname, {}).get('real_name', '')
                }

            # Notify all users about new user
            self._broadcast_system_message(f"{username} joined the server")
            self._trigger_callback('user_registered', {'username': username, 'real_name': real_name})

            # Send acknowledgement: encryption key + existing friends list
            response = {
                'type': 'register_ack',
                'status': 'success',
                'encryption_key': self.encryption_key,
                'encryption_type': self.encryption_type,
                'friends': friends_details   # {username: {real_name: ...}}
            }
            self.server.send_to_client(client_address, json.dumps(response))
    
    def _handle_friend_request(self, client_address, data):
        """Handle friend request"""
        from_user = data.get('from_user')
        to_user = data.get('to_user')
        
        if to_user in self.users:
            if from_user not in self.friend_requests[to_user]:
                self.friend_requests[to_user].append(from_user)
            
            notification = {
                'type': 'friend_request_notification',
                'from_user': from_user,
                'real_name': self.users[from_user]['real_name']
            }
            self.server.send_to_client(
                self.users[to_user]['address'],
                json.dumps(notification)
            )
            
            self._trigger_callback('friend_request_sent', {'from': from_user, 'to': to_user})
    
    def _handle_friend_response(self, client_address, data):
        """Handle friend request response (accept/decline)"""
        from_user = data.get('from_user')
        to_user = data.get('to_user')
        accepted = data.get('accepted', False)
        
        if from_user in self.friend_requests.get(to_user, []):
            self.friend_requests[to_user].remove(from_user)
        
        if accepted:
            if from_user not in self.friendships[to_user]:
                self.friendships[to_user].append(from_user)
            if to_user not in self.friendships[from_user]:
                self.friendships[from_user].append(to_user)
            
            notification = {
                'type': 'friend_accepted',
                'friend_username': from_user,
                'friend_real_name': self.users[from_user]['real_name']
            }
            self.server.send_to_client(
                self.users[to_user]['address'],
                json.dumps(notification)
            )
            
            notification2 = {
                'type': 'friend_accepted',
                'friend_username': to_user,
                'friend_real_name': self.users[to_user]['real_name']
            }
            self.server.send_to_client(
                self.users[from_user]['address'],
                json.dumps(notification2)
            )
            
            self._trigger_callback('friendship_established', {'user1': from_user, 'user2': to_user})

            # ---- Persist the new friendship so it survives reconnects ----
            db = _load_db()
            fs = db.setdefault('friendships', {})
            fs.setdefault(from_user, [])
            fs.setdefault(to_user, [])
            if to_user not in fs[from_user]:
                fs[from_user].append(to_user)
            if from_user not in fs[to_user]:
                fs[to_user].append(from_user)
            _save_db(db)
        else:
            notification = {
                'type': 'friend_declined',
                'friend_username': to_user
            }
            self.server.send_to_client(
                self.users[from_user]['address'],
                json.dumps(notification)
            )
    
    def _handle_private_message(self, client_address, data):
        """Handle private message between friends"""
        from_user = data.get('from_user')
        to_user = data.get('to_user')
        message = data.get('message')
        
        if to_user in self.friendships.get(from_user, []):
            encrypted = self._encrypt_with_layers(message)
            
            msg_obj = {
                'type': 'private_message',
                'from_user': from_user,
                'message': encrypted,
                'encrypted': True
            }
            
            self.server.send_to_client(
                self.users[to_user]['address'],
                json.dumps(msg_obj)
            )
            
            self._trigger_callback('private_message', {'from': from_user, 'to': to_user})
    
    def _handle_broadcast(self, client_address, data):
        """Handle broadcast message to all users"""
        from_user = data.get('from_user')
        message = data.get('message')

        # Respect server mute list
        if from_user in self.muted_from_broadcast:
            if from_user in self.users:
                notice = {'type': 'system_message',
                          'message': 'You are muted from broadcasting by the server.'}
                self.server.send_to_client(self.users[from_user]['address'], json.dumps(notice))
            return

        encrypted = self._encrypt_with_layers(message)
        
        broadcast_obj = {
            'type': 'broadcast_message',
            'from_user': from_user,
            'message': encrypted,
            'encrypted': True
        }
        
        self.server.broadcast(json.dumps(broadcast_obj))
        self._trigger_callback('broadcast_sent', {'from_user': from_user})
    
    def _handle_list_users(self, client_address):
        """Send list of connected users"""
        users_list = list(self.users.keys())
        response = {
            'type': 'users_list',
            'users': users_list
        }
        self.server.send_to_client(client_address, json.dumps(response))
    
    def _handle_client_kicked(self, client_address, reason):
        """Handle client disconnect (normal or kicked)"""
        username_to_remove = None
        for username, user_data in self.users.items():
            if user_data['address'] == client_address:
                username_to_remove = username
                break

        if username_to_remove:
            del self.users[username_to_remove]
            self.friend_requests.pop(username_to_remove, None)
            self.friendships.pop(username_to_remove, None)
            self._broadcast_system_message(f"{username_to_remove} left the server")
            self._trigger_callback('user_disconnected', {'username': username_to_remove})
    
    def _encrypt_with_layers(self, message, iterations=15):
        """Encrypt message through 15 Vigenère layers"""
        result = message
        keys = self.encryption_key.split('|') if '|' in self.encryption_key else [self.encryption_key]

        for i in range(min(iterations, len(keys))):
            try:
                result = Encription.encrypt(
                    result,
                    {'key': keys[i]},
                    Encription.VIGENERE
                )['text']
            except Exception:
                pass

        return result
    
    def _broadcast_system_message(self, message):
        """Broadcast a system message to all users"""
        if self.server:
            broadcast_obj = {
                'type': 'system_message',
                'message': message
            }
            self.server.broadcast(json.dumps(broadcast_obj))
    
    def register_callback(self, event_name, callback):
        """Register callback for events"""
        if event_name not in self.callbacks:
            self.callbacks[event_name] = []
        self.callbacks[event_name].append(callback)

    def _trigger_callback(self, event_name, data):
        """Trigger callbacks"""
        if event_name in self.callbacks:
            for callback in self.callbacks[event_name]:
                try:
                    callback(data)
                except Exception as e:
                    print(f"Error in callback {event_name}: {e}")

    # ------------------------------------------------------------------
    # Server admin controls
    # ------------------------------------------------------------------
    def kick_user(self, username):
        """Kick a connected user by username"""
        if username in self.users and self.server:
            address = self.users[username]['address']
            self.server.kick_client(address)
            return True
        return False

    def mute_user(self, username):
        """Prevent a user from sending broadcasts"""
        self.muted_from_broadcast.add(username)
        if username in self.users and self.server:
            notice = {'type': 'system_message',
                      'message': 'The server has muted you from broadcasting.'}
            self.server.send_to_client(self.users[username]['address'], json.dumps(notice))

    def unmute_user(self, username):
        """Allow a user to send broadcasts again"""
        self.muted_from_broadcast.discard(username)
        if username in self.users and self.server:
            notice = {'type': 'system_message',
                      'message': 'The server has unmuted you — you can broadcast again.'}
            self.server.send_to_client(self.users[username]['address'], json.dumps(notice))

    def set_server_master_key(self, key):
        """Set the server admin's master key as the 16th encryption layer"""
        self.server_master_key = key
        base_keys = self.encryption_key.split('|')
        # Keep only first 15 auto-generated keys, then append master key
        base_keys = base_keys[:15]
        if key:
            base_keys.append(key)
        self.encryption_key = '|'.join(base_keys)

    def regenerate_keys(self):
        """Re-generate all 15 random keys, keep the master key if set"""
        self.encryption_key = self._generate_multi_layer_key(15)
        if self.server_master_key:
            self.encryption_key = self.encryption_key + '|' + self.server_master_key

    def get_encryption_layers(self):
        """Return the list of encryption layer keys"""
        return self.encryption_key.split('|')

    def broadcast_as_server(self, message):
        """Send a broadcast from the server itself (not from any user)"""
        if not self.server:
            return
        encrypted = self._encrypt_with_layers(message)
        payload = {
            'type': 'broadcast_message',
            'from_user': '[SERVER]',
            'message': encrypted,
            'encrypted': True
        }
        self.server.broadcast(json.dumps(payload))
        self._trigger_callback('broadcast_sent', {'from_user': '[SERVER]'})


class FastConnect:
    """Client-side FastConnect"""
    
    def __init__(self, data_file='fc_data.json'):
        """Initialize FastConnect with data persistence"""
        self.data_file = data_file
        self.username = None
        self.real_name = None
        self.server_ip = None
        self.server_port = None
        self.client = None
        self.server = None
        self.friends = {}            # username -> {'real_name': name}
        self.encryption_key = None   # received from server on registration
        self.encryption_type = None
        self.callbacks = {}  # Callbacks for events
        
        # Load existing data
        self.load_data()
    
    def load_data(self):
        """Load user data from JSON file"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    self.username = data.get('username')
                    self.real_name = data.get('real_name', '')
                    self.server_ip = data.get('server_ip')
                    self.server_port = data.get('server_port')
            else:
                self._save_data()
        except Exception as e:
            print(f"Error loading data: {e}")
    
    def _save_data(self):
        """Save user data to JSON file"""
        try:
            data = {
                'username': self.username,
                'real_name': self.real_name,
                'server_ip': self.server_ip,
                'server_port': self.server_port
            }
            with open(self.data_file, 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Error saving data: {e}")
    
    def set_username(self, username):
        """Set the current user's username"""
        if not username or len(username) < 3:
            raise ValueError("Username must be at least 3 characters long")
        
        self.username = username
        self._save_data()
        self._trigger_callback('username_set', {'username': username})
        return True
    
    def set_real_name(self, real_name):
        """Set real name"""
        self.real_name = real_name
        self._save_data()
        self._trigger_callback('real_name_set', {'real_name': real_name})
    
    def get_username(self):
        """Get the current user's username"""
        return self.username
    
    def set_server_address(self, ip, port):
        """Set the server address"""
        self.server_ip = ip
        self.server_port = int(port)
        self._save_data()
        self._trigger_callback('server_set', {'ip': ip, 'port': port})
    
    def get_server_address(self):
        """Get the current server address"""
        return f"{self.server_ip}:{self.server_port}" if self.server_ip else None
    
    def start_local_server(self):
        """Start a local FastConnect server"""
        try:
            self.server = FastConnectServer(
                self.server_ip or '0.0.0.0', 
                self.server_port or 9999
            )
            if self.server.start():
                self._trigger_callback('server_started', {'port': self.server_port or 9999})
                return True
        except Exception as e:
            print(f"Error starting server: {e}")
        return False
    
    def stop_local_server(self):
        """Stop local server"""
        if self.server:
            self.server.stop()
            self._trigger_callback('server_stopped', {})
            return True
        return False
    
    def connect_to_server(self, host, port):
        """Connect to server as client"""
        try:
            self.client = Client(host, int(port))
            self.client.set_message_callback(self._handle_client_message)
            self.client.set_disconnect_callback(self._handle_disconnect)
            
            # Send registration
            if self.username:
                register_msg = {
                    'type': 'register',
                    'username': self.username,
                    'real_name': self.real_name
                }
                self.client.send(json.dumps(register_msg))
            
            self._trigger_callback('connected_to_server', {'host': host, 'port': port})
            return True
        except Exception as e:
            print(f"Error connecting: {e}")
            self._trigger_callback('connection_error', {'error': str(e)})
            return False
    
    def disconnect_from_server(self):
        """Disconnect from server"""
        if self.client:
            self.client.close()
            self.client = None
            self._trigger_callback('disconnected_from_server', {})
            return True
        return False
    
    def _handle_client_message(self, message):
        """Handle incoming messages"""
        try:
            data = json.loads(message)
            msg_type = data.get('type')
            
            if msg_type == 'register_ack':
                self.encryption_key = data.get('encryption_key')
                self.encryption_type = data.get('encryption_type')
                # Restore friends that the server already knows about
                server_friends = data.get('friends', {})
                self.friends = dict(server_friends)  # {username: {real_name: ...}}
                self._trigger_callback('registration_confirmed', {
                    'username': self.username,
                    'friends': self.friends
                })
            
            elif msg_type == 'friend_request_notification':
                from_user = data.get('from_user')
                self._trigger_callback('friend_request_received', {'from_user': from_user})
            
            elif msg_type == 'friend_accepted':
                friend_username = data.get('friend_username')
                friend_real_name = data.get('friend_real_name', '')
                self.friends[friend_username] = {'real_name': friend_real_name}
                self._trigger_callback('friend_accepted', {'friend': friend_username})
            
            elif msg_type == 'friend_declined':
                friend_username = data.get('friend_username')
                self._trigger_callback('friend_declined', {'friend': friend_username})
            
            elif msg_type == 'private_message':
                from_user = data.get('from_user')
                message_text = data.get('message')
                if data.get('encrypted') and self.encryption_key:
                    message_text = self._decrypt_with_layers(message_text)
                self._trigger_callback('private_message_received', {'from': from_user, 'message': message_text})

            elif msg_type == 'broadcast_message':
                from_user = data.get('from_user')
                broadcast_msg = data.get('message')
                if data.get('encrypted') and self.encryption_key:
                    broadcast_msg = self._decrypt_with_layers(broadcast_msg)
                self._trigger_callback('broadcast_received', {'from': from_user, 'message': broadcast_msg})
            
            elif msg_type == 'users_list':
                users = data.get('users', [])
                self._trigger_callback('users_list_received', {'users': users})
            
            elif msg_type == 'system_message':
                system_msg = data.get('message')
                self._trigger_callback('system_message', {'message': system_msg})
            
        except Exception as e:
            print(f"Error handling message: {e}")
    
    def _decrypt_with_layers(self, message):
        """Decrypt a message through the 15 Vigenère layers in reverse order"""
        if not self.encryption_key:
            return message
        keys = self.encryption_key.split('|')
        result = message
        for key in reversed(keys):
            try:
                result = Encription.decrypt({
                    'type': Encription.VIGENERE,
                    'text': result,
                    'params': {'key': key}
                })
            except Exception:
                pass
        return result

    def _handle_disconnect(self, reason):
        """Handle disconnect"""
        self._trigger_callback('disconnected', {'reason': reason})
    
    def send_friend_request(self, to_user):
        """Send friend request"""
        if self.client:
            msg = {
                'type': 'friend_request',
                'from_user': self.username,
                'to_user': to_user
            }
            self.client.send(json.dumps(msg))
            self._trigger_callback('friend_request_sent', {'to': to_user})
    
    def respond_to_friend_request(self, from_user, accepted):
        """Respond to friend request"""
        if self.client:
            msg = {
                'type': 'friend_response',
                'from_user': from_user,
                'to_user': self.username,
                'accepted': accepted
            }
            self.client.send(json.dumps(msg))
    
    def send_private_message(self, to_user, message):
        """Send private message to friend"""
        if self.client:
            msg = {
                'type': 'private_message',
                'from_user': self.username,
                'to_user': to_user,
                'message': message
            }
            self.client.send(json.dumps(msg))
            self._trigger_callback('private_message_sent', {'to': to_user, 'message': message})
    
    def send_broadcast(self, message):
        """Send broadcast message to all users"""
        if self.client:
            msg = {
                'type': 'broadcast',
                'from_user': self.username,
                'message': message
            }
            self.client.send(json.dumps(msg))
            self._trigger_callback('broadcast_sent', {'message': message})
    
    def request_users_list(self):
        """Request list of online users"""
        if self.client:
            msg = {'type': 'list_users'}
            self.client.send(json.dumps(msg))
    
    def register_callback(self, event_name, callback):
        """Register event callback"""
        if event_name not in self.callbacks:
            self.callbacks[event_name] = []
        self.callbacks[event_name].append(callback)
    
    def _trigger_callback(self, event_name, data):
        """Trigger callbacks"""
        if event_name in self.callbacks:
            for callback in self.callbacks[event_name]:
                try:
                    callback(data)
                except Exception as e:
                    print(f"Error in callback: {e}")
    
    def get_status(self):
        """Get current status"""
        return {
            'username': self.username,
            'real_name': self.real_name,
            'server_running': self.server is not None,
            'connected_to_server': self.client is not None and self.client.running if self.client else False,
            'encryption_enabled': True
        }


if __name__ == '__main__':
    fc = FastConnect()
    fc.set_username('TestUser')
    fc.set_real_name('Test User')
    print(f"Status: {fc.get_status()}")