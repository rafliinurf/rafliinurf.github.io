"""Login and registration dialog for offline game accounts."""
import tkinter as tk
from tkinter import messagebox

from game.accounts import AccountError


class AccountDialog(tk.Toplevel):
    def __init__(self, root, account_store):
        super().__init__(root)
        self.root = root
        self.account_store = account_store
        self.username = None
        self.mode = "login"
        self.title("Farmer Replica — Akun")
        self.geometry("380x340")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.cancel)

        self.frame = tk.Frame(self, padx=28, pady=24, bg="#30393c")
        self.frame.pack(fill="both", expand=True)
        self.username_var = tk.StringVar()
        self.password_var = tk.StringVar()
        self.confirm_var = tk.StringVar()
        self._render()
        self.grab_set()
        self.username_entry.focus_set()

    def show(self):
        self.deiconify()
        self.lift()
        self.root.wait_window(self)
        return self.username

    def _render(self):
        for child in self.frame.winfo_children():
            child.destroy()

        registering = self.mode == "register"
        self.geometry("380x430" if registering else "380x340")
        heading = "BUAT AKUN" if registering else "MASUK"
        tk.Label(
            self.frame,
            text="FARMER REPLICA",
            bg="#30393c",
            fg="#94ad4d",
            font=("Bahnschrift SemiBold", 11),
        ).pack(anchor="w")
        tk.Label(
            self.frame,
            text=heading,
            bg="#30393c",
            fg="#d8dfdc",
            font=("Bahnschrift SemiBold", 20),
        ).pack(anchor="w", pady=(5, 18))

        self._field("Username", self.username_var)
        self._field("Kata sandi", self.password_var, show="*")
        if registering:
            self._field("Ulangi kata sandi", self.confirm_var, show="*")

        tk.Button(
            self.frame,
            text="DAFTAR" if registering else "MASUK",
            command=self._submit,
            bg="#627d39",
            fg="white",
            activebackground="#94ad4d",
            relief="flat",
            padx=14,
            pady=8,
        ).pack(fill="x", pady=(18, 6))
        tk.Button(
            self.frame,
            text="Sudah punya akun? Masuk" if registering else "Belum punya akun? Daftar",
            command=self._toggle_mode,
            bg="#30393c",
            fg="#d8dfdc",
            activebackground="#46545b",
            relief="flat",
        ).pack(anchor="center")
        tk.Label(
            self.frame,
            text="Akun dan progres tersimpan lokal di komputer ini.",
            bg="#30393c",
            fg="#93a09f",
            font=("Consolas", 8),
        ).pack(anchor="center", pady=(10, 0))

    def _field(self, label, variable, show=None):
        tk.Label(
            self.frame,
            text=label,
            bg="#30393c",
            fg="#d8dfdc",
            font=("Consolas", 9),
        ).pack(anchor="w", pady=(0, 4))
        entry = tk.Entry(
            self.frame,
            textvariable=variable,
            show=show or "",
            bg="#252d30",
            fg="#d8dfdc",
            insertbackground="white",
            relief="flat",
        )
        entry.pack(fill="x", ipady=6, pady=(0, 10))
        if label == "Username":
            self.username_entry = entry

    def _toggle_mode(self):
        self.mode = "register" if self.mode == "login" else "login"
        self.confirm_var.set("")
        self._render()
        self.username_entry.focus_set()

    def _submit(self):
        username = self.username_var.get()
        password = self.password_var.get()
        try:
            if self.mode == "register":
                if password != self.confirm_var.get():
                    raise AccountError("Konfirmasi kata sandi tidak cocok.")
                self.username = self.account_store.register(username, password)
            else:
                self.username = self.account_store.authenticate(username, password)
        except (AccountError, OSError) as exc:
            messagebox.showerror("Akun", str(exc), parent=self)
            return
        self.destroy()

    def cancel(self):
        self.username = None
        self.destroy()
