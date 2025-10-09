import can
import cantools
import time
from typing import Dict, Any

class CANMessageSender:
    # (이전과 동일한 CANMessageSender 클래스 내용)
    def __init__(self, dbc_file_path: str, can_interface: str, channel: str, bitrate: int):
        try:
            self.db = cantools.database.load_file(dbc_file_path)
            print(f"✅ DBC 파일 로드 성공: {dbc_file_path}")
            self.bus = can.interface.Bus(channel=channel, interface=can_interface, bitrate=bitrate)
            print(f"✅ CAN 버스 초기화 성공: {can_interface} on {channel} @ {bitrate}bps")
        except Exception as e:
            print(f"❌ 초기화 오류: {e}")
            raise
    
    def send_message(self, message_name: str, signal_values: Dict[str, Any]) -> bool:
        try:
            message = self.db.get_message_by_name(message_name)
            data = message.encode(signal_values)
            can_msg = can.Message(arbitration_id=message.frame_id, data=data, is_extended_id=False)
            self.bus.send(can_msg)
            return True
        except Exception as e:
            if isinstance(e, KeyError):
                print(f"❌ '{message_name}' 인코딩 오류: DBC에 '{e.args[0]}' 신호가 없습니다. 이름을 확인하세요.")
            else:
                print(f"❌ '{message_name}' 전송 중 오류: {e}")
            return False
    
    def close(self) -> None:
        if hasattr(self, 'bus') and self.bus is not None:
            self.bus.shutdown()
            print("✅ CAN 버스 연결이 안전하게 종료되었습니다.")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

def main():
    """
    메인 실행 함수: 여러 필수 메시지를 함께 전송하여 버스를 활성화하고,
    '최종 수정된 신호 이름'으로 오른쪽 방향지시등 점등을 테스트합니다.
    """
    # ============================ 사용자 설정 ============================
    DBC_FILE_PATH = "Temp_DBC.dbc"
    CAN_INTERFACE = "slcan"
    CHANNEL = "COM14"
    BITRATE = 500000
    # =================================================================

    try:
        with CANMessageSender(DBC_FILE_PATH, CAN_INTERFACE, CHANNEL, BITRATE) as sender:
            print("\n" + "="*50)
            print("테스트 시작: 최종 수정된 신호 이름으로 재시도합니다.")
            print("프로그램을 중지하려면 Ctrl+C를 누르세요.")
            print("="*50 + "\n")

            bcm_07_signals = {
                'BCM_Crc7Val': 171, 'BCM_AlvCnt7Val': 3, 'Lamp_DedicatedDrlOnReq': 0,
                'Lamp_HiPrioHzrdReq': 0, 'Lamp_LoPrioHzrdReq': 0, 'Lamp_IntTailLmpOnReq': 0,
                'Lamp_ExtrnlTailLmpOnReq': 0, 'Lamp_HdLmpLoOnReq': 0, 'Lamp_HdLmpHiOnReq': 0,
                'Lamp_AvTailLmpSta': 0, 'Lamp_ExtrnlLpWlcmSta': 0
            }
            
            icu_04_signals = {
                'ExtLamp_TrnSigLmpLftBlnkngSta': 0,
                'ExtLamp_TrnSigLmpRtBlnkngSta': 0,
                'ExtLamp_ExtrnlTailLmpSta': 0,
                'ExtLamp_HzrdSwSta': 0,
                'ExtLamp_RrFgLmpSta': 0,
                'IntLamp_InlTailLmpSta': 0,
                'Lamp_TrnSigLmpLftOnReq': 0,      
                'Lamp_TrnSigLmpRtOnReq': 0      
            }

            bcm_08_signals = {
                'BCM_Crc8Val': 0, 'BCM_AlvCnt8Val': 0, 'Lamp_HbaCtrlModTyp': 0,
                'Lamp_IFSCtrlModTyp': 3, 'Lamp_RrFogLmpOnReq': 0, 'Lamp_TailLmpWlcmCmd': 0,
                'Lamp_HdLmpWlcmCmd': 0, 'Lamp_PuddleLmpOnReq': 0
            }

            counter = 3
            while True:
                bcm_07_signals['BCM_AlvCnt7Val'] = counter
                sender.send_message('BCM_07_200ms', bcm_07_signals)
                
                sender.send_message('ICU_04_200ms', icu_04_signals)
                
                bcm_08_signals['BCM_AlvCnt8Val'] = counter % 8
                sender.send_message('BCM_08_200ms', bcm_08_signals)

                print(f"\r✅ 3개 메시지 동시 전송 성공! | RightTurnReq: {icu_04_signals['Lamp_TrnSigLmpRtOnReq']}", end="")
                
                counter = (counter + 1) % 16
                time.sleep(0.2)
                
    except KeyboardInterrupt:
        print("\n\n⏹️ 사용자가 전송을 중단했습니다.")
    except Exception as e:
        print(f"\n❌ 프로그램 실행 중 오류가 발생했습니다: {e}")

if __name__ == "__main__":
    main()
