import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
import threading
import serial
import time
import csv
import datetime
from collections import deque

# CONFIGURACIÓN

PUERTO = "COM3"
BAUDIOS = 9600
CSV_FILENAME = "registros_dht11.csv"
READ_TIMEOUT = 1.0

# HILOS / VARIABLES COMPARTIDAS

data_lock = threading.Lock()
serial_conn = None
running_serial = False
logging_enabled = False

def crear_csv_si_no_existe():
    try:
        with open(CSV_FILENAME, "x", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["fecha_hora", "temperatura_C", "humedad_%"])
    except FileExistsError:
        pass

# HILO DE LECTURA SERIAL

def serial_reader_thread(on_new_sample_callback=None):
    global serial_conn, running_serial, logging_enabled
    try:
        serial_conn = serial.Serial(PUERTO, BAUDIOS, timeout=READ_TIMEOUT)
    except Exception as e:
        messagebox.showerror("Error Serial", f"No se pudo abrir {PUERTO}: {e}")
        running_serial = False
        return

    running_serial = True
    crear_csv_si_no_existe()

    while running_serial:
        try:
            raw = serial_conn.readline().decode(errors="ignore").strip()
            if not raw:
                continue

            parts = raw.split(",")
            if len(parts) < 2:
                continue

            try:
                t = float(parts[0])
                h = float(parts[1])
            except ValueError:
                continue

            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if logging_enabled:
                with open(CSV_FILENAME, "a", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow([ts, f"{t:.2f}", f"{h:.2f}"])

            if on_new_sample_callback:
                try:
                    on_new_sample_callback(t, h)
                except:
                    pass

        except Exception:
            time.sleep(0.1)

    try:
        serial_conn.close()
    except:
        pass
    serial_conn = None

def start_serial(on_new_sample_callback):
    global running_serial, serial_thread
    if running_serial:
        return
    serial_thread = threading.Thread(target=serial_reader_thread, args=(on_new_sample_callback,), daemon=True)
    serial_thread.start()


def stop_serial():
    global running_serial
    running_serial = False


def send_limits_to_arduino(tmin, tmax):
    global serial_conn
    if serial_conn and serial_conn.is_open:
        cmd = f"{tmin},{tmax}\n"
        try:
            serial_conn.write(cmd.encode())
            time.sleep(0.05)
            return True
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo enviar al Arduino: {e}")
            return False
    else:
        try:
            with serial.Serial(PUERTO, BAUDIOS, timeout=1) as ser:
                ser.write(f"{tmin},{tmax}\n".encode())
                time.sleep(0.05)
            return True
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir puerto {PUERTO}: {e}")
            return False


# GUI

class App:
    def __init__(self, root):
        self.root = root
        root.title("RBP Sensor")
        root.geometry("420x350")
        root.resizable(False, False)

        frm = ttk.Frame(root, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text="RBP Sensor", font=("Segoe UI", 14, "bold")).pack(pady=(0,10))

        frame_vals = ttk.LabelFrame(frm, text="Lectura actual", padding=8)
        frame_vals.pack(fill=tk.X, pady=6)

        self.lbl_temp = ttk.Label(frame_vals, text="Temp: -- °C", font=("Segoe UI", 12))
        self.lbl_temp.grid(row=0, column=0, padx=8, pady=4)

        self.lbl_hum = ttk.Label(frame_vals, text="Hum: -- %", font=("Segoe UI", 12))
        self.lbl_hum.grid(row=0, column=1, padx=8, pady=4)

        self.lbl_status = ttk.Label(frame_vals, text="Estado: --", font=("Segoe UI", 12, "bold"))
        self.lbl_status.grid(row=1, column=0, columnspan=2, pady=4)

        # límites
        frame_limits = ttk.LabelFrame(frm, text="Límites (enviar al Arduino)", padding=8)
        frame_limits.pack(fill=tk.X, pady=6)

        ttk.Label(frame_limits, text="Temp min (°C):").grid(row=0, column=0)
        self.entry_tmin = ttk.Entry(frame_limits, width=10)
        self.entry_tmin.grid(row=0, column=1, padx=6)
        self.entry_tmin.insert(0, "20")

        ttk.Label(frame_limits, text="Temp max (°C):").grid(row=0, column=2)
        self.entry_tmax = ttk.Entry(frame_limits, width=10)
        self.entry_tmax.grid(row=0, column=3, padx=6)
        self.entry_tmax.insert(0, "28")

        ttk.Button(frame_limits, text="Enviar límites", command=self.on_send_limits).grid(row=1, column=0, columnspan=4, pady=6)

        # controles
        frame_ctrl = ttk.LabelFrame(frm, text="Controles", padding=8)
        frame_ctrl.pack(fill=tk.X, pady=6)

        self.btn_start_log = ttk.Button(frame_ctrl, text="Iniciar Registro CSV", command=self.on_start_log)
        self.btn_start_log.grid(row=0, column=0, padx=6, pady=6)

        self.btn_stop_log = ttk.Button(frame_ctrl, text="Detener Registro CSV", command=self.on_stop_log, state=tk.DISABLED)
        self.btn_stop_log.grid(row=0, column=1, padx=6, pady=6)

        ttk.Button(frame_ctrl, text="Salir", command=self.on_exit).grid(row=1, column=0, columnspan=2, pady=8)

        ttk.Label(frm, text=f"Puerto: {PUERTO}  |  Baud: {BAUDIOS}").pack(pady=(8,0))

        start_serial(self.on_new_sample)

        self.local_tmin = float(self.entry_tmin.get())
        self.local_tmax = float(self.entry_tmax.get())

    def on_new_sample(self, t, h):
        def upd():
            self.lbl_temp.config(text=f"Temp: {t:.2f} °C")
            self.lbl_hum.config(text=f"Hum: {h:.2f} %")

            try:
                tmin = float(self.entry_tmin.get())
                tmax = float(self.entry_tmax.get())
            except:
                tmin = self.local_tmin
                tmax = self.local_tmax

            if tmin <= t <= tmax:
                self.lbl_status.config(text="Estado: ÓPTIMO", foreground="blue")
            else:
                self.lbl_status.config(text="Estado: FUERA DE RANGO", foreground="red")

        self.root.after(0, upd)

    def on_send_limits(self):
        try:
            tmin = float(self.entry_tmin.get())
            tmax = float(self.entry_tmax.get())
        except:
            messagebox.showerror("Error", "Introduce valores válidos.")
            return

        if send_limits_to_arduino(tmin, tmax):
            messagebox.showinfo("OK", f"Límites enviados: {tmin}-{tmax} °C")
            self.local_tmin = tmin
            self.local_tmax = tmax

    def on_start_log(self):
        global logging_enabled
        crear_csv_si_no_existe()
        logging_enabled = True
        self.btn_start_log.config(state=tk.DISABLED)
        self.btn_stop_log.config(state=tk.NORMAL)
        messagebox.showinfo("Registro", f"Registrando en {CSV_FILENAME}")

    def on_stop_log(self):
        global logging_enabled
        logging_enabled = False
        self.btn_start_log.config(state=tk.NORMAL)
        self.btn_stop_log.config(state=tk.DISABLED)
        messagebox.showinfo("Registro", "Registro detenido.")

    def on_exit(self):
        if messagebox.askokcancel("Salir", "¿Deseas salir?"):
            stop_serial()
            time.sleep(0.3)
            self.root.destroy()


def main():
    crear_csv_si_no_existe()
    root = tk.Tk()
    app = App(root)
    root.mainloop()

if __name__ == "__main__":
    main()
