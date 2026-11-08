import tkinter as tk
from tkinter import messagebox
import mss
import imageio.v2 as imageio
import numpy as np
from PIL import Image
import time
import argparse
import sys

MIN_REGION_WIDTH = 70
MIN_REGION_HEIGHT = 45

def set_dpi_awareness():
    if sys.platform != "win32":
        return

    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        ctypes.windll.user32.SetProcessDPIAware()

class ScreenSelector:
    def __init__(self):
        set_dpi_awareness()

        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.attributes('-alpha', 0.3)
        
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        geometry_string = "{}x{}+0+0".format(screen_width, screen_height)
        self.root.geometry(geometry_string)

        self.root.configure(bg='grey')
        
        self.canvas = tk.Canvas(
            self.root, 
            #cursor="cross",
            #bg='grey',
            highlightthickness=0,
            width=screen_width,
            height=screen_height
        )
        self.canvas.pack()
    
        self.start_x = None
        self.start_y = None
        self.start_root_x = None
        self.start_root_y = None
        self.rect = None
        self.region = None
        
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.root.bind("<Escape>", self.on_cancel)
        self.root.focus_force()
    
    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        self.start_root_x = event.x_root
        self.start_root_y = event.y_root
        
        self.rect = self.canvas.create_rectangle(
            self.start_x, self.start_y, 
            self.start_x, self.start_y,
            outline='red', 
            width=3
        )
    
    def on_drag(self, event):
        if self.rect:
            self.canvas.coords(
                self.rect,
                self.start_x, self.start_y,
                event.x, event.y
            )
    
    def on_cancel(self, event):
        self.region = None
        self.root.withdraw()
        self.root.quit()

    def on_release(self, event):
        if self.rect is None:
            return

        end_x = event.x_root
        end_y = event.y_root
        
        left = min(self.start_root_x, end_x)
        top = min(self.start_root_y, end_y)
        width = abs(end_x - self.start_root_x)
        height = abs(end_y - self.start_root_y)
        
        self.region = {
            "top": top,
            "left": left,
            "width": width,
            "height": height
        }
        
        self.root.withdraw()
        self.root.quit()
    
    def get_region(self):
        self.root.mainloop()
        self.root.destroy()
        return self.region


class ScreenRecorder:
    def __init__(self, region, output_file, fps):
        self.region = region
        self.output_file = output_file
        self.fps = fps
        
    def record(self):
        
        with mss.MSS() as sct:
            with imageio.get_writer(
                self.output_file, 
                format='FFMPEG',
                fps=self.fps,
                codec='libx264',
                quality=10,
                pixelformat='yuv444p',
                macro_block_size=1,
                ffmpeg_params=['-preset', 'ultrafast']
            ) as writer:
                start_time = time.perf_counter()
                frame_count = 0
                
                try:
                    while True:
                        img = sct.grab(self.region)
                        frame = Image.frombytes('RGB', img.size, img.bgra, 'raw', 'BGRX')
                        writer.append_data(np.array(frame))
                        
                        frame_count += 1
                        elapsed = time.perf_counter() - start_time
                        
                        expected_time = frame_count / self.fps
                        sleep_time = expected_time - elapsed
                        if sleep_time > 0:
                            time.sleep(sleep_time)
                except KeyboardInterrupt:
                    elapsed = time.perf_counter() - start_time
                    print("[*] Recording stopped")
                    if elapsed > 0:
                        print("[*] Recorded {} frames at an average of {:.1f} FPS".format(frame_count, frame_count / elapsed))
                    return
                


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-o", "--output", help="Path to save output file (Default = canvas_recording.mp4)")
    parser.add_argument("-fps", "--recording-fps", help="Target FPS for recording (Default = 120)")
    parser.add_argument("-d", "--delay", help="Delay before recording starts in seconds (Default = 5, Minimum = 1)")

    args = parser.parse_args()

    if args.output:
        output_file = args.output
    else:
        output_file = "canvas_recording.mp4"

    if args.recording_fps:
        fps_target = int(args.recording_fps)
    else:
        fps_target = 120

    if args.delay and int(args.delay) >= 1:
        recording_delay = int(args.delay)
    else:
        recording_delay = 5

    print("[+] Drag to select region to record")
    print("[*] Start in the top left, drag to bottom right")

    screen_selector = ScreenSelector()
    selected_region = screen_selector.get_region()

    if selected_region is None:
        print('[-] Canceled selection')
        sys.exit(0)

    if selected_region["width"] < MIN_REGION_WIDTH or selected_region["height"] < MIN_REGION_HEIGHT:
        print("[-] Selected region is too small, it must be at least {}x{}".format(MIN_REGION_WIDTH, MIN_REGION_HEIGHT))
        sys.exit(1)

    print("[+] Region selected")
    print("[+] Press enter to continue...")
    input()
    print("[+] Recording starting in {} seconds".format(recording_delay))
    print("[*] Ensure target region only contains the grid")

    recorder = ScreenRecorder(selected_region, output_file, fps_target)

    slept = 0
    while slept < recording_delay:
        time.sleep(1)
        slept += 1

    print("[+] Started recording")
    print("[*] Press Ctrl-C to end recording")

    recorder.record()
    
    print("[+] Recording complete")


if __name__ == "__main__":
    main()