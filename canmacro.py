import can
import time
import random
import os

def main():
    bus = None
    try:
        # 클래식 CAN 모드로 PCAN-USB 버스 초기화 ---
        bus = can.interface.Bus(
            bustype='pcan',
            channel='PCAN_USBBUS1',
            state=can.BusState.ACTIVE,
            # fd=True 와 data_bitrate 옵션 제거
            bitrate=500000  # 클래식 CAN 통신 속도 (500kbit/s)
        )
        print("PCAN 버스가 python-can을 통해 클래식 CAN 모드로 초기화되었습니다.")
        print("랜덤 CAN 메시지 전송을 시작합니다. (Ctrl+C를 눌러 중지)")

        while True:
            # python-can 방식으로 메시지 생성
            random_id = random.randint(0x000, 0x7FF)
            
            data_length = random.randint(0, 8)
            random_data = [random.randint(0, 255) for _ in range(data_length)]

            msg = can.Message(
                arbitration_id=random_id,
                is_extended_id=False,
                # is_fd=True 옵션 제거
                dlc=data_length,
                data=random_data
            )

            try:
                # python-can 방식으로 메시지 전송
                bus.send(msg)
                hex_data = ' '.join(f'{byte:02X}' for byte in msg.data)
                print(f"ID: {msg.arbitration_id:03X}  DLC: {msg.dlc}  DATA: {hex_data}")
            except can.CanError as e:
                print(f"메시지 전송 실패: {e}")

            time.sleep(0.005)

    except can.CanError as e:
        print(f"CAN 버스 초기화 실패: {e}")
    except KeyboardInterrupt:
        print("\n프로그램을 종료합니다.")
    finally:
        if bus:
            # python-can 방식으로 버스를 종료합니다.
            bus.shutdown()
            print("CAN 버스가 종료되었습니다.")

if __name__ == "__main__":
    main()
