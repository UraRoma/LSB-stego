from PIL import Image
from typing import List, Tuple


# ==============================
# Utilities
# ==============================

def derive_seed_from_password(password: str) -> int:
    """Простейшая некриптографическая деривация 32-bit seed из пароля."""
    seed = 0
    for i, ch in enumerate(password):
        seed ^= (ord(ch) << (i % 24))
        seed &= 0xFFFFFFFF
    return seed if seed != 0 else 0xDEADBEEF


class SimplePRNG:
    """LCG: X_{n+1} = (a * X_n + c) mod 2^32. Только для детерминированности."""
    def __init__(self, seed: int):
        self.state = seed & 0xFFFFFFFF

    def next_u32(self) -> int:
        self.state = (1103515245 * self.state + 12345) & 0xFFFFFFFF
        return self.state


def load_image(image_path: str) -> Tuple[Image.Image, any, int, int, str]:
    """
    Загружает изображение, конвертирует в RGB/RGBA и возвращает (img, pixels, w, h, fmt).
    Поддерживаются только BMP и PNG.
    """
    img = Image.open(image_path)
    file_format = (img.format or "UNKNOWN").upper()

    if file_format not in ("BMP", "PNG"):
        raise ValueError(f"Поддерживаются только BMP и PNG. Получен формат: {file_format}")

    # Нормализуем режим: используем RGB или RGBA (если был альфа, оставляем)
    if img.mode in ("RGB", "RGBA"):
        pass
    elif img.mode in ("L", "P"):
        img = img.convert("RGB")
    else:
        raise ValueError(f"Неподдерживаемый цветовой режим: {img.mode}")

    pixels = img.load()
    width, height = img.size
    return img, pixels, width, height, file_format


def compute_local_complexity(pixels, x: int, y: int, width: int, height: int) -> int:
    """
    Простая локальная сложность: сумма абсолютных разностей с 4 соседями по первым 3 каналам.
    Работает и для RGB, и для RGBA (игнорирует альфу).
    """
    def clamp(v, lo, hi):
        return max(lo, min(v, hi))

    cx = clamp(x, 1, width - 2)
    cy = clamp(y, 1, height - 2)
    center = pixels[cx, cy]
    if not isinstance(center, (tuple, list)):
        center = (center, center, center)
    complexity = 0
    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nb = pixels[cx + dx, cy + dy]
        if not isinstance(nb, (tuple, list)):
            nb = (nb, nb, nb)
        for c in range(3):
            complexity += abs(int(nb[c]) - int(center[c]))
    return complexity


# ==============================
# Embedding
# ==============================

def embed_message_bits(
    input_path: str,
    output_path: str,
    message_bits: List[int],
    password: str,
    complexity_threshold: int,
    max_attempt_factor: int = 4
) -> None:
    img, pixels, width, height, file_format = load_image(input_path)

    # Определяем число каналов (на пиксель) и usable_channels (игнорируем alpha)
    sample = pixels[0, 0]
    num_channels = len(sample) if isinstance(sample, (tuple, list)) else 1
    # Если RGBA, мы используем только первые 3 (RGB)
    usable_channels = 3 if num_channels >= 3 else num_channels

    total_pixels = width * height
    total_capacity_bits = total_pixels * usable_channels

    if len(message_bits) > total_capacity_bits:
        raise ValueError(f"Сообщение ({len(message_bits)} бит) не помещается в изображение ({total_capacity_bits} бит).")

    seed = derive_seed_from_password(password)
    prng = SimplePRNG(seed)

    embedded = 0
    used_positions = set()
    attempts = 0
    max_attempts = total_capacity_bits * max_attempt_factor

    while embedded < len(message_bits) and attempts < max_attempts:
        attempts += 1
        pos_rand = prng.next_u32()
        pos = pos_rand % total_capacity_bits  # индекс в диапазоне [0, total_capacity_bits-1]

        # вычисляем координаты и канал (только RGB)
        pixel_index = pos // usable_channels
        channel_index = pos % usable_channels
        x = pixel_index % width
        y = pixel_index // width

        # фильтр сложности — если низкая, пропускаем
        if compute_local_complexity(pixels, x, y, width, height) < complexity_threshold:
            continue

        # если позиция уже использована — пропускаем
        if pos in used_positions:
            continue

        # готовим значение канала
        pix = pixels[x, y]
        pix_list = list(pix) if isinstance(pix, (tuple, list)) else [pix]
        current = int(pix_list[channel_index])
        target_bit = int(message_bits[embedded])
        current_lsb = current & 1

        if current_lsb != target_bit:
            # LSB matching (±1) — выбираем направление детерминированно из PRNG
            if current == 0:
                new_value = 1
            elif current == 255:
                new_value = 254
            else:
                # следующий вызов PRNG решает направление
                new_value = current + (1 if (prng.next_u32() & 1) else -1)
            pix_list[channel_index] = new_value
            # если картинка была RGBA, сохраняем альфу как было
            pixels[x, y] = tuple(pix_list)
        else:
            # ничего менять не нужно, но всё равно считаем бит внедрённым (LSB уже совпадает)
            pass

        used_positions.add(pos)
        embedded += 1

    if embedded < len(message_bits):
        raise RuntimeError(f"Не удалось внедрить все биты: embedded={embedded}, required={len(message_bits)}, attempts={attempts}")

    # Сохраняем
    # Для PNG предпочтительно compress_level=0,
    # для BMP просто сохраняем
    save_kwargs = {}
    if file_format == "PNG":
        save_kwargs["compress_level"] = 0
    img.save(output_path, **save_kwargs)
    print(f"[+] Внедрено {embedded} бит в {output_path} (attempts={attempts})")


# ==============================
# Extraction
# ==============================

def extract_message_bits(
    input_path: str,
    num_bits: int,
    password: str,
    complexity_threshold: int,
    max_attempt_factor: int = 4
) -> List[int]:
    """
    Извлекает num_bits бит, предполагая те же параметры PRNG/password и порог сложности.
    Читает LSB в том же порядке, в котором они могли быть внедрены.
    """
    img, pixels, width, height, file_format = load_image(input_path)

    sample = pixels[0, 0]
    num_channels = len(sample) if isinstance(sample, (tuple, list)) else 1
    usable_channels = 3 if num_channels >= 3 else num_channels

    total_pixels = width * height
    total_capacity_bits = total_pixels * usable_channels

    if num_bits > total_capacity_bits:
        raise ValueError("Запрошено слишком много бит для извлечения.")

    seed = derive_seed_from_password(password)
    prng = SimplePRNG(seed)

    extracted: List[int] = []
    attempts = 0
    max_attempts = total_capacity_bits * max_attempt_factor
    used_positions = set()

    while len(extracted) < num_bits and attempts < max_attempts:
        attempts += 1
        pos_rand = prng.next_u32()
        pos = pos_rand % total_capacity_bits
        pixel_index = pos // usable_channels
        channel_index = pos % usable_channels
        x = pixel_index % width
        y = pixel_index // width

        if compute_local_complexity(pixels, x, y, width, height) < complexity_threshold:
            continue
        if pos in used_positions:
            continue

        pix = pixels[x, y]
        pix_list = list(pix) if isinstance(pix, (tuple, list)) else [pix]
        bit = int(pix_list[channel_index]) & 1
        extracted.append(bit)
        used_positions.add(pos)

    if len(extracted) < num_bits:
        raise RuntimeError(f"Не удалось извлечь запрошенные биты: extracted={len(extracted)}, attempts={attempts}")

    print(f"[+] Извлечено {len(extracted)} бит (attempts={attempts})")
    return extracted


# ==============================
# Helpers: bits <-> bytes
# ==============================

def bytes_to_bits(data: bytes) -> List[int]:
    bits: List[int] = []
    for b in data:
        for i in range(7, -1, -1):
            bits.append((b >> i) & 1)
    return bits

def bits_to_bytes(bits: List[int]) -> bytes:
    # доводим до кратности 8 нулями, если нужно
    padded = bits.copy()
    while len(padded) % 8 != 0:
        padded.append(0)
    out = bytearray()
    for i in range(0, len(padded), 8):
        byte = 0
        for j in range(8):
            byte = (byte << 1) | (padded[i + j] & 1)
        out.append(byte)
    return bytes(out)


# ==============================
# Пример использования
# ==============================

if __name__ == "__main__":
    mode = int(input("1) Вы хотите внедрить сообщение?\n2) Вы хотите извлечь сообщение?\nВведите 1 или 2 или 12: "))
    if mode == 1 or mode == 12:
        password = input("[*] Какой пароль использовать? ")
        text = input("[*] Какой текст внедрить? ")
        in_path = input("[*] Какой контейнер использовать? ") # положи подходящий BMP/PNG в эту папку
    elif mode == 2:
        password_temp = input("[*] Какой пароль использовать? ")
        out_path = input("[*] Из какого контейнера извлечь? ")
    
    if mode == 1 or mode == 12:
        out_path = "stego_out.png" if in_path.lower().endswith(".png") else "stego_out.bmp"
        data = text.encode("utf-8")
        bits = bytes_to_bits(data)
        password_temp = password + '_' + str(len(bits))
        
    if mode == 1 or mode == 12:
        print("[*] Начинаю внедрение...")
        embed_message_bits(
            input_path=in_path,
            output_path=out_path,
            message_bits=bits,
            password=password,
            complexity_threshold=20
        )
        print("[+] Передайте этот ключ тому кто будет расшифровывать сообщение: ")
        print(password_temp)
          
    if mode == 2 or mode == 12:
        print("[*] Пытаюсь извлечь...")
        
        password_temp, count = password_temp.rsplit("_", 1)
        count = int(count)
            
        extracted_bits = extract_message_bits(
            input_path=out_path,
            num_bits=count,
            password=password_temp,
            complexity_threshold=20
        )
        extracted_bytes = bits_to_bytes(extracted_bits)
        try:
            extracted_text = extracted_bytes.decode("utf-8", errors="replace")
        except Exception:
            extracted_text = "<decode error>"


        print(f"[+] Извлечённый текст: {extracted_text!r}")
    time.sleep(5)
