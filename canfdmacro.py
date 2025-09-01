import can
import time
import random
import serial

def main():
    """메인 실행 함수"""
    bus = None
    com_port = 'COM14' # 장치 관리자에서 확인한 COM 포트 번호

    try:
        bus = can.interface.Bus(
            interface='slcan',
            channel=com_port,
            fd=True,            # CAN FD 모드 활성화 시도
            bitrate=500000,     # Nominal Bitrate
            data_bitrate=2000000 # Data Bitrate
        )
        print(f"CANable 버스가 'slcan' 방식을 통해 {com_port}에서 CAN FD 모드로 초기화되었습니다.")
        print("랜덤 CAN FD 메시지 전송을 시작합니다. (Ctrl+C를 눌러 중지)")

        DLC_TO_BYTES = [0, 1, 2, 3, 4, 5, 6, 7, 8, 12, 16, 20, 24, 32, 48, 64]
        while True:
            random_id = random.randint(0x000, 0x7FF)
            random_dlc = random.randint(0, 15)
            data_length = DLC_TO_BYTES[random_dlc]
            random_data = [random.randint(0, 255) for _ in range(data_length)]

            msg = can.Message(
                arbitration_id=random_id,
                is_extended_id=False,
                is_fd=True,
                dlc=random_dlc,
                data=random_data
            )
            try:
                bus.send(msg)
                hex_data = ' '.join(f'{byte:02X}' for byte in msg.data)
                print(f"ID: {msg.arbitration_id:03X}  DLC: {msg.dlc} ({len(msg.data)} bytes)  DATA: {hex_data}")
            except can.CanError as e:
                print(f"메시지 전송 실패: {e}")
            time.sleep(0.01)

    except (can.CanError, serial.SerialException) as e:
        print(f"CAN 버스 초기화 실패: {e}")
    except KeyboardInterrupt:
        print("\n프로그램을 종료합니다.")
    finally:
        if bus:
            bus.shutdown()
            print("CAN 버스가 종료되었습니다.")

if __name__ == "__main__":
    main()
