import struct

def calculate_crc8(data, poly, init, xor_out):
    crc = init
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = (crc << 1) ^ poly
            else:
                crc <<= 1
            crc &= 0xFF
    return crc ^ xor_out

# 로그에서 확인된 0x413 샘플 데이터 (Byte 0: Target CRC, Byte 1~7: Payload)
samples = [
    [0x18, 0x80, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
    [0x54, 0x90, 0x00, 0x41, 0x00, 0x00, 0x00, 0x00],
    [0x77, 0xA0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
    [0x3B, 0xB0, 0x00, 0x41, 0x00, 0x00, 0x00, 0x00],
    [0xC6, 0xC0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
]

print("Analyzing CRC parameters for CAN ID 0x413...")
print("-" * 60)

found = False

# 1. 다항식(Polynomial) 탐색 (0x00 ~ 0xFF)
# CRC의 선형성(Linearity)을 이용: CRC(A) ^ CRC(B) == CRC(A ^ B) (Init=0, Xor=0일 때)
for poly in range(256):
    is_poly_valid = True
    
    # 샘플 간의 차이를 이용해 Poly 검증
    for i in range(len(samples) - 1):
        target_a = samples[i][0]
        payload_a = samples[i][1:]
        
        target_b = samples[i+1][0]
        payload_b = samples[i+1][1:]
        
        # 두 데이터의 XOR 차이 계산
        payload_diff = [a ^ b for a, b in zip(payload_a, payload_b)]
        target_diff = target_a ^ target_b
        
        # Init=0, Xor=0 상태에서 차이값에 대한 CRC 계산
        calc_diff = calculate_crc8(payload_diff, poly, 0, 0)
        
        if calc_diff != target_diff:
            is_poly_valid = False
            break
    
    # 2. 다항식이 맞다면, 상수 오프셋(Init/Xor 조합) 찾기
    if is_poly_valid:
        # 첫 번째 샘플을 기준으로 오프셋 역산
        # Target = CRC(Payload, Poly, 0, 0) ^ Offset
        # Offset = Target ^ CRC(Payload, Poly, 0, 0)
        
        base_crc = calculate_crc8(samples[0][1:], poly, 0, 0)
        offset = samples[0][0] ^ base_crc
        
        # 찾아낸 파라미터(Poly, Offset)로 모든 샘플 검증
        all_match = True
        for sample in samples:
            target = sample[0]
            payload = sample[1:]
            # 여기서 offset은 Init이나 XOR Out 중 하나로 처리 가능합니다.
            # 계산의 편의를 위해 Init=0, XorOut=offset 으로 가정하고 검증합니다.
            if calculate_crc8(payload, poly, 0, offset) != target:
                all_match = False
                break
        
        if all_match:
            print(f"[SUCCESS] MATCH FOUND!")
            print(f"  Polynomial : 0x{poly:02X}")
            print(f"  XOR Offset : 0x{offset:02X} (Combination of Init & Final XOR)")
            print(f"  Formula    : CRC = CRC8(Data, Poly=0x{poly:02X}, Init=0x00) ^ 0x{offset:02X}")
            print("-" * 60)
            
            # 파이썬 코드로 바로 쓸 수 있는 형태 출력
            print("Python Implementation:")
            print(f"def get_checksum_413(data):")
            print(f"    crc = 0x00")
            print(f"    poly = 0x{poly:02X}")
            print(f"    for byte in data:")
            print(f"        crc ^= byte")
            print(f"        for _ in range(8):")
            print(f"            if crc & 0x80: crc = (crc << 1) ^ poly")
            print(f"            else: crc <<= 1")
            print(f"            crc &= 0xFF")
            print(f"    return crc ^ 0x{offset:02X}")
            found = True
            break # 하나 찾으면 종료

if not found:
    print("[FAIL] Could not find a matching CRC-8 algorithm.")
    print("Possibilities:")
    print("1. Not a standard CRC-8 (e.g., Sum, XOR, or includes CAN ID in calculation).")
    print("2. Bit order is reversed (LSB First).")
