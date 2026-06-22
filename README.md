# Fast Connect — Secure Friend Network & Chat Client

Fast Connect is a Python-based, multi-layered encrypted chat application that features a localized secure friend network. It includes an account authentication layer, friend discovery, secure end-to-end private messaging, global broadcast systems, and a dedicated administrative server control panel.

## Features

- **Multi-Layered Encryption:** Implements 15 auto-generated layers of Vigenère cipher paired with an optional 16th administrative Master Key layer, alongside robust support for AES-256 password-based key derivation encryption.
- **Dedicated Administrative Panel (`server_control.py`):** Fully-featured graphical dashboard for server administrators to spin up server instances, monitor live network stats, kick users, mute/unmute broadcast permissions, and manage real-time cryptographic layers.
- **Client Application GUI (`gui.py`):** An intuitive, tabbed interface structured into Setup, Users & Friends, Friends Chat, and Global Broadcast modes.
- **Secure Authentication System (`login.py`):** User registration and login protected by SHA-256 password hashing and distinct user sequence identifiers.
- **Robust Networking Protocol:** Length-prefixed 4-byte big-endian header framing layout preventing socket stream bleeding and ensuring data integrity over TCP.

---

## File Architecture

- **`main.py`**: The cryptographic engine containing core implementation logics for Caesar, Vigenère, and AES block-cipher encryption/decryption routines, alongside folder and file package compressors.
- **`server.py`**: Low-level TCP socket listener that manages client pools, dispatches network frames, handles active disconnects, and manages broadcasts.
- **`client.py`**: Client-side framing network socket handler responsible for establishing persistent server link pipelines and background thread listening hooks.
- **`fast_connect.py`**: Middleware application wrapper bridging networking components with system logic, maintaining data persistence (`fc_data.json`), and implementing multi-layer key wrapping algorithms.
- **`login.py`**: Authentication view controller utilizing local file persistence (`users_db.json`) for user records.
- **`gui.py`**: Main user application client interface showcasing connected network peers, friend workflows, and isolated private chat sub-windows.
- **`server_control.py`**: Secure administrative terminal for server operational workflows.

---

## Prerequisites & Installation

### 1. Requirements
Ensure you have Python 3.7+ installed. The graphic engine uses Python's built-in `tkinter` framework.

### 2. Dependencies
Install the required encryption engine library wrapper via `pip`: pip install -r requirements.txt
