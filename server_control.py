"""
server_control.py — Fast Connect Server Administration Panel
============================================================
Run this file to start and manage the server.
Clients use gui.py; only the admin uses this file.
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import json
import os
import hashlib
import datetime
from fast_connect import FastConnectServer

SERVER_CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'server_config.json')


# ------------------------------------------------------------------
# Config helpers
# ------------------------------------------------------------------
def _hash(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _load_cfg():
    if os.path.exists(SERVER_CONFIG_FILE):
        try:
            with open(SERVER_CONFIG_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_cfg(cfg):
    with open(SERVER_CONFIG_FILE, 'w') as f:
        json.dump(cfg, f, indent=4)


# ------------------------------------------------------------------
# Main app
# ------------------------------------------------------------------
class ServerControlApp:
    """Server admin control panel."""

    def __init__(self, root):
        self.root = root
        self.root.title("Fast Connect — Server Control Panel")
        self.root.geometry("980x740")
        self.root.resizable(True, True)

        self.fc_server = None           # FastConnectServer, created on Start
        self._running = False

        # Must authenticate before anything else
        if not self._authenticate():
            self.root.after(100, self.root.destroy)
            return

        self._build_ui()
        # Auto-refresh every 4 seconds
        self._schedule_refresh()

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------
    def _authenticate(self):
        cfg = _load_cfg()
        if 'admin_password_hash' not in cfg:
            # First launch — choose an admin password
            while True:
                pwd = simpledialog.askstring(
                    "Create Admin Password",
                    "First launch!\nCreate a server admin password (min 4 chars):",
                    show='*', parent=self.root)
                if pwd is None:
                    return False
                if len(pwd) < 4:
                    messagebox.showerror("Too Short", "Password needs at least 4 characters.",
                                         parent=self.root)
                    continue
                cfg['admin_password_hash'] = _hash(pwd)
                _save_cfg(cfg)
                messagebox.showinfo("Password Set",
                                    "Admin password created. Welcome, Server Admin!",
                                    parent=self.root)
                return True
        else:
            pwd = simpledialog.askstring(
                "Server Admin Login",
                "Enter admin password:", show='*', parent=self.root)
            if pwd is None:
                return False
            if _hash(pwd) != cfg['admin_password_hash']:
                messagebox.showerror("Access Denied", "Incorrect password.", parent=self.root)
                return False
            return True

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self):
        # Header
        ttk.Label(self.root,
                  text="Fast Connect — Server Control Panel",
                  font=("Arial", 14, "bold")).pack(pady=(10, 2))

        # Status bar (below header)
        self.status_var = tk.StringVar(value="● Server: Stopped")
        self._status_lbl = ttk.Label(self.root, textvariable=self.status_var,
                                     foreground="red", font=("Arial", 10, "bold"))
        self._status_lbl.pack(pady=(0, 4))

        # Tabs
        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        tabs = [
            ("  Server  ",        "_tab_server"),
            ("  Encryption  ",    "_tab_enc"),
            ("  Users & Control  ", "_tab_users"),
            ("  Broadcast  ",     "_tab_bc"),
            ("  Logs  ",          "_tab_logs"),
        ]
        for text, attr in tabs:
            frame = ttk.Frame(self.nb, padding=10)
            setattr(self, attr, frame)
            self.nb.add(frame, text=text)

        self._build_server_tab()
        self._build_encryption_tab()
        self._build_users_tab()
        self._build_broadcast_tab()
        self._build_logs_tab()

    # ---- Server tab ---------------------------------------------------
    def _build_server_tab(self):
        f = self._tab_server

        cfg_frame = ttk.LabelFrame(f, text="Server Configuration", padding=10)
        cfg_frame.pack(fill=tk.X, pady=6)
        cfg_frame.columnconfigure(1, weight=1)

        ttk.Label(cfg_frame, text="Listen IP:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.srv_ip = tk.StringVar(value="0.0.0.0")
        ttk.Entry(cfg_frame, textvariable=self.srv_ip, width=22).grid(
            row=0, column=1, sticky=tk.EW, padx=6)

        ttk.Label(cfg_frame, text="Port:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.srv_port = tk.StringVar(value="9999")
        ttk.Entry(cfg_frame, textvariable=self.srv_port, width=22).grid(
            row=1, column=1, sticky=tk.EW, padx=6)

        btn_f = ttk.Frame(f)
        btn_f.pack(pady=10)
        ttk.Button(btn_f, text="▶  Start Server",
                   command=self._start_server).pack(side=tk.LEFT, padx=8)
        ttk.Button(btn_f, text="■  Stop Server",
                   command=self._stop_server).pack(side=tk.LEFT, padx=8)

        # Live stats
        stats = ttk.LabelFrame(f, text="Live Stats", padding=10)
        stats.pack(fill=tk.X, pady=6)

        self.v_users   = tk.StringVar(value="Connected users: 0")
        self.v_friends = tk.StringVar(value="Active friendships: 0")
        self.v_muted   = tk.StringVar(value="Muted from broadcast: 0")
        self.v_pending = tk.StringVar(value="Pending friend requests: 0")

        for var in (self.v_users, self.v_friends, self.v_muted, self.v_pending):
            ttk.Label(stats, textvariable=var).pack(anchor=tk.W, pady=1)

        ttk.Button(f, text="Refresh Stats", command=self._refresh_stats).pack(pady=4)

    # ---- Encryption tab -----------------------------------------------
    def _build_encryption_tab(self):
        f = self._tab_enc

        ttk.Label(f, text="Encryption Layers",
                  font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 4))
        ttk.Label(f,
                  text="Layers 1-15 are auto-generated randomly by the server.\n"
                       "Layer 16 is the Master Key that only the server admin sets.",
                  foreground="#555").pack(anchor=tk.W, pady=(0, 6))

        # Scrollable key display
        kf = ttk.Frame(f)
        kf.pack(fill=tk.BOTH, expand=True)
        self.keys_text = tk.Text(kf, height=13, state=tk.DISABLED,
                                 font=("Courier", 9), wrap=tk.NONE)
        ys = ttk.Scrollbar(kf, command=self.keys_text.yview)
        xs = ttk.Scrollbar(kf, orient=tk.HORIZONTAL, command=self.keys_text.xview)
        self.keys_text.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        ys.pack(side=tk.RIGHT, fill=tk.Y)
        xs.pack(side=tk.BOTTOM, fill=tk.X)
        self.keys_text.pack(fill=tk.BOTH, expand=True)

        # Master key entry
        mf = ttk.LabelFrame(f, text="Server Master Key (Layer 16 — set by admin)", padding=8)
        mf.pack(fill=tk.X, pady=8)
        mf.columnconfigure(1, weight=1)

        ttk.Label(mf, text="Master Key:").grid(row=0, column=0, sticky=tk.W, padx=4)
        self.master_key_var = tk.StringVar()
        self._master_entry = ttk.Entry(mf, textvariable=self.master_key_var, width=32, show="*")
        self._master_entry.grid(row=0, column=1, sticky=tk.EW, padx=4)
        ttk.Button(mf, text="Show",
                   command=lambda: self._toggle_show(self._master_entry)).grid(
            row=0, column=2, padx=4)
        ttk.Button(mf, text="Apply as Layer 16",
                   command=self._apply_master_key).grid(row=0, column=3, padx=4)

        bf = ttk.Frame(f)
        bf.pack(pady=4)
        ttk.Button(bf, text="Regenerate Layers 1–15",
                   command=self._regen_keys).pack(side=tk.LEFT, padx=6)
        ttk.Button(bf, text="Refresh Display",
                   command=self._refresh_keys).pack(side=tk.LEFT, padx=6)

    # ---- Users & Control tab ------------------------------------------
    def _build_users_tab(self):
        f = self._tab_users

        ttk.Label(f, text="Connected Users",
                  font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 4))

        tree_f = ttk.Frame(f)
        tree_f.pack(fill=tk.BOTH, expand=True)

        cols = ("no", "username", "real_name", "address", "broadcast")
        self.users_tree = ttk.Treeview(tree_f, columns=cols, show="headings", height=13)
        self.users_tree.heading("no",          text="#")
        self.users_tree.heading("username",    text="Username")
        self.users_tree.heading("real_name",   text="Real Name")
        self.users_tree.heading("address",     text="Address")
        self.users_tree.heading("broadcast",   text="Broadcast")
        self.users_tree.column("no",        width=40,  anchor=tk.CENTER)
        self.users_tree.column("username",  width=120)
        self.users_tree.column("real_name", width=160)
        self.users_tree.column("address",   width=150)
        self.users_tree.column("broadcast", width=90, anchor=tk.CENTER)

        ys = ttk.Scrollbar(tree_f, command=self.users_tree.yview)
        self.users_tree.configure(yscrollcommand=ys.set)
        ys.pack(side=tk.RIGHT, fill=tk.Y)
        self.users_tree.pack(fill=tk.BOTH, expand=True)

        ctrl_f = ttk.Frame(f)
        ctrl_f.pack(fill=tk.X, pady=8)

        ttk.Button(ctrl_f, text="Kick Selected",
                   command=self._kick_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(ctrl_f, text="Mute Broadcast",
                   command=self._mute_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(ctrl_f, text="Unmute Broadcast",
                   command=self._unmute_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(ctrl_f, text="Refresh List",
                   command=self._refresh_users).pack(side=tk.LEFT, padx=5)

    # ---- Broadcast tab ------------------------------------------------
    def _build_broadcast_tab(self):
        f = self._tab_bc

        ttk.Label(f, text="Broadcast Control",
                  font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 4))

        hist_f = ttk.Frame(f)
        hist_f.pack(fill=tk.BOTH, expand=True)
        self.bc_text = tk.Text(hist_f, state=tk.DISABLED, height=14, wrap=tk.WORD)
        ys = ttk.Scrollbar(hist_f, command=self.bc_text.yview)
        self.bc_text.configure(yscrollcommand=ys.set)
        ys.pack(side=tk.RIGHT, fill=tk.Y)
        self.bc_text.pack(fill=tk.BOTH, expand=True)

        send_f = ttk.LabelFrame(f, text="Send Broadcast as [SERVER]", padding=8)
        send_f.pack(fill=tk.X, pady=8)

        self.bc_input = tk.Text(send_f, height=3)
        self.bc_input.pack(fill=tk.X, pady=4)

        btn_f = ttk.Frame(send_f)
        btn_f.pack()
        ttk.Button(btn_f, text="Send Broadcast",
                   command=self._send_server_broadcast).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_f, text="Clear History",
                   command=self._clear_bc_history).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_f, text="Refresh",
                   command=lambda: self.bc_text.see(tk.END)).pack(side=tk.LEFT, padx=5)

    # ---- Logs tab -----------------------------------------------------
    def _build_logs_tab(self):
        f = self._tab_logs

        ttk.Label(f, text="Server Activity Log",
                  font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 4))

        log_f = ttk.Frame(f)
        log_f.pack(fill=tk.BOTH, expand=True)
        self.log_text = tk.Text(log_f, state=tk.DISABLED, height=22,
                                font=("Courier", 9), wrap=tk.WORD)
        ys = ttk.Scrollbar(log_f, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=ys.set)
        ys.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        btn_f = ttk.Frame(f)
        btn_f.pack(pady=6)
        ttk.Button(btn_f, text="Refresh Log",
                   command=self._refresh_log).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_f, text="Clear Log",
                   command=self._clear_log).pack(side=tk.LEFT, padx=5)

    # ------------------------------------------------------------------
    # Server actions
    # ------------------------------------------------------------------
    def _start_server(self):
        if self._running:
            messagebox.showinfo("Info", "Server is already running.", parent=self.root)
            return
        try:
            host = self.srv_ip.get().strip()
            port = int(self.srv_port.get().strip())
        except ValueError:
            messagebox.showerror("Error", "Invalid port number.", parent=self.root)
            return

        self.fc_server = FastConnectServer(host, port)
        self.fc_server.register_callback('broadcast_sent',    self._cb_broadcast)
        self.fc_server.register_callback('user_registered',   self._cb_user_joined)
        self.fc_server.register_callback('user_disconnected', self._cb_user_left)

        if self.fc_server.start():
            self._running = True
            self.status_var.set(f"● Server: Running  ({host}:{port})")
            self._status_lbl.configure(foreground="green")
            self._log(f"Server started on {host}:{port}")
            self._refresh_keys()
            self._refresh_stats()
        else:
            self.fc_server = None
            messagebox.showerror("Error", "Could not start server. Port may be in use.",
                                 parent=self.root)

    def _stop_server(self):
        if not self._running or not self.fc_server:
            messagebox.showinfo("Info", "Server is not running.", parent=self.root)
            return
        self.fc_server.stop()
        self._running = False
        self.status_var.set("● Server: Stopped")
        self._status_lbl.configure(foreground="red")
        self._log("Server stopped.")

    # ------------------------------------------------------------------
    # Encryption actions
    # ------------------------------------------------------------------
    def _refresh_keys(self):
        if not self.fc_server:
            return
        layers = self.fc_server.get_encryption_layers()
        self.keys_text.config(state=tk.NORMAL)
        self.keys_text.delete("1.0", tk.END)
        for i, key in enumerate(layers):
            if i < 15:
                label = f"Layer {i + 1:2d} (auto):  "
            else:
                label = f"Layer {i + 1:2d} [MASTER]: "
            self.keys_text.insert(tk.END, label + key + "\n")
        self.keys_text.config(state=tk.DISABLED)

        # Pre-fill master key field if already set
        if len(layers) == 16:
            self.master_key_var.set(layers[-1])

    def _apply_master_key(self):
        if not self.fc_server:
            messagebox.showwarning("Warning", "Start the server first.", parent=self.root)
            return
        key = self.master_key_var.get().strip()
        if not key:
            messagebox.showwarning("Warning", "Type a master key first.", parent=self.root)
            return
        self.fc_server.set_server_master_key(key)
        self._refresh_keys()
        self._log(f"Master key applied (first 8 chars): {key[:8]}…")
        messagebox.showinfo("Applied", "Master key set as Layer 16.", parent=self.root)

    def _regen_keys(self):
        if not self.fc_server:
            messagebox.showwarning("Warning", "Start the server first.", parent=self.root)
            return
        if messagebox.askyesno(
                "Regenerate?",
                "Regenerate all 15 random layers?\n"
                "All connected clients will need to reconnect to get the new keys.",
                parent=self.root):
            self.fc_server.regenerate_keys()
            self._refresh_keys()
            self._log("Encryption layers 1-15 regenerated.")

    # ------------------------------------------------------------------
    # Users & Control actions
    # ------------------------------------------------------------------
    def _refresh_users(self):
        if not self.fc_server:
            return
        for row in self.users_tree.get_children():
            self.users_tree.delete(row)
        for idx, (username, udata) in enumerate(self.fc_server.users.items(), 1):
            addr = udata.get('address', ('?', '?'))
            addr_str = f"{addr[0]}:{addr[1]}"
            real_name = udata.get('real_name', '')
            bc_status = "Muted" if username in self.fc_server.muted_from_broadcast else "Allowed"
            self.users_tree.insert("", tk.END, iid=username,
                                   values=(idx, username, real_name, addr_str, bc_status))

    def _selected_username(self):
        sel = self.users_tree.selection()
        if not sel:
            messagebox.showwarning("Select a user",
                                   "Please select a user from the list first.",
                                   parent=self.root)
            return None
        return sel[0]  # iid == username

    def _kick_selected(self):
        if not self.fc_server:
            return
        username = self._selected_username()
        if username and messagebox.askyesno(
                "Kick?", f"Kick  {username}  from the server?", parent=self.root):
            self.fc_server.kick_user(username)
            self._log(f"Kicked: {username}")
            self.root.after(600, self._refresh_users)

    def _mute_selected(self):
        if not self.fc_server:
            return
        username = self._selected_username()
        if username:
            self.fc_server.mute_user(username)
            self._log(f"Muted from broadcast: {username}")
            self._refresh_users()

    def _unmute_selected(self):
        if not self.fc_server:
            return
        username = self._selected_username()
        if username:
            self.fc_server.unmute_user(username)
            self._log(f"Unmuted from broadcast: {username}")
            self._refresh_users()

    # ------------------------------------------------------------------
    # Broadcast actions
    # ------------------------------------------------------------------
    def _send_server_broadcast(self):
        if not self._running or not self.fc_server:
            messagebox.showwarning("Warning", "Server is not running.", parent=self.root)
            return
        msg = self.bc_input.get("1.0", tk.END).strip()
        if not msg:
            messagebox.showwarning("Warning", "Enter a message.", parent=self.root)
            return
        self.fc_server.broadcast_as_server(msg)
        self._append_bc("[SERVER]", msg)
        self.bc_input.delete("1.0", tk.END)
        self._log(f"Server broadcast: {msg[:80]}")

    def _append_bc(self, sender, message):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.bc_text.config(state=tk.NORMAL)
        self.bc_text.insert(tk.END, f"[{ts}] {sender}: {message}\n")
        self.bc_text.see(tk.END)
        self.bc_text.config(state=tk.DISABLED)

    def _clear_bc_history(self):
        self.bc_text.config(state=tk.NORMAL)
        self.bc_text.delete("1.0", tk.END)
        self.bc_text.config(state=tk.DISABLED)

    # ------------------------------------------------------------------
    # Log helpers
    # ------------------------------------------------------------------
    def _log(self, msg):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{ts}] {msg}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _refresh_log(self):
        if not self.fc_server or not self.fc_server.server:
            return
        entries = list(self.fc_server.server.log[-80:])
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        for entry in entries:
            self.log_text.insert(tk.END, entry + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _clear_log(self):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state=tk.DISABLED)
        if self.fc_server and self.fc_server.server:
            self.fc_server.server.log.clear()

    # ------------------------------------------------------------------
    # Stats refresh
    # ------------------------------------------------------------------
    def _refresh_stats(self):
        if not self.fc_server:
            return
        n_users = len(self.fc_server.users)
        # Count unique friendship pairs
        n_friends = sum(len(v) for v in self.fc_server.friendships.values()) // 2
        n_muted   = len(self.fc_server.muted_from_broadcast)
        n_pending = sum(len(v) for v in self.fc_server.friend_requests.values())
        self.v_users.set(f"Connected users: {n_users}")
        self.v_friends.set(f"Active friendships: {n_friends}")
        self.v_muted.set(f"Muted from broadcast: {n_muted}")
        self.v_pending.set(f"Pending friend requests: {n_pending}")

    # ------------------------------------------------------------------
    # Server event callbacks (called from network thread)
    # ------------------------------------------------------------------
    def _cb_broadcast(self, data):
        sender = data.get('from_user', '?')
        self.root.after(0, lambda: self._append_bc(sender, "<encrypted message>"))
        self.root.after(0, self._refresh_stats)

    def _cb_user_joined(self, data):
        uname = data.get('username', '?')
        self.root.after(0, self._refresh_users)
        self.root.after(0, self._refresh_stats)
        self.root.after(0, lambda: self._log(f"User joined: {uname}"))

    def _cb_user_left(self, data):
        uname = data.get('username', '?')
        self.root.after(0, self._refresh_users)
        self.root.after(0, self._refresh_stats)
        self.root.after(0, lambda: self._log(f"User left: {uname}"))

    # ------------------------------------------------------------------
    # Misc helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _toggle_show(entry):
        entry.config(show='' if entry.cget('show') == '*' else '*')

    # ------------------------------------------------------------------
    # Auto refresh
    # ------------------------------------------------------------------
    def _schedule_refresh(self):
        self._do_refresh()

    def _do_refresh(self):
        if self._running:
            self._refresh_stats()
            self._refresh_users()
            self._refresh_log()
        self.root.after(5000, self._do_refresh)


# ------------------------------------------------------------------
def main():
    root = tk.Tk()
    ServerControlApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
