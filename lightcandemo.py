import can
import cantools
import time
import threading

CAN_CHANNEL = 'COM14'
CAN_BITRATE = 500000
MESSAGE_ID = 1345
MESSAGE_NAME = 'CGW1'
MESSAGE_LEN = 8

DBC_STRING = f"""
VERSION ""

BO_ {MESSAGE_ID} {MESSAGE_NAME}: {MESSAGE_LEN} BCM
 SG_ CF_Gway_HeadLampHigh : 32|1@1+ (1,0) [0|1] "" CLU
 SG_ CF_Gway_HeadLampLow : 31|1@1+ (1,0) [0|1] "" CLU
 SG_ CF_Gway_TurnSigLh : 19|2@1+ (1,0) [0|3] "" CLU
 SG_ CF_Gway_TurnSigRh : 62|2@1+ (1,0) [0|3] "" CLU
 SG_ CF_Gway_IGNSw : 0|3@1+ (1,0) [0|7] "" CLU

VAL_ {MESSAGE_ID} CF_Gway_HeadLampHigh 1 "On" 0 "Off";
VAL_ {MESSAGE_ID} CF_Gway_HeadLampLow 1 "On" 0 "Off";
VAL_ {MESSAGE_ID} CF_Gway_TurnSigLh 1 "Left_On" 0 "Off";
VAL_ {MESSAGE_ID} CF_Gway_TurnSigRh 2 "Right_On" 0 "Off";
VAL_ {MESSAGE_ID} CF_Gway_IGNSw 2 "IGNSw_ON" 1 "ACC" 0 "LOCK";
"""

class BenchController:
    def __init__(self, interface, channel, bitrate):
        self.bus = can.interface.Bus(
            bustype=interface,
            channel=channel,
            bitrate=bitrate,
        )
        self.db = cantools.database.load_string(DBC_STRING)
        self.run_wakeup_thread = True
        
        self.wakeup_thread = threading.Thread(target=self._send_wakeup_messages, daemon=True)
        self.wakeup_thread.start()
        
        print(f"컨트롤러가 '{channel}' 채널({interface} 타입)에서 초기화되었습니다.")

    def _send_wakeup_messages(self):
        print("⚡️ ECU 깨우기 스레드 시작 (IGN ON 신호 주기적 전송)")
        msg = self.db.get_message_by_name(MESSAGE_NAME)
        signals = {'CF_Gway_IGNSw': 2}
        data = msg.encode(signals)
        message = can.Message(arbitration_id=msg.frame_id, data=data)
        
        while self.run_wakeup_thread:
            self.bus.send(message)
            time.sleep(0.1)

    def _send_control_message(self, signals):
        try:
            msg = self.db.get_message_by_name(MESSAGE_NAME)
            data = msg.encode(signals)
            message = can.Message(arbitration_id=msg.frame_id, data=data)
            self.bus.send(message)
        except Exception as e:
            print(f"메시지 전송 실패: {e}")

    def set_lights(self, light_state="Off", turn_signal="Off"):
        signals = {'CF_Gway_IGNSw': 2}

        if light_state == "Low_Beam":
            signals['CF_Gway_HeadLampLow'] = 1
            signals['CF_Gway_HeadLampHigh'] = 0
        elif light_state == "High_Beam":
            signals['CF_Gway_HeadLampLow'] = 1
            signals['CF_Gway_HeadLampHigh'] = 1
        else:
            signals['CF_Gway_HeadLampLow'] = 0
            signals['CF_Gway_HeadLampHigh'] = 0

        if turn_signal == "Left":
            signals['CF_Gway_TurnSigLh'] = 1
            signals['CF_Gway_TurnSigRh'] = 0
        elif turn_signal == "Right":
            signals['CF_Gway_TurnSigLh'] = 0
            signals['CF_Gway_TurnSigRh'] = 2
        else:
            signals['CF_Gway_TurnSigLh'] = 0
            signals['CF_Gway_TurnSigRh'] = 0
        
        print(f"전송 명령: {signals}")
        self._send_control_message(signals)

    def shutdown(self):
        self.run_wakeup_thread = False
        self.wakeup_thread.join()
        self.bus.shutdown()
        print("CAN 버스 연결 종료")

if __name__ == "__main__":
    controller = None
    try:
        controller = BenchController(
            interface='slcan',
            channel=CAN_CHANNEL,
            bitrate=CAN_BITRATE
        )

        
        print("\n[1단계] 하향등 켜기")
        controller.set_lights(light_state="Low_Beam")
        time.sleep(3)

        print("\n[2단계] 좌측 방향지시등 추가")
        controller.set_lights(light_state="Low_Beam", turn_signal="Left")
        time.sleep(3)
        
        print("\n[3단계] 우측 방향지시등으로 변경")
        controller.set_lights(light_state="Low_Beam", turn_signal="Right")
        time.sleep(3)
        
        print("\n[4단계] 상향등 켜기")
        controller.set_lights(light_state="High_Beam", turn_signal="Off")
        time.sleep(3)
        
        print("\n[5단계] 모든 조명 끄기")
        controller.set_lights(light_state="Off", turn_signal="Off")
        print("\n--- 시퀀스 종료 ---")
        time.sleep(1)

    except Exception as e:
        print(f"\n스크립트 실행 중 오류 발생: {e}")
    
    finally:
        if controller:
            controller.shutdown()
