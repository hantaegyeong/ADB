import can

bus = can.interface.Bus(bustype="slcan", channel="COM14", bitrate=500000)

try:

    msg = can.Message(arbitration_id=0x123, data=[0x11, 0x22, 0x33], is_extended_id=False)
    bus.send(msg)
    print("✅ 메시지 송신 완료")

    print("📡 수신 대기 중...")
    while True:
        message = bus.recv(timeout=5.0)  
        if message is None:
            print("⚠️ 수신된 메시지가 없습니다.")
            break
        else:
            print(f"📥 수신: ID=0x{message.arbitration_id:X}, Data={message.data.hex().upper()}")

finally:

    bus.shutdown()
    print("🔌 CAN Bus 종료 완료")
