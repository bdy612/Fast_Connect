import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
from fast_connect import FastConnect


class FastConnectGUI:
    """Comprehensive GUI for FastConnect with friend requests and private chats"""

    def __init__(self, root, username=None, real_name=None, user_number=None):
        self.root = root
        self.root.title("Fast Connect - Friend Network")
        self.root.geometry("900x800")
        self.fc = FastConnect()

        # Apply credentials that came from the login window
        if username:
            self.fc.username = username
            self.fc.real_name = real_name or ''
            self.fc._save_data()
        self._user_number = user_number
        
        # Chat windows for private messages
        self.chat_windows = {}
        
        # Configure style
        style = ttk.Style()
        style.theme_use('clam')
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create tabs
        self.setup_tab = ttk.Frame(self.notebook)
        self.users_tab = ttk.Frame(self.notebook)
        self.friends_tab = ttk.Frame(self.notebook)
        self.broadcast_tab = ttk.Frame(self.notebook)
        
        self.notebook.add(self.setup_tab, text="Setup")
        self.notebook.add(self.users_tab, text="Users & Friends")
        self.notebook.add(self.friends_tab, text="Friends Chat")
        self.notebook.add(self.broadcast_tab, text="Broadcast")
        
        # Build UI
        self.build_setup_tab()
        self.build_users_tab()
        self.build_friends_tab()
        self.build_broadcast_tab()
        
        # Register callbacks
        self.fc.register_callback('server_started', self.on_server_started)
        self.fc.register_callback('server_stopped', self.on_server_stopped)
        self.fc.register_callback('connected_to_server', self.on_connected_to_server)
        self.fc.register_callback('disconnected_from_server', self.on_disconnected_from_server)
        self.fc.register_callback('registration_confirmed', self.on_registration_confirmed)
        self.fc.register_callback('friend_request_received', self.on_friend_request_received)
        self.fc.register_callback('friend_accepted', self.on_friend_accepted)
        self.fc.register_callback('friend_declined', self.on_friend_declined)
        self.fc.register_callback('private_message_received', self.on_private_message_received)
        self.fc.register_callback('broadcast_received', self.on_broadcast_received)
        self.fc.register_callback('users_list_received', self.on_users_list_received)
        self.fc.register_callback('system_message', self.on_system_message)
    
    def build_setup_tab(self):
        """Build setup tab with username, real name, and server connection"""
        frame = ttk.LabelFrame(self.setup_tab, text="User Setup", padding=10)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Account info banner
        if self._user_number is not None:
            info_frame = ttk.Frame(frame)
            info_frame.grid(row=0, column=0, columnspan=3, sticky=tk.EW, pady=(0, 8))
            ttk.Label(
                info_frame,
                text=f"Logged in as: {self.fc.username}   |   User #{self._user_number}",
                font=("Arial", 10, "bold"), foreground="#0055aa"
            ).pack(anchor=tk.W)

        row_offset = 1 if self._user_number is not None else 0

        # Username (read-only after login)
        ttk.Label(frame, text="Username:").grid(row=row_offset, column=0, sticky=tk.W, pady=5)
        self.username_var = tk.StringVar(value=self.fc.username or "")
        ttk.Entry(frame, textvariable=self.username_var, width=30,
                  state='readonly' if self._user_number else 'normal').grid(
            row=row_offset, column=1, sticky=tk.EW, pady=5)

        # Real Name (read-only after login)
        ttk.Label(frame, text="Real Name:").grid(row=row_offset + 1, column=0, sticky=tk.W, pady=5)
        self.real_name_var = tk.StringVar(value=self.fc.real_name or "")
        ttk.Entry(frame, textvariable=self.real_name_var, width=30,
                  state='readonly' if self._user_number else 'normal').grid(
            row=row_offset + 1, column=1, sticky=tk.EW, pady=5)

        # Server connection section
        server_frame = ttk.LabelFrame(frame, text="Connect to Server", padding=10)
        server_frame.grid(row=row_offset + 2, column=0, columnspan=3, sticky=tk.EW, pady=10)

        ttk.Label(server_frame, text="Server IP:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.server_ip_var = tk.StringVar(value="127.0.0.1")
        server_ip_entry = ttk.Entry(server_frame, textvariable=self.server_ip_var, width=30)
        server_ip_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)
        
        ttk.Label(server_frame, text="Port:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.server_port_var = tk.StringVar(value="9999")
        server_port_entry = ttk.Entry(server_frame, textvariable=self.server_port_var, width=30)
        server_port_entry.grid(row=1, column=1, sticky=tk.EW, pady=5)
        
        connect_btn_frame = ttk.Frame(server_frame)
        connect_btn_frame.grid(row=2, column=0, columnspan=2, pady=10)

        ttk.Button(connect_btn_frame, text="Connect to Server", command=self.connect_to_server).pack(side=tk.LEFT, padx=5)
        ttk.Button(connect_btn_frame, text="Disconnect", command=self.disconnect_from_server).pack(side=tk.LEFT, padx=5)

        self.connection_status_var = tk.StringVar(value="Disconnected")
        ttk.Label(connect_btn_frame, textvariable=self.connection_status_var, foreground="red").pack(side=tk.LEFT, padx=20)

        # Server start is handled exclusively by server_control.py
        note_frame = ttk.LabelFrame(frame, text="Server Management", padding=10)
        note_frame.grid(row=row_offset + 3, column=0, columnspan=3, sticky=tk.EW, pady=10)
        ttk.Label(note_frame,
                  text="Only the server admin can start or stop the server.\n"
                       "Run  server_control.py  to manage the server.",
                  foreground="#666666", font=("Arial", 9, "italic")).pack(anchor=tk.W)

        frame.columnconfigure(1, weight=1)
    
    def build_users_tab(self):
        """Build users and friend requests tab"""
        frame = ttk.Frame(self.users_tab, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Online users
        ttk.Label(frame, text="Online Users:", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=5)
        
        users_frame = ttk.Frame(frame)
        users_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.users_listbox = tk.Listbox(users_frame, height=8)
        self.users_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(users_frame, command=self.users_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.users_listbox.config(yscrollcommand=scrollbar.set)
        
        # User actions
        action_frame = ttk.Frame(frame)
        action_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(action_frame, text="Refresh Users", command=self.refresh_users).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Send Friend Request", command=self.send_friend_request).pack(side=tk.LEFT, padx=5)
        
        # Friend requests section
        ttk.Label(frame, text="Friend Requests:", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=5)
        
        requests_frame = ttk.Frame(frame)
        requests_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.requests_text = tk.Text(requests_frame, height=5, state=tk.DISABLED)
        self.requests_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(requests_frame, command=self.requests_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.requests_text.config(yscrollcommand=scrollbar.set)
        
        # Accept/Decline buttons
        request_btn_frame = ttk.Frame(frame)
        request_btn_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(request_btn_frame, text="Accept Request", command=self.accept_friend_request).pack(side=tk.LEFT, padx=5)
        ttk.Button(request_btn_frame, text="Decline Request", command=self.decline_friend_request).pack(side=tk.LEFT, padx=5)
        
        self.selected_request_var = tk.StringVar()
    
    def build_friends_tab(self):
        """Build friends chat tab"""
        frame = ttk.Frame(self.friends_tab, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Friends list
        ttk.Label(frame, text="Your Friends:", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=5)
        
        friends_frame = ttk.Frame(frame)
        friends_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.friends_listbox = tk.Listbox(friends_frame, height=6)
        self.friends_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(friends_frame, command=self.friends_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.friends_listbox.config(yscrollcommand=scrollbar.set)
        
        # Open chat button
        ttk.Button(frame, text="Open Chat Window", command=self.open_chat_window).pack(pady=5)
        
        # Chat display
        ttk.Label(frame, text="Chat Messages:", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=5)
        
        chat_display_frame = ttk.Frame(frame)
        chat_display_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.chat_display = tk.Text(chat_display_frame, height=10, state=tk.DISABLED)
        self.chat_display.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(chat_display_frame, command=self.chat_display.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.chat_display.config(yscrollcommand=scrollbar.set)
        
        # Message input
        ttk.Label(frame, text="Message:", font=("Arial", 9)).pack(anchor=tk.W, pady=2)
        self.private_message_input = tk.Text(frame, height=3)
        self.private_message_input.pack(fill=tk.X, pady=5)
        
        msg_button_frame = ttk.Frame(frame)
        msg_button_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(msg_button_frame, text="Send Private Message", command=self.send_private_message).pack(side=tk.LEFT, padx=5)
        ttk.Button(msg_button_frame, text="Refresh Messages", command=self.refresh_private_messages).pack(side=tk.LEFT, padx=5)
    
    def build_broadcast_tab(self):
        """Build broadcast tab"""
        frame = ttk.LabelFrame(self.broadcast_tab, text="Broadcast Messages (Auto-Encrypted)", padding=10)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Broadcast display
        ttk.Label(frame, text="Broadcast Messages:", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=5)
        
        broadcast_display_frame = ttk.Frame(frame)
        broadcast_display_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.broadcast_text = tk.Text(broadcast_display_frame, height=12, state=tk.DISABLED)
        self.broadcast_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(broadcast_display_frame, command=self.broadcast_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.broadcast_text.config(yscrollcommand=scrollbar.set)
        
        # Message input
        ttk.Label(frame, text="Message:", font=("Arial", 9)).pack(anchor=tk.W, pady=2)
        self.broadcast_input = tk.Text(frame, height=3)
        self.broadcast_input.pack(fill=tk.X, pady=5)
        
        ttk.Label(frame, text="Encryption: ON (Server Controlled - Cannot Be Changed)", foreground="green", font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=2)
        
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Send Broadcast to Everyone", command=self.send_broadcast).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Refresh Broadcasts", command=self.refresh_broadcasts).pack(side=tk.LEFT, padx=5)
    
    def set_username(self):
        """Set username"""
        try:
            username = self.username_var.get()
            self.fc.set_username(username)
            messagebox.showinfo("Success", f"Username set to: {username}")
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def set_real_name(self):
        """Set real name"""
        try:
            real_name = self.real_name_var.get()
            self.fc.set_real_name(real_name)
            messagebox.showinfo("Success", f"Real name set to: {real_name}")
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def start_local_server(self):
        """Start local server"""
        try:
            ip = self.listen_ip_var.get()
            port = int(self.listen_port_var.get())
            self.fc.set_server_address(ip, port)
            if self.fc.start_local_server():
                messagebox.showinfo("Success", f"Server started on {ip}:{port}")
                self.server_status_var.set(f"Server: Running ({ip}:{port})")
            else:
                messagebox.showerror("Error", "Failed to start server")
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def stop_local_server(self):
        """Stop local server"""
        if self.fc.stop_local_server():
            messagebox.showinfo("Success", "Server stopped")
            self.server_status_var.set("Server: Stopped")
        else:
            messagebox.showerror("Error", "Server is not running")
    
    def connect_to_server(self):
        """Connect to server"""
        try:
            ip = self.server_ip_var.get()
            port = int(self.server_port_var.get())
            
            def do_connect():
                if self.fc.connect_to_server(ip, port):
                    self.root.after(0, lambda: self.connection_status_var.set("Connected"))
                    self.root.after(0, lambda: messagebox.showinfo("Success", "Connected to server"))
                else:
                    self.root.after(0, lambda: messagebox.showerror("Error", "Failed to connect"))
            
            thread = threading.Thread(target=do_connect, daemon=True)
            thread.start()
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def disconnect_from_server(self):
        """Disconnect from server"""
        if self.fc.disconnect_from_server():
            self.connection_status_var.set("Disconnected")
            messagebox.showinfo("Success", "Disconnected from server")
        else:
            messagebox.showerror("Error", "Not connected")
    
    def refresh_users(self):
        """Refresh online users list"""
        self.fc.request_users_list()
    
    def send_friend_request(self):
        """Send friend request"""
        selection = self.users_listbox.curselection()
        if selection:
            username = self.users_listbox.get(selection[0])
            if username != self.fc.username:
                self.fc.send_friend_request(username)
                messagebox.showinfo("Success", f"Friend request sent to {username}")
            else:
                messagebox.showwarning("Warning", "Cannot friend yourself")
        else:
            messagebox.showwarning("Warning", "Please select a user")
    
    def accept_friend_request(self):
        """Accept friend request"""
        from_user = simpledialog.askstring("Accept Request", "Enter username of the person whose request to accept:")
        if from_user:
            self.fc.respond_to_friend_request(from_user, True)
            self.refresh_friends()
    
    def decline_friend_request(self):
        """Decline friend request"""
        from_user = simpledialog.askstring("Decline Request", "Enter username of the person whose request to decline:")
        if from_user:
            self.fc.respond_to_friend_request(from_user, False)
    
    def refresh_friends(self):
        """Refresh friends list"""
        self.friends_listbox.delete(0, tk.END)
        # Friends are stored in fc.friends dict
        for friend in self.fc.friends:
            self.friends_listbox.insert(tk.END, friend)
    
    def open_chat_window(self):
        """Open private chat window with selected friend"""
        selection = self.friends_listbox.curselection()
        if selection:
            friend = self.friends_listbox.get(selection[0])
            if friend not in self.chat_windows or not self.chat_windows[friend].winfo_exists():
                self.chat_windows[friend] = self.create_chat_window(friend)
            else:
                self.chat_windows[friend].lift()
        else:
            messagebox.showwarning("Warning", "Please select a friend")
    
    def create_chat_window(self, friend_username):
        """Create a private chat window"""
        chat_window = tk.Toplevel(self.root)
        chat_window.title(f"Chat with {friend_username} (Encrypted)")
        chat_window.geometry("500x400")
        
        # Chat display
        ttk.Label(chat_window, text=f"Chat with {friend_username}", font=("Arial", 10, "bold")).pack(anchor=tk.W, padx=10, pady=5)
        
        chat_frame = ttk.Frame(chat_window)
        chat_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        chat_text = tk.Text(chat_frame, height=12, state=tk.DISABLED)
        chat_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(chat_frame, command=chat_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        chat_text.config(yscrollcommand=scrollbar.set)
        
        # Message input
        ttk.Label(chat_window, text="Message (Auto-Encrypted):", font=("Arial", 9)).pack(anchor=tk.W, padx=10)
        
        message_input = tk.Text(chat_window, height=3)
        message_input.pack(fill=tk.X, padx=10, pady=5)
        
        def send():
            msg = message_input.get("1.0", tk.END).strip()
            if msg:
                self.fc.send_private_message(friend_username, msg)
                chat_text.config(state=tk.NORMAL)
                chat_text.insert(tk.END, f"You: {msg}\n")
                chat_text.config(state=tk.DISABLED)
                message_input.delete("1.0", tk.END)
            else:
                messagebox.showwarning("Warning", "Please enter a message")
        
        ttk.Button(chat_window, text="Send", command=send).pack(pady=10)
        
        # Store reference to chat text widget
        chat_window.chat_text = chat_text
        
        return chat_window
    
    def send_private_message(self):
        """Send private message"""
        selection = self.friends_listbox.curselection()
        if selection:
            friend = self.friends_listbox.get(selection[0])
            msg = self.private_message_input.get("1.0", tk.END).strip()
            if msg:
                self.fc.send_private_message(friend, msg)
                self.chat_display.config(state=tk.NORMAL)
                self.chat_display.insert(tk.END, f"You to {friend}: {msg}\n")
                self.chat_display.config(state=tk.DISABLED)
                self.private_message_input.delete("1.0", tk.END)
            else:
                messagebox.showwarning("Warning", "Please enter a message")
        else:
            messagebox.showwarning("Warning", "Please select a friend")
    
    def send_broadcast(self):
        """Send broadcast message"""
        msg = self.broadcast_input.get("1.0", tk.END).strip()
        if msg:
            self.fc.send_broadcast(msg)
            self.broadcast_text.config(state=tk.NORMAL)
            self.broadcast_text.insert(tk.END, f"[You]: {msg}\n")
            self.broadcast_text.config(state=tk.DISABLED)
            self.broadcast_input.delete("1.0", tk.END)
            messagebox.showinfo("Success", "Broadcast sent to everyone (Encrypted by Server)")
        else:
            messagebox.showwarning("Warning", "Please enter a message")
    
    def refresh_broadcasts(self):
        """Refresh broadcasts display"""
        self.broadcast_text.config(state=tk.NORMAL)
        self.broadcast_text.see(tk.END)
        self.broadcast_text.config(state=tk.DISABLED)
    
    def refresh_private_messages(self):
        """Refresh private messages display"""
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.see(tk.END)
        self.chat_display.config(state=tk.DISABLED)
    
    # Callbacks
    def on_server_started(self, data):
        """Handle server started"""
        self.server_status_var.set(f"Server: Running (:{data['port']})")
    
    def on_server_stopped(self, data):
        """Handle server stopped"""
        self.server_status_var.set("Server: Stopped")
    
    def on_connected_to_server(self, data):
        """Handle connected to server"""
        self.connection_status_var.set("Connected")
        self.add_status_message(f"Connected to {data['host']}:{data['port']}")

    def on_registration_confirmed(self, data):
        """Server confirmed registration — populate friends list from server data (network thread)"""
        def _update():
            self.refresh_friends()
            n = len(self.fc.friends)
            if n:
                self.add_status_message(
                    f"Friends list restored: {', '.join(self.fc.friends.keys())}")
        self.root.after(0, _update)
    
    def on_disconnected_from_server(self, data):
        """Handle disconnected from server"""
        self.connection_status_var.set("Disconnected")
        self.add_status_message("Disconnected from server")
    
    def on_friend_request_received(self, data):
        """Handle friend request (called from network thread)"""
        from_user = data.get('from_user')
        def _update():
            self.requests_text.config(state=tk.NORMAL)
            self.requests_text.insert(tk.END, f"Friend request from: {from_user}\n")
            self.requests_text.config(state=tk.DISABLED)
            messagebox.showinfo("Friend Request", f"{from_user} sent you a friend request!")
        self.root.after(0, _update)
    
    def on_friend_accepted(self, data):
        """Handle friend accepted (called from network thread)"""
        friend = data.get('friend')
        def _update():
            messagebox.showinfo("Friend Added", f"You are now friends with {friend}")
            self.refresh_friends()
        self.root.after(0, _update)
    
    def on_friend_declined(self, data):
        """Handle friend declined (called from network thread)"""
        friend = data.get('friend')
        self.root.after(0, lambda: messagebox.showinfo(
            "Request Declined", f"{friend} declined your friend request"))
    
    def on_private_message_received(self, data):
        """Handle private message (called from network thread)"""
        from_user = data.get('from')
        message = data.get('message')
        def _update():
            self.chat_display.config(state=tk.NORMAL)
            self.chat_display.insert(tk.END, f"{from_user}: {message}\n")
            self.chat_display.see(tk.END)
            self.chat_display.config(state=tk.DISABLED)
            if from_user in self.chat_windows and self.chat_windows[from_user].winfo_exists():
                self.chat_windows[from_user].chat_text.config(state=tk.NORMAL)
                self.chat_windows[from_user].chat_text.insert(tk.END, f"{from_user}: {message}\n")
                self.chat_windows[from_user].chat_text.see(tk.END)
                self.chat_windows[from_user].chat_text.config(state=tk.DISABLED)
        self.root.after(0, _update)
    
    def on_broadcast_received(self, data):
        """Handle broadcast message (called from network thread)"""
        from_user = data.get('from')
        message = data.get('message')
        def _update():
            self.broadcast_text.config(state=tk.NORMAL)
            self.broadcast_text.insert(tk.END, f"[{from_user}]: {message}\n")
            self.broadcast_text.see(tk.END)
            self.broadcast_text.config(state=tk.DISABLED)
        self.root.after(0, _update)
    
    def on_users_list_received(self, data):
        """Handle users list (called from network thread)"""
        users = data.get('users', [])
        def _update():
            self.users_listbox.delete(0, tk.END)
            for user in users:
                if user != self.fc.username:
                    self.users_listbox.insert(tk.END, user)
        self.root.after(0, _update)
    
    def on_system_message(self, data):
        """Handle system message (called from network thread)"""
        message = data.get('message')
        def _update():
            self.broadcast_text.config(state=tk.NORMAL)
            self.broadcast_text.insert(tk.END, f"[SYSTEM]: {message}\n")
            self.broadcast_text.see(tk.END)
            self.broadcast_text.config(state=tk.DISABLED)
        self.root.after(0, _update)
    
    def add_status_message(self, message):
        """Add status message to broadcast tab"""
        self.broadcast_text.config(state=tk.NORMAL)
        self.broadcast_text.insert(tk.END, f">>> {message}\n")
        self.broadcast_text.config(state=tk.DISABLED)


def main():
    """Main entry point — show login window first, then the main app"""
    from login import LoginWindow

    login_root = tk.Tk()
    login_root.resizable(False, False)

    def on_login_success(username, real_name, user_number):
        login_root.destroy()
        main_root = tk.Tk()
        FastConnectGUI(main_root, username=username, real_name=real_name, user_number=user_number)
        main_root.mainloop()

    LoginWindow(login_root, on_login_success)
    login_root.mainloop()


if __name__ == '__main__':
    main()
