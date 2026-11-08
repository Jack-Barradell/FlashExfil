import os
import sys
import argparse
import time
import ctypes

if sys.platform != "win32":
    import pyautogui

INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008
MAPVK_VK_TO_VSC = 0

VK_TAB = 0x09
VK_RETURN = 0x0D
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_DELETE = 0x2E

WRITE_PAUSE = 0.1

class KeyboardInput(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_size_t),
    ]

class MouseInput(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_size_t),
    ]

class InputUnion(ctypes.Union):
    _fields_ = [("ki", KeyboardInput), ("mi", MouseInput)]

class Input(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("union", InputUnion)]

class Point(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class WindowsTyper:
    def __init__(self, unicode_mode):
        self.unicode_mode = unicode_mode
        self.user32 = ctypes.windll.user32

        self.user32.VkKeyScanW.argtypes = [ctypes.c_wchar]
        self.user32.VkKeyScanW.restype = ctypes.c_short
        self.user32.MapVirtualKeyW.argtypes = [ctypes.c_uint, ctypes.c_uint]
        self.user32.MapVirtualKeyW.restype = ctypes.c_uint
        self.user32.SendInput.argtypes = [ctypes.c_uint, ctypes.POINTER(Input), ctypes.c_int]
        self.user32.SendInput.restype = ctypes.c_uint
        self.user32.GetCursorPos.argtypes = [ctypes.POINTER(Point)]

    def send(self, scan, flags):
        event = Input(type=INPUT_KEYBOARD)
        event.union.ki = KeyboardInput(wVk=0, wScan=scan, dwFlags=flags)
        self.user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(event))

    def key_down(self, vk, flags=0):
        scan = self.user32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC)
        self.send(scan, KEYEVENTF_SCANCODE | flags)

    def key_up(self, vk, flags=0):
        scan = self.user32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC)
        self.send(scan, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP | flags)

    def tap(self, vk, flags=0):
        self.key_down(vk, flags)
        self.key_up(vk, flags)

    def write_unicode(self, char):
        self.send(ord(char), KEYEVENTF_UNICODE)
        self.send(ord(char), KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)

    def write_char(self, char):
        if char == "\n":
            self.tap(VK_RETURN)
            return

        if char == "\t":
            self.tap(VK_TAB)
            return

        if self.unicode_mode:
            self.write_unicode(char)
            return

        result = self.user32.VkKeyScanW(char)
        if result == -1:
            self.write_unicode(char)
            return

        vk = result & 0xFF
        shift_state = (result >> 8) & 0xFF

        if self.user32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC) == 0:
            self.write_unicode(char)
            return

        modifiers = []
        if shift_state & 1:
            modifiers.append(VK_SHIFT)
        if shift_state & 2:
            modifiers.append(VK_CONTROL)
        if shift_state & 4:
            modifiers.append(VK_MENU)

        for modifier in modifiers:
            self.key_down(modifier)
        self.tap(vk)
        for modifier in reversed(modifiers):
            self.key_up(modifier)

    def mouse_in_corner(self):
        point = Point()
        self.user32.GetCursorPos(ctypes.byref(point))
        return point.x == 0 and point.y == 0

    def write(self, text, interval):
        for char in text:
            if self.mouse_in_corner():
                print("[!] Mouse moved to the top left corner, typing aborted")
                sys.exit(1)

            self.write_char(char)
            if interval:
                time.sleep(interval)

        time.sleep(WRITE_PAUSE)

    def press_delete(self):
        self.tap(VK_DELETE, KEYEVENTF_EXTENDEDKEY)


class PyAutoGuiTyper:
    def write(self, text, interval):
        pyautogui.write(text, interval)

    def press_delete(self):
        pyautogui.press('delete')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--file", help="Input file to type", required=True)
    parser.add_argument("-c", "--chunk", help="Chunk typing file content, for use if typing large files", action="store_true")
    parser.add_argument("-cs", "--chunk-size", help="Number of characters per chunk for use with --chunk (Default = 100, Minimum = 1)")
    parser.add_argument("-d", "--delay", help="Delay before typing starts in seconds (Default = 5, Minimum = 1)")
    parser.add_argument("-i", "--interval", help="Interval between key presses (Default = 0, Minimum = 0)")
    parser.add_argument("-m", "--mode", help="Windows only, keys sends key presses for the local keyboard layout, unicode sends characters directly (Default = keys)")

    args = parser.parse_args()

    if not os.path.isfile(args.file):
        print("[!] File not found: {}".format(args.file))
        sys.exit(1)

    if args.delay and int(args.delay) >= 1:
        wait_time = int(args.delay)
    else:
        wait_time = 5

    if args.interval and float(args.interval) >= 0:
        interval = float(args.interval)
    else:
        interval = 0

    if args.chunk_size:
        if not args.chunk:
            print("[!] Must specify -c or --chunk to use chunk size")
            sys.exit(1)
        if int(args.chunk_size) < 1:
            print("[!] Chunk size must be at least 1")
            sys.exit(1)
        chunk_size = int(args.chunk_size)
    else:
        chunk_size = 100

    if args.mode and args.mode not in ("keys", "unicode"):
        print("[!] Mode must be either keys or unicode")
        sys.exit(1)

    unicode_mode = args.mode == "unicode"

    if sys.platform == "win32":
        typer = WindowsTyper(unicode_mode)
    else:
        if unicode_mode:
            print("[!] Unicode mode is only available on Windows")
            sys.exit(1)
        typer = PyAutoGuiTyper()

    print("[+] Typing starts in {} seconds".format(wait_time))
    print("[*] Make sure your target window has focus")
    print("[*] Move the mouse to the top left corner of the screen to abort")

    slept = 0
    while slept < wait_time:
        time.sleep(1)
        slept += 1

    print("[+] Typing starting")
    with open(args.file, "r", encoding="utf-8") as f:
        if args.chunk:
            done = False
            while not done:
                read = 0
                chunk_list = []
                while read < chunk_size:
                    c = f.read(1)
                    if not c:
                        done = True
                        break
                    chunk_list.append(c)
                    read += 1
                chunk_string = ''.join(chunk_list)
                typer.write(chunk_string, interval)
        else:
            typer.write(f.read(), interval)
    typer.press_delete()
    print("[+] Typing complete")

if __name__ == '__main__':
    main()
