
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading, time, random, json, sqlite3, hashlib, math
from datetime import datetime
from collections import deque
import os
import socket

# LAST DAY PRESENTATION 
    
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


try:
    import customtkinter as ctk
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    HAS_CUSTOMTKINTER = True
except Exception:
    HAS_CUSTOMTKINTER = False


try:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    import numpy as np
    HAS_SKLEARN = True
except Exception:
    HAS_SKLEARN = False

try:
    import networkx as nx  
    HAS_NETWORKX = True
except Exception:
    HAS_NETWORKX = False


try:
    import serial
    import serial.tools.list_ports
    HAS_PYSERIAL = True
except Exception:
    HAS_PYSERIAL = False

DB_FILE = "energy_ledger.db"


class PowerGridTopology:
    def __init__(self):
        self.central_station = {"id": "CENTRAL_01", "address": "192.168.0.2", "type": "Central Monitoring"}
        self.substation = {"id": "SUB_001", "address": "192.168.0.10", "location": "Sector A"}
        self.meters = {}
        self.generate_realistic_topology()

    def generate_realistic_topology(self):
        
        base_ip = "192.168.1."
        meter_id = 1
        count = random.randint(8, 12)
        for j in range(count):
            addr = f"{base_ip}{20 + j}"
            self.meters[f"M{meter_id:03d}"] = {
                "id": f"M{meter_id:03d}",
                "address": addr,
                "substation": self.substation["id"],
                "location": f"{self.substation['location']}-Unit-{j+1}",
                "private_key": f"{random.randint(0x10000000, 0xFFFFFFFF):08X}"
            }
            meter_id += 1


class SmartEnergyTheftDetector:
    def __init__(self):
        
        if HAS_CUSTOMTKINTER:
            self.root = ctk.CTk()
            self.root.configure(fg_color="#0a0a0a")
        else:
            self.root = tk.Tk()
            self.root.configure(bg="#0a0a0a")
        self.root.title("🔋 CRYPTETHERA - SFT 2025")
        self.root.geometry("1400x900")

        
        self.grid_topology = PowerGridTopology()

        
        self.current_mode = "NONE"  
        self.simulation_running = False
        self.live_running = False
        self.serial_conn = None
      
        self.serial_sub = None   
        self.serial_meter = None 

        # Wi-Fi (ESP32 AP TCP) live path
        self.net_sock = None          # TCP socket to ESP32 (192.168.4.1:8080)
        self.live_running_net = False # Wi-Fi live loop flag


        
        self.meters = {}


        self.residuals = deque(maxlen=1000)
        self.live_currents = deque(maxlen=600)  

        # Detection metrics
        self.detection_accuracy = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
        self.live_theft_detected = False

        
        self.model_trained = False
        self.scaler = None
        self.iforest = None
        if HAS_SKLEARN:
            self.scaler = StandardScaler()
            self.iforest = IsolationForest(
                contamination=0.03,  
                random_state=42,
                n_estimators=150,
                bootstrap=True
            )

        
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.init_ledger()

        
        self.canvas_grid_win = None
        self.live_grid_canvas = None
        self.fig_residuals = None
        self.ax_residuals = None
        self.canvas_residuals = None
        self.fig_current = None
        self.ax_current = None
        self.canvas_current = None

    
        self.create_startup_ui()

        # Threads
        self.sim_thread = None
        self.live_thread = None


    def init_ledger(self):
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS simulation_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                meter_id TEXT NOT NULL,
                meter_address TEXT NOT NULL,
                private_key TEXT NOT NULL,
                power_reading REAL NOT NULL,
                substation_reading REAL NOT NULL,
                residual REAL NOT NULL,
                hash TEXT NOT NULL,
                prev_hash TEXT,
                is_theft_detected INTEGER DEFAULT 0,
                confidence_score REAL DEFAULT 0.0,
                detection_time_ms INTEGER DEFAULT 0
            )
            """
        )
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS live_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                meter_id TEXT NOT NULL,
                meter_address TEXT NOT NULL,
                private_key TEXT NOT NULL,
                current_reading REAL NOT NULL,
                power_reading REAL NOT NULL,
                substation_current REAL NOT NULL,
                substation_power REAL NOT NULL,
                residual REAL NOT NULL,
                hash TEXT NOT NULL,
                prev_hash TEXT,
                is_theft_detected INTEGER DEFAULT 0,
                confidence_score REAL DEFAULT 0.0,
                detection_time_ms INTEGER DEFAULT 0
            )
            """
        )
        self.conn.commit()

    def get_last_hash(self, table):
        try:
            self.cursor.execute(f"SELECT hash FROM {table} ORDER BY id DESC LIMIT 1")
            row = self.cursor.fetchone()
            return row[0] if row else "GENESIS"
        except Exception:
            return "GENESIS"

    def insert_simulation_record(self, meter_id, meter_addr, pk, p_meter, p_sub, residual, is_theft, confidence, detection_ms=0):
        prev = self.get_last_hash("simulation_transactions")
        raw = f"{meter_id}{p_meter}{p_sub}{residual}{datetime.now().isoformat()}{prev}"
        h = hashlib.sha256(raw.encode()).hexdigest()
        try:
            self.cursor.execute(
                """
                INSERT INTO simulation_transactions
                (timestamp,meter_id,meter_address,private_key,power_reading,substation_reading,residual,hash,prev_hash,is_theft_detected,confidence_score,detection_time_ms)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    meter_id,
                    meter_addr,
                    pk,
                    float(p_meter),
                    float(p_sub),
                    float(residual),
                    h,
                    prev,
                    int(bool(is_theft)),
                    float(confidence),
                    int(detection_ms),
                ),
            )
            self.conn.commit()
        except Exception as e:
            print("Insert sim record error:", e)

    def insert_live_record(self, meter_id, meter_addr, pk, cur, p_meter, sub_cur, sub_pwr, residual, is_theft, confidence, detection_ms=0):
        prev = self.get_last_hash("live_transactions")
        raw = f"{meter_id}{p_meter}{sub_pwr}{residual}{datetime.now().isoformat()}{prev}"
        h = hashlib.sha256(raw.encode()).hexdigest()
        try:
            self.cursor.execute(
                """
                INSERT INTO live_transactions
                (timestamp,meter_id,meter_address,private_key,current_reading,power_reading,substation_current,substation_power,residual,hash,prev_hash,is_theft_detected,confidence_score,detection_time_ms)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    meter_id,
                    meter_addr,
                    pk,
                    float(cur),
                    float(p_meter),
                    float(sub_cur),
                    float(sub_pwr),
                    float(residual),
                    h,
                    prev,
                    int(bool(is_theft)),
                    float(confidence),
                    int(detection_ms),
                ),
            )
            self.conn.commit()
        except Exception as e:
            print("Insert live record error:", e)


    def create_startup_ui(self):
        for w in self.root.winfo_children():
            w.destroy()

        if HAS_CUSTOMTKINTER:
            main = ctk.CTkFrame(self.root, fg_color="transparent")
        else:
            main = tk.Frame(self.root, bg="#0a0a0a")
        main.pack(fill="both", expand=True, padx=20, pady=20)

        # Header
        title_frame = (ctk.CTkFrame(main, height=120, fg_color="#1a1a2e") if HAS_CUSTOMTKINTER
                       else tk.Frame(main, height=120, bg="#1a1a2e"))
        title_frame.pack(fill="x", pady=(0, 30))
        title_frame.pack_propagate(False)

        title_label = (ctk.CTkLabel(title_frame, text="⚡ CRYPTETHERA ⚡",
                                     font=ctk.CTkFont(size=32, weight="bold"), text_color="#00ff88")
                       if HAS_CUSTOMTKINTER else
                       tk.Label(title_frame, text="⚡ SMART ENERGY THEFT DETECTION ⚡",
                                font=("Arial", 24, "bold"), fg="#00ff88", bg="#1a1a2e"))
        title_label.pack(pady=20)

        subtitle_label = (ctk.CTkLabel(title_frame, text="Advanced ML-Powered Energy Monitoring • Samsung Solve for Tomorrow 2025",
                                       font=ctk.CTkFont(size=14), text_color="#888888")
                          if HAS_CUSTOMTKINTER else
                          tk.Label(title_frame, text="Advanced ML-Powered Energy Monitoring • Samsung Solve for Tomorrow 2025",
                                   font=("Arial", 12), fg="#888888", bg="#1a1a2e"))
        subtitle_label.pack()

        btns = tk.Frame(main, bg="#0a0a0a")
        btns.pack(expand=True, pady=50)

        b_sim = tk.Button(btns, text="🎯 SIMULATION MODE\nAdvanced ML Training",
                           font=("Arial", 14, "bold"), fg="white", bg="#ff6b6b", width=24, height=3,
                           command=self.start_simulation_mode)
        b_sim.grid(row=0, column=0, padx=12)

        b_live = tk.Button(btns, text="📡 LIVE MODE\nSerial",
                           font=("Arial", 14, "bold"), fg="white", bg="#4ecdc4", width=24, height=3,
                           command=self.start_live_mode)
        b_live.grid(row=0, column=1, padx=12)

        b_ledger = tk.Button(btns, text="🔐 LEDGER VIEWER\nTamper-proof Log",
                             font=("Arial", 14, "bold"), fg="white", bg="#a8e6cf", width=24, height=3,
                             command=self.view_ledger)
        b_ledger.grid(row=0, column=2, padx=12)

        b_grid = tk.Button(btns, text="⚡ GRID VIEW\nNetwork Visualization",
                           font=("Arial", 14, "bold"), fg="white", bg="#8ecae6", width=24, height=3,
                           command=self.launch_electrical_grid)
        b_grid.grid(row=0, column=3, padx=12)

        b_live_wifi = tk.Button(btns, text="📶 LIVE MODE (Wi-Fi)\nESP32 Hotspot",
                                font=("Arial", 14, "bold"), fg="white", bg="#3b82f6", width=24, height=3,
                                command=self.start_live_mode_wifi)
        b_live_wifi.grid(row=0, column=4, padx=12)

        status = tk.Frame(main, bg="#0f3460", height=40)
        status.pack(fill="x", pady=(20, 0))
        status.pack_propagate(False)
        self.status_label = tk.Label(status,
                                     text="⚡ System Ready • ML Models Initialized • Awaiting Mode Selection",
                                     font=("Arial", 10), fg="#00ff88", bg="#0f3460")
        self.status_label.pack(pady=8)

    
    def start_simulation_mode(self):
        self.current_mode = "SIMULATION"
        self.create_simulation_interface()
        self.initialize_realistic_simulation()
        
        self.simulation_running = False
        self.update_sim_controls()

    def toggle_live(self):
       if self.live_running:
        self.live_running = False
       else:
        if not self.serial_conn:
            self.try_connect_serial()
        if self.serial_conn:
            self.live_running = True
            if not self.live_thread or not self.live_thread.is_alive():
                self.live_thread = threading.Thread(target=self.live_loop, daemon=True)
                self.live_thread.start()
        else:
            messagebox.showwarning("Serial Connection", "Cannot start live mode - Arduino not connected")
            self.update_live_controls()

    def start_live_mode(self):
       self.current_mode = "LIVE"
       self.create_live_interface()
    
       self.meters = {}
       self.residuals.clear()
       self.live_currents.clear()
    
       self.try_connect_serial()
       self.live_running = False
       self.update_live_controls()

    def try_connect_serial(self):
    
     if not HAS_PYSERIAL:
        messagebox.showwarning("Serial", "BHAI pyserial not installed. Live mode will remain OFF until installed.")
        return

     try:
        ports = list(serial.tools.list_ports.comports())
     except Exception:
        ports = []

    # close any previous handles
     for conn in (getattr(self, 'serial_sub', None), getattr(self, 'serial_meter', None), getattr(self, 'serial_conn', None)):
        try:
            if conn: conn.close()
        except: 
            pass

     self.serial_sub = None
     self.serial_meter = None
     self.serial_conn = None  

    
     for p in ports:
        desc = (p.description or "").lower()
        name = (p.device or "")
        try:
            if any(k in desc for k in ("arduino", "usb", "ch340", "cp210", "ftdi")) or "usb" in name.lower():
                try:
                    conn = serial.Serial(p.device, 115200, timeout=1)
                    time.sleep(1.5)
                except Exception:
                    continue

                if self.serial_sub is None:
                    self.serial_sub = conn
                elif self.serial_meter is None:
                    self.serial_meter = conn
                else:
                    try: conn.close()
                    except: pass
        except Exception:
            continue

     self.serial_conn = self.serial_sub or self.serial_meter

     if self.serial_sub and self.serial_meter:
        self.status_label.configure(text=f"📡 Connected: Sub={self.serial_sub.port} Meter={self.serial_meter.port}")
     elif self.serial_sub:
        self.status_label.configure(text=f"📡 Connected: Sub={self.serial_sub.port} (meter missing)")
     elif self.serial_meter:
        self.status_label.configure(text=f"📡 Connected: Meter={self.serial_meter.port} (substation missing)")
     else:
        self.status_label.configure(text="📡 No Arduino found • GRID OFF in LIVE mode")


    def start_live_mode_wifi(self):
        """Prepare Live mode over Wi-Fi TCP (ESP32 AP 192.168.4.1:8080)."""
        self.current_mode = "LIVE_WIFI"
        self.create_live_interface()
        self.meters = {}
        self.residuals.clear()
        self.live_currents.clear()
        self.try_connect_wifi()
        self.live_running_net = False
        self.update_live_controls_wifi()

    def update_live_controls_wifi(self):
        if self.current_mode != "LIVE_WIFI":
            return
        if not hasattr(self, 'start_live_btn'):
            return
        if self.live_running_net and self.net_sock:
            self.start_live_btn.configure(text="⏸ PAUSE LIVE (Wi-Fi)", bg="#ffaa00")
            self.live_status_label.configure(text="🟢 GRID ONLINE (Wi-Fi) • 192.168.4.1:8080", fg="#00ff88")
        else:
            self.start_live_btn.configure(text="▶ START LIVE (Wi-Fi)", bg="#3b82f6")
            self.live_status_label.configure(text="🔴 GRID OFFLINE (Wi-Fi) — connect to ESP32 AP", fg="#ff6b6b")

    def toggle_live_wifi(self):
        if self.current_mode != "LIVE_WIFI":
            return
        if self.live_running_net:
            self.live_running_net = False
            self.update_live_controls_wifi()
            return
        if not self.net_sock:
            self.try_connect_wifi()
        if self.net_sock:
            self.live_running_net = True
            if not self.live_thread or not self.live_thread.is_alive():
                self.live_thread = threading.Thread(target=self.live_loop_wifi, daemon=True)
                self.live_thread.start()
        self.update_live_controls_wifi()

    def try_connect_wifi(self, host="192.168.4.1", port=8080):
        """Open TCP socket to ESP32 gateway (AP)."""
        
        try:
            if self.net_sock:
                try: self.net_sock.shutdown(socket.SHUT_RDWR)
                except: pass
                try: self.net_sock.close()
                except: pass
        except: pass
        self.net_sock = None

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3.0)
            s.connect((host, port))
            s.settimeout(None)
            self.net_sock = s
            if hasattr(self, 'live_status_label'):
                self.live_status_label.configure(text=f"🟢 Connected to {host}:{port} (Wi-Fi)", fg="#00ff88")
        except Exception as e:
            if hasattr(self, 'live_status_label'):
                self.live_status_label.configure(text=f"🔴 Wi-Fi connect failed: {e}", fg="#ff6b6b")
            self.net_sock = None

    def live_loop_wifi(self):
        """Read CSV lines from ESP32 TCP socket and feed UI/ledger."""
        sock = self.net_sock
        if not sock:
            return
        f = sock.makefile('r', encoding='utf-8', errors='ignore')
        try:
            while self.current_mode == "LIVE_WIFI" and self.live_running_net:
                line = f.readline()
                if not line:
                    # connection dropped → try reconnect
                    try:
                        f.close()
                    except: pass
                    try:
                        sock.close()
                    except: pass
                    self.net_sock = None
                    self.try_connect_wifi()
                    sock = self.net_sock
                    if not sock:
                        time.sleep(1.0)
                        continue
                    f = sock.makefile('r', encoding='utf-8', errors='ignore')
                    continue

                line = line.strip()
                # Expect: SUBSTATION,ts_ms,sub_irms,residual,meter_irms
                self.process_gateway_csv(line)
                try:
                    self.root.after(0, self.update_live_ui)
                except Exception:
                    pass
        except Exception:
            pass
        finally:
            try:
                f.close()
            except: pass
            try:
                sock.close()
            except: pass
            self.net_sock = None
            self.live_running_net = False
            self.root.after(0, self.update_live_controls_wifi)

    def process_gateway_csv(self, line):
        """Parse ESP32 CSV and update charts + ledger."""
        parts = [p.strip() for p in line.split(',')]
        if len(parts) != 5 or parts[0] != "SUBSTATION":
            return
        try:
            ts_ms = int(parts[1])
            sub_irms = float(parts[2])
            residual_irms = float(parts[3])
            meter_irms = float(parts[4])
        except Exception:
            return

        # VERSION 1 PLOT
        self.residuals.append(residual_irms * 230.0)  
        self.live_currents.append(residual_irms)      

        # BAAD MEIN 28/09/2025 TRY POLYNOMIAL INTERPOLATION FOR LATER
        V = 230.0
        p_meter = meter_irms * V
        p_sub   = sub_irms   * V
        resid_w = residual_irms * V

        
        is_theft = (residual_irms > 0.2)
        confidence = min(0.99, max(0.05, residual_irms / 2.0))

        
        meter_id = "MGA1"
        meter_addr = "192.168.4.1"
        pk = "DEMO_KEY"

        try:
            self.insert_live_record(
                meter_id=meter_id,
                meter_addr=meter_addr,
                pk=pk,
                cur=meter_irms,
                p_meter=p_meter,
                sub_cur=sub_irms,
                sub_pwr=p_sub,
                residual=resid_w,
                is_theft=is_theft,
                confidence=confidence,
                detection_ms=0
            )
        except Exception:
            pass

    def initialize_realistic_simulation(self):
        self.meters = {}
        for mid, info in self.grid_topology.meters.items():
            base = random.uniform(90, 420)  # household baseline
            self.meters[mid] = {
                "id": mid,
                "address": info["address"],
                "private_key": info["private_key"],
                "substation": info["substation"],
                "base_consumption": base,
                "current_power": base,
                "current_reading": base / 230.0,
                "is_theft": False,
                "theft_power": 0.0,
                "theft_start": 0,
            }

        
        if HAS_SKLEARN:
            normal = []
            theft = []
            for _ in range(2000):
                hour = random.randint(0, 23)
                base = random.uniform(60, 500)
                daily = 0.7 + 0.5 * math.sin(2 * math.pi * (hour - 6) / 24)
                noise = random.gauss(0, 18)
                pm = max(10.0, base * daily + noise)  # meter-reported (no theft)
                resid = random.uniform(0, 20)  # small technical loss
                normal.append([pm + resid, hour, resid])
            for _ in range(240):  # rarer thefts
                hour = random.randint(0, 23)
                base = random.uniform(60, 500)
                daily = 0.7 + 0.5 * math.sin(2 * math.pi * (hour - 6) / 24)
                noise = random.gauss(0, 18)
                pm = max(10.0, base * daily + noise)
                theft_p = random.uniform(70, 260)
                resid = theft_p + random.uniform(0, 15)
                theft.append([pm + resid, hour, resid])
            X = np.array(normal + theft)
            try:
                self.scaler.fit(X)
                Xs = self.scaler.transform(X)
                self.iforest.fit(Xs)
                self.model_trained = True
            except Exception as e:
                print("Model train error:", e)
                self.model_trained = False
        else:
            self.model_trained = False

        # Reset metrics/buffers
        self.detection_accuracy = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
        self.residuals.clear()

    def toggle_simulation(self):
        if self.simulation_running:
            self.simulation_running = False
        else:
            self.simulation_running = True
            if not self.sim_thread or not self.sim_thread.is_alive():
                self.sim_thread = threading.Thread(target=self.simulation_loop, daemon=True)
                self.sim_thread.start()
        self.update_sim_controls()

    def update_sim_controls(self):
        if self.current_mode != "SIMULATION":
            return
        if self.simulation_running:
            self.start_sim_btn.configure(text="⏸ PAUSE SIMULATION", bg="#ffaa00")
            self.sim_status_label.configure(text="🟢 GRID ONLINE (SIM)", fg="#00ff88")
        else:
            self.start_sim_btn.configure(text="▶ START GRID SIMULATION", bg="#00ff88")
            self.sim_status_label.configure(text="🔴 GRID OFFLINE (SIM)", fg="#ff6b6b")

    def simulation_loop(self):
        while self.simulation_running:
            try:
                self.update_simulation_step()
                self.root.after(0, self.update_live_ui)
            except Exception as e:
                print("Simulation loop error:", e)
            time.sleep(1.0)

    def update_simulation_step(self):
        hour = datetime.now().hour
        sub_total = 0.0
        meter_sum_reported = 0.0
        theft_any = False

        
        for mid, m in self.meters.items():
            base = m["base_consumption"]
            daily = 0.8 + 0.55 * math.sin(2 * math.pi * (hour - 6) / 24)
            noise = random.gauss(0, 14)
            normal_power = max(15.0, base * daily + noise)

            
            if not m["is_theft"] and random.random() < 0.012:
                m["is_theft"] = True
                m["theft_power"] = random.uniform(60, 220)
                m["theft_start"] = time.time()
            elif m["is_theft"] and (random.random() < 0.03 or time.time() - m["theft_start"] > 50):
                m["is_theft"] = False
                m["theft_power"] = 0.0

            theft_p = m["theft_power"] if m["is_theft"] else 0.0
            total = normal_power + theft_p
            m["current_power"] = total
            m["current_reading"] = total / 230.0
            sub_total += total
            meter_sum_reported += normal_power  # compromised meters report normal only
            theft_any = theft_any or m["is_theft"]

        residual = sub_total - meter_sum_reported  # what we expect to catch
        self.residuals.append(residual)

        # ML detect or fallback
        detected = False
        conf = 0.0
        if HAS_SKLEARN and self.model_trained:
            try:
                feat = np.array([[sub_total, hour, residual]])
                feat_s = self.scaler.transform(feat)
                score = float(self.iforest.decision_function(feat_s)[0])  # higher is normal
                # Threshold tuned to produce high accuracy on our synthetic stream
                detected = (score < -0.07) or (residual > 85)
                conf = min(0.99, max(0.05, abs(score) / 0.5))
            except Exception as e:
                print("ML detect error:", e)
                detected = residual > 90
                conf = min(0.99, residual / (sub_total + 1e-6)) if sub_total > 0 else 0.0
        else:
            detected = residual > 95
            conf = min(0.98, residual / (sub_total + 1e-6)) if sub_total > 0 else 0.0

        self.live_theft_detected = detected
        # Update metrics
        if detected and theft_any:
            self.detection_accuracy["tp"] += 1
        elif detected and not theft_any:
            self.detection_accuracy["fp"] += 1
        elif not detected and theft_any:
            self.detection_accuracy["fn"] += 1
        else:
            self.detection_accuracy["tn"] += 1

        # Log a single system summary row per tick (no per-meter spam)
        self.insert_simulation_record("SYS", "NETWORK", "SYSKEY",
                                      p_meter=meter_sum_reported,
                                      p_sub=sub_total,
                                      residual=residual,
                                      is_theft=detected,
                                      confidence=conf,
                                      detection_ms=1)

    # --------------------------
    # TO BE EDITED LATER 
    # --------------------------
    def update_live_controls(self):
     if self.current_mode != "LIVE":
        return
     if not hasattr(self, 'start_live_btn'):
        return

     if self.live_running and (getattr(self, 'serial_sub', None) or getattr(self, 'serial_meter', None)):
         self.start_live_btn.configure(text="⏸ PAUSE LIVE MONITORING", bg="#ffaa00")
         if getattr(self, 'serial_sub', None) and getattr(self, 'serial_meter', None):
            self.live_status_label.configure(
                text=f"🟢 GRID ONLINE (LIVE) • Sub:{self.serial_sub.port} Meter:{self.serial_meter.port}", 
                fg="#00ff88")
         else:
            port = (self.serial_sub.port if getattr(self, 'serial_sub', None) else self.serial_meter.port)
            self.live_status_label.configure(
                text=f"🟢 GRID ONLINE (LIVE) • {port} (partial)", 
                fg="#00ff88")
     else:
         self.start_live_btn.configure(text="▶ START LIVE MONITORING", bg="#4ecdc4")
         self.live_status_label.configure(text="🔴 GRID OFFLINE (LIVE) — Connect Arduino", fg="#ff6b6b")


     def live_loop(self):
      meter_val = None
      sub_val = None

     while self.current_mode == "LIVE" and self.live_running:
        
        if self.serial_sub and self.serial_sub.in_waiting:
            try:
                raw = self.serial_sub.readline().decode(errors="ignore").strip()
                sub_val = float(raw)
            except Exception:
                pass

            # SOCKET CLOSE FOR PURPOSE 2
            try:
                if self.net_sock:
                    try: self.net_sock.shutdown(socket.SHUT_RDWR)
                    except: pass
                    try: self.net_sock.close()
                    except: pass
                    self.net_sock = None
            except Exception:
                pass

        
        if self.serial_meter and self.serial_meter.in_waiting:
            try:
                raw = self.serial_meter.readline().decode(errors="ignore").strip()
                meter_val = float(raw)
            except Exception:
                pass

        
        if sub_val is not None and meter_val is not None:
            residual = sub_val - meter_val
            ts = int(time.time() * 1000)
            line = f"SUBSTATION,{ts},{sub_val:.3f},{residual:.3f},{meter_val:.3f}"
            self.process_line(line)
            sub_val = None
            meter_val = None

        time.sleep(0.05)

    # --------------------------
    # Interfaces TBE BY 5/12/2025
    # --------------------------
    def create_simulation_interface(self):
        for w in self.root.winfo_children():
            w.destroy()

        frame = tk.Frame(self.root, bg="#0a0a0a")
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        ctrl = tk.Frame(frame, bg="#1a1a2e", height=90)
        ctrl.pack(fill="x", pady=(0, 10))
        ctrl.pack_propagate(False)

        self.start_sim_btn = tk.Button(ctrl, text="▶ START GRID SIMULATION", bg="#00ff88", command=self.toggle_simulation)
        self.start_sim_btn.pack(side="left", padx=10, pady=20)

        back = tk.Button(ctrl, text="◀ BACK", bg="#ff6b6b", command=self.create_startup_ui)
        back.pack(side="left", padx=10, pady=20)

        self.sim_status_label = tk.Label(ctrl, text="🔴 GRID OFFLINE (SIM)", fg="#ff6b6b", bg="#1a1a2e")
        self.sim_status_label.pack(side="left", padx=20)

        self.accuracy_label = tk.Label(ctrl, text="Accuracy: Ready", bg="#1a1a2e", fg="white")
        self.accuracy_label.pack(side="right", padx=20)

        content = tk.Frame(frame, bg="#0a0a0a")
        content.pack(fill="both", expand=True)

        # Left: grid canvas + ledger button
        left = tk.Frame(content, bg="#1a1a2e", width=520)
        left.pack(side="left", fill="y", padx=(0, 10))
        left.pack_propagate(False)

        tk.Label(left, text="⚡ SMART METER GRID (SIM)", bg="#1a1a2e", fg="#00ff88", font=("Arial", 12, "bold")).pack(pady=8)

        canvas_holder = tk.Frame(left, bg="#1a1a2e")
        canvas_holder.pack(fill="both", expand=True, padx=10, pady=10)
        self.live_grid_canvas = tk.Canvas(canvas_holder, bg="#0a0a0a", width=500, height=460)
        self.live_grid_canvas.pack(fill="both", expand=True)

        tk.Button(left, text="🔐 VIEW LEDGER (SIM)", bg="#a8e6cf",
                  command=lambda: self.view_ledger(which="simulation")).pack(pady=6)

        
        right = tk.Frame(content, bg="#1a1a2e")
        right.pack(side="right", fill="both", expand=True)

        
        self.fig_residuals, self.ax_residuals = plt.subplots(figsize=(6, 3))
        self.ax_residuals.set_facecolor('#1a1a2e')
        self.canvas_residuals = FigureCanvasTkAgg(self.fig_residuals, master=right)
        self.canvas_residuals.get_tk_widget().pack(fill="both", expand=True, padx=6, pady=6)

        # CHANGE BEFORE FINAL ROUND BAAD MEIN CHECK NO.12
        self.fig_current, self.ax_current = plt.subplots(figsize=(6, 3))
        self.ax_current.set_facecolor('#1a1a2e')
        self.canvas_current = FigureCanvasTkAgg(self.fig_current, master=right)
        self.canvas_current.get_tk_widget().pack(fill="both", expand=True, padx=6, pady=(0, 6))

        self.root.after(300, self.draw_live_power_grid)
        # If LIVE_WIFI mode,repurpose the start button to Wifi BAAD MEIN CHECK NO.13
        if self.current_mode == "LIVE_WIFI":
            self.start_live_btn.configure(command=self.toggle_live_wifi, bg="#3b82f6", text="▶ START LIVE (Wi-Fi)")

    def create_live_interface(self):
        for w in self.root.winfo_children():
            w.destroy()

        frame = tk.Frame(self.root, bg="#0a0a0a")
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        ctrl = tk.Frame(frame, bg="#1a1a2e", height=90)
        ctrl.pack(fill="x", pady=(0, 10))
        ctrl.pack_propagate(False)

        self.start_live_btn = tk.Button(ctrl, text="▶ START LIVE MONITORING", bg="#4ecdc4", command=self.toggle_live)
        self.start_live_btn.pack(side="left", padx=10, pady=20)

        back = tk.Button(ctrl, text="◀ BACK", bg="#ff6b6b", command=self.create_startup_ui)
        back.pack(side="left", padx=10, pady=20)

        self.live_status_label = tk.Label(ctrl, text="🔴 GRID OFFLINE (LIVE)", fg="#ff6b6b", bg="#1a1a2e")
        self.live_status_label.pack(side="left", padx=20)

        content = tk.Frame(frame, bg="#0a0a0a")
        content.pack(fill="both", expand=True)

        
        left = tk.Frame(content, bg="#1a1a2e", width=520)
        left.pack(side="left", fill="y", padx=(0, 10))
        left.pack_propagate(False)

        tk.Label(left, text="⚡ SMART METER GRID (LIVE)", bg="#1a1a2e", fg="#00ff88", font=("Arial", 12, "bold")).pack(pady=8)

        canvas_holder = tk.Frame(left, bg="#1a1a2e")
        canvas_holder.pack(fill="both", expand=True, padx=10, pady=10)
        self.live_grid_canvas = tk.Canvas(canvas_holder, bg="#0a0a0a", width=500, height=460)
        self.live_grid_canvas.pack(fill="both", expand=True)

        tk.Button(left, text="🔐 VIEW LEDGER (LIVE)", bg="#4ecdc4",
                  command=lambda: self.view_ledger(which="live")).pack(pady=6)

        
        right = tk.Frame(content, bg="#1a1a2e")
        right.pack(side="right", fill="both", expand=True)

        
        self.fig_residuals, self.ax_residuals = plt.subplots(figsize=(6, 3))
        self.ax_residuals.set_facecolor('#1a1a2e')
        self.canvas_residuals = FigureCanvasTkAgg(self.fig_residuals, master=right)
        self.canvas_residuals.get_tk_widget().pack(fill="both", expand=True, padx=6, pady=6)

        
        self.fig_current, self.ax_current = plt.subplots(figsize=(6, 3))
        self.ax_current.set_facecolor('#1a1a2e')
        self.canvas_current = FigureCanvasTkAgg(self.fig_current, master=right)
        self.canvas_current.get_tk_widget().pack(fill="both", expand=True, padx=6, pady=(0, 6))

        self.root.after(300, self.draw_live_power_grid)

    # --------------------------
    # BAAD MEIN CHECK NO.14
    # --------------------------
    def launch_electrical_grid(self):
        if self.canvas_grid_win and tk.Toplevel.winfo_exists(self.canvas_grid_win):
            try:
                self.canvas_grid_win.lift()
                return
            except Exception:
                pass
        win = tk.Toplevel(self.root)
        win.title("⚡ Electrical Grid - Live Network View")
        win.geometry("900x600")
        win.configure(bg="#0a0a0a")
        self.canvas_grid_win = win

        canvas = tk.Canvas(win, bg="#0a0a0a")
        canvas.pack(fill="both", expand=True)
        self.live_grid_canvas = canvas
        canvas.bind("<Button-1>", lambda e: messagebox.showinfo("Grid", "Use Ledger for detailed records."))
        self.root.after(300, self.draw_live_power_grid)

    def draw_live_power_grid(self):
        c = self.live_grid_canvas
        if not c:
            return
        try:
            c.delete("all")
        except Exception:
            pass
        w = c.winfo_width() or 800
        h = c.winfo_height() or 450

        # PC node
        pc_x, pc_y = w // 2, 60
        pc_online = self.current_mode in ("SIMULATION", "LIVE")
        pc_color = "#00ff88" if pc_online else "#666666"
        c.create_rectangle(pc_x - 70, pc_y - 30, pc_x + 70, pc_y + 30, fill=pc_color, outline="#fff")
        c.create_text(pc_x, pc_y, text="CENTRAL PC\nMonitor", fill="black", font=("Arial", 10, "bold"))
        c.create_text(pc_x, pc_y + 48, text=self.grid_topology.central_station["address"], fill="#aaa", font=("Arial", 8))

        # Substation node
        sub_x, sub_y = w // 2, h // 2 - 40
        live_ok = (self.current_mode == "LIVE" and self.serial_conn is not None)
        sim_ok = (self.current_mode == "SIMULATION" and self.simulation_running)
        sub_online = live_ok or sim_ok
        sub_color = "#1e90ff" if sub_online and not self.live_theft_detected else ("#ff3b30" if self.live_theft_detected else "#666666")
        c.create_rectangle(sub_x - 70, sub_y - 28, sub_x + 70, sub_y + 28, fill=sub_color, outline="#fff")
        c.create_text(sub_x, sub_y, text="Substation\nArduino", fill="white", font=("Arial", 9, "bold"))
        c.create_text(sub_x, sub_y + 42, text=self.grid_topology.substation["address"], fill="#aaa", font=("Arial", 8))

        line_color = "#00ff88" if sub_online else "#666666"
        c.create_line(pc_x, pc_y + 30, sub_x, sub_y - 28, fill=line_color, width=3)
        c.create_text((pc_x + sub_x) // 2 + 10, (pc_y + sub_y) // 2, text="USB Serial 115200", fill="#aaa", font=("Arial", 8))

        # NEAR THE TABLE METER
        if self.current_mode == "SIMULATION":
            meters_to_draw = list(self.meters.keys()) or list(self.grid_topology.meters.keys())
            max_draw = min(len(meters_to_draw), 12)
            radius = min(220, (w // 2) - 120)
            cx, cy = sub_x, sub_y + 40
            for i, mid in enumerate(meters_to_draw[:max_draw]):
                angle = 2 * math.pi * i / max_draw
                mx = int(cx + radius * math.cos(angle))
                my = int(cy + radius * math.sin(angle))
                info = self.meters.get(mid) or self.grid_topology.meters.get(mid, {})
                theft = bool(info.get("is_theft", False))
                node_color = "#ff3b30" if theft else ("#00c853" if sub_online else "#666666")
                c.create_oval(mx - 28, my - 18, mx + 28, my + 18, fill=node_color, outline="#fff")
                c.create_text(mx, my - 2, text=mid, fill="black", font=("Arial", 9, "bold"))
                addr = info.get("address", "-")
                c.create_text(mx, my + 18, text=addr, fill="#ddd", font=("Arial", 7))
                c.create_line(sub_x, sub_y + 28, mx, my - 10, fill=("#ff3b30" if theft else line_color), width=2)
        elif self.current_mode == "LIVE":
            # Exactly one meter in live view
            mx, my = sub_x + 220, sub_y + 40
            theft = any(m.get("is_theft", False) for m in self.meters.values()) if self.meters else False
            node_color = "#ff3b30" if theft else ("#00c853" if sub_online else "#666666")
            c.create_oval(mx - 28, my - 18, mx + 28, my + 18, fill=node_color, outline="#fff")
            mid = next(iter(self.meters.keys()), "M001")
            addr = (self.meters.get(mid, {}).get("address") if self.meters else "192.168.1.20")
            c.create_text(mx, my - 2, text=mid, fill="black", font=("Arial", 9, "bold"))
            c.create_text(mx, my + 18, text=addr, fill="#ddd", font=("Arial", 7))
            c.create_line(sub_x, sub_y + 28, mx, my - 10, fill=("#ff3b30" if theft else line_color), width=2)

        # If live mode but no serial/data => show OFF overlay
        if self.current_mode == "LIVE" and not self.serial_conn:
            c.create_text(w // 2, h // 2 + 120, text="GRID OFF — NO DATA", fill="red", font=("Arial", 18, "bold"))

        try:
            self.root.after(700, self.draw_live_power_grid)
        except Exception:
            pass

    # --------------------------
    # BAAD MEIN CHECK NO.15 REPLACE WITH HYPERLEDGER FABRIC
    # --------------------------
    def view_ledger(self, which=None):
        # Decide which by mode unless forced
        if which is None:
            which = "simulation" if self.current_mode == "SIMULATION" else ("live" if self.current_mode == "LIVE" else "simulation")
        w = tk.Toplevel(self.root)
        w.title("Ledger Viewer")
        w.geometry("1000x700")
        w.configure(bg="#0a0a0a")
        header = tk.Label(w, text="🔐 TAMPER-PROOF ENERGY TRANSACTION LEDGER", bg="#1a1a2e", fg="#a8e6cf", font=("Arial", 14, "bold"))
        header.pack(fill="x", padx=10, pady=8)

        # Only show relevant buttons
        filt = tk.Frame(w, bg="#0a0a0a")
        filt.pack(fill="x", padx=10)
        if which == "simulation":
            tk.Button(filt, text="SIMULATION", state="disabled").pack(side="left", padx=6)
        else:
            tk.Button(filt, text="LIVE", state="disabled").pack(side="left", padx=6)

        textbox = scrolledtext.ScrolledText(w, font=("Courier", 10), bg="#0a0a0a", fg="#00ff88")
        textbox.pack(fill="both", expand=True, padx=10, pady=10)
        self.load_ledger_text(textbox, which)

    def load_ledger_text(self, text_widget, which):
        text_widget.delete("1.0", tk.END)
        if which == "simulation":
            text_widget.insert("end", "=== SIMULATION LEDGER (most recent first) ===\n\n")
            try:
                self.cursor.execute("SELECT * FROM simulation_transactions ORDER BY id DESC LIMIT 300")
                rows = self.cursor.fetchall()
            except Exception as e:
                rows = []
                print("Ledger fetch error:", e)
            if not rows:
                text_widget.insert("end", "No simulation data yet. Start Grid Simulation.\n")
                return
            for row in rows:
                try:
                    (id_, ts, meter_id, meter_addr, pk, p_meter, p_sub, resid, h, prev, is_th, conf, dms) = row
                    block = (
                        f"[SIM #{id_}] {ts}\n"
                        f"Meter: {meter_id} ({meter_addr})\n"
                        f"P_meter: {p_meter:.2f} W\nP_sub: {p_sub:.2f} W\n"
                        f"Residual: {resid:.2f} W\n"
                        f"Theft: {bool(is_th)}  Confidence: {conf*100:.1f}%\n"
                        f"Hash: {h[:16]}...\n\n"
                    )
                    text_widget.insert("end", block)
                except Exception:
                    text_widget.insert("end", str(row) + "\n\n")
        else:  
            text_widget.insert("end", "=== LIVE LEDGER (most recent first) ===\n\n")
            try:
                self.cursor.execute("SELECT * FROM live_transactions ORDER BY id DESC LIMIT 300")
                rows = self.cursor.fetchall()
            except Exception as e:
                rows = []
                print("Ledger fetch error:", e)
            if not rows:
                text_widget.insert("end", "GRID OFF — NO DATA (connect Arduino to begin logging).\n")
                return
            for row in rows:
                try:
                    (id_, ts, meter_id, meter_addr, pk, cur, p_meter, sub_cur, sub_pwr, resid, h, prev, is_th, conf, dms) = row
                    block = (
                        f"[LIVE #{id_}] {ts}\n"
                        f"Meter: {meter_id} ({meter_addr})\n"
                        f"I_meter: {cur:.3f} A  P_meter: {p_meter:.2f} W\n"
                        f"I_sub: {sub_cur:.3f} A  P_sub: {sub_pwr:.2f} W\n"
                        f"Residual: {resid:.2f} W\n"
                        f"Theft: {bool(is_th)}  Confidence: {conf*100:.1f}%\n"
                        f"Hash: {h[:16]}...\n\n"
                    )
                    text_widget.insert("end", block)
                except Exception:
                    text_widget.insert("end", str(row) + "\n\n")

    # --------------------------
    # 13/08/2025
    # --------------------------
    def update_live_ui(self):
        # Accuracy label (simulation)
        if self.current_mode == "SIMULATION":
            tp = self.detection_accuracy["tp"]
            fp = self.detection_accuracy["fp"]
            tn = self.detection_accuracy["tn"]
            fn = self.detection_accuracy["fn"]
            total = tp + fp + tn + fn
            if total > 0:
                acc = (tp + tn) / total * 100.0
                self.accuracy_label.configure(text=f"Accuracy: {acc:.2f}%  (TP:{tp} FP:{fp} TN:{tn} FN:{fn}, n={total})")
            else:
                self.accuracy_label.configure(text="Accuracy: Waiting for data…")

        
        try:
            y = list(self.residuals)[-240:]
            self.ax_residuals.clear()
            if len(y) == 0:
                self.ax_residuals.text(0.5, 0.5, "No data yet", ha='center')
            else:
                self.ax_residuals.plot(y, lw=1.2)
                # No explicit threshold label text requested
                
                
                self.ax_residuals.set_title("Residuals (Substation − Sum Meters) [W]")
            self.canvas_residuals.draw_idle()
        except Exception:
            pass

        
        try:
            if self.current_mode == "LIVE":
                cur_series = list(self.live_currents)[-240:]
            else:
                # BAAD MEIN CHECKPOINT NO.11
                cur_series = [max(0.0, v / 230.0) for v in list(self.residuals)[-240:]]

            self.ax_current.clear()
            if len(cur_series) == 0:
                self.ax_current.text(0.5, 0.5, "No data yet", ha='center')
            else:
                self.ax_current.plot(cur_series, lw=1.2)
                self.ax_current.set_title("Live Theft Current (A)")
            self.canvas_current.draw_idle()
        except Exception:
            pass

        # Live status text when relevant
        if self.current_mode == "LIVE":
            self.update_live_controls()

    # --------------------------
    # CHECK POINT NO. 16 DEBUG THIS BEFORE FINAL ROUND 13/09
    # --------------------------
    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.mainloop()

    def on_close(self):
        try:
            self.simulation_running = False
            self.live_running = False
            self.current_mode = "NONE"  # Signal all threads to stop

            try:
                if getattr(self, 'serial_sub', None):
                    try:
                        self.serial_sub.close()
                    except:
                        pass
                if getattr(self, 'serial_meter', None):
                   try:
                        self.serial_meter.close()
                   except:
                        pass
                if self.serial_conn:
                    try:
                        self.serial_conn.close()
                    except:
                        pass
            except Exception:
                pass


        
            if self.sim_thread and self.sim_thread.is_alive():
                self.sim_thread.join(timeout=2.0)
            if self.live_thread and self.live_thread.is_alive():
                self.live_thread.join(timeout=2.0)
            self.conn.close()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass


if __name__ == "__main__":
    app = SmartEnergyTheftDetector()
    app.run()
