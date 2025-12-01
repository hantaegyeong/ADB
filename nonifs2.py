import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext
import can
import cantools
import time
import threading
import crcmod

# =========================== CRC-8 계산 함수 ===========================
try:
    crc8_func = crcmod.mkCrcFun(0x11D, initCrc=0xFF, rev=True, xorOut=0xFF)
except NameError:
    print("WARNING: crcmod is not installed. CRC calculations will fail.")
    crc8_func = lambda data: 0

def calculate_message_crc(message: cantools.database.can.Message, signal_values: dict, crc_signal_name: str) -> int:
    temp_signals = signal_values.copy()
    if crc_signal_name in temp_signals:
        temp_signals[crc_signal_name] = 0
    try:
        encoded_data = message.encode(temp_signals)
    except Exception as e:
        print(f"CRC 인코딩 오류 ({message.name}): {e}")
        encoded_data = b'\x00' * message.length
    return crc8_func(encoded_data)

# ============================ CAN 메시지 클래스 ============================
class CANMessageSender:
    def __init__(self, dbc_file_path: str, can_interface: str, channel: str, bitrate: int):
        self.db = cantools.database.load_file(dbc_file_path)
        
        if can_interface == 'gs_usb':
            try:
                final_channel = int(channel)
            except ValueError:
                print(f"Warning: gs_usb channel '{channel}' is not an integer. Defaulting to 0.")
                final_channel = 0
        else:
            final_channel = channel

        self.bus = can.interface.Bus(channel=final_channel, interface=can_interface, bitrate=bitrate)
    
    def send_message(self, message_name: str, signal_values: dict):
        message = self.db.get_message_by_name(message_name)
        data = message.encode(signal_values)
        can_msg = can.Message(arbitration_id=message.frame_id, data=data, is_extended_id=False)
        self.bus.send(can_msg)
    
    def close(self):
        if self.bus is not None:
            self.bus.shutdown()

# =============================== Tkinter GUI 애플리케이션 ===============================
class CanControlApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("GV80 헤드램프 제어 (gs_usb Mode)")
        self.geometry("600x720") 

        # --- 상태 변수 ---
        self.sender = None
        self.is_sending = False
        self.sending_thread = None
        self.counter = 0
        
        self.turn_signal_state = None 
        self.blink_state = False 
        
        self.is_low_beam_on = False
        self.is_high_beam_on = False
        
        self.is_ifs_on = False 

        self._create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- 1. 연결 설정 프레임 ---
        conn_frame = ttk.LabelFrame(main_frame, text="CAN 연결 설정", padding="10")
        conn_frame.pack(fill=tk.X, pady=5)
        conn_frame.columnconfigure(1, weight=1)
        
        self.dbc_path = tk.StringVar(value="Temp_DBC.dbc")
        ttk.Label(conn_frame, text="DBC 파일:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(conn_frame, textvariable=self.dbc_path, width=40).grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(conn_frame, text="찾아보기", command=self.browse_dbc).grid(row=0, column=2, padx=5, pady=5)
        
        # --- [수정됨] 기본값을 gs_usb 환경에 맞게 변경 ---
        self.interface = tk.StringVar(value="gs_usb")  # 기본값: slcan -> gs_usb
        self.channel = tk.StringVar(value="0")         # 기본값: COM14 -> 0 (USB 장치 인덱스)
        self.bitrate = tk.IntVar(value=500000)
        
        ttk.Label(conn_frame, text="인터페이스:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(conn_frame, textvariable=self.interface).grid(row=1, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        
        ttk.Label(conn_frame, text="채널 (USB Index):").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(conn_frame, textvariable=self.channel).grid(row=2, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        
        ttk.Label(conn_frame, text="비트레이트:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(conn_frame, textvariable=self.bitrate).grid(row=3, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        
        self.connect_button = ttk.Button(conn_frame, text="연결", command=self.connect_can)
        self.connect_button.grid(row=4, column=1, padx=5, pady=10, sticky="e")
        self.disconnect_button = ttk.Button(conn_frame, text="연결 해제", command=self.disconnect_can, state=tk.DISABLED)
        self.disconnect_button.grid(row=4, column=2, padx=5, pady=10, sticky="w")


        # --- 2. 방향지시등 제어 프레임 ---
        control_frame = ttk.LabelFrame(main_frame, text="방향지시등 제어", padding="10")
        control_frame.pack(fill=tk.X, pady=5)
        self.solid_on_button = ttk.Button(control_frame, text="켜기", command=self.send_solid_on, state=tk.DISABLED)
        self.solid_on_button.pack(side=tk.LEFT, padx=5, pady=10, expand=True)
        self.solid_off_button = ttk.Button(control_frame, text="끄기", command=self.send_solid_off, state=tk.DISABLED)
        self.solid_off_button.pack(side=tk.LEFT, padx=5, pady=10, expand=True)
        self.blink_start_button = ttk.Button(control_frame, text="깜빡임 시작", command=self.start_blinking, state=tk.DISABLED)
        self.blink_start_button.pack(side=tk.LEFT, padx=5, pady=10, expand=True)
        self.blink_stop_button = ttk.Button(control_frame, text="깜빡임 중지", command=self.stop_blinking, state=tk.DISABLED)
        self.blink_stop_button.pack(side=tk.LEFT, padx=5, pady=10, expand=True)
        
        # --- 3. IFS 제어 프레임 ---
        ifs_frame = ttk.LabelFrame(main_frame, text="IFS 제어", padding="10")
        ifs_frame.pack(fill=tk.X, pady=5)
        self.ifs_toggle_button = ttk.Button(ifs_frame, text="IFS 켜기", command=self.toggle_ifs, state=tk.DISABLED)
        self.ifs_toggle_button.pack(fill=tk.X, padx=5, pady=5)

        # --- 4. 전조등 제어 프레임 ---
        self.headlight_frame = ttk.LabelFrame(main_frame, text="전조등 제어 (BCM 수동)", padding="10")
        self.headlight_frame.pack(fill=tk.X, pady=5)
        self.low_beam_button = ttk.Button(self.headlight_frame, text="하향등 켜기", command=self.set_low_beam, state=tk.DISABLED)
        self.low_beam_button.pack(side=tk.LEFT, padx=5, pady=5, expand=True)
        self.high_beam_button = ttk.Button(self.headlight_frame, text="상향등 켜기", command=self.set_high_beam, state=tk.DISABLED)
        self.high_beam_button.pack(side=tk.LEFT, padx=5, pady=5, expand=True)
        self.headlights_off_button = ttk.Button(self.headlight_frame, text="끄기", command=self.set_headlights_off, state=tk.DISABLED)
        self.headlights_off_button.pack(side=tk.LEFT, padx=5, pady=5, expand=True)

        # --- 5. 로그 프레임 ---
        log_frame = ttk.LabelFrame(main_frame, text="로그", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=10)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log("프로그램이 시작되었습니다.")
        self.log("TIP: gs_usb 모드 사용 시 채널은 보통 0 입니다.")

    def set_control_buttons_state(self, is_enabled):
        """연결 상태에 따라 모든 제어 버튼의 기본 상태를 설정합니다."""
        state = tk.NORMAL if is_enabled else tk.DISABLED
        
        # 방향지시등
        self.solid_on_button.config(state=state)
        self.solid_off_button.config(state=state)
        self.blink_start_button.config(state=state)
        self.blink_stop_button.config(state=tk.DISABLED)
        
        # IFS
        self.ifs_toggle_button.config(state=state)

        # 전조등 (IFS가 꺼져있을 때만 활성화)
        if is_enabled and not self.is_ifs_on:
            self.low_beam_button.config(state=tk.NORMAL)
            self.high_beam_button.config(state=tk.NORMAL)
            self.headlights_off_button.config(state=tk.NORMAL)
        else:
            self.low_beam_button.config(state=tk.DISABLED)
            self.high_beam_button.config(state=tk.DISABLED)
            self.headlights_off_button.config(state=tk.DISABLED)

    # --- 연결 및 상태 관리 ---
    def connect_can(self):
        try:
            self.sender = CANMessageSender(self.dbc_path.get(), self.interface.get(), self.channel.get(), self.bitrate.get())
            self.log(f"✅ CAN 연결 성공: {self.interface.get()} (Ch: {self.channel.get()})")
            self.connect_button.config(state=tk.DISABLED)
            self.disconnect_button.config(state=tk.NORMAL)
            self.set_control_buttons_state(True)
            self.manage_sending_loop()
        except Exception as e:
            self.log(f"❌ CAN 연결 실패: {e}")
            self.log("TIP: 'pip install gs_usb'를 했는지 확인하세요.")

    def disconnect_can(self):
        self.stop_sending_loop()
        if self.sender:
            self.sender.close()
            self.sender = None
            self.log("✅ CAN 연결이 안전하게 해제되었습니다.")
        self.connect_button.config(state=tk.NORMAL)
        self.disconnect_button.config(state=tk.DISABLED)
        self.set_control_buttons_state(False)

    def manage_sending_loop(self):
        should_be_sending = True 
        
        if should_be_sending and not self.is_sending:
            self.is_sending = True
            self.sending_thread = threading.Thread(target=self._sending_loop, daemon=True)
            self.sending_thread.start()
            self.log("▶️ 주기적 메시지 전송을 시작합니다.")
        elif not should_be_sending and self.is_sending:
            self.stop_sending_loop()
    
    def stop_sending_loop(self):
        if not self.is_sending: return
        self.is_sending = False
        if self.sending_thread:
            self.sending_thread.join(timeout=0.5)
        self.log("⏹️ 주기적 메시지 전송을 중단했습니다.")

    # --- 버튼 콜백 함수 ---
    def start_blinking(self):
        self.turn_signal_state = 'right_blink'
        self.log("▶️ 우측 방향지시등 깜빡임을 시작합니다.")
        self.blink_start_button.config(state=tk.DISABLED)
        self.solid_on_button.config(state=tk.DISABLED)
        self.solid_off_button.config(state=tk.DISABLED)
        self.blink_stop_button.config(state=tk.NORMAL)

    def stop_blinking(self):
        self.turn_signal_state = None
        self.log("⏹️ 깜빡임을 중단했습니다.")
        self.blink_start_button.config(state=tk.NORMAL)
        self.solid_on_button.config(state=tk.NORMAL)
        self.solid_off_button.config(state=tk.NORMAL)
        self.blink_stop_button.config(state=tk.DISABLED)

    def send_solid_on(self):
        self.turn_signal_state = 'right_solid_on'
        self.log("🔼 '켜기' 상태를 유지합니다.")
        self.blink_start_button.config(state=tk.DISABLED)
        self.solid_on_button.config(state=tk.DISABLED)
        self.solid_off_button.config(state=tk.NORMAL)
        self.blink_stop_button.config(state=tk.DISABLED)

    def send_solid_off(self):
        self.turn_signal_state = None
        self.log("🔽 '끄기' 상태로 변경합니다.")
        self.blink_start_button.config(state=tk.NORMAL)
        self.solid_on_button.config(state=tk.NORMAL)
        self.solid_off_button.config(state=tk.DISABLED)
        self.blink_stop_button.config(state=tk.DISABLED)

    # --- IFS 토글 ---
    def toggle_ifs(self):
        self.is_ifs_on = not self.is_ifs_on
        
        if self.is_ifs_on:
            self.ifs_toggle_button.config(text="IFS 끄기 (BCM 수동 제어)")
            self.log("💡 IFS 켜기 요청됨. (H/Lamp High control Mode by IFS)")
            
            self.set_headlights_off()
            self.low_beam_button.config(state=tk.NORMAL)
            self.high_beam_button.config(state=tk.NORMAL)
            self.headlights_off_button.config(state=tk.NORMAL)
            self.headlight_frame.config(text="전조등 제어 (IFS 자동)")
        else:
            self.ifs_toggle_button.config(text="IFS 켜기 (자동 제어)")
            self.log(" manual BCM 수동 제어 모드로 전환합니다.")
            
            self.low_beam_button.config(state=tk.NORMAL)
            self.high_beam_button.config(state=tk.NORMAL)
            self.headlights_off_button.config(state=tk.NORMAL)
            self.headlight_frame.config(text="전조등 제어 (BCM 수동)")

    # --- 전조등 콜백 ---
    def set_low_beam(self):
        self.is_low_beam_on = True
        self.is_high_beam_on = False
        self.log("하향등 켜기 요청됨.")

    def set_high_beam(self):
        self.is_low_beam_on = True 
        self.is_high_beam_on = True
        self.log("상향등 켜기 요청됨.")
        
    def set_headlights_off(self):
        self.is_low_beam_on = False
        self.is_high_beam_on = False
        self.log("전조등 끄기 요청됨.")

    # --- 핵심 전송 루프 ---
    def _sending_loop(self):
        try:
            bcm_07_msg = self.sender.db.get_message_by_name('BCM_07_200ms')
            bcm_08_msg = self.sender.db.get_message_by_name('BCM_08_200ms')
        except Exception as e:
            self.after(0, self.log, f"❌ DBC 메시지 로드 실패: {e}")
            self.after(0, self.stop_sending_loop)
            return

        while self.is_sending:
            try:
                # --- 1. 방향지시등(ICU_04_200ms) ---
                right_req = 0
                if self.turn_signal_state == 'right_blink':
                    if self.blink_state: right_req = 2
                    self.blink_state = not self.blink_state
                elif self.turn_signal_state == 'right_solid_on':
                    right_req = 2
                
                icu_04_signals = {
                    'Lamp_TrnSigLmpRtOnReq': right_req, 'Lamp_TrnSigLmpLftOnReq': 0,
                    'ExtLamp_TrnSigLmpLftBlnkngSta': 0, 'ExtLamp_TrnSigLmpRtBlnkngSta': 0,
                    'ExtLamp_ExtrnlTailLmpSta': 0, 'ExtLamp_HzrdSwSta': 0,
                    'ExtLamp_RrFgLmpSta': 0, 'IntLamp_InlTailLmpSta': 0
                }
                
                # --- 2. 전조등(BCM_07_200ms) ---
                bcm_07_signals = {
                    'Lamp_HdLmpLoOnReq': int(self.is_low_beam_on),
                    'Lamp_HdLmpHiOnReq': int(self.is_high_beam_on),
                    'BCM_AlvCnt7Val': self.counter % 16, 'BCM_Crc7Val': 0,
                    'Lamp_DedicatedDrlOnReq': 0, 'Lamp_HiPrioHzrdReq': 0,
                    'Lamp_LoPrioHzrdReq': 0, 'Lamp_IntTailLmpOnReq': 0,
                    'Lamp_ExtrnlTailLmpOnReq': 0, 'Lamp_AvTailLmpSta': 0,
                    'Lamp_ExtrnlLpWlcmSta': 0
                }
                bcm_07_signals['BCM_Crc7Val'] = calculate_message_crc(bcm_07_msg, bcm_07_signals, 'BCM_Crc7Val')
                
                # --- 3. IFS 제어(BCM_08_200ms) ---
                bcm_08_signals = {
                    'Lamp_IFSCtrlModTyp': int(self.is_ifs_on), 
                    'BCM_Crc8Val': 0,
                    'BCM_AlvCnt8Val': self.counter % 16,
                    'Lamp_HbaCtrlModTyp': 0, 'Lamp_RrFogLmpOnReq': 0,
                    'Lamp_TailLmpWlcmCmd': 0, 'Lamp_HdLmpWlcmCmd': 0,
                    'Lamp_PuddleLmpOnReq': 0
                }
                bcm_08_signals['BCM_Crc8Val'] = calculate_message_crc(bcm_08_msg, bcm_08_signals, 'BCM_Crc8Val')

                # --- 메시지 전송 ---
                self.sender.send_message('ICU_04_200ms', icu_04_signals)
                self.sender.send_message('BCM_07_200ms', bcm_07_signals)
                self.sender.send_message('BCM_08_200ms', bcm_08_signals)
                
                self.counter += 1
                time.sleep(0.2)

            except Exception as e:
                self.after(0, self.log, f"❌ 전송 루프 오류: {e}")
                time.sleep(1)
    
    # --- 유틸리티 함수 ---
    def browse_dbc(self):
        filepath = filedialog.askopenfilename(filetypes=(("DBC Files", "*.dbc"), ("All files", "*.*")))
        if filepath: self.dbc_path.set(filepath)
    def on_closing(self):
        self.log("프로그램을 종료합니다...")
        self.disconnect_can()
        self.destroy()

    def log(self, message):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.config(state=tk.DISABLED)
        self.log_text.see(tk.END)

if __name__ == "__main__":
    app = CanControlApp()
    app.mainloop()
