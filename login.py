import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import hashlib
import gdrive_storage

_USERS_DB_FILENAME = 'users_db.json'


def hash_password(password):
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def load_users_db():
    """Load the users database from Google Drive"""
    try:
        data = gdrive_storage.load_json(_USERS_DB_FILENAME, default=None)
        if data is not None:
            return data
    except Exception:
        pass
    return {'users': {}, 'next_user_number': 1}


def save_users_db(db):
    """Save the users database to Google Drive"""
    gdrive_storage.save_json(_USERS_DB_FILENAME, db)


class LoginWindow:
    """Login / Register window shown before the main app"""

    def __init__(self, root, on_login_success):
        self.root = root
        self.root.title("Fast Connect - Login")
        self.root.resizable(False, False)
        self.on_login_success = on_login_success

        # Center window on screen
        self.root.update_idletasks()
        w, h = 400, 380
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

        # Title label
        title_lbl = ttk.Label(root, text="Fast Connect", font=("Arial", 18, "bold"))
        title_lbl.pack(pady=(15, 5))

        # Notebook (tabs)
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

        self.login_frame = ttk.Frame(self.notebook, padding=15)
        self.register_frame = ttk.Frame(self.notebook, padding=15)

        self.notebook.add(self.login_frame, text="  Login  ")
        self.notebook.add(self.register_frame, text="  Register  ")

        self._build_login_tab()
        self._build_register_tab()

        # Allow pressing Enter to submit
        self.root.bind('<Return>', lambda e: self._do_login()
                       if self.notebook.index('current') == 0 else self._do_register())

    # ------------------------------------------------------------------
    # Login tab
    # ------------------------------------------------------------------
    def _build_login_tab(self):
        frame = self.login_frame
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Username:").grid(row=0, column=0, sticky=tk.W, pady=10)
        self.login_username = tk.StringVar()
        ttk.Entry(frame, textvariable=self.login_username, width=28).grid(
            row=0, column=1, columnspan=2, sticky=tk.EW, pady=10)

        ttk.Label(frame, text="Password:").grid(row=1, column=0, sticky=tk.W, pady=10)
        self.login_password = tk.StringVar()
        self._login_pwd_entry = ttk.Entry(
            frame, textvariable=self.login_password, show="*", width=24)
        self._login_pwd_entry.grid(row=1, column=1, sticky=tk.EW, pady=10)
        ttk.Button(frame, text="Show",
                   command=lambda: self._toggle_show(self._login_pwd_entry)).grid(
            row=1, column=2, padx=(4, 0))

        btn = ttk.Button(frame, text="Login", command=self._do_login)
        btn.grid(row=2, column=0, columnspan=3, pady=15)

    # ------------------------------------------------------------------
    # Register tab
    # ------------------------------------------------------------------
    def _build_register_tab(self):
        frame = self.register_frame
        frame.columnconfigure(1, weight=1)

        fields = [
            ("Username:",         "reg_username",  False),
            ("Real Name:",        "reg_real_name", False),
            ("Password:",         "reg_password",  True),
            ("Confirm Password:", "reg_confirm",   True),
        ]

        self._reg_pwd_entries = {}  # attr -> Entry widget (for secret fields)

        for row, (label, attr, secret) in enumerate(fields):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky=tk.W, pady=6)
            var = tk.StringVar()
            setattr(self, attr, var)
            kw = {"show": "*"} if secret else {}
            entry = ttk.Entry(frame, textvariable=var, width=24, **kw)
            entry.grid(row=row, column=1, sticky=tk.EW, pady=6)
            if secret:
                self._reg_pwd_entries[attr] = entry
                ttk.Button(
                    frame, text="Show",
                    command=lambda e=entry: self._toggle_show(e)
                ).grid(row=row, column=2, padx=(4, 0))

        ttk.Button(frame, text="Register", command=self._do_register).grid(
            row=len(fields), column=0, columnspan=3, pady=12)

    # ------------------------------------------------------------------
    # Toggle password visibility
    # ------------------------------------------------------------------
    @staticmethod
    def _toggle_show(entry):
        """Toggle between showing and hiding password text"""
        if entry.cget('show') == '*':
            entry.config(show='')
        else:
            entry.config(show='*')

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _do_login(self):
        username = self.login_username.get().strip()
        password = self.login_password.get()

        if not username or not password:
            messagebox.showerror("Error", "Please fill in all fields.", parent=self.root)
            return

        db = load_users_db()

        if username not in db['users']:
            messagebox.showerror("Error", "Username not found. Please register first.", parent=self.root)
            return

        user = db['users'][username]
        if user['password_hash'] != hash_password(password):
            messagebox.showerror("Error", "Incorrect password.", parent=self.root)
            return

        # Success — hand off to main app
        self.on_login_success(username, user['real_name'], user['user_number'])

    def _do_register(self):
        username = self.reg_username.get().strip()
        real_name = self.reg_real_name.get().strip()
        password = self.reg_password.get()
        confirm = self.reg_confirm.get()

        if not username or not real_name or not password or not confirm:
            messagebox.showerror("Error", "Please fill in all fields.", parent=self.root)
            return

        if len(username) < 3:
            messagebox.showerror("Error", "Username must be at least 3 characters.", parent=self.root)
            return

        if len(password) < 6:
            messagebox.showerror("Error", "Password must be at least 6 characters.", parent=self.root)
            return

        if password != confirm:
            messagebox.showerror("Error", "Passwords do not match.", parent=self.root)
            return

        db = load_users_db()

        if username in db['users']:
            messagebox.showerror("Error", "Username already taken. Choose another.", parent=self.root)
            return

        user_number = db['next_user_number']
        db['users'][username] = {
            'password_hash': hash_password(password),
            'real_name': real_name,
            'user_number': user_number,
        }
        db['next_user_number'] += 1
        save_users_db(db)

        messagebox.showinfo(
            "Registered!",
            f"Account created!\nYour user number is #{user_number}.\nYou can now log in.",
            parent=self.root
        )
        # Switch to login tab and pre-fill username
        self.notebook.select(0)
        self.login_username.set(username)
        self.login_password.set("")
